"""Packet build: determinism, rotation, idempotency, PDFs (no answers on child pages), render check."""
import json
from pathlib import Path

import pytest

from homework_coach import config, packet, verify
from homework_coach.models import SkillState
from homework_coach.storage import Store

from .conftest import EXAMPLE_FAMILY

MON, TUE, WED, THU = "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"


@pytest.fixture
def fam():
    return config.load(EXAMPLE_FAMILY)


@pytest.fixture
def store(tmp_path):
    return Store(root=tmp_path / "data", output_dir=tmp_path / "packets")


def test_plan_is_deterministic(store, fam, tmp_path):
    a = packet.plan_child(store, fam, fam.child("nova"), MON)
    b = packet.plan_child(Store(root=tmp_path / "other"), fam, fam.child("nova"), MON)
    assert [i.to_dict() for i in a.items] == [i.to_dict() for i in b.items]


def test_plan_respects_budget_and_roles(store, fam):
    for cid in ("nova", "pip"):
        child = fam.child(cid)
        p = packet.plan_child(store, fam, child, MON)
        core = [i for i in p.items if not i.optional]
        assert len(core) == child.item_budget
        assert [i.id for i in core] == [str(n) for n in range(1, len(core) + 1)]
        assert p.items[-1].optional and p.items[-1].id == "S1"
        assert {i.role for i in core} == {"target", "review"}
        assert verify.check_items(core, budget=child.item_budget) == []


def test_build_writes_verified_pdfs(store, fam):
    res = packet.build_packet(store, fam, MON)
    assert res["ok"], res.get("verification")
    files = {k: Path(v) for k, v in res["files"].items()}
    assert set(files) == {"nova", "pip", "parent_key"}
    data = json.loads((Path(res["folder"]) / "packet.json").read_text(encoding="utf-8"))
    assert data["verification"]["ok"] and data["verification"]["errors"] == []
    assert all(data["verification"]["raster_checked"].values())  # pypdfium2 is a dev dep
    for cid in ("nova", "pip"):
        text, pages = verify.pdf_text(files[cid])
        items = data["children"][cid]["items"]
        assert pages >= 1
        for it in items:
            assert it["worked_solution"] not in text
        assert "Answer key" not in text
    key_text, _ = verify.pdf_text(files["parent_key"])
    assert "Nova" in key_text and "Pip" in key_text and "1=I" in key_text
    assert (Path(res["folder"]) / "progression.md").read_text(encoding="utf-8").startswith("# Packet progression")


def test_schedule_skips_unscheduled_children(store, fam):
    res = packet.build_packet(store, fam, TUE)  # pip is mon/wed/fri only
    assert set(res["files"]) == {"nova", "parent_key"}
    sun = packet.build_packet(store, fam, "2026-11-08")
    assert sun.get("skipped") and not sun["files"]


def test_rerun_same_date_reuses_and_never_overwrites(store, fam):
    first = packet.build_packet(store, fam, MON)
    pdf = Path(first["files"]["nova"])
    mtime = pdf.stat().st_mtime_ns
    second = packet.build_packet(store, fam, MON)
    assert second["reused"] and second["files"] == first["files"]
    assert pdf.stat().st_mtime_ns == mtime


def test_formats_rotate_across_days(store, fam):
    seqs = []
    for d in (MON, TUE, WED, THU):
        res = packet.build_packet(store, fam, d, ["nova"])
        data = json.loads((Path(res["folder"]) / "packet.json").read_text(encoding="utf-8"))
        seqs.append([i["format"] for i in data["children"]["nova"]["items"] if not i["optional"]])
    for a, b in zip(seqs, seqs[1:]):
        assert a != b, "same ordered template on consecutive days"
        assert set(b) - set(a), "no new format vs previous day"
    all_used = {f for s in seqs for f in s}
    assert len(all_used) >= 8  # variety of formats, not just numbers


def test_anchor_drives_target_and_prior_topic_becomes_review(store, fam):
    store.save_anchor("nova", {"skill": "division", "formats": ["fact_family"], "since": MON,
                               "previous_skill": "multiplication"})
    p = packet.plan_child(store, fam, fam.child("nova"), TUE)
    assert p.target_skill == "division" and p.review_skill == "multiplication"
    assert any(i.format == "fact_family" for i in p.items)


def test_difficulty_state_feeds_generators(store, fam):
    hard = SkillState(skill="multiplication", dims={"scaffold": 5, "steps": 5, "representation": 5, "number_range": 5})
    store.save_skills("nova", {"multiplication": hard})
    p = packet.plan_child(store, fam, fam.child("nova"), MON)
    target = [i for i in p.items if i.skill == "multiplication" and not i.optional]
    assert target and all(i.hint == "" for i in target)


def test_render_failure_falls_back_to_text(store, fam, monkeypatch):
    from homework_coach import render

    def boom(*a, **k):
        raise render.BoundsError("forced")
    monkeypatch.setattr(render, "child_pdf", boom)
    res = packet.build_packet(store, fam, MON)
    assert res["ok"] is False and "PDF rendering failed" in res["error"]
    assert "PARENT KEY" in res["fallback_text"] and "Nova" in res["fallback_text"]
    assert not store.packet_dir(MON, create=False).exists()


def test_verification_failure_is_not_delivered(store, fam, monkeypatch):
    real = packet.plan_child

    def broken(*a, **k):
        p = real(*a, **k)
        p.items[0].answer = "999999"
        return p
    monkeypatch.setattr(packet, "plan_child", broken)
    res = packet.build_packet(store, fam, MON)
    assert res["ok"] is False and res["error"] == "verification failed"
    assert not (store.packet_dir(MON, create=False) / "packet.json").exists()


def test_render_check_flags_blank_pdf(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    blank = tmp_path / "blank.pdf"
    c = Canvas(str(blank))
    c.showPage()
    c.save()
    rc = verify.render_check(blank)
    assert rc["checked"] and any("blank" in e for e in rc["errors"])


def test_check_child_pdf_flags_leaked_answer(tmp_path, store, fam):
    from reportlab.pdfgen.canvas import Canvas
    p = packet.plan_child(store, fam, fam.child("nova"), MON)
    leak = tmp_path / "leak.pdf"
    c = Canvas(str(leak))
    y = 750
    for it in p.items:
        c.drawString(60, y, f"{it.id}. {it.prompt[:60]}")
        y -= 14
        c.drawString(60, y, it.worked_solution[:90])
        y -= 14
    c.save()
    assert any("worked solution" in e for e in verify.check_child_pdf(leak, p.items))
