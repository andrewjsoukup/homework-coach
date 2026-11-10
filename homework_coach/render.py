"""PDF rendering with reportlab (SPEC §9.2 step 5).

Child pages: one flowing column, every item numbered, drawn visual, choices and
blank working lines — never answers. Parent key: per child, answer + worked
solution + an I/S/N tick box per item. Every draw call goes through
:class:`Page`, which refuses text outside the printable box (bounds check) and
counts what was actually drawn so :func:`check_drawn` can compare drawn shapes
with the item's inventory.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .models import PacketItem

if TYPE_CHECKING:  # pragma: no cover
    from .packet import ChildPlan

W, H = letter
MARGIN = 54  # 0.75in
FONT, BOLD = "Helvetica", "Helvetica-Bold"
GREY = 0.55


class BoundsError(RuntimeError):
    pass


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if stringWidth(cand, font, size) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class Page:
    def __init__(self, path: Path, title: str, subtitle: str, size: float):
        self.c = Canvas(str(path), pagesize=letter, pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor("Homework Coach")
        self.title, self.subtitle, self.size = title, subtitle, size
        self.page_no = 0
        self.y = 0.0
        self.dot_r = 9.0 if size >= 15 else 6.0
        self._new_page()

    # -- primitives with bounds checks ---------------------------------------------------------
    def text(self, x: float, y: float, s: str, font: str = FONT, size: float | None = None, grey: float = 0) -> None:
        size = size or self.size
        w = stringWidth(s, font, size)
        if x < MARGIN - 0.5 or x + w > W - MARGIN + 0.5 or y < MARGIN - 0.5 or y + size > H - MARGIN + 0.5:
            raise BoundsError(f"text out of bounds on page {self.page_no}: {s[:40]!r}")
        self.c.setFillGray(grey)
        self.c.setFont(font, size)
        self.c.drawString(x, y, s)
        self.c.setFillGray(0)

    def box_ok(self, x: float, y: float, w: float, h: float) -> None:
        if x < MARGIN - 0.5 or x + w > W - MARGIN + 0.5 or y < MARGIN - 0.5 or y + h > H - MARGIN + 0.5:
            raise BoundsError(f"shape out of bounds on page {self.page_no}")

    def _new_page(self) -> None:
        if self.page_no:
            self.c.showPage()
        self.page_no += 1
        top = H - MARGIN
        self.text(MARGIN, top - 16, self.title, BOLD, 16)
        sub_w = stringWidth(self.subtitle, FONT, 10)
        self.text(W - MARGIN - sub_w, top - 14, self.subtitle, FONT, 10, GREY)
        self.c.setLineWidth(0.6)
        self.c.line(MARGIN, top - 24, W - MARGIN, top - 24)
        foot = f"page {self.page_no}"
        self.text(W - MARGIN - stringWidth(foot, FONT, 8), MARGIN, foot, FONT, 8, GREY)
        self.y = top - 44

    def need(self, h: float) -> None:
        if self.y - h < MARGIN + 16:
            self._new_page()

    def save(self) -> None:
        self.c.save()


# -- visuals -------------------------------------------------------------------------------------
def _circles(p: Page, x: float, y: float, n: int, per_row: int = 10, r: float | None = None,
             filled: int = 0) -> tuple[int, float]:
    """Draw n circles (first ``filled`` shaded); return (count drawn, height used)."""
    r = r if r is not None else p.dot_r
    drawn = 0
    rows = (n + per_row - 1) // per_row
    for i in range(n):
        cx = x + r + (i % per_row) * (2 * r + 6)
        cy = y - r - (i // per_row) * (2 * r + 6)
        p.box_ok(cx - r, cy - r, 2 * r, 2 * r)
        p.c.circle(cx, cy, r, stroke=1, fill=1 if i < filled else 0)
        drawn += 1
    return drawn, rows * (2 * r + 6)


def _ten_frame(p: Page, x: float, y: float, filled: int, cell: float = 18) -> int:
    p.box_ok(x, y - 2 * cell, 5 * cell, 2 * cell)
    dots = 0
    for i in range(10):
        cx, cy = x + (i % 5) * cell, y - (i // 5 + 1) * cell
        p.c.rect(cx, cy, cell, cell)
        if i < filled:
            p.c.circle(cx + cell / 2, cy + cell / 2, cell * 0.3, fill=1)
            dots += 1
    return dots


def visual_height(item: PacketItem, r: float = 6.0) -> float:
    v = item.visual_inventory
    t = v.get("type")
    if not t:
        return 0
    if t == "objects":
        return ((v["count"] + 9) // 10) * (2 * r + 6) + 6
    if t == "ten_frame":
        return 44
    if t == "two_groups":
        return max((v["a"] + 4) // 5, (v["b"] + 4) // 5) * (2 * r + 6) + 20
    if t == "base_ten":
        return 70
    if t == "number_line":
        return 40
    if t in ("bar", "bar_equal", "fraction_bar"):
        return 46
    if t == "array":
        return v["rows"] * 14 + 6
    if t == "groups":
        rows = (v["groups"] + 4) // 5
        return rows * (_group_box(v["per_group"])[1] + 10)
    if t == "share":
        return max(64, ((v["total"] + 14) // 15) * 14 + 74)
    if t == "set":
        return ((v["total"] + 9) // 10) * (2 * r + 6) + 6
    return 0


def _group_box(n: int) -> tuple[float, float]:
    per_row = 5
    rows = (n + per_row - 1) // per_row
    return per_row * 12 + 10, rows * 12 + 10


def draw_visual(p: Page, item: PacketItem, x: float, y: float) -> dict[str, Any]:
    """Draw ``item``'s visual with its top-left at (x, y). Returns counts actually drawn."""
    v = item.visual_inventory
    t = v.get("type")
    c = p.c
    c.setLineWidth(0.8)
    if t == "objects":
        n, _ = _circles(p, x, y, v["count"])
        return {"objects": n}
    if t == "ten_frame":
        dots = [_ten_frame(p, x + i * 110, y, f) for i, f in enumerate(v["filled"])]
        return {"filled": dots}
    if t == "two_groups":
        p.text(x, y - 10, "A", BOLD)
        a, _ = _circles(p, x + 16, y, v["a"], per_row=5)
        bx = x + 16 + 5 * (2 * p.dot_r + 6) + 30
        p.text(bx, y - 10, "B", BOLD)
        b, _ = _circles(p, bx + 16, y, v["b"], per_row=5)
        return {"a": a, "b": b}
    if t == "base_ten":
        cx = x
        counts = {"hundreds": 0, "tens": 0, "ones": 0}
        for _ in range(v["hundreds"]):
            p.box_ok(cx, y - 50, 50, 50)
            c.rect(cx, y - 50, 50, 50)
            for k in range(1, 10):
                c.setLineWidth(0.2)
                c.line(cx + 5 * k, y - 50, cx + 5 * k, y)
                c.line(cx, y - 50 + 5 * k, cx + 50, y - 50 + 5 * k)
            c.setLineWidth(0.8)
            cx += 56
            counts["hundreds"] += 1
        for _ in range(v["tens"]):
            p.box_ok(cx, y - 50, 6, 50)
            c.rect(cx, y - 50, 6, 50)
            cx += 10
            counts["tens"] += 1
        cx += 6
        for i in range(v["ones"]):
            p.box_ok(cx + (i % 5) * 9, y - 50, 6, 6)
            c.rect(cx + (i % 5) * 9, y - 50 + (i // 5) * 9, 6, 6)
            counts["ones"] += 1
        return counts
    if t == "number_line":
        lo, hi = v["lo"], v["hi"]
        width = W - 2 * MARGIN - 40
        span = max(1, hi - lo)
        jump = v.get("jump", 1)
        step = jump if span / jump <= 20 else jump * 2
        ly = y - 22
        p.box_ok(x, ly - 14, width, 20)
        c.line(x, ly, x + width, ly)
        ticks = 0
        for n in range(lo - lo % step, hi + 1, step):
            if n < lo:
                continue
            tx = x + (n - lo) / span * width
            c.line(tx, ly - 4, tx, ly + 4)
            p.text(tx - stringWidth(str(n), FONT, 7) / 2, ly - 13, str(n), FONT, 7)
            ticks += 1
        return {"ticks": ticks, "lo": lo, "hi": hi}
    if t in ("bar", "bar_equal", "fraction_bar"):
        width = min(360, W - 2 * MARGIN - 40)
        by = y - 30
        p.box_ok(x, by, width, 30)
        if t == "bar":
            label = "?" if v["total"] is None else str(v["total"])
            p.text(x + width / 2 - stringWidth(label, BOLD, 11) / 2, y - 10, label, BOLD, 11)
            c.line(x, y - 14, x + width, y - 14)
            parts = v["parts"]
            known = sum(q for q in parts if q is not None)
            fracs = [(q if q is not None else v["true_total"] - known) / v["true_total"] for q in parts]
            cx = x
            for q, fr in zip(parts, fracs):
                pw = width * fr
                c.rect(cx, by - 4, pw, 18)
                s = "?" if q is None else str(q)
                p.text(cx + pw / 2 - stringWidth(s, FONT, 10) / 2, by + 1, s, FONT, 10)
                cx += pw
            return {"parts": len(parts), "labels": [q for q in parts]}
        n = v["parts"]
        shaded = v.get("shaded", 0)
        if t == "bar_equal":
            s = str(v["total"])
            p.text(x + width / 2 - stringWidth(s, BOLD, 11) / 2, y - 10, s, BOLD, 11)
            c.line(x, y - 14, x + width, y - 14)
        for i in range(n):
            c.setFillGray(0.7)
            c.rect(x + i * width / n, by - 4, width / n, 18, fill=1 if i < shaded else 0)
            c.setFillGray(0)
        return {"parts": n, "shaded": min(shaded, n)}
    if t == "array":
        n, _ = 0, 0
        for r in range(v["rows"]):
            for k in range(v["cols"]):
                cx, cy = x + 6 + k * 14, y - 6 - r * 14
                p.box_ok(cx - 4, cy - 4, 8, 8)
                c.circle(cx, cy, 4, fill=1)
                n += 1
        return {"dots": n, "rows": v["rows"], "cols": v["cols"]}
    if t == "groups":
        bw, bh = _group_box(v["per_group"])
        dots = 0
        boxes = 0
        for gi in range(v["groups"]):
            gx = x + (gi % 5) * (bw + 10)
            gy = y - (gi // 5) * (bh + 10)
            p.box_ok(gx, gy - bh, bw, bh)
            c.roundRect(gx, gy - bh, bw, bh, 6)
            boxes += 1
            for k in range(v["per_group"]):
                c.circle(gx + 11 + (k % 5) * 12, gy - 11 - (k // 5) * 12, 3.5, fill=1)
                dots += 1
        return {"groups": boxes, "dots": dots}
    if t == "share":
        dots, _ = _circles(p, x, y, v["total"], per_row=15, r=4)
        top = y - ((v["total"] + 14) // 15) * 14 - 8
        rings = 0
        for gi in range(v["groups"]):
            p.box_ok(x + gi * 62, top - 56, 54, 54)
            c.circle(x + gi * 62 + 27, top - 29, 27)
            rings += 1
        return {"dots": dots, "rings": rings}
    if t == "set":
        n, _ = _circles(p, x, y, v["total"], filled=v["shaded"])
        return {"total": n, "shaded": min(v["shaded"], n)}
    return {}


def visual_description(item: PacketItem) -> str:
    """One-line description of the child-page picture, for the parent key."""
    v = item.visual_inventory
    t = v.get("type")
    if t == "objects":
        return f"picture: {v['count']} circles"
    if t == "ten_frame":
        return "picture: ten frame(s) with " + " and ".join(str(f) for f in v["filled"]) + " dots"
    if t == "two_groups":
        return f"picture: group A {v['a']}, group B {v['b']}"
    if t == "base_ten":
        return f"picture: {v['hundreds']} hundreds, {v['tens']} tens, {v['ones']} ones"
    if t == "array":
        return f"picture: {v['rows']} rows of {v['cols']} dots"
    if t == "groups":
        return f"picture: {v['groups']} groups of {v['per_group']} dots"
    if t == "share":
        return f"picture: {v['total']} dots, {v['groups']} empty circles"
    if t == "bar":
        return "picture: bar model " + " + ".join("?" if q is None else str(q) for q in v["parts"]) +             f" = {'?' if v['total'] is None else v['total']}"
    if t == "bar_equal":
        return f"picture: bar of {v['total']} in {v['parts']} equal parts"
    if t == "fraction_bar":
        return f"picture: bar in {v['parts']} parts, {v['shaded']} shaded"
    if t == "set":
        return f"picture: {v['total']} circles, {v['shaded']} shaded"
    if t == "number_line":
        return f"picture: number line {v['lo']}-{v['hi']}"
    return ""


def check_drawn(items: list[PacketItem], drawn: dict[str, dict]) -> list[str]:
    """Compare what the renderer actually drew with each item's inventory."""
    errs = []
    for it in items:
        v, d = it.visual_inventory, drawn.get(it.id, {})
        t = v.get("type")
        exp: dict[str, Any] = {}
        if t == "objects":
            exp = {"objects": v["count"]}
        elif t == "ten_frame":
            exp = {"filled": v["filled"]}
        elif t == "two_groups":
            exp = {"a": v["a"], "b": v["b"]}
        elif t == "base_ten":
            exp = {k: v[k] for k in ("hundreds", "tens", "ones")}
        elif t == "array":
            exp = {"dots": v["rows"] * v["cols"]}
        elif t == "groups":
            exp = {"groups": v["groups"], "dots": v["groups"] * v["per_group"]}
        elif t == "share":
            exp = {"dots": v["total"], "rings": v["groups"]}
        elif t in ("bar_equal", "fraction_bar"):
            exp = {"parts": v["parts"]}
        elif t == "bar":
            exp = {"parts": len(v["parts"])}
        elif t == "set":
            exp = {"total": v["total"], "shaded": v["shaded"]}
        elif t == "number_line":
            exp = {"lo": v["lo"], "hi": v["hi"]}
        for k, val in exp.items():
            if d.get(k) != val:
                errs.append(f"item {it.id} ({it.format}): drew {k}={d.get(k)!r}, expected {val!r}")
    return errs


# -- documents -----------------------------------------------------------------------------------
def _child_size(grade: str) -> float:
    return 15 if grade in ("PK", "K", "1") else 13 if grade in ("2", "3") else 12


def child_pdf(path: Path, plan: "ChildPlan", date: str) -> dict[str, dict]:
    child = plan.child
    size = _child_size(child.grade)
    p = Page(path, f"{child.name}'s practice", f"{date}  ·  Name: ____________", size)
    drawn: dict[str, dict] = {}
    if child.reading_support:
        p.text(MARGIN, p.y, "Grown-up: please read each direction aloud.", FONT, 10, GREY)
        p.y -= 22
    width = W - 2 * MARGIN - 28
    for it in plan.items:
        label = f"{it.id}." if not it.optional else f"{it.id}. (optional challenge)"
        lines = wrap(it.prompt, FONT, size, width)
        hint_lines = wrap(f"Hint: {it.hint}", FONT, size - 3, width) if it.hint else []
        vh = visual_height(it, p.dot_r)
        disp_h = (size + 8) if it.display and it.spec.get("kind") != "select" else len(it.display) * (size + 6)
        work_h = it.work_lines * (size + 12) + 2 * size + 16
        block = (len(lines) * (size + 4) + len(hint_lines) * (size + 1) + (vh + 10 if vh else 0)
                 + disp_h + work_h + 18)
        p.need(block)
        lx = MARGIN
        p.text(lx, p.y - size, label if not it.optional else f"{it.id}.", BOLD, size)
        if it.optional:
            p.text(lx + 28, p.y - size + 1, "Optional challenge", FONT, size - 4, GREY)
            p.y -= size + 4
        tx = MARGIN + 28
        for ln in lines:
            p.text(tx, p.y - size, ln, FONT, size)
            p.y -= size + 4
        for ln in hint_lines:
            p.text(tx, p.y - (size - 3), ln, "Helvetica-Oblique", size - 3, GREY)
            p.y -= size + 1
        if vh:
            p.y -= 4
            drawn[it.id] = draw_visual(p, it, tx, p.y)
            p.y -= vh + 6
        if it.display:
            if it.spec.get("kind") == "select":
                for d in it.display:
                    p.text(tx + 10, p.y - size, d, FONT, size)
                    p.y -= size + 6
            else:
                p.text(tx, p.y - size, "Circle one:", FONT, size - 2, GREY)
                cx = tx + stringWidth("Circle one:", FONT, size - 2) + 20
                for d in it.display:
                    p.text(cx, p.y - size, d, BOLD, size)
                    cx += stringWidth(d, BOLD, size) + 50
                p.y -= size + 8
        if not it.display and "___" not in it.prompt and it.format != "shade_fraction":
            p.y -= 6
            lab = "Answer:"
            p.text(tx, p.y - size, lab, BOLD, size)
            bx = tx + stringWidth(lab, BOLD, size) + 8
            bw = 150 if len(it.answer) <= 6 else 300
            p.box_ok(bx, p.y - size - 6, bw, size + 10)
            p.c.setStrokeGray(0.4)
            p.c.rect(bx, p.y - size - 6, bw, size + 10)
            p.c.setStrokeGray(0)
            p.y -= size + 10
        if "word_problem" in it.format:
            bh = it.work_lines * (size + 12)
            p.y -= 6
            p.box_ok(tx, p.y - bh, W - MARGIN - tx, bh)
            p.c.setStrokeGray(0.75)
            p.c.rect(tx, p.y - bh, W - MARGIN - tx, bh)
            p.c.setStrokeGray(0)
            p.text(tx + 4, p.y - 11, "Draw or write your thinking:", FONT, 8, GREY)
            p.y -= bh + 12
            continue
        for _ in range(it.work_lines):
            p.y -= size + 12
            p.c.setStrokeGray(0.75)
            p.c.setLineWidth(0.5)
            p.c.line(tx, p.y, W - MARGIN, p.y)
            p.c.setStrokeGray(0)
        p.y -= 18
    p.save()
    return drawn


def key_pdf(path: Path, plans: list["ChildPlan"], date: str) -> None:
    p = Page(path, "Parent answer key", date, 10.5)
    box_col = W - MARGIN - 96  # left edge of the I/S/N column
    width = box_col - (MARGIN + 30) - 12  # text column ends 12pt before the boxes
    p.text(MARGIN, p.y, "After practice, tick I (did it alone), S (needed help) or N (not yet) for each item.",
           FONT, 10)
    p.y -= 15
    first = plans[0].child.id if plans else "child"
    p.text(MARGIN, p.y, f"Then reply, for example:  {first} 1=I 2=S 3=N S1=I   (or /homework feedback ...)", FONT, 10)
    p.y -= 26
    for plan in plans:
        p.need(60)
        p.text(MARGIN, p.y - 13, f"{plan.child.name} (grade {plan.child.grade})", BOLD, 13)
        p.y -= 30
        for it in plan.items:
            desc = visual_description(it)
            prompt = wrap(it.prompt + (f"  [{desc}]" if desc else ""), FONT, 9, width)
            ans = wrap(f"Answer: {it.answer}", BOLD, 10.5, width)
            work = wrap(it.worked_solution, FONT, 9.5, width)
            tip = wrap(f"If stuck: {it.parent_tip}", FONT, 8.5, width) if it.parent_tip else []
            h = len(prompt) * 12 + len(ans) * 14 + len(work) * 12 + len(tip) * 11 + 14
            p.need(h)
            top = p.y
            p.text(MARGIN, p.y - 10.5, f"{it.id}.", BOLD, 10.5)
            for ln in prompt:
                p.text(MARGIN + 30, p.y - 9, ln, FONT, 9, 0.3)
                p.y -= 12
            for ln in ans:
                p.text(MARGIN + 30, p.y - 10.5, ln, BOLD, 10.5)
                p.y -= 14
            for ln in work:
                p.text(MARGIN + 30, p.y - 9.5, ln, FONT, 9.5)
                p.y -= 12
            for ln in tip:
                p.text(MARGIN + 30, p.y - 8.5, ln, FONT, 8.5, 0.35)
                p.y -= 11
            bx = box_col
            for k, letter_ in enumerate("ISN"):
                cx = bx + k * 32
                p.box_ok(cx, top - 16, 15, 15)
                p.c.rect(cx, top - 16, 15, 15)
                p.text(cx + 7.5 - stringWidth(letter_, BOLD, 9) / 2, top - 27, letter_, BOLD, 9)
            p.y -= 14
        p.y -= 10
    p.save()
