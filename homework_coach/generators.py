"""Deterministic item generators, one per task format (SPEC §9.2).

Every generator returns a :class:`~homework_coach.models.PacketItem` whose
``spec`` lets :mod:`verify` recompute the answer independently and whose
``visual_inventory`` describes exactly what the renderer must draw. Difficulty
comes from the child's :class:`SkillState` dims:

- ``number_range`` → operand size
- ``representation`` → low levels favour drawn formats (chosen in ``packet``)
- ``scaffold`` → level 1-2 show a hint line on the child page; 3+ do not
- ``steps`` → level 3+ adds a second step / "explain" line to story problems
"""
from __future__ import annotations

import random
from typing import Callable

from . import arith
from .catalog import grade_num
from .models import PacketItem

NAMES = ("Mo", "Rin", "Tess", "Oli", "Kai", "Bea", "Juno", "Ezra", "Lark", "Remy")
THINGS = ("apples", "stickers", "shells", "pencils", "marbles", "leaves", "buttons", "stars")


def _lvl(dims: dict[str, int], key: str) -> int:
    return max(1, min(5, int(dims.get(key, 1))))


def num_max(skill: str, grade: str, level: int) -> int:
    g = grade_num(grade)
    i = level - 1
    if skill == "count":
        return ([3, 4, 5, 6, 8] if g < 0 else [5, 8, 10, 15, 20])[i]
    if skill == "add_sub":
        table = {0: [5, 6, 8, 10, 10], 1: [10, 12, 15, 20, 20], 2: [20, 30, 50, 80, 100]}
        return table.get(g, [50, 100, 200, 500, 1000])[i] if g <= 2 else [50, 100, 200, 500, 1000][i]
    if skill in ("multiplication", "division"):
        return ([3, 4, 5, 5, 5] if g <= 2 else [5, 6, 8, 10, 10] if g == 3 else [6, 8, 10, 12, 12])[i]
    if skill == "place_value":
        return ([20, 50, 99, 99, 120] if g <= 1 else [99, 200, 500, 999, 999] if g == 2 else [999, 999, 2000, 5000, 9999])[i]
    if skill == "fractions":
        return [3, 4, 4, 6, 8][i]
    return 10


class Gen:
    """Context handed to each generator."""

    def __init__(self, rng: random.Random, grade: str, dims: dict[str, int], skill: str,
                 guide: dict | None = None):
        self.rng, self.grade, self.dims, self.skill = rng, grade, dims, skill
        self.nmax = num_max(skill, grade, _lvl(dims, "number_range"))
        self.hint_on = _lvl(dims, "scaffold") <= 2
        self.steps = _lvl(dims, "steps")
        # Model-written sheets: preferred numbers (in draw order), a name and an object. Each is
        # used only when it fits what the generator would have drawn anyway.
        guide = guide or {}
        self.picks = [n for n in (guide.get("numbers") or []) if isinstance(n, int) and not isinstance(n, bool)]
        self.who, self.things = str(guide.get("who") or ""), str(guide.get("things") or "")

    def r(self, lo: int, hi: int) -> int:
        hi = max(lo, hi)
        if self.picks:
            n = self.picks.pop(0)
            if lo <= n <= hi:
                return n
        return self.rng.randint(lo, hi)

    def name(self) -> str:
        return self.who or self.rng.choice(NAMES)

    def thing(self) -> str:
        return self.things or self.rng.choice(THINGS)

    def item(self, fmt: str, prompt: str, answer: str, worked: str, spec: dict, *, display: list[str] | None = None,
             visual: dict | None = None, hint: str = "", work_lines: int = 2) -> PacketItem:
        return PacketItem(id="", skill=self.skill, format=fmt, prompt=prompt, answer=answer, worked_solution=worked,
                          spec=spec, display=display or [], visual_inventory=visual or {},
                          hint=hint if self.hint_on else "", work_lines=work_lines)


# -- count ---------------------------------------------------------------------------------------
def count_objects(g: Gen) -> PacketItem:
    n = g.r(2, min(g.nmax, 20))
    return g.item("count_objects", "Count the circles. Write how many.", str(n), f"Touch and count each circle: {n}.",
                  {"kind": "expr", "expr": str(n)}, visual={"type": "objects", "count": n},
                  hint="Cross off each circle as you count it.", work_lines=1)


