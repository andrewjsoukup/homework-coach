"""Per-child durable storage under the plugin data root (SPEC §5).

Never writes to the plugin install tree. The root comes from Hermes's
``plugins.plugin_storage.plugin_data_dir`` in production; tests pass a tmp path.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator

from .models import Feedback, Observation, SkillState

PLUGIN_NAME = "homework-coach"


def default_root() -> Path:
    from plugins.plugin_storage import plugin_data_dir  # public Hermes helper

    return plugin_data_dir(PLUGIN_NAME)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Store:
    def __init__(self, root: Path | None = None, output_dir: Path | None = None):
        self.root = Path(root) if root else default_root()
        self.packets_root = Path(output_dir) if output_dir else self.root / "packets"

    # -- paths ---------------------------------------------------------------------------
    def child_dir(self, child_id: str) -> Path:
        if not child_id or "/" in child_id or "\\" in child_id or ".." in child_id:
            raise ValueError(f"bad child id {child_id!r}")
        d = self.root / "children" / child_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def packet_dir(self, date: str, *, create: bool = True) -> Path:
        d = self.packets_root / date
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def family_config_path(self) -> Path:
        return self.root / "family.yaml"

    # -- brief ---------------------------------------------------------------------------
    def brief_path(self, child_id: str) -> Path:
        return self.child_dir(child_id) / "brief.md"

    def read_brief(self, child_id: str) -> str:
        p = self.brief_path(child_id)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def append_brief_section(self, child_id: str, heading: str, body: str) -> None:
        current = self.read_brief(child_id)
        sep = "\n\n" if current and not current.endswith("\n\n") else ""
        _atomic_write(self.brief_path(child_id), f"{current}{sep}## {heading}\n\n{body.strip()}\n")

    # -- jsonl logs ----------------------------------------------------------------------
    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _iter_jsonl(self, path: Path) -> Iterator[dict[str, Any]]:
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def add_observation(self, obs: Observation) -> None:
        self._append_jsonl(self.child_dir(obs.child_id) / "observations.jsonl", obs.to_dict())

    def observations(self, child_id: str) -> list[Observation]:
        return [Observation.from_dict(d) for d in self._iter_jsonl(self.child_dir(child_id) / "observations.jsonl")]

    def add_feedback(self, fb: Feedback) -> None:
        self._append_jsonl(self.child_dir(fb.child_id) / "feedback.jsonl", asdict(fb))

    def feedback(self, child_id: str) -> list[Feedback]:
        return [Feedback(**d) for d in self._iter_jsonl(self.child_dir(child_id) / "feedback.jsonl")]

    # -- skill state ---------------------------------------------------------------------
    def _state_path(self, child_id: str) -> Path:
        return self.child_dir(child_id) / "state.json"

    def _load_state(self, child_id: str) -> dict[str, Any]:
        p = self._state_path(child_id)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"schema_version": 1}

    def _save_state(self, child_id: str, payload: dict[str, Any]) -> None:
        payload.setdefault("schema_version", 1)
        _atomic_write(self._state_path(child_id), json.dumps(payload, indent=2, sort_keys=True))

    def load_skills(self, child_id: str) -> dict[str, SkillState]:
        raw = self._load_state(child_id)
        return {k: SkillState(**v) for k, v in raw.get("skills", {}).items()}

    def save_skills(self, child_id: str, skills: dict[str, SkillState]) -> None:
        payload = self._load_state(child_id)
        payload["skills"] = {k: asdict(v) for k, v in skills.items()}
        self._save_state(child_id, payload)

    def load_anchor(self, child_id: str) -> dict[str, Any] | None:
        """Current classroom anchor: ``{skill, formats, since, lesson, previous_skill}``."""
        return self._load_state(child_id).get("anchor")

    def save_anchor(self, child_id: str, anchor: dict[str, Any]) -> None:
        payload = self._load_state(child_id)
        payload["anchor"] = anchor
        self._save_state(child_id, payload)

    def source_path(self, child_id: str, date: str, original: Path) -> Path:
        d = self.child_dir(child_id) / "sources"
        d.mkdir(parents=True, exist_ok=True)
        stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in original.stem)[:40] or "page"
        ext = original.suffix.lower()
        p = d / f"{date}_{stem}{ext}"
        n = 2
        while p.exists():
            p = d / f"{date}_{stem}-{n}{ext}"
            n += 1
        return p

    # -- packets -------------------------------------------------------------------------
    def recent_packets(self, limit: int = 3, before: str | None = None) -> list[Path]:
        if not self.packets_root.exists():
            return []
        dirs = sorted(d for d in self.packets_root.iterdir()
                      if d.is_dir() and (d / "packet.json").exists() and (before is None or d.name < before))
        return dirs[-limit:]
