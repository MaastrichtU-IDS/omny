"""Manchester-syntax + class-relation tests on the owlapy 'family' ontology,
recreated for omny's public API.

Ported from the owlready2-fork script test_manchester_owlapy.py (which used the
fork's to_manchester / parse_manchester_expression / classes_matching /
instances_of). Here we use omny's equivalents:

  to_manchester(ce)               -> omny.render_expression(ce, prefixes)
  parse_manchester_expression     -> omny.parse_expression(text, onto, prefixes)
  manchester_render_ontology      -> omny.render(onto, prefixes)
  parse_manchester_ontology       -> omny.parse(doc)
  classes_matching / instances_of -> omny.class_relations_query(...) over a store
"""
import io

import owlready2
import pyoxigraph
import pytest
from owlready2 import (World, Thing, ObjectProperty, And, Or, Not,
                       SOME, ONLY, MIN, MAX, EXACTLY, OneOf)

import omny
from omny import class_relations_query, parse_expression, render_expression
from omny.store import run_rdflib, run_pyoxigraph

NS = "http://example.com/family#"
PFX = {"": NS}


@pytest.fixture(scope="module")
def family():
    """The owlapy family ontology with parent/father defined classes."""
    w = World()
    onto = w.get_ontology(NS)
    with onto:
        class person(Thing): pass
        class male(person): pass
        class female(person): pass
        class hasChild(ObjectProperty): pass

        class parent(person):
            equivalent_to = [person & hasChild.some(person)]

        class father(male):
            equivalent_to = [male & hasChild.some(person)]

        female("anna"); male("markus"); female("michelle")
        male("martin"); male("heinz"); female("marta")
    return w, onto


@pytest.fixture(scope="module")
def names(family):
    _, onto = family
    g = {e.name: e for e in onto.classes()}
    g.update({p.name: p for p in onto.object_properties()})
    g.update({i.name: i for i in onto.individuals()})
    return g


def _pm(text, onto):
    return parse_expression(text, onto, prefixes=PFX)


# ── 1. Render (serializer) ──────────────────────────────────────────────────────
def test_render_constructs(names):
    male, female, person, hasChild = (names[n] for n in
                                      ("male", "female", "person", "hasChild"))

    def r(ce):
        return render_expression(ce, prefixes=PFX)

    assert r(hasChild.some(male)) == ":hasChild some :male"
    assert r(hasChild.only(person)) == ":hasChild only :person"
    assert r(hasChild.min(1, person)) == ":hasChild min 1 :person"
    assert r(male & hasChild.min(1, person)) == ":male and :hasChild min 1 :person"
    assert r((male | female) & person) == "(:male or :female) and :person"
    assert r(Not(male | female)) == "not (:male or :female)"
    oneof = r(OneOf([names["anna"], names["markus"]]))
    assert oneof.startswith("{") and ":anna" in oneof and ":markus" in oneof


# ── 2. Parse (structure) ─────────────────────────────────────────────────────────
def test_parse_and_min(family, names):
    _, onto = family
    e = _pm("male and (hasChild min 1 person)", onto)
    assert isinstance(e, And) and len(e.Classes) == 2
    assert names["male"] in e.Classes
    restr = next(c for c in e.Classes if isinstance(c, owlready2.Restriction))
    assert restr.type == MIN and restr.cardinality == 1 and restr.value is names["person"]


def test_parse_max_exactly(family, names):
    _, onto = family
    e = _pm("hasChild max 2 person", onto)
    assert e.type == MAX and e.cardinality == 2 and e.value is names["person"]
    e2 = _pm("hasChild exactly 2 person", onto)
    assert e2.type == EXACTLY and e2.cardinality == 2 and e2.value is names["person"]


def test_parse_some_only(family, names):
    _, onto = family
    e = _pm("hasChild some male", onto)
    assert isinstance(e, owlready2.Restriction)
    assert e.type == SOME and e.value is names["male"]
    e2 = _pm("hasChild only person", onto)
    assert e2.type == ONLY and e2.value is names["person"]


