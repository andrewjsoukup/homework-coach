"""Read/act service behind the Desktop panel (SPEC §8, card t_c3e9fbd8).

Pure functions over :class:`~homework_coach.tools.Runtime` so the REST router in
``dashboard/plugin_api.py`` stays a thin shell and everything here is unit-testable
without FastAPI. Every mutation goes through the same tool handlers the agent uses,
so the panel can never drift from the tool behaviour.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date as _date
from pathlib import Path
from typing import Any

from . import config as cfg
from .models import DIMENSIONS
from .tools import Runtime, make_handlers

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PACKETS = 14
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ITEM_ID_RE = re.compile(r"^[A-Za-z]*\d+$")
# extension -> accepted leading-byte signatures (sniffed so a renamed file is refused)
_IMAGE_MAGIC: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"), ".webp": (b"RIFF",), ".heic": (b"ftyp",), ".heif": (b"ftyp",),
}


class PanelError(ValueError):
    """A user-correctable problem; the router maps it to HTTP 400."""


# -- reads -------------------------------------------------------------------------------------
def overview(rt: Runtime, *, packet_limit: int = 5) -> dict[str, Any]:
    """Everything the panel's first paint needs: children, skill progress, recent packets."""
    try:
        fam = rt.family()
    except FileNotFoundError:
        return {"configured": False, "family_config": str(_family_path(rt)), "children": [], "packets": []}
    except cfg.ConfigError as e:
        return {"configured": False, "family_config": str(_family_path(rt)), "config_errors": e.errors,
                "children": [], "packets": []}
    return {
        "configured": True,
        "family_id": fam.family_id,
        "timezone": fam.timezone,
        "today": rt.today(fam),
        "children": [_child_view(rt, c) for c in fam.children],
        "packets": packets(rt, limit=packet_limit),
    }


def _family_path(rt: Runtime) -> Path:
    return Path(rt._get("family_config", "") or rt.store.family_config_path())


def _child_view(rt: Runtime, child: cfg.Child) -> dict[str, Any]:
    store = rt.store
    obs = store.observations(child.id)
    fb = store.feedback(child.id)
    skills = store.load_skills(child.id)
    latest = obs[-1] if obs else None
    return {
        "id": child.id,
        "name": child.name,
        "grade": child.grade,
        "curriculum": child.curriculum,
        "minutes_per_day": child.minutes_per_day,
        "item_budget": child.item_budget,
        "schedule": {"days": list(child.schedule.days), "time": child.schedule.time},
        "observations": len(obs),
        "last_observation": latest.date if latest else None,
        "anchor": ({"date": latest.date, "lesson": latest.lesson, "skills": latest.skills,
                    "formats": latest.formats} if latest else None),
        "skills": [_skill_view(name, st, fb) for name, st in sorted(skills.items())],
        "feedback_count": len(fb),
        "last_feedback": ({"date": fb[-1].date, "packet_date": fb[-1].packet_date,
                           "tally": _tally(fb[-1].item_ratings.values())} if fb else None),
    }


def _skill_view(name: str, st: Any, feedback: list[Any]) -> dict[str, Any]:
    recent: list[str] = []
    for f in feedback[-2:]:
        recent += [r for item, r in f.item_ratings.items() if f.item_skills.get(item) == name]
    last = st.history[-1] if st.history else None
    return {
        "skill": name,
        "level": st.level,
        "dims": {d: st.dims.get(d, 1) for d in DIMENSIONS},
        "recent": _tally(recent),
        "last_change": last,
    }


def _tally(ratings: Any) -> dict[str, int]:
    out = {"I": 0, "S": 0, "N": 0}
    for r in ratings:
        if r in out:
            out[r] += 1
    return out


def packets(rt: Runtime, *, limit: int = 5) -> list[dict[str, Any]]:
    """Newest-first packet summaries with PDF paths and per-child items for the feedback form."""
    limit = max(1, min(int(limit), MAX_PACKETS))
    return [_packet_view(rt, d) for d in reversed(rt.store.recent_packets(limit))]


