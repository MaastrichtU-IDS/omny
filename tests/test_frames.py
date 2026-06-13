import rdflib
import owlready2
import pytest
from omny import parse


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


def test_facts_typed_literal_not_dropped():
    """Issue #66 bug 1: a typed literal ``"1868"^^xsd:integer`` in a Facts
    clause must be parsed as a data-property assertion, not mis-tokenised
    as a CURIE (which dropped the whole Individual frame with a warning).
    """
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    DataProperty: :hasBirthYear
    Individual: :alice
        Facts: :hasBirthYear "1868"^^xsd:integer
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any UserWarning -> failure
        onto = parse(doc)
    alice = onto.world["http://ex.org/alice"]
    assert alice is not None
    assert alice.hasBirthYear == [1868]
    assert isinstance(alice.hasBirthYear[0], int)


def test_facts_typed_literal_string_decimal_boolean():
    """Other typed-literal datatypes coerce to the right Python value."""
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    DataProperty: :s
    DataProperty: :d
    DataProperty: :b
    Individual: :x
        Facts: :s "hi"^^xsd:string, :d "3.5"^^xsd:decimal, :b "true"^^xsd:boolean
    """
    onto = parse(doc)
    x = onto.world["http://ex.org/x"]
    assert x.s == ["hi"]
    assert x.d == [3.5]
    assert x.b == [True]


def test_facts_lang_tagged_literal():
    """A language-tagged literal ``"hej"@sv`` in Facts is preserved as a
    locstr with its language tag (round-trips through render)."""
    doc = """
    Prefix: : <http://ex.org/>
    DataProperty: :label
    Individual: :x
        Facts: :label "hej"@sv
    """
    onto = parse(doc)
    x = onto.world["http://ex.org/x"]
    assert str(x.label[0]) == "hej"
    assert x.label[0].lang == "sv"


def test_subpropertychain_parsed():
    """Issue #66 bug 2: ``SubPropertyChain: :p o :q`` on ObjectProperty :r
    yields a property chain (:p o :q) on :r, not an unknown-keyword warning.
    """
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: :p
    ObjectProperty: :q
    ObjectProperty: :r
        SubPropertyChain: :p o :q
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        onto = parse(doc)
    r = onto.world["http://ex.org/r"]
    assert r is not None
    chains = [[link.iri for link in c.properties] for c in r.property_chain]
    assert chains == [["http://ex.org/p", "http://ex.org/q"]]


def test_subpropertychain_three_links_roundtrip():
    """A longer chain renders back to a ``SubPropertyChain:`` line."""
    from omny import render
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: :a
    ObjectProperty: :b
    ObjectProperty: :c
    ObjectProperty: :r
        SubPropertyChain: :a o :b o :c
    """
    onto = parse(doc)
    r = onto.world["http://ex.org/r"]
    chains = [[link.iri for link in c.properties] for c in r.property_chain]
    assert chains == [["http://ex.org/a", "http://ex.org/b", "http://ex.org/c"]]
    out = render(onto, prefixes={"": "http://ex.org/"})
    assert "SubPropertyChain: :a o :b o :c" in out


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


