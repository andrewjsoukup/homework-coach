"""Intake with a fake ctx.llm and a generated, fictional homework photo."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from homework_coach import intake, plugin
from homework_coach.storage import Store

from .conftest import FakeCtx


@dataclass
class _Res:
    parsed: Any
    text: str = ""


class FakeLlm:
    """Mimics PluginLlm.complete_structured; returns queued responses and records calls."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete_structured(self, **kw):
        self.calls.append(kw)
        return _Res(parsed=self.responses.pop(0) if self.responses else {"child_answer": "", "confidence": 0})


@pytest.fixture
def photo(tmp_path) -> Path:
    """A fictional worksheet image drawn with Pillow (no real child's work)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    for n, line in enumerate(["Lesson 6-2: Division as sharing", "1. 24 / 6 = 4", "2. 18 / 3 = 5",
                              "3. 30 / 5 = 6", "4. 12 / 4 = (skip)"]):
        d.text((20, 20 + 40 * n), line, fill="black")
    p = tmp_path / "Nova homework p1.png"
    img.save(p)
    return p


def _vision(**over):
    base = {
        "lesson": "Lesson 6-2: Division as sharing",
        "main_skill": "division",
        "items": [
            {"number": "1", "printed_prompt": "24 ÷ 6 = ___", "math_expression": "24 / 6", "child_answer": "4",
             "attempted": True, "skill": "division", "format": "missing_number_div", "status": "correct",
             "confidence": 0.95},
            {"number": "2", "printed_prompt": "18 ÷ 3 = ___", "math_expression": "18 / 3", "child_answer": "5",
             "attempted": True, "skill": "division", "format": "missing_number_div", "status": "incorrect",
             "confidence": 0.9},
            {"number": "3", "printed_prompt": "30 ÷ 5 = ___", "math_expression": "30 / 5", "child_answer": "6",
             "attempted": True, "skill": "division", "format": "missing_number_div", "status": "correct",
             "intermediate_error": True, "confidence": 0.9},
            {"number": "4", "printed_prompt": "12 ÷ 4 = ___", "math_expression": "12 / 4", "child_answer": "",
             "attempted": False, "marks": "crossed out", "skill": "division", "format": "missing_number_div",
             "status": "incorrect", "confidence": 0.9},
            {"number": "5", "printed_prompt": "Write the fact family for 3, 7, 21", "math_expression": "",
             "child_answer": "3x7=21 ...", "attempted": True, "skill": "division", "format": "fact_family",
             "status": "correct", "confidence": 0.8},
        ],
        "teacher_feedback": "Nice sharing pictures!",
    }
    base.update(over)
    return base


def test_normalise_blank_is_never_wrong():
    it, rc = intake.normalise_item({"printed_prompt": "5+5", "math_expression": "5+5", "child_answer": "",
                                    "attempted": False, "skill": "add_sub", "format": "equation",
                                    "status": "incorrect", "confidence": 1})
    assert it.status == "unattempted" and not it.attempted and not rc


def test_normalise_model_wrong_math_right_is_corrected():
    it, rc = intake.normalise_item({"printed_prompt": "6 × ___ = 42", "math_expression": "6 * ? = 42",
                                    "child_answer": "7", "attempted": True, "skill": "multiplication",
                                    "format": "missing_factor", "status": "incorrect", "confidence": 0.9})
    assert it.status == "correct" and it.expected_answer == "7" and rc


def test_normalise_model_says_correct_but_math_disagrees():
    it, rc = intake.normalise_item({"printed_prompt": "8 × 7", "math_expression": "8*7", "child_answer": "54",
                                    "attempted": True, "skill": "multiplication", "format": "equation",
                                    "status": "correct", "confidence": 0.9})
    assert it.status == "needs_recheck" and rc


def test_beyond_grade_not_overridden():
    it, _ = intake.normalise_item({"printed_prompt": "7 ÷ 2", "math_expression": "7/2", "child_answer": "7/2",
                                   "attempted": True, "skill": "division", "format": "equation",
                                   "status": "beyond_grade", "confidence": 0.9})
    assert it.status == "beyond_grade"


def test_run_intake_end_to_end(tmp_path, photo, fake_ctx):
    from homework_coach import config
    fam = config.load(fake_ctx.settings["family_config"])
    store = Store(root=tmp_path / "data")
    # item 2 is wrong (18/3=6 not 5) → one narrow re-ask; re-read confirms "5"
    llm = FakeLlm(_vision(), {"child_answer": "5", "confidence": 0.9})
    res = intake.run_intake(llm=llm, store=store, child=fam.child("nova"), image_paths=[str(photo)],
                            date="2026-11-03", parent_note="Lesson 6-2")
    # vision call shape: public ctx.llm API, registered aux task, image bytes, no model/provider override
    first = llm.calls[0]
    assert first["task"] == "homework_vision" and "model" not in first and "provider" not in first
    assert any(b.get("type") == "image" and b["data"].startswith(b"\x89PNG") for b in first["input"])
    assert len(llm.calls) == 2 and "item 2" in llm.calls[1]["instructions"]

    s = res["summary"]
    assert s["attempted"] == 4 and s["not_scored"] == 1  # crossed-out item 4 not scored
    assert s["correct"] == 2  # items 1 and 5
    assert s["checking_targets"] == ["30 ÷ 5 = ___"]
    assert s["to_revisit"] == ["18 ÷ 3 = ___"]  # model's explicit "incorrect" is kept, confirmed by re-read
    assert res["anchor_updated"] and res["main_skill"] == "division"
    assert "brief updated" in res["next_step"].lower() and "no packet" in res["next_step"].lower()

    brief = store.read_brief("nova")
    assert "## Current classroom anchor — 2026-11-03" in brief
    assert "## Homework observed — 2026-11-03" in brief
    assert "not attempted (not scored)" in brief
    assert Path(res["sources_saved"][0]).name.startswith("2026-11-03_")
    assert store.load_anchor("nova")["skill"] == "division"
    assert len(store.observations("nova")) == 1


def test_overturned_correct_becomes_slip_when_format_right_elsewhere(tmp_path, photo, fake_ctx):
    from homework_coach import config
    fam = config.load(fake_ctx.settings["family_config"])
    v = _vision()
    v["items"][1]["status"] = "correct"  # model missed that 18 ÷ 3 = 5 is wrong
    llm = FakeLlm(v, {"child_answer": "5", "confidence": 0.9})
    res = intake.run_intake(llm=llm, store=Store(root=tmp_path / "d"), child=fam.child("nova"),
                            image_paths=[str(photo)], date="2026-11-03")
    assert res["summary"]["likely_slips"] == ["18 ÷ 3 = ___"]


def test_persisted_observation_shape_is_accepted():
    it, _ = intake.normalise_item({"prompt": "5. 20 / 4 = ___", "child_answer": "16", "status": "incorrect",
                                   "skill": "div.equal_sharing", "format": "bare division fact", "confidence": 1.0})
    assert it.skill == "division" and it.expected_answer == "5" and it.status == "incorrect"
    assert it.note.startswith("#5")


def test_same_topic_does_not_duplicate_anchor(tmp_path, photo, fake_ctx):
    from homework_coach import config
    fam = config.load(fake_ctx.settings["family_config"])
    store = Store(root=tmp_path / "data")
    for d in ("2026-11-03", "2026-11-04"):
        intake.run_intake(llm=FakeLlm(_vision(), {"child_answer": "5", "confidence": 0.9}), store=store,
                          child=fam.child("nova"), image_paths=[str(photo)], date=d)
    assert store.read_brief("nova").count("## Current classroom anchor") == 1
    # topic change → new dated anchor, old topic becomes review
    intake.run_intake(llm=FakeLlm(_vision(main_skill="fractions", items=[{
        "printed_prompt": "One half of the circle is shaded", "child_answer": "1/2",
        "skill": "fractions", "format": "fraction_of_set", "status": "correct", "confidence": 0.9,
        "attempted": True,
    }])), store=store,
                      child=fam.child("nova"), image_paths=[str(photo)], date="2026-11-05")
    a = store.load_anchor("nova")
    assert a["skill"] == "fractions" and a["previous_skill"] == "division"
    assert store.read_brief("nova").count("## Current classroom anchor") == 2


def test_recheck_budget_is_bounded(tmp_path, photo, fake_ctx):
    from homework_coach import config
    fam = config.load(fake_ctx.settings["family_config"])
    wrong = [{"number": str(n), "printed_prompt": f"{n} + 1", "math_expression": f"{n}+1", "child_answer": "0",
              "attempted": True, "skill": "add_sub", "format": f"f{n}", "status": "incorrect", "confidence": 0.9}
             for n in range(1, 7)]
    llm = FakeLlm(_vision(items=wrong))
    intake.run_intake(llm=llm, store=Store(root=tmp_path / "d"), child=fam.child("nova"),
                      image_paths=[str(photo)], date="2026-11-03")
    assert len(llm.calls) == 1 + intake.MAX_RECHECKS


def test_intake_tool_without_llm_reports_clearly(fake_ctx, photo):
    plugin.register(fake_ctx)  # FakeCtx.llm is None
    out = json.loads(fake_ctx.tools["homework_coach_intake"]["handler"](
        {"child_id": "nova", "image_paths": [str(photo)], "date": "2026-11-03"}))
    assert out["ok"] is False and "ctx.llm" in out["error"]


def test_intake_tool_rejects_non_images(fake_ctx, tmp_path):
    fake_ctx.llm = FakeLlm(_vision())
    plugin.register(fake_ctx)
    bad = tmp_path / "notes.txt"
    bad.write_text("x")
    out = json.loads(fake_ctx.tools["homework_coach_intake"]["handler"]({"child_id": "nova", "image_paths": [str(bad)]}))
    assert out["ok"] is False and "not an image" in out["error"]


def test_tools_end_to_end_intake_then_packet(fake_ctx, photo):
    fake_ctx.llm = FakeLlm(_vision(), {"child_answer": "5", "confidence": 0.9})
    plugin.register(fake_ctx)
    h = fake_ctx.tools
    out = json.loads(h["homework_coach_intake"]["handler"](
        {"child_id": "nova", "image_paths": [str(photo)], "date": "2026-11-03"}))
    assert out["ok"], out
    pk = json.loads(h["homework_coach_generate_packet"]["handler"]({"date": "2026-11-04", "child_ids": ["nova"]}))
    assert pk["ok"], pk
    assert all(m.startswith("MEDIA:") and m.endswith(".pdf") for m in pk["media"])
    data = json.loads((Path(pk["folder"]) / "packet.json").read_text(encoding="utf-8"))
    assert data["children"]["nova"]["target_skill"] == "division"
    fb = json.loads(h["homework_coach_record_feedback"]["handler"](
        {"child_id": "nova", "packet_date": "2026-11-04", "ratings": "1I 2I 3I 4I 5I 6I"}))
    assert fb["ok"] and not fb["unknown_items"]
    bad = json.loads(h["homework_coach_generate_packet"]["handler"]({"date": "11/04/2026"}))
    assert bad["ok"] is False
