"""Model-written sheets (opt-in: "Who writes the sheet" = your model).

The parent's model writes the problems itself: fresh task shapes aimed at what the child's
homework, the class unit, the parent's ratings and the parent's own guidance show is needed.
Nothing it writes is printed on trust. Every written problem must pass three checks:

1. **Arithmetic.** A number problem carries the model's own arithmetic (``check``). The plugin
   evaluates it with :mod:`arith` (no ``eval``) and prints *its* result as the answer; a claimed
   answer that differs is thrown out.
2. **Second pass.** A separate model call solves every problem seeing only what the child sees
   (prompt, picture, choices). A different answer, or "this is ambiguous", throws it out.
3. **Page checks.** The usual item and PDF verification.

A problem that fails is rewritten once with the reason; if it fails again the built-in
generator fills that slot. Any model failure gives the built-in sheet, so a sheet is always made.
The model may also pick one of the plugin's ready-made drawn formats for a slot.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from typing import Any, Callable

from . import arith, catalog, verify
from .generators import GENERATORS, num_max
from .models import PacketItem

AUX_TASK = "homework_writer"
WRITTEN = "written"                 # PacketItem.format of a model-written problem
WRITTEN_LABEL = "Written for this sheet"
MAX_REPEAT = 2                      # a ready-made format appears at most twice among the core problems
MAX_NUMBERS = 6
WRITE_TIMEOUT, CHECK_TIMEOUT = 180, 120
REWRITE_BUDGET_SECONDS = 200        # no rewrite round once this much time has gone
PROMPT_MIN, PROMPT_MAX, WORD_MAX = 8, 420, 34
CHOICE_MAX, MAX_CHOICES = 48, 4
MAX_OPEN = 2
BRIEF_CHARS = 2500
LETTERS = "ABCD"
WHO_RE = re.compile(r"^[A-Z][a-z]{1,11}$")
THINGS_RE = re.compile(r"^[a-z]{2,13}s$")
NUM_RE = re.compile(r"-?\d+(?:\s*/\s*\d+|\.\d+)?")
PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users|mnt|var|tmp)/)\S+")
RATING_WORDS = {"I": "on their own", "S": "with support", "N": "not yet"}
SWAPS = {"\u2212": "-", "\u2013": "-", "\u2192": "->", "\u2264": "<=", "\u2265": ">=", "\u2260": "is not equal to",
         "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u2217": "\u00d7", "\u22c5": "\u00d7", "\u2026": "..."}

# The order each ready-made generator takes its numbers in. Shown to the model; a test keeps it complete.
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

# Pictures a written problem may ask for. The plugin draws exactly these numbers.
PICTURES: dict[str, str] = {
    "objects": "[how many circles] (1 to 30): a row of circles to count",
    "ten_frame": "[dots in frame 1, dots in frame 2 (optional), dots in frame 3 (optional)] (each 0 to 10)",
    "two_groups": "[circles in group A, circles in group B] (each 1 to 10), labelled A and B",
    "array": "[rows, columns] (rows 1 to 10, columns 1 to 12): dots in rows and columns",
    "groups": "[groups, dots in each group] (each 1 to 10): boxes with dots inside",
    "share": "[dots, empty circles to share them into] (dots 2 to 45, circles 2 to 7)",
    "bar": "[whole, part, part, ...] (2 to 4 parts): a bar model; write 0 for the one box that shows a question mark",
    "bar_equal": "[total written above the bar, equal parts] (parts 2 to 10): a bar cut into equal empty parts",
    "fraction_bar": "[equal parts, shaded parts] (parts 2 to 12): a bar with some parts shaded (0 shaded = blank bar)",
    "set": "[circles in all, shaded circles] (1 to 30 circles)",
    "number_line": "[first number, last number, tick step] (2 to 20 steps; first number a multiple of the step): a labelled number line with nothing marked on it",
    "base_ten": "[hundreds blocks 0 to 5, tens rods 0 to 9, ones cubes 0 to 9]",
}

INSTRUCTIONS = (
    "You are an experienced elementary maths teacher writing one short practice sheet for one child. "
    "You write the problems yourself. A program prints the page, so return data only.\n\n"
    "WHAT YOU KNOW (`child`): grade and school programme; the class unit, its goals and vocabulary; "
    "`learning_brief` (running notes from the child's homework photos and teacher material); "
    "`latest_homework` (each problem, what the child wrote, and how it went); `recent_parent_ratings` "
    "(the parent marked each earlier practice problem done on their own / with support / not yet, "
    "sometimes with a note); `recent_sheets` (problems already printed on the last few sheets); and "
    "`parent_guidance` (what the parent asked these sheets to work on: follow it).\n\n"
    "THE SLOTS: write exactly one item for every entry in `slots`. role `target` = the current class "
    "skill, aimed at what the homework and ratings show is still hard: rebuild the exact mistake in a "
    "fresh setting (the same number facts, the same problem structure, the step that was missed). "
    "role `review` = confident wins on the review skill. role `stretch` = one optional harder problem "
    "(two steps, or explain your thinking). Each slot gives `max_number` (keep numbers at or below it "
    "unless the homework itself used bigger ones) and `difficulty` from 1 to 5: `steps` 3 or more means "
    "two-step problems suit this child; `scaffold` 1 or 2 means keep wording simple and give a `hint`; "
    "`representation` 1 or 2 means lean on pictures.\n\n"
    "VARIETY: change the task shape, not just the numbers. For example: find the hidden question in a "
    "two-step story; spot and fix a made-up student's mistake; choose the equation that matches a "
    "story; complete a pattern and say the rule; compare two strategies; decide true or false and why; "
    "fill a missing number; read a picture; a real-life setting this child would enjoy. No two problems "
    "on the sheet may share a template, and none may copy a problem or the order of problems in "
    "`recent_sheets`.\n\n"
    "READABILITY: words and sentence length for the grade. For kindergarten and grade 1 use one short "
    "sentence a grown-up can read aloud and lean on pictures. Never need colours, scissors or objects. "
    "Plain keyboard characters plus the signs for times and divide only; write ___ for a blank inside "
    "an equation. Never use the child's own name. Never put an answer in a `prompt` or `hint`.\n\n"
    "EACH ITEM: `slot`; `kind` = \"written\"; `prompt` (the problem as the child reads it); "
    "`answer_type`:\n"
    "- \"number\": `answer` is only a whole number or a fraction like 3/4 (no units, no words), and "
    "`check` is plain arithmetic using only numbers and + - * / ( ) that works out to exactly that "
    "answer, built from the problem's own numbers, e.g. \"(4 + 3) * 5\". The program recomputes it.\n"
    "- \"choice\": `choices` has 2 to 4 short options, exactly one correct; `answer` is its letter "
    "(A, B, C or D in the order given). Do not letter the options yourself.\n"
    "- \"open\": explain, draw or show thinking; `answer` is one short sentence saying what a good "
    "response includes. At most `max_open` open problems on the sheet.\n"
    "`picture`: optional. `type` is one of `pictures` with `numbers` in the order shown; it is drawn "
    "exactly, so the prompt must agree with it. Use type \"\" and [] for no picture. "
    "`hint`: a short nudge that does not give the answer away. `solution`: the worked solution for "
    "the parent in one to three short sentences. `tip`: one line telling the parent how to help if "
    "the child is stuck. `why`: a few words on why this problem for this child. Leave `format`, "
    "`who` and `things` empty and `numbers` [] for a written item.\n\n"
    "READY-MADE OPTION: instead of writing, a slot may use one of the program's own drawn formats "
    "listed under its skill in `formats` (useful for a fact family, select-all, expanded form and "
    "similar). Then set `kind` = \"builtin\", `format` to its id, `numbers` in the order shown, `who` "
    "and `things` (a first name and a lowercase plural object for story formats, else empty), `why`, "
    "and leave the written fields empty. Write most problems yourself.\n\n"
    "CHECKING: a second teacher will solve every written problem seeing only what the child sees. "
    "A problem that is ambiguous, has more than one right answer, or needs something not on the page "
    "is thrown away. If `rewrite` is present, those problems were thrown away for the reason given: "
    "write a different, sound problem for each of those slots, and do not reuse the numbers or the "
    "setting of the problems in `already_on_sheet`, which are being kept.\n\n"
    "`note`: one plain sentence telling the parent what this sheet concentrates on and why."
)

CHECK_INSTRUCTIONS = (
    "You are checking a child's maths practice sheet before it is printed. Each entry in `problems` "
    "shows exactly what the child will see: the `prompt`, a description of the drawn `picture` if "
    "there is one, the `choices` if there are any, and a printed `hint` if there is one. Solve each one from that alone.\n"
    "Return one entry per problem with `slot`, and `answer`: for type \"number\" only the number "
    "(a whole number or a fraction like 3/4); for type \"choice\" only the letter of the correct "
    "option; for type \"open\" an empty string.\n"
    "Set `ok` to false, with a few words in `issue`, when the problem is ambiguous, has no correct "
    "answer or more than one, depends on something that is not shown, disagrees with its picture, "
    "gives its own answer away, or is clearly wrong for the grade given. Otherwise `ok` is true and "
    "`issue` is empty. Be strict: a child will work from this page."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "note": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "slot": {"type": "integer"},
                "kind": {"type": "string", "enum": ["written", "builtin"]},
                "prompt": {"type": "string"},
                "answer_type": {"type": "string", "enum": ["number", "choice", "open", ""]},
                "answer": {"type": "string"},
                "check": {"type": "string"},
                "choices": {"type": "array", "items": {"type": "string"}},
                "picture": {"type": "object", "properties": {
                    "type": {"type": "string"},
                    "numbers": {"type": "array", "items": {"type": "integer"}}},
                    "required": ["type", "numbers"]},
                "hint": {"type": "string"},
                "solution": {"type": "string"},
                "tip": {"type": "string"},
                "format": {"type": "string"},
                "numbers": {"type": "array", "items": {"type": "integer"}},
                "who": {"type": "string"},
                "things": {"type": "string"},
                "why": {"type": "string"},
            },
            "required": ["slot", "kind", "prompt", "answer_type", "answer", "check", "choices", "picture", "hint",
                         "solution", "tip", "format", "numbers", "who", "things", "why"],
        }},
    },
    "required": ["note", "items"],
}

CHECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {
        "type": "object",
        "properties": {"slot": {"type": "integer"}, "answer": {"type": "string"}, "ok": {"type": "boolean"},
                       "issue": {"type": "string"}},
        "required": ["slot", "answer", "ok", "issue"]}}},
    "required": ["answers"],
}


class WriterError(RuntimeError):
    pass


# -- text ----------------------------------------------------------------------------------------
def _printable(text: str) -> bool:
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _text(value: Any, limit: int) -> str:
    s = str(value or "")
    for a, b in SWAPS.items():
        s = s.replace(a, b)
    return " ".join(s.split())[:limit]


def _ints(value: Any) -> list[int]:
    return [n for n in value if isinstance(n, int) and not isinstance(n, bool)] if isinstance(value, list) else []


def scrub(text: str, child: Any, siblings: list[str] | None = None) -> str:
    """Take names and file paths out of free text before it is sent to the model provider."""
    out = PATH_RE.sub("[file]", str(text or ""))
    out = re.sub(rf"\b{re.escape(child.name)}\b", "the child", out, flags=re.I)
    if child.id.lower() != child.name.lower():
        out = re.sub(rf"\b{re.escape(child.id)}\b", "the child", out, flags=re.I)
    for name in siblings or []:
        if name and name.lower() != child.name.lower():
            out = re.sub(rf"\b{re.escape(name)}\b", "a sibling", out, flags=re.I)
    return out


# -- pictures ------------------------------------------------------------------------------------
def picture_inventory(ptype: str, nums: list[int]) -> dict[str, Any]:
    """Turn a model's picture request into the renderer's inventory, or raise WriterError."""
    def need(n: int, lo: int | None = None) -> None:
        if not (lo if lo is not None else n) <= len(nums) <= n:
            raise WriterError(f"picture {ptype} needs {n} numbers")

    def rng(v: int, lo: int, hi: int, what: str) -> int:
        if not lo <= v <= hi:
            raise WriterError(f"picture {ptype}: {what} must be {lo} to {hi}")
        return v

    if ptype == "objects":
        need(1)
        return {"type": "objects", "count": rng(nums[0], 1, 30, "count")}
    if ptype == "ten_frame":
        need(3, 1)
        return {"type": "ten_frame", "filled": [rng(n, 0, 10, "dots") for n in nums]}
    if ptype == "two_groups":
        need(2)
        return {"type": "two_groups", "a": rng(nums[0], 1, 10, "group A"), "b": rng(nums[1], 1, 10, "group B")}
    if ptype == "array":
        need(2)
        return {"type": "array", "rows": rng(nums[0], 1, 10, "rows"), "cols": rng(nums[1], 1, 12, "columns")}
    if ptype == "groups":
        need(2)
        return {"type": "groups", "groups": rng(nums[0], 1, 10, "groups"), "per_group": rng(nums[1], 1, 10, "dots")}
    if ptype == "share":
        need(2)
        return {"type": "share", "total": rng(nums[0], 2, 45, "dots"), "groups": rng(nums[1], 2, 7, "circles")}
    if ptype == "bar":
        need(5, 3)
        whole, parts = nums[0], nums[1:]
        if any(n < 0 or n > 9999 for n in nums) or [whole, *parts].count(0) > 1:
            raise WriterError("picture bar: at most one box may be the question mark (0)")
        known = sum(parts)
        if whole == 0:
            true_total = known
        elif 0 in parts:
            true_total = whole
            if whole <= known:
                raise WriterError("picture bar: the parts are bigger than the whole")
        else:
            true_total = whole
            if whole != known:
                raise WriterError("picture bar: the parts do not add up to the whole")
        return {"type": "bar", "total": whole or None, "parts": [p or None for p in parts], "true_total": true_total}
    if ptype == "bar_equal":
        need(2)
        return {"type": "bar_equal", "total": rng(nums[0], 1, 9999, "total"), "parts": rng(nums[1], 2, 10, "parts")}
    if ptype == "fraction_bar":
        need(2)
        parts = rng(nums[0], 2, 12, "parts")
        return {"type": "fraction_bar", "parts": parts, "shaded": rng(nums[1], 0, parts, "shaded parts")}
    if ptype == "set":
        need(2)
        total = rng(nums[0], 1, 30, "circles")
        return {"type": "set", "total": total, "shaded": rng(nums[1], 0, total, "shaded circles")}
    if ptype == "number_line":
        need(3)
        lo, hi, step = rng(nums[0], 0, 9990, "first number"), nums[1], rng(nums[2], 1, 1000, "step")
        if not lo < hi <= 9999 or (hi - lo) % step or lo % step or not 2 <= (hi - lo) // step <= 20:
            raise WriterError("picture number_line: needs 2 to 20 equal steps, starting on a multiple of the step")
        return {"type": "number_line", "lo": lo, "hi": hi, "jump": step}
    if ptype == "base_ten":
        need(3)
        h, t, o = rng(nums[0], 0, 5, "hundreds"), rng(nums[1], 0, 9, "tens"), rng(nums[2], 0, 9, "ones")
        if h + t + o == 0:
            raise WriterError("picture base_ten: no blocks")
        return {"type": "base_ten", "hundreds": h, "tens": t, "ones": o}
    raise WriterError(f"unknown picture {ptype!r}")


# -- one written problem -------------------------------------------------------------------------
def written_item(raw: dict[str, Any], slot: dict[str, Any], grade: str) -> PacketItem:
    """Build a PacketItem from a model-written problem, or raise WriterError saying why not."""
    prompt = _text(raw.get("prompt"), PROMPT_MAX + 1)
    if not PROMPT_MIN <= len(prompt) <= PROMPT_MAX:
        raise WriterError("the problem text is missing or too long")
    if any(len(w) > WORD_MAX for w in prompt.split()):
        raise WriterError("a word in the problem is too long to print")
    kind = raw.get("answer_type")
    pic = raw.get("picture") if isinstance(raw.get("picture"), dict) else {}
    visual = picture_inventory(str(pic.get("type")), _ints(pic.get("numbers"))) if pic.get("type") else {}
    solution = _text(raw.get("solution"), 400)
    display: list[str] = []
    spec: dict[str, Any] = {"kind": "free", "type": kind}
    young = catalog.grade_num(grade) <= 1
    work_lines = 1 if young else 2
    if kind == "number":
        check = _text(raw.get("check"), 80)
        try:
            value = arith.evaluate(check)
        except arith.ArithError:
            raise WriterError("its arithmetic check is not plain arithmetic") from None
        claimed = arith.parse_number(_text(raw.get("answer"), 40))
        if claimed is None:
            raise WriterError("its answer is not a plain number")
        if claimed != value:
            raise WriterError(f"its answer {arith.fmt(claimed)} does not match its own arithmetic "
                              f"({check} = {arith.fmt(value)})")
        if value < 0 or value.denominator > 100:
            raise WriterError("its answer is negative or an awkward fraction")
        answer = arith.fmt(value)
        spec["check"] = check
        if not solution:
            solution = f"{check.replace('*', '×').replace('/', '÷')} = {answer}."
    elif kind == "choice":
        opts = [re.sub(r"^\(?[A-Da-d][.):]\s+", "", _text(c, CHOICE_MAX + 8)) for c in (raw.get("choices") or [])
                if isinstance(c, str)]
        if not 2 <= len(opts) <= MAX_CHOICES or len({o.lower() for o in opts}) != len(opts) \
                or any(not o or len(o) > CHOICE_MAX for o in opts):
            raise WriterError("it needs 2 to 4 short, different choices")
        answer = _text(raw.get("answer"), 4).strip(".() ").upper()
        labels = list(LETTERS[:len(opts)])
        if answer not in labels:
            raise WriterError("its answer is not the letter of one of the choices")
        display = [f"{lab}. {o}" for lab, o in zip(labels, opts)]
        spec["labels"] = labels
        work_lines = 0 if young else 1
        right = opts[labels.index(answer)]
        solution = f"{answer}. {right}{'' if right[-1] in '.?!' else '.'}" + (f" {solution}" if solution else "")
    elif kind == "open":
        look = _text(raw.get("answer"), 240)
        if len(look) < 8:
            raise WriterError("an explain problem needs a line saying what a good answer includes")
        answer = "Answers vary"
        solution = f"Look for: {look}" + (f" {solution}" if solution else "")
        spec["box"] = True
        work_lines = 3
    else:
        raise WriterError("it has no answer type")
    if slot["role"] == "stretch":
        spec["box"] = True
        work_lines = max(work_lines, 3)
    scaffold = max(1, min(5, int(slot["dims"].get("scaffold", 1))))
    hint = _text(raw.get("hint"), 140) if scaffold <= 2 else ""
    tip = _text(raw.get("tip"), 220)
    for piece in (prompt, hint, solution, tip, *display):
        if not _printable(piece):
            raise WriterError("it uses a character the page cannot print")
    return PacketItem(id="", skill=slot["skill"], format=WRITTEN, prompt=prompt, answer=answer,
                      worked_solution=solution, role=slot["role"], visual_inventory=visual, spec=spec,
                      display=display, hint=hint, work_lines=work_lines, parent_tip=tip)


def same_task(a: PacketItem, b: PacketItem) -> bool:
    """Two written problems that are the same task: the same wording, or the same arithmetic."""
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    if norm(a.prompt) == norm(b.prompt):
        return True
    ca, cb = a.spec.get("check"), b.spec.get("check")
    return bool(ca and cb and re.sub(r"\s+", "", ca) == re.sub(r"\s+", "", cb))


def builtin_choice(raw: dict[str, Any], slot: dict[str, Any], counts: dict[str, int]) -> dict[str, Any] | None:
    """A ready-made format the generators can use for this slot, or None."""
    fmt = raw.get("format")
    if not (isinstance(fmt, str) and fmt in slot["allowed"] and fmt in GENERATORS):
        return None
    if slot["role"] != "stretch":
        if counts.get(fmt, 0) >= MAX_REPEAT:
            return None
        counts[fmt] = counts.get(fmt, 0) + 1
    who, things = str(raw.get("who") or "").strip(), str(raw.get("things") or "").strip()
    return {"format": fmt, "numbers": [n for n in _ints(raw.get("numbers")) if 0 <= n <= 9999][:MAX_NUMBERS],
            "who": who if WHO_RE.match(who) else "", "things": things if THINGS_RE.match(things) else "",
            "why": _text(raw.get("why"), 120)}


# -- what the model is told ----------------------------------------------------------------------
def _packet_items(store: Any, date: str, child_id: str) -> list[dict[str, Any]]:
    try:
        data = json.loads((store.packet_dir(date, create=False) / "packet.json").read_text(encoding="utf-8"))
        return list(data["children"][child_id]["items"])
    except (OSError, ValueError, KeyError, TypeError):
        return []


def context(store: Any, child: Any, date: str, info: dict[str, Any]) -> dict[str, Any]:
    """What the model is told about the child. Names and file paths are taken out of free text."""
    from . import daily
    from .difficulty import effective_feedback

    sibs = list(info.get("siblings") or [])

    def clean(text: Any, limit: int) -> str:
        return scrub(str(text or ""), child, sibs)[:limit]

    obs = [o for o in store.observations(child.id) if o.date <= date]
    homework = None
    if obs:
        o = obs[-1]
        homework = {"date": o.date, "lesson": clean(o.lesson, 160), "notes": clean(o.notes, 300),
                    "problems": [{"problem": clean(i.prompt, 160), "child_wrote": i.child_answer,
                                  "expected": i.expected_answer, "result": i.status,
                                  "note": clean(i.note, 120)} for i in o.items[:16]]}
    rated = []
    for fb in effective_feedback(store.feedback(child.id))[-3:]:
        items = _packet_items(store, fb.packet_date, child.id)
        if not items:
            continue
        rated.append({"sheet": fb.packet_date, "parent_note": clean(fb.note, 240),
                      "problems": [{"problem": str(i["prompt"])[:160],
                                    "parent_rating": RATING_WORDS.get(fb.item_ratings.get(str(i["id"])), "not rated")}
                                   for i in items]})
    recent = []
    for d in store.recent_packets(3, before=date):
        items = _packet_items(store, d.name, child.id)
        if items:
            recent.append({"sheet": d.name, "problems": [str(i["prompt"])[:160] for i in items]})
    steer = info.get("steer") or {}
    unit = steer.get("unit") or {}
    brief = clean(store.read_brief(child.id)[-BRIEF_CHARS:], BRIEF_CHARS)
    return {"grade": child.grade, "school_program": child.curriculum, "sheet_date": date,
            "class_unit": unit.get("title"), "unit_goals": list(steer.get("goals") or []),
            "unit_vocabulary": [str(v) for v in (unit.get("vocabulary") or [])][:12],
            "practice_follows": steer.get("source"),
            "parent_guidance": clean(daily.settings(store)["guidance"].get(child.id, ""), daily.GUIDANCE_MAX),
            "learning_brief": brief, "latest_homework": homework, "recent_parent_ratings": rated,
            "recent_sheets": recent}


def request(child: Any, date: str, slots: list[dict[str, Any]], info: dict[str, Any], store: Any) -> dict[str, Any]:
    """The JSON the model reads: the child's context, the slots to fill and what it may draw on."""
    skills = sorted({s["skill"] for s in slots})
    formats = {catalog.SKILLS.get(sk, sk): [
        {"id": f, "what": catalog.FORMATS[f].label, "numbers": NUMBERS.get(f, "[]")}
        for f in dict.fromkeys(f for s in slots if s["skill"] == sk for f in s["allowed"])] for sk in skills}
    young = catalog.grade_num(child.grade) <= 0
    return {"child": context(store, child, date, info), "max_open": 1 if young else MAX_OPEN,
            "pictures": PICTURES, "formats": formats,
            "slots": [{"slot": s["slot"], "role": s["role"], "skill": catalog.SKILLS.get(s["skill"], s["skill"]),
                       "max_number": num_max(s["skill"], child.grade, max(1, min(5, int(s["dims"].get("number_range", 1))))),
                       "difficulty": {k: max(1, min(5, int(s["dims"].get(k, 1))))
                                      for k in ("steps", "scaffold", "representation")}}
                      for s in slots]}


