"""Arithmetic evaluator + every generator × difficulty level produces verified items."""
import random
from fractions import Fraction

import pytest

from homework_coach import arith, catalog, verify
from homework_coach.generators import GENERATORS, Gen
from homework_coach.models import DIMENSIONS


def test_evaluate_basic():
    assert arith.evaluate("3 × 4 + 2") == 14
    assert arith.evaluate("24 ÷ 6") == 4
    assert arith.evaluate("7 x 8") == 56
    assert arith.evaluate("1/3 + 1/6") == Fraction(1, 2)


@pytest.mark.parametrize("bad", ["__import__('os')", "2**99", "a+1", "", "1;2", "9" * 100])
def test_evaluate_rejects(bad):
    with pytest.raises(arith.ArithError):
        arith.evaluate(bad)


def test_solve_missing_and_equations():
    assert arith.solve_missing("6 × ___ = 42") == 7
    assert arith.solve_missing("? / 4 = 5") == 20
    assert arith.solve_missing("56 ÷ ? = 8") == 7
    assert arith.solve_missing("3 + ? = 10") == 7
    assert arith.equation_holds("3 × 4 = 12 = 6 + 6")
    assert not arith.equation_holds("12 ÷ 3 = 5")
    with pytest.raises(arith.ArithError):
        arith.solve_missing("? × ? = 12")


def test_parse_number():
    assert arith.parse_number("12") == 12
    assert arith.parse_number(" 3/4 ") == Fraction(3, 4)
    assert arith.parse_number("abc") is None


def test_every_catalog_format_has_generator():
    assert set(catalog.FORMATS) == set(GENERATORS)


GRADES = ["PK", "K", "1", "2", "3", "4", "5"]


@pytest.mark.parametrize("fmt", sorted(GENERATORS))
def test_generator_items_verify_at_all_levels(fmt):
    f = catalog.FORMATS[fmt]
    grades = [g for g in GRADES if catalog.grade_num(g) >= f.min_grade]
    failures = []
    for grade in grades:
        for level in range(1, 6):
            dims = {d: level for d in DIMENSIONS}
            for seed in range(25):
                rng = random.Random(seed * 31 + level)
                it = GENERATORS[fmt](Gen(rng, grade, dims, f.skill))
                it.id = "1"
                errs = verify.check_item(it)
                if errs:
                    failures.append((grade, level, seed, errs))
    assert not failures, failures[:5]


def test_generators_are_deterministic():
    dims = {d: 2 for d in DIMENSIONS}
    for fmt, gen in GENERATORS.items():
        skill = catalog.FORMATS[fmt].skill
        a = gen(Gen(random.Random(7), "3", dims, skill))
        b = gen(Gen(random.Random(7), "3", dims, skill))
        assert a.to_dict() == b.to_dict(), fmt


def test_number_range_dimension_grows_operands():
    def biggest(level):
        dims = {d: 1 for d in DIMENSIONS} | {"number_range": level}
        m = 0
        for s in range(40):
            it = GENERATORS["missing_factor"](Gen(random.Random(s), "3", dims, "multiplication"))
            m = max(m, int(it.answer))
        return m
    assert biggest(1) < biggest(5)


def test_scaffold_dimension_removes_hints():
    low = GENERATORS["equation"](Gen(random.Random(1), "2", {d: 1 for d in DIMENSIONS}, "add_sub"))
    high = GENERATORS["equation"](Gen(random.Random(1), "2", {d: 1 for d in DIMENSIONS} | {"scaffold": 3}, "add_sub"))
    assert low.hint and not high.hint


def test_steps_dimension_adds_a_step():
    one = GENERATORS["mult_word_problem"](Gen(random.Random(3), "3", {d: 1 for d in DIMENSIONS}, "multiplication"))
    two = GENERATORS["mult_word_problem"](Gen(random.Random(3), "3", {d: 1 for d in DIMENSIONS} | {"steps": 3},
                                               "multiplication"))
    assert "+" not in one.spec["expr"] and "+" in two.spec["expr"]


def test_compare_products_never_compares_an_expression_with_itself():
    gen = GENERATORS["compare_products"]
    skill = catalog.FORMATS["compare_products"].skill
    for level in (1, 2, 3):
        dims = {d: level for d in DIMENSIONS}
        for seed in range(300):
            it = gen(Gen(random.Random(seed), "3", dims, skill))
            assert it.spec["left"] != it.spec["right"], (level, seed, it.prompt)