def test_parse_boolean_and_oneof(family, names):
    _, onto = family
    e = _pm("not (male and female)", onto)
    assert isinstance(e, Not) and isinstance(e.Class, And)
    e2 = _pm("(male or female) and person", onto)
    assert isinstance(e2, And) and any(isinstance(c, Or) for c in e2.Classes)
    e3 = _pm("{anna, markus}", onto)
    assert isinstance(e3, OneOf) and len(e3.instances) == 2
    assert names["anna"] in e3.instances and names["markus"] in e3.instances
    e4 = _pm("hasChild some {anna}", onto)
    assert e4.type == SOME and isinstance(e4.value, OneOf)


@pytest.mark.xfail(reason="omny's Manchester lexer requires a filler on "
                          "cardinality restrictions; bare `min 1` / `max 0` "
                          "(no filler) do not parse — use `min 1 owl:Thing`.",
                   raises=Exception, strict=True)
def test_parse_unqualified_cardinality(family):
    _, onto = family
    _pm("hasChild min 1", onto)


# ── 3. Round-trip: render → parse → equal ───────────────────────────────────────
def test_roundtrip_expressions(family, names):
    _, onto = family
    male, female, person, hasChild = (names[n] for n in
                                      ("male", "female", "person", "hasChild"))
    exprs = [
        hasChild.some(male), hasChild.only(person),
        hasChild.min(1, person), hasChild.max(2, person), hasChild.exactly(1, person),
        male & female, male | female, Not(male),
        male & hasChild.min(1, person), female & hasChild.max(2, person),
        Not(male | female),
    ]
    for ce in exprs:
        assert _pm(render_expression(ce, prefixes=PFX), onto) == ce


# ── 4. Document round-trip via omny.parse / omny.render ─────────────────────────
def test_document_roundtrip(family):
    _, onto = family
    doc = omny.render(onto, prefixes=PFX)
    reparsed = omny.parse(doc)
    cls_names = {c.name for c in reparsed.classes()}
    assert {"person", "male", "female", "parent", "father"} <= cls_names
    assert omny.render(reparsed, prefixes=PFX) == doc  # idempotent


# ── 5. Class relations (replaces classes_matching / instances_of) ───────────────
def _store(onto, kind):
    nt = onto.world.as_rdflib_graph().serialize(format="nt").encode()
    if kind == "pyoxigraph":
        s = pyoxigraph.Store()
        s.load(io.BytesIO(nt), format=pyoxigraph.RdfFormat.N_TRIPLES)
        return s
    import rdflib
    g = rdflib.Graph()
    g.parse(data=nt, format="nt")
    return g


def _run(q, store, kind):
    if kind == "pyoxigraph":
        res = run_pyoxigraph(q, store)
        var = res.variables[0]
        return {str(sol[var]).strip("<>").split("#")[-1] for sol in res}
    return {str(r[0]).strip("<>").split("#")[-1] for r in run_rdflib(q, store)}


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_subclasses(family, kind):
    _, onto = family
    store = _store(onto, kind)
    q = class_relations_query(f"<{NS}person>", relations=["sub"], construct=False)
    assert {"male", "female", "parent", "father"} <= _run(q, store, kind)


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_individuals(family, kind):
    _, onto = family
    store = _store(onto, kind)
    q = class_relations_query(f"<{NS}male>", relations=["individual"], construct=False)
    males = _run(q, store, kind)
    assert {"markus", "martin", "heinz"} <= males
    assert "anna" not in males  # anna is female


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_equivalent_class_matching(family, kind):
    """omny analogue of classes_matching: the defining expression of `parent`
    (person and hasChild some person) matches parent via owl:equivalentClass —
    exercising structural (unordered) intersection matching on proper OWL."""
    _, onto = family
    store = _store(onto, kind)
    expr = _pm("person and (hasChild some person)", onto)
    q = class_relations_query(expr, relations=["equiv"], construct=False)
    assert "parent" in _run(q, store, kind)