def ten_frame(g: Gen) -> PacketItem:
    n = g.r(1, min(10, g.nmax))
    return g.item("ten_frame", "How many dots are in the ten frame?", str(n),
                  f"{n} {'box is' if n == 1 else 'boxes are'} filled; {10 - n} {'is' if 10 - n == 1 else 'are'} empty.",
                  {"kind": "expr", "expr": str(n)}, visual={"type": "ten_frame", "filled": [n]},
                  hint="A full row has 5." if n > 5 else "Touch each dot as you count.", work_lines=1)


def more_less(g: Gen) -> PacketItem:
    a = g.r(1, min(g.nmax, 10))
    b = a
    while b == a:
        b = g.r(1, min(g.nmax, 10))
    ans = "A" if a > b else "B"
    return g.item("more_less", "Which group has MORE? Circle A or B.", ans,
                  f"A has {a}, B has {b}. {max(a, b)} is more, so {ans}.",
                  {"kind": "choice_more", "a": a, "b": b}, display=["A", "B"],
                  visual={"type": "two_groups", "a": a, "b": b}, hint="Count each group first.", work_lines=0)


def number_after(g: Gen) -> PacketItem:
    step = 1 if g.steps < 3 else g.rng.choice([1, 2])
    start = g.r(0, max(1, g.nmax - 4 * step))
    seq = [start + step * i for i in range(4)]
    nxt = seq[-1] + step
    return g.item("number_after", f"What comes next?   {', '.join(map(str, seq))}, ___", str(nxt),
                  f"The numbers go up by {step}: {seq[-1]} + {step} = {nxt}.",
                  {"kind": "next", "seq": seq}, hint="Say the numbers out loud.", work_lines=0)


# -- place value ---------------------------------------------------------------------------------
def _digits(n: int) -> tuple[int, int, int, int]:
    return n // 1000, n // 100 % 10, n // 10 % 10, n % 10


def base_ten_blocks(g: Gen) -> PacketItem:
    n = g.r(11, min(g.nmax, 999))
    _, h, t, o = _digits(n)
    return g.item("base_ten_blocks", "What number do the blocks show?", str(n),
                  f"{h} hundreds + {t} tens + {o} ones = {h * 100} + {t * 10} + {o} = {n}.",
                  {"kind": "expr", "expr": f"{h}*100+{t}*10+{o}"},
                  visual={"type": "base_ten", "hundreds": h, "tens": t, "ones": o},
                  hint="Count the tall sticks by tens.", work_lines=1)


def _expanded(n: int) -> str:
    th, h, t, o = _digits(n)
    parts = [str(d * p) for d, p in ((th, 1000), (h, 100), (t, 10), (o, 1)) if d]
    return " + ".join(parts)


def expanded_form(g: Gen) -> PacketItem:
    n = g.r(21, g.nmax)
    return g.item("expanded_form", f"Write {n} in expanded form.", _expanded(n),
                  f"Split by place value: {_expanded(n)} = {n}.", {"kind": "expanded", "n": n},
                  hint="Hundreds + tens + ones.", work_lines=1)


def compare_symbol(g: Gen) -> PacketItem:
    a = g.r(10, g.nmax)
    b = a if g.rng.random() < 0.15 else g.r(10, g.nmax)
    sym = "<" if a < b else ">" if a > b else "="
    return g.item("compare_symbol", f"Write <, > or = in the blank:   {a}  ___  {b}", sym,
                  f"Compare the biggest place first: {a} {sym} {b}.", {"kind": "compare", "left": str(a), "right": str(b)},
                  hint="The open side faces the bigger number.", work_lines=0)


def order_numbers(g: Gen) -> PacketItem:
    vals: list[int] = []
    while len(vals) < 4:
        v = g.r(10, g.nmax)
        if v not in vals:
            vals.append(v)
    s = ", ".join(map(str, sorted(vals)))
    return g.item("order_numbers", f"Order from least to greatest:   {'   '.join(map(str, vals))}", s,
                  f"Compare place by place: {s}.", {"kind": "order", "values": vals},
                  hint="Find the smallest first.", work_lines=1)


