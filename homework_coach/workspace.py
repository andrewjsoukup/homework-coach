"""Desktop workspace service: Today, Class plan, Progress, History, Rate desk, family setup.

Pure functions over :class:`~homework_coach.tools.Runtime`, behind the REST router in
``dashboard/plugin_api.py``. Reads only what the plugin already stores; every write goes
through the same storage helpers / tool handlers the agent uses, so the desktop views and
chat can never disagree. No network, no credentials. Model calls (teacher-material reading)
go through the host-owned ``rt.llm`` exactly like homework intake.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from typing import Any

from . import catalog, daily, intake
from . import config as cfg
from . import curriculum as cur
from .delivery import next_packet_date
from .panel import PanelError, _IMAGE_MAGIC, _rated, save_upload
from .storage import _atomic_write
from .tips import tip_for
from .tools import Runtime, make_handlers
DAY_NAMES_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DIM_PLAIN = {
    ("scaffold", "up"): "fewer hints on the sheet",
    ("scaffold", "down"): "hints brought back",
    ("steps", "up"): "one more step per problem",
    ("steps", "down"): "fewer steps per problem",
    ("representation", "up"): "less picture support",
    ("representation", "down"): "more pictures to lean on",
    ("number_range", "up"): "bigger numbers",
    ("number_range", "down"): "smaller numbers",
}
WHY_PLAIN = {"up": "after every rated problem was done on their own", "down": "after a \u201cnot yet\u201d",
             "hold-floor": "already at the easiest setting"}
MATERIAL_UPLOAD_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt", ".md"}
MAX_B64_BYTES = 15 * 1024 * 1024
STALE_PHOTO_DAYS = 7


# -- helpers -----------------------------------------------------------------------------------
def _family(rt: Runtime) -> cfg.FamilyConfig:
    return rt.family()


def _human(d: str | None) -> str:
    if not d:
        return ""
    x = Date.fromisoformat(d)
    return f"{x.strftime('%a')} {x.strftime('%b')} {x.day}"


def _packet_json(rt: Runtime, day: str) -> dict[str, Any] | None:
    p = rt.store.packet_dir(day, create=False) / "packet.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _child_packets(rt: Runtime, child_id: str, limit: int = 60) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for d in rt.store.recent_packets(limit):
        data = _packet_json(rt, d.name)
        if data and child_id in (data.get("children") or {}):
            out.append((d.name, data))
    return out


def _merged_ratings(rt: Runtime, child_id: str) -> dict[str, dict[str, str]]:
    from .difficulty import effective_feedback

    return {f.packet_date: dict(f.item_ratings) for f in effective_feedback(rt.store.feedback(child_id))}


def decode_b64(data_b64: str) -> bytes:
    if not isinstance(data_b64, str) or not data_b64:
        raise PanelError("file data required")
    if data_b64.startswith("data:"):
        data_b64 = data_b64.split(",", 1)[-1]
    if len(data_b64) > MAX_B64_BYTES * 4 // 3 + 8:
        raise PanelError("file is larger than 15 MB")
    try:
        return base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise PanelError("file data is not valid base64") from None


def image_data_url(path: Path, max_side: int = 1400) -> str | None:
    """A downscaled JPEG data URL for showing a stored photo in the desktop (None if unreadable)."""
    if not path.is_file():
        return None
    try:
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        if path.suffix.lower() in (".png", ".jpg", ".jpeg") and path.stat().st_size < 4 * 1024 * 1024:
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
        return None


def _inside(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


# -- Today -------------------------------------------------------------------------------------
def today(rt: Runtime) -> dict[str, Any]:
    """Per-child status and the one next step, derived from stored data (no parallel state)."""
    fam = _family(rt)
    t = rt.today(fam)
    kids = []
    to_rate = 0
    for c in fam.children:
        kids.append(_child_today(rt, c, t))
        to_rate += 1 if kids[-1]["status"] == "needs_rating" or kids[-1].get("rate_date") else 0
    return {"today": t, "today_label": _human(t), "timezone": fam.timezone, "children": kids, "to_rate": to_rate,
            "schedule": {"days": list(fam.schedule.days), "time": fam.schedule.time},
            "daily": daily.status(rt)}


def _child_today(rt: Runtime, c: cfg.Child, t: str) -> dict[str, Any]:
    obs = rt.store.observations(c.id)
    last_photo = obs[-1].date if obs else None
    photo_age = (Date.fromisoformat(t) - Date.fromisoformat(last_photo)).days if last_photo else None
    practice_today = DAY_NAMES_KEYS[Date.fromisoformat(t).weekday()] in c.schedule.days
    nxt = t if practice_today else next_packet_date(c, t)
    packets = _child_packets(rt, c.id, 30)
    rated = _merged_ratings(rt, c.id)
    unrated_past = [d for d, _ in packets if d <= t and d not in rated]
    upcoming = next(((d, p) for d, p in packets if d >= t), None)
    steer = cur.steer(rt.store, c, nxt or t)
    unit = steer.get("unit")
    base = {"id": c.id, "name": c.name, "grade": c.grade, "minutes": c.minutes_per_day,
            "items": c.item_budget, "practice_today": practice_today, "next_practice": nxt,
            "next_practice_label": _human(nxt), "last_photo": last_photo, "photo_age_days": photo_age,
            "steered_by": steer.get("source"), "class_unit": unit.get("title") if unit else None,
            "has_plan": cur.load_plan(rt.store, c.id) is not None}
    # A child who has never had a homework photo (no school homework yet) is not blocked on one when a
    # class plan or earlier sheets already give practice something to follow.
    no_photo_ok = photo_age is None and (bool(packets) or steer.get("source") == "curriculum plan")
    needs_photo = not no_photo_ok and (photo_age is None or photo_age > STALE_PHOTO_DAYS)
    # Today's sheet always leads; an earlier sheet still waiting for ratings is a second, smaller ask.
    earlier = [d for d in unrated_past if d < t]
    also_rate = {"rate_date": earlier[-1], "rate_label": _human(earlier[-1])} if earlier else {}
    todays = next((p for d, p in packets if d == t), None)
    if todays is not None and t not in rated:
        n = len([i for i in todays["children"][c.id].get("items", []) if not i.get("optional")])
        return {**base, **also_rate, "status": "packet_ready", "packet_date": t,
                "headline": f"{_human(t)}\u2019s sheet is ready \u00b7 {n} problems", "action": "open"}
    if todays is None and practice_today and not needs_photo:
        return {**base, **also_rate, "status": "make_packet", "packet_date": t,
                "headline": f"Make {_human(t)}\u2019s practice", "action": "generate"}
    if unrated_past:
        d = unrated_past[-1]
        return {**base, "status": "needs_rating", "packet_date": d,
                "headline": f"Rate {_human(d)}\u2019s sheet", "action": "rate"}
    if upcoming:
        d, data = upcoming
        n = len([i for i in data["children"][c.id].get("items", []) if not i.get("optional")])
        return {**base, "status": "packet_ready", "packet_date": d,
                "headline": f"{_human(d)}\u2019s sheet is ready \u00b7 {n} problems", "action": "open"}
    if needs_photo:
        return {**base, "status": "needs_photo", "packet_date": None,
                "headline": "Add this week\u2019s homework photo" if obs else "Add a homework photo to start",
                "action": "photo"}
    if not nxt:
        return {**base, "status": "off", "packet_date": None, "headline": "No practice days set", "action": "settings"}
    return {**base, "status": "make_packet", "packet_date": nxt,
            "headline": f"Make {_human(nxt)}\u2019s practice", "action": "generate"}



def generate(rt: Runtime, date: str | None, child_ids: list[str] | None) -> dict[str, Any]:
    args: dict[str, Any] = {}
    if date:
        args["date"] = date
    if child_ids:
        args["child_ids"] = list(child_ids)
    return json.loads(make_handlers(rt)["homework_coach_generate_packet"](args))


# -- Class plan --------------------------------------------------------------------------------
def class_plan(rt: Runtime, child_id: str) -> dict[str, Any]:
    fam = _family(rt)
    child = fam.child(child_id)
    t = rt.today(fam)
    plan = cur.load_plan(rt.store, child.id)
    mats = cur.materials(rt.store, child.id)
    packets = _child_packets(rt, child.id, 120)
    units = []
    for i, u in enumerate((plan or {}).get("units", [])):
        phase = "earlier" if u["end"] < t else "now" if u["start"] <= t <= u["end"] else "next"
        pins = [_material_view(m, j) for j, m in enumerate(mats) if u["start"] <= m["date"] <= u["end"]]
        title_key = u["title"].split(" (")[0].strip().lower()
        made = [d for d, p in packets
                if (p["children"][child.id].get("class_unit") or "").split(" (")[0].strip().lower() == title_key]
        shifted = bool(u.get("researched_start") and (u.get("researched_start"), u.get("researched_end"))
                       != (u["start"], u["end"]))
        units.append({
            "index": i, "title": u["title"], "skill": u.get("skill"),
            "skill_label": catalog.SKILLS.get(u.get("skill") or "", "") if u.get("skill") else "",
            "start": u["start"], "end": u["end"], "start_label": _human(u["start"]), "end_label": _human(u["end"]),
            "phase": phase, "goals": u.get("goals", []), "standards": u.get("standards", []),
            "vocabulary": u.get("vocabulary", []), "notes": u.get("notes", ""), "practicable": u.get("practicable", False),
            "source": "teacher" if (shifted or pins or u.get("teacher_update")) else "researched",
            "shifted": shifted, "researched_start": u.get("researched_start"), "researched_end": u.get("researched_end"),
            "shift_note": u.get("shift_note", ""), "materials": pins, "packets": made,
            "undo": bool(u.get("shift_history")),
        })
    unmatched = [_material_view(m, j) for j, m in enumerate(mats)
                 if not any(u["start"] <= m["date"] <= u["end"] for u in (plan or {}).get("units", []))]
    steer = cur.steer(rt.store, child, t)
    return {"child": {"id": child.id, "name": child.name, "grade": child.grade, "curriculum": child.curriculum},
            "today": t, "has_plan": plan is not None,
            "curriculum": (plan or {}).get("curriculum") or child.curriculum, "school_year": (plan or {}).get("school_year", ""),
            "sources": (plan or {}).get("sources", []), "units": units, "unmatched_materials": unmatched,
            "materials_count": len(mats),
            "steering": {"source": steer.get("source"), "unit": (steer.get("unit") or {}).get("title"),
                         "anchor_since": steer.get("anchor_since")}}


def _material_view(m: dict[str, Any], idx: int) -> dict[str, Any]:
    return {"index": idx, "date": m["date"], "date_label": _human(m["date"]), "title": m.get("title", ""),
            "kind": m.get("kind", ""), "skill": m.get("skill"), "summary": m.get("summary", ""),
            "goals": m.get("goals", []), "has_file": bool(m.get("file")), "file": m.get("file")}


def material_file(rt: Runtime, child_id: str, idx: int) -> dict[str, Any]:
    mats = cur.materials(rt.store, child_id)
    if not (0 <= idx < len(mats)) or not mats[idx].get("file"):
        raise PanelError("material has no file")
    p = Path(mats[idx]["file"])
    if not _inside(rt.store.child_dir(child_id), p) or not p.is_file():
        raise PanelError("material file not found")
    return {"path": str(p), "name": p.name, "image": image_data_url(p) if p.suffix.lower() in _IMAGE_MAGIC else None}


# -- teacher material: read, propose, apply, undo ---------------------------------------------
MATERIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "date": {"type": "string"},
        "kind": {"type": "string", "enum": ["newsletter", "unit letter", "study guide", "practice page", "calendar", "other"]},
        "skill": {"type": "string", "enum": [*sorted(catalog.SKILLS), ""]},
        "goals": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "unit_title": {"type": "string"},
        "unit_end": {"type": "string"},
        "assessment": {"type": "string"},
    },
    "required": ["title", "date", "kind", "skill", "goals", "summary", "unit_title", "unit_end", "assessment"],
}
MATERIAL_PROMPT = (
    "You are reading something a child's teacher sent home (newsletter, unit letter, study guide or "
    "calendar). Extract only what it actually says. title: short title as written. date: the week or "
    "issue date as YYYY-MM-DD (use the 'today' given if none is printed). kind: best fit. skill: the "
    "math skill the class is on, from the allowed list, or '' if none fits. goals: up to 5 stated "
    "learning goals, short. summary: one plain sentence for a parent. unit_title: the unit/topic name "
    "as written (e.g. 'Topic 3'), or ''. unit_end: YYYY-MM-DD when the text states when the unit or its "
    "test/quiz happens (the quiz date is the unit end), else ''. assessment: the quiz/test line as "
    "written, or ''. Never guess dates that are not printed."
)


def read_material(rt: Runtime, child_id: str, filename: str, data: bytes, note: str = "") -> dict[str, Any]:
    """Stage a teacher file and read it with the host model; returns a proposal, writes nothing else."""
    fam = _family(rt)
    child = fam.child(child_id)
    ext = Path(filename or "").suffix.lower()
    if ext not in MATERIAL_UPLOAD_EXTS:
        raise PanelError(f"unsupported file type {ext or '(none)'}; use an image, PDF or text file")
    if not data:
        raise PanelError("empty file")
    digest = hashlib.sha256(data).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(filename).stem)[:40] or "material"
    staged = rt.store.root / "uploads" / child.id / f"material_{digest}_{stem}{ext}"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(data)
    t = rt.today(fam)
    inputs: list[dict[str, Any]] = [{"type": "text", "text": f"today: {t}. Child: grade {child.grade}. "
                                     f"Parent note: {note[:300]}"}]
    if ext in _IMAGE_MAGIC:
        mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
        inputs.append({"type": "image", "data": data, "mime_type": mime, "file_name": staged.name})
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader

            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:6])
        except Exception as e:
            raise PanelError(f"could not read the PDF: {type(e).__name__}") from None
        inputs.append({"type": "text", "text": text[:12000]})
    else:
        inputs.append({"type": "text", "text": data.decode("utf-8", "replace")[:12000]})
    from .intake import _call

    try:
        got = _call(rt.llm, MATERIAL_PROMPT, inputs, MATERIAL_SCHEMA, "homework.material")
    except Exception as e:
        raise PanelError(f"could not read this file: {e}") from None
    got = {k: got.get(k) for k in MATERIAL_SCHEMA["properties"]}
    got["date"] = got["date"] if _is_date(got.get("date")) else t
    got["unit_end"] = got["unit_end"] if _is_date(got.get("unit_end")) else ""
    got["skill"] = got["skill"] if got.get("skill") in catalog.SKILLS else ""
    got["goals"] = [str(g).strip() for g in (got.get("goals") or []) if str(g).strip()][:5]
    return {"token": staged.name, "material": got, "proposal": propose_shift(rt, child.id, got),
            "preview": image_data_url(staged) if ext in _IMAGE_MAGIC else None}


def _is_date(s: Any) -> bool:
    try:
        Date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def propose_shift(rt: Runtime, child_id: str, material: dict[str, Any]) -> dict[str, Any] | None:
    """If the material dates its unit differently from the plan, propose moving that unit and those after it."""
    plan = cur.load_plan(rt.store, child_id)
    if not plan or not material.get("unit_end"):
        return None
    units = plan["units"]
    want = _norm_title(material.get("unit_title", "")).split()
    idx = None
    if want:
        for i, u in enumerate(units):
            if _norm_title(u["title"]).split()[:len(want)] == want:  # token match: "topic 1" never hits "topic 10"
                idx = i
                break
    if idx is None and material.get("skill"):
        on = [i for i, u in enumerate(units) if u.get("skill") == material["skill"]]
        idx = min(on, key=lambda i: abs((Date.fromisoformat(units[i]["end"]) - Date.fromisoformat(material["unit_end"])).days)) if on else None
    if idx is None:
        return None
    u = units[idx]
    delta = (Date.fromisoformat(material["unit_end"]) - Date.fromisoformat(u["end"])).days
    if delta == 0:
        return {"unit_index": idx, "unit_title": u["title"], "delta_days": 0, "message": f"{u['title']} already matches the plan."}
    later = len(units) - idx - 1
    new_start, new_end = _shift(u["start"], delta), material["unit_end"]
    direction = "later" if delta > 0 else "earlier"
    weeks = round(abs(delta) / 7, 1)
    span = f"{weeks:g} week{'s' if weeks != 1 else ''}" if abs(delta) >= 7 else f"{abs(delta)} day{'s' if abs(delta) != 1 else ''}"
    return {"unit_index": idx, "unit_title": u["title"], "delta_days": delta,
            "from": {"start": u["start"], "end": u["end"], "label": f"{_human(u['start'])} \u2013 {_human(u['end'])}"},
            "to": {"start": new_start, "end": new_end, "label": f"{_human(new_start)} \u2013 {_human(new_end)}"},
            "later_units": later,
            "message": f"The class is {span} {'behind' if delta > 0 else 'ahead of'} the researched plan. "
                       f"Move {u['title'].split(':')[0]} to end {_human(new_end)}"
                       + (f" and the {later} unit{'s' if later != 1 else ''} after it {span} {direction}." if later else ".")}


def _shift(d: str, days: int) -> str:
    return (Date.fromisoformat(d) + timedelta(days=days)).isoformat()


def apply_material(rt: Runtime, child_id: str, token: str, material: dict[str, Any], apply_shift: bool,
                   expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Save a reviewed teacher material and (optionally) the date change the parent saw.

    ``expected`` is the proposal shown on screen ({unit_index, delta_days}); if the plan has moved
    since, nothing is written and the upload is kept so the parent can review again.
    """
    fam = _family(rt)
    child = fam.child(child_id)
    if not token or Path(token).name != token:
        raise PanelError("bad material reference")
    staged = rt.store.root / "uploads" / child.id / token
    if not staged.is_file():
        raise PanelError("that upload has expired; add the file again")
    prop = propose_shift(rt, child.id, material) if apply_shift else None
    if apply_shift and expected is not None:
        now = {"unit_index": (prop or {}).get("unit_index"), "delta_days": (prop or {}).get("delta_days")}
        want = {"unit_index": expected.get("unit_index"), "delta_days": expected.get("delta_days")}
        if now != want:
            raise PanelError("the class plan changed since you reviewed this; check the proposed change again")
    skill = material.get("skill") or ""
    try:
        rec = cur.add_material(rt.store, child, path=str(staged), title=str(material.get("title") or ""),
                               date=str(material.get("date") or rt.today(fam)), kind=str(material.get("kind") or ""),
                               skill=skill if skill in catalog.SKILLS else "",
                               goals=[str(g) for g in (material.get("goals") or [])][:6],
                               summary=str(material.get("summary") or ""))
    except cur.CurriculumError as e:
        raise PanelError(str(e)) from None
    staged.unlink(missing_ok=True)
    shift = None
    if prop and prop.get("delta_days"):
        shift = _apply_shift(rt, child.id, prop["unit_index"], prop["delta_days"],
                             note=f"Moved to match “{rec['title']}” ({_human(rec['date'])}).")
    return {"ok": True, "material": rec, "shift": shift}


