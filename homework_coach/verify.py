"""Programmatic verification (SPEC §9.2 step 4).

Item checks recompute every answer from the item's ``spec`` using :mod:`arith`
only (never trusting the generator's own arithmetic), and check every drawn
inventory against the numbers in the prompt/answer. PDF checks confirm child
pages carry no answers, every item is present, text is printable, and (when
``pypdfium2`` is available) pages render non-blank with clear margins.
"""
from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from . import arith
from .models import PacketItem

CHOICE_ANSWERS = {"A", "B", "C", "D", "True", "False", "<", ">", "="}
FREE_VISUALS = {"objects", "ten_frame", "two_groups", "array", "groups", "share", "bar", "bar_equal",
                "fraction_bar", "set", "number_line", "base_ten", "number_path"}


def _expected(item: PacketItem) -> str:
    s = item.spec
    k = s.get("kind")
    if k == "expr":
        return arith.fmt(arith.evaluate(s["expr"]))
    if k == "missing":
        return arith.fmt(arith.solve_missing(s["equation"]))
    if k == "compare":
        a, b = arith.evaluate(s["left"]), arith.evaluate(s["right"])
        return "<" if a < b else ">" if a > b else "="
    if k == "tf":
        return "True" if arith.equation_holds(s["equation"]) else "False"
    if k == "choice_more":
        if s["a"] == s["b"]:
            raise AssertionError("more/less groups are equal")
        return "A" if s["a"] > s["b"] else "B"
    if k == "next":
        seq = [int(x) for x in s["seq"]]
        diffs = {b - a for a, b in zip(seq, seq[1:])}
        if len(diffs) != 1:
            raise AssertionError("sequence step is not constant")
        return str(seq[-1] + diffs.pop())
    if k == "expanded":
        n = int(s["n"])
        parts = [int(p) for p in item.answer.split("+")]
        if sum(parts) != n or any(not re.fullmatch(r"[1-9]0*", str(p)) for p in parts):
            raise AssertionError(f"expanded form {item.answer!r} != {n}")
        return item.answer
    if k == "order":
        return ", ".join(str(v) for v in sorted(int(v) for v in s["values"]))
    if k == "select":
        target = arith.evaluate(s["target"])
        letters = "ABCDE"
        vals = [arith.evaluate(o) for o in s["options"]]
        good = [letters[i] for i, v in enumerate(vals) if v == target]
        if not good or len(good) == len(vals):
            raise AssertionError("select-all needs at least one correct and one incorrect option")
        if len(set(s["options"])) != len(s["options"]):
            raise AssertionError("duplicate options")
        return ", ".join(good)
    if k == "fact_family":
        a, b = int(s["a"]), int(s["b"])
        eqs = s["equations"]
        if len(set(eqs)) != 4 or not all(arith.equation_holds(e) for e in eqs):
            raise AssertionError("fact family must be 4 distinct true equations")
        nums = {frozenset(int(x) for x in re.findall(r"\d+", e)) for e in eqs}
        if nums != {frozenset({a, b, a * b})}:
            raise AssertionError("fact family uses numbers outside the family")
        return "; ".join(eqs)
    if k == "fraction":
        num, den = int(s["num"]), int(s["den"])
        if not (0 < num < den):
            raise AssertionError("fraction must be proper and non-zero")
        return f"{num}/{den}" if item.format != "shade_fraction" else f"{num} of {den} parts shaded"
    if k == "free":  # a problem the parent's model wrote (see writer.py)
        t = s.get("type")
        steps = s.get("steps") or []
        for st in steps:  # every fill-in line is recomputed too
            if st["text"].count("___") != 1 or arith.fmt(arith.evaluate(st["check"])) != st["answer"]:
                raise AssertionError("a fill-in line does not match its arithmetic")
        filled = " ".join(f"({'abcd'[i]}) {st['answer']}" for i, st in enumerate(steps))
        if t == "lines":
            if not steps:
                raise AssertionError("no fill-in lines")
            return filled
        if steps and f"Fill-ins: {filled}." not in item.worked_solution:
            raise AssertionError("fill-in answers are missing from the parent key")
        if t == "number":
            return arith.fmt(arith.evaluate(s["check"]))  # the printed answer is recomputed, never trusted
        if t == "choice":
            labels = [d.split(".")[0].strip() for d in item.display]
            if labels != list(s.get("labels") or []) or not 2 <= len(labels) <= 4 or item.answer not in labels:
                raise AssertionError("answer is not one of the printed choices")
            return item.answer
        if t == "open":
            if item.answer != "Answers vary" or not item.worked_solution.startswith("Look for:"):
                raise AssertionError("an explain problem needs a 'Look for' line for the parent")
            return item.answer
        raise AssertionError(f"unknown written answer type {t!r}")
    raise AssertionError(f"unknown spec kind {k!r}")


