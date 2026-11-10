"""Homework photo intake (SPEC §9.1).

Pipeline: copy photos → one structured vision call through ``ctx.llm`` (the
host's configured provider; registered aux task ``homework_vision``) →
recompute every arithmetic claim locally → up to 3 narrow re-asks for
disagreements → status normalisation (attempted-only scoring) → observation log
→ dated classroom anchor in the brief when the topic changes (only when at least one item
was read credibly; an entirely unclear page is logged but never steers) → parent summary.
"""
from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any

from . import arith, catalog
from .models import Observation, ObservedItem
from .storage import Store

AUX_TASK = "homework_vision"
MAX_RECHECKS = 3
CREDIBLE_CONFIDENCE = 0.6  # same bar as the re-ask / "incorrect" threshold
MAX_IMAGE_BYTES = 12 * 1024 * 1024
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}

STATUSES = ["correct", "incorrect", "slip", "checking_target", "beyond_grade", "unattempted", "not_assigned"]

OBSERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lesson": {"type": "string", "description": "Lesson/page title printed on the sheet, if any."},
        "main_skill": {"type": "string", "enum": list(catalog.SKILLS) + ["other"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "string"},
                    "printed_prompt": {"type": "string", "description": "Exactly what is PRINTED, not handwriting."},
                    "math_expression": {"type": "string", "description":
                                        "Plain arithmetic the item asks for, e.g. '24 / 6' or '3 * ? = 12'; empty if not arithmetic."},
                    "child_work": {"type": "string", "description": "Child's handwritten working (intermediate lines)."},
                    "child_answer": {"type": "string", "description": "Child's final answer; empty if blank."},
                    "marks": {"type": "string", "description":
                              "Non-answer marks: crossed out, 'skip', circled number, teacher tick/X, parent note."},
                    "attempted": {"type": "boolean"},
                    "assigned": {"type": "boolean", "description": "False only if marks/instructions say not assigned."},
                    "skill": {"type": "string", "enum": list(catalog.SKILLS) + ["other"]},
                    "format": {"type": "string", "description": "Format id from the catalog, or a short new label."},
                    "status": {"type": "string", "enum": STATUSES},
                    "intermediate_error": {"type": "boolean",
                                           "description": "A working line is wrong even if the final answer is right."},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "note": {"type": "string"},
                },
                "required": ["printed_prompt", "child_answer", "attempted", "skill", "format", "status", "confidence"],
            },
        },
        "teacher_feedback": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["main_skill", "items"],
}

OBSERVE_PROMPT = f"""You are reading photos of a child's completed school math homework for a parent.

Separate, for every item: (1) the PRINTED prompt, (2) the child's handwritten working,
(3) the child's final answer, (4) other marks — crossed-out items, 'skip'/'not assigned'
notes, teacher ticks or Xs, parent notes. Never treat printed text as the child's answer.

Rules:
- Score ATTEMPTED items only. Blank or crossed-out items are 'unattempted' (or
  'not_assigned' when marked so) — never 'incorrect'.
- Correct final answer but a wrong working line → status 'checking_target' and
  intermediate_error=true.
- A wrong answer where the same rule is applied correctly elsewhere on these pages →
  'slip', not 'incorrect'.
- A true answer that goes beyond grade level (e.g. a fraction where whole numbers
  are expected) → 'beyond_grade'.
- If handwriting is unclear, give your best reading and a low confidence.
- Put plain arithmetic for the item in math_expression using + - * / and '?' for a
  blank (e.g. '6 * ? = 42'); leave empty when the item is not arithmetic.
- Do not diagnose the child or infer mastery from one page.

Map skill and format onto this catalog when possible (use the ids):
{catalog.catalog_text()}
"""

RECHECK_PROMPT = """Look only at item {number} ("{prompt}") on these homework photos.
What final answer did the CHILD write by hand for that item? Ignore printed text.
If it is blank or crossed out, answer with an empty string. Give a confidence 0-1."""

RECHECK_SCHEMA = {
    "type": "object",
    "properties": {"child_answer": {"type": "string"}, "confidence": {"type": "number"}},
    "required": ["child_answer", "confidence"],
}


class IntakeError(RuntimeError):
    pass


def _image_block(path: Path) -> dict[str, Any]:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return {"type": "image", "data": path.read_bytes(), "mime_type": mime, "file_name": path.name}


