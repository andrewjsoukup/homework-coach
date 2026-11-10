"""Regression: settings changed after registration must take effect without a restart."""
from __future__ import annotations

import json
from pathlib import Path

from homework_coach.tools import Runtime, make_handlers


def test_store_follows_output_dir_change(tmp_path, family_file, monkeypatch):
    monkeypatch.setattr("homework_coach.storage.default_root", lambda: tmp_path / "data")
    settings = {"family_config": str(family_file)}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d))
    first = rt.store
    assert first.packets_root == tmp_path / "data" / "packets"

    settings["output_dir"] = str(tmp_path / "custom")
    assert rt.store.packets_root == tmp_path / "custom"
    assert rt.store is rt.store  # cached while the setting is unchanged


def test_feedback_finds_packet_written_after_output_dir_change(tmp_path, family_file, monkeypatch):
    monkeypatch.setattr("homework_coach.storage.default_root", lambda: tmp_path / "data")
    settings = {"family_config": str(family_file)}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d))
    rt.today = lambda _f: "2026-11-07"  # type: ignore[method-assign]
    tools = make_handlers(rt)
    _ = rt.store  # first use caches the default folder (the old bug kept it forever)

    settings["output_dir"] = str(tmp_path / "custom")
    made = json.loads(tools["homework_coach_generate_packet"]({"date": "2026-11-07"}))
    assert made["ok"], made
    assert Path(tmp_path / "custom" / "2026-11-07" / "packet.json").exists()

    child = next(iter(made["children"]))
    out = json.loads(tools["homework_coach_record_feedback"]({"child_id": child, "ratings": "1=I"}))
    assert out["ok"], out
    assert out["packet_date"] == "2026-11-07"
