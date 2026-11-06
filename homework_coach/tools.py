"""Tool handlers. Contract: ``handler(args: dict, **kwargs) -> str`` (JSON), never raise.

"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import config as cfg
from . import difficulty
from .models import Feedback, SkillState
from .storage import Store


class Runtime:
    """Resolves settings → config + store. Built from a plugin ctx or directly in tests."""

    def __init__(self, get_setting: Callable[[str, Any], Any], llm: Any = None, store: Store | None = None,
                 cron_run: Callable[[], Any] | None = None):
        self._get = get_setting
        self.llm = llm
        self._store = store
        self._cron_run = cron_run or (lambda: None)

    def cron_run(self) -> Any:
        """The Hermes cron run this call executes inside (``ctx.current_cron_execution``), else None."""
        try:
            return self._cron_run()
        except Exception:
            return None

    @property
    def store(self) -> Store:
        if self._store is None:
            out = self._get("output_dir", "") or None
            self._store = Store(output_dir=Path(out) if out else None)
        return self._store

    def family(self) -> cfg.FamilyConfig:
        path = self._get("family_config", "") or self.store.family_config_path()
        return cfg.load(path)

    def today(self, family: cfg.FamilyConfig) -> str:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(family.timezone)).date().isoformat()


def _ok(**data: Any) -> str:
    return json.dumps({"ok": True, **data}, ensure_ascii=False)


def _err(msg: str, **data: Any) -> str:
    return json.dumps({"ok": False, "error": msg, **data}, ensure_ascii=False)


def _guard(fn: Callable[..., str]) -> Callable[..., str]:
    def wrapped(*a: Any, **kw: Any) -> str:
        try:
            return fn(*a, **kw)
        except cfg.ConfigError as e:
            return _err("family config invalid", details=e.errors)
        except Exception as e:  # handlers must never raise
            return _err(f"{type(e).__name__}: {e}")
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


def make_handlers(rt: Runtime) -> dict[str, Callable[..., str]]:
    @_guard
    def status(args: dict, **_: Any) -> str:
        fam = rt.family()
        only = args.get("child_id")
        kids = []
        for c in fam.children:
            if only and c.id != only:
                continue
            skills = rt.store.load_skills(c.id)
            kids.append({
                "id": c.id, "name": c.name, "grade": c.grade, "curriculum": c.curriculum,
                "minutes_per_day": c.minutes_per_day, "item_budget": c.item_budget,
                "schedule": {"days": list(c.schedule.days), "time": c.schedule.time, "cron": c.schedule.to_cron()},
                "skills": {k: {"level": v.level, "dims": v.dims} for k, v in skills.items()},
                "observations": len(rt.store.observations(c.id)),
            })
        if only and not kids:
            return _err(f"unknown child {only!r}")
        recent = [str(p) for p in rt.store.recent_packets(5)]
        return _ok(family_id=fam.family_id, timezone=fam.timezone, children=kids, recent_packets=recent)

    @_guard
    def record_feedback(args: dict, **_: Any) -> str:
        fam = rt.family()
        if args.get("reply"):
            return _record_reply(rt, fam, args["reply"], args.get("note", ""), args.get("packet_date"))
        child = fam.child(args["child_id"])
        res = _record_one(rt, fam, child, args["ratings"], args.get("packet_date"), args.get("note", ""))
        return _ok(**res) if res.pop("ok") else _err(res.pop("error"), **res)

    @_guard
    def intake(args: dict, **_: Any) -> str:
        from .intake import IntakeError, run_intake

        fam = rt.family()
        child = fam.child(args["child_id"])
        paths = list(args.get("image_paths") or [])
        if not paths:
            return _err("image_paths is required")
        missing = [p for p in paths if not Path(p).is_file()]
        if missing:
            return _err("image not found", paths=missing)
        date = args.get("date") or rt.today(fam)
        _check_date(date)
        try:
            result = run_intake(llm=rt.llm, store=rt.store, child=child, image_paths=paths, date=date,
                                parent_note=args.get("parent_note", ""),
                                keep_sources=bool(rt._get("keep_source_images", True)))
        except IntakeError as e:
            return _err(str(e))
        return _ok(**result)

    @_guard
    def generate_packet(args: dict, **_: Any) -> str:
        from .delivery import failure_message, packet_message
        from .packet import build_packet

        fam = rt.family()
        date = args.get("date") or rt.today(fam)
        _check_date(date)
        raw_ids = args.get("child_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        only = [c.strip() for x in raw_ids for c in str(x).split(",") if c.strip() and c.strip() != "all"] or None
        history = int(rt._get("packet_history_days", 3) or 3)
        in_cron = rt.cron_run() is not None
        # scheduled runs follow the family schedule even when the job names children explicitly
        res = build_packet(rt.store, fam, date, only, history_days=max(1, min(14, history)),
                           respect_schedule=in_cron)
        if res.get("ok") is False:
            msg = failure_message(res, in_cron=in_cron)
            return _err(res.pop("error", "packet generation failed"), **res, message=msg)
        res.pop("ok", None)
        if res.get("skipped"):
            # nothing scheduled today: a cron run stays quiet instead of messaging the family
            return _ok(**res, paths=[], media=[], message="[SILENT]" if in_cron else
                       f"No children are scheduled for {date}; no packet generated.")
        res["paths"] = list(res.get("files", {}).values())
        media = [f"MEDIA:{p}" for p in res["paths"]]
        return _ok(**res, media=media, message=packet_message(res, fam))

    return {
        "homework_coach_intake": intake,
        "homework_coach_generate_packet": generate_packet,
        "homework_coach_record_feedback": record_feedback,
        "homework_coach_status": status,
    }


def _check_date(date: str) -> None:
    from datetime import date as Date

    try:
        Date.fromisoformat(date)
    except (TypeError, ValueError):
        raise ValueError(f"date must be YYYY-MM-DD, got {date!r}") from None


def _packet_item_skills(store: Store, date: str, child_id: str) -> dict[str, str]:
    """Map item id → skill from ``packets/<date>/packet.json`` if present."""
    p = store.packet_dir(date, create=False) / "packet.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    items = data.get("children", {}).get(child_id, {}).get("items", [])
    return {str(i["id"]): i["skill"] for i in items}


def latest_packet_date(store: Store, child_id: str, on_or_before: str) -> str | None:
    """Most recent packet date (<= ``on_or_before``) that contains ``child_id``."""
    for d in reversed(store.recent_packets(60, before=_next_day(on_or_before))):
        if _packet_item_skills(store, d.name, child_id):
            return d.name
    return None


def _next_day(date: str) -> str:
    from datetime import date as Date, timedelta

    return (Date.fromisoformat(date) + timedelta(days=1)).isoformat()


def _record_one(rt: Runtime, fam: cfg.FamilyConfig, child: cfg.Child, ratings_raw: str,
                packet_date: str | None, note: str) -> dict[str, Any]:
    """Validate ratings against the packet, append them, rebuild skill state by replay."""
    from .delivery import next_packet_date

    today = rt.today(fam)
    ratings = difficulty.parse_ratings(ratings_raw)
    if packet_date:
        _check_date(packet_date)
    else:
        packet_date = latest_packet_date(rt.store, child.id, today)
        if not packet_date:
            return {"ok": False, "error": f"no packet found for {child.id}; pass packet_date", "child_id": child.id}
    item_skills = _packet_item_skills(rt.store, packet_date, child.id)
    if not item_skills:
        return {"ok": False, "error": f"no packet for {child.id} on {packet_date}", "child_id": child.id}
    unknown = sorted(set(ratings) - set(item_skills))
    ratings = {k: v for k, v in ratings.items() if k in item_skills}
    if not ratings:
        return {"ok": False, "error": f"none of those item ids are in {child.id}'s {packet_date} packet",
                "unknown_items": unknown, "valid_items": sorted(item_skills, key=_item_sort)}
    rated_skills = {k: item_skills[k] for k in ratings}
    rt.store.add_feedback(Feedback(date=today, child_id=child.id, packet_date=packet_date,
                                   item_ratings=ratings, item_skills=rated_skills, note=note or ""))
    skills, moves = difficulty.replay(rt.store.feedback(child.id))
    rt.store.save_skills(child.id, skills)
    merged = next(f for f in difficulty.effective_feedback(rt.store.feedback(child.id)) if f.packet_date == packet_date)
    unrated = sorted((k for k in item_skills if k not in merged.item_ratings), key=_item_sort)
    nxt = next_packet_date(child, max(today, packet_date))
    return {"ok": True, "child_id": child.id, "packet_date": packet_date, "recorded": ratings,
            "unknown_items": unknown, "unrated_items": unrated, "changes": moves.get(packet_date, {}),
            "levels": {s: dict(st.dims) for s, st in skills.items() if s in set(item_skills.values())},
            "applies_to": nxt}


def _record_reply(rt: Runtime, fam: cfg.FamilyConfig, reply: str, note: str, packet_date: str | None) -> str:
    from .delivery import parse_reply

    try:
        parsed = parse_reply(reply, [c.id for c in fam.children])
    except ValueError as e:
        return _err(str(e))
    results = {cid: _record_one(rt, fam, fam.child(cid), v["ratings"], v["date"] or packet_date, note)
               for cid, v in parsed.items()}
    ok = all(r["ok"] for r in results.values())
    lines = []
    for cid, r in results.items():
        if not r["ok"]:
            lines.append(f"{cid}: not recorded — {r['error']}")
            continue
        ch = ", ".join(f"{s} {d}" for s, d in r["changes"].items()) or "no difficulty change"
        extra = f"; ignored unknown items {r['unknown_items']}" if r["unknown_items"] else ""
        lines.append(f"{cid}: recorded {len(r['recorded'])} rating(s) for {r['packet_date']} → {ch}"
                     f" (next packet {r['applies_to'] or 'not scheduled'}){extra}")
    payload = {"children": results, "message": "\n".join(lines)}
    return _ok(**payload) if ok else _err("some feedback was not recorded", **payload)


def _item_sort(item_id: str) -> tuple:
    digits = "".join(ch for ch in item_id if ch.isdigit())
    return (not item_id.isdigit(), int(digits) if digits else 0, item_id)
