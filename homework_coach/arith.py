"""Safe arithmetic: parse/evaluate small expressions without ``eval``.

Used to (a) recompute answers a vision model claims for homework items and
(b) independently re-check every generated packet answer. Accepts ``+ - * / ×
÷ x ( )``, integers, decimals and ``a/b`` fractions. Returns :class:`Fraction`
so division is exact.
"""
from __future__ import annotations

import ast
import re
from fractions import Fraction

_ALLOWED_BIN = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_MAX_LEN = 80
_MAX_ABS = 10**9


class ArithError(ValueError):
    pass


def normalize(expr: str) -> str:
    s = str(expr).strip()
    s = s.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    s = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d|\()", "*", s)  # 3 x 4
    s = s.replace(",", "")
    return s


def evaluate(expr: str) -> Fraction:
    s = normalize(expr)
    if not s or len(s) > _MAX_LEN or not re.fullmatch(r"[\d\s+\-*/().]+", s):
        raise ArithError(f"not a plain arithmetic expression: {expr!r}")
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise ArithError(f"cannot parse {expr!r}") from e
    return _eval(tree.body)


def _eval(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        v = Fraction(str(node.value))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        v = -v if isinstance(node.op, ast.USub) else v
    elif isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BIN):
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Add):
            v = a + b
        elif isinstance(node.op, ast.Sub):
            v = a - b
        elif isinstance(node.op, ast.Mult):
            v = a * b
        else:
            if b == 0:
                raise ArithError("division by zero")
            v = a / b
    else:
        raise ArithError(f"unsupported syntax: {type(node).__name__}")
    if abs(v) > _MAX_ABS:
        raise ArithError("number too large")
    return v


def parse_number(text: str | None) -> Fraction | None:
    """Read a child's final answer: ``12``, ``3/4``, ``2.5``, ``12 r 1`` → None (remainders unsupported)."""
    if text is None:
        return None
    s = normalize(text).strip().rstrip(".")
    m = re.fullmatch(r"-?\d+(\.\d+)?", s)
    if m:
        return Fraction(s)
    m = re.fullmatch(r"(-?\d+)\s*/\s*(\d+)", s)
    if m and int(m.group(2)) != 0:
        return Fraction(int(m.group(1)), int(m.group(2)))
    return None


def equation_holds(eq: str) -> bool:
    """True when every ``=``-separated side of ``eq`` evaluates equal (``3 × 4 = 12 = 6 + 6``)."""
    sides = [p for p in normalize(eq).split("=")]
    if len(sides) < 2:
        raise ArithError(f"not an equation: {eq!r}")
    vals = [evaluate(p) for p in sides]
    return all(v == vals[0] for v in vals)


_BLANK_RE = re.compile(r"_{2,}|\?|□|\[\s*\]")


def solve_missing(eq: str, *, lo: int = 0, hi: int = 2000) -> Fraction:
    """Solve an equation with exactly one blank (``___``, ``?``, ``□``) by search over integers.

    Deliberately independent of how a generator built the item: the verifier and
    intake both use it to recompute the unknown from the printed equation alone.
    """
    blanks = _BLANK_RE.findall(eq)
    if len(blanks) != 1:
        raise ArithError(f"need exactly one blank in {eq!r}")
    template = _BLANK_RE.sub("{x}", eq, count=1)
    left, _, right = normalize(template).partition("=")
    if not right:
        raise ArithError(f"not an equation: {eq!r}")
    side_with_x, other = (left, right) if "{x}" in left else (right, left)
    target = evaluate(other)
    if "{x}" not in side_with_x.replace(" ", ""):
        raise ArithError("blank not found")
    if side_with_x.strip() == "{x}":
        return target
    sols = []
    for x in range(lo, hi + 1):
        try:
            if evaluate(side_with_x.replace("{x}", str(x))) == target:
                sols.append(x)
        except ArithError:
            continue
        if len(sols) > 1:
            break
    if len(sols) != 1:
        raise ArithError(f"{'no' if not sols else 'multiple'} integer solutions for {eq!r}")
    return Fraction(sols[0])


def fmt(v: Fraction | int) -> str:
    v = Fraction(v)
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"
