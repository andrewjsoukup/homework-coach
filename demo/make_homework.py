# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10.1"]
# ///
"""Generate the fictional demo homework pages + ground-truth observations.

    uv run demo/make_homework.py            # writes demo/homework/*.png and *.truth.json

Everything here is synthetic: the "handwriting" is a tiny single-stroke vector
font defined below and jittered with a seeded RNG — no real child's writing, no
OS fonts (printed text uses Pillow's bundled default font). Output is
deterministic for a given Pillow version.

Each page has a ``<name>.truth.json`` in the plugin's ``Observation`` shape
(``homework_coach/models.py``). Expected answers are computed in code, never
typed by hand, so the fixtures obey the plugin's own "validate arithmetic in
code" rule. Tests and the demo runner use these as the fake-vision response.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "homework"
W, H = 1275, 1650  # US Letter @ 150 dpi
PAPER = (252, 251, 247)
INK = (25, 25, 30)
PENCIL = (78, 80, 92)
RED = (200, 40, 40)
BLUE = (60, 110, 190)

# ---------------------------------------------------------------------------------------
# Single-stroke "handwriting" font. Glyph box: x 0..adv, y 0 (cap top) .. 1 (baseline).
# Strokes starting with "L" are straight polylines; others are Catmull-Rom smoothed.
# ---------------------------------------------------------------------------------------


def _ell(cx, cy, rx, ry, a0=0.0, a1=360.0, n=28):
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]


GLYPHS: dict[str, tuple[float, list]] = {
    "0": (0.7, [["L", *_ell(0.35, 0.5, 0.3, 0.5, -90, 275)]]),
    "1": (0.45, [["L", (0.08, 0.22), (0.3, 0.0), (0.3, 1.0)]]),
    "2": (0.7, [[(0.06, 0.25), (0.28, 0.02), (0.55, 0.02), (0.66, 0.25), (0.55, 0.5), (0.05, 1.0)],
                ["L", (0.05, 1.0), (0.7, 0.98)]]),
    "3": (0.7, [[(0.06, 0.1), (0.38, 0.0), (0.64, 0.2), (0.34, 0.47)],
                [(0.34, 0.47), (0.66, 0.7), (0.4, 1.0), (0.05, 0.9)]]),
    "4": (0.75, [["L", (0.55, 1.0), (0.55, 0.0), (0.03, 0.66), (0.75, 0.66)]]),
    "5": (0.7, [["L", (0.66, 0.0), (0.16, 0.0), (0.12, 0.45)],
                [(0.12, 0.45), (0.45, 0.38), (0.68, 0.62), (0.58, 0.92), (0.3, 1.0), (0.04, 0.9)]]),
    "6": (0.7, [[(0.62, 0.04), (0.3, 0.12), (0.08, 0.55), (0.12, 0.88), (0.38, 1.0),
                 (0.64, 0.82), (0.6, 0.56), (0.34, 0.5), (0.1, 0.66)]]),
    "7": (0.7, [["L", (0.04, 0.0), (0.68, 0.0), (0.28, 1.0)]]),
    "8": (0.7, [["L", *_ell(0.35, 0.25, 0.24, 0.25, 90, 450)], ["L", *_ell(0.35, 0.74, 0.3, 0.26, -90, 270)]]),
    "9": (0.7, [["L", *_ell(0.35, 0.3, 0.28, 0.29, 0, 365)], [(0.63, 0.3), (0.6, 0.7), (0.52, 1.0)]]),
    "+": (0.7, [["L", (0.08, 0.55), (0.62, 0.55)], ["L", (0.35, 0.28), (0.35, 0.82)]]),
    "-": (0.6, [["L", (0.08, 0.58), (0.52, 0.58)]]),
    "=": (0.7, [["L", (0.08, 0.44), (0.62, 0.44)], ["L", (0.08, 0.7), (0.62, 0.7)]]),
    "x": (0.65, [["L", (0.08, 0.42), (0.56, 0.95)], ["L", (0.56, 0.42), (0.08, 0.95)]]),
    "/": (0.5, [["L", (0.45, 0.0), (0.05, 1.0)]]),
    " ": (0.4, []),
    "N": (0.85, [["L", (0.08, 1.0), (0.08, 0.0), (0.74, 1.0), (0.74, 0.0)]]),
    "P": (0.75, [["L", (0.1, 1.0), (0.1, 0.0)], [(0.1, 0.0), (0.5, 0.02), (0.68, 0.22), (0.5, 0.45), (0.1, 0.46)]]),
    "o": (0.7, [["L", *_ell(0.34, 0.76, 0.27, 0.24, -90, 275)]]),
    "v": (0.7, [["L", (0.04, 0.5), (0.34, 1.0), (0.64, 0.5)]]),
    "a": (0.72, [["L", *_ell(0.33, 0.76, 0.26, 0.24, -20, 330)], ["L", (0.62, 0.5), (0.64, 1.0)]]),
    "i": (0.35, [["L", (0.16, 0.52), (0.16, 1.0)], ["L", (0.16, 0.3), (0.17, 0.33)]]),
    "p": (0.72, [["L", (0.1, 0.5), (0.1, 1.38)], ["L", *_ell(0.38, 0.75, 0.28, 0.25, 180, 535)]]),
    "s": (0.65, [[(0.58, 0.54), (0.32, 0.48), (0.1, 0.6), (0.32, 0.74), (0.58, 0.86), (0.42, 1.0), (0.06, 0.95)]]),
    "k": (0.65, [["L", (0.1, 0.0), (0.1, 1.0)], ["L", (0.56, 0.5), (0.12, 0.76), (0.6, 1.0)]]),
}


def _catmull(pts, steps=8):
    if len(pts) < 3:
        return pts
    p = [pts[0], *pts, pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    out.append(pts[-1])
    return out


class Hand:
    """Seeded jittery pencil writer."""

    def __init__(self, draw: ImageDraw.ImageDraw, seed: str, color=PENCIL, width=4):
        self.d, self.rng, self.color, self.width = draw, random.Random(seed), color, width

    def _j(self, a):
        return self.rng.uniform(-a, a)

    def write(self, text: str, x: float, y: float, h: float, *, mirror: set[int] | None = None,
              color=None, slant=0.12) -> float:
        """Write ``text`` with cap-top at (x, y), cap height ``h``. Returns end x."""
        mirror = mirror or set()
        for idx, ch in enumerate(text):
            adv, strokes = GLYPHS[ch]
            gx, gy, gs = x + self._j(h * 0.04), y + self._j(h * 0.06), h * (1 + self._j(0.07))
            rot = math.radians(self._j(5))
            for st in strokes:
                straight = st and st[0] == "L"
                pts = list(st[1:] if straight else st)
                if idx in mirror:
                    pts = [(adv - px, py) for px, py in pts]
                pts = [(px + self._j(0.025), py + self._j(0.025)) for px, py in pts]
                if not straight:
                    pts = _catmull(pts)
                out = []
                for px, py in pts:
                    px -= slant * (py - 1)  # forward lean
                    rx, ry = px * math.cos(rot) - py * math.sin(rot), px * math.sin(rot) + py * math.cos(rot)
                    out.append((gx + rx * gs, gy + ry * gs))
                if len(out) == 1:
                    out.append((out[0][0] + 1, out[0][1] + 1))
                self.d.line(out, fill=color or self.color, width=self.width, joint="curve")
            x += adv * h * (1 + self._j(0.06)) + h * 0.12
        return x

    def check(self, x, y, s=40, color=RED):
        pts = [(x, y + s * 0.55), (x + s * 0.35, y + s), (x + s * 1.1, y - s * 0.1)]
        pts = [(px + self._j(3), py + self._j(3)) for px, py in pts]
        self.d.line(_catmull(pts, 5), fill=color, width=5, joint="curve")

    def circle(self, box, color=None, width=None):
        x0, y0, x1, y1 = box
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        start = self.rng.uniform(0, 360)
        pts = [(cx + (rx + self._j(4)) * math.cos(math.radians(a)), cy + (ry + self._j(4)) * math.sin(math.radians(a)))
               for a in (start + i * 12 for i in range(33))]
        self.d.line(pts, fill=color or self.color, width=width or self.width, joint="curve")

    def strike(self, a, b, color=RED):
        self.d.line([(a[0] + self._j(3), a[1] + self._j(3)), (b[0] + self._j(3), b[1] + self._j(3))],
                    fill=color, width=5)

    def dots(self, cx, cy, n, r=9):
        for i in range(n):
            ang = 2 * math.pi * i / max(n, 1) + self._j(0.3)
            rr = 0 if n == 1 else r * 2.2
            px, py = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
            self.d.ellipse([px - r / 2, py - r / 2, px + r / 2, py + r / 2], fill=self.color)


# ---------------------------------------------------------------------------------------
# Printed worksheet helpers
# ---------------------------------------------------------------------------------------


def font(size: int):
    return ImageFont.load_default(size=size)


def header(d: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    d.rectangle([60, 50, W - 60, 190], outline=BLUE, width=3)
    d.text((85, 66), title, font=font(40), fill=INK)
    d.text((85, 120), subtitle, font=font(24), fill=(80, 80, 90))
    d.text((W - 470, 70), "Name ____________", font=font(26), fill=INK)
    d.text((W - 470, 128), "Date ____________", font=font(26), fill=INK)


def text(d, xy, s, size=24, fill=INK):
    d.text(xy, s, font=font(size), fill=fill)
    return d.textlength(s, font=font(size))


def blanks(d, x, y, template: str, size=26, blank_w=70) -> list[tuple[float, float]]:
    """Print ``template`` with ``{}`` as underlined blanks; return blank (x0, y_top) positions."""
    out, parts = [], template.split("{}")
    for i, part in enumerate(parts):
        x += text(d, (x, y), part, size)
        if i < len(parts) - 1:
            d.line([(x + 4, y + size + 4), (x + blank_w - 4, y + size + 4)], fill=INK, width=2)
            out.append((x + 10, y - 8))
            x += blank_w
    return out


def dot_array(d, x, y, rows, cols, gap=30, r=9):
    for rr in range(rows):
        for cc in range(cols):
            cx, cy = x + cc * gap, y + rr * gap
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)


def picture(d, kind: str, cx, cy, s=22):
    if kind == "apple":
        d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=(210, 60, 50), outline=INK, width=2)
        d.line([(cx, cy - s), (cx + 4, cy - s - 10)], fill=(90, 60, 30), width=4)
    elif kind == "star":
        pts = [(cx + (s if i % 2 == 0 else s * 0.45) * math.sin(math.pi * i / 5),
                cy - (s if i % 2 == 0 else s * 0.45) * math.cos(math.pi * i / 5)) for i in range(10)]
        d.polygon(pts, fill=(240, 190, 40), outline=INK)
    elif kind == "ball":
        d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=(70, 140, 220), outline=INK, width=2)
        d.arc([cx - s, cy - s * 0.4, cx + s, cy + s * 0.4], 0, 180, fill=PAPER, width=3)
    elif kind == "fish":
        d.ellipse([cx - s, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6], fill=(250, 150, 60), outline=INK, width=2)
        d.polygon([(cx + s * 0.5, cy), (cx + s * 1.1, cy - s * 0.6), (cx + s * 1.1, cy + s * 0.6)],
                  fill=(250, 150, 60), outline=INK)
    elif kind == "heart":
        d.ellipse([cx - s, cy - s * 0.8, cx, cy + s * 0.2], fill=(230, 80, 130))
        d.ellipse([cx, cy - s * 0.8, cx + s, cy + s * 0.2], fill=(230, 80, 130))
        d.polygon([(cx - s, cy - s * 0.25), (cx + s, cy - s * 0.25), (cx, cy + s)], fill=(230, 80, 130))
    elif kind == "sun":
        for i in range(8):
            a = math.pi * i / 4
            d.line([(cx + s * 0.8 * math.cos(a), cy + s * 0.8 * math.sin(a)),
                    (cx + s * 1.25 * math.cos(a), cy + s * 1.25 * math.sin(a))], fill=(230, 160, 20), width=3)
        d.ellipse([cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7], fill=(250, 200, 40), outline=INK)
    elif kind == "counter":
        d.ellipse([cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6], fill=(120, 190, 110), outline=INK, width=2)


def scatter(d, kind, n, box, seed, s=22):
    """Place ``n`` pictures in ``box`` on a jittered grid (no overlaps)."""
    rng = random.Random(seed)
    x0, y0, x1, y1 = box
    cols = math.ceil(math.sqrt(n * (x1 - x0) / (y1 - y0)))
    rows = math.ceil(n / cols)
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    cells = [(c, r) for r in range(rows) for c in range(cols)]
    rng.shuffle(cells)
    for c, r in sorted(cells[:n], key=lambda t: (t[1], t[0])):
        picture(d, kind, x0 + cw * (c + 0.5) + rng.uniform(-cw * 0.15, cw * 0.15),
                y0 + ch * (r + 0.5) + rng.uniform(-ch * 0.15, ch * 0.15), s)


def new_page():
    img = Image.new("RGB", (W, H), PAPER)
    return img, ImageDraw.Draw(img)


def finish(img: Image.Image, name: str, truth: dict) -> None:
    # tiny tilt so it reads as a phone photo of a sheet, while staying clean
    img = img.rotate(-0.6, resample=Image.BICUBIC, expand=False, fillcolor=(236, 234, 228))
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png", optimize=True)
    truth["source"] = f"{name}.png"
    (OUT / f"{name}.truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")


def item(prompt, child_answer, status, skill, fmt, expected=None, note="", confidence=1.0):
    return {"prompt": prompt, "child_answer": child_answer, "status": status, "skill": skill, "format": fmt,
            "expected_answer": None if expected is None else str(expected), "confidence": confidence, "note": note}


def observation(date, child_id, lesson, items, notes):
    return {"date": date, "child_id": child_id, "source": "", "items": items,
            "skills": sorted({i["skill"] for i in items if i["status"] != "not_assigned"}),
            "formats": sorted({i["format"] for i in items if i["status"] != "not_assigned"}),
            "lesson": lesson, "notes": notes, "schema_version": 1}


# ---------------------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------------------
ARR, FACT = "mult.arrays_equal_groups", "mult.repeated_addition"
SHARE = "div.equal_sharing"
COUNT, NUMERAL, COMPARE = "count.objects_to_10", "numeral.write_0_10", "compare.more_fewer"


def nova_arrays():
    """Grade 3, Mon 2026-09-14 — arrays -> multiplication equations."""
    img, d = new_page()
    hand, teacher = Hand(d, "nova-0914"), Hand(d, "teacher-0914", color=RED)
    header(d, "Lesson 3-2  Arrays and Multiplication", "Write how many rows, how many in each row, and the total.")
    hand.write("Nova", W - 360, 58, 34)
    hand.write("9/14", W - 380, 116, 34)
    items = []
    cells = [(80 + c * 390, 230 + r * 440) for r in range(3) for c in range(3)]

    def cell(n, prompt):
        x, y = cells[n - 1]
        text(d, (x, y), f"{n}.", 30)
        if prompt:
            text(d, (x + 40, y + 4), prompt, 22)
        return x, y

    # 1-3, 6: read an array -> rows, columns, total
    for n, (r, c, written) in {1: (3, 4, r"{}"), 2: (2, 5, r"{}"), 3: (4, 6, "26"), 6: (6, 4, r"{}")}.items():
        x, y = cell(n, "")
        dot_array(d, x + 70, y + 60, r, c)
        bl = blanks(d, x + 10, y + 270, "{} rows of {} = {}", 24, 62)
        total = written if written != "{}" else str(r * c)
        for (bx, by), val in zip(bl, (str(r), str(c), total)):
            hand.write(val, bx, by, 30)
        status = "correct" if total == str(r * c) else "slip"
        note = "" if status == "correct" else "4x6 written as 26; the same fact (6x4=24) is correct in item 6, so likely a slip."
        items.append(item(f"{n}. Array with {r} rows of {c}: rows, number in each row, total",
                          f"{r} rows of {c} = {total}", status, ARR, "array -> rows/cols/total", r * c, note))
        if status == "correct":
            teacher.check(x + 300, y + 230)
    # 4: draw an array
    x, y = cell(4, "Draw an array for 3 x 5.")
    for rr in range(3):
        for cc in range(5):
            hand.dots(x + 80 + cc * 34, y + 80 + rr * 34, 1, r=14)
    bl = blanks(d, x + 10, y + 270, "3 x 5 = {}", 24)
    hand.write("15", *bl[0], 30)
    teacher.check(x + 300, y + 230)
    items.append(item("4. Draw an array for 3 x 5 and find the total", "drew 3 rows of 5; 15", "correct", ARR,
                      "equation -> draw array", 15))
    # 5: repeated addition -> multiplication
    x, y = cell(5, "5 + 5 = ___ so 2 x 5 = ___")
    hand.write("10", x + 100, y + 120, 34)
    hand.write("2x5=10", x + 60, y + 200, 34)
    teacher.check(x + 300, y + 230)
    items.append(item("5. 5 + 5 = ___ so 2 x 5 = ___", "10; 2x5=10", "correct", FACT,
                      "repeated addition -> equation", 10))
    # 7: checking target — wrong intermediate, right final
    x, y = cell(7, "4 groups of 3. Write an addition")
    text(d, (x + 40, y + 32), "and a multiplication equation.", 22)
    hand.write("3+3+3+3=13", x + 20, y + 110, 30)
    hand.write("4x3=12", x + 20, y + 200, 34)
    items.append(item("7. 4 groups of 3: write an addition and a multiplication equation", "3+3+3+3=13; 4x3=12",
                      "checking_target", FACT, "equal groups -> addition + equation", 12,
                      "Final equation correct but the addition line says 13; good item to re-check sums."))
    # 8: not assigned — teacher strike + "skip"
    x, y = cell(8, "Draw 2 arrays that show 12.")
    teacher.strike((x + 10, y + 10), (x + 330, y + 330))
    teacher.write("skip", x + 200, y + 260, 36, color=RED)
    items.append(item("8. Draw 2 arrays that show 12", None, "not_assigned", ARR, "total -> two arrays", None,
                      "Teacher crossed out and wrote 'skip'."))
    # 9: challenge left blank — unattempted, not wrong
    x, y = cell(9, "Challenge: 7 x 4 = ___")
    items.append(item("9. Challenge: 7 x 4 = ___", None, "unattempted", FACT, "bare fact", 28, "Left blank."))
    finish(img, "nova_2026-09-14_arrays", observation(
        "2026-09-14", "nova", "Lesson 3-2 Arrays and Multiplication", items,
        "Reads arrays reliably; one likely slip (4x6) and one addition line to re-check."))


def nova_sharing():
    """Grade 3, Wed 2026-09-16 — new classroom topic: division as equal sharing."""
    img, d = new_page()
    hand, teacher = Hand(d, "nova-0916"), Hand(d, "teacher-0916", color=RED)
    header(d, "Lesson 4-1  Division as Sharing", "Share equally. Write the division equation.")
    hand.write("Nova", W - 360, 58, 34)
    hand.write("9/16", W - 380, 116, 34)
    items = []
    rows = [(80, 230 + i * 170) for i in range(8)]
    # 1: draw-to-share
    x, y = rows[0]
    text(d, (x, y), "1.  Share 12 counters into 3 equal groups. How many in each group?", 26)
    for g in range(3):
        hand.circle((x + 120 + g * 190, y + 50, x + 280 + g * 190, y + 150))
        hand.dots(x + 200 + g * 190, y + 100, 4, r=12)
    hand.write("4", x + 760, y + 70, 48)
    teacher.check(x + 860, y + 80)
    items.append(item("1. Share 12 counters into 3 equal groups", "drew 3 groups of 4; 4", "correct", SHARE,
                      "draw groups -> quotient", 12 // 3))
    facts = [(2, 10, 2, None), (3, 15, 3, None), (4, 18, 3, None), (5, 20, 4, "16")]
    for n, a, b, wrong in facts:
        x, y = rows[n - 1]
        bl = blanks(d, x, y + 10, f"{n}.   {a} / {b} = {{}}", 34, 90)
        val = wrong or str(a // b)
        hand.write(val, bl[0][0], bl[0][1] + 4, 42)
        if wrong is None:
            teacher.check(x + 420, y + 10)
            items.append(item(f"{n}. {a} / {b} = ___", val, "correct", SHARE, "bare division fact", a // b))
        else:
            teacher.d.text((x + 420, y + 10), "?", font=font(48), fill=RED)
            items.append(item(f"{n}. {a} / {b} = ___", val, "incorrect", SHARE, "bare division fact", a // b,
                              "Wrote 16 = 20 - 4: subtracted once instead of sharing. Other facts are right."))
    x, y = rows[5]
    text(d, (x, y), "6.  Write a multiplication fact that helps you solve 12 / 3.", 26)
    hand.write("3x4=12", x + 80, y + 60, 44)
    teacher.check(x + 420, y + 70)
    items.append(item("6. Write a multiplication fact that helps solve 12 / 3", "3x4=12", "correct", SHARE,
                      "division -> related multiplication", "3x4=12"))
    x, y = rows[6]
    text(d, (x, y), "7.  16 stickers are shared equally by 4 friends. How many does each get?", 26)
    hand.write("4", x + 80, y + 60, 48)
    teacher.check(x + 160, y + 70)
    items.append(item("7. 16 stickers shared equally by 4 friends", "4", "correct", SHARE, "sharing story -> quotient",
                      16 // 4))
    x, y = rows[7]
    text(d, (x, y), "8.  Show 8 / 2 another way.", 26)
    hand.write("8x1/2=4", x + 80, y + 60, 44)
    items.append(item("8. Show 8 / 2 another way", "8 x 1/2 = 4", "beyond_grade", SHARE, "division -> another way",
                      8 // 2, "True (multiplying by one half) but beyond grade 3; not an error."))
    finish(img, "nova_2026-09-16_sharing", observation(
        "2026-09-16", "nova", "Lesson 4-1 Division as Sharing", items,
        "New topic. Sharing pictures and facts mostly right; one subtraction-instead-of-division miss."))


def pip_counting():
    """Kindergarten, Mon 2026-09-14 — count objects to 10, write the numeral."""
    img, d = new_page()
    hand, teacher = Hand(d, "pip-0914", width=6), Hand(d, "teacher-pip-0914", color=RED)
    header(d, "Count and Write", "Count the pictures. Write the number in the box.")
    hand.write("Pip", W - 350, 54, 40)
    boxes = [("apple", 5, "5", set()), ("star", 7, "7", set()), ("ball", 3, "3", {0}),
             ("fish", 9, "8", set()), ("heart", 6, "6", set()), ("sun", 8, "8", set())]
    items = []
    for n, (kind, count, written, mirror) in enumerate(boxes, 1):
        col, row = (n - 1) % 2, (n - 1) // 2
        x, y = 80 + col * 570, 240 + row * 440
        d.rounded_rectangle([x, y, x + 540, y + 400], 18, outline=INK, width=3)
        text(d, (x + 16, y + 10), f"{n}.", 30)
        scatter(d, kind, count, (x + 30, y + 60, x + 360, y + 380), f"{kind}{count}")
        d.rectangle([x + 390, y + 140, x + 510, y + 280], outline=INK, width=3)
        hand.write(written, x + 420, y + 165, 90, mirror=mirror, slant=0.05)
        expected = str(count)
        if written == expected:
            status, note = "correct", "Numeral 3 written backwards (reversal is common in K); count is right." if mirror else ""
            teacher.check(x + 470, y + 320, 36)
        else:
            status, note = "incorrect", "Wrote 8 for 9 fish; possibly skipped one when pictures are scattered."
        items.append(item(f"{n}. Count the {kind}s and write the number", written, status,
                          COUNT, "scattered pictures -> write numeral", count, note))
    # tracing strip (printed dotted numerals, child traced) — practice, not scored
    text(d, (80, 1570), "Trace:  1  2  3  4  5", 34, fill=(170, 170, 170))
    items.append(item("Trace 1-5", "traced", "not_assigned", NUMERAL, "trace numerals", None,
                      "Tracing warm-up; not scored."))
    finish(img, "pip_2026-09-14_counting", observation(
        "2026-09-14", "pip", "Count and Write (to 10)", items,
        "Counts small groups well; miscounted the largest scattered group; one reversed 3."))


def pip_compare():
    """Kindergarten, Wed 2026-09-16 — new topic: compare groups (more / fewer)."""
    img, d = new_page()
    hand = Hand(d, "pip-0916", width=6)
    header(d, "More or Fewer?", "Circle the group that has MORE.")
    hand.write("Pip", W - 350, 54, 40)
    pairs = [("apple", 4, 6, "right"), ("star", 7, 3, "left"), ("ball", 5, 5, "left"),
             ("fish", 2, 8, "right"), ("heart", 9, 6, None)]
    items = []
    for n, (kind, a, b, circled) in enumerate(pairs, 1):
        y = 230 + (n - 1) * 270
        text(d, (80, y + 100), f"{n}.", 34)
        left, right = (160, y + 10, 600, y + 240), (700, y + 10, 1140, y + 240)
        for box, cnt, tag in ((left, a, "L"), (right, b, "R")):
            d.rounded_rectangle(box, 14, outline=(170, 170, 170), width=2)
            scatter(d, kind, cnt, (box[0] + 20, box[1] + 20, box[2] - 20, box[3] - 20), f"{kind}{cnt}{tag}{n}", 20)
        if circled:
            b0 = left if circled == "left" else right
            hand.circle((b0[0] - 12, b0[1] - 12, b0[2] + 12, b0[3] + 12))
        if a == b:
            expected, status = "same", ("incorrect" if circled else "unattempted")
            note = "Groups are equal; circled one. Introduce 'same' language."
        else:
            expected = "left" if a > b else "right"
            status = "unattempted" if circled is None else ("correct" if circled == expected else "incorrect")
            note = "Left blank." if circled is None else ""
        items.append(item(f"{n}. {a} {kind}s vs {b} {kind}s: circle the group with more", circled, status,
                          COMPARE, "two pictured groups -> circle more", expected, note))
    finish(img, "pip_2026-09-16_compare", observation(
        "2026-09-16", "pip", "More or Fewer?", items,
        "New topic. Compares clearly unequal groups; equal groups not yet understood as 'same'."))


PAGES = (nova_arrays, pip_counting, nova_sharing, pip_compare)


def main() -> None:
    for page in PAGES:
        page()
        print("wrote", page.__name__)


if __name__ == "__main__":
    main()
