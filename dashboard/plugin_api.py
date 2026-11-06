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

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

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


@router.post("/intake")
async def intake(child_id: str = Query(..., min_length=1, max_length=40), note: str = Query("", max_length=500),
                 file: UploadFile = File(...)):
    panel_mod, _, _ = _modules()
    data = await file.read(panel_mod.MAX_UPLOAD_BYTES + 1)
    return await run_in_threadpool(lambda: _call(
        panel_mod.intake_upload, _runtime(), child_id, file.filename or "", data, note))
