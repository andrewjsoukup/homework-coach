"""Registration contract: what plugin.yaml declares == what register() registers."""
import json
import re

import yaml

from homework_coach import plugin
from homework_coach.models import Observation, ObservedItem
from homework_coach.storage import Store

from .conftest import ROOT, FakeCtx

MANIFEST = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def test_manifest_basics():
    assert MANIFEST["name"] == "homework-coach"
    assert re.fullmatch(r">=\d+\.\d+\.\d+", MANIFEST["requires_hermes"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", MANIFEST["version"])
    for forbidden in ("requires_env", "requires_auth", "oauth"):
        assert not MANIFEST.get(forbidden)
    assert not any(v.get("type") == "secret" for v in MANIFEST["config_schema"].values())


def test_version_matches_package():
    import homework_coach
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{MANIFEST["version"]}"' in py
    assert homework_coach.__version__ == MANIFEST["version"]


def test_declared_tools_match_registered(fake_ctx):
    plugin.register(fake_ctx)
    assert sorted(fake_ctx.tools) == sorted(MANIFEST["provides_tools"])
    assert sorted(fake_ctx.hooks) == sorted(MANIFEST.get("provides_hooks") or [])
    for name, t in fake_ctx.tools.items():
        assert t["schema"]["name"] == name and t["toolset"] == plugin.TOOLSET


def test_other_registrations(fake_ctx):
    plugin.register(fake_ctx)
    assert "homework" in fake_ctx.commands
    assert fake_ctx.aux_tasks[plugin.AUX_TASK]["inherit_from"] == "vision"
    assert "workflow" in fake_ctx.skills and fake_ctx.skills["workflow"].is_file()
    bp = fake_ctx.blueprints["daily-packet"]
    slot_names = {s["name"] for s in bp["slots"]}
    for ph in re.findall(r"{(\w+)}", bp["schedule_template"]):
        assert ph in slot_names or ph in ("minute", "hour")


def test_status_tool(fake_ctx, tmp_path):
    plugin.register(fake_ctx)
    out = json.loads(fake_ctx.tools["homework_coach_status"]["handler"]({}))
    assert out["ok"] and [c["id"] for c in out["children"]] == ["nova", "pip"]
    assert out["children"][0]["schedule"]["cron"] == "0 9 * * 1-6"


def test_handlers_never_raise_on_bad_config(tmp_path):
    ctx = FakeCtx({"family_config": str(tmp_path / "missing.yaml")})
    plugin.register(ctx)
    for name, t in ctx.tools.items():
        out = json.loads(t["handler"]({"child_id": "nova", "packet_date": "2026-01-05", "ratings": "1I",
                                       "image_paths": ["x.jpg"]}))
        assert out["ok"] is False, name


def test_feedback_roundtrip(fake_ctx, tmp_path, monkeypatch):
    monkeypatch.setattr("homework_coach.storage.default_root", lambda: tmp_path / "data")
    plugin.register(fake_ctx)
    pdir = tmp_path / "packets" / "2026-01-05"
    pdir.mkdir(parents=True)
    (pdir / "packet.json").write_text(json.dumps({"children": {"nova": {"items": [
        {"id": "1", "skill": "division"}, {"id": "2", "skill": "division"}]}}}), encoding="utf-8")
    h = fake_ctx.tools["homework_coach_record_feedback"]["handler"]
    out = json.loads(h({"child_id": "nova", "packet_date": "2026-01-05", "ratings": "1I 2I"}))
    assert out["ok"] and out["changes"] == {"division": "up"}, out
    status = json.loads(fake_ctx.tools["homework_coach_status"]["handler"]({"child_id": "nova"}))
    assert status["children"][0]["skills"]["division"]["dims"]["scaffold"] == 2


def test_slash_command_usage(fake_ctx):
    plugin.register(fake_ctx)
    assert "Usage" in fake_ctx.commands["homework"]("bogus")


def test_store_scores_attempted_only(tmp_path):
    store = Store(root=tmp_path)
    obs = Observation(date="2026-01-05", child_id="nova", source="p1.jpg", items=[
        ObservedItem("3x4", "12", "correct", "mult", "equation"),
        ObservedItem("5x2", None, "unattempted", "mult", "equation"),
        ObservedItem("6x2", None, "not_assigned", "mult", "equation"),
    ])
    store.add_observation(obs)
    back = store.observations("nova")[0]
    assert len(back.scored_items()) == 1


def test_store_rejects_traversal(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        Store(root=tmp_path).child_dir("../x")
