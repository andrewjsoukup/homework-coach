"""Parent coaching tips: how to help when a child is stuck, in the class's own language.

One short, concrete line per task format, written for a parent sitting beside the child.
When the active curriculum unit lists vocabulary the tip can use (e.g. "array", "skip count"),
the tip names it so home help sounds like class. Pure functions; no model call.
"""
from __future__ import annotations

from typing import Any

TIPS: dict[str, str] = {
    # counting
    "count_objects": "Have them touch each object once and say the number out loud; the last number said is the answer.",
    "ten_frame": "Ask how many empty boxes there are first; ten take away the empty ones is the answer.",
    "more_less": "Line the two groups up side by side so the extra ones stick out.",
    "number_after": "Count up together from a smaller number and stop right after the given one.",
    # place value
    "base_ten_blocks": "Count the hundreds, then the tens, then the ones, and say each place as you write it.",
    "expanded_form": "Cover all but one digit with a finger and ask what that digit is worth.",
    "compare_symbol": "Compare the biggest place first; only move right if those digits match.",
    "order_numbers": "Find the smallest number first, cross it off, then repeat.",
    # addition and subtraction
    "equation": "Start from the bigger number and count on (or back) on fingers or a quick number line.",
    "missing_addend": "Ask what you add to the first number to reach the total; count up the gap.",
    "ten_frame_add": "Fill one ten frame first, then count what spills into the next.",
    "number_line": "Draw each jump as an arc and write the jump size above it.",
    "bar_model": "Point at the whole bar and each part; the parts together make the whole.",
    "true_false": "Work out each side separately, then check whether they really match.",
    "word_problem": "Have them retell the story in their own words before choosing add or subtract.",
    # multiplication
    "array_to_equation": "Point at one row and count it, then skip-count by that number once for every row.",
    "equal_groups": "Count one group, then skip-count by that number for each group.",
    "missing_factor": "Skip-count by the number shown until you reach the total; the count of skips is the answer.",
    "select_all_equivalent": "Work out each choice on its own before deciding which ones match.",
    "compare_products": "Find each product separately first; only then compare them.",
    "mult_word_problem": "Ask: how many groups, and how many in each group? Draw it if it helps.",
    # division
    "equal_sharing": "Deal the dots out one at a time like cards until none are left.",
    "fact_family": "Start from the multiplication fact they know, then turn it around into division.",
    "missing_number_div": "Think multiplication: what times the divisor makes the total?",
    "bar_model_div": "The bar is the total; each equal part is one share.",
    "div_true_false": "Check it with multiplication: does the answer times the divisor give the total?",
    "div_word_problem": "Ask whether we know the number of groups or the size of each group.",
    # fractions
    "name_fraction": "Count all the equal parts for the bottom number, then the shaded ones for the top.",
    "shade_fraction": "The bottom number says how many equal parts; shade as many as the top number.",
    "compare_unit_fractions": "More pieces means smaller pieces: one of 8 is smaller than one of 4.",
    "fraction_of_set": "Split the set into equal groups first, then count the groups asked for.",
}

_VOCAB_HOOKS = {
    "array_to_equation": ("array", "skip count", "rows"),
    "equal_groups": ("equal groups", "skip count"),
    "missing_factor": ("factor", "skip count"),
    "compare_products": ("product",),
    "fact_family": ("fact family",),
    "bar_model": ("bar model", "part-part-whole"),
    "number_line": ("number line",),
    "expanded_form": ("expanded form",),
    "name_fraction": ("numerator", "denominator", "unit fraction"),
    "shade_fraction": ("numerator", "denominator"),
}


def tip_for(fmt: str, unit: dict[str, Any] | None = None) -> str:
    """Parent tip for ``fmt``; mentions the unit's own vocabulary when one of its words fits."""
    tip = TIPS.get(fmt, "Ask them to explain their thinking out loud; stop at the first step that is unclear.")
    vocab = [str(v).strip() for v in ((unit or {}).get("vocabulary") or []) if str(v).strip()]
    hooks = _VOCAB_HOOKS.get(fmt, ())
    used = [v for v in vocab if any(h in v.lower() for h in hooks)]
    if used:
        words = ", ".join(f"\u201c{w}\u201d" for w in used[:2])
        tip += f" Class words: {words}."
    return tip


__all__ = ["TIPS", "tip_for"]
