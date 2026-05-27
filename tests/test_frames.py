import rdflib
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


def test_individual_frame():
    doc = """
    Prefix: : <http://ex.org/>
    Individual: bob
        Types: Person
        Facts: hasAge 42
        SameAs: robert
        DifferentFrom: alice
    """
    onto = parse(doc)
    bob = onto.world["http://ex.org/bob"]
    assert onto.world["http://ex.org/Person"] in bob.is_a
    g = onto.world.as_rdflib_graph()
    same = rdflib.URIRef("http://www.w3.org/2002/07/owl#sameAs")
    assert (rdflib.URIRef("http://ex.org/bob"), same,
            rdflib.URIRef("http://ex.org/robert")) in g


def test_full_pizza_document():
    doc = open("tests/data/pizza.omn").read()
    onto = parse(doc)
    assert onto.world["http://ex.org/Pizza"] is not None
    assert onto.world["http://ex.org/Margherita"] is not None
    import io
    onto.save(file=io.BytesIO(), format="rdfxml")


# FIX 1 tests

def test_custom_annotation_property():
    doc = """
    Prefix: : <http://ex.org/>
    AnnotationProperty: note
    Class: C
        Annotations: note "hello"
    """
    onto = parse(doc)
    c = onto.world["http://ex.org/C"]
    assert "hello" in getattr(c, "note", [])


def test_annotation_property_name_collision_raises():
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: rel
    Class: C
        Annotations: rel "oops"
    """
    with pytest.raises(ValueError):
        parse(doc)


# FIX 2 test

def test_datatype_declaration_emits_triple():
    doc = """
    Prefix: : <http://ex.org/>
    Datatype: MyType
    """
    onto = parse(doc)
    g = onto.world.as_rdflib_graph()
    assert (rdflib.URIRef("http://ex.org/MyType"),
            rdflib.URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
            rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#Datatype")) in g