def preview_proposal(rt: Runtime, child_id: str, material: dict[str, Any]) -> dict[str, Any]:
    """Recompute the date-change proposal after the parent edits extracted details. Writes nothing."""
    _family(rt).child(child_id)
    m = dict(material or {})
    m["unit_end"] = m.get("unit_end") if _is_date(m.get("unit_end")) else ""
    return {"proposal": propose_shift(rt, child_id, m)}


PREVIEW_KINDS = ("practice", "key")


def packet_preview(rt: Runtime, day: str, child_id: str, page: int = 0, kind: str = "practice",
                   width: int = 1100) -> dict[str, Any]:
    """One page of the real packet PDF as a PNG data URL (what the parent actually printed)."""
    if kind not in PREVIEW_KINDS:
        raise PanelError("kind must be practice or key")
    d = packet_detail(rt, day, child_id)
    path = Path(d["practice_pdf"] if kind == "practice" else d["key_pdf"] or "")
    pdir = rt.store.packet_dir(day, create=False)
    if not path.is_file() or not _inside(pdir, path):
        raise PanelError("that PDF is not in the packet folder")
    try:
        import pypdfium2 as pdfium
    except ImportError:
        fitz = _pymupdf()
        if fitz is None:
            return {"image": None, "page": 0, "pages": 0, "unavailable": True,
                    "error": "PDF preview needs pypdfium2 or PyMuPDF; save the PDF to view it"}
        return _preview_pymupdf(fitz, path, int(page), width)
    doc = pdfium.PdfDocument(str(path))
    try:
        n = len(doc)
        if not (0 <= int(page) < n):
            raise PanelError(f"page {page + 1} does not exist (this PDF has {n})")
        pg = doc[int(page)]
        scale = width / max(1.0, pg.get_width())
        img = pg.render(scale=scale).to_pil()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "PNG", optimize=True)
        return {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
                "page": int(page), "pages": n}
    finally:
        doc.close()


