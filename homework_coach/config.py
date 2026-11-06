"""Family/child config: load, validate (pure Python), derive schedule + item budget.

The JSON Schema in ``schemas/family.schema.json`` is the published contract; this
validator mirrors it so the plugin needs no ``jsonschema`` at runtime. A test keeps
the two in agreement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GRADES = ("PK", "K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12")
SUBJECTS = ("math",)
DEFAULT_SCHEDULE = {"days": ["mon", "tue", "wed", "thu", "fri", "sat"], "time": "09:00"}
EARLY_GRADES = ("PK", "K", "1")

_FAMILY_KEYS = {"family_id", "timezone", "schedule", "children"}
_CHILD_KEYS = {"id", "name", "grade", "curriculum", "subjects", "minutes_per_day", "schedule", "reading_support"}


class ConfigError(ValueError):
    """Raised with every validation problem joined, so a parent can fix them in one pass."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class Schedule:
    days: tuple[str, ...]
    time: str  # HH:MM local to the family timezone

    def to_cron(self) -> str:
        """Standard 5-field cron (minute hour * * dow), dow 0=Sun..6=Sat."""
        hh, mm = self.time.split(":")
        dow_num = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
        nums = sorted(dow_num[d] for d in self.days)
        return f"{int(mm)} {int(hh)} * * {_compress(nums)}"


def _compress(nums: list[int]) -> str:
    if len(nums) == 7:
        return "*"
    parts: list[str] = []
    start = prev = nums[0]
    for n in nums[1:] + [None]:  # type: ignore[list-item]
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if prev - start >= 2 else ",".join(str(x) for x in range(start, prev + 1)))
        if n is not None:
            start = prev = n
    return ",".join(parts)


@dataclass(frozen=True)
class Child:
    id: str
    name: str
    grade: str
    curriculum: str
    minutes_per_day: int
    schedule: Schedule
    subjects: tuple[str, ...] = ("math",)
    reading_support: bool = False

    @property
    def item_budget(self) -> int:
        items = max(3, min(12, round(self.minutes_per_day / 2.5)))
        return min(items, 6) if self.grade in EARLY_GRADES else items


@dataclass(frozen=True)
class FamilyConfig:
    family_id: str
    timezone: str
    schedule: Schedule
    children: tuple[Child, ...] = field(default_factory=tuple)

    def child(self, child_id: str) -> Child:
        for c in self.children:
            if c.id == child_id:
                return c
        raise KeyError(f"unknown child {child_id!r}; known: {', '.join(c.id for c in self.children)}")


def _check_schedule(raw: Any, where: str, errors: list[str]) -> Schedule | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: must be a mapping with days and time")
        return None
    extra = set(raw) - {"days", "time"}
    if extra:
        errors.append(f"{where}: unknown keys {sorted(extra)}")
    days = raw.get("days")
    time = raw.get("time")
    ok = True
    if not isinstance(days, list) or not days:
        errors.append(f"{where}.days: non-empty list required")
        ok = False
    else:
        bad = [d for d in days if d not in DAYS]
        if bad:
            errors.append(f"{where}.days: invalid {bad}; use {list(DAYS)}")
            ok = False
        if len(set(days)) != len(days):
            errors.append(f"{where}.days: duplicates")
            ok = False
    if not isinstance(time, str) or not TIME_RE.match(time):
        errors.append(f"{where}.time: HH:MM 24-hour required")
        ok = False
    return Schedule(tuple(days), time) if ok else None


def validate(raw: Any) -> FamilyConfig:
    errors: list[str] = []
    if not isinstance(raw, dict):
        raise ConfigError(["family config must be a mapping"])
    extra = set(raw) - _FAMILY_KEYS
    if extra:
        errors.append(f"unknown keys {sorted(extra)}")
    fid = raw.get("family_id")
    if not isinstance(fid, str) or not SLUG_RE.match(fid):
        errors.append("family_id: lowercase slug required")
    tz = raw.get("timezone")
    if not isinstance(tz, str) or not tz:
        errors.append("timezone: IANA zone required")
    else:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz)
        except Exception:
            errors.append(f"timezone: unknown zone {tz!r}")
    fam_sched = _check_schedule(raw.get("schedule", DEFAULT_SCHEDULE), "schedule", errors)

    kids_raw = raw.get("children")
    children: list[Child] = []
    if not isinstance(kids_raw, list) or not kids_raw:
        errors.append("children: at least one child required")
        kids_raw = []
    if len(kids_raw) > 8:
        errors.append("children: at most 8")
    seen: set[str] = set()
    for i, c in enumerate(kids_raw):
        w = f"children[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{w}: must be a mapping")
            continue
        extra = set(c) - _CHILD_KEYS
        if extra:
            errors.append(f"{w}: unknown keys {sorted(extra)}")
        cid = c.get("id")
        if not isinstance(cid, str) or not SLUG_RE.match(cid):
            errors.append(f"{w}.id: lowercase slug required")
        elif cid in seen:
            errors.append(f"{w}.id: duplicate {cid!r}")
        else:
            seen.add(cid)
        name = c.get("name")
        if not isinstance(name, str) or not (1 <= len(name) <= 40):
            errors.append(f"{w}.name: 1-40 characters")
        grade = c.get("grade")
        if isinstance(grade, int):
            grade = str(grade)
        if grade not in GRADES:
            errors.append(f"{w}.grade: one of {list(GRADES)}")
        cur = c.get("curriculum")
        if not isinstance(cur, str) or not (1 <= len(cur) <= 120):
            errors.append(f"{w}.curriculum: 1-120 characters")
        mins = c.get("minutes_per_day")
        if not isinstance(mins, int) or isinstance(mins, bool) or not (5 <= mins <= 60):
            errors.append(f"{w}.minutes_per_day: integer 5-60")
        subjects = c.get("subjects", ["math"])
        if (not isinstance(subjects, list) or not subjects or any(s not in SUBJECTS for s in subjects)
                or len(set(subjects)) != len(subjects)):
            errors.append(f"{w}.subjects: subset of {list(SUBJECTS)}")
        rs = c.get("reading_support")
        if rs is not None and not isinstance(rs, bool):
            errors.append(f"{w}.reading_support: boolean")
        sched = _check_schedule(c["schedule"], f"{w}.schedule", errors) if "schedule" in c else fam_sched
        if not errors or all(not e.startswith(w) for e in errors):
            if sched is not None and isinstance(grade, str):
                children.append(Child(
                    id=cid, name=name, grade=grade, curriculum=cur, minutes_per_day=mins,
                    schedule=sched, subjects=tuple(subjects),
                    reading_support=rs if rs is not None else grade in EARLY_GRADES,
                ))
    if errors:
        raise ConfigError(errors)
    return FamilyConfig(family_id=fid, timezone=tz, schedule=fam_sched, children=tuple(children))


def load(path: str | Path) -> FamilyConfig:
    import yaml  # PyYAML ships with Hermes core

    p = Path(path)
    if not p.is_file():
        raise ConfigError([f"family config not found: {p}"])
    with p.open(encoding="utf-8") as f:
        return validate(yaml.safe_load(f))
