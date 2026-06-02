"""Tests for owlready2 -> Manchester rendering (Milestone 5)."""
import owlready2

from omny import parse, parse_expression
from omny.render import render, render_expression, render_frame


def _rt(expr, onto, prefixes=None):
    """Parse then render; useful for asserting output shape."""
    ce = parse_expression(expr, onto, prefixes=prefixes)
    return render_expression(ce, prefixes=prefixes)


# ---- Task 19: expression renderer --------------------------------------------

def test_render_named_class_full_iri(onto):
    assert _rt("Pizza", onto) == "<http://omny.test/onto.owl#Pizza>"


def test_render_named_class_with_prefix(onto):
    prefixes = {"": "http://omny.test/onto.owl#"}
    assert _rt("Pizza", onto, prefixes) == ":Pizza"


def test_render_some(onto):
    assert _rt("hasTopping some Cheese", onto) == (
        "<http://omny.test/onto.owl#hasTopping> some "
        "<http://omny.test/onto.owl#Cheese>"
    )


def test_render_only(onto):
    assert " only " in _rt("hasTopping only Cheese", onto)


def test_render_intersection(onto):
    out = _rt("A and B", onto)
    assert " and " in out
    assert out.count("<http://omny.test/onto.owl#") == 2


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


# ---- Task 21: document renderer + round-trip --------------------------------

# Fixture covering exactly what render currently supports: Prefix/Ontology header,
# Class frames (SubClassOf/EquivalentTo/DisjointWith), Object/DataProperty frames
# (Domain/Range/Characteristics/InverseOf), Individual frames (Types).
# Annotations / Facts / SameAs / DifferentFrom / AnnotationProperty / Datatype
# rendering is a follow-up (see render.py TODO).
_ROUND_TRIP_DOC = """\
Prefix: : <http://ex.org/>
Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>

Ontology: <http://ex.org/omny-rt.owl>

Class: Food
Class: Topping
Class: Cheese
    SubClassOf: Topping
Class: Tomato
    SubClassOf: Topping
Class: Pizza
    SubClassOf: Food
Class: Margherita
    SubClassOf: Pizza, hasTopping some Cheese
    EquivalentTo: hasTopping only (Cheese or Tomato)
    DisjointWith: IceCream
Class: IceCream

ObjectProperty: hasTopping
    Domain: Pizza
    Range: Topping
    Characteristics: Transitive
ObjectProperty: isToppingOf
    InverseOf: hasTopping

DataProperty: hasCalories
    Domain: Pizza
    Range: xsd:integer

Individual: margherita1
    Types: Margherita
Individual: iceCream1
    Types: IceCream
"""

_RT_PREFIXES = {"": "http://ex.org/", "xsd": "http://www.w3.org/2001/XMLSchema#"}


def test_render_document_emits_header_and_frames():
    o = parse(_ROUND_TRIP_DOC)
    text = render(o, prefixes=_RT_PREFIXES)
    assert "Prefix: : <http://ex.org/>" in text
    assert "Ontology: <http://ex.org/omny-rt.owl>" in text
    assert "Class: :Margherita" in text
    assert "ObjectProperty: :hasTopping" in text
    assert "DataProperty: :hasCalories" in text
    assert "Individual: :margherita1" in text


def test_render_document_round_trips_structurally():
    onto1 = parse(_ROUND_TRIP_DOC)
    text = render(onto1, prefixes=_RT_PREFIXES)
    onto2 = parse(text)

    iris1 = {c.iri for c in onto1.classes()}
    iris2 = {c.iri for c in onto2.classes()}
    assert iris1 == iris2

    for iri in iris1:
        c1, c2 = onto1.world[iri], onto2.world[iri]
        supers1 = [s for s in c1.is_a if s is not owlready2.Thing]
        supers2 = [s for s in c2.is_a if s is not owlready2.Thing]
        assert len(supers1) == len(supers2), f"is_a mismatch for {iri}"
        assert len(c1.equivalent_to) == len(c2.equivalent_to), f"equiv mismatch for {iri}"

    op1 = {p.iri for p in onto1.object_properties()}
    op2 = {p.iri for p in onto2.object_properties()}
    assert op1 == op2

    ind1 = {i.iri for i in onto1.individuals()}
    ind2 = {i.iri for i in onto2.individuals()}
    assert ind1 == ind2


def test_render_document_idempotent_on_second_pass():
    text1 = render(parse(_ROUND_TRIP_DOC), prefixes=_RT_PREFIXES)
    text2 = render(parse(text1), prefixes=_RT_PREFIXES)
    assert text1 == text2  # second pass is stable


