"""Model-written sheets (opt-in: "Who writes the sheet" = your model).

The model never writes an answer or a finished problem. For each slot on the sheet it
chooses a task format from the ones the plugin can draw and check, the numbers to use,
and (for story problems) a first name and an everyday object. The ordinary generators
then build the problem from those choices, compute the answer themselves and the usual
verification runs. A choice the generator cannot use (unknown format, number outside the
child's current range) is replaced by the built-in choice, and any model failure falls
back to the built-in sheet, so a sheet is always produced.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from . import catalog
from .generators import GENERATORS, num_max

AUX_TASK = "homework_writer"
MAX_REPEAT = 2          # a format appears at most twice among the core problems
MAX_NUMBERS = 6
TIMEOUT_SECONDS = 120
WHO_RE = re.compile(r"^[A-Z][a-z]{1,11}$")
THINGS_RE = re.compile(r"^[a-z]{2,13}s$")
RATING_WORDS = {"I": "on their own", "S": "with support", "N": "not yet"}

# The order each generator takes its numbers in. Shown to the model; a test keeps it complete.
NUMBERS: dict[str, str] = {
    "count_objects": "[how many circles]",
    "ten_frame": "[dots filled, 1 to 10]",
    "more_less": "[size of group A, size of group B] (different sizes)",
    "number_after": "[first number of the pattern]",
    "base_ten_blocks": "[the number the blocks show]",
    "expanded_form": "[the number]",
    "compare_symbol": "[left number, right number]",
    "order_numbers": "[four different numbers]",
    "equation": "[whole, one part] (printed as part + other part, or whole - part)",
    "missing_addend": "[whole, known part]",
    "ten_frame_add": "[first frame, second frame] (each 1 to 10)",
    "number_line": "[number of jumps 2 to 4, starting number]",
    "bar_model": "[whole, one part]",
    "true_false": "[whole, one part]",
    "word_problem": "[first amount, second amount, amount given away (higher levels only)]",
    "array_to_equation": "[rows, columns]",
    "equal_groups": "[groups, how many in each group]",
    "missing_factor": "[known factor, missing factor]",
    "select_all_equivalent": "[first factor, second factor]",
    "compare_products": "[a, b, c, d] for a x b compared with c x d",
    "mult_word_problem": "[containers, how many in each, extra found (higher levels only)]",
    "equal_sharing": "[circles, how many in each circle]",
    "fact_family": "[first factor, second factor] (different)",
    "missing_number_div": "[one factor, the other factor]",
    "bar_model_div": "[equal parts, size of each part]",
    "div_true_false": "[divisor, quotient]",
    "div_word_problem": "[friends, how many each friend gets, amount kept (higher levels only)]",
    "name_fraction": "[equal parts, shaded parts]",
    "shade_fraction": "[equal parts, parts to shade]",
    "compare_unit_fractions": "[first denominator, second denominator] (different)",
    "fraction_of_set": "[circles in all, shaded circles]",
}

INSTRUCTIONS = (
    "You are planning one short maths practice sheet for a school child. A separate program builds "
    "each problem from your choices, works out every answer itself and prints the page, so you never "
    "write answers or finished problem text.\n"
    "For every slot in `slots`, return one entry in `items` with: `slot` (the slot number); `format` "
    "(one of the ids listed under that slot's skill in `formats`); `numbers` (whole numbers in the "
    "order shown for that format, each no bigger than the slot's `max_number`; numbers outside the "
    "child's range are replaced automatically); `who` (a first name for story problems, otherwise an "
    "empty string); `things` (one lowercase plural everyday object for story problems such as "
    "stickers, otherwise an empty string); and `why` (a few words for the parent).\n"
    "Aim the target slots at what the homework and the parent's ratings show is still hard: reuse the "
    "exact number facts the child slipped on and close neighbours of them, and prefer formats rated "
    "'with support' or 'not yet'. Keep review slots as confident wins. Vary the sheet: give each slot "
    "a different format where the skill offers enough (a repeated format may be swapped for another) "
    "and avoid repeating the previous sheets' format order. The stretch slot is an optional harder "
    "story problem.\n"
    "`note` is one plain sentence telling the parent what this sheet concentrates on and why. Never "
    "include the child's name or any answer."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "note": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "slot": {"type": "integer"},
                "format": {"type": "string"},
                "numbers": {"type": "array", "items": {"type": "integer"}},
                "who": {"type": "string"},
                "things": {"type": "string"},
                "why": {"type": "string"},
            },
            "required": ["slot", "format", "numbers", "who", "things", "why"],
        }},
    },
    "required": ["note", "items"],
}


class WriterError(RuntimeError):
    pass


def _printable(text: str) -> bool:
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def context(store: Any, child: Any, date: str, info: dict[str, Any]) -> dict[str, Any]:
    """What the model is told about the child: grade, class unit, latest homework reading, recent ratings."""
    from .difficulty import effective_feedback

    obs = [o for o in store.observations(child.id) if o.date <= date]
    homework = None
    if obs:
        o = obs[-1]
        homework = {"date": o.date, "lesson": o.lesson,
                    "problems": [{"problem": i.prompt[:120], "child_wrote": i.child_answer,
                                  "expected": i.expected_answer, "result": i.status} for i in o.items[:14]]}
    rated = []
    for fb in effective_feedback(store.feedback(child.id))[-2:]:
        try:
            data = json.loads((store.packet_dir(fb.packet_date, create=False) / "packet.json")
                              .read_text(encoding="utf-8"))
            items = data["children"][child.id]["items"]
        except (OSError, ValueError, KeyError):
            continue
        rated.append({"sheet": fb.packet_date, "parent_note": (fb.note or "")[:200],
                      "problems": [{"format": i["format"], "problem": str(i["prompt"])[:120],
                                    "parent_rating": RATING_WORDS.get(fb.item_ratings.get(str(i["id"])), "not rated")}
                                   for i in items]})
    steer = info.get("steer") or {}
    unit = steer.get("unit") or {}
    return {"grade": child.grade, "school_program": child.curriculum, "sheet_date": date,
            "class_unit": unit.get("title"), "unit_goals": list(steer.get("goals") or []),
            "practice_follows": steer.get("source"),
            "latest_homework": homework, "recent_parent_ratings": rated,
            "recent_sheet_formats": list(info.get("history") or [])[-2:]}


def request(child: Any, date: str, slots: list[dict[str, Any]], info: dict[str, Any], store: Any) -> dict[str, Any]:
    """The JSON the model reads: the child's context, the formats on offer and the slots to fill."""
    skills = sorted({s["skill"] for s in slots})
    formats = {catalog.SKILLS.get(sk, sk): [
        {"id": f, "what": catalog.FORMATS[f].label, "numbers": NUMBERS.get(f, "[]")}
        for f in dict.fromkeys(f for s in slots if s["skill"] == sk for f in s["allowed"])] for sk in skills}
    return {"child": context(store, child, date, info), "formats": formats,
            "slots": [{"slot": s["slot"], "role": s["role"], "skill": catalog.SKILLS.get(s["skill"], s["skill"]),
                       "max_number": num_max(s["skill"], child.grade, max(1, min(5, int(s["dims"].get("number_range", 1)))))}
                      for s in slots]}


