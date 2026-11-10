"""docs/demo/script.md drives demo/demo_beats.py on camera; the shot list must stay reproducible."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("reportlab")


def _run(out: Path, *args: str) -> str:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run([sys.executable, str(ROOT / "demo" / "demo_beats.py"), "--out", str(out), *args],
                         capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_script_beats_reproduce(tmp_path):
    out = tmp_path / "take"
    reply = (ROOT / "demo" / "feedback" / "nova_2026-09-19.txt").read_text("utf-8").strip()
    assert "attempted 7, correct 5, not scored 2" in _run(out, "photo")
    assert "nova_practice.pdf" in _run(out, "packet", "2026-09-14")
    assert "Next practice day: 2026-09-19" in _run(out, "fastforward")
    _run(out, "packet", "2026-09-19")
    assert "multiplication down" in _run(out, "feedback", reply, "2026-09-19")
    assert "Mon Sep 21" in _run(out, "packet", "2026-09-21")
    hints = _run(out, "hints", "2026-09-19", "2026-09-21")
    assert "2026-09-19: multiplication items with a hint line: 0 of 4" in hints
    assert "2026-09-21: multiplication items with a hint line: 4 of 4" in hints
    _run(out, "reset")
    assert not out.exists()
