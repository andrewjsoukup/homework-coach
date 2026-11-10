"""Workspace REST routes through the real plugin router (FastAPI TestClient, temp data only)."""
from __future__ import annotations

import base64
import time

import pytest

from .test_panel import _load_api


@pytest.fixture
def client(monkeypatch, tmp_path, family_file):
    mod, store = _load_api(monkeypatch, tmp_path, family_file)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mod.router, prefix="/api/plugins/homework-coach")
    return TestClient(app), store


P = "/api/plugins/homework-coach"


def test_today_family_and_child_edit_round_trip(client):
    c, _ = client
    t = c.get(P + "/today").json()
    assert {k["id"] for k in t["children"]} == {"nova", "pip"} and all(k["headline"] for k in t["children"])
    added = c.post(P + "/family/children", json={"name": "Ollie", "grade": "1", "minutes_per_day": 10}).json()
    assert added["child"]["id"] == "ollie"
    assert c.post(P + "/family/children/ollie", json={"minutes_per_day": 20}).json()["child"]["minutes_per_day"] == 20
    assert c.post(P + "/family/children/ghost", json={"name": "x"}).status_code == 404
    bad = c.post(P + "/family/children/ollie", json={"minutes_per_day": "lots"})
    assert bad.status_code == 400
    assert c.post(P + "/family/schedule", json={"days": [], "time": "09:00"}).status_code == 400
    assert "ollie" in [k["id"] for k in c.get(P + "/family").json()["children"]]


def test_unknown_packet_and_bad_preview_kind_are_clear_errors(client):
    c, _ = client
    assert c.get(P + "/packet/2026-11-07/nova").status_code == 400
    assert c.get(P + "/packet/2026-11-07/nova/preview?kind=../x").status_code == 400
    assert c.get(P + "/packet/2026-11-07/nova/preview?width=99999").status_code == 422


def test_slow_reads_run_as_jobs_and_report_failures(client):
    c, _ = client
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 64).decode()
    assert c.post(P + "/intake64", json={"child_id": "nova", "filename": "x.exe", "data_b64": png}).status_code == 400
    start = c.post(P + "/intake64", json={"child_id": "nova", "filename": "hw.png", "data_b64": png}).json()
    assert start["status"] == "running" and start["job"]
    for _ in range(50):
        j = c.get(P + f"/jobs/{start['job']}").json()
        if j["status"] != "running":
            break
        time.sleep(0.1)
    assert j["status"] in ("error", "done")
    if j["status"] == "error":
        assert j["error"]  # no model in tests: the parent sees why, the job never hangs
    assert c.get(P + "/jobs/doesnotexist").status_code == 404


def test_material_propose_writes_nothing(client):
    c, store = client
    r = c.post(P + "/children/nova/materials/propose", json={"material": {"unit_title": "Topic 3", "unit_end": "2026-11-13"}})
    assert r.status_code == 200 and r.json()["proposal"] is None  # no plan saved yet
    assert not (store.root / "children" / "nova" / "curriculum.json").exists()
