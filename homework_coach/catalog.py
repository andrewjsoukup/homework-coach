"""Skill + task-format catalog (v1: elementary math).

The vision step maps what it sees onto these ids (``other`` when nothing fits) so
observations, the brief and the packet generator speak the same vocabulary.
A *format* is the task shape (array -> equation, bar model, select-all...), which
is what rotates day to day — not just the operands.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    id: str
    skill: str
    label: str
    visual: bool  # uses a drawn representation (favoured at low `representation` levels)
    min_grade: int = -1  # PK=-1, K=0, 1..12


SKILLS: dict[str, str] = {
    "count": "Counting objects and number order",
    "place_value": "Place value, comparing and ordering numbers",
    "add_sub": "Addition and subtraction",
    "multiplication": "Multiplication (equal groups, arrays, facts)",
    "division": "Division (equal sharing, fact families)",
    "fractions": "Fractions (naming, shading, comparing)",
}

_F = [
    # count
    Format("count_objects", "count", "Count the objects and write the number", True),
    Format("ten_frame", "count", "Read a ten frame", True),
    Format("more_less", "count", "Which group has more?", True),
    Format("number_after", "count", "What number comes next?", False),
    # place value
    Format("base_ten_blocks", "place_value", "Base-ten blocks -> number", True, 1),
    Format("expanded_form", "place_value", "Write in expanded form", False, 1),
    Format("compare_symbol", "place_value", "Compare with <, >, =", False, 1),
    Format("order_numbers", "place_value", "Order numbers least to greatest", False, 1),
    # add / sub
    Format("equation", "add_sub", "Solve the equation", False),
    Format("missing_addend", "add_sub", "Find the missing number", False),
    Format("ten_frame_add", "add_sub", "Add with ten frames", True),
    Format("number_line", "add_sub", "Jump on a number line", True),
    Format("bar_model", "add_sub", "Part-part-whole bar model", True, 1),
    Format("true_false", "add_sub", "True or false?", False, 1),
    Format("word_problem", "add_sub", "Story problem", False),
    # multiplication
    Format("array_to_equation", "multiplication", "Array -> multiplication equation", True, 2),
    Format("equal_groups", "multiplication", "Equal groups -> total", True, 2),
    Format("missing_factor", "multiplication", "Find the missing factor", False, 2),
    Format("select_all_equivalent", "multiplication", "Select all that are equal", False, 2),
    Format("compare_products", "multiplication", "Compare two products", False, 2),
    Format("mult_word_problem", "multiplication", "Story problem", False, 2),
    # division
    Format("equal_sharing", "division", "Share equally into groups", True, 2),
    Format("fact_family", "division", "Write the fact family", False, 3),
    Format("missing_number_div", "division", "Find the missing number", False, 3),
    Format("bar_model_div", "division", "Equal-parts bar model", True, 3),
    Format("div_true_false", "division", "True or false?", False, 3),
    Format("div_word_problem", "division", "Story problem", False, 3),
    # fractions
    Format("name_fraction", "fractions", "Name the shaded fraction", True, 2),
    Format("shade_fraction", "fractions", "Shade the fraction", True, 2),
    Format("compare_unit_fractions", "fractions", "Compare unit fractions", False, 3),
    Format("fraction_of_set", "fractions", "Fraction of a set", True, 3),
]

FORMATS: dict[str, Format] = {f.id: f for f in _F}

# Supporting review when a topic is current (SPEC §3.7: prior topic demoted to review).
SUPPORT = {
    "count": "add_sub",
    "place_value": "add_sub",
    "add_sub": "place_value",
    "multiplication": "add_sub",
    "division": "multiplication",
    "fractions": "multiplication",
}

GRADE_NUM = {"PK": -1, "K": 0, **{str(i): i for i in range(1, 13)}}

DEFAULT_SKILL_BY_GRADE = {-1: "count", 0: "count", 1: "add_sub", 2: "add_sub", 3: "multiplication",
                          4: "multiplication", 5: "fractions"}


def grade_num(grade: str) -> int:
    return GRADE_NUM.get(str(grade), 3)


def default_skill(grade: str) -> str:
    g = grade_num(grade)
    return DEFAULT_SKILL_BY_GRADE.get(g, "fractions")


def support_skill(skill: str, grade: str) -> str:
    g = grade_num(grade)
    if skill == "add_sub" and g <= 1:
        return "count"
    s = SUPPORT.get(skill, "add_sub")
    # never pick a review skill whose formats are all above grade
    return s if formats_for(s, grade) else "count"


def formats_for(skill: str, grade: str) -> list[Format]:
    g = grade_num(grade)
    return [f for f in _F if f.skill == skill and f.min_grade <= g]


def catalog_text() -> str:
    """Compact vocabulary for the vision prompt."""
    lines = []
    for sid, desc in SKILLS.items():
        fmts = ", ".join(f"{f.id} ({f.label})" for f in _F if f.skill == sid)
        lines.append(f"- {sid}: {desc}. Formats: {fmts}")
    return "\n".join(lines)
