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


# ---- Task 20: frame renderers ------------------------------------------------

from pymos import parse
from pymos.render import render_frame


def test_render_class_frame_subclass_equivalent_disjoint():
    doc = """
    Prefix: : <http://ex.org/>
    Class: Margherita
        SubClassOf: Pizza, hasTopping some Cheese
        EquivalentTo: hasTopping only Cheese
        DisjointWith: IceCream
    """
    o = parse(doc)
    m = o.world["http://ex.org/Margherita"]
    out = render_frame(m, prefixes={"": "http://ex.org/"})
    assert out.startswith("Class: :Margherita")
    assert "SubClassOf:" in out
    assert ":Pizza" in out
    assert "some" in out
    assert "EquivalentTo:" in out and "only" in out
    assert "DisjointWith:" in out and ":IceCream" in out


def test_render_class_frame_filters_thing_from_superclasses():
    """owlready2 puts owl:Thing in is_a; renderer must skip it."""
    doc = """
    Prefix: : <http://ex.org/>
    Class: Cheese
    """
    o = parse(doc)
    c = o.world["http://ex.org/Cheese"]
    out = render_frame(c, prefixes={"": "http://ex.org/"})
    assert out.strip() == "Class: :Cheese"
    assert "Thing" not in out


def test_render_object_property_frame():
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: hasTopping
        Domain: Pizza
        Range: Topping
        Characteristics: Transitive, Functional
        InverseOf: isToppingOf
    """
    o = parse(doc)
    p = o.world["http://ex.org/hasTopping"]
    out = render_frame(p, prefixes={"": "http://ex.org/"})
    assert out.startswith("ObjectProperty: :hasTopping")
    assert "Domain: :Pizza" in out
    assert "Range: :Topping" in out
    assert "Characteristics:" in out
    assert "Transitive" in out and "Functional" in out
    assert "InverseOf: :isToppingOf" in out


def test_render_data_property_frame():
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    DataProperty: hasName
        Domain: Person
        Range: xsd:string
        Characteristics: Functional
    """
    o = parse(doc)
    p = o.world["http://ex.org/hasName"]
    out = render_frame(p, prefixes={
        "": "http://ex.org/",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
    })
    assert out.startswith("DataProperty: :hasName")
    assert "Domain: :Person" in out
    assert "Range: xsd:string" in out
    assert "Characteristics: Functional" in out


def test_render_individual_frame():
    doc = """
    Prefix: : <http://ex.org/>
    Individual: bob
        Types: Person
    """
    o = parse(doc)
    b = o.world["http://ex.org/bob"]
    out = render_frame(b, prefixes={"": "http://ex.org/"})
    assert out.startswith("Individual: :bob")
    assert "Types: :Person" in out


def test_render_frame_drops_empty_axiom_lines():
    """A class with no axioms produces just the header — no empty SubClassOf:."""
    doc = """
    Prefix: : <http://ex.org/>
    Class: Cheese
    """
    o = parse(doc)
    out = render_frame(o.world["http://ex.org/Cheese"], prefixes={"": "http://ex.org/"})
    assert "SubClassOf:" not in out
    assert "EquivalentTo:" not in out
    assert "DisjointWith:" not in out
