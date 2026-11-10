"""Packet planning + build orchestration (SPEC §9.2).

plan_child()  → verified PacketItems for one child (deterministic per family/child/date)
build_packet() → plan every child, render PDFs into a temp dir, verify the PDFs,
                 then move the folder into place. A verified dated folder is
                 never overwritten; a re-run returns it unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Any

from . import catalog, verify
from .config import Child, FamilyConfig
from .generators import GENERATORS, Gen
from .models import DIMENSIONS, PacketItem, SkillState
from .storage import Store

MAX_REGEN = 8
DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class ChildPlan:
    child: Child
    items: list[PacketItem]
    target_skill: str
    review_skill: str
    dims: dict[str, dict[str, int]]
    prev_formats: list[str] = field(default_factory=list)
    steer: dict[str, Any] = field(default_factory=dict)
    written_by: str = "builtin"  # "model" when the parent's model chose the formats and numbers
    writer_note: str = ""        # the model's one-line reason, shown to the parent only
    writer_model: str = ""
    writer_fallback: str = ""    # why a model-written sheet fell back to the built-in writer


def _seed(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:8], "big")


def recent_formats(store: Store, child_id: str, before: str, limit: int) -> list[list[str]]:
    """Ordered format lists from the last ``limit`` packets for this child, oldest first."""
    out = []
    for d in store.recent_packets(limit, before=before):
        try:
            data = json.loads((d / "packet.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items = data.get("children", {}).get(child_id, {}).get("items", [])
        if items:
            out.append([i["format"] for i in items])
    return out


def _order_formats(skill: str, grade: str, history: list[list[str]], anchor_formats: list[str],
                   representation: int) -> list[str]:
    """Least-recently-used first; ties → formats seen in class, then visual-first at low representation."""
    fmts = catalog.formats_for(skill, grade)
    last_used: dict[str, int] = {}
    for age, packet in enumerate(reversed(history), start=1):  # age 1 = most recent
        for f in packet:
            last_used.setdefault(f, age)
    never = len(history) + 1

    def key(f: catalog.Format) -> tuple:
        recency = last_used.get(f.id, never + 1)  # bigger = longer ago = better
        return (-recency, f.id not in anchor_formats, (not f.visual) if representation <= 2 else f.visual, f.id)

    return [f.id for f in sorted(fmts, key=key)]


def _dims(states: dict[str, SkillState], skill: str) -> dict[str, int]:
    st = states.get(skill)
    return dict(st.dims) if st else {k: 1 for k in DIMENSIONS}


def _make(fmt: str, rng: random.Random, grade: str, dims: dict[str, int], skill: str,
          seen_prompts: set[str], guide: dict[str, Any] | None = None) -> PacketItem:
    last_errs: list[str] = []
    for attempt in range(MAX_REGEN):
        # a model's preferences get one try; if that item does not verify, the built-in draw takes over
        it = GENERATORS[fmt](Gen(rng, grade, dims, skill, guide if attempt == 0 else None))
        it.id = "tmp"
        last_errs = verify.check_item(it)
        if not last_errs and it.prompt not in seen_prompts:
            seen_prompts.add(it.prompt)
            return it
    raise RuntimeError(f"generator {fmt} could not produce a verified item: {last_errs}")


def plan_child(store: Store, family: FamilyConfig, child: Child, date: str, history_days: int = 3,
               writer: Any = None) -> ChildPlan:
    """Plan one child's sheet. ``writer`` (optional) is the model writer: it may choose each slot's
    format and numbers; the generators still build and check every problem, and any writer failure
    falls back to the built-in choices."""
    rng = random.Random(_seed(family.family_id, child.id, date))
    states = store.load_skills(child.id)
    anchor = store.load_anchor(child.id) or {}
    from . import curriculum

    steer = curriculum.steer(store, child, date)
    if steer["source"] == "curriculum plan":
        # no recent homework photo: follow the preloaded unit; the photo's topic becomes review
        anchor = {"skill": steer["skill"], "formats": anchor.get("formats") if anchor.get("skill") == steer["skill"] else [],
                  "previous_skill": anchor.get("skill") if anchor.get("skill") != steer["skill"] else None}
    target = anchor.get("skill") or catalog.default_skill(child.grade)
    if not catalog.formats_for(target, child.grade):
        target = catalog.default_skill(child.grade)
    review = anchor.get("previous_skill") or catalog.support_skill(target, child.grade)
    if review == target or not catalog.formats_for(review, child.grade):
        review = catalog.support_skill(target, child.grade)
    history = recent_formats(store, child.id, date, history_days)
    anchor_formats = list(anchor.get("formats") or [])

    budget = child.item_budget
    n_review = max(1, round(budget * 0.34))
    n_target = budget - n_review
    t_dims, r_dims = _dims(states, target), _dims(states, review)
    t_order = _order_formats(target, child.grade, history, anchor_formats, t_dims["representation"])
    r_order = _order_formats(review, child.grade, history, [], r_dims["representation"])

    s_dims = dict(t_dims)
    s_dims["number_range"] = min(5, s_dims["number_range"] + 1)
    s_dims["steps"] = min(5, s_dims["steps"] + 1)
    s_dims["scaffold"] = 5
    stretch_fmt = next((f for f in t_order if "word_problem" in f), t_order[-1])

    # One slot per problem: the built-in choice, plus what a model writer may choose instead.
    slots: list[dict[str, Any]] = []
    for i in range(n_target):
        slots.append({"slot": len(slots) + 1, "role": "target", "skill": target, "dims": t_dims,
                      "default": t_order[i % len(t_order)], "allowed": list(t_order)})
    for i in range(n_review):
        slots.append({"slot": len(slots) + 1, "role": "review", "skill": review, "dims": r_dims,
                      "default": r_order[i % len(r_order)], "allowed": list(r_order)})
    slots.append({"slot": len(slots) + 1, "role": "stretch", "skill": target, "dims": s_dims,
                  "default": stretch_fmt, "allowed": [f for f in t_order if "word_problem" in f] or [stretch_fmt]})

    guide: dict[int, dict[str, Any]] = {}
    written_by, writer_note, writer_model, writer_fallback = "builtin", "", "", ""
    if writer is not None:
        try:
            out = writer(child=child, date=date, slots=slots, info={"steer": steer, "history": history})
            guide = dict(out.get("slots") or {})
            if not guide:
                raise ValueError("the model returned no choices")
            written_by, writer_note = "model", str(out.get("note") or "")
            writer_model = str(out.get("model") or "")
        except Exception as e:  # no model, timeout, unusable reply: the built-in sheet is always there
            guide, writer_fallback = {}, f"{type(e).__name__}: {e}"[:200]

    seen: set[str] = set()

    def build(s: dict[str, Any]) -> PacketItem:
        g = guide.get(s["slot"]) or {}
        # The model's choice first; if it cannot give a new, verified problem (some formats print the
        # same instruction every time, so they fit on a sheet once), the built-in choice, then any
        # other format for this skill.
        tries: list[tuple[str, dict[str, Any] | None]] = [(g["format"], g)] if g.get("format") else []
        tries += [(f, None) for f in dict.fromkeys([s["default"], *s["allowed"]])]
        err: RuntimeError | None = None
        for fmt, hint in tries:
            try:
                it = _make(fmt, rng, child.grade, s["dims"], s["skill"], seen, hint)
            except RuntimeError as e:
                err = err or e
                if writer is None:
                    break  # built-in sheets behave exactly as before
                continue
            it.role = s["role"]
            return it
        raise err or RuntimeError("no format could produce a verified item")

    items: list[PacketItem] = [build(s) for s in slots[:-1]]
    # interleave review among target so the page isn't two blocks; deterministic shuffle
    core = items[:]
    rng.shuffle(core)
    # avoid repeating yesterday's exact ordered template
    if history and [c.format for c in core] == history[-1][:len(core)]:
        core = core[1:] + core[:1]
    for n, it in enumerate(core, start=1):
        it.id = str(n)

    stretch = build(slots[-1])
    stretch.id, stretch.role, stretch.optional = "S1", "stretch", True
    from .tips import tip_for

    unit = steer.get("unit") if steer.get("source") != "grade default" else None
    for it in core + [stretch]:
        it.parent_tip = tip_for(it.format, unit)

    return ChildPlan(child=child, items=core + [stretch], target_skill=target, review_skill=review,
                     dims={target: t_dims, review: r_dims}, prev_formats=history[-1] if history else [],
                     steer=steer, written_by=written_by, writer_note=writer_note, writer_model=writer_model,
                     writer_fallback=writer_fallback)


def steering_photo(store: Store, child_id: str, date: str, steer: dict[str, Any]) -> dict[str, Any] | None:
    """The homework photo a photo-steered packet was built from, frozen at build time.

    Stored in packet.json so a photo added later (even the same day) never rewrites history.
    ``index`` is the position in observations.jsonl (append-only); date/source pin it.
    """
    if steer.get("source") != "homework photo":
        return None
    obs = store.observations(child_id)
    idx = next((i for i in range(len(obs) - 1, -1, -1) if obs[i].date <= date), None)
    if idx is None:
        return None
    o = obs[idx]
    return {"index": idx, "date": o.date, "source": o.source, "lesson": o.lesson,
            "anchor_since": steer.get("anchor_since")}


def scheduled_children(family: FamilyConfig, date: str, only: list[str] | None = None,
                       respect_schedule: bool = False) -> list[Child]:
    """Children to build for ``date``. An explicit ``only`` list is honoured as asked unless
    ``respect_schedule`` (scheduled runs): then each child must also be scheduled that weekday."""
    dow = DOW[Date.fromisoformat(date).weekday()]
    if only:
        kids = [family.child(c) for c in only]
        return [c for c in kids if dow in c.schedule.days] if respect_schedule else kids
    return [c for c in family.children if dow in c.schedule.days]


# -- progression notes ---------------------------------------------------------------------------
def progression_md(date: str, plans: list[ChildPlan]) -> str:
    lines = [f"# Packet progression — {date}", ""]
    for p in plans:
        fmts = [i.format for i in p.items if not i.optional]
        new = [f for f in fmts if f not in p.prev_formats]
        lines += [
            f"## {p.child.name} (grade {p.child.grade})",
            "",
            f"- Classroom target: {catalog.SKILLS.get(p.target_skill, p.target_skill)}"
            f" (from {p.steer.get('source', 'grade default')})",
            *([f"- Class unit: {p.steer['unit']['title']}"] if p.steer.get("unit") else []),
            *([f"- Unit goals: {'; '.join(p.steer['goals'])}"] if p.steer.get("goals") else []),
            f"- Supporting review: {catalog.SKILLS.get(p.review_skill, p.review_skill)}",
            *([f"- Problems chosen by: your model{' - ' + p.writer_note if p.writer_note else ''}"]
              if p.written_by == "model" else []),
            *([f"- Model writer unavailable, built-in sheet used: {p.writer_fallback}"] if p.writer_fallback else []),
            f"- Core items: {len(fmts)} (budget {p.child.item_budget}) + 1 optional stretch",
            "- Difficulty dims: " + "; ".join(
                f"{s}: " + ", ".join(f"{k}={v}" for k, v in d.items()) for s, d in p.dims.items()),
            f"- Formats today: {', '.join(fmts)}",
            f"- Previous packet formats: {', '.join(p.prev_formats) or '(none)'}",
            f"- New vs previous packet: {', '.join(new) or '(none — formats reused, numbers/contexts changed)'}",
            "",
        ]
    return "\n".join(lines)


def text_fallback(date: str, plans: list[ChildPlan]) -> str:
    out = [f"PRACTICE PACKET {date} (PDF rendering failed; text version)"]
    for p in plans:
        out.append(f"\n== {p.child.name} ==")
        for it in p.items:
            extra = ("  [" + " | ".join(it.display) + "]") if it.display else ""
            out.append(f"{it.id}. {it.prompt}{extra}")
    out.append("\n---- PARENT KEY (keep separate) ----")
    for p in plans:
        out.append(f"\n== {p.child.name} ==")
        for it in p.items:
            out.append(f"{it.id}. {it.answer} — {it.worked_solution}")
    return "\n".join(out)


# -- build ---------------------------------------------------------------------------------------
LOCK_NAME = ".build.lock"
LOCK_WAIT_SECONDS = 120.0
LOCK_STALE_SECONDS = 600.0


@contextmanager
def _build_lock(root: Path, date: str, wait: float = LOCK_WAIT_SECONDS):
    """Exclusive per-date build lock (O_EXCL lock file). A cron run and a manual run for the
    same date serialize here, so neither can replace the other's verified folder."""
    root.mkdir(parents=True, exist_ok=True)
    lock = root / f".{date}{LOCK_NAME}"
    deadline = time.monotonic() + wait
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
                    lock.unlink(missing_ok=True)  # crashed builder
                    continue
            except OSError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"another packet build for {date} is still running") from None
            time.sleep(0.2)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _load(pdir: Path) -> dict[str, Any] | None:
    try:
        return json.loads((pdir / "packet.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def key_coverage(data: dict[str, Any]) -> dict[str, list[str]]:
    """``{key_file: [child ids it covers]}``; packets written before parts existed have one key."""
    keys = data.get("keys")
    if isinstance(keys, dict) and keys:
        return {k: list(v) for k, v in keys.items()}
    return {data.get("files", {}).get("parent_key", "parent_key.pdf"): list(data.get("children", {}))}


def _is_verified(pdir: Path) -> bool:
    data = _load(pdir)
    if not data or not data.get("verification", {}).get("ok"):
        return False
    return all((pdir / f).exists() for f in data.get("files", {}).values())


def _selection(pdir: Path, data: dict[str, Any], requested: list[str]) -> dict[str, Any]:
    """Files for ``requested`` children (all children when empty) plus the key(s) covering them."""
    kids = [c for c in (requested or list(data["children"])) if c in data["children"]]
    files: dict[str, str] = {}
    for c in kids:
        files[c] = str((pdir / data["files"][c]).resolve())
    for key_file, covers in key_coverage(data).items():
        if set(covers) & set(kids):
            label = "parent_key" if key_file == "parent_key.pdf" else f"parent_key:{'+'.join(covers)}"
            files[label] = str((pdir / key_file).resolve())
    return {"folder": str(pdir.resolve()), "files": files,
            "children": {c: data["children"][c]["focus"] for c in kids},
            "steering": {c: {"source": data["children"][c].get("steered_by"),
                             "unit": data["children"][c].get("class_unit")} for c in kids},
            "written_by": {c: data["children"][c].get("written_by") or "builtin" for c in kids},
            "items": {c: [{"id": i["id"], "skill": i["skill"], "format": i["format"],
                           "optional": bool(i.get("optional"))} for i in data["children"][c]["items"]]
                      for c in kids},
            "verification": data["verification"]}


def build_packet(store: Store, family: FamilyConfig, date: str, only: list[str] | None = None,
                 history_days: int = 3, respect_schedule: bool = False, writer: Any = None) -> dict[str, Any]:
    """Build (or reuse) the packet for ``date``.

    ``writer`` is the optional model writer (see :mod:`writer`); a model-written build that does
    not verify is rebuilt with the built-in writer before anything is reported as failed.

    Idempotent: a verified dated folder is never overwritten and re-runs return it. A run for a
    child who is not yet in that folder (per-child schedules at different times) adds that
    child's PDF and a separate key part next to the existing files; existing PDFs are untouched.
    """
    Date.fromisoformat(date)  # validates format
    kids = scheduled_children(family, date, only, respect_schedule=respect_schedule)
    if not kids:
        return {"date": date, "reused": False, "skipped": True, "files": {},
                "reason": "no children scheduled for this weekday"}
    final = store.packet_dir(date, create=False)
    requested = [c.id for c in kids]
    with _build_lock(store.packets_root, date):
        existing = _load(final) if _is_verified(final) else None
        if existing is not None:
            missing = [c for c in kids if c.id not in existing["children"]]
            if not missing:
                return {"date": date, "reused": True, "added": [], "ok": True,
                        **_selection(final, existing, requested)}
            res = _build_checked(store, family, date, missing, history_days, existing, writer)
            if res.get("ok") is False:
                return res
            data = _load(final) or {}
            return {"date": date, "reused": True, "added": [c.id for c in missing], "ok": True,
                    **_selection(final, data, requested)}
        res = _build_checked(store, family, date, kids, history_days, None, writer)
        if res.get("ok") is False:
            return res
        return {"date": date, "reused": False, "added": requested, "ok": True,
                **_selection(final, _load(final) or {}, requested)}


def _build_checked(store: Store, family: FamilyConfig, date: str, kids: list[Child], history_days: int,
                   existing: dict[str, Any] | None, writer: Any) -> dict[str, Any]:
    res = _build_into(store, family, date, kids, history_days, existing, writer)
    if res.get("ok") is False and writer is not None:
        res = _build_into(store, family, date, kids, history_days, existing, None)
    return res


def _build_into(store: Store, family: FamilyConfig, date: str, kids: list[Child], history_days: int,
                existing: dict[str, Any] | None, writer: Any = None) -> dict[str, Any]:
    final = store.packet_dir(date, create=False)
    plans = [plan_child(store, family, c, date, history_days, writer=writer) for c in kids]
    errors: list[str] = []
    for p in plans:
        errors += verify.check_items(p.items[:-1], budget=p.child.item_budget)
        errors += verify.check_items(p.items[-1:])

    key_name = "parent_key.pdf" if existing is None else f"parent_key-{'-'.join(c.id for c in kids)}.pdf"
    store.packets_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{date}-", dir=store.packets_root))
    files: dict[str, str] = {}
    render_info: dict[str, Any] = {}
    try:
        from . import render

        drawn: dict[str, dict[str, dict]] = {}
        for p in plans:
            name = f"{p.child.id}_practice.pdf"
            drawn[p.child.id] = render.child_pdf(tmp / name, p, date)
            files[p.child.id] = name
            errors += verify.check_child_pdf(tmp / name, p.items)
            errors += render.check_drawn(p.items, drawn[p.child.id])
        render.key_pdf(tmp / key_name, plans, date)
        errors += verify.check_key_pdf(tmp / key_name, {p.child.id: p.items for p in plans})
        for f in [*files.values(), key_name]:
            rc = verify.render_check(tmp / f)
            render_info[f] = rc.get("checked")
            errors += rc["errors"]
    except Exception as e:  # rendering failed → honest text fallback, nothing moved into place
        shutil.rmtree(tmp, ignore_errors=True)
        msg = f"PDF rendering failed: {type(e).__name__}: {e}"
        if isinstance(e, ImportError):
            msg += (" — the plugin's PDF libraries are installed but this Hermes process started before "
                    "they were; restart Hermes (gateway / desktop app) once to load them")
        return {"date": date, "reused": False, "ok": False, "error": msg,
                "fallback_text": text_fallback(date, plans), "files": {}}

    verification = {"ok": not errors, "errors": errors, "raster_checked": render_info,
                    "items_checked": sum(len(p.items) for p in plans)}
    children = {p.child.id: {
        "name": p.child.name, "grade": p.child.grade, "target_skill": p.target_skill,
        "review_skill": p.review_skill, "dims": p.dims,
        "focus": f"{catalog.SKILLS.get(p.target_skill, p.target_skill)} + review of "
                 f"{catalog.SKILLS.get(p.review_skill, p.review_skill).split(' (')[0].lower()}",
        "steered_by": p.steer.get("source"),
        "class_unit": (p.steer.get("unit") or {}).get("title"),
        "unit_goals": p.steer.get("goals", []),
        "steering_photo": steering_photo(store, p.child.id, date, p.steer),
        "written_by": p.written_by, "writer_note": p.writer_note, "writer_model": p.writer_model,
        "writer_fallback": p.writer_fallback,
        "items": [i.to_dict() for i in p.items]} for p in plans}

    if errors:
        # keep the failed attempt for inspection but never present it as deliverable
        (tmp / "packet.json").write_text(json.dumps({"date": date, "verification": verification,
                                                     "children": children}, indent=2), encoding="utf-8")
        failed = store.packets_root / f".failed-{date}"
        shutil.rmtree(failed, ignore_errors=True)
        tmp.rename(failed)
        return {"date": date, "reused": False, "ok": False, "error": "verification failed",
                "verification": verification, "fallback_text": text_fallback(date, plans), "files": {}}

    if existing is None:
        packet = {"schema_version": 1, "date": date, "family_id": family.family_id,
                  "files": {**files, "parent_key": key_name}, "keys": {key_name: [p.child.id for p in plans]},
                  "verification": verification, "children": children}
        (tmp / "packet.json").write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        (tmp / "progression.md").write_text(progression_md(date, plans), encoding="utf-8")
        if final.exists():  # unverified leftovers from an older crashed run (checked under the lock)
            shutil.rmtree(final)
        tmp.rename(final)
        return {"ok": True}

    # additive part: move only new files in (never replacing one), then rewrite packet.json atomically
    clash = [f for f in [*files.values(), key_name] if (final / f).exists()]
    if clash:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"date": date, "reused": True, "ok": False, "files": {},
                "error": f"refusing to overwrite existing packet files: {clash}"}
    for f in [*files.values(), key_name]:
        os.replace(tmp / f, final / f)
    shutil.rmtree(tmp, ignore_errors=True)
    data = dict(existing)
    data["keys"] = {**key_coverage(existing), key_name: [p.child.id for p in plans]}
    data["files"] = {**existing["files"], **files}
    data["children"] = {**existing["children"], **children}
    prev = existing["verification"]
    data["verification"] = {"ok": True, "errors": [],
                            "raster_checked": {**prev.get("raster_checked", {}), **render_info},
                            "items_checked": prev.get("items_checked", 0) + verification["items_checked"]}
    data.setdefault("parts", []).append({"children": [p.child.id for p in plans], "key": key_name})
    _atomic_json(final / "packet.json", data)
    prog = final / "progression.md"
    old = prog.read_text(encoding="utf-8") if prog.exists() else ""
    add = progression_md(date, plans).split("\n", 2)[2]  # drop the duplicate title
    _atomic_text(prog, old.rstrip("\n") + "\n\n" + add)
    return {"ok": True}


def _atomic_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(data, indent=2, ensure_ascii=False))