def _pymupdf() -> Any:
    """PyMuPDF module if installed (``fitz`` or the newer ``pymupdf`` name), else None."""
    for name in ("fitz", "pymupdf"):
        try:
            mod = __import__(name)
        except ImportError:
            continue
        if hasattr(mod, "open") and hasattr(mod, "Matrix"):
            return mod
    return None


def _preview_pymupdf(fitz: Any, path: Path, page: int, width: int) -> dict[str, Any]:
    """Same page of the same validated PDF, drawn with PyMuPDF (hosts without pypdfium2)."""
    if page < 0:
        raise PanelError(f"page {page + 1} does not exist")
    doc = fitz.open(str(path))
    try:
        n = len(doc)
        if page >= n:
            raise PanelError(f"page {page + 1} does not exist (this PDF has {n})")
        pg = doc.load_page(page)
        scale = width / max(1.0, float(pg.rect.width))
        pix = pg.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return {"image": "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode(),
                "page": page, "pages": n}
    finally:
        doc.close()


def _apply_shift(rt: Runtime, child_id: str, idx: int, delta: int, note: str) -> dict[str, Any]:
    p = rt.store.child_dir(child_id) / "curriculum.json"
    plan = json.loads(p.read_text(encoding="utf-8"))
    moved = []
    for j, u in enumerate(plan["units"]):
        if j < idx:
            continue
        u.setdefault("researched_start", u["start"])
        u.setdefault("researched_end", u["end"])
        u.setdefault("shift_history", []).append({"start": u["start"], "end": u["end"], "note": note})
        u["start"], u["end"] = _shift(u["start"], delta), _shift(u["end"], delta)
        u["shift_note"] = note
        if j == idx:
            u["teacher_update"] = True
        moved.append(u["title"])
    _atomic_write(p, json.dumps(plan, indent=2))
    return {"unit_index": idx, "delta_days": delta, "moved": moved}


