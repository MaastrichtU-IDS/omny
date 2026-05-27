import owlready2
from pymos.parser import parse_expression


def test_named_class(onto):
    ce = parse_expression("Pizza", onto)
    assert isinstance(ce, owlready2.ThingClass)
    assert ce.iri == "http://pymos.test/onto.owl#Pizza"


def test_full_iri_class(onto):
    ce = parse_expression("<http://ex.org/Pizza>", onto)
    assert ce.iri == "http://ex.org/Pizza"


def test_prefixed_class(onto):
    ce = parse_expression("ex:Pizza", onto, prefixes={"ex": "http://ex.org/"})
    assert ce.iri == "http://ex.org/Pizza"


def test_intersection(onto):
    ce = parse_expression("A and B", onto)
    assert isinstance(ce, owlready2.And)
    assert {c.name for c in ce.Classes} == {"A", "B"}


def test_union(onto):
    ce = parse_expression("A or B", onto)
    assert isinstance(ce, owlready2.Or)


def test_complement(onto):
    ce = parse_expression("not A", onto)
    assert isinstance(ce, owlready2.Not)


def test_nested_precedence(onto):
    ce = parse_expression("A and (B or not C)", onto)
    assert isinstance(ce, owlready2.And)


def test_some(onto):
    ce = parse_expression("hasTopping some Cheese", onto)
    assert ce.type == owlready2.SOME
    assert ce.property.name == "hasTopping"
    assert ce.value.name == "Cheese"


def test_only(onto):
    ce = parse_expression("hasTopping only Cheese", onto)
    assert ce.type == owlready2.ONLY


def test_value(onto):
    ce = parse_expression("hasTopping value myCheese", onto)
    assert ce.type == owlready2.VALUE
    assert isinstance(ce.value, owlready2.Thing)


def test_has_self(onto):
    ce = parse_expression("likes Self", onto)
    assert ce.type == owlready2.HAS_SELF


def test_inverse_some(onto):
    ce = parse_expression("inverse hasTopping some Pizza", onto)
    assert isinstance(ce.property, owlready2.Inverse)
