"""Unclear homework pages must not move the classroom anchor (audit follow-up).

An entirely unclear page (every item low-confidence or needs_recheck) creates no anchor,
changes no topic and refreshes no freshness date until there is credible item evidence,
either from a later clear photo or a parent correction. Genuine attempted wrong answers
read with confidence are credible evidence and still steer normally.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from homework_coach import config, intake
from homework_coach import workspace as ws
from homework_coach.storage import Store
from homework_coach.tools import Runtime

from .test_intake import FakeLlm, _vision, photo  # noqa: F401  (fixture re-export)


def _item(n, expr, answer, status, conf, skill="division", fmt="missing_number_div"):
    return {"number": str(n), "printed_prompt": f"{expr} = ___", "math_expression": expr, "child_answer": answer,
            "attempted": bool(answer), "skill": skill, "format": fmt, "status": status, "confidence": conf}


def _unclear(skill="fractions", fmt="fraction_of_set"):
    # model guessed answers it could not read; local maths disagrees → rechecks also come back unclear
    return _vision(main_skill=skill, lesson="", items=[
        _item(1, "12 / 3", "7", "incorrect", 0.2, skill, fmt),
        _item(2, "20 / 4", "9", "slip", 0.3, skill, fmt)])


_UNCLEAR_REREAD = {"child_answer": "?", "confidence": 0.1}


def _run(store, child, date, data, *rereads, photo_path):
    return intake.run_intake(llm=FakeLlm(data, *rereads), store=store, child=child,
                             image_paths=[str(photo_path)], date=date)


@pytest.fixture
def setup(tmp_path, fake_ctx):
    fam = config.load(fake_ctx.settings["family_config"])
    return Store(root=tmp_path / "data"), fam.child("nova"), fake_ctx


def test_unclear_first_page_creates_no_anchor(setup, photo):
    store, child, _ = setup
    res = _run(store, child, "2026-11-03", _unclear(), _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    assert res["anchor_updated"] is False
    assert res["anchor_held"]  # explained to the parent
    assert store.load_anchor("nova") is None
    assert "## Current classroom anchor" not in store.read_brief("nova")
    assert "## Homework observed — 2026-11-03" in store.read_brief("nova")  # still logged
    assert len(store.observations("nova")) == 1


def test_unclear_page_does_not_change_topic(setup, photo):
    store, child, _ = setup
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    before = store.load_anchor("nova")
    res = _run(store, child, "2026-11-05", _unclear("fractions"), _UNCLEAR_REREAD, _UNCLEAR_REREAD,
               photo_path=photo)
    assert res["anchor_updated"] is False and res["anchor_held"]
    assert store.load_anchor("nova") == before
    assert store.read_brief("nova").count("## Current classroom anchor") == 1


def test_unclear_same_topic_page_does_not_refresh_since(setup, photo):
    store, child, _ = setup
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    before = store.load_anchor("nova")
    _run(store, child, "2026-11-09", _unclear("division", "missing_number_div"), _UNCLEAR_REREAD,
         _UNCLEAR_REREAD, photo_path=photo)
    after = store.load_anchor("nova")
    assert after == before and after["since"] == "2026-11-03"


def test_clear_same_topic_page_still_refreshes_since_and_keeps_topic_since(setup, photo):
    store, child, _ = setup
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    _run(store, child, "2026-11-09", _vision(lesson="Lesson 6-3"), {"child_answer": "5", "confidence": 0.9},
         photo_path=photo)
    a = store.load_anchor("nova")
    assert a["since"] == "2026-11-09" and a["topic_since"] == "2026-11-03" and a["lesson"] == "Lesson 6-3"


def test_confident_wrong_answers_are_credible_evidence(setup, photo):
    """Genuine attempted wrong answers (read clearly, confirmed) still move the anchor."""
    store, child, _ = setup
    data = _vision(main_skill="multiplication", items=[
        _item(1, "6 * 4", "26", "incorrect", 0.95, "multiplication", "equation"),
        _item(2, "7 * 3", "24", "incorrect", 0.9, "multiplication", "equation")])
    res = _run(store, child, "2026-11-03", data, {"child_answer": "26", "confidence": 0.95},
               {"child_answer": "24", "confidence": 0.9}, photo_path=photo)
    assert res["anchor_updated"] is True and not res.get("anchor_held")
    assert store.load_anchor("nova")["skill"] == "multiplication"
    assert res["summary"]["to_revisit"] == ["6 * 4 = ___", "7 * 3 = ___"]  # statuses untouched


def test_mixed_page_with_one_credible_item_steers(setup, photo):
    store, child, _ = setup
    data = _unclear()
    data["items"].append(_item(3, "1 / 2", "1/2", "correct", 0.9, "fractions", "fraction_of_set"))
    res = _run(store, child, "2026-11-03", data, _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    assert res["anchor_updated"] is True and store.load_anchor("nova")["skill"] == "fractions"


def test_page_with_no_items_does_not_steer(setup, photo):
    """An empty reading is not evidence, even if the model guessed a topic label."""
    store, child, _ = setup
    res = _run(store, child, "2026-11-03", _vision(main_skill="fractions", items=[]), photo_path=photo)
    assert res["anchor_updated"] is False and res.get("anchor_held")
    assert store.load_anchor("nova") is None


def test_has_credible_evidence_rules():
    from homework_coach.models import ObservedItem as I
    mk = lambda s, c: I(prompt="p", child_answer="1", status=s, skill="division", format="f", confidence=c)  # noqa
    assert not intake.has_credible_evidence([])
    assert not intake.has_credible_evidence([mk("needs_recheck", 0.9), mk("incorrect", 0.3)])
    assert intake.has_credible_evidence([mk("incorrect", 0.9)])
    assert intake.has_credible_evidence([mk("unattempted", 0.8)])  # a clearly blank printed item is evidence


# -- parent correction ----------------------------------------------------------------------------
def _rt(store: Store, fake_ctx) -> Runtime:
    s = fake_ctx.settings
    return Runtime(get_setting=lambda k, d=None: s.get(k, d), store=store)


def test_parent_correction_makes_unclear_page_usable(setup, photo):
    store, child, ctx = setup
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    _run(store, child, "2026-11-05", _unclear("fractions"), _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    assert store.load_anchor("nova")["skill"] == "division"
    rt = _rt(store, ctx)
    r = ws.fix_reading(rt, "nova", -1, 0, {"status": "correct", "child_answer": "4"})
    assert r["changed"] and r["anchor_updated"] is True
    a = store.load_anchor("nova")
    assert a["skill"] == "fractions" and a["since"] == "2026-11-05" and a["topic_since"] == "2026-11-05"
    assert a["previous_skill"] == "division"
    assert store.read_brief("nova").count("## Current classroom anchor") == 2


def test_correction_that_stays_unclear_does_not_move_anchor(setup, photo):
    store, child, ctx = setup
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    before = store.load_anchor("nova")
    _run(store, child, "2026-11-05", _unclear("fractions"), _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    r = ws.fix_reading(_rt(store, ctx), "nova", -1, 0, {"child_answer": "8"})  # still needs_recheck
    assert r["changed"] and store.observations("nova")[-1].items[0].status == "needs_recheck"
    assert r["anchor_updated"] is False
    assert store.load_anchor("nova") == before


def test_correcting_an_older_page_never_rewinds_anchor(setup, photo):
    store, child, ctx = setup
    _run(store, child, "2026-11-01", _unclear("fractions"), _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    _run(store, child, "2026-11-03", _vision(), {"child_answer": "5", "confidence": 0.9}, photo_path=photo)
    before = store.load_anchor("nova")
    r = ws.fix_reading(_rt(store, ctx), "nova", 0, 0, {"status": "correct", "child_answer": "4"})
    assert r["changed"] and r["anchor_updated"] is False
    assert store.load_anchor("nova") == before


def test_correction_does_not_invent_difficulty(setup, photo):
    store, child, ctx = setup
    _run(store, child, "2026-11-05", _unclear("fractions"), _UNCLEAR_REREAD, _UNCLEAR_REREAD, photo_path=photo)
    ws.fix_reading(_rt(store, ctx), "nova", -1, 0, {"status": "correct", "child_answer": "4"})
    assert store.load_skills("nova") == {}
    assert store.feedback("nova") == []