# -- model calls ---------------------------------------------------------------------------------
def _call(llm: Any, instructions: str, schema: dict[str, Any], name: str, payload: dict[str, Any],
          timeout: int) -> tuple[dict[str, Any], str]:
    from .intake import IntakeError, _parsed, strict_schema

    if llm is None or not hasattr(llm, "complete_structured"):
        raise WriterError("no model connection is available to this plugin")
    kw = dict(instructions=instructions, input=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
              json_schema=strict_schema(schema), schema_name=name, purpose="homework-coach sheet writer",
              timeout=timeout)
    try:
        res = llm.complete_structured(task=AUX_TASK, **kw)
    except Exception as e:
        if type(e).__name__ != "PluginLlmTrustError":
            raise
        res = llm.complete_structured(**kw)  # writer task not registered in this process: use the main model
    try:
        return _parsed(res), str(getattr(res, "model", "") or "")
    except IntakeError:
        raise WriterError("the model did not return usable data") from None


def _seen_by_child(item: PacketItem) -> dict[str, Any]:
    from .render import visual_description

    return {"type": item.spec.get("type"), "prompt": item.prompt,
            "picture": visual_description(item).replace("picture: ", ""), "choices": list(item.display),
            "hint": item.hint}


def disagreement(item: PacketItem, sol: dict[str, Any] | None) -> str:
    """Why the second pass does not back this problem ('' when it does)."""
    if not isinstance(sol, dict):
        return "the second check did not look at it"
    if sol.get("ok") is not True:
        return "second check: " + (_text(sol.get("issue"), 140) or "not clear enough")
    kind = item.spec.get("type")
    got = str(sol.get("answer") or "")
    if kind == "number":
        found = NUM_RE.findall(got.replace(",", ""))
        value = arith.parse_number(found[-1]) if found else None
        if value is None or value != arith.parse_number(item.answer):
            return f"second check worked out {got[:20] or 'nothing'}, not {item.answer}"
    elif kind == "choice":
        if got.strip(".() ").upper()[:1] != item.answer:
            return f"second check chose {got[:8] or 'nothing'}, not {item.answer}"
    return ""