def undo_shift(rt: Runtime, child_id: str, idx: int) -> dict[str, Any]:
    p = rt.store.child_dir(child_id) / "curriculum.json"
    if not p.exists():
        raise PanelError("no curriculum saved")
    plan = json.loads(p.read_text(encoding="utf-8"))
    units = plan["units"]
    if not (0 <= idx < len(units)) or not units[idx].get("shift_history"):
        raise PanelError("nothing to undo for that unit")
    note = units[idx]["shift_history"][-1].get("note")
    restored = []
    for u in units[idx:]:
        hist = u.get("shift_history") or []
        if hist and hist[-1].get("note") == note:
            last = hist.pop()
            u["start"], u["end"] = last["start"], last["end"]
            u["shift_note"] = hist[-1]["note"] if hist else ""
            if not hist:
                u.pop("teacher_update", None)
            restored.append(u["title"])
    _atomic_write(p, json.dumps(plan, indent=2))
    return {"ok": True, "restored": restored}


# -- Progress ----------------------------------------------------------------------------------
def progress(rt: Runtime, child_id: str, days: int = 30) -> dict[str, Any]:
    fam = _family(rt)
    child = fam.child(child_id)
    t = rt.today(fam)
    start = (Date.fromisoformat(t) - timedelta(days=max(7, min(int(days), 120)) - 1)).isoformat()
    rated = _merged_ratings(rt, child.id)
    packets = [(d, p) for d, p in _child_packets(rt, child.id, 120) if start <= d <= t or d in rated and d >= start]
    skills_state = rt.store.load_skills(child.id)
    names = sorted(set(skills_state) | {i.get("skill") for _, p in packets for i in p["children"][child.id]["items"]} - {None})
    cols = [{"date": d, "label": _human(d), "rated": d in rated} for d, _ in packets]
    rows = []
    totals = {"I": 0, "S": 0, "N": 0}
    for name in names:
        cells = []
        for d, p in packets:
            items = [i for i in p["children"][child.id]["items"] if i.get("skill") == name]
            marks = [{"id": str(i["id"]), "rating": rated.get(d, {}).get(str(i["id"])), "prompt": i.get("prompt", ""),
                      "format": i.get("format", ""), "optional": bool(i.get("optional"))} for i in items]
            for m in marks:
                if m["rating"] in totals:
                    totals[m["rating"]] += 1
            cells.append({"date": d, "marks": marks})
        st = skills_state.get(name)
        changes = []
        for h in (st.history if st else []):
            if h.get("date", "") < start:
                continue
            changes.append({"date": h.get("date"), "label": _human(h.get("date")), "change": h.get("change"),
                            "dim": h.get("dim"),
                            "plain": DIM_PLAIN.get((h.get("dim"), h.get("change")), h.get("change") or ""),
                            "why": WHY_PLAIN.get(h.get("change"), "")})
        rows.append({"skill": name, "label": catalog.SKILLS.get(name, name),
                     "level": st.level if st else 1,
                     "dims": dict(st.dims) if st else {}, "cells": cells, "changes": changes[::-1]})
    obs = [{"date": o.date, "label": _human(o.date), "lesson": o.lesson,
            "slips": sum(1 for i in o.items if i.status in ("incorrect", "slip")), "items": len(o.scored_items())}
           for o in rt.store.observations(child.id) if o.date >= start]
    scored = sum(totals.values())
    return {"child": {"id": child.id, "name": child.name, "grade": child.grade}, "today": t, "start": start,
            "window_days": days, "columns": cols, "skills": rows, "totals": totals, "rated_problems": scored,
            "independent_share": round(totals["I"] / scored, 2) if scored else None, "homework": obs,
            "enough_data": len([c for c in cols if c["rated"]]) >= 2}


