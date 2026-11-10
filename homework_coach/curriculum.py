"""Preloaded curriculum plan + teacher materials: what class will cover, and when.

The plugin never browses the web itself. Hermes researches the district / publisher
curriculum (scope and sequence, unit goals, standards) with its own tools, reads any teacher
material the parent shares, then saves the result here. Packet planning uses it as the
steering signal between homework photos:

    recent homework photo (<= ANCHOR_FRESH_DAYS old)  >  curriculum unit active today  >  grade default

so practice follows class even in weeks when no homework came home.
"""
from __future__ import annotations

import json
import shutil
from datetime import date as Date
from pathlib import Path
from typing import Any

from . import catalog

ANCHOR_FRESH_DAYS = 14
MATERIAL_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic", ".txt", ".md", ".docx"}


class CurriculumError(ValueError):
    pass


def _path(store: Any, child_id: str) -> Path:
    return store.child_dir(child_id) / "curriculum.json"


def _check_date(d: str, field: str) -> str:
    try:
        Date.fromisoformat(d)
    except (TypeError, ValueError):
        raise CurriculumError(f"{field} must be YYYY-MM-DD, got {d!r}") from None
    return d


def normalize_unit(u: dict[str, Any], grade: str) -> dict[str, Any]:
    title = str(u.get("title") or "").strip()
    if not title:
        raise CurriculumError("every unit needs a title")
    skill = str(u.get("skill") or "").strip()
    if skill and skill not in catalog.SKILLS:
        raise CurriculumError(f"unit {title!r}: skill must be one of {sorted(catalog.SKILLS)} (got {skill!r})")
    start = _check_date(u.get("start"), f"unit {title!r} start")
    end = _check_date(u.get("end"), f"unit {title!r} end")
    if end < start:
        raise CurriculumError(f"unit {title!r} ends before it starts")
    return {
        "title": title, "skill": skill or None, "start": start, "end": end,
        "goals": [str(g).strip() for g in (u.get("goals") or []) if str(g).strip()],
        "standards": [str(s).strip() for s in (u.get("standards") or []) if str(s).strip()],
        "vocabulary": [str(s).strip() for s in (u.get("vocabulary") or []) if str(s).strip()],
        "notes": str(u.get("notes") or "").strip(),
        "practicable": bool(skill and catalog.formats_for(skill, grade)),
    }


def save_plan(store: Any, child: Any, *, curriculum: str, units: list[dict[str, Any]],
              sources: list[str] | None, school_year: str = "", replace: bool = True) -> dict[str, Any]:
    if not units:
        raise CurriculumError("units is empty; research the scope and sequence first")
    new = [normalize_unit(u, child.grade) for u in units]
    plan = load_plan(store, child.id) if not replace else None
    if plan:
        keep = {(u["title"], u["start"]) for u in new}
        new = [u for u in plan["units"] if (u["title"], u["start"]) not in keep] + new
    new.sort(key=lambda u: (u["start"], u["end"]))
    plan = {"curriculum": curriculum or child.curriculum, "school_year": school_year,
            "sources": [s for s in (sources or []) if s], "units": new}
    _path(store, child.id).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def load_plan(store: Any, child_id: str) -> dict[str, Any] | None:
    p = _path(store, child_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def unit_on(plan: dict[str, Any] | None, day: str) -> dict[str, Any] | None:
    if not plan:
        return None
    hits = [u for u in plan["units"] if u["start"] <= day <= u["end"]]
    return hits[-1] if hits else None


def next_unit(plan: dict[str, Any] | None, day: str) -> dict[str, Any] | None:
    if not plan:
        return None
    return next((u for u in plan["units"] if u["start"] > day), None)


# -- teacher materials -----------------------------------------------------------------------------
def add_material(store: Any, child: Any, *, path: str | None, title: str, date: str, kind: str = "",
                 skill: str = "", goals: list[str] | None = None, summary: str = "") -> dict[str, Any]:
    _check_date(date, "date")
    if skill and skill not in catalog.SKILLS:
        raise CurriculumError(f"skill must be one of {sorted(catalog.SKILLS)} (got {skill!r})")
    saved = None
    if path:
        src = Path(path)
        if not src.is_file():
            raise CurriculumError(f"material not found: {path}")
        if src.suffix.lower() not in MATERIAL_EXTS:
            raise CurriculumError(f"unsupported file type {src.suffix!r}; use {sorted(MATERIAL_EXTS)}")
        d = store.child_dir(child.id) / "materials"
        d.mkdir(parents=True, exist_ok=True)
        dest = d / f"{date}_{src.name}"
        shutil.copy2(src, dest)
        saved = str(dest)
    rec = {"date": date, "title": title.strip() or (Path(path).name if path else "note"),
           "kind": kind.strip(), "skill": skill or None,
           "goals": [g.strip() for g in (goals or []) if g.strip()], "summary": summary.strip(),
           "file": saved}
    with (store.child_dir(child.id) / "materials.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def materials(store: Any, child_id: str) -> list[dict[str, Any]]:
    p = store.child_dir(child_id) / "materials.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# -- steering ----------------------------------------------------------------------------------------
def steer(store: Any, child: Any, day: str) -> dict[str, Any]:
    """Which skill class is on for ``day``, and why. Never raises."""
    anchor = store.load_anchor(child.id) or {}
    since = anchor.get("since")
    fresh = bool(anchor.get("skill") and since and
                 0 <= (Date.fromisoformat(day) - Date.fromisoformat(since)).days <= ANCHOR_FRESH_DAYS)
    plan = load_plan(store, child.id)
    unit = unit_on(plan, day)
    mats = [m for m in materials(store, child.id) if m["date"] <= day][-3:]
    goals = list(unit["goals"]) if unit else []
    for m in mats:
        if m.get("skill") and (not unit or m["skill"] == unit.get("skill")):
            goals += [g for g in m["goals"] if g not in goals]
    if fresh:
        source, skill = "homework photo", anchor["skill"]
    elif unit and unit.get("practicable"):
        source, skill = "curriculum plan", unit["skill"]
    else:
        source, skill = "grade default", None
    return {"skill": skill, "source": source, "unit": unit, "goals": goals[:6],
            "next_unit": next_unit(plan, day), "materials": mats,
            "anchor_since": since, "anchor_fresh": fresh}
