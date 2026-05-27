import owlready2
import pytest
from pymos import parse


def test_prefix_and_class_frame():
    doc = """
    Prefix: : <http://ex.org/>
    Ontology: <http://ex.org/onto>
    Class: Pizza
        SubClassOf: hasTopping some Cheese
    """
    onto = parse(doc)
    pizza = onto.world["http://ex.org/Pizza"]
    assert pizza is not None


@pytest.mark.xfail(reason="SubClassOf axioms completed in Task 10")
def test_prefix_and_class_frame_subclassof():
    doc = """
    Prefix: : <http://ex.org/>
    Class: Pizza
        SubClassOf: hasTopping some Cheese
    """
    onto = parse(doc)
    pizza = onto.world["http://ex.org/Pizza"]
    assert any(getattr(sc, "type", None) == owlready2.SOME for sc in pizza.is_a)
