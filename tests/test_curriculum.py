"""Preloaded curriculum + teacher materials steer packets between homework photos."""
from __future__ import annotations

import json

from homework_coach import curriculum
from homework_coach.plugin import register


def _tools(fake_ctx):
    register(fake_ctx)
    return {k: v["handler"] for k, v in fake_ctx.tools.items()}


UNITS = [
    {"title": "Topic 1: Addition strategies", "skill": "add_sub", "start": "2026-09-01", "end": "2026-10-15",
     "goals": ["Add within 1,000 using place value"]},
    {"title": "Topic 2: Meanings of multiplication", "skill": "multiplication", "start": "2026-10-16",
     "end": "2026-12-01", "goals": ["Interpret products as equal groups", "Use arrays"], "standards": ["3.OA.A.1"]},
    {"title": "Topic 9: Area and perimeter", "start": "2027-02-01", "end": "2027-03-01"},
]


def test_set_curriculum_validates_and_reports(fake_ctx):
    tools = _tools(fake_ctx)
    child = json.loads(tools["homework_coach_status"]({}))["children"][0]["id"]
    bad = json.loads(tools["homework_coach_set_curriculum"](
        {"child_id": child, "units": [{"title": "x", "skill": "calculus", "start": "2026-09-01", "end": "2026-09-02"}],
         "sources": []}))
    assert bad["ok"] is False and "skill must be one of" in bad["error"]
    ok = json.loads(tools["homework_coach_set_curriculum"](
        {"child_id": child, "curriculum": "District Grade 3 Math", "units": UNITS, "sources": ["https://example.org/pacing"]}))
    assert ok["ok"], ok
    assert "Recorded but not practised" in ok["message"]  # area/perimeter has no practice skill yet


def test_plan_steers_when_no_recent_photo(fake_ctx):
    tools = _tools(fake_ctx)
    child = json.loads(tools["homework_coach_status"]({}))["children"][0]["id"]
    tools["homework_coach_set_curriculum"]({"child_id": child, "units": UNITS, "sources": ["x"]})
    made = json.loads(tools["homework_coach_generate_packet"]({"date": "2026-11-09", "child_ids": [child]}))
    assert made["ok"], made
    assert "Multiplication" in made["message"]
    assert "Class unit: Topic 2: Meanings of multiplication" in made["message"]


def test_material_saved_and_goals_merge(fake_ctx, tmp_path):
    tools = _tools(fake_ctx)
    child = json.loads(tools["homework_coach_status"]({}))["children"][0]["id"]
    tools["homework_coach_set_curriculum"]({"child_id": child, "units": UNITS, "sources": ["x"]})
    note = tmp_path / "newsletter.txt"
    note.write_text("This week: multiplication with arrays, skip counting by 5s.", encoding="utf-8")
    out = json.loads(tools["homework_coach_add_material"](
        {"child_id": child, "path": str(note), "title": "Week 9 newsletter", "date": "2026-11-02",
         "skill": "multiplication", "goals": ["Skip count by 5s"]}))
    assert out["ok"], out
    from homework_coach.tools import Runtime  # noqa: F401
    rt_store = fake_ctx  # noqa: F841
    rep = json.loads(tools["homework_coach_progress"]({"child_id": child}))
    c = rep["children"][0]
    assert c["teacher_materials"] == 1


def test_steer_priority_unit_window():
    plan = {"units": [curriculum.normalize_unit(u, "3") for u in UNITS[:2]]}
    assert curriculum.unit_on(plan, "2026-10-20")["skill"] == "multiplication"
    assert curriculum.next_unit(plan, "2026-10-01")["title"].startswith("Topic 2")
    assert curriculum.unit_on(plan, "2027-06-01") is None
