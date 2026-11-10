"""Homework Coach backend routes for the Desktop panel → ``/api/plugins/homework-coach/``.

Thin FastAPI shell over ``homework_coach.panel``. Mounted by Hermes only when the
plugin is in ``plugins.enabled``. No network calls, no credentials, no shell: it
reads/writes the plugin's own data directory and reuses the agent tool handlers.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

PLUGIN_ID = "homework-coach"
_PKG_DIR = Path(__file__).resolve().parent.parent / "homework_coach"
_PKG_NAME = "_homework_coach_dashboard_pkg"  # private name: never shadows a core module


def _load_pkg():
    """Import the sibling ``homework_coach`` package without touching ``sys.path``."""
    if _PKG_NAME in sys.modules:
        return sys.modules[_PKG_NAME]
    spec = importlib.util.spec_from_file_location(
        _PKG_NAME, _PKG_DIR / "__init__.py", submodule_search_locations=[str(_PKG_DIR)])
    if spec is None or spec.loader is None:
        raise ImportError("homework_coach package not found beside dashboard/")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_PKG_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(_PKG_NAME, None)
        raise
    return mod


def _modules():
    """(panel, tools, config) submodules of the privately-loaded package."""
    _load_pkg()
    return (importlib.import_module(f"{_PKG_NAME}.panel"), importlib.import_module(f"{_PKG_NAME}.tools"),
            importlib.import_module(f"{_PKG_NAME}.config"))


def _setting(key: str, default: Any = None) -> Any:
    """``plugins.entries.homework-coach.settings.<key>`` from the active profile's config."""
    from hermes_cli.config import load_config_readonly  # public plugin surface

    entries = ((load_config_readonly() or {}).get("plugins") or {}).get("entries") or {}
    entry = entries.get(PLUGIN_ID) or {}
    settings = entry.get("settings") if isinstance(entry.get("settings"), dict) else {}
    value = settings.get(key, default)
    return default if value is None else value


def _runtime():
    _, tools, _ = _modules()
    return tools.Runtime(get_setting=_setting, llm=_plugin_llm())


def _plugin_llm():
    """Host-owned LLM facade for photo intake (same object ``ctx.llm`` returns)."""
    try:
        from agent.plugin_llm import PluginLlm  # public: what PluginContext.llm hands out

        return PluginLlm(plugin_id=PLUGIN_ID)
    except Exception:  # older host: intake reports it cannot read photos
        return None


def _call(fn, *a, **kw):
    panel_mod, _, config_mod = _modules()
    try:
        return fn(*a, **kw)
    except panel_mod.PanelError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except config_mod.ConfigError as e:
        raise HTTPException(status_code=400, detail={"error": "family config invalid", "details": e.errors})
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"unknown child {e.args[0] if e.args else ''}".strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="family config not found")


router = APIRouter()


@router.get("/overview")
async def overview(packets: int = Query(5, ge=1, le=14)):
    panel_mod, _, _ = _modules()
    return await run_in_threadpool(lambda: _call(panel_mod.overview, _runtime(), packet_limit=packets))


@router.get("/packets")
async def list_packets(limit: int = Query(5, ge=1, le=14)):
    panel_mod, _, _ = _modules()
    return {"packets": await run_in_threadpool(lambda: _call(panel_mod.packets, _runtime(), limit=limit))}


@router.get("/packets/{packet_date}/{name}")
async def packet_file(packet_date: str, name: str):
    """Resolve one packet PDF to its absolute path (the Desktop saves it via the gateway file door)."""
    panel_mod, _, _ = _modules()
    p = await run_in_threadpool(lambda: _call(panel_mod.resolve_packet_file, _runtime(), packet_date, name))
    return {"path": str(p), "name": p.name, "size": p.stat().st_size}


@router.post("/feedback")
async def feedback(body: dict):
    panel_mod, _, _ = _modules()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    result = await run_in_threadpool(lambda: _call(
        panel_mod.record_feedback, _runtime(), str(body.get("child_id", "")), str(body.get("packet_date", "")),
        body.get("ratings"), str(body.get("note", ""))))
    return result