def second_pass(llm: Any, grade: str, items: dict[int, PacketItem]) -> dict[int, str]:
    """Solve every written problem blind. Returns ``{slot: reason}`` for the ones that fail."""
    payload = {"grade": grade, "problems": [{"slot": n, **_seen_by_child(it)} for n, it in sorted(items.items())]}
    parsed, _ = _call(llm, CHECK_INSTRUCTIONS, CHECK_SCHEMA, "homework_coach_check", payload, CHECK_TIMEOUT)
    by = {a.get("slot"): a for a in (parsed.get("answers") or []) if isinstance(a, dict)}
    return {n: why for n, it in items.items() if (why := disagreement(it, by.get(n)))}


def make(llm: Any, store: Any) -> Callable[..., dict[str, Any]]:
    """The callable ``plan_child`` asks for a sheet. Raises on any failure (the caller falls back)."""
    def write(*, child: Any, date: str, slots: list[dict[str, Any]], info: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        base = request(child, date, slots, info, store)
        guide: dict[int, dict[str, Any]] = {}
        failed: dict[int, tuple[str, str]] = {}   # slot -> (problem text, reason)
        counts: dict[str, int] = {}
        note = model = ""
        opens = 0
        pending = list(slots)
        payload = base
        for attempt in (1, 2):
            parsed, used = _call(llm, INSTRUCTIONS, SCHEMA, "homework_coach_sheet", payload, WRITE_TIMEOUT)
            model = model or used
            note = note or _text(parsed.get("note"), 240)
            by = {s["slot"]: s for s in pending}
            fresh: dict[int, PacketItem] = {}
            whys: dict[int, str] = {}
            for raw in parsed.get("items") or []:
                s = by.get(raw.get("slot")) if isinstance(raw, dict) else None
                if s is None or s["slot"] in guide or s["slot"] in fresh:
                    continue
                if raw.get("kind") == "builtin":
                    choice = builtin_choice(raw, s, counts)
                    if choice:
                        guide[s["slot"]] = choice
                        failed.pop(s["slot"], None)
                    continue
                try:
                    it = written_item(raw, s, child.grade)
                    if re.search(rf"\b{re.escape(child.name)}\b", " ".join([it.prompt, it.hint, *it.display]), re.I):
                        raise WriterError("it uses the child's own name")
                    errs = verify.check_item(replace(it, id=str(s["slot"])))
                    if errs:
                        raise WriterError(errs[0].split(": ", 1)[-1])
                    kept = [g["written"] for g in guide.values() if "written" in g] + list(fresh.values())
                    if any(same_task(it, k) for k in kept):
                        raise WriterError("it repeats another problem on this sheet")
                    if it.spec.get("type") == "open":
                        if opens >= base["max_open"]:
                            raise WriterError("too many explain problems on one sheet")
                        opens += 1
                    fresh[s["slot"]] = it
                    whys[s["slot"]] = _text(raw.get("why"), 120)
                except WriterError as e:
                    failed[s["slot"]] = (_text(raw.get("prompt"), 200), str(e))
            if fresh:
                bad = second_pass(llm, child.grade, fresh)
                for n, it in fresh.items():
                    if n in bad:
                        failed[n] = (it.prompt[:200], bad[n])
                        opens -= it.spec.get("type") == "open"
                    else:
                        guide[n] = {"written": it, "why": whys.get(n, "")}
                        failed.pop(n, None)
            pending = [s for s in pending if s["slot"] not in guide]
            if not pending or attempt == 2 or time.monotonic() - started > REWRITE_BUDGET_SECONDS:
                break
            want = {s["slot"] for s in pending}
            payload = {**base, "slots": [s for s in base["slots"] if s["slot"] in want],
                       "already_on_sheet": [g["written"].prompt for _, g in sorted(guide.items()) if "written" in g],
                       "rewrite": [{"slot": n, "problem": failed[n][0], "thrown_away_because": failed[n][1]}
                                   for n in sorted(want) if n in failed]}
        if not guide:
            reason = next(iter(failed.values()))[1] if failed else "it returned nothing usable"
            raise WriterError(f"the model wrote no usable problems ({reason})")
        return {"slots": guide, "note": note if _printable(note) else "", "model": model[:80],
                "rejected": [f"problem {n}: {why}"[:200] for n, (_, why) in sorted(failed.items())
                             if n not in guide]}
    return write
