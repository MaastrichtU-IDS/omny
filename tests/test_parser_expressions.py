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
