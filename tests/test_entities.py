import pytest
import owlready2
from omny.entities import EntityResolver


def test_get_or_create_class_by_simple_name(onto):
    r = EntityResolver(onto, prefixes={})
    A = r.get_class("Pizza")
    assert isinstance(A, owlready2.ThingClass)
    assert A.iri == "http://omny.test/onto.owl#Pizza"
    # idempotent: same name returns same entity
    assert r.get_class("Pizza") is A


def test_get_or_create_class_by_full_iri(onto):
    r = EntityResolver(onto, prefixes={})
    A = r.get_class("http://other.org/Thing")
    assert A.iri == "http://other.org/Thing"


def test_prefix_resolution(onto):
    r = EntityResolver(onto, prefixes={"ex": "http://ex.org/"})
    A = r.get_class("ex:Foo")
    assert A.iri == "http://ex.org/Foo"


def test_object_vs_data_property(onto):
    r = EntityResolver(onto, prefixes={})
    op = r.get_object_property("hasTopping")
    dp = r.get_data_property("hasCalories")
    assert owlready2.ObjectProperty in op.is_a or owlready2.ObjectPropertyClass in type(op).__mro__
    assert owlready2.DataProperty in dp.is_a or owlready2.DataPropertyClass in type(dp).__mro__


def test_unknown_prefix_raises(onto):
    r = EntityResolver(onto, prefixes={})
    with pytest.raises(ValueError):
        r.get_class("bogus:Thing")


def test_anonymous_individual_blank_node(onto):
    """Issue #69: a nodeID (``_:label``) resolves to an owlready2 anonymous
    individual (blank node) rather than being CURIE-expanded."""
    r = EntityResolver(onto, prefixes={})
    ind = r.get_individual("_:b1")
    assert isinstance(ind, owlready2.Thing)
    # blank node: negative storid, no real IRI
    assert ind.storid < 0
    assert not getattr(ind, "name", "")


def test_anonymous_individual_reused_within_parse(onto):
    """Repeated references to the same nodeID map to the same blank node."""
    r = EntityResolver(onto, prefixes={})
    assert r.get_individual("_:b1") is r.get_individual("_:b1")
    assert r.get_individual("_:b1") is not r.get_individual("_:b2")
