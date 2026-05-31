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


def test_frame_tokeniser_ignores_keywords_inside_quoted_literals():
    """A frame keyword like ``Class:`` or a prefixed name like ``26th:`` that
    appears inside a quoted annotation literal must not be treated as a real
    frame/axiom boundary. Regression: OBI annotations contain text such as
    ``"Following OBI call November 2012,26th: it was decided..."`` — the
    tokeniser must not raise ``Unknown prefix '26th'`` or warn about
    ``it`` looking like an axiom keyword."""
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    Class: A
        Annotations: rdfs:comment "Following OBI call November 2012,26th: it was decided. ObjectProperty: not really, just text."
    Class: B
    """
    onto = parse(doc)
    a = onto.world["http://ex.org/A"]
    b = onto.world["http://ex.org/B"]
    assert a is not None and b is not None
    # The annotation text containing "ObjectProperty:" must NOT have
    # been parsed as a separate frame, so B (the next real frame) is reachable.
    assert b in list(onto.classes())


def test_misc_axiom_disjoint_classes():
    """Top-level ``DisjointClasses:`` is a Manchester misc axiom (no subject,
    comma-separated class list). Regression: real OBO ontologies like SIO
    use it heavily."""
    doc = """
    Prefix: : <http://ex.org/>
    Class: A
    Class: B
    Class: C
    DisjointClasses: A, B, C
    """
    onto = parse(doc)
    a = onto.world["http://ex.org/A"]
    b = onto.world["http://ex.org/B"]
    c = onto.world["http://ex.org/C"]
    groups = list(onto.disjoint_classes())
    assert any(set([a, b, c]).issubset(set(g.entities)) for g in groups)


def test_misc_axiom_different_individuals():
    doc = """
    Prefix: : <http://ex.org/>
    Individual: i1
    Individual: i2
    Individual: i3
    DifferentIndividuals: i1, i2, i3
    """
    onto = parse(doc)
    inds = [onto.world[f"http://ex.org/i{n}"] for n in (1, 2, 3)]
    groups = list(onto.different_individuals())
    assert any(set(inds).issubset(set(g.entities)) for g in groups)


def test_misc_axiom_equivalent_classes():
    doc = """
    Prefix: : <http://ex.org/>
    Class: A
    Class: B
    EquivalentClasses: A, B
    """
    onto = parse(doc)
    a = onto.world["http://ex.org/A"]
    b = onto.world["http://ex.org/B"]
    assert b in a.equivalent_to or a in b.equivalent_to


def test_frame_tokeniser_handles_escaped_quotes_inside_literals():
    doc = r"""
    Prefix: : <http://ex.org/>
    Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    Class: A
        Annotations: rdfs:comment "He said \"Class: B is here\" but it's not really."
    Class: C
    """
    onto = parse(doc)
    assert onto.world["http://ex.org/A"] is not None
    assert onto.world["http://ex.org/C"] is not None
    # The fake "Class: B" inside the escaped-quote literal must not become an entity
    assert onto.world["http://ex.org/B"] is None


def test_facts_on_functional_object_property():
    """owlready2 stores values of FunctionalProperty as a scalar, not a list,
    so getattr returns None for an unset Functional property. The frame loader
    must not do ``None + [value]`` (the previous naive append pattern)."""
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: hasMother
        Characteristics: Functional
    Individual: bob
        Facts: hasMother alice
    """
    onto = parse(doc)
    bob = onto.world["http://ex.org/bob"]
    alice = onto.world["http://ex.org/alice"]
    # Functional → scalar storage in owlready2
    assert bob.hasMother is alice


def test_facts_on_functional_data_property():
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    DataProperty: hasAge
        Characteristics: Functional
        Range: xsd:integer
    Individual: bob
        Facts: hasAge 42
    """
    onto = parse(doc)
    bob = onto.world["http://ex.org/bob"]
    assert bob.hasAge == 42


def test_facts_non_functional_still_works():
    """Non-functional Facts must continue to work (list storage)."""
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: hasFriend
    Individual: bob
        Facts: hasFriend alice, hasFriend carol
    """
    onto = parse(doc)
    bob = onto.world["http://ex.org/bob"]
    names = {f.name for f in bob.hasFriend}
    assert names == {"alice", "carol"}


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


def test_ontology_iri_is_set():
    doc = """
    Prefix: : <http://ex.org/>
    Ontology: <http://ex.org/myonto>
    Class: Pizza
    """
    onto = parse(doc)
    assert onto.base_iri.rstrip("#/") == "http://ex.org/myonto"
    # simple names still resolve via the empty prefix, not the ontology IRI
    assert onto.world["http://ex.org/Pizza"] is not None


def test_import_recorded_without_fetch():
    doc = """
    Prefix: : <http://ex.org/>
    Ontology: <http://ex.org/myonto>
    Import: <http://other.org/imported>
    Class: Pizza
    """
    onto = parse(doc)
    imported_iris = {o.base_iri.rstrip("#/") for o in onto.imported_ontologies}
    assert "http://other.org/imported" in imported_iris


def test_repeated_axiom_keyword_concatenates():
    """Multiple lines of the same axiom keyword inside one frame must all
    contribute, not overwrite. Regression: ``Class: C
        SubClassOf: A
        SubClassOf: B`` used to drop the first SubClassOf."""
    doc = """
    Prefix: : <http://ex.org/>
    Class: MyPizza
        SubClassOf: Pizza
        SubClassOf: hasTopping some Cheese
    """
    onto = parse(doc)
    my = onto.world["http://ex.org/MyPizza"]
    pizza = onto.world["http://ex.org/Pizza"]
    assert pizza in my.is_a, "first SubClassOf was dropped"
    # And the restriction is still applied
    assert any(getattr(sc, "type", None) == owlready2.SOME for sc in my.is_a), \
        "restriction SubClassOf was dropped"
