"""Tests for owlready2 -> Manchester rendering (Milestone 5)."""
import owlready2

from pymos import parse_expression
from pymos.render import render_expression


def _rt(expr, onto, prefixes=None):
    """Parse then render; useful for asserting output shape."""
    ce = parse_expression(expr, onto, prefixes=prefixes)
    return render_expression(ce, prefixes=prefixes)


# ---- Task 19: expression renderer --------------------------------------------

def test_render_named_class_full_iri(onto):
    assert _rt("Pizza", onto) == "<http://pymos.test/onto.owl#Pizza>"


def test_render_named_class_with_prefix(onto):
    prefixes = {"": "http://pymos.test/onto.owl#"}
    assert _rt("Pizza", onto, prefixes) == ":Pizza"


def test_render_some(onto):
    assert _rt("hasTopping some Cheese", onto) == (
        "<http://pymos.test/onto.owl#hasTopping> some "
        "<http://pymos.test/onto.owl#Cheese>"
    )


def test_render_only(onto):
    assert " only " in _rt("hasTopping only Cheese", onto)


def test_render_intersection(onto):
    out = _rt("A and B", onto)
    assert " and " in out
    assert out.count("<http://pymos.test/onto.owl#") == 2


def test_render_union(onto):
    out = _rt("A or B", onto)
    assert " or " in out


def test_render_precedence_parens(onto):
    # 'or' is lower precedence than 'and'; the (B or C) must be parenthesised
    out = _rt("A and (B or C)", onto)
    assert "and (" in out and " or " in out


def test_render_not(onto):
    out = _rt("not A", onto)
    assert out.startswith("not ")


def test_render_min_cardinality(onto):
    out = _rt("hasTopping min 2 Cheese", onto)
    assert " min 2 " in out


def test_render_max_cardinality(onto):
    out = _rt("hasTopping max 3 Cheese", onto)
    assert " max 3 " in out


def test_render_exactly_cardinality(onto):
    out = _rt("hasTopping exactly 1 Cheese", onto)
    assert " exactly 1 " in out


def test_render_value(onto):
    out = _rt("hasTopping value myCheese", onto)
    assert " value " in out


def test_render_self(onto):
    out = _rt("likes Self", onto)
    assert out.endswith(" Self")


def test_render_one_of(onto):
    out = _rt("{ a , b , c }", onto)
    assert out.startswith("{") and out.endswith("}")
    assert out.count(",") == 2


def test_render_inverse(onto):
    out = _rt("inverse hasTopping some Pizza", onto)
    assert out.startswith("inverse ")
