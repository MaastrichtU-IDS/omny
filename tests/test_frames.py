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


def test_prefix_and_class_frame_subclassof():
    doc = """
    Prefix: : <http://ex.org/>
    Class: Pizza
        SubClassOf: hasTopping some Cheese
    """
    onto = parse(doc)
    pizza = onto.world["http://ex.org/Pizza"]
    assert any(getattr(sc, "type", None) == owlready2.SOME for sc in pizza.is_a)


def test_object_property_frame():
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: hasTopping
        Domain: Pizza
        Range: Topping
        Characteristics: Transitive, Functional
        InverseOf: isToppingOf
    """
    onto = parse(doc)
    p = onto.world["http://ex.org/hasTopping"]
    assert onto.world["http://ex.org/Pizza"] in p.domain
    assert onto.world["http://ex.org/Topping"] in p.range
    assert owlready2.TransitiveProperty in p.is_a
    assert owlready2.FunctionalProperty in p.is_a


def test_class_axioms():
    doc = """
    Prefix: : <http://ex.org/>
    Class: Margherita
        SubClassOf: Pizza, hasTopping some Cheese
        EquivalentTo: hasTopping only (Cheese or Tomato)
        DisjointWith: IceCream
    """
    onto = parse(doc)
    m = onto.world["http://ex.org/Margherita"]
    assert onto.world["http://ex.org/Pizza"] in m.is_a
    assert len(m.equivalent_to) == 1
    ice = onto.world["http://ex.org/IceCream"]
    assert any(m in d.entities and ice in d.entities
               for d in onto.disjoint_classes())