# -- History + homework read-back --------------------------------------------------------------
def history(rt: Runtime, child_id: str) -> dict[str, Any]:
    fam = _family(rt)
    child = fam.child(child_id)
    rated = _merged_ratings(rt, child.id)
    events = []
    for idx, o in enumerate(rt.store.observations(child.id)):
        slips = [i for i in o.items if i.status in ("incorrect", "slip", "needs_recheck")]
        events.append({"type": "homework", "date": o.date, "label": _human(o.date), "index": idx,
                       "title": o.lesson or "Homework photo",
                       "detail": f"{len(o.scored_items())} problems read \u00b7 {len(slips)} to check" if o.items else "Photo saved",
                       "skills": list(o.skills)})
    for midx, m in enumerate(cur.materials(rt.store, child.id)):
        events.append({"type": "teacher", "date": m["date"], "label": _human(m["date"]), "index": midx,
                       "has_file": bool(m.get("file")), "title": m.get("title", ""),
                       "detail": m.get("summary", ""), "skills": [m["skill"]] if m.get("skill") else []})
    for d, p in _child_packets(rt, child.id, 120):
        c = p["children"][child.id]
        r = rated.get(d, {})
        tally = {k: list(r.values()).count(k) for k in "ISN"}
        events.append({"type": "practice", "date": d, "label": _human(d), "title": c.get("focus", "Practice"),
                       "detail": (f"Rated: {tally['I']} on their own \u00b7 {tally['S']} with help \u00b7 {tally['N']} not yet"
                                  if r else "Not rated yet"),
                       "steered_by": c.get("steered_by"), "class_unit": c.get("class_unit"), "rated": bool(r)})
    order = {"teacher": 0, "homework": 1, "practice": 2}
    events.sort(key=lambda e: (e["date"], order[e["type"]]), reverse=True)
    return {"child": {"id": child.id, "name": child.name}, "events": events}


