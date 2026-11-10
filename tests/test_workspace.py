"""Desktop workspace service: provenance, previews, teacher-material review, family edits."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from homework_coach import curriculum as cur
from homework_coach import workspace as ws
from homework_coach.models import Observation, ObservedItem
from homework_coach.panel import PanelError
from homework_coach.storage import Store
from homework_coach.tools import Runtime


def _rt(tmp_path: Path, family_file: Path) -> Runtime:
    s = {"family_config": str(family_file)}
    return Runtime(get_setting=lambda k, d=None: s.get(k, d), store=Store(root=tmp_path / "data"))


def _obs(rt: Runtime, date: str, photo: Path | None = None) -> None:
    o = Observation(child_id="nova", date=date, source=str(photo or ""), lesson=f"Lesson {date}",
                    items=[ObservedItem(prompt="6 x 4", child_answer="26", expected_answer="24",
                                        status="slip", skill="multiplication", format="equation")])
    rt.store.add_observation(o)


def _plan(rt: Runtime, fam) -> None:
    cur.save_plan(rt.store, fam.child("nova"), curriculum="enVision", sources=["https://example.org/s"],
                  units=[{"title": "Topic 3: Multiplication Facts", "start": "2026-10-05", "end": "2026-10-30",
                          "skill": "multiplication", "vocabulary": ["array", "skip count"]},
                         {"title": "Topic 4: Division", "start": "2026-11-02", "end": "2026-11-20",
                          "skill": "division"},
                         {"title": "Topic 10: Fractions", "start": "2027-02-01", "end": "2027-02-26",
                          "skill": "fractions"}])


def _packet(rt: Runtime, date: str, *, steered="homework photo", pdf: bytes = b"%PDF-1.4\n%x\n") -> Path:
    d = rt.store.packet_dir(date)
    items = [{"id": "1", "skill": "multiplication", "format": "array_to_equation", "prompt": "3 rows of 4",
              "answer": "12", "worked_solution": "4 + 4 + 4 = 12", "role": "target"}]
    data = {"date": date, "verification": {"ok": True}, "files": {"nova": "nova_practice.pdf"},
            "children": {"nova": {"name": "Nova", "focus": "arrays", "items": items, "steered_by": steered,
                                  "class_unit": "Topic 3: Multiplication Facts"}}}
    (d / "packet.json").write_text(json.dumps(data), encoding="utf-8")
    (d / "nova_practice.pdf").write_bytes(pdf)
    (d / "parent_key.pdf").write_bytes(pdf)
    return d


def test_packet_links_to_the_photo_that_steered_it_not_the_latest(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _obs(rt, "2026-11-02")
    _obs(rt, "2026-11-06")
    _obs(rt, "2026-11-12")  # newer than the packet: must not be claimed as its source
    _packet(rt, "2026-11-07")
    d = ws.packet_detail(rt, "2026-11-07", "nova")
    assert d["photo_date"] == "2026-11-06" and d["photo_index"] == 1


def test_packet_tips_use_the_class_vocabulary(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _plan(rt, rt.family())
    _packet(rt, "2026-10-20", steered="class curriculum")
    tip = ws.packet_detail(rt, "2026-10-20", "nova")["items"][0]["tip"]
    assert "array" in tip and "Class words" in tip


def test_packet_preview_renders_a_real_page_or_says_unavailable(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    from reportlab.pdfgen import canvas

    pdf = tmp_path / "real.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 720, "Nova practice")
    c.showPage()
    c.save()
    _packet(rt, "2026-11-07", pdf=pdf.read_bytes())
    r = ws.packet_preview(rt, "2026-11-07", "nova", page=0, kind="practice")
    assert r["pages"] == 1 and r["image"].startswith("data:image/")
    with pytest.raises(PanelError):
        ws.packet_preview(rt, "2026-11-07", "nova", page=5, kind="practice")
    with pytest.raises(PanelError):
        ws.packet_preview(rt, "2026-11-07", "nova", page=0, kind="../etc")


def test_print_preview_is_larger_than_the_screen_preview(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    from reportlab.pdfgen import canvas

    pdf = tmp_path / "real.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 720, "Nova practice")
    c.save()
    _packet(rt, "2026-11-07", pdf=pdf.read_bytes())
    screen = ws.packet_preview(rt, "2026-11-07", "nova", 0, "practice")
    paper = ws.packet_preview(rt, "2026-11-07", "nova", 0, "practice", 1700)
    assert paper["pages"] == 1 and len(paper["image"]) > len(screen["image"])


def test_child_without_homework_photos_can_still_make_practice(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    card = lambda: next(c for c in ws.today(rt)["children"] if c["id"] == "nova")  # noqa: E731
    assert card()["status"] == "needs_photo"  # nothing to follow yet: ask for a first photo
    cur.save_plan(rt.store, rt.family().child("nova"), curriculum="enVision", sources=[],
                  units=[{"title": "Topic 3: Multiplication Facts", "start": "2020-01-01", "end": "2099-12-31",
                          "skill": "multiplication"}])
    assert card()["status"] in ("make_packet", "off")  # the class plan is enough; no photo demanded
    _obs(rt, "2020-01-01")  # a family that does send photos is still nudged when theirs goes stale
    assert card()["status"] == "needs_photo"


def test_topic_1_never_matches_topic_10(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _plan(rt, rt.family())
    p = ws.propose_shift(rt, "nova", {"unit_title": "Topic 1", "unit_end": "2026-09-30", "skill": ""})
    assert p is None
    p = ws.propose_shift(rt, "nova", {"unit_title": "Topic 3", "unit_end": "2026-11-13", "skill": ""})
    assert p["unit_index"] == 0 and p["delta_days"] == 14 and p["later_units"] == 2


def test_apply_refuses_a_stale_proposal_and_undo_restores(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _plan(rt, rt.family())
    up = rt.store.root / "uploads" / "nova"
    up.mkdir(parents=True)
    mat = {"title": "Room 12 news", "date": "2026-11-02", "kind": "newsletter", "skill": "multiplication",
           "goals": [], "summary": "s", "unit_title": "Topic 3", "unit_end": "2026-11-13"}
    (up / "material_a.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
    with pytest.raises(PanelError, match="changed"):
        ws.apply_material(rt, "nova", "material_a.png", mat, True, expected={"unit_index": 0, "delta_days": 3})
    assert cur.load_plan(rt.store, "nova")["units"][0]["end"] == "2026-10-30"  # nothing written
    assert (up / "material_a.png").exists()  # upload kept so the parent can retry
    r = ws.apply_material(rt, "nova", "material_a.png", mat, True, expected={"unit_index": 0, "delta_days": 14})
    units = cur.load_plan(rt.store, "nova")["units"]
    assert r["shift"]["delta_days"] == 14 and units[0]["end"] == "2026-11-13" and units[2]["start"] == "2027-02-15"
    ws.undo_shift(rt, "nova", 0)
    assert [u["end"] for u in cur.load_plan(rt.store, "nova")["units"]] == ["2026-10-30", "2026-11-20", "2027-02-26"]


def test_add_child_never_overwrites_an_unreadable_family_file(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    family_file.write_text("children: [unclosed\n", encoding="utf-8")
    before = family_file.read_text(encoding="utf-8")
    with pytest.raises(Exception):
        ws.add_child(rt, {"name": "Ollie", "grade": "1"})
    assert family_file.read_text(encoding="utf-8") == before


def test_new_child_does_not_reuse_an_archived_id(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    ws.add_child(rt, {"name": "Ollie", "grade": "1"})
    ws.archive_child(rt, "ollie")
    again = ws.add_child(rt, {"name": "Ollie", "grade": "2"})
    assert again["child"]["id"] != "ollie"
    with pytest.raises(PanelError):
        ws.restore_child(rt, "nope")


def test_reading_correction_is_recorded_with_provenance(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _obs(rt, "2026-11-06")
    r = ws.fix_reading(rt, "nova", -1, 0, {"status": "correct", "child_answer": "24"})
    assert r["changed"]
    o = ws.observation(rt, "nova", -1)
    assert o["items"][0]["corrected"] and o["items"][0]["status"] == "correct"
    with pytest.raises(PanelError):
        ws.fix_reading(rt, "nova", 0, 0, {"status": "great"})
