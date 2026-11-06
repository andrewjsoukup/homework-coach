import copy
import json

import pytest
import yaml

from homework_coach import config as cfg

from .conftest import EXAMPLE_FAMILY, ROOT


def example() -> dict:
    return yaml.safe_load(EXAMPLE_FAMILY.read_text(encoding="utf-8"))


def test_example_family_is_valid():
    fam = cfg.validate(example())
    assert fam.family_id == "maple"
    assert [c.id for c in fam.children] == ["nova", "pip"]
    nova, pip = fam.children
    assert nova.schedule.to_cron() == "0 9 * * 1-6"
    assert pip.schedule.to_cron() == "30 8 * * 1,3,5"
    assert pip.reading_support is True and nova.reading_support is False


@pytest.mark.parametrize("minutes,grade,expected", [(15, "3", 6), (5, "3", 3), (60, "5", 12), (30, "K", 6), (8, "K", 3)])
def test_item_budget(minutes, grade, expected):
    raw = example()
    raw["children"][0].update(minutes_per_day=minutes, grade=grade)
    assert cfg.validate(raw).children[0].item_budget == expected


@pytest.mark.parametrize("days,expected", [
    (["mon", "tue", "wed", "thu", "fri"], "1-5"),
    (["sun", "mon", "tue", "wed", "thu", "fri", "sat"], "*"),
    (["sat", "sun"], "0,6"),
    (["mon", "tue", "thu", "fri", "sat"], "1,2,4-6"),
])
def test_schedule_cron(days, expected):
    assert cfg.Schedule(tuple(days), "07:05").to_cron() == f"5 7 * * {expected}"


BAD_CASES = [
    ("family_id", "Bad Id", "family_id"),
    ("timezone", "Mars/Olympus", "timezone"),
    ("extra", 1, "unknown keys"),
]


@pytest.mark.parametrize("key,value,needle", BAD_CASES)
def test_family_level_errors(key, value, needle):
    raw = example()
    raw[key] = value
    with pytest.raises(cfg.ConfigError) as e:
        cfg.validate(raw)
    assert needle in str(e.value)


@pytest.mark.parametrize("field,value,needle", [
    ("grade", "13", "grade"),
    ("minutes_per_day", 2, "minutes_per_day"),
    ("minutes_per_day", True, "minutes_per_day"),
    ("subjects", ["art"], "subjects"),
    ("id", "Nova!", "id"),
    ("schedule", {"days": ["funday"], "time": "9am"}, "schedule"),
])
def test_child_errors(field, value, needle):
    raw = example()
    raw["children"][0][field] = value
    with pytest.raises(cfg.ConfigError) as e:
        cfg.validate(raw)
    assert needle in str(e.value)


def test_duplicate_child_ids():
    raw = example()
    raw["children"].append(copy.deepcopy(raw["children"][0]))
    with pytest.raises(cfg.ConfigError, match="duplicate"):
        cfg.validate(raw)


def test_errors_are_collected_together():
    raw = example()
    raw["family_id"] = "X"
    raw["children"][0]["grade"] = "99"
    with pytest.raises(cfg.ConfigError) as e:
        cfg.validate(raw)
    assert len(e.value.errors) >= 2


def test_load_missing_file(tmp_path):
    with pytest.raises(cfg.ConfigError, match="not found"):
        cfg.load(tmp_path / "nope.yaml")


def test_json_schema_agrees_with_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "schemas" / "family.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    good = example()
    assert not list(v.iter_errors(good))
    for mutate in (
        lambda r: r.update(family_id="Bad Id"),
        lambda r: r["children"][0].update(grade="13"),
        lambda r: r["children"][0].update(minutes_per_day=99),
        lambda r: r["children"][0].update(subjects=["art"]),
        lambda r: r["children"][0].update(nickname="x"),
        lambda r: r.update(schedule={"days": ["mon"], "time": "25:00"}),
    ):
        raw = example()
        mutate(raw)
        assert list(v.iter_errors(raw)), raw
        with pytest.raises(cfg.ConfigError):
            cfg.validate(raw)