def _answer_matches(item: PacketItem, expected: str) -> bool:
    if item.answer == expected:
        return True
    # equation-style answers ("3 × 4 = 12") must be true and contain the expected value
    if "=" in item.answer and item.spec.get("kind") == "expr":
        try:
            return arith.equation_holds(item.answer) and arith.evaluate(item.answer.split("=")[-1]) == arith.evaluate(expected)
        except arith.ArithError:
            return False
    return False


def _check_visual(item: PacketItem) -> list[str]:
    v, s, errs = item.visual_inventory, item.spec, []
    t = v.get("type")
    if not t:
        return errs
    if s.get("kind") == "free":  # the picture illustrates the problem; its numbers were range-checked
        return errs if t in FREE_VISUALS else [f"unknown visual {t!r}"]
    ans = item.answer
    try:
        if t == "objects":
            if v["count"] != int(ans):
                errs.append(f"drew {v['count']} objects, answer {ans}")
        elif t == "ten_frame":
            if any(not 0 <= f <= 10 for f in v["filled"]):
                errs.append("ten frame over-filled")
            total = sum(v["filled"])
            claimed = arith.evaluate(ans.split("=")[-1]) if "=" in ans else Fraction(ans)
            if total != claimed:
                errs.append(f"ten frames hold {total}, answer {ans}")
        elif t == "two_groups":
            if (v["a"], v["b"]) != (s["a"], s["b"]):
                errs.append("group sizes differ from spec")
        elif t == "base_ten":
            if v["hundreds"] * 100 + v["tens"] * 10 + v["ones"] != int(ans):
                errs.append("blocks do not total the answer")
            if any(not 0 <= v[k] <= 9 for k in ("hundreds", "tens", "ones")):
                errs.append("block digit out of range")
        elif t == "number_line":
            end = v["start"] + v["jump"] * v["count"]
            if end != int(ans):
                errs.append("number line end != answer")
            if not (v["lo"] <= v["start"] and end <= v["hi"]):
                errs.append("number line range does not include the jumps")
        elif t == "bar":
            parts = v["parts"]
            if v["total"] is not None and v["total"] != v["true_total"]:
                errs.append("bar total label wrong")
            known = [p for p in parts if p is not None]
            if None in parts:
                if sum(known) + int(ans) != v["true_total"]:
                    errs.append("bar parts + answer != whole")
            elif sum(known) != v["true_total"] or int(ans) != v["true_total"]:
                errs.append("bar parts do not sum to the whole")
        elif t == "array":
            claimed = arith.evaluate(ans.split("=")[-1])
            if v["rows"] * v["cols"] != claimed:
                errs.append("array size != answer")
            m = re.match(r"\s*(\d+)\s*×\s*(\d+)", ans)
            if not m or sorted(map(int, m.groups())) != sorted((v["rows"], v["cols"])):
                errs.append("array equation factors differ from drawing")
        elif t == "groups":
            if v["groups"] * v["per_group"] != int(ans):
                errs.append("groups × per_group != answer")
            nums = [int(x) for x in re.findall(r"\d+", item.prompt)]
            if nums[:2] != [v["groups"], v["per_group"]]:
                errs.append("prompt numbers differ from drawing")
        elif t == "share":
            if v["total"] % v["groups"] or v["total"] // v["groups"] != int(ans):
                errs.append("sharing does not divide evenly to the answer")
        elif t == "bar_equal":
            if v["total"] != v["parts"] * int(ans):
                errs.append("equal bar parts != answer")
        elif t == "fraction_bar":
            if not 2 <= v["parts"] <= 12:
                errs.append("fraction bar parts out of range")
            if item.format == "name_fraction" and f"{v['shaded']}/{v['parts']}" != ans:
                errs.append("shaded parts differ from answer")
            if item.format == "shade_fraction" and v["shaded"] != 0:
                errs.append("shade-the-fraction bar must start unshaded")
        elif t == "set":
            if f"{v['shaded']}/{v['total']}" != ans:
                errs.append("set shading differs from answer")
        else:
            errs.append(f"unknown visual {t!r}")
    except (KeyError, ValueError, TypeError, arith.ArithError) as e:
        errs.append(f"visual check error: {e}")
    return errs