def observation(rt: Runtime, child_id: str, idx: int) -> dict[str, Any]:
    obs = rt.store.observations(child_id)
    if idx < 0:  # -1 = the latest photo (what the Today card links to right after intake)
        idx += len(obs)
    if not (0 <= idx < len(obs)):
        raise PanelError("unknown homework entry")
    o = obs[idx]
    photo = None
    for src in [s.strip() for s in (o.source or "").split(",") if s.strip()]:
        p = Path(src)
        if p.is_file() and _inside(rt.store.child_dir(child_id), p):
            photo = image_data_url(p)
            break
    items = [{"n": n, "prompt": i.prompt, "child_answer": i.child_answer, "expected_answer": i.expected_answer,
              "status": i.status, "skill": i.skill, "format": i.format, "confidence": i.confidence,
              "note": i.note, "corrected": "corrected by parent" in (i.note or "")}
             for n, i in enumerate(o.items)]
    return {"index": idx, "date": o.date, "label": _human(o.date), "lesson": o.lesson, "notes": o.notes,
            "photo": photo, "items": items, "skills": list(o.skills)}


_FIXABLE = {"status", "child_answer", "expected_answer"}
_STATUSES = {"correct", "incorrect", "slip", "checking_target", "beyond_grade", "unattempted", "not_assigned", "needs_recheck"}


def fix_reading(rt: Runtime, child_id: str, idx: int, item_n: int, fields: dict[str, Any]) -> dict[str, Any]:
    """Parent corrects one item Hermes misread; appended to the note as provenance, brief updated."""
    path = rt.store.child_dir(child_id) / "observations.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()] if path.exists() else []
    if idx < 0:
        idx += len(rows)
    if not (0 <= idx < len(rows)) or not (0 <= item_n < len(rows[idx].get("items", []))):
        raise PanelError("unknown homework item")
    it = rows[idx]["items"][item_n]
    changed = []
    for k, v in (fields or {}).items():
        if k not in _FIXABLE:
            continue
        v = None if v in ("", None) else str(v)[:40]
        if k == "status" and v not in _STATUSES:
            raise PanelError(f"status must be one of {sorted(_STATUSES)}")
        if it.get(k) != v:
            changed.append(f"{k} {it.get(k)!r}\u2192{v!r}")
            it[k] = v
    if not changed:
        return {"ok": True, "changed": [], "anchor_updated": False}
    was_credible = intake.has_credible_evidence(rt.store.observations(child_id)[idx].items)
    it["confidence"] = 1.0
    it["note"] = ((it.get("note") or "") + f" [corrected by parent: {', '.join(changed)}]").strip()
    _atomic_write(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))
    rt.store.append_brief_section(child_id, f"Reading corrected \u2014 {rows[idx]['date']}",
                                  f"- Item {item_n + 1} ({it.get('prompt', '')[:60]}): {', '.join(changed)}")
    return {"ok": True, "changed": changed, "anchor_updated": _resteer_after_fix(rt, child_id, idx, was_credible)}


def _resteer_after_fix(rt: Runtime, child_id: str, idx: int, was_credible: bool) -> bool:
    """A parent correction can make an unclear page usable evidence for the classroom anchor.

    Only when the page had no credible item before the fix, has one now, and is the newest
    photo (so an older correction never rewinds the anchor). Difficulty levels come only
    from packet ratings and are never touched here.
    """
    obs = rt.store.observations(child_id)
    o = obs[idx]
    if was_credible or idx != len(obs) - 1 or not intake.has_credible_evidence(o.items):
        return False
    anchor = rt.store.load_anchor(child_id) or {}
    if anchor.get("since") and o.date < anchor["since"]:
        return False
    skill = intake.main_skill_from_items(o.items)
    child = _family(rt).child(child_id)
    return intake.update_anchor(rt.store, child, o, skill, sorted(set(o.formats) & set(catalog.FORMATS)), o.date)


# -- Rate desk ---------------------------------------------------------------------------------
def packet_detail(rt: Runtime, day: str, child_id: str) -> dict[str, Any]:
    data = _packet_json(rt, day)
    if not data or child_id not in (data.get("children") or {}):
        raise PanelError("no packet for that child and date")
    c = data["children"][child_id]
    ratings = _merged_ratings(rt, child_id).get(day, {})
    from .render import visual_description
    from .models import PacketItem

    plan = cur.load_plan(rt.store, child_id)
    key = (c.get("class_unit") or "").split(" (")[0].strip().lower()
    unit = next((u for u in (plan or {}).get("units", []) if u["title"].split(" (")[0].strip().lower() == key), None)         if key else None
    unit = unit or (cur.unit_on(plan, day) if c.get("steered_by") != "grade default" else None)
    items = []
    for raw in c.get("items", []):
        it = PacketItem.from_dict(raw)
        items.append({"id": it.id, "prompt": it.prompt, "display": it.display, "picture": visual_description(it),
                      "visual": it.visual_inventory,
                      "hint": it.hint, "answer": it.answer, "worked": it.worked_solution, "format": it.format,
                      "format_label": catalog.FORMATS[it.format].label if it.format in catalog.FORMATS else it.format,
                      "skill": it.skill, "skill_label": catalog.SKILLS.get(it.skill, it.skill), "role": it.role,
                      "optional": it.optional,
                      "tip": raw.get("parent_tip") or tip_for(it.format, unit),
                      "rating": ratings.get(str(it.id))})
    files = data.get("files", {})
    pdir = rt.store.packet_dir(day, create=False)
    prog = pdir / "progression.md"
    lines = []
    if prog.exists():
        sec, take = prog.read_text(encoding="utf-8").splitlines(), False
        for ln in sec:
            if ln.startswith("## "):
                take = ln[3:].startswith(c.get("name", child_id))
            elif take and ln.startswith("- "):
                lines.append(ln[2:])
    photo_index, photo_date, provenance = _packet_photo(rt, child_id, day, c)
    photo_label = _human(photo_date)
    if provenance == "inferred":
        photo_label += " (best match)"
    elif provenance == "missing":
        photo_label += " (photo no longer on file)"
    fam = _family(rt)
    order = [ch for ch in fam.children if ch.id in data["children"]]
    later = [ch for ch in order if ch.id != child_id and not _rated(rt, ch.id, day)]
    return {"date": day, "label": _human(day), "child": {"id": child_id, "name": c.get("name", child_id), "grade": c.get("grade")},
            "focus": c.get("focus", ""), "steered_by": c.get("steered_by"), "class_unit": c.get("class_unit"),
            "photo_date": photo_date, "photo_label": photo_label, "photo_index": photo_index,
            "photo_provenance": provenance,
            "written_by": c.get("written_by") or "builtin", "writer_note": c.get("writer_note") or "",
            "writer_fallback": c.get("writer_fallback") or "",
            "unit_goals": c.get("unit_goals", []), "verified": (data.get("verification") or {}).get("ok"),
            "items": items, "rated": bool(ratings), "progression": lines,
            "practice_pdf": str(pdir / files[child_id]) if child_id in files else None,
            "key_pdf": str(pdir / next((k for k, v in (data.get("keys") or {}).items() if child_id in v), files.get("parent_key", "parent_key.pdf"))),
            "next_child": ({"id": later[0].id, "name": later[0].name} if later else None)}