# ---- Task 22: edge cases -----------------------------------------------------

def test_render_constrained_datatype(onto):
    out = _rt(
        "hasAge some xsd:integer[>= 18]",
        onto,
        prefixes={"xsd": "http://www.w3.org/2001/XMLSchema#"},
    )
    assert "xsd:integer" in out
    assert ">= 18" in out
    assert "[" in out and "]" in out


def test_render_nested_precedence_or_under_and(onto):
    # (A or B) and not C → the 'or' operand must be parenthesised
    out = _rt("(A or B) and not C", onto)
    assert " and " in out
    assert " or " in out
    assert "not " in out
    # Find 'and' and check that the operand to its left starts with '(' (the or-subexpr)
    pre_and = out.split(" and ")[0].strip()
    assert pre_and.startswith("(") and pre_and.endswith(")"), (
        f"expected 'or' operand to be parenthesised, got: {pre_and!r}"
    )


def test_render_double_negation(onto):
    out = _rt("not (not A)", onto)
    assert out.count("not ") == 2


# ---- Rendering fidelity: Annotations / Facts / SameAs / DifferentFrom -------
# ---- AnnotationProperty / Datatype / full pizza.omn round-trip --------------

_FIDELITY_PREFIXES = {
    "": "http://ex.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


def test_render_class_annotations():
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    Class: Pizza
        Annotations: rdfs:label "Pizza"
        SubClassOf: Food
    """
    o = parse(doc)
    out = render_frame(o.world["http://ex.org/Pizza"], prefixes=_FIDELITY_PREFIXES)
    assert "Annotations:" in out
    assert "rdfs:label" in out and '"Pizza"' in out
    assert "SubClassOf: :Food" in out


def test_render_individual_facts():
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    DataProperty: hasCalories
        Range: xsd:integer
    Individual: bob
        Types: Person
        Facts: hasCalories 800
    """
    o = parse(doc)
    out = render_frame(o.world["http://ex.org/bob"], prefixes=_FIDELITY_PREFIXES)
    assert "Facts:" in out
    assert ":hasCalories 800" in out


def test_render_individual_same_as():
    doc = """
    Prefix: : <http://ex.org/>
    Individual: bob
        SameAs: robert
    """
    o = parse(doc)
    out = render_frame(o.world["http://ex.org/bob"], prefixes=_FIDELITY_PREFIXES)
    assert "SameAs: :robert" in out


def test_render_individual_different_from():
    doc = """
    Prefix: : <http://ex.org/>
    Individual: bob
        DifferentFrom: alice
    """
    o = parse(doc)
    out = render_frame(o.world["http://ex.org/bob"], prefixes=_FIDELITY_PREFIXES)
    assert "DifferentFrom: :alice" in out


def test_render_annotation_property_frame():
    doc = """
    Prefix: : <http://ex.org/>
    AnnotationProperty: hasNote
    """
    o = parse(doc)
    p = o.world["http://ex.org/hasNote"]
    out = render_frame(p, prefixes=_FIDELITY_PREFIXES)
    assert out.startswith("AnnotationProperty: :hasNote")


def test_render_annotation_aliased_python_names_no_duplicate():
    """When two annotation properties share an owlready2 ``python_name``
    (e.g. ``rdfs:comment`` and ``schema:comment`` both map to the
    ``.comment`` attribute), each entity's rendered Annotations line must
    list each triple ONCE under its actual predicate — not duplicate every
    value across both predicates.

    Regression guard for the bulk-fetch render path. The pre-bulk
    per-entity ``getattr`` path used to iterate both APs and ask
    owlready2 for ``entity.comment`` each time, so the same value was
    rendered twice — once as ``rdfs:comment "X"`` and once as
    ``schema:comment "X"``. The bulk path goes triple-by-triple, so this
    can never happen.

    We populate the graph directly via ``world.as_rdflib_graph()`` because
    omny's parser also collapses python_name-aliased predicates today
    (separate bug); this test isolates the renderer's behaviour.
    """
    import rdflib
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    Prefix: schema: <http://schema.org/>
    AnnotationProperty: schema:comment
    Class: A
    Class: B
    """
    o = parse(doc)
    g = o.world.as_rdflib_graph()
    A = rdflib.URIRef("http://ex.org/A")
    B = rdflib.URIRef("http://ex.org/B")
    with o:
        g.add((A, rdflib.RDFS.comment, rdflib.Literal("from-rdfs")))
        g.add((B, rdflib.URIRef("http://schema.org/comment"), rdflib.Literal("from-schema")))

    text = render(o, prefixes={"": "http://ex.org/",
                               "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                               "schema": "http://schema.org/"})
    # A's frame: only rdfs:comment "from-rdfs"; schema:comment must not appear
    a_frame = next(b for b in text.split("\n\n") if b.startswith("Class: :A"))
    assert 'rdfs:comment "from-rdfs"' in a_frame
    assert "schema:comment" not in a_frame, (
        f"schema:comment leaked into A's frame (alias-collision bug):\n{a_frame}"
    )
    # B's frame: only schema:comment "from-schema"; rdfs:comment must not appear
    b_frame = next(b for b in text.split("\n\n") if b.startswith("Class: :B"))
    assert 'schema:comment "from-schema"' in b_frame
    assert "rdfs:comment" not in b_frame, (
        f"rdfs:comment leaked into B's frame (alias-collision bug):\n{b_frame}"
    )


def test_render_datatype_frame_in_document():
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    Datatype: xsd:integer
    Class: Pizza
    """
    o = parse(doc)
    text = render(o, prefixes=_FIDELITY_PREFIXES)
    assert "Datatype: xsd:integer" in text


def test_full_pizza_document_round_trips_structurally():
    """The complete pizza.omn fixture covers every frame and axiom kind omny
    supports — round-trip must preserve class/property/individual sets and
    axiom counts after rendering with full fidelity."""
    doc = open("tests/data/pizza.omn").read()
    onto1 = parse(doc)
    text = render(onto1, prefixes=_FIDELITY_PREFIXES)
    onto2 = parse(text)

    iris1 = {c.iri for c in onto1.classes()}
    iris2 = {c.iri for c in onto2.classes()}
    assert iris1 == iris2

    op1 = {p.iri for p in onto1.object_properties()}
    op2 = {p.iri for p in onto2.object_properties()}
    assert op1 == op2

    dp1 = {p.iri for p in onto1.data_properties()}
    dp2 = {p.iri for p in onto2.data_properties()}
    assert dp1 == dp2

    ind1 = {i.iri for i in onto1.individuals()}
    ind2 = {i.iri for i in onto2.individuals()}
    assert ind1 == ind2

    for iri in iris1:
        c1, c2 = onto1.world[iri], onto2.world[iri]
        supers1 = [s for s in c1.is_a if s is not owlready2.Thing]
        supers2 = [s for s in c2.is_a if s is not owlready2.Thing]
        assert len(supers1) == len(supers2), f"is_a mismatch for {iri}"
        assert len(c1.equivalent_to) == len(c2.equivalent_to), \
            f"equivalent_to mismatch for {iri}"


def test_full_pizza_document_idempotent_on_second_pass():
    doc = open("tests/data/pizza.omn").read()
    text1 = render(parse(doc), prefixes=_FIDELITY_PREFIXES)
    text2 = render(parse(text1), prefixes=_FIDELITY_PREFIXES)
    assert text1 == text2


def test_render_escapes_double_quote_in_string_literal(onto):
    # Round-trip a class with an annotation that contains a literal ``"``.
    # Pre-fix: the renderer emitted the raw ``"`` which broke the frame/section
    # tokeniser on re-parse and triggered an owlready2 inheritance cycle via
    # mis-attributed SubPropertyOf operands.
    doc = (
        'Prefix: : <http://ex.org/>\n'
        'Class: Pizza\n'
        '    Annotations: rdfs:label "called \\"pizza\\""\n'
    )
    onto1 = parse(doc)
    out = render(onto1)
    # The escaped form must survive on render.
    assert '\\"pizza\\"' in out
    # And it must round-trip cleanly (no cycle on the second parse).
    onto2 = parse(out)
    pizza = onto2.world["http://ex.org/Pizza"]
    assert pizza is not None
    assert any('"pizza"' in str(v) for v in (pizza.label or []))


def test_render_escapes_backslash_in_string_literal(onto):
    doc = (
        'Prefix: : <http://ex.org/>\n'
        'Class: WindowsPath\n'
        '    Annotations: rdfs:label "C:\\\\Users"\n'
    )
    onto1 = parse(doc)
    out = render(onto1)
    # The literal backslash must be escaped in the output.
    assert "C:\\\\Users" in out
    onto2 = parse(out)
    cls = onto2.world["http://ex.org/WindowsPath"]
    assert cls is not None
    assert any("C:\\Users" in str(v) for v in (cls.label or []))
