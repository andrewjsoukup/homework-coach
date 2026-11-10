from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_FAMILY = ROOT / "examples" / "family.example.yaml"


class FakeCtx:
    """Records every public PluginContext call the plugin makes."""

    def __init__(self, settings: dict[str, Any] | None = None):
        self.settings = settings or {}
        self.tools: dict[str, dict[str, Any]] = {}
        self.commands: dict[str, Any] = {}
        self.aux_tasks: dict[str, dict[str, Any]] = {}
        self.skills: dict[str, Path] = {}
        self.blueprints: dict[str, dict[str, Any]] = {}
        self.hooks: list[str] = []
        self.unload: list[Any] = []
        self.llm = None

    def on_unload(self, callback):
        self.unload.append(callback)

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_command(self, name, handler, description="", args_hint="", **kw):
        self.commands[name] = handler

    def register_auxiliary_task(self, key, **kw):
        self.aux_tasks[key] = kw

    def register_skill(self, name, path, **kw):
        self.skills[name] = Path(path)

    def register_automation_blueprint(self, key, **kw):
        self.blueprints[key] = kw

    def register_hook(self, name, cb, **kw):
        self.hooks.append(name)


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path: Path, monkeypatch):
    """Never touch a real Hermes home: plugin data root → tmp."""
    root = tmp_path / "plugin-data"
    monkeypatch.setattr("homework_coach.storage.default_root", lambda: root)
    # register() starts the Daily sheets timer; tests that want a real one start it themselves
    monkeypatch.setattr("homework_coach.daily.start_timer", lambda *a, **k: None)
    return root


@pytest.fixture
def family_file(tmp_path: Path) -> Path:
    p = tmp_path / "family.yaml"
    p.write_text(EXAMPLE_FAMILY.read_text(encoding="utf-8"), encoding="utf-8")
    return p


@pytest.fixture
def fake_ctx(tmp_path: Path, family_file: Path) -> FakeCtx:
    return FakeCtx({"family_config": str(family_file), "output_dir": str(tmp_path / "packets")})