def _parsed(result: Any) -> dict[str, Any]:
    parsed = getattr(result, "parsed", None)
    if parsed is None:
        import json

        try:
            parsed = json.loads(getattr(result, "text", "") or "")
        except ValueError as e:
            raise IntakeError("vision model did not return JSON") from e
    if not isinstance(parsed, dict):
        raise IntakeError("vision model returned an unexpected shape")
    return parsed


_UNSUPPORTED_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength",
                         "maxLength", "minItems", "maxItems", "pattern", "format")


def strict_schema(schema: Any) -> Any:
    """Portable structured-output schema: every object closed (``additionalProperties: false``)
    and numeric/string range keywords dropped. Anthropic rejects open objects and OpenAI strict
    mode rejects range keywords; ranges are enforced locally after parsing instead."""
    if isinstance(schema, list):
        return [strict_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "properties" and isinstance(v, dict):
            out[k] = {name: strict_schema(sub) for name, sub in v.items()}  # names, not keywords
        elif k in ("items", "anyOf", "oneOf", "allOf"):
            out[k] = strict_schema(v)
        elif k in _UNSUPPORTED_KEYWORDS:
            continue
        else:
            out[k] = v
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def _call(llm: Any, instructions: str, inputs: list[dict], schema: dict, name: str) -> dict[str, Any]:
    if llm is None or not hasattr(llm, "complete_structured"):
        raise IntakeError("this Hermes build does not expose ctx.llm to plugins (needs plugin LLM access)")
    res = llm.complete_structured(instructions=instructions, input=inputs, json_schema=strict_schema(schema),
                                  schema_name=name, purpose="homework-coach intake", task=AUX_TASK,
                                  temperature=0)
    return _parsed(res)


def expected_from_expression(expr: str) -> str | None:
    """Locally compute what an item's arithmetic should give. None when not checkable."""
    if not expr or not expr.strip():
        return None
    try:
        if "?" in expr or "_" in expr:
            return arith.fmt(arith.solve_missing(expr))
        if "=" in expr:
            return None
        return arith.fmt(arith.evaluate(expr))
    except arith.ArithError:
        return None


def _answers_equal(child: str, expected: str) -> bool:
    a, b = arith.parse_number(child), arith.parse_number(expected)
    if a is not None and b is not None:
        return a == b
    return arith.normalize(child).replace(" ", "") == arith.normalize(expected).replace(" ", "")


SKILL_ALIASES = {
    "mult": "multiplication", "multiply": "multiplication", "times": "multiplication",
    "div": "division", "divide": "division", "share": "division",
    "add": "add_sub", "sub": "add_sub", "addition": "add_sub", "subtraction": "add_sub",
    "count": "count", "counting": "count", "compare": "count", "numeral": "count", "number_sense": "count",
    "pv": "place_value", "place": "place_value", "frac": "fractions", "fraction": "fractions",
}
_ITEM_NO_RE = re.compile(r"^\s*(\d{1,2}|[A-Z]\d?)[.)]\s+")
_BARE_EQ_RE = re.compile(r"^[\d\s+\-*/x×÷().]+=\s*(_{2,}|\?)\s*$")


def map_skill(label: Any) -> str:
    """Catalog id for a skill label: exact id, or dotted/free label via its first word."""
    s = str(label or "").strip().lower()
    if s in catalog.SKILLS:
        return s
    head = re.split(r"[.\s:/-]", s, maxsplit=1)[0]
    return SKILL_ALIASES.get(head, catalog.SKILLS.get(head) and head or "other")


def _expression_for(raw: dict[str, Any], prompt: str) -> str:
    expr = str(raw.get("math_expression") or "").strip()
    if expr:
        return expr
    bare = _ITEM_NO_RE.sub("", prompt).strip()
    return bare.replace("=", "= ").rstrip() if _BARE_EQ_RE.match(bare) else ""


def normalise_item(raw: dict[str, Any]) -> tuple[ObservedItem, bool]:
    """Turn one vision item into an ObservedItem; returns (item, needs_recheck).

    Tolerates the persisted-observation shape too (``prompt`` instead of
    ``printed_prompt``, no ``attempted``/``assigned`` flags, dotted skill labels).
    """
    prompt = str(raw.get("printed_prompt") or raw.get("prompt") or "")
    answer = (str(raw.get("child_answer") or "")).strip() or None
    status = raw.get("status") if raw.get("status") in STATUSES else "incorrect"
    attempted = (bool(raw["attempted"]) if "attempted" in raw else status not in ("unattempted", "not_assigned"))
    attempted = attempted and answer is not None
    assigned = raw.get("assigned", status != "not_assigned") is not False
    skill = map_skill(raw.get("skill"))
    fmt = str(raw.get("format") or "other")[:60]
    note = str(raw.get("note") or "")
    expected = expected_from_expression(_expression_for(raw, prompt))
    needs_recheck = False
    overturned = False

    if not assigned:
        status = "not_assigned"
    elif not attempted:
        status = "unattempted"  # blank/crossed out is never wrong
    elif expected is not None and status != "beyond_grade":
        right = _answers_equal(answer or "", expected)
        if right and status in ("incorrect", "slip"):
            status, needs_recheck = "correct", True  # model said wrong, maths says right
            note = (note + " Recomputed: answer is correct.").strip()
        elif not right and status in ("correct", "checking_target"):
            status, needs_recheck = "needs_recheck", True
            note = (note + f" Recomputed expected {expected}; model marked it correct.").strip()
            overturned = True
        elif not right:
            needs_recheck = True  # confirm the reading before telling a parent it is wrong
    if attempted and status == "correct" and raw.get("intermediate_error"):
        status = "checking_target"
    conf = float(raw.get("confidence") or 0)
    if attempted and conf < 0.6 and status in ("incorrect", "slip"):
        needs_recheck = True
    if expected is None and raw.get("expected_answer") not in (None, ""):
        expected_label = str(raw["expected_answer"])[:40]  # model's claim, kept only as a label
    else:
        expected_label = expected
    item = ObservedItem(prompt=prompt[:300], child_answer=answer, status=status, skill=skill, format=fmt,
                        expected_answer=expected_label, confidence=max(0.0, min(1.0, conf)), note=note[:300])
    m = _ITEM_NO_RE.match(prompt)
    item_number = str(raw.get("number") or (m.group(1) if m else ""))
    if item_number:
        item.note = f"#{item_number} {item.note}".strip()
    # local-only flags (not dataclass fields, so never persisted)
    item.__dict__["_verified_expected"] = expected
    item.__dict__["_overturned"] = overturned
    return item, needs_recheck


def _apply_recheck(item: ObservedItem, reread: dict[str, Any]) -> bool:
    """Apply a narrow re-read. Returns False (item untouched) when the reply is not a re-read."""
    if "child_answer" not in reread:
        return False
    ans = (str(reread.get("child_answer") or "")).strip() or None
    conf = float(reread.get("confidence") or 0)
    item.child_answer = ans
    item.confidence = min(item.confidence, conf) if ans else conf
    expected = item.__dict__.get("_verified_expected")
    if ans is None:
        item.status = "unattempted"
    elif expected is not None:
        if _answers_equal(ans, expected):
            item.status = "correct" if item.status != "checking_target" else item.status
        else:
            item.status = "incorrect" if conf >= 0.6 else "needs_recheck"
    item.note = (item.note + " Re-read once.").strip()
    return True


def classify_slips(items: list[ObservedItem]) -> None:
    """Local arithmetic overturned a model "correct" → slip if the same format is right elsewhere.

    Explicit model judgments (incorrect / slip) are never overridden: the model saw the
    working and may have recognised a real misconception (e.g. subtracting instead of sharing).
    """
    right_formats = {i.format for i in items if i.status == "correct"}
    for i in items:
        if i.status == "incorrect" and i.__dict__.get("_overturned") and i.format in right_formats:
            i.status = "slip"


# -- brief ---------------------------------------------------------------------------------------
def brief_about(grade: str, curriculum: str) -> str:
    return (f"Grade {grade} · {curriculum}\n\n"
            "Maintained by Homework Coach. Sections are dated and append-only; the most recent "
            "*Current classroom anchor* drives the next packet.")


def anchor_section(obs: Observation, skill: str, formats: list[str], previous: str | None, grade: str) -> str:
    scored = obs.scored_items()
    fresh = [f.id for f in catalog.formats_for(skill, grade) if f.id not in formats][:5]
    lines = [
        f"- Lesson/page: {obs.lesson or '(not printed)'}",
        f"- Skill: {catalog.SKILLS.get(skill, skill)}",
        f"- Formats seen in class: {', '.join(formats) or '(none recognised)'}",
        f"- Observed work: {sum(1 for i in scored if i.status == 'correct')}/{len(scored)} attempted items correct"
        f" ({len(obs.items) - len(scored)} not attempted or not assigned, not scored)",
        f"- Rotating fresh formats for practice: {', '.join(fresh) or '(catalog formats already covered)'}",
    ]
    if previous and previous != skill:
        lines.append(f"- Prior topic {catalog.SKILLS.get(previous, previous)} is now supporting review.")
    if obs.notes:
        lines.append(f"- Notes: {obs.notes}")
    return "\n".join(lines)


def observation_section(obs: Observation) -> str:
    lines = []
    for i in obs.items:
        mark = {"correct": "ok", "checking_target": "check working", "slip": "likely slip",
                "incorrect": "revisit", "beyond_grade": "beyond grade (not an error)",
                "unattempted": "not attempted (not scored)", "not_assigned": "not assigned (not scored)",
                "needs_recheck": "unclear — confirm with child"}.get(i.status, i.status)
        ans = i.child_answer if i.child_answer is not None else "—"
        lines.append(f"- {i.prompt[:80]} → {ans} [{mark}; {i.format}]")
    return "\n".join(lines) or "- (no items read)"


def parent_summary(obs: Observation) -> dict[str, Any]:
    scored = obs.scored_items()
    by = lambda s: [i for i in obs.items if i.status == s]  # noqa: E731
    return {
        "attempted": len(scored),
        "correct": len(by("correct")),
        "not_scored": len(obs.items) - len(scored),
        "strengths": sorted({i.format for i in by("correct")}),
        "likely_slips": [i.prompt for i in by("slip")],
        "checking_targets": [i.prompt for i in by("checking_target")],
        "to_revisit": [i.prompt for i in by("incorrect")],
        "unclear": [i.prompt for i in by("needs_recheck")],
        "beyond_grade": [i.prompt for i in by("beyond_grade")],
        "caution": "Based on one set of photos; not a measure of mastery or pacing.",
    }


# -- main entry ----------------------------------------------------------------------------------
def run_intake(*, llm: Any, store: Store, child: Any, image_paths: list[str], date: str,
               parent_note: str = "", keep_sources: bool = True) -> dict[str, Any]:
    paths = [Path(p) for p in image_paths]
    for p in paths:
        if not p.is_file():
            raise IntakeError(f"image not found: {p}")
        if p.suffix.lower() not in IMAGE_EXTS:
            raise IntakeError(f"not an image file: {p.name}")
        if p.stat().st_size > MAX_IMAGE_BYTES:
            raise IntakeError(f"image too large (>12 MB): {p.name}")

    stored: list[str] = []
    if keep_sources:
        for p in paths:
            dest = store.source_path(child.id, date, p)
            shutil.copy2(p, dest)
            stored.append(str(dest))

    images = [_image_block(p) for p in paths]
    context = f"Child: grade {child.grade}, curriculum '{child.curriculum}'. Pages: {len(paths)}."
    if parent_note:
        context += f" Parent note: {parent_note[:500]}"
    data = _call(llm, OBSERVE_PROMPT, [{"type": "text", "text": context}, *images],
                 OBSERVATION_SCHEMA, "homework.observation")

    items: list[ObservedItem] = []
    to_recheck: list[ObservedItem] = []
    for raw in (data.get("items") or [])[:60]:
        if not isinstance(raw, dict):
            continue
        it, rc = normalise_item(raw)
        items.append(it)
        if rc:
            to_recheck.append(it)
    rechecked = 0
    for it in to_recheck[:MAX_RECHECKS]:
        number = it.note.split()[0].lstrip("#") if it.note.startswith("#") else "?"
        try:
            reread = _call(llm, RECHECK_PROMPT.format(number=number, prompt=it.prompt[:120]), images,
                           RECHECK_SCHEMA, "homework.recheck")
            if _apply_recheck(it, reread):
                rechecked += 1
        except Exception:
            it.status = "needs_recheck" if it.status in ("incorrect", "slip") else it.status
    for it in to_recheck[MAX_RECHECKS:]:
        if it.status in ("incorrect", "slip"):
            it.status = "needs_recheck"
    classify_slips(items)

    main_skill = map_skill(data.get("main_skill")) if data.get("main_skill") else None
    main_skill = main_skill if main_skill in catalog.SKILLS else None
    if main_skill is None:
        counts: dict[str, int] = {}
        for i in items:
            if i.skill in catalog.SKILLS:
                counts[i.skill] = counts.get(i.skill, 0) + 1
        main_skill = max(counts, key=counts.get) if counts else None
    formats = sorted({i.format for i in items if i.format in catalog.FORMATS})
    notes = " ".join(x for x in (str(data.get("teacher_feedback") or ""), str(data.get("notes") or "")) if x)[:500]
    obs = Observation(date=date, child_id=child.id, source=", ".join(stored or [p.name for p in paths]),
                      items=items, skills=sorted({i.skill for i in items}), formats=formats,
                      lesson=str(data.get("lesson") or "")[:120], notes=notes)
    store.add_observation(obs)

    # brief: header once, anchor when the topic changes, dated observation every time
    if not store.read_brief(child.id):
        store.append_brief_section(child.id, f"Learning brief — {child.name}",
                                   brief_about(child.grade, child.curriculum))
    held = not has_credible_evidence(items)  # empty or entirely unclear pages never steer
    anchor_changed = False if held else update_anchor(store, child, obs, main_skill, formats, date)
    store.append_brief_section(child.id, f"Homework observed — {date}", observation_section(obs))

    out = {
        "child_id": child.id, "date": date, "lesson": obs.lesson, "main_skill": main_skill,
        "formats": formats, "anchor_updated": anchor_changed, "rechecked_items": rechecked,
        "summary": parent_summary(obs), "sources_saved": stored,
        "brief_path": str(store.brief_path(child.id)),
        "next_step": "Brief updated. The next generated packet will use it; no packet was generated by this step.",
    }
    if held:
        out["anchor_held"] = ("No item on these photos could be read with confidence, so the classroom topic "
                              "was left unchanged. Correct a reading or send a clearer photo to update it.")
    return out


def has_credible_evidence(items: list[ObservedItem]) -> bool:
    """True when at least one item was read with confidence (or confirmed by a parent).

    ``needs_recheck`` items and low-confidence readings are not evidence. Status is never
    judged here: a clearly read wrong answer is just as credible as a right one.
    """
    return any(i.status != "needs_recheck" and float(i.confidence or 0) >= CREDIBLE_CONFIDENCE for i in items)


def main_skill_from_items(items: list[ObservedItem]) -> str | None:
    """Most common catalog skill among credible items (used when re-steering after a correction)."""
    counts: dict[str, int] = {}
    for i in items:
        if i.skill in catalog.SKILLS and i.status != "needs_recheck" and i.confidence >= CREDIBLE_CONFIDENCE:
            counts[i.skill] = counts.get(i.skill, 0) + 1
    return max(counts, key=counts.get) if counts else None


def update_anchor(store: Store, child: Any, obs: Observation, main_skill: str | None, formats: list[str],
                  date: str) -> bool:
    """New dated anchor on a topic change; same topic refreshes ``since`` (keeps ``topic_since``).

    Returns True only when a new anchor section was written. Callers gate on credible evidence.
    """
    anchor = store.load_anchor(child.id) or {}
    anchor_changed = False
    if main_skill and catalog.formats_for(main_skill, child.grade) and main_skill != anchor.get("skill"):
        previous = anchor.get("skill")
        store.append_brief_section(child.id, f"Current classroom anchor — {date}",
                                   anchor_section(obs, main_skill, formats, previous, child.grade))
        # since = newest photo of this topic (drives freshness); topic_since = first photo of it
        store.save_anchor(child.id, {"skill": main_skill, "formats": formats, "since": date,
                                     "topic_since": date, "lesson": obs.lesson, "previous_skill": previous})
        anchor_changed = True
    elif main_skill and main_skill == anchor.get("skill"):
        updated = dict(anchor)
        updated.setdefault("topic_since", anchor.get("since") or date)
        if formats:
            updated["formats"] = sorted(set(anchor.get("formats") or []) | set(formats))
        if not anchor.get("since") or date > anchor["since"]:  # a newer photo of the same topic
            updated["since"] = date
            updated["lesson"] = obs.lesson or anchor.get("lesson", "")
        if updated != anchor:
            store.save_anchor(child.id, updated)
    return anchor_changed
