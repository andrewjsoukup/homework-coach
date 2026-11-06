"""Demo fixtures (card t_286440eb): fictional family, synthetic homework, 3-day progression.

These keep the demo honest: ground truth agrees with the arithmetic, the story in
scenario.yaml agrees with the real difficulty engine, and the fixture vision
backend returns the right page for the bytes the plugin will send.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from homework_coach import config as cfg
from homework_coach import difficulty
from homework_coach.models import DIMENSIONS, Feedback, Observation, SkillState

from .conftest import ROOT

sys.path.insert(0, str(ROOT / "demo"))
import scenario as sc  # noqa: E402

SCN = sc.load_scenario()
TRUTHS = sorted(sc.HOMEWORK_DIR.glob("*.truth.json"))
ARITH = re.compile(r"^\s*(\d+)\s*([x+\-/])\s*(\d+)\s*=\s*_*\s*$")


def test_demo_family_valid_and_two_grades():
    fam = cfg.load(SCN["family_path"])
    assert len(fam.children) == 2
    assert len({c.grade for c in fam.children}) == 2
    assert {c.id for c in fam.children} == {"nova", "pip"}
    # the story never rates more items than the child's packet holds
    budget = {c.id: c.item_budget for c in fam.children}
    for day in SCN["days"]:
        for child, fb in (day.get("feedback") or {}).items():
            assert sum(len(r) for r in fb["ratings"].values()) <= budget[child], (day["date"], child)


def test_every_scenario_image_and_truth_exists():
    for day in SCN["days"]:
        for intake in day.get("intake") or []:
            assert intake["image_path"].is_file(), intake
            assert intake["truth_path"].is_file(), intake
            assert intake["image_path"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("path", TRUTHS, ids=lambda p: p.stem)
def test_truth_matches_observation_model(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    obs = Observation.from_dict(raw)
    assert obs.child_id in {"nova", "pip"}
    assert path.name.startswith(f"{obs.child_id}_{obs.date}_")
    assert obs.source == path.with_suffix("").with_suffix(".png").name
    assert obs.scored_items(), "a page with nothing scorable is a useless demo"
    assert set(obs.skills) == {i.skill for i in obs.items if i.status != "not_assigned"}


@pytest.mark.parametrize("path", TRUTHS, ids=lambda p: p.stem)
def test_truth_arithmetic_is_computed_not_typed(path: Path):
    """Every bare fact's expected answer is right, and status agrees with the child's answer."""
    ops = {"x": lambda a, b: a * b, "+": lambda a, b: a + b, "-": lambda a, b: a - b, "/": lambda a, b: a // b}
    obs = Observation.from_dict(json.loads(path.read_text(encoding="utf-8")))
    for it in obs.items:
        body = it.prompt.split(".", 1)[-1]
        m = ARITH.match(body)
        if m:
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            assert it.expected_answer == str(ops[op](a, b)), it
        if it.status == "correct" and it.child_answer and it.expected_answer and it.child_answer.isdigit():
            assert it.child_answer == it.expected_answer, it
        if it.status in ("incorrect", "slip") and it.child_answer and it.expected_answer and it.child_answer.isdigit():
            assert it.child_answer != it.expected_answer, it


def test_truth_covers_the_scoring_rules_the_demo_shows():
    statuses = {i.status for p in TRUTHS for i in Observation.from_dict(json.loads(p.read_text("utf-8"))).items}
    for needed in ("correct", "incorrect", "slip", "checking_target", "beyond_grade", "unattempted", "not_assigned"):
        assert needed in statuses, needed


def test_fixture_vision_matches_by_bytes_and_name():
    fv = sc.FixtureVision()
    for p in TRUTHS:
        png = p.with_suffix("").with_suffix(".png")
        by_bytes = fv.complete_structured(instructions="observe", input=[{"type": "image", "data": png.read_bytes()}])
        by_name = fv.complete_structured(instructions="observe", input=[{"type": "text", "text": "x"},
                                                                        {"type": "image", "file_name": png.name}])
        assert by_bytes.parsed == by_name.parsed == json.loads(p.read_text("utf-8"))
    # a text-only narrow re-ask follows the last page
    again = fv.complete_structured(instructions="re-check item 3", input=[{"type": "text", "text": "item 3"}])
    assert again.parsed["source"] == png.name
    with pytest.raises(ValueError):
        sc.FixtureVision().complete_structured(instructions="x", input=[{"type": "text", "text": "no image"}])


def test_ratings_mapping_onto_packet_items():
    items = [{"id": "1", "skill": "a"}, {"id": "2", "skill": "b"}, {"id": "3", "skill": "a"}]
    r, s = sc.ratings_for_packet({"a": ["I", "N", "S"], "b": ["S"], "zzz": ["I"]}, items)
    assert r == {"1": "I", "3": "N", "2": "S"} and s == {"1": "a", "3": "a", "2": "b"}
    r, s = sc.ratings_for_packet({"a": ["I", "S"], "b": ["N"]}, None)
    assert sc.format_ratings(r) == "1I 2S 3N" and s == {"1": "a", "2": "a", "3": "b"}
    assert difficulty.parse_ratings(sc.format_ratings(r)) == r


def _replay():
    """Feed scenario feedback through the real engine, yielding per-day decisions and dims."""
    states: dict[str, dict[str, SkillState]] = {}
    history: dict[str, list[Feedback]] = {}
    for day in SCN["days"]:
        decisions, dims = {}, {}
        for child, fb in (day.get("feedback") or {}).items():
            ratings, skills = sc.ratings_for_packet(fb["ratings"], None)
            history.setdefault(child, []).append(Feedback(date=day["date"], child_id=child, packet_date=day["date"],
                                                          item_ratings=ratings, item_skills=skills))
            st = states.setdefault(child, {})
            for s in skills.values():
                st.setdefault(s, SkillState(skill=s))
            decisions[child] = difficulty.update_child(st, history[child], date=day["date"])
        for child, st in states.items():
            dims[child] = {s: [v.dims[d] for d in DIMENSIONS] for s, v in st.items()}
        yield day, decisions, dims


def test_three_day_progression_matches_engine():
    days = list(_replay())
    assert len(days) == 3
    for day, decisions, dims in days:
        for child, expected in day["expect_after_feedback"].items():
            got = {s: decisions[child][s] for s in expected}
            assert got == expected, (day["date"], child, decisions[child])
            # every skill the child has rated so far is either listed or holding
            for s, d in decisions[child].items():
                assert s in expected or d == "hold", (day["date"], child, s, d)
        assert dims == day["expect_dims"], day["date"]


def test_progression_shows_up_down_and_new_topic():
    seen = {d for _, decisions, _ in _replay() for c in decisions.values() for d in c.values()}
    assert {"up", "down", "hold"} <= seen
    day3 = SCN["days"][2]
    assert {i["child"] for i in day3["intake"]} == {"nova", "pip"}
    for child, exp in day3["expect_packet"].items():
        assert exp["new_anchor"] and exp["same_item_budget"]


def test_new_topic_anchor_matches_homework_lesson():
    by_child = {}
    for day in SCN["days"]:
        for intake in day.get("intake") or []:
            by_child.setdefault(intake["child"], []).append(json.loads(intake["truth_path"].read_text("utf-8")))
    for child, obs in by_child.items():
        assert obs[0]["lesson"] != obs[-1]["lesson"], child
        assert SCN["days"][2]["expect_packet"][child]["new_anchor"] == obs[-1]["lesson"]
        assert set(obs[-1]["skills"]) >= set(SCN["days"][2]["expect_packet"][child]["target"])


def test_demo_runner_end_to_end(tmp_path: Path):
    """The runner drives the real handlers; stand-ins are used only where a stage is unimplemented."""
    import run_demo

    res = run_demo.run(tmp_path / "out")
    assert len(res["days"]) == 3
    transcript = (tmp_path / "out" / "transcript.md").read_text(encoding="utf-8")
    assert "Maple" in transcript and "Day 3" in transcript
    for day, (sday, decisions, _) in zip(res["days"], _replay()):
        for child, fb in day["feedback"].items():
            assert fb["ok"], fb
            moved = {s: d for s, d in decisions[child].items() if d != "hold"}
            if day["packet"].get("ok"):
                continue  # real packets may group items differently; engine replay already checked
            assert fb["changes"] == moved, (sday["date"], child)
    data = tmp_path / "out" / "data"
    assert sorted(p.name for p in (data / "children").iterdir()) == ["nova", "pip"]
    assert sorted(p.name for p in (data / "packets").iterdir()) == [d["date"] for d in SCN["days"]]


def test_generator_script_is_self_contained():
    """make_homework.py: PEP 723 deps, no OS font paths, seeded RNG only."""
    src = (ROOT / "demo" / "make_homework.py").read_text(encoding="utf-8")
    assert "# /// script" in src and "pillow" in src
    assert "truetype(" not in src and "Fonts" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("random", "randint", "uniform", "shuffle"):
            assert isinstance(node.func.value, (ast.Attribute, ast.Name)) and getattr(node.func.value, "id", "") != "random", \
                "use a seeded random.Random instance"
