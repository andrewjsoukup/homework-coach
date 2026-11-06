"""Plain dataclasses persisted as JSON/JSONL. Keep fields additive (persisted format)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = 1

ItemStatus = Literal[
    "correct", "incorrect", "slip", "checking_target", "beyond_grade",
    "unattempted", "not_assigned", "needs_recheck",
]
Rating = Literal["I", "S", "N"]
RATING_SCORE = {"I": 1, "S": 0, "N": -1}
DIMENSIONS = ("scaffold", "steps", "representation", "number_range")


@dataclass
class ObservedItem:
    prompt: str
    child_answer: str | None
    status: ItemStatus
    skill: str
    format: str
    expected_answer: str | None = None
    confidence: float = 1.0
    note: str = ""

    @property
    def attempted(self) -> bool:
        return self.status not in ("unattempted", "not_assigned")


@dataclass
class Observation:
    date: str
    child_id: str
    source: str
    items: list[ObservedItem] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    lesson: str = ""
    notes: str = ""
    schema_version: int = SCHEMA_VERSION

    def scored_items(self) -> list[ObservedItem]:
        """Only attempted items count; blanks/crossed-out are never 'wrong'."""
        return [i for i in self.items if i.attempted]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Observation":
        d = dict(d)
        d["items"] = [ObservedItem(**i) for i in d.get("items", [])]
        return cls(**d)


@dataclass
class SkillState:
    skill: str
    level: int = 1
    dims: dict[str, int] = field(default_factory=lambda: {k: 1 for k in DIMENSIONS})
    raised: list[str] = field(default_factory=list)  # stack of dims raised, most recent last
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Feedback:
    date: str
    child_id: str
    packet_date: str
    item_ratings: dict[str, Rating]
    item_skills: dict[str, str] = field(default_factory=dict)
    note: str = ""
    schema_version: int = SCHEMA_VERSION


@dataclass
class PacketItem:
    id: str
    skill: str
    format: str
    prompt: str
    answer: str
    worked_solution: str
    role: Literal["target", "review", "stretch"] = "target"
    optional: bool = False
    visual_inventory: dict[str, Any] = field(default_factory=dict)
    # machine-checkable description used by verify.py to recompute ``answer`` independently
    spec: dict[str, Any] = field(default_factory=dict)
    display: list[str] = field(default_factory=list)  # answer choices / extra child-page lines
    hint: str = ""  # scaffold line shown on the child page (empty at higher scaffold levels)
    work_lines: int = 2  # blank lines reserved for working

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PacketItem":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})
