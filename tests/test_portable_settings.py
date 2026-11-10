"""Portable settings: ~/env expansion, profile-anchored relative paths, family timezone."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from homework_coach import workspace as ws
from homework_coach.panel import PanelError
from homework_coach.tools import Runtime


def _rt(settings: dict) -> Runtime:
    return Runtime(get_setting=lambda k, d=None: settings.get(k, d))


def test_output_dir_expands_tilde_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HC_OUT", str(tmp_path / "envout"))
    assert _rt({"output_dir": "~/packets"}).store.packets_root == tmp_path / "home" / "packets"
    assert _rt({"output_dir": "$HC_OUT/x"}).store.packets_root == tmp_path / "envout" / "x"


def test_relative_output_dir_anchored_to_plugin_data(tmp_path, isolated_data_root, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rt = _rt({"output_dir": "my-packets"})
    assert rt.store.packets_root == isolated_data_root / "my-packets"


def test_relative_family_config_anchored_for_read_and_first_write(isolated_data_root, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    rt = _rt({"family_config": "fam/family.yaml"})
    ws.add_child(rt, {"name": "Ada", "grade": "3", "timezone": "Europe/Paris"})
    target = isolated_data_root / "fam" / "family.yaml"
    assert target.is_file()
    assert not (tmp_path / "fam").exists()
    assert rt.family().timezone == "Europe/Paris"  # read path agrees with write path
    assert ws.family_settings(rt)["path"] == str(target)


def test_family_config_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    rt = _rt({"family_config": "~/hc/family.yaml"})
    ws.add_child(rt, {"name": "Ada", "grade": "3"})
    assert (tmp_path / "home" / "hc" / "family.yaml").is_file()
    assert rt.family().children[0].name == "Ada"


def test_new_family_defaults_to_utc_not_chicago(isolated_data_root):
    rt = _rt({})
    ws.add_child(rt, {"name": "Ada", "grade": "3"})
    assert ws.family_settings(rt)["timezone"] == "UTC"


def test_new_family_uses_supplied_zone(isolated_data_root):
    rt = _rt({})
    ws.add_child(rt, {"name": "Ada", "grade": "3", "timezone": "Asia/Tokyo"})
    assert ws.family_settings(rt)["timezone"] == "Asia/Tokyo"


def test_new_family_invalid_zone_errors_and_writes_nothing(isolated_data_root):
    rt = _rt({})
    with pytest.raises(Exception):
        ws.add_child(rt, {"name": "Ada", "grade": "3", "timezone": "Mars/Base"})
    assert not (isolated_data_root / "family.yaml").exists()


def test_existing_family_timezone_retained_on_add_child(family_file, tmp_path):
    rt = _rt({"family_config": str(family_file)})
    before = yaml.safe_load(family_file.read_text(encoding="utf-8"))["timezone"]
    ws.add_child(rt, {"name": "Zed", "grade": "2", "timezone": "Asia/Tokyo"})
    assert ws.family_settings(rt)["timezone"] == before


def test_update_schedule_changes_timezone_preserving_rest(family_file):
    rt = _rt({"family_config": str(family_file)})
    before = ws.family_settings(rt)
    out = ws.update_schedule(rt, {"days": ["mon", "wed"], "time": "08:30", "timezone": "Asia/Tokyo"})
    assert out["ok"]
    after = ws.family_settings(rt)
    assert after["timezone"] == "Asia/Tokyo"
    assert after["schedule"] == {"days": ["mon", "wed"], "time": "08:30"}
    assert after["children"] == before["children"]


def test_update_schedule_invalid_timezone_rejected_untouched(family_file):
    rt = _rt({"family_config": str(family_file)})
    before = family_file.read_text(encoding="utf-8")
    with pytest.raises(PanelError):
        ws.update_schedule(rt, {"days": ["mon"], "time": "08:30", "timezone": "Nope/Zone"})
    assert family_file.read_text(encoding="utf-8") == before


def test_update_schedule_without_timezone_keeps_it(family_file):
    rt = _rt({"family_config": str(family_file)})
    tz = ws.family_settings(rt)["timezone"]
    ws.update_schedule(rt, {"days": ["mon"], "time": "08:30"})
    assert ws.family_settings(rt)["timezone"] == tz


def test_cached_store_follows_profile_data_context(tmp_path, monkeypatch):
    from homework_coach import storage
    root = [tmp_path / 'first-profile']
    monkeypatch.setattr(storage, 'default_root', lambda: root[0])
    rt = _rt({})
    assert rt.store.root == root[0]
    root[0] = tmp_path / 'second-profile'
    assert rt.store.root == root[0]


def test_path_setting_preserves_literal_leading_spaces(isolated_data_root):
    assert _rt({'output_dir': ' family packets'}).store.packets_root == isolated_data_root / ' family packets'
