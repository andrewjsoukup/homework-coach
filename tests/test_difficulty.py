import pytest

from homework_coach import difficulty as d
from homework_coach.models import Feedback, SkillState


def fb(ratings: dict, skills: dict, date="2026-01-05") -> Feedback:
    return Feedback(date=date, child_id="nova", packet_date=date, item_ratings=ratings, item_skills=skills)


@pytest.mark.parametrize("raw,expected", [
    ("1I 2S 3N", {"1": "I", "2": "S", "3": "N"}),
    ("1:i, 2:s", {"1": "I", "2": "S"}),
    ("q1=I q2=N", {"q1": "I", "q2": "N"}),
])
def test_parse_ratings(raw, expected):
    assert d.parse_ratings(raw) == expected


@pytest.mark.parametrize("raw", ["", "1X", "hello"])
def test_parse_ratings_rejects(raw):
    with pytest.raises(ValueError):
        d.parse_ratings(raw)


def test_hold_without_feedback():
    assert d.decide(SkillState("division"), []) == "hold"


def test_up_on_consistent_independent():
    hist = [fb({"1": "I", "2": "I"}, {"1": "division", "2": "division"})]
    assert d.decide(SkillState("division"), hist) == "up"


def test_single_I_is_not_enough():
    hist = [fb({"1": "I"}, {"1": "division"})]
    assert d.decide(SkillState("division"), hist) == "hold"


def test_any_recent_N_steps_down():
    hist = [fb({"1": "I", "2": "I"}, {"1": "x", "2": "x"}), fb({"1": "I", "2": "N"}, {"1": "x", "2": "x"})]
    assert d.decide(SkillState("x"), hist) == "down"


def test_supported_holds():
    hist = [fb({"1": "I", "2": "S"}, {"1": "x", "2": "x"})]
    assert d.decide(SkillState("x"), hist) == "hold"


def test_up_moves_exactly_one_dimension_and_rotates():
    s = SkillState("x")
    before = dict(s.dims)
    d.apply(s, "up")
    changed = [k for k in s.dims if s.dims[k] != before[k]]
    assert changed == ["scaffold"]
    d.apply(s, "up")
    assert s.raised == ["scaffold", "steps"]


def test_down_reverts_most_recent_raise_and_floors():
    s = SkillState("x")
    d.apply(s, "up")
    d.apply(s, "up")
    d.apply(s, "down")
    assert s.dims["steps"] == 1 and s.dims["scaffold"] == 2
    floor = SkillState("y")
    d.apply(floor, "down")
    assert all(v == 1 for v in floor.dims.values())


def test_levels_clamp():
    s = SkillState("x")
    for _ in range(40):
        d.apply(s, "up")
    assert all(v <= d.MAX_LEVEL for v in s.dims.values()) and s.level == d.MAX_LEVEL


def test_update_child_caps_moving_skills_and_prioritises_down():
    skills = {k: SkillState(k) for k in ("a", "b", "c")}
    hist = [fb({"1": "I", "2": "I", "3": "I", "4": "I", "5": "N"},
               {"1": "a", "2": "a", "3": "b", "4": "b", "5": "c"})]
    res = d.update_child(skills, hist)
    assert res["c"] == "down"
    assert sum(v != "hold" for v in res.values()) == d.MAX_SKILLS_MOVED_PER_PACKET