def clean(parsed: Any, slots: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Keep only choices the generators can use; everything else falls back to the built-in choice."""
    by = {s["slot"]: s for s in slots}
    out: dict[int, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for raw in (parsed.get("items") if isinstance(parsed, dict) else None) or []:
        if not isinstance(raw, dict):
            continue
        s = by.get(raw.get("slot"))
        if s is None or s["slot"] in out:
            continue
        fmt = raw.get("format")
        chosen = isinstance(fmt, str) and fmt in s["allowed"] and fmt in GENERATORS
        if chosen and s["role"] != "stretch" and counts.get(fmt, 0) >= MAX_REPEAT:
            chosen = False
        if not chosen:
            fmt = s["default"]
        if s["role"] != "stretch":
            counts[fmt] = counts.get(fmt, 0) + 1
        nums = [n for n in (raw.get("numbers") or []) if isinstance(n, int) and not isinstance(n, bool)
                and 0 <= n <= 9999][:MAX_NUMBERS] if chosen and isinstance(raw.get("numbers"), list) else []
        who, things = str(raw.get("who") or "").strip(), str(raw.get("things") or "").strip()
        out[s["slot"]] = {"format": fmt, "numbers": nums, "chosen": bool(chosen),
                          "who": who if WHO_RE.match(who) else "",
                          "things": things if THINGS_RE.match(things) else "",
                          "why": " ".join(str(raw.get("why") or "").split())[:120]}
    if not any(g["chosen"] for g in out.values()):
        raise WriterError("the model returned no usable choices")
    return out


def _complete(llm: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    from .intake import IntakeError, _parsed, strict_schema

    if llm is None or not hasattr(llm, "complete_structured"):
        raise WriterError("no model connection is available to this plugin")
    kw = dict(instructions=INSTRUCTIONS, input=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
              json_schema=strict_schema(SCHEMA), schema_name="homework_coach_sheet",
              purpose="homework-coach sheet writer", timeout=TIMEOUT_SECONDS)
    try:
        res = llm.complete_structured(task=AUX_TASK, **kw)
    except Exception as e:
        if type(e).__name__ != "PluginLlmTrustError":
            raise
        res = llm.complete_structured(**kw)  # writer task not registered in this process: use the main model
    try:
        return _parsed(res), str(getattr(res, "model", "") or "")
    except IntakeError:
        raise WriterError("the model did not return a usable plan") from None


def make(llm: Any, store: Any) -> Callable[..., dict[str, Any]]:
    """The callable ``plan_child`` asks for a guide. Raises on any failure (the caller falls back)."""
    def write(*, child: Any, date: str, slots: list[dict[str, Any]], info: dict[str, Any]) -> dict[str, Any]:
        parsed, model = _complete(llm, request(child, date, slots, info, store))
        guide = clean(parsed, slots)
        note = " ".join(str(parsed.get("note") or "").split())[:240]
        return {"slots": guide, "note": note if _printable(note) else "", "model": model[:80]}
    return write