def check_item(item: PacketItem) -> list[str]:
    errs: list[str] = []
    try:
        expected = _expected(item)
        if not _answer_matches(item, expected):
            errs.append(f"answer {item.answer!r} != recomputed {expected!r}")
    except (AssertionError, arith.ArithError, KeyError, ValueError) as e:
        errs.append(f"cannot verify: {e}")
    errs += _check_visual(item)
    child_text = " ".join([item.prompt, item.hint, *item.display,
                           *(str(st.get("text", "")) for st in item.spec.get("steps") or [])])
    try:
        child_text.encode("cp1252")
        item.answer.encode("cp1252")
        item.worked_solution.encode("cp1252")
    except UnicodeEncodeError as e:
        errs.append(f"unprintable character: {e.object[e.start:e.end]!r}")
    if item.answer not in CHOICE_ANSWERS and len(item.answer) > 3 and item.answer in child_text:
        errs.append("answer appears on the child page")
    if item.display and item.spec.get("kind") in ("tf", "choice_more", "select"):
        labels = {d.split(".")[0].strip() for d in item.display}
        if not set(re.split(r",\s*", item.answer)) <= labels:
            errs.append("answer is not one of the printed choices")
    return [f"item {item.id or '?'} ({item.format}): {e}" for e in errs]


def check_items(items: Iterable[PacketItem], budget: int | None = None) -> list[str]:
    items = list(items)
    errs = [e for it in items for e in check_item(it)]
    ids = [it.id for it in items]
    if len(set(ids)) != len(ids):
        errs.append("duplicate item ids")
    core = [it for it in items if not it.optional]
    if budget is not None and len(core) != budget:
        errs.append(f"core item count {len(core)} != budget {budget}")
    return errs


# -- PDF checks ----------------------------------------------------------------------------------
def pdf_text(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    r = PdfReader(str(path))
    return "\n".join(p.extract_text() or "" for p in r.pages), len(r.pages)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_child_pdf(path: Path, items: list[PacketItem]) -> list[str]:
    errs: list[str] = []
    text, pages = pdf_text(path)
    flat = _norm(text)
    if pages < 1:
        errs.append(f"{path.name}: no pages")
    for it in items:
        if not re.search(rf"(?<!\d){re.escape(it.id)}\.", flat):
            errs.append(f"{path.name}: item {it.id} label missing")
        if it.worked_solution and _norm(it.worked_solution) in flat:
            errs.append(f"{path.name}: worked solution for item {it.id} on child page")
        if it.answer not in CHOICE_ANSWERS and len(it.answer) > 3 and _norm(it.answer) in flat:
            errs.append(f"{path.name}: answer for item {it.id} on child page")
    for banned in ("Answer key", "Worked solution", "ANSWER"):
        if banned in text:
            errs.append(f"{path.name}: contains {banned!r}")
    return errs


def check_key_pdf(path: Path, items_by_child: dict[str, list[PacketItem]]) -> list[str]:
    errs: list[str] = []
    text, _ = pdf_text(path)
    flat = _norm(text)
    for cid, items in items_by_child.items():
        for it in items:
            if _norm(it.answer) not in flat:
                errs.append(f"{path.name}: {cid} item {it.id} answer missing from key")
    return errs


def render_check(path: Path, *, margin_pt: float = 18.0, dpi: int = 50) -> dict[str, Any]:
    """Rasterise each page; assert it is non-blank and the outer margin band is empty.

    Returns ``{"checked": bool, "errors": [...]}``; ``checked`` is False when
    pypdfium2 is not installed (text-bounds checks in the renderer still ran).
    """
    try:
        import pypdfium2 as pdfium
    except Exception:
        return {"checked": False, "errors": [], "note": "pypdfium2 not installed; raster check skipped"}
    errs: list[str] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            img = page.render(scale=dpi / 72).to_pil().convert("L")
            w, h = img.size
            px = img.load()
            m = max(1, int(margin_pt * dpi / 72))
            dark = sum(1 for y in range(0, h, 2) for x in range(0, w, 2) if px[x, y] < 200)
            if dark < 50:
                errs.append(f"{path.name} p{i + 1}: page renders blank")
            band = [(x, y) for y in range(h) for x in range(w)
                    if (x < m or x >= w - m or y < m or y >= h - m) and px[x, y] < 200]
            if band:
                errs.append(f"{path.name} p{i + 1}: {len(band)} dark pixels in the outer margin")
    finally:
        pdf.close()
    return {"checked": True, "errors": errs}