@router.post("/download")
async def download(body: dict):
    """Transfer a registered plugin artifact, not a terminal/SSH workspace file."""
    _load_pkg()
    artifacts = importlib.import_module(f"{_PKG_NAME}.downloads")
    rt = _runtime()
    payload = await run_in_threadpool(lambda: _call(
        artifacts.artifact_download, rt, _body(body).get("path")))
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


# -- workspace (Today · Class plan · Progress · History · Rate desk · Family) -------------------------
# Uploads arrive as base64 JSON: the Desktop's multipart door is refused on OAuth-gated connections.
def _ws():
    _load_pkg()
    return importlib.import_module(f"{_PKG_NAME}.workspace")


async def _run(fn_name: str, *a, **kw):
    ws = _ws()
    return await run_in_threadpool(lambda: _call(getattr(ws, fn_name), _runtime(), *a, **kw))


def _body(body: Any) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    return body


@router.get("/today")
async def ws_today():
    return await _run("today")


@router.post("/generate")
async def ws_generate(body: dict):
    b = _body(body)
    ids = b.get("child_ids")
    return await _run("generate", str(b.get("date") or "") or None,
                      [str(x) for x in ids] if isinstance(ids, list) else None)


# Slow model work (photo / newsletter reading) runs as a background job and is polled: hosted
# plugin requests are cut off after 60 s, and a careful homework read can take longer.
import contextvars as _cv
import threading as _th
import time as _time
import uuid as _uuid

_JOBS: dict[str, dict] = {}
_JOB_TTL = 30 * 60
_JOB_LOCK = _th.RLock()


def _job_scope(rt) -> tuple[str, str, str]:
    return (str(rt.store.root.resolve()), str(rt.store.packets_root.resolve()),
            str(rt._get("family_config", "") or ""))


def _start_job(fn, rt=None) -> dict:
    now = _time.time()
    owner = _job_scope(rt if rt is not None else _runtime())
    jid = _uuid.uuid4().hex
    with _JOB_LOCK:
        for k in [k for k, v in _JOBS.items() if now - v.get("at", now) > _JOB_TTL]:
            _JOBS.pop(k, None)
        _JOBS[jid] = {"status": "running", "at": now, "scope": owner}
    ctx = _cv.copy_context()  # keeps this request's profile / secret scope for the worker

    def work():
        try:
            finished = {"status": "done", "result": fn()}
        except HTTPException as e:
            d = e.detail
            msg = d if isinstance(d, str) else "; ".join([str(d.get("error", ""))] + [str(x) for x in d.get("details", [])]) if isinstance(d, dict) else str(d)
            finished = {"status": "error", "error": msg}
        except Exception as e:  # never leave a job running forever
            finished = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        with _JOB_LOCK:
            _JOBS[jid] = {**finished, "at": _time.time(), "scope": owner}

    _th.Thread(target=ctx.run, args=(work,), daemon=True, name=f"homework-coach-job-{jid}").start()
    return {"job": jid, "status": "running"}


@router.get("/jobs/{job_id}")
async def ws_job(job_id: str):
    scope = _job_scope(_runtime())
    with _JOB_LOCK:
        job = _JOBS.get(job_id)
        if job is None or job.get("scope") != scope or _time.time() - job.get("at", 0) > _JOB_TTL:
            raise HTTPException(status_code=404, detail="job not found in this profile (it may have expired)")
        payload = {k: v for k, v in job.items() if k not in {"at", "scope"}}
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@router.post("/intake64")
async def ws_intake64(body: dict):
    b = _body(body)
    ws = _ws()
    panel_mod, _, _ = _modules()
    data = await run_in_threadpool(lambda: _call(ws.decode_b64, b.get("data_b64", "")))
    rt = _runtime()
    # validate (type, size, child) before going async so mistakes come back immediately
    staged = await run_in_threadpool(lambda: _call(panel_mod.save_upload, rt, str(b.get("child_id", "")),
                                                   str(b.get("filename", "")), data))
    staged.unlink(missing_ok=True)
    child_id, filename, note = str(b.get("child_id", "")), str(b.get("filename", "")), str(b.get("note", ""))[:500]
    return _start_job(lambda: _call(panel_mod.intake_upload, rt, child_id, filename, data, note), rt)


