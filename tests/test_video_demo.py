"""The video's "next packet adapts" beat must be visible on paper, not just in state."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("reportlab")
pytest.importorskip("pypdfium2")
pytest.importorskip("PIL")


def _load():
    spec = importlib.util.spec_from_file_location("video_demo", ROOT / "demo" / "video_demo.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["video_demo"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_one_not_yet_brings_hints_back(tmp_path):
    res = _load().run(tmp_path / "video")
    assert res["hints_a"] == 0 and res["mult_a"] >= 1          # support faded before the N
    assert res["changes"].get("multiplication") == "down"
    assert res["hints_b"] >= 1                                   # and is back on the next packet
    assert len(res["frames"]) == 3


def test_seed_copies_state_and_family(tmp_path):
    seed = tmp_path / "seed"
    res = _load().run(tmp_path / "video", seed=seed)
    assert (seed / "family.yaml").is_file()
    assert (seed / "children" / "nova" / "state.json").is_file()
    assert res["dims"]["multiplication"]["dims"]["scaffold"] == 3
    with pytest.raises(SystemExit):
        _load().run(tmp_path / "video2", seed=seed)              # never overwrites existing data
