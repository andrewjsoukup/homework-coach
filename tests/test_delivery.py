"""Scheduling, delivery and the feedback loop (card t_a62d383f).

Where Hermes is importable (PYTHONPATH=<hermes-agent>), the blueprint is filled with the real
``cron.blueprint_catalog.fill_blueprint`` and the delivery text is parsed with the real gateway
``BasePlatformAdapter.extract_media`` — the same code that turns MEDIA: lines into attachments.
Nothing here sends a message anywhere.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from homework_coach import config, delivery, difficulty, packet, plugin
from homework_coach.storage import Store
from homework_coach.tools import Runtime, make_handlers

from .conftest import EXAMPLE_FAMILY

MON, TUE, WED, SUN = "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-08"


@pytest.fixture
def fam():
    return config.load(EXAMPLE_FAMILY)


def _rt(tmp_path: Path, *, cron=None, today: str | None = None) -> Runtime:
    settings = {"family_config": str(EXAMPLE_FAMILY)}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d),
                 store=Store(root=tmp_path / "data", output_dir=tmp_path / "packets"),
                 cron_run=(lambda: cron))
    if today:
        rt.today = lambda _fam: today  # type: ignore[method-assign]
    return rt


def _call(h, name, args):
    return json.loads(h[name](args))


# -- schedule / blueprint ------------------------------------------------------------------------
def test_schedule_groups_one_job_per_distinct_schedule(fam):
    groups = {tuple(g["children"]): g for g in delivery.schedule_groups(fam)}
    assert groups[("nova",)]["cron"] == "0 9 * * 1-6"
    assert groups[("pip",)]["cron"] == "30 8 * * 1,3,5"
    assert groups[("pip",)]["blueprint_command"] == (
        "/blueprint homework-coach:daily-packet time=08:30 days=1,3,5 children=pip deliver=origin")
    text = delivery.schedule_text(fam)
    assert "does not create cron jobs itself" in text and text.count("/blueprint ") == 2


def test_blueprint_fills_with_real_hermes_catalog(fake_ctx, fam):
    bp_mod = pytest.importorskip("cron.blueprint_plugins")
    from cron.blueprint_catalog import fill_blueprint
    from hermes_cli.blueprint_cmd import _parse_kv

    plugin.register(fake_ctx)
    kw = fake_ctx.blueprints["daily-packet"]
    bp = bp_mod.build_plugin_blueprint("homework-coach", "daily-packet", **kw)
    assert bp.key == delivery.BLUEPRINT_KEY
    for g in delivery.schedule_groups(fam):
        values, rest = _parse_kv(g["blueprint_command"].split()[2:])
        assert not rest
        spec = fill_blueprint(bp, values)
        assert spec["schedule"] == g["cron"]
        assert spec["deliver"] == "origin"
        assert f'child_ids=["{",".join(g["children"])}"]' in spec["prompt"]
        assert "homework_coach_generate_packet" in spec["prompt"] and "verbatim" in spec["prompt"]
    defaults = fill_blueprint(bp, {})  # every slot has a default → Hermes fills it at load too
    assert defaults["schedule"] == "0 9 * * 1-6" and 'child_ids=["all"]' in defaults["prompt"]


# -- delivery ------------------------------------------------------------------------------------
def test_packet_message_attaches_every_pdf_via_gateway_parser(tmp_path):
    h = make_handlers(_rt(tmp_path))
    out = _call(h, "homework_coach_generate_packet", {"date": MON})
    assert out["ok"], out
    msg = out["message"]
    media_lines = [ln[len("MEDIA:"):] for ln in msg.splitlines() if ln.startswith("MEDIA:")]
    assert sorted(media_lines) == sorted(out["paths"]) and len(media_lines) == 3
    assert all(Path(p).is_file() and Path(p).is_absolute() for p in media_lines)
    assert media_lines[-1].endswith("parent_key.pdf")  # key last, separate from the sheets
    assert "Nova:" in msg and "Pip:" in msg and "nova 1=I 2=S 3=N" in msg
    base = pytest.importorskip("gateway.platforms.base")
    media, cleaned = base.BasePlatformAdapter.extract_media(msg)
    assert sorted(Path(p).resolve() for p, _ in media) == sorted(Path(p).resolve() for p in out["paths"])
    assert "MEDIA:" not in cleaned and "Nova:" in cleaned


def test_same_date_rerun_resends_identical_files(tmp_path):
    h = make_handlers(_rt(tmp_path))
    first = _call(h, "homework_coach_generate_packet", {"date": MON})
    mtimes = {p: Path(p).stat().st_mtime_ns for p in first["paths"]}
    second = _call(h, "homework_coach_generate_packet", {"date": MON})
    assert second["reused"] and second["added"] == []
    assert second["paths"] == first["paths"]
    assert {p: Path(p).stat().st_mtime_ns for p in second["paths"]} == mtimes
    assert "same packet re-sent" in second["message"]
    assert sorted(x.name for x in (tmp_path / "packets").iterdir()) == [MON]  # no temp/failed leftovers


def test_per_child_jobs_add_parts_without_touching_existing_files(tmp_path):
    h = make_handlers(_rt(tmp_path))
    pip = _call(h, "homework_coach_generate_packet", {"date": MON, "child_ids": ["pip"]})  # 08:30 job
    assert pip["ok"] and set(pip["files"]) == {"pip", "parent_key"}
    pip_mtimes = {p: Path(p).stat().st_mtime_ns for p in pip["paths"]}
    nova = _call(h, "homework_coach_generate_packet", {"date": MON, "child_ids": "nova"})  # 09:00 job
    assert nova["ok"] and nova["reused"] and nova["added"] == ["nova"]
    assert set(nova["files"]) == {"nova", "parent_key:nova"}  # only nova's sheet + nova's key part
    assert Path(nova["files"]["parent_key:nova"]).name == "parent_key-nova.pdf"
    assert {p: Path(p).stat().st_mtime_ns for p in pip["paths"]} == pip_mtimes
    data = json.loads((tmp_path / "packets" / MON / "packet.json").read_text(encoding="utf-8"))
    assert set(data["children"]) == {"pip", "nova"} and data["verification"]["ok"]
    assert packet.key_coverage(data) == {"parent_key.pdf": ["pip"], "parent_key-nova.pdf": ["nova"]}
    again = _call(h, "homework_coach_generate_packet", {"date": MON, "child_ids": ["nova"]})
    assert again["reused"] and again["added"] == [] and again["files"] == nova["files"]
    both = _call(h, "homework_coach_generate_packet", {"date": MON})
    assert set(both["files"]) == {"pip", "nova", "parent_key", "parent_key:nova"}
    assert len([ln for ln in both["message"].splitlines() if ln.startswith("MEDIA:")]) == 4


def test_concurrent_runs_for_same_date_build_once(tmp_path, fam):
    store = Store(root=tmp_path / "data", output_dir=tmp_path / "packets")
    results: list[dict] = []
    threads = [threading.Thread(target=lambda: results.append(packet.build_packet(store, fam, MON)))
               for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 3 and all(r["ok"] is not False for r in results)
    assert sum(not r["reused"] for r in results) == 1  # exactly one builder; others reuse
    assert len({json.dumps(r["files"], sort_keys=True) for r in results}) == 1
    assert sorted(x.name for x in (tmp_path / "packets").iterdir()) == [MON]


def test_cron_run_stays_silent_on_unscheduled_day(tmp_path):
    cron = SimpleNamespace(job_id="j1", scheduled_instant="2026-11-08T09:00:00")
    out = _call(make_handlers(_rt(tmp_path, cron=cron)), "homework_coach_generate_packet", {"date": SUN})
    assert out["ok"] and out["skipped"] and out["message"] == "[SILENT]"
    manual = _call(make_handlers(_rt(tmp_path)), "homework_coach_generate_packet", {"date": SUN})
    assert "No children are scheduled" in manual["message"]
    # a per-child job naming pip (Mon/Wed/Fri) stays quiet on Tuesday...
    pip_tue = _call(make_handlers(_rt(tmp_path, cron=cron)), "homework_coach_generate_packet",
                    {"date": TUE, "child_ids": ["pip"]})
    assert pip_tue["message"] == "[SILENT]" and not (tmp_path / "packets" / TUE).exists()
    # ...while a parent asking by hand for pip on Tuesday gets one
    by_hand = _call(make_handlers(_rt(tmp_path)), "homework_coach_generate_packet",
                    {"date": TUE, "child_ids": ["pip"]})
    assert by_hand["ok"] and set(by_hand["files"]) == {"pip", "parent_key"}


def test_cron_failure_is_declared_and_carries_text_fallback(tmp_path, monkeypatch):
    from homework_coach import render

    def boom(*a, **k):
        raise RuntimeError("font missing")
    monkeypatch.setattr(render, "child_pdf", boom)
    cron = SimpleNamespace(job_id="j1", scheduled_instant="2026-11-02T09:00:00")
    out = _call(make_handlers(_rt(tmp_path, cron=cron)), "homework_coach_generate_packet", {"date": MON})
    assert out["ok"] is False
    lines = out["message"].splitlines()
    assert lines[0] == "[CRON_FAILURE]" and "PDF rendering failed" in lines[1]
    assert "PARENT KEY (keep separate)" in out["message"] and "MEDIA:" not in out["message"]
    sched = pytest.importorskip("cron.scheduler")
    assert sched._cron_failure_marker_error(out["message"])  # Hermes records the run as failed
    interactive = _call(make_handlers(_rt(tmp_path)), "homework_coach_generate_packet", {"date": MON})
    assert not interactive["message"].startswith("[CRON_FAILURE]")


# -- feedback ------------------------------------------------------------------------------------
def test_parse_reply_shapes():
    ids = ["nova", "pip"]
    assert delivery.parse_reply("nova 1=I 2=S S1=N\npip: 1I 2i", ids) == {
        "nova": {"ratings": "1=I 2=S S1=N", "date": None}, "pip": {"ratings": "1I 2i", "date": None}}
    assert delivery.parse_reply("Nova 2026-11-02 1=I; nova 2026-11-02 2=S", ids)["nova"] == {
        "ratings": "1=I 2=S", "date": "2026-11-02"}
    assert delivery.parse_reply("1=I 2=N", ["solo"]) == {"solo": {"ratings": "1=I 2=N", "date": None}}
    for bad in ("1=I 2=S", "nova great job", "ghost 1=I", ""):
        with pytest.raises(ValueError):
            delivery.parse_reply(bad, ids)


def test_chat_reply_records_latest_packet_and_is_idempotent(tmp_path):
    rt = _rt(tmp_path, today=TUE)
    h = make_handlers(rt)
    assert _call(h, "homework_coach_generate_packet", {"date": MON})["ok"]
    first = _call(h, "homework_coach_record_feedback", {"reply": "nova 1=I 2=I 3=I\npip 1=S 99=I"})
    assert first["ok"], first
    nova, pip = first["children"]["nova"], first["children"]["pip"]
    assert nova["packet_date"] == MON and nova["applies_to"] == WED  # Tue is today → next is Wed
    assert pip["unknown_items"] == ["99"] and pip["recorded"] == {"1": "S"}
    assert "nova: recorded 3 rating(s)" in first["message"]
    state1 = json.loads((tmp_path / "data/children/nova/state.json").read_text(encoding="utf-8"))
    again = _call(h, "homework_coach_record_feedback", {"reply": "nova 1=I 2=I 3=I"})
    assert again["ok"]
    state2 = json.loads((tmp_path / "data/children/nova/state.json").read_text(encoding="utf-8"))
    assert state1["skills"] == state2["skills"]  # re-sending the same reply changes nothing


def test_feedback_correction_replaces_earlier_rating(tmp_path):
    h = make_handlers(_rt(tmp_path, today=MON))
    _call(h, "homework_coach_generate_packet", {"date": MON})
    data = json.loads((tmp_path / "packets" / MON / "packet.json").read_text(encoding="utf-8"))["children"]["nova"]
    target = data["target_skill"]
    ids = [i["id"] for i in data["items"] if i["skill"] == target][:3]
    up = _call(h, "homework_coach_record_feedback", {"child_id": "nova", "ratings": " ".join(f"{i}I" for i in ids)})
    assert up["changes"] == {target: "up"}, up
    fixed = _call(h, "homework_coach_record_feedback", {"child_id": "nova", "ratings": f"{ids[1]}N"})
    assert fixed["ok"]
    # merged Mon ratings are now I,N,I: the raise is gone (replay from the log, not a stacked down)
    st = json.loads((tmp_path / "data/children/nova/state.json").read_text(encoding="utf-8"))["skills"][target]
    assert st["dims"] == {"scaffold": 1, "steps": 1, "representation": 1, "number_range": 1}
    assert [h_["change"] for h_ in st["history"]] == ["hold-floor"]


def test_feedback_errors_are_reported_not_raised(tmp_path):
    h = make_handlers(_rt(tmp_path, today=MON))
    none_yet = _call(h, "homework_coach_record_feedback", {"child_id": "nova", "ratings": "1I"})
    assert none_yet["ok"] is False and "no packet" in none_yet["error"]
    _call(h, "homework_coach_generate_packet", {"date": MON})
    wrong = _call(h, "homework_coach_record_feedback", {"child_id": "nova", "ratings": "77I"})
    assert wrong["ok"] is False and wrong["unknown_items"] == ["77"] and "1" in wrong["valid_items"]
    garbage = _call(h, "homework_coach_record_feedback", {"reply": "nova was great"})
    assert garbage["ok"] is False


def test_feedback_feeds_the_next_packet(tmp_path):
    """Mon packet → all I → Wed packet is one notch harder on exactly one dimension; N steps back."""
    rt = _rt(tmp_path, today=MON)
    h = make_handlers(rt)
    mon = _call(h, "homework_coach_generate_packet", {"date": MON, "child_ids": ["nova"]})
    pdir = tmp_path / "packets"
    mon_data = json.loads((pdir / MON / "packet.json").read_text(encoding="utf-8"))["children"]["nova"]
    target = mon_data["target_skill"]
    target_ids = [i["id"] for i in mon_data["items"] if i["skill"] == target]
    fb = _call(h, "homework_coach_record_feedback",
               {"reply": "nova " + " ".join(f"{i}=I" for i in target_ids)})
    assert fb["children"]["nova"]["changes"].get(target) == "up", fb
    assert mon["ok"]
    rt.today = lambda _f: WED  # type: ignore[method-assign]
    _call(h, "homework_coach_generate_packet", {"date": WED, "child_ids": ["nova"]})
    wed_data = json.loads((pdir / WED / "packet.json").read_text(encoding="utf-8"))["children"]["nova"]
    before, after = mon_data["dims"][target], wed_data["dims"][target]
    assert sum(after.values()) - sum(before.values()) == 1
    assert [k for k in after if after[k] != before[k]] == ["scaffold"]
    wed_target = [i["id"] for i in wed_data["items"] if i["skill"] == target]
    down = _call(h, "homework_coach_record_feedback", {"child_id": "nova", "ratings": f"{wed_target[0]}N"})
    assert down["changes"].get(target) == "down"
    st = json.loads((tmp_path / "data/children/nova/state.json").read_text(encoding="utf-8"))
    assert st["skills"][target]["dims"] == before
    # the dated Mon folder is never rewritten by later feedback
    assert json.loads((pdir / MON / "packet.json").read_text(encoding="utf-8"))["children"]["nova"] == mon_data


def test_slash_commands(fake_ctx, tmp_path, monkeypatch):
    plugin.register(fake_ctx)
    cmd = fake_ctx.commands["homework"]
    assert "/blueprint homework-coach:daily-packet" in cmd("schedule")
    out = cmd(f"packet {MON} nova")
    assert out.startswith("Homework Coach practice") and out.count("MEDIA:") == 2
    reply = cmd(f"feedback nova {MON} 1=I 2=S")
    assert reply.startswith("nova: recorded 2 rating(s)"), reply
    assert cmd("feedback ghost 1=I").startswith("Not done")
    assert "Usage" in cmd("nonsense")


def test_register_passes_cron_identity_through(tmp_path, family_file):
    from .conftest import FakeCtx

    ctx = FakeCtx({"family_config": str(family_file), "output_dir": str(tmp_path / "packets")})
    ctx.current_cron_execution = lambda: SimpleNamespace(job_id="x", scheduled_instant=None)
    plugin.register(ctx)
    out = json.loads(ctx.tools["homework_coach_generate_packet"]["handler"]({"date": SUN}))
    assert out["message"] == "[SILENT]"
