"""Progress report: class focus from photos, independence trend from ratings."""
from __future__ import annotations

import json

from homework_coach.plugin import register


def test_progress_report_and_slash(fake_ctx):
    register(fake_ctx)
    tools = {k: v["handler"] for k, v in fake_ctx.tools.items()}
    out = json.loads(tools["homework_coach_progress"]({}))
    assert out["ok"], out
    assert out["message"].startswith("Homework Coach progress")
    names = [c["name"] for c in out["children"]]
    assert names and all(n in out["message"] for n in names)
    # no photo yet → the report asks for one instead of guessing class focus
    assert "no homework photo yet" in out["message"]
    cmd = fake_ctx.commands["homework"]
    assert cmd("progress").startswith("Homework Coach progress")
    assert json.loads(tools["homework_coach_progress"]({"child_id": "ghost"}))["ok"] is False


def test_progress_counts_ratings(fake_ctx):
    register(fake_ctx)
    tools = {k: v["handler"] for k, v in fake_ctx.tools.items()}
    child = json.loads(tools["homework_coach_status"]({}))["children"][0]["id"]
    made = json.loads(tools["homework_coach_generate_packet"]({"child_ids": [child]}))
    assert made["ok"], made
    json.loads(tools["homework_coach_record_feedback"]({"child_id": child, "ratings": "1=I 2=I 3=S"}))
    rep = json.loads(tools["homework_coach_progress"]({"child_id": child}))
    c = rep["children"][0]
    assert c["rated_practice_days"] == 1
    assert c["independent_now"] == round(2 / 3, 2)