# -- add / sub -----------------------------------------------------------------------------------
def _add_or_sub(g: Gen) -> tuple[int, int, str]:
    total = g.r(3, g.nmax)
    a = g.r(1, total - 1)
    if g.rng.random() < 0.5:
        return a, total - a, "+"
    return total, a, "-"


def equation(g: Gen) -> PacketItem:
    a, b, op = _add_or_sub(g)
    v = arith.evaluate(f"{a}{op}{b}")
    return g.item("equation", f"{a} {op} {b} = ___", arith.fmt(v), f"{a} {op} {b} = {arith.fmt(v)}.",
                  {"kind": "expr", "expr": f"{a}{op}{b}"}, hint="Count on from the bigger number." if op == "+" else
                  "Count back, or think addition.", work_lines=2)


def missing_addend(g: Gen) -> PacketItem:
    total = g.r(4, g.nmax)
    a = g.r(1, total - 1)
    eq = f"{a} + ? = {total}"
    return g.item("missing_addend", f"{a} + ___ = {total}", str(total - a), f"{total} - {a} = {total - a}, so {a} + {total - a} = {total}.",
                  {"kind": "missing", "equation": eq}, hint=f"Count up from {a} to {total}.", work_lines=2)


def ten_frame_add(g: Gen) -> PacketItem:
    a = g.r(1, min(10, g.nmax - 1))
    b = g.r(1, min(10, max(1, g.nmax - a)))
    return g.item("ten_frame_add", "Write an addition sentence for the two ten frames.", f"{a} + {b} = {a + b}",
                  f"First frame {a}, second frame {b}: {a} + {b} = {a + b}.",
                  {"kind": "expr", "expr": f"{a}+{b}"}, visual={"type": "ten_frame", "filled": [a, b]},
                  hint="Make a ten if you can." if a + b >= 10 else "Count all the dots.", work_lines=1)


def number_line(g: Gen) -> PacketItem:
    jump = g.rng.choice([1, 2, 5] if g.nmax <= 20 else [2, 5, 10])
    count = g.r(2, 4)
    end_max = min(g.nmax, 20 if jump < 5 else 100)
    start = g.r(0, max(0, end_max - jump * count))
    end = start + jump * count
    return g.item("number_line", f"Start at {start}. Make {count} jumps of {jump}. Where do you land?", str(end),
                  f"{start} + {' + '.join([str(jump)] * count)} = {end}.",
                  {"kind": "expr", "expr": f"{start}+{jump}*{count}"},
                  visual={"type": "number_line", "start": start, "jump": jump, "count": count,
                          "lo": max(0, start - jump), "hi": end + jump},
                  hint="Draw each jump as a little hill.", work_lines=1)


def bar_model(g: Gen) -> PacketItem:
    total = g.r(6, g.nmax)
    a = g.r(1, total - 1)
    b = total - a
    unknown = g.rng.choice(["part", "whole"])
    if unknown == "whole":
        parts, shown_total, ans, worked = [a, b], None, total, f"{a} + {b} = {total}."
        spec = {"kind": "expr", "expr": f"{a}+{b}"}
    else:
        parts, shown_total, ans, worked = [a, None], total, b, f"{total} - {a} = {b}."
        spec = {"kind": "missing", "equation": f"{a} + ? = {total}"}
    return g.item("bar_model", "Find the missing number in the bar model.", str(ans), worked, spec,
                  visual={"type": "bar", "total": shown_total, "parts": parts, "true_total": total},
                  hint="The two parts make the whole.", work_lines=2)


def true_false(g: Gen) -> PacketItem:
    a, b, op = _add_or_sub(g)
    v = arith.evaluate(f"{a}{op}{b}")
    shown = v if g.rng.random() < 0.5 else v + g.rng.choice([-2, -1, 1, 2])
    eq = f"{a} {op} {b} = {arith.fmt(shown)}"
    holds = arith.equation_holds(eq)
    return g.item("true_false", f"True or false?   {eq}", "True" if holds else "False",
                  f"{a} {op} {b} is {arith.fmt(v)}, so it is {'true' if holds else 'false'}.",
                  {"kind": "tf", "equation": eq}, display=["True", "False"], hint="Work out the left side first.",
                  work_lines=1)