@router.get("/children/{child_id}/class-plan")
async def ws_class_plan(child_id: str):
    return await _run("class_plan", child_id)


@router.post("/children/{child_id}/materials/read")
async def ws_material_read(child_id: str, body: dict):
    b = _body(body)
    ws = _ws()
    data = await run_in_threadpool(lambda: _call(ws.decode_b64, b.get("data_b64", "")))
    rt = _runtime()
    filename, note = str(b.get("filename", "")), str(b.get("note", ""))[:300]
    return _start_job(lambda: _call(ws.read_material, rt, child_id, filename, data, note), rt)


@router.post("/children/{child_id}/materials/apply")
async def ws_material_apply(child_id: str, body: dict):
    b = _body(body)
    mat = b.get("material") if isinstance(b.get("material"), dict) else {}
    exp = b.get("expected") if isinstance(b.get("expected"), dict) else None
    return await _run("apply_material", child_id, str(b.get("token", "")), mat, bool(b.get("apply_shift")), exp)


@router.get("/children/{child_id}/materials/{idx}/file")
async def ws_material_file(child_id: str, idx: int):
    return await _run("material_file", child_id, idx)


@router.post("/children/{child_id}/units/{idx}/undo")
async def ws_undo_shift(child_id: str, idx: int):
    return await _run("undo_shift", child_id, idx)


@router.get("/children/{child_id}/progress")
async def ws_progress(child_id: str, days: int = Query(30, ge=7, le=120)):
    return await _run("progress", child_id, days)


@router.get("/children/{child_id}/history")
async def ws_history(child_id: str):
    return await _run("history", child_id)


@router.get("/children/{child_id}/observations/{idx}")
async def ws_observation(child_id: str, idx: int):
    return await _run("observation", child_id, idx)


@router.post("/children/{child_id}/observations/{idx}/items/{item_n}")
async def ws_fix_reading(child_id: str, idx: int, item_n: int, body: dict):
    b = _body(body)
    return await _run("fix_reading", child_id, idx, item_n, b.get("fields") if isinstance(b.get("fields"), dict) else {})


@router.get("/children/{child_id}/research-prompt")
async def ws_research_prompt(child_id: str):
    return await _run("research_prompt", child_id)


@router.get("/packet/{packet_date}/{child_id}/preview")
async def ws_packet_preview(packet_date: str, child_id: str, page: int = Query(0, ge=0, le=50),
                            kind: str = Query("practice")):
    return await _run("packet_preview", packet_date, child_id, page, kind)


@router.post("/children/{child_id}/materials/propose")
async def ws_material_propose(child_id: str, body: dict):
    b = _body(body)
    return await _run("preview_proposal", child_id, b.get("material") if isinstance(b.get("material"), dict) else {})


@router.get("/packet/{packet_date}/{child_id}")
async def ws_packet(packet_date: str, child_id: str):
    return await _run("packet_detail", packet_date, child_id)


@router.post("/rate")
async def ws_rate(body: dict):
    b = _body(body)
    return await _run("rate", str(b.get("child_id", "")), str(b.get("packet_date", "")), b.get("ratings"),
                      str(b.get("note", ""))[:1000])


@router.get("/family")
async def ws_family():
    return await _run("family_settings")


@router.post("/family/children")
async def ws_add_child(body: dict):
    return await _run("add_child", _body(body))


@router.post("/family/children/{child_id}")
async def ws_update_child(child_id: str, body: dict):
    return await _run("update_child", child_id, _body(body))


@router.post("/family/children/{child_id}/archive")
async def ws_archive_child(child_id: str):
    return await _run("archive_child", child_id)


@router.post("/family/children/{child_id}/restore")
async def ws_restore_child(child_id: str):
    return await _run("restore_child", child_id)


@router.post("/family/schedule")
async def ws_schedule(body: dict):
    return await _run("update_schedule", _body(body))