def _packet_photo(rt: Runtime, child_id: str, day: str, c: dict[str, Any]) -> tuple[int | None, str | None, str]:
    """(observation index, photo date, provenance) for a packet's steering photo.

    provenance: ``recorded`` (frozen in packet.json at build time and still on file),
    ``missing`` (recorded, but that observation is no longer at that position),
    ``inferred`` (older packet with no record: latest photo dated on/before the packet; a
    photo added later the same day could be picked, so the UI labels it a best match),
    ``none`` (packet was not steered by a photo).
    """
    obs = rt.store.observations(child_id)
    if "steering_photo" in c:
        rec = c.get("steering_photo")
        if not isinstance(rec, dict):
            return None, None, "none"
        idx = rec.get("index")
        if (isinstance(idx, int) and 0 <= idx < len(obs) and obs[idx].date == rec.get("date")
                and obs[idx].source == rec.get("source")):
            return idx, obs[idx].date, "recorded"
        return None, rec.get("date"), "missing"
    if c.get("steered_by") != "homework photo":
        return None, None, "none"
    idx = next((i for i in range(len(obs) - 1, -1, -1) if obs[i].date <= day), None)
    return (idx, obs[idx].date, "inferred") if idx is not None else (None, None, "none")


def rate(rt: Runtime, child_id: str, day: str, ratings: Any, note: str = "") -> dict[str, Any]:
    """Record Rate-desk ratings via the agent's own handler, then explain tomorrow in plain words."""
    from .panel import record_feedback

    res = record_feedback(rt, child_id, day, ratings, note)
    if not res.get("ok", True):
        return res
    skills = rt.store.load_skills(child_id)
    plain = []
    for name, st in skills.items():
        for h in st.history:
            if h.get("date") == day and h.get("change") in ("up", "down"):
                plain.append({"skill": name, "label": catalog.SKILLS.get(name, name).split(" (")[0],
                              "change": h["change"], "plain": DIM_PLAIN.get((h.get("dim"), h["change"]), h["change"])})
    fam = _family(rt)
    data = _packet_json(rt, day) or {}
    later = [ch for ch in fam.children if ch.id != child_id and ch.id in (data.get("children") or {})
             and not _rated(rt, ch.id, day)]
    return {**res, "plain_changes": plain, "applies_label": _human(res.get("applies_to")),
            "next_child": ({"id": later[0].id, "name": later[0].name} if later else None)}


# -- Family setup ------------------------------------------------------------------------------
def _family_file(rt: Runtime) -> Path:
    return rt.family_path()


def _read_raw(rt: Runtime) -> tuple[Path, dict[str, Any]]:
    p = _family_file(rt)
    if not p.is_file():
        raise PanelError(f"family config not found: {p}")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return p, json.loads(text)
    import yaml

    return p, yaml.safe_load(text) or {}


def _write_raw(p: Path, raw: dict[str, Any]) -> None:
    cfg.validate(raw)  # raises ConfigError with every problem
    if p.suffix.lower() == ".json":
        _atomic_write(p, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    else:
        import yaml

        _atomic_write(p, yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))


def _archive_path(rt: Runtime) -> Path:
    return rt.store.root / "archived_children.json"


def family_settings(rt: Runtime) -> dict[str, Any]:
    p, raw = _read_raw(rt)
    archived = json.loads(_archive_path(rt).read_text(encoding="utf-8")) if _archive_path(rt).exists() else []
    return {"path": str(p), "family_id": raw.get("family_id"), "timezone": raw.get("timezone"),
            "schedule": raw.get("schedule") or cfg.DEFAULT_SCHEDULE, "children": raw.get("children", []),
            "archived": archived, "grades": list(cfg.GRADES), "days": list(cfg.DAYS)}


def _slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "child"
    if not cfg.SLUG_RE.match(base):
        base = "child"
    s, n = base, 2
    while s in taken:
        s, n = f"{base}-{n}", n + 1
    return s