def _packet_view(rt: Runtime, d: Path) -> dict[str, Any]:
    try:
        data = json.loads((d / "packet.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    files = []
    for pdf in sorted(d.glob("*.pdf")):
        if pdf.name.startswith("parent_key"):  # parent_key.pdf, or parent_key-<child>.pdf for a later part
            files.append({"kind": "parent_key", "child_id": None, "name": pdf.name, "path": str(pdf)})
        elif pdf.name.endswith("_practice.pdf"):
            files.append({"kind": "practice", "child_id": pdf.name[: -len("_practice.pdf")],
                          "name": pdf.name, "path": str(pdf)})
    children = {}
    raw_children = data.get("children") if isinstance(data.get("children"), dict) else {}
    for cid, cdata in raw_children.items():
        items = cdata.get("items", []) if isinstance(cdata, dict) else []
        children[cid] = {
            "focus": cdata.get("focus", "") if isinstance(cdata, dict) else "",
            "items": [{"id": str(i.get("id")), "skill": i.get("skill", ""), "format": i.get("format", ""),
                       "role": i.get("role", "target"), "optional": bool(i.get("optional", False)),
                       "prompt": _clip(i.get("prompt", ""), 140)}
                      for i in items if isinstance(i, dict) and i.get("id") is not None],
            "rated": _rated(rt, cid, d.name),
        }
    return {"date": d.name, "dir": str(d), "verified": _verified(data), "files": files, "children": children}


def _verified(data: dict[str, Any]) -> bool | None:
    v = data.get("verification", data.get("verified"))
    if isinstance(v, dict):
        v = v.get("ok", v.get("passed"))
    return v if isinstance(v, bool) else None


def _rated(rt: Runtime, child_id: str, packet_date: str) -> bool:
    try:
        return any(f.packet_date == packet_date for f in rt.store.feedback(child_id))
    except ValueError:
        return False


def _clip(text: Any, n: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def resolve_packet_file(rt: Runtime, packet_date: str, name: str) -> Path:
    """Absolute path of one packet PDF, refusing anything outside the packets root."""
    if not _DATE_RE.match(packet_date or "") or not name or Path(name).name != name or not name.endswith(".pdf"):
        raise PanelError("bad packet file reference")
    root = rt.store.packets_root.resolve()
    p = (rt.store.packets_root / packet_date / name).resolve()
    if root not in p.parents or not p.is_file():
        raise PanelError("packet file not found")
    return p


# -- actions -----------------------------------------------------------------------------------
def save_upload(rt: Runtime, child_id: str, filename: str, data: bytes) -> Path:
    """Validate and stage an uploaded homework photo under ``<data>/uploads/``."""
    rt.family().child(child_id)  # KeyError/ConfigError for unknown child or bad config
    ext = Path(filename or "").suffix.lower()
    if ext not in _IMAGE_MAGIC:
        raise PanelError(f"unsupported file type {ext or '(none)'}; use JPG, PNG, WEBP, GIF or HEIC")
    if not data:
        raise PanelError("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise PanelError(f"photo is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    head = data[:16]
    sigs = _IMAGE_MAGIC[ext]
    ok = head[4:8] == b"ftyp" if ext in (".heic", ".heif") else any(head.startswith(s) for s in sigs)
    if ext == ".webp":
        ok = ok and head[8:12] == b"WEBP"
    if not ok:
        raise PanelError("file content does not match its image type")
    digest = hashlib.sha256(data).hexdigest()[:10]
    dest = rt.store.root / "uploads" / child_id / f"{_date.today().isoformat()}_{digest}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def intake_upload(rt: Runtime, child_id: str, filename: str, data: bytes, note: str = "") -> dict[str, Any]:
    """Stage the photo, run the intake tool on it, then drop the staging copy.

    The intake tool itself copies the image into ``children/<id>/sources/`` when the
    ``keep_source_images`` setting is on, so deleting the staging file honours that setting.
    """
    staged = save_upload(rt, child_id, filename, data)
    try:
        args: dict[str, Any] = {"child_id": child_id, "image_paths": [str(staged)]}
        if note.strip():
            args["parent_note"] = note.strip()[:500]
        return json.loads(make_handlers(rt)["homework_coach_intake"](args))
    finally:
        staged.unlink(missing_ok=True)


def record_feedback(rt: Runtime, child_id: str, packet_date: str, ratings: Any, note: str = "") -> dict[str, Any]:
    """Record I/S/N ratings via the same tool handler the agent uses."""
    if not _DATE_RE.match(packet_date or ""):
        raise PanelError("packet_date must be YYYY-MM-DD")
    if isinstance(ratings, dict):
        clean = {str(k): str(v).upper() for k, v in ratings.items() if str(v).upper() in ("I", "S", "N")}
        bad = [k for k in clean if not _ITEM_ID_RE.match(k)]
        if bad:
            raise PanelError(f"bad item ids {bad}")
        if not clean:
            raise PanelError("rate at least one item I, S or N")
        ratings_str = " ".join(f"{k}{v}" for k, v in clean.items())
    elif isinstance(ratings, str) and ratings.strip():
        ratings_str = ratings
    else:
        raise PanelError("ratings required")
    args = {"child_id": child_id, "packet_date": packet_date, "ratings": ratings_str, "note": (note or "")[:1000]}
    return json.loads(make_handlers(rt)["homework_coach_record_feedback"](args))


__all__ = ["PanelError", "overview", "packets", "resolve_packet_file", "save_upload", "intake_upload",
           "record_feedback", "MAX_UPLOAD_BYTES"]
