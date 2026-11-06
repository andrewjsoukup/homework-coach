"""Load the 3-day demo scenario and provide a fake vision backend for it.

Shared by ``demo/run_demo.py`` and ``tests/test_demo_scenario.py``. Pure Python
plus PyYAML (already a Hermes core dependency); no network, no real model.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEMO_DIR = Path(__file__).resolve().parent
HOMEWORK_DIR = DEMO_DIR / "homework"
SCENARIO_FILE = DEMO_DIR / "scenario.yaml"


def load_scenario(path: Path = SCENARIO_FILE) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["family_path"] = (path.parent / data["family"]).resolve()
    for day in data["days"]:
        for intake in day.get("intake") or []:
            intake["image_path"] = (path.parent / intake["image"]).resolve()
            intake["truth_path"] = intake["image_path"].with_suffix(".truth.json")
    return data


def load_truth(image_path: Path) -> dict[str, Any]:
    return json.loads(Path(image_path).with_suffix(".truth.json").read_text(encoding="utf-8"))


def ratings_for_packet(skill_ratings: dict[str, list[str]], packet_items: list[dict[str, Any]] | None
                       ) -> tuple[dict[str, str], dict[str, str]]:
    """Map scenario ratings (keyed by skill) onto packet item ids.

    With real packet items, the k-th rating for a skill goes to the k-th item of
    that skill; surplus ratings are dropped and items the scenario does not rate
    stay unrated. Without packet items, synthetic ids ``<n>`` are allocated in order.
    Returns ``(item_ratings, item_skills)``.
    """
    ratings: dict[str, str] = {}
    skills: dict[str, str] = {}
    if packet_items:
        by_skill: dict[str, list[str]] = {}
        for it in packet_items:
            by_skill.setdefault(it["skill"], []).append(str(it["id"]))
        for skill, rs in skill_ratings.items():
            ids = by_skill.get(skill)
            if not ids:
                continue
            for item_id, r in zip(ids, rs):
                ratings[item_id] = r
                skills[item_id] = skill
        return ratings, skills
    n = 0
    for skill, rs in skill_ratings.items():
        for r in rs:
            n += 1
            ratings[str(n)] = r
            skills[str(n)] = skill
    return ratings, skills


def format_ratings(item_ratings: dict[str, str]) -> str:
    """``{"1": "I", "2": "S"}`` -> ``"1I 2S"`` (the tool's text format)."""
    return " ".join(f"{k}{v}" for k, v in item_ratings.items())


# -----------------------------------------------------------------------------------------
# Fake ctx.llm for the demo: returns the ground-truth observation for a known image.
# -----------------------------------------------------------------------------------------


@dataclass
class FakeResult:
    text: str
    parsed: Any
    provider: str = "demo-fixture"
    model: str = "truth-json"
    agent_id: str = "default"
    content_type: str = "json"
    usage: Any = None
    audit: dict[str, Any] = field(default_factory=dict)


class FixtureVision:
    """Stands in for ``ctx.llm`` in demos/tests.

    ``complete_structured`` finds the first image block in ``input`` (bytes,
    ``file_name`` or ``url``), matches it to a demo homework PNG and returns that
    page's ``.truth.json`` as ``parsed``. Narrow re-asks (a text-only follow-up
    naming an item) get the matching item back. Every call is recorded in
    ``self.calls`` so tests can assert what the plugin sent.
    """

    def __init__(self, homework_dir: Path = HOMEWORK_DIR):
        self.by_hash: dict[str, Path] = {}
        self.by_name: dict[str, Path] = {}
        for png in sorted(Path(homework_dir).glob("*.png")):
            self.by_hash[hashlib.sha256(png.read_bytes()).hexdigest()] = png
            self.by_name[png.name] = png
        self.calls: list[dict[str, Any]] = []
        self._last: Path | None = None

    def _match(self, block: Any) -> Path | None:
        get = block.get if isinstance(block, dict) else (lambda k, d=None: getattr(block, k, d))
        if get("type") != "image":
            return None
        data = get("data")
        if isinstance(data, (bytes, bytearray)):
            hit = self.by_hash.get(hashlib.sha256(data).hexdigest())
            if hit:
                return hit
        for key in ("file_name", "url", "path"):
            val = get(key) or ""
            name = str(val).replace("\\", "/").rsplit("/", 1)[-1]
            if name in self.by_name:
                return self.by_name[name]
        return None

    def complete_structured(self, *, instructions: str, input: list[Any], **kw: Any) -> FakeResult:
        self.calls.append({"instructions": instructions, "input": input, **kw})
        page = next((p for p in (self._match(b) for b in input) if p), None) or self._last
        if page is None:
            raise ValueError("FixtureVision: no known demo homework image in input")
        self._last = page
        truth = load_truth(page)
        return FakeResult(text=json.dumps(truth), parsed=truth)

    def complete(self, messages: list[dict[str, Any]], **kw: Any) -> FakeResult:
        self.calls.append({"messages": messages, **kw})
        return FakeResult(text="", parsed=None, content_type="text")
