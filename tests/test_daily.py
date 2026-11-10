"""Daily sheets: opt-in switch, due check, one sheet per child per day, retries, the in-process timer."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homework_coach import daily, plugin
from homework_coach.daily import start_timer as real_start_timer
from homework_coach.storage import Store
from homework_coach.tools import Runtime

from .conftest import FakeCtx

TZ = ZoneInfo("America/Chicago")
MON_EARLY = datetime(2026, 11, 2, 8, 0, tzinfo=TZ)    # before both practice times
MON_MID = datetime(2026, 11, 2, 8, 45, tzinfo=TZ)     # Pip (08:30) due, Nova (09:00) not yet
MON_LATE = datetime(2026, 11, 2, 9, 5, tzinfo=TZ)
TUE_LATE = datetime(2026, 11, 3, 9, 5, tzinfo=TZ)     # Pip practises Mon/Wed/Fri only
SUN = datetime(2026, 11, 8, 12, 0, tzinfo=TZ)


@pytest.fixture
def rt(tmp_path: Path, family_file: Path) -> Runtime:
    s = {"family_config": str(family_file)}
    return Runtime(get_setting=lambda k, d=None: s.get(k, d), store=Store(root=tmp_path / "data"))


def _packet(rt: Runtime, day: str) -> dict:
    return json.loads((rt.store.packet_dir(day, create=False) / "packet.json").read_text(encoding="utf-8"))


def test_off_by_default_and_settings_validate(rt):
    assert daily.settings(rt.store) == {"enabled": False, "writer": "builtin"}
    assert daily.run_due(rt, MON_LATE) == {"ran": False, "reason": "off"}
    assert not rt.store.packet_dir("2026-11-02", create=False).exists()
    assert daily.save_settings(rt.store, {"enabled": True, "writer": "model"}) == {"enabled": True, "writer": "model"}
    assert daily.save_settings(rt.store, {"writer": "builtin"}) == {"enabled": True, "writer": "builtin"}
    for bad in ({"enabled": "yes"}, {"writer": "gpt"}):
        with pytest.raises(ValueError):
            daily.save_settings(rt.store, bad)
    (rt.store.root / daily.SETTINGS_FILE).write_text("not json", encoding="utf-8")
    assert daily.settings(rt.store) == {"enabled": False, "writer": "builtin"}  # a damaged file means off


def test_due_follows_each_childs_days_and_time(rt):
    assert daily.due(rt, MON_EARLY) == ("2026-11-02", [])
    assert daily.due(rt, MON_MID) == ("2026-11-02", ["pip"])
    assert daily.due(rt, MON_LATE) == ("2026-11-02", ["nova", "pip"])
    assert daily.due(rt, TUE_LATE) == ("2026-11-03", ["nova"])
    assert daily.due(rt, SUN) == ("2026-11-08", [])


def test_builds_once_and_never_duplicates(rt):
    daily.save_settings(rt.store, {"enabled": True})
    assert daily.should_run(rt, MON_EARLY) is False
    assert daily.should_run(rt, MON_LATE) is True
    first = daily.run_due(rt, MON_LATE)
    assert first["ran"] and first["ok"] and first["children"] == ["nova", "pip"]
    pdir = rt.store.packet_dir("2026-11-02", create=False)
    before = {p.name: p.stat().st_mtime_ns for p in pdir.iterdir()}
    assert {"nova_practice.pdf", "pip_practice.pdf", "parent_key.pdf", "packet.json"} <= set(before)
    again = daily.run_due(rt, MON_LATE)
    assert again == {"ran": False, "reason": "nothing due", "date": "2026-11-02"}
    assert daily.should_run(rt, MON_LATE) is False
    assert {p.name: p.stat().st_mtime_ns for p in pdir.iterdir()} == before  # nothing rewritten
    st = daily.status(rt)
    assert st["enabled"] and st["last"]["status"] == "ok" and st["last"]["date"] == "2026-11-02"


def test_children_with_different_times_share_one_days_folder(rt):
    daily.save_settings(rt.store, {"enabled": True})
    assert daily.run_due(rt, MON_MID)["children"] == ["pip"]
    assert set(_packet(rt, "2026-11-02")["children"]) == {"pip"}
    assert daily.run_due(rt, MON_LATE)["children"] == ["nova"]
    data = _packet(rt, "2026-11-02")
    assert set(data["children"]) == {"nova", "pip"} and data["verification"]["ok"]


def test_a_sheet_made_by_hand_is_not_made_again(rt):
    from homework_coach.tools import make_handlers

    daily.save_settings(rt.store, {"enabled": True})
    made = json.loads(make_handlers(rt)["homework_coach_generate_packet"]({"date": "2026-11-02"}))
    assert made["ok"]
    assert daily.run_due(rt, MON_LATE)["reason"] == "nothing due"


def test_failures_wait_then_retry_then_stop_for_the_day(rt, monkeypatch):
    daily.save_settings(rt.store, {"enabled": True})
    calls = []

    def boom(*a, **k):
        calls.append(1)
        return {"date": "2026-11-02", "ok": False, "error": "PDF rendering failed", "files": {}}

    monkeypatch.setattr("homework_coach.packet.build_packet", boom)
    r = daily.run_due(rt, MON_LATE)
    assert r["ran"] and r["ok"] is False and "PDF rendering failed" in r["error"]
    assert daily.status(rt)["last"]["status"] == "failed"
    assert daily.run_due(rt, MON_LATE)["reason"] == "waiting to retry" and len(calls) == 1
    st = daily.state(rt.store)
    st["last_attempt"] -= daily.RETRY_SECONDS + 1
    (rt.store.root / daily.STATE_FILE).write_text(json.dumps(st), encoding="utf-8")
    assert daily.run_due(rt, MON_LATE)["ran"] and len(calls) == 2
    st = daily.state(rt.store)
    st.update(attempts=daily.MAX_ATTEMPTS, last_attempt=0)
    (rt.store.root / daily.STATE_FILE).write_text(json.dumps(st), encoding="utf-8")
    assert daily.run_due(rt, MON_LATE)["reason"] == "gave up for today" and len(calls) == 2
    assert daily.should_run(rt, TUE_LATE) is True  # a new day starts fresh


def test_a_run_in_progress_blocks_a_second_one(rt):
    daily.save_settings(rt.store, {"enabled": True})
    (rt.store.root / daily.STATE_FILE).write_text(json.dumps(
        {"date": "2026-11-02", "status": "running", "last_attempt": time.time(), "attempts": 1}), encoding="utf-8")
    assert daily.should_run(rt, MON_LATE) is False
    assert daily.run_due(rt, MON_LATE)["reason"] == "already running"
    (rt.store.root / daily.STATE_FILE).write_text(json.dumps(
        {"date": "2026-11-02", "status": "running", "last_attempt": time.time() - daily.RUNNING_STALE_SECONDS - 1,
         "attempts": 1}), encoding="utf-8")
    assert daily.should_run(rt, MON_LATE) is True  # a builder that died does not block the day


def test_status_write_survives_a_file_that_is_briefly_locked(rt, monkeypatch):
    real, fails = daily._atomic_write, [PermissionError("in use"), PermissionError("in use")]

    def flaky(path, text):
        if fails:
            raise fails.pop()
        real(path, text)

    monkeypatch.setattr(daily, "_atomic_write", flaky)
    monkeypatch.setattr(daily.time, "sleep", lambda s: None)
    daily._write(rt.store, daily.STATE_FILE, {"date": "2026-11-02", "status": "ok"})
    assert daily.state(rt.store)["status"] == "ok" and fails == []
    monkeypatch.setattr(daily, "_atomic_write", lambda p, t: (_ for _ in ()).throw(PermissionError("locked")))
    daily._write(rt.store, daily.STATE_FILE, {"status": "failed"})  # gives up quietly, never raises
    assert daily.state(rt.store)["status"] == "ok"


def test_missing_family_file_never_raises(tmp_path):
    rt = Runtime(get_setting=lambda k, d=None: {"family_config": str(tmp_path / "none.yaml")}.get(k, d),
                 store=Store(root=tmp_path / "data"))
    daily.save_settings(rt.store, {"enabled": True})
    assert daily.should_run(rt, MON_LATE) is False
    assert daily.run_due(rt, MON_LATE)["ran"] is False


def test_today_is_taken_from_the_family_timezone(rt, monkeypatch):
    seen = {}

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            seen["tz"] = tz
            return datetime(2026, 11, 2, 9, 5, tzinfo=tz)

    monkeypatch.setattr(daily, "datetime", FakeDatetime)
    assert daily.due(rt)[0] == "2026-11-02" and str(seen["tz"]) == "America/Chicago"


def test_timer_ticks_builds_and_stops(rt, monkeypatch):
    daily.save_settings(rt.store, {"enabled": True})
    monkeypatch.setattr(daily, "_now", lambda family: MON_LATE)
    stop = real_start_timer(lambda: rt, first=0.01, every=0.05)
    assert callable(stop)
    try:
        assert real_start_timer(lambda: rt, first=0.01, every=0.05) is None  # one timer per process
        deadline = time.time() + 30
        while time.time() < deadline and daily.state(rt.store).get("status") != "ok":
            time.sleep(0.05)
        assert daily.state(rt.store).get("status") == "ok"
        assert set(_packet(rt, "2026-11-02")["children"]) == {"nova", "pip"}
        assert daily.timer_alive(rt.store) is True
    finally:
        stop()
    for t in threading.enumerate():
        if t.name == daily.THREAD_NAME:
            t.join(timeout=5)
    assert not any(t.name == daily.THREAD_NAME and t.is_alive() for t in threading.enumerate())
    again = real_start_timer(lambda: rt, first=60, every=60)  # a stopped timer can be started again
    assert callable(again)
    again()


def test_timer_leaves_no_trace_while_daily_sheets_is_off(rt):
    assert daily.tick(rt) == {"ran": False, "reason": "off"}
    assert not (rt.store.root / daily.TIMER_FILE).exists()
    assert daily.timer_alive(rt.store) is False


def test_register_starts_the_timer_and_stops_it_on_unload(fake_ctx, monkeypatch):
    started, stopped = [], []
    monkeypatch.setattr(daily, "start_timer", lambda make: started.append(make) or (lambda: stopped.append(1)))
    plugin.register(fake_ctx)
    assert len(started) == 1 and len(fake_ctx.unload) == 1
    assert started[0]().family().family_id == "maple"  # the timer gets the plugin's own runtime
    fake_ctx.unload[0]()
    assert stopped == [1]
    assert fake_ctx.blueprints["daily-packet"]  # chat delivery stays an optional, user-created job


def test_slash_daily_turns_it_on_and_picks_the_writer(fake_ctx, tmp_path, monkeypatch):
    monkeypatch.setattr("homework_coach.storage.default_root", lambda: tmp_path / "data")
    plugin.register(fake_ctx)
    cmd = fake_ctx.commands["homework"]
    assert "off" in cmd("daily")
    on = cmd("daily on model")
    assert "Daily sheets are on" in on and "your model" in on and "America/Chicago" in on
    assert daily.settings(Store(root=tmp_path / "data")) == {"enabled": True, "writer": "model"}
    assert "off" in cmd("daily off") and "Usage" in cmd("daily sometimes")


def test_old_hosts_without_on_unload_still_register(tmp_path, family_file):
    class OldCtx(FakeCtx):
        on_unload = None

    ctx = OldCtx({"family_config": str(family_file)})
    plugin.register(ctx)
    assert "homework_coach_generate_packet" in ctx.tools
