"""Verifier negative tests: it must catch wrong answers, miscounted visuals and leaks."""
import copy
import random

from homework_coach import verify
from homework_coach.generators import GENERATORS, Gen
from homework_coach.models import DIMENSIONS, PacketItem

DIMS = {d: 1 for d in DIMENSIONS}


def _item(fmt, skill, seed=1, grade="3"):
    it = GENERATORS[fmt](Gen(random.Random(seed), grade, DIMS, skill))
    it.id = "1"
    assert verify.check_item(it) == []
    return it


def test_wrong_answer_caught():
    it = _item("missing_factor", "multiplication")
    it.answer = str(int(it.answer) + 1)
    assert any("recomputed" in e for e in verify.check_item(it))


def test_wrong_compare_symbol_caught():
    it = _item("compare_products", "multiplication")
    it.answer = {"<": ">", ">": "<", "=": "<"}[it.answer]
    assert verify.check_item(it)


def test_array_count_mismatch_caught():
    it = _item("array_to_equation", "multiplication")
    it.visual_inventory["cols"] += 1
    assert any("array" in e for e in verify.check_item(it))


def test_bar_total_mismatch_caught():
    it = _item("bar_model", "add_sub", grade="2")
    it.visual_inventory["true_total"] += 1
    assert verify.check_item(it)


def test_groups_prompt_vs_drawing_caught():
    it = _item("equal_groups", "multiplication")
    it.visual_inventory["per_group"] += 1
    assert verify.check_item(it)


def test_ten_frame_overfill_caught():
    it = _item("ten_frame", "count", grade="K")
    it.visual_inventory["filled"] = [11]
    assert verify.check_item(it)


def test_select_all_requires_a_wrong_option():
    it = _item("select_all_equivalent", "multiplication")
    a, b = it.spec["target"].split("*")
    it.spec["options"] = [f"{a} × {b}", f"{b} × {a}"]
    assert any("at least one" in e for e in verify.check_item(it))


def test_fact_family_must_be_true():
    it = _item("fact_family", "division")
    bad = copy.deepcopy(it)
    bad.spec["equations"][2] = bad.spec["equations"][2].replace("=", "= 1 +")
    assert verify.check_item(bad)


def test_answer_on_child_page_caught():
    it = _item("fact_family", "division")
    it.hint = it.answer
    assert any("child page" in e for e in verify.check_item(it))


def test_unknown_spec_kind():
    it = PacketItem(id="1", skill="x", format="x", prompt="p", answer="1", worked_solution="", spec={"kind": "zzz"})
    assert verify.check_item(it)


def test_budget_and_duplicate_ids():
    a = _item("missing_factor", "multiplication", 1)
    b = _item("missing_factor", "multiplication", 2)
    errs = verify.check_items([a, b], budget=3)
    assert any("duplicate" in e for e in errs) and any("budget" in e for e in errs)
