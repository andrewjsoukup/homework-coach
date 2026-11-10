"""Desktop panel backend: panel service + dashboard/plugin_api.py router (card t_c3e9fbd8)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from homework_coach import panel
from homework_coach.storage import Store
from homework_coach.tools import Runtime

from .conftest import ROOT

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _rt(tmp_path: Path, family_file: Path | None) -> Runtime:
    settings = {"family_config": str(family_file) if family_file else str(tmp_path / "missing.yaml")}
    return Runtime(get_setting=lambda k, d=None: settings.get(k, d), store=Store(root=tmp_path / "data"))


def _write_packet(rt: Runtime, date: str, *, verified: bool = True) -> Path:
    d = rt.store.packet_dir(date)
    items = [
        {"id": "1", "skill": "multiplication-arrays", "format": "array -> equation", "prompt": "3 rows of 4 dots",
         "role": "target"},
        {"id": "2", "skill": "multiplication-arrays", "format": "equation -> array", "prompt": "Draw 2 x 5",
         "role": "target"},
        {"id": "3", "skill": "place-value", "format": "expanded form", "prompt": "Write 352 in expanded form",
         "role": "review", "optional": True},
    ]
    data = {"date": date, "verification": {"ok": verified},
            "children": {"nova": {"focus": "arrays", "items": items},
                         "pip": {"focus": "counting", "items": [{"id": "1", "skill": "counting-to-10",
                                                                 "format": "count and circle", "prompt": "Count"}]}}}
    (d / "packet.json").write_text(json.dumps(data), encoding="utf-8")
    for name in ("nova_practice.pdf", "pip_practice.pdf", "parent_key.pdf"):
        (d / name).write_bytes(b"%PDF-1.4\n%fixture\n")
    return d


# -- overview ----------------------------------------------------------------------------------
def test_overview_unconfigured(tmp_path):
    out = panel.overview(_rt(tmp_path, None))
    assert out["configured"] is False and out["children"] == [] and out["family_config"].endswith("missing.yaml")


def test_overview_bad_config_reports_errors(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("family_id: Not A Slug\nchildren: []\n", encoding="utf-8")
    out = panel.overview(_rt(tmp_path, bad))
    assert out["configured"] is False and out["config_errors"]


def test_overview_children_and_packets(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _write_packet(rt, "2026-11-02")
    _write_packet(rt, "2026-11-03", verified=False)
    out = panel.overview(rt)
    assert out["configured"] and out["family_id"] == "maple"
    assert [c["id"] for c in out["children"]] == ["nova", "pip"]
    nova = out["children"][0]
    assert nova["item_budget"] == 6 and nova["skills"] == [] and nova["anchor"] is None
    assert [p["date"] for p in out["packets"]] == ["2026-11-03", "2026-11-02"]  # newest first
    p = out["packets"][1]
    assert p["verified"] is True and out["packets"][0]["verified"] is False
    kinds = {(f["kind"], f["child_id"]) for f in p["files"]}
    assert kinds == {("practice", "nova"), ("practice", "pip"), ("parent_key", None)}
    assert [i["id"] for i in p["children"]["nova"]["items"]] == ["1", "2", "3"]
    assert p["children"]["nova"]["items"][2]["optional"] is True
    assert p["children"]["nova"]["rated"] is False


def test_feedback_updates_progress_view(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _write_packet(rt, "2026-11-02")
    _write_packet(rt, "2026-11-03")
    r1 = panel.record_feedback(rt, "nova", "2026-11-02", {"1": "I", "2": "I", "3": "S"}, "steady")
    assert r1["ok"], r1
    r2 = panel.record_feedback(rt, "nova", "2026-11-03", {"1": "I", "2": "I"})
    assert r2["ok"] and r2["changes"].get("multiplication-arrays") == "up"
    out = panel.overview(rt)
    nova = out["children"][0]
    arrays = next(s for s in nova["skills"] if s["skill"] == "multiplication-arrays")
    assert arrays["dims"]["scaffold"] == 2 and arrays["last_change"]["change"] == "up"
    assert arrays["recent"] == {"I": 4, "S": 0, "N": 0}
    assert nova["last_feedback"]["packet_date"] == "2026-11-03"
    assert next(p for p in out["packets"] if p["date"] == "2026-11-03")["children"]["nova"]["rated"] is True


def test_feedback_rejects_bad_input(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    with pytest.raises(panel.PanelError):
        panel.record_feedback(rt, "nova", "11/03/2026", {"1": "I"})
    with pytest.raises(panel.PanelError):
        panel.record_feedback(rt, "nova", "2026-11-03", {"1": "X"})
    with pytest.raises(panel.PanelError):
        panel.record_feedback(rt, "nova", "2026-11-03", {"../1": "I"})
    assert panel.record_feedback(rt, "ghost", "2026-11-03", {"1": "I"})["ok"] is False  # tool error, not raise


# -- packet files ------------------------------------------------------------------------------
def test_resolve_packet_file_stays_in_root(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    d = _write_packet(rt, "2026-11-02")
    assert panel.resolve_packet_file(rt, "2026-11-02", "parent_key.pdf") == (d / "parent_key.pdf").resolve()
    for date, name in [("2026-11-02", "../../family.yaml"), ("..", "x.pdf"), ("2026-11-02", "packet.json"),
                       ("2026-11-09", "parent_key.pdf"), ("2026-11-02", "a/b.pdf")]:
        with pytest.raises(panel.PanelError):
            panel.resolve_packet_file(rt, date, name)


# -- upload ------------------------------------------------------------------------------------
def test_save_upload_validates(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    p = panel.save_upload(rt, "nova", "page.png", PNG)
    assert p.is_file() and p.parent == rt.store.root / "uploads" / "nova"
    assert panel.save_upload(rt, "nova", "IMG.JPG", JPG).suffix == ".jpg"
    for name, data in [("x.exe", PNG), ("x.png", JPG), ("x.png", b""), ("x", PNG),
                       ("x.png", PNG[:8] + b"\x00" * panel.MAX_UPLOAD_BYTES)]:
        with pytest.raises(panel.PanelError):
            panel.save_upload(rt, "nova", name, data)
    with pytest.raises(KeyError):
        panel.save_upload(rt, "ghost", "x.png", PNG)


def test_intake_upload_runs_tool_and_drops_staging(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    out = panel.intake_upload(rt, "nova", "page.png", PNG, note="Lesson 4-2")
    assert isinstance(out, dict) and "ok" in out
    assert not any((rt.store.root / "uploads" / "nova").iterdir())


# -- router ------------------------------------------------------------------------------------
def _load_api(monkeypatch, tmp_path, family_file):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")

    name = "hc_plugin_api_under_test"
    spec = importlib.util.spec_from_file_location(name, ROOT / "dashboard" / "plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    store = Store(root=tmp_path / "data")
    tools = mod._modules()[1]
    settings = {"family_config": str(family_file)}
    monkeypatch.setattr(mod, "_runtime", lambda: tools.Runtime(
        get_setting=lambda k, d=None: settings.get(k, d), store=tools.Store(root=store.root)))
    return mod, store


def test_router_endpoints(monkeypatch, tmp_path, family_file):
    mod, store = _load_api(monkeypatch, tmp_path, family_file)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router, prefix="/api/plugins/homework-coach")
    c = TestClient(app)
    base = "/api/plugins/homework-coach"

    d = store.packet_dir("2026-11-02")
    (d / "packet.json").write_text(json.dumps({"children": {"nova": {"items": [
        {"id": "1", "skill": "arrays", "format": "array -> equation", "prompt": "p"}]}}}), encoding="utf-8")
    (d / "parent_key.pdf").write_bytes(b"%PDF-1.4\n")

    r = c.get(f"{base}/overview")
    assert r.status_code == 200 and r.json()["configured"] and r.json()["packets"][0]["date"] == "2026-11-02"
    assert c.get(f"{base}/packets?limit=3").json()["packets"][0]["files"][0]["kind"] == "parent_key"
    assert c.get(f"{base}/packets?limit=99").status_code == 422

    r = c.get(f"{base}/packets/2026-11-02/parent_key.pdf")
    assert r.status_code == 200 and Path(r.json()["path"]).name == "parent_key.pdf"
    assert c.get(f"{base}/packets/2026-11-02/packet.json").status_code == 400

    r = c.post(f"{base}/feedback", json={"child_id": "nova", "packet_date": "2026-11-02", "ratings": {"1": "I"}})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert c.post(f"{base}/feedback", json={"child_id": "nova", "packet_date": "bad", "ratings": {"1": "I"}}
                  ).status_code == 400

    import base64
    photo = {"child_id": "nova", "filename": "page.png", "data_b64": base64.b64encode(PNG).decode("ascii")}
    r = c.post(f"{base}/intake64", json=photo)
    assert r.status_code == 200 and r.json()["job"]
    assert c.post(f"{base}/intake64", json={**photo, "filename": "page.txt"}).status_code == 400
    assert c.post(f"{base}/intake64", json={**photo, "child_id": "ghost"}).status_code == 404


def test_router_private_package_name_does_not_shadow(monkeypatch, tmp_path, family_file):
    mod, _ = _load_api(monkeypatch, tmp_path, family_file)
    assert mod._PKG_NAME == "_homework_coach_dashboard_pkg" and mod._PKG_NAME in sys.modules
    assert sys.modules[f"{mod._PKG_NAME}.panel"].__file__.endswith(str(Path("homework_coach") / "panel.py"))


# -- repo layout -------------------------------------------------------------------------------
def test_desktop_and_dashboard_layout():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "homework-coach" and manifest["api"] == "plugin_api.py"
    assert manifest["tab"]["hidden"] is True and (ROOT / "dashboard" / manifest["entry"]).is_file()
    js = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    imports = {line.split("from")[-1].strip().strip("'\";") for line in js.splitlines()
               if line.startswith("import ")}
    assert imports <= {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}, imports
    assert 'var ID = "homework-coach"' in js and "id: ID" in js
    assert "Generated from desktop/src/plugin.jsx" in js  # rebuild with: node desktop/build.mjs