def test_annotation_property_punning_does_not_raise():
    """OWL 2 punning: the same IRI may be used as both an object property
    AND an annotation property (real example: OBO's ``RO_0002433`` in
    the Human Phenotype Ontology). omny must accept this without
    erroring — the annotation value is stored via owlready2's IRI-keyed
    ``prop[entity]`` view, which keeps the two uses' values apart.

    Earlier (PR #25) the loader raised on this case to prevent same-
    local-name collisions between two distinct annotation properties
    (e.g. ``rdfs:comment`` vs ``schema.org/comment``); that collision is
    now prevented by the IRI-keyed write itself in
    ``_append_property_value``, so the raise is no longer needed and
    actively blocks legitimate ontologies (HP, OBI, sio).
    """
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: rel
    Class: C
        Annotations: rel "punned"
    """
    import rdflib
    onto = parse(doc)
    C = onto.world["http://ex.org/C"]
    rel = onto.world["http://ex.org/rel"]
    assert C is not None and rel is not None
    # The value is stored as a bare data triple bypassing owlready2's
    # ObjectProperty callback machinery; check the RDF graph directly.
    g = onto.world.as_rdflib_graph()
    found = list(g.triples(
        (rdflib.URIRef("http://ex.org/C"),
         rdflib.URIRef("http://ex.org/rel"),
         None),
    ))
    assert any(str(t[2]) == "punned" for t in found), f"got {found}"


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


def test_subclassof_named_and_anonymous_parents_mixed():
    """Regression for the direct-write SubClassOf path: when a Class frame
    mixes named-class parents (which go through
    ``_direct_write_subclassof`` → triple store + lazy reload) with
    anonymous-restriction parents (which stay on the per-item
    ``_safe_append_is_a`` path), both kinds must end up in ``is_a``
    after the end-of-parse invalidation pass.
    """
    doc = """
    Prefix: : <http://ex.org/>
    Class: Pizza
    Class: Topping
    Class: Cheese
        SubClassOf: Topping
    ObjectProperty: hasTopping
    Class: Margherita
        SubClassOf: Pizza, Cheese, hasTopping some Cheese, hasTopping only Cheese
    """
    onto = parse(doc)
    m = onto.world["http://ex.org/Margherita"]
    pizza = onto.world["http://ex.org/Pizza"]
    cheese = onto.world["http://ex.org/Cheese"]
    # Both named-class parents (direct-write path) must be present.
    assert pizza in m.is_a, "named parent Pizza missing from is_a (direct-write path)"
    assert cheese in m.is_a, "named parent Cheese missing from is_a (direct-write path)"
    # Both anonymous restrictions (per-item path) must still be present.
    restrictions = [sc for sc in m.is_a if getattr(sc, "property", None) is not None]
    assert len(restrictions) == 2, (
        f"expected 2 anonymous restrictions in is_a, got {len(restrictions)}: {m.is_a}"
    )


def test_individual_types_named_and_anonymous_mixed():
    """Regression for the direct-write rdf:type path on Individual frames:
    when ``Types:`` mixes named-class targets (which go through
    ``_direct_write_rdf_type`` → triple store + lazy reload) with
    anonymous-restriction targets (which stay on the per-item
    ``is_a.append`` path), both kinds must end up in ``ind.is_a`` after
    the end-of-parse invalidation pass.
    """
    doc = """
    Prefix: : <http://ex.org/>
    Class: Pizza
    Class: Topping
    Class: Cheese
        SubClassOf: Topping
    ObjectProperty: hasTopping
    Individual: m1
        Types: Pizza, Cheese, hasTopping some Cheese
    """
    onto = parse(doc)
    m1 = onto.world["http://ex.org/m1"]
    pizza = onto.world["http://ex.org/Pizza"]
    cheese = onto.world["http://ex.org/Cheese"]
    # Both named-class types (direct-write path) must be present.
    assert pizza in m1.is_a, "named type Pizza missing from is_a (direct-write path)"
    assert cheese in m1.is_a, "named type Cheese missing from is_a (direct-write path)"
    # Anonymous restriction type (per-item path) must still be present.
    restrictions = [t for t in m1.is_a if getattr(t, "property", None) is not None]
    assert len(restrictions) == 1, (
        f"expected 1 anonymous restriction in is_a, got {len(restrictions)}: {m1.is_a}"
    )


def test_annotation_alias_predicate_identity_preserved():
    """The ``rdfs:label`` / ``rdfs:comment`` shorthand forms (and the bare
    ``label`` / ``comment`` aliases) must write triples under the actual
    rdfs IRI — not under whichever ``python_name``-aliased annotation
    property owlready2 happens to bind to the ``.label`` / ``.comment``
    attribute.

    Regression: pre-fix ``_apply_annotations`` did
    ``entity.label.append(value)`` for the shorthand cases, which owlready2
    routes through ``setattr(entity, "label", …)``. If the doc had
    *also* declared e.g. ``<http://schema.org/label>`` (same
    ``python_name="label"``), the .label binding pointed to schema:label
    and the value ended up under that predicate instead of rdfs:label.
    """
    import rdflib
    doc = """
    Prefix: : <http://ex.org/>
    Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    Prefix: schema: <http://schema.org/>
    AnnotationProperty: schema:comment
    AnnotationProperty: schema:label
    Class: A
        Annotations: rdfs:comment "from-rdfs-c", label "from-bare-label"
    Class: B
        Annotations: schema:comment "from-schema-c", schema:label "from-schema-l"
    """
    onto = parse(doc)
    g = onto.world.as_rdflib_graph()
    A = rdflib.URIRef("http://ex.org/A")
    B = rdflib.URIRef("http://ex.org/B")
    RDFS_C = rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#comment")
    RDFS_L = rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#label")
    SCHEMA_C = rdflib.URIRef("http://schema.org/comment")
    SCHEMA_L = rdflib.URIRef("http://schema.org/label")

    # Each value lands under its actual predicate.
    assert (A, RDFS_C, rdflib.Literal("from-rdfs-c")) in g, \
        "rdfs:comment shorthand did not write under rdfs:comment IRI"
    assert (A, RDFS_L, rdflib.Literal("from-bare-label")) in g, \
        "bare 'label' did not write under rdfs:label IRI"
    assert (B, SCHEMA_C, rdflib.Literal("from-schema-c")) in g
    assert (B, SCHEMA_L, rdflib.Literal("from-schema-l")) in g

    # And no cross-routing — values must not appear under the wrong predicate.
    assert (A, SCHEMA_C, rdflib.Literal("from-rdfs-c")) not in g, \
        "rdfs:comment value leaked into schema:comment (alias-collision bug)"
    assert (A, SCHEMA_L, rdflib.Literal("from-bare-label")) not in g, \
        "bare 'label' value leaked into schema:label (alias-collision bug)"


def test_annotation_properties_with_same_local_name_do_not_collide():
    """Distinct annotation properties whose IRIs share a local name (e.g.
    ``rdfs:comment`` and ``schema.org/comment`` both alias ``entity.comment``)
    must be stored independently. Pre-fix, ``_append_property_value`` used
    ``setattr(entity, "comment", ...)`` which routed both values into the
    same list, and round-tripping a rendered ontology would duplicate every
    such pair on each cycle (sio.omn: 10 512 → 14 633 → 22 875 annotation
    pairs across three rounds).
    """
    doc = """
    Prefix: : <http://ex.org/>
    AnnotationProperty: <http://www.w3.org/2000/01/rdf-schema#comment>
    AnnotationProperty: <http://schema.org/comment>
    Class: A
        Annotations: <http://www.w3.org/2000/01/rdf-schema#comment> "rdfs side",
                     <http://schema.org/comment> "schema side"
    """
    onto = parse(doc)
    A = onto.world["http://ex.org/A"]
    rdfs_comment = onto.world["http://www.w3.org/2000/01/rdf-schema#comment"]
    schema_comment = onto.world["http://schema.org/comment"]
    # Each property carries exactly its own value — no cross-pollination.
    assert list(rdfs_comment[A]) == ["rdfs side"]
    assert list(schema_comment[A]) == ["schema side"]


def test_round_trip_does_not_duplicate_annotations():
    """Parse → render → parse → render must reach a fixed point (idempotent
    from the second render onward), not grow each cycle."""
    import omny
    doc = """
    Prefix: : <http://ex.org/>
    AnnotationProperty: <http://www.w3.org/2000/01/rdf-schema#comment>
    AnnotationProperty: <http://schema.org/comment>
    AnnotationProperty: <http://purl.org/dc/elements/1.1/description>
    AnnotationProperty: <http://purl.org/dc/terms/description>
    Class: A
        Annotations: <http://www.w3.org/2000/01/rdf-schema#comment> "rdfs c",
                     <http://schema.org/comment> "schema c",
                     <http://purl.org/dc/elements/1.1/description> "dc d",
                     <http://purl.org/dc/terms/description> "terms d"
    """
    o1 = omny.parse(doc)
    r1 = omny.render(o1)
    o2 = omny.parse(r1)
    r2 = omny.render(o2)
    o3 = omny.parse(r2)
    r3 = omny.render(o3)
    # The renderer reaches a fixed point — neither round-trip duplicates.
    assert r2 == r3
    # And the second pass's annotation count isn't bigger than the first's.
    assert r2.count("Annotations:") == r1.count("Annotations:")
    assert r2.count("comment") <= r1.count("comment") * 2  # nothing exponential


def test_axiom_keyword_does_not_leak_into_previous_section():
    """Regression: an axiom keyword inside a frame body must terminate the
    preceding section, not silently extend it.

    Pre-fix, ``_split_sections`` only used *known* section matches as
    boundaries, so a keyword that wasn't yet recognised concatenated into the
    prior operand list. With sio.omn, the ``SubPropertyOf:`` operand became a
    multi-line ``sio:SIO_000322\\n    SubPropertyChain:\\n        sio:...``
    string, which was then handed to ``get_object_property`` and turned
    into a malformed entity IRI containing literal newlines + Manchester
    text. owlready2's N-Triples writer faithfully serialised that IRI,
    and pyoxigraph rejected the load.

    ``SubPropertyChain:`` is now a recognised keyword (issue #66), so this
    also asserts the chain itself is parsed; the leak-prevention is still
    exercised via the ``SubPropertyOf:``/``Characteristics:`` boundaries.
    """
    doc = """
    Prefix: : <http://ex.org/>
    ObjectProperty: p1
        SubPropertyOf: q1
        SubPropertyChain: :a o :b
        Characteristics: Symmetric
    ObjectProperty: q1
    Class: A
    Class: B
    """
    onto = parse(doc)
    p1 = onto.world["http://ex.org/p1"]
    q1 = onto.world["http://ex.org/q1"]
    assert p1 is not None and q1 is not None
    # p1 has q1 as a USER-declared super-property; everything else in is_a is
    # an owlready2 base / characteristic mixin (e.g. ObjectProperty,
    # SymmetricProperty). The point: no malformed multi-line entity is picked
    # up as a super-property.
    user_supers = [s for s in p1.is_a
                   if hasattr(s, "iri") and s.iri.startswith("http://ex.org/")]
    assert [s.iri for s in user_supers] == ["http://ex.org/q1"]
    # No entity in the world has a newline or "SubPropertyChain" in its IRI.
    for e in list(onto.classes()) + list(onto.object_properties()):
        assert "\n" not in e.iri
        assert "SubPropertyChain" not in e.iri
    # Characteristics: section still parsed correctly (the chain keyword did
    # not consume it).
    assert owlready2.SymmetricProperty in p1.is_a
    # SubPropertyChain: parsed into a property chain of :a o :b.
    chains = [[link.iri for link in c.properties] for c in p1.property_chain]
    assert chains == [["http://ex.org/a", "http://ex.org/b"]]