def _clean_child(body: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    out = dict(existing or {})
    if "name" in body:
        out["name"] = str(body["name"]).strip()[:40]
    if "grade" in body:
        out["grade"] = str(body["grade"]).strip().upper() if str(body["grade"]).strip().upper() in ("K", "PK") else str(body["grade"]).strip()
    if "curriculum" in body:
        out["curriculum"] = str(body["curriculum"]).strip()[:120] or "School math"
    if "minutes_per_day" in body:
        try:
            out["minutes_per_day"] = int(body["minutes_per_day"])
        except (TypeError, ValueError):
            raise PanelError("minutes per day must be a number") from None
    if "days" in body:
        days = [d for d in cfg.DAYS if d in (body.get("days") or [])]
        if days:
            out["schedule"] = {"days": days, "time": (body.get("time") or (out.get("schedule") or {}).get("time") or "09:00")}
        else:
            out.pop("schedule", None)
    out.setdefault("subjects", ["math"])
    out.setdefault("curriculum", "School math")
    out.setdefault("minutes_per_day", 15)
    return out


def _valid_zone(value: Any) -> str:
    tz = str(value).strip()
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
    except Exception:
        raise PanelError(f"unknown timezone {tz!r}; use an IANA name like Europe/Paris") from None
    return tz


def add_child(rt: Runtime, body: dict[str, Any]) -> dict[str, Any]:
    try:
        p, raw = _read_raw(rt)
    except PanelError:  # first child: start a family file in the default location
        p = _family_file(rt)
        tz = _valid_zone(body.get("timezone")) if body.get("timezone") else "UTC"
        raw = {"family_id": "family", "timezone": tz,
               "schedule": dict(cfg.DEFAULT_SCHEDULE), "children": []}
    kids = list(raw.get("children") or [])
    if not str(body.get("name", "")).strip():
        raise PanelError("name required")
    child = _clean_child(body)
    archived = json.loads(_archive_path(rt).read_text(encoding="utf-8")) if _archive_path(rt).exists() else []
    children_root = rt.store.root / "children"
    taken = {k.get("id") for k in kids} | {k.get("id") for k in archived}
    taken |= {d.name for d in children_root.iterdir()} if children_root.is_dir() else set()
    child = {"id": _slug(child["name"], taken), **child}
    kids.append(child)
    raw["children"] = kids
    _write_raw(p, raw)
    rt.store.child_dir(child["id"])
    return {"ok": True, "child": child}


def update_child(rt: Runtime, child_id: str, body: dict[str, Any]) -> dict[str, Any]:
    p, raw = _read_raw(rt)
    kids = list(raw.get("children") or [])
    for i, k in enumerate(kids):
        if k.get("id") == child_id:
            kids[i] = _clean_child(body, k)
            raw["children"] = kids
            _write_raw(p, raw)
            return {"ok": True, "child": kids[i]}
    raise KeyError(child_id)


def archive_child(rt: Runtime, child_id: str) -> dict[str, Any]:
    p, raw = _read_raw(rt)
    kids = list(raw.get("children") or [])
    keep = [k for k in kids if k.get("id") != child_id]
    if len(keep) == len(kids):
        raise KeyError(child_id)
    if not keep:
        raise PanelError("keep at least one child; add another before archiving this one")
    raw["children"] = keep
    _write_raw(p, raw)
    arch = json.loads(_archive_path(rt).read_text(encoding="utf-8")) if _archive_path(rt).exists() else []
    arch.append(next(k for k in kids if k.get("id") == child_id))
    _atomic_write(_archive_path(rt), json.dumps(arch, indent=2))
    return {"ok": True, "archived": child_id, "note": "Their history is kept; restore any time."}


def restore_child(rt: Runtime, child_id: str) -> dict[str, Any]:
    arch = json.loads(_archive_path(rt).read_text(encoding="utf-8")) if _archive_path(rt).exists() else []
    hit = next((k for k in arch if k.get("id") == child_id), None)
    if not hit:
        raise PanelError("not archived")
    p, raw = _read_raw(rt)
    raw["children"] = [*raw.get("children", []), hit]
    _write_raw(p, raw)
    _atomic_write(_archive_path(rt), json.dumps([k for k in arch if k.get("id") != child_id], indent=2))
    return {"ok": True, "child": hit}


def update_schedule(rt: Runtime, body: dict[str, Any]) -> dict[str, Any]:
    p, raw = _read_raw(rt)
    days = [d for d in cfg.DAYS if d in (body.get("days") or [])]
    if not days:
        raise PanelError("pick at least one practice day")
    time = str(body.get("time") or "09:00")
    if not cfg.TIME_RE.match(time):
        raise PanelError("time must be HH:MM")
    raw["schedule"] = {"days": days, "time": time}
    if body.get("timezone"):
        raw["timezone"] = _valid_zone(body["timezone"])
    _write_raw(p, raw)
    return {"ok": True, "schedule": raw["schedule"], "timezone": raw.get("timezone")}


def daily_settings(rt: Runtime) -> dict[str, Any]:
    """Daily sheets switch, who writes the sheet, and the last automatic run."""
    fam = _family(rt)
    return {**daily.status(rt), "timezone": fam.timezone,
            "times": sorted({c.schedule.time for c in fam.children} or {fam.schedule.time})}


def update_daily(rt: Runtime, body: dict[str, Any]) -> dict[str, Any]:
    change = {k: body[k] for k in ("enabled", "writer") if k in body}
    if not change:
        raise PanelError("nothing to change")
    try:
        daily.save_settings(rt.store, change)
    except ValueError as e:
        raise PanelError(str(e)) from None
    return {"ok": True, **daily_settings(rt)}


def research_prompt(rt: Runtime, child_id: str) -> dict[str, Any]:
    """The chat prompt that asks Hermes to research and save this child's curriculum."""
    child = _family(rt).child(child_id)
    return {"prompt": f"{child.name} is in grade {child.grade} and the school uses {child.curriculum}. "
                      f"Research the grade {child.grade} curriculum and set up {child.name}'s year."}


__all__ = [n for n in dir() if not n.startswith("_") and n not in ("annotations",)]