def word_problem(g: Gen) -> PacketItem:
    n, t = g.name(), g.thing()
    a = g.r(2, max(3, g.nmax // 2))
    b = g.r(1, max(2, g.nmax // 2))
    if g.steps >= 3 and a + b + 2 <= g.nmax:
        c = g.r(1, a + b - 1)
        expr = f"{a}+{b}-{c}"
        prompt = f"{n} has {a} {t}. A friend gives {n} {b} more. Then {n} gives away {c}. How many {t} now?"
        worked = f"{a} + {b} = {a + b}; {a + b} - {c} = {a + b - c}."
    elif g.rng.random() < 0.5:
        expr = f"{a}+{b}"
        prompt = f"{n} has {a} {t} and finds {b} more. How many {t} does {n} have now?"
        worked = f"{a} + {b} = {a + b}."
    else:
        big = a + b
        expr = f"{big}-{b}"
        prompt = f"{n} had {big} {t} and used {b}. How many {t} are left?"
        worked = f"{big} - {b} = {a}."
    v = arith.evaluate(expr)
    if g.steps >= 4:
        prompt += " Show how you know."
    return g.item("word_problem", prompt, arith.fmt(v), worked, {"kind": "expr", "expr": expr},
                  hint="Draw a picture or a bar.", work_lines=3)


# -- multiplication ------------------------------------------------------------------------------
def _factors(g: Gen) -> tuple[int, int]:
    return g.r(2, g.nmax), g.r(2, g.nmax)


def array_to_equation(g: Gen) -> PacketItem:
    r, c = _factors(g)
    return g.item("array_to_equation", "Write a multiplication equation for the array.", f"{r} × {c} = {r * c}",
                  f"{r} rows of {c}: {r} × {c} = {r * c}" + (f" (or {c} × {r} = {r * c})." if r != c else "."),
                  {"kind": "expr", "expr": f"{r}*{c}"}, visual={"type": "array", "rows": r, "cols": c},
                  hint="Rows × how many in each row.", work_lines=1)


def equal_groups(g: Gen) -> PacketItem:
    k, each = _factors(g)
    return g.item("equal_groups", f"There are {k} groups with {each} in each group. How many in all?", str(k * each),
                  f"{k} × {each} = {k * each}.", {"kind": "expr", "expr": f"{k}*{each}"},
                  visual={"type": "groups", "groups": k, "per_group": each}, hint="Skip-count by the group size.",
                  work_lines=2)


def missing_factor(g: Gen) -> PacketItem:
    a, b = _factors(g)
    eq = f"{a} * ? = {a * b}"
    return g.item("missing_factor", f"{a} × ___ = {a * b}", str(b), f"{a * b} ÷ {a} = {b}, so {a} × {b} = {a * b}.",
                  {"kind": "missing", "equation": eq}, hint=f"Skip-count by {a} to {a * b}.", work_lines=2)


def select_all_equivalent(g: Gen) -> PacketItem:
    a, b = _factors(g)
    target = a * b
    good = [f"{b} × {a}", f"{a} × {b - 1} + {a}"]
    bad = [f"{a} + {b}", f"{a} × {b + 1}", f"{a - 1} × {b}"]
    bad = [x for x in bad if arith.evaluate(x) != target]
    opts = good + bad[:2]
    g.rng.shuffle(opts)
    letters = "ABCDE"
    shown = [f"{letters[i]}.  {o}" for i, o in enumerate(opts)]
    correct = [letters[i] for i, o in enumerate(opts) if arith.evaluate(o) == target]
    return g.item("select_all_equivalent", f"Circle ALL that are equal to {a} × {b}.", ", ".join(correct),
                  "; ".join(f"{letters[i]}: {o} = {arith.fmt(arith.evaluate(o))}" for i, o in enumerate(opts)),
                  {"kind": "select", "target": f"{a}*{b}", "options": opts}, display=shown,
                  hint="Work out each one, then compare.", work_lines=1)


def compare_products(g: Gen) -> PacketItem:
    a, b = _factors(g)
    if a != b and g.rng.random() < 0.3:
        c, d = b, a  # commutative pair: same product, different order
    else:
        c, d = _factors(g)
        for _ in range(20):  # never compare an expression with itself
            if (c, d) != (a, b):
                break
            c, d = _factors(g)
    sym = "<" if a * b < c * d else ">" if a * b > c * d else "="
    return g.item("compare_products", f"Write <, > or = in the blank:   {a} × {b}  ___  {c} × {d}", sym,
                  f"{a} × {b} = {a * b}; {c} × {d} = {c * d}; so {sym}.",
                  {"kind": "compare", "left": f"{a}*{b}", "right": f"{c}*{d}"}, hint="Find both products first.",
                  work_lines=1)


def mult_word_problem(g: Gen) -> PacketItem:
    n, t = g.name(), g.thing()
    a, b = _factors(g)
    if g.steps >= 3:
        extra = g.r(1, 9)
        expr = f"{a}*{b}+{extra}"
        prompt = f"{n} fills {a} bags with {b} {t} each, then finds {extra} more {t}. How many {t} in all?"
        worked = f"{a} × {b} = {a * b}; {a * b} + {extra} = {a * b + extra}."
    else:
        expr = f"{a}*{b}"
        prompt = f"{n} has {a} boxes. Each box holds {b} {t}. How many {t} altogether?"
        worked = f"{a} × {b} = {a * b}."
    if g.steps >= 4:
        prompt += " Write the equation you used."
    return g.item("mult_word_problem", prompt, arith.fmt(arith.evaluate(expr)), worked, {"kind": "expr", "expr": expr},
                  hint="Draw equal groups.", work_lines=3)


# -- division ------------------------------------------------------------------------------------
def equal_sharing(g: Gen) -> PacketItem:
    groups, each = _factors(g)
    total = groups * each
    return g.item("equal_sharing", f"Share {total} dots equally into {groups} circles. How many in each circle?",
                  str(each), f"{total} ÷ {groups} = {each}, because {groups} × {each} = {total}.",
                  {"kind": "expr", "expr": f"{total}/{groups}"},
                  visual={"type": "share", "total": total, "groups": groups},
                  hint="Deal them out one at a time.", work_lines=2)


def fact_family(g: Gen) -> PacketItem:
    a, b = _factors(g)
    if a == b:
        b = a + 1 if a < g.nmax else a - 1
    p = a * b
    eqs = [f"{a} × {b} = {p}", f"{b} × {a} = {p}", f"{p} ÷ {a} = {b}", f"{p} ÷ {b} = {a}"]
    return g.item("fact_family", f"Write the fact family for {a}, {b} and {p}.", "; ".join(eqs),
                  "Two multiplication and two division facts use the same three numbers.",
                  {"kind": "fact_family", "a": a, "b": b, "equations": eqs},
                  hint="Two × facts, two ÷ facts.", work_lines=4)


def missing_number_div(g: Gen) -> PacketItem:
    a, b = _factors(g)
    p = a * b
    if g.rng.random() < 0.5:
        prompt, eq, ans = f"{p} ÷ ___ = {b}", f"{p} / ? = {b}", a
    else:
        prompt, eq, ans = f"___ ÷ {a} = {b}", f"? / {a} = {b}", p
    return g.item("missing_number_div", prompt, str(ans), f"Think multiplication: {a} × {b} = {p}.",
                  {"kind": "missing", "equation": eq}, hint="Use the matching × fact.", work_lines=2)


def bar_model_div(g: Gen) -> PacketItem:
    parts, each = _factors(g)
    total = parts * each
    return g.item("bar_model_div", f"The bar is {total} long and has {parts} equal parts. How much is each part?",
                  str(each), f"{total} ÷ {parts} = {each}.", {"kind": "expr", "expr": f"{total}/{parts}"},
                  visual={"type": "bar_equal", "total": total, "parts": parts},
                  hint="Equal parts means divide.", work_lines=2)


def div_true_false(g: Gen) -> PacketItem:
    a, b = _factors(g)
    p = a * b
    shown = b if g.rng.random() < 0.5 else b + g.rng.choice([-1, 1])
    eq = f"{p} ÷ {a} = {shown}"
    holds = arith.equation_holds(eq)
    return g.item("div_true_false", f"True or false?   {eq}", "True" if holds else "False",
                  f"{a} × {b} = {p}, so {p} ÷ {a} = {b}; the statement is {'true' if holds else 'false'}.",
                  {"kind": "tf", "equation": eq}, display=["True", "False"], hint="Check with multiplication.",
                  work_lines=1)


def div_word_problem(g: Gen) -> PacketItem:
    n, t = g.name(), g.thing()
    a, b = _factors(g)
    p = a * b
    if g.steps >= 3:
        keep = g.r(1, 5)
        expr = f"({p + keep}-{keep})/{a}"
        prompt = f"{n} has {p + keep} {t}, keeps {keep}, and shares the rest equally with {a} friends. How many does each friend get?"
        worked = f"{p + keep} - {keep} = {p}; {p} ÷ {a} = {b}."
    else:
        expr = f"{p}/{a}"
        prompt = f"{n} shares {p} {t} equally among {a} friends. How many does each friend get?"
        worked = f"{p} ÷ {a} = {b}."
    if g.steps >= 4:
        prompt += " Write the × fact that checks it."
    return g.item("div_word_problem", prompt, str(b), worked, {"kind": "expr", "expr": expr},
                  hint="Draw the friends, deal out the items.", work_lines=3)


# -- fractions -----------------------------------------------------------------------------------
def name_fraction(g: Gen) -> PacketItem:
    den = g.r(2, g.nmax)
    num = g.r(1, den - 1) if g.steps >= 2 else 1
    return g.item("name_fraction", "What fraction of the shape is shaded?", f"{num}/{den}",
                  f"{num} of {den} equal parts are shaded: {num}/{den}.", {"kind": "fraction", "num": num, "den": den},
                  visual={"type": "fraction_bar", "parts": den, "shaded": num},
                  hint="Bottom number = how many equal parts.", work_lines=1)


def shade_fraction(g: Gen) -> PacketItem:
    den = g.r(2, g.nmax)
    num = g.r(1, den - 1)
    return g.item("shade_fraction", f"Shade {num}/{den} of the bar.", f"{num} of {den} parts shaded",
                  f"The bar has {den} equal parts; shade any {num}.", {"kind": "fraction", "num": num, "den": den},
                  visual={"type": "fraction_bar", "parts": den, "shaded": 0}, hint="Count the parts first.",
                  work_lines=0)


def compare_unit_fractions(g: Gen) -> PacketItem:
    a = g.r(2, max(3, g.nmax))
    b = a
    while b == a:
        b = g.r(2, max(3, g.nmax))
    sym = "<" if b < a else ">"
    return g.item("compare_unit_fractions", f"Write <, > or = in the blank:   1/{a}  ___  1/{b}", sym,
                  f"More equal parts means smaller parts: 1/{a} {sym} 1/{b}.",
                  {"kind": "compare", "left": f"1/{a}", "right": f"1/{b}"}, hint="Picture the pizza slices.",
                  work_lines=1)


def fraction_of_set(g: Gen) -> PacketItem:
    total = g.r(3, max(4, g.nmax))
    shaded = g.r(1, total - 1)
    return g.item("fraction_of_set", "What fraction of the circles are shaded?", f"{shaded}/{total}",
                  f"{shaded} shaded out of {total} circles: {shaded}/{total}.",
                  {"kind": "fraction", "num": shaded, "den": total},
                  visual={"type": "set", "total": total, "shaded": shaded}, hint="Count shaded, then count all.",
                  work_lines=1)


GENERATORS: dict[str, Callable[[Gen], PacketItem]] = {f.__name__: f for f in (
    count_objects, ten_frame, more_less, number_after,
    base_ten_blocks, expanded_form, compare_symbol, order_numbers,
    equation, missing_addend, ten_frame_add, number_line, bar_model, true_false, word_problem,
    array_to_equation, equal_groups, missing_factor, select_all_equivalent, compare_products, mult_word_problem,
    equal_sharing, fact_family, missing_number_div, bar_model_div, div_true_false, div_word_problem,
    name_fraction, shade_fraction, compare_unit_fractions, fraction_of_set,
)}
