import io
from pathlib import Path

import pyoxigraph
import pytest
import rdflib

import omny
from omny import parse, class_relations_query
from omny.store import run_rdflib, run_pyoxigraph


def _build_doc():
    return """
    Prefix: : <http://ex.org/>
    Class: Food
    Class: Pizza SubClassOf: Food
    Class: Margherita
        SubClassOf: Pizza, hasTopping some Cheese
    Class: Cheese
    Individual: myMargherita Types: Margherita
    """


def _rdflib_graph():
    onto = parse(_build_doc())
    data = onto.world.as_rdflib_graph().serialize(format="turtle")
    g = rdflib.Graph()
    g.parse(data=data, format="turtle")
    return g


def _oxigraph_store():
    # owlready2 -> pyoxigraph WITHOUT an rdflib bridge: owlready2 serialises
    # N-Triples natively, pyoxigraph loads them.
    onto = parse(_build_doc())
    buf = io.BytesIO()
    onto.save(file=buf, format="ntriples")
    store = pyoxigraph.Store()
    store.load(buf.getvalue(), format=pyoxigraph.RdfFormat.N_TRIPLES)
    return store


def test_transitive_super_both_engines():
    q = class_relations_query("<http://ex.org/Margherita>", relations=("super",))
    g = run_rdflib(q, _rdflib_graph())
    supers = {str(s) for s, p, o in g if str(p).endswith("subClassOf")}
    assert {"http://ex.org/Margherita", "http://ex.org/Pizza"} <= supers
    ox = list(run_pyoxigraph(q, _oxigraph_store()))
    assert len(ox) > 0


def test_anonymous_superclass_subgraph_returned():
    q = class_relations_query("<http://ex.org/Margherita>", relations=("super",))
    g = run_rdflib(q, _rdflib_graph())
    owl_some = rdflib.URIRef("http://www.w3.org/2002/07/owl#someValuesFrom")
    assert any(p == owl_some for _, p, _ in g)


def test_direct_super_excludes_transitive():
    q = class_relations_query("<http://ex.org/Margherita>", relations=("direct_super",),
                              construct=False)
    rows = run_rdflib(q, _rdflib_graph())
    iris = {str(r[0]) for r in rows}
    assert "http://ex.org/Pizza" in iris
    assert "http://ex.org/Food" not in iris  # Food is indirect


def test_individual_retrieval():
    q = class_relations_query("<http://ex.org/Margherita>", relations=("individual",),
                              construct=False)
    rows = run_rdflib(q, _rdflib_graph())
    assert any("myMargherita" in str(r[0]) for r in rows)


def test_select_super_returns_only_iris():
    q = class_relations_query("<http://ex.org/Margherita>", relations=("super",), construct=False)
    rows = run_rdflib(q, _rdflib_graph())
    assert rows  # non-empty
    assert all(isinstance(r[0], rdflib.URIRef) for r in rows)  # no blank nodes


def test_direct_sub_excludes_transitive():
    # Food's direct subclass is Pizza; Margherita is indirect.
    q = class_relations_query("<http://ex.org/Food>", relations=("direct_sub",), construct=False)
    rows = run_rdflib(q, _rdflib_graph())
    iris = {str(r[0]) for r in rows}
    assert "http://ex.org/Pizza" in iris
    assert "http://ex.org/Margherita" not in iris


def test_flat_role_encoding_matches_flat_triples():
    """role_encoding='flat' answers role-restriction queries over a flat role
    encoding (direct ?c <prop> <val> triples, no owl:Restriction bnodes), the
    way SNOMED CT is stored. Structural mode finds nothing in such a graph."""
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: site
        ObjectProperty: morph
        Class: Heart
        Class: Lung
        Class: Organ
        Class: Swelling
    """)
    NS = "http://ex.org/"
    PFX = {"": NS, "owl": "http://www.w3.org/2002/07/owl#",
           "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}
    # FLAT data: roles as direct triples; Heart/Lung are subclasses of Organ.
    g = rdflib.Graph()
    g.parse(data="""
        @prefix ex: <http://ex.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        ex:Heart rdfs:subClassOf ex:Organ .  ex:Lung rdfs:subClassOf ex:Organ .
        ex:A ex:site ex:Heart .
        ex:B ex:site ex:Lung ;  ex:morph ex:Swelling .
        ex:C ex:site ex:Heart ; ex:site ex:Lung .
    """, format="turtle")
    store = pyoxigraph.Store()
    store.load(io.BytesIO(g.serialize(format="nt").encode()),
               format=pyoxigraph.RdfFormat.N_TRIPLES)

    def run(expr_text, **kw):
        expr = omny.parse_expression(expr_text, onto, prefixes=PFX)
        q = class_relations_query(expr, construct=False, **kw)
        return {str(s["rel"]).strip("<>") for s in run_pyoxigraph(q, store)}

    def L(*xs):
        return {NS + x for x in xs}

    assert run("site some owl:Thing", role_encoding="flat") == L("A", "B", "C")
    assert run("site some Organ", role_encoding="flat") == L("A", "B", "C")  # filler subsumption
    assert run("site some Heart", role_encoding="flat") == L("A", "C")
    assert run("site min 2 owl:Thing", role_encoding="flat") == L("C")
    assert run("site some owl:Thing and morph some owl:Thing",
               role_encoding="flat") == L("B")
    assert run("site some owl:Thing and not (morph some owl:Thing)",
               role_encoding="flat") == L("A", "C")
    # Structural mode finds nothing: there are no owl:Restriction bnodes here.
    assert run("site some owl:Thing", role_encoding="structural") == set()


def _pizza_onto():
    text = Path("tests/data/pizza.omn").read_text()
    return omny.parse(text)


def _pyox_store(onto):
    nt = onto.world.as_rdflib_graph().serialize(format="nt").encode()
    store = pyoxigraph.Store()
    store.load(io.BytesIO(nt), format=pyoxigraph.RdfFormat.N_TRIPLES)
    return store


# pizza.omn declares ``Prefix: : <http://ex.org/>`` so its classes live under
# ``http://ex.org/``, but the ontology IRI ``<http://ex.org/pizza.owl>`` makes
# ``onto.base_iri`` ``http://ex.org/pizza.owl#``.  parse_expression resolves
# unqualified names against ``onto.base_iri`` by default, which would point at
# phantom classes that don't exist in the data.  Passing ``prefixes={"": ...}``
# overrides that and resolves names to the actual classes in the graph.
_PIZZA_NS = {"": "http://ex.org/"}


def test_anonymous_equiv_finds_named_class_rdflib():
    onto = _pizza_onto()
    # Margherita EquivalentTo: hasTopping only (Cheese or Tomato)
    expr = omny.parse_expression(
        "hasTopping only (Cheese or Tomato)", onto, prefixes=_PIZZA_NS
    )
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    rows = {str(r[0]) for r in run_rdflib(q, onto.world.as_rdflib_graph())}
    assert "http://ex.org/Margherita" in rows


def test_anonymous_equiv_finds_named_class_pyoxigraph():
    onto = _pizza_onto()
    expr = omny.parse_expression(
        "hasTopping only (Cheese or Tomato)", onto, prefixes=_PIZZA_NS
    )
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    store = _pyox_store(onto)
    rows = {str(s["rel"]).strip("<>") for s in run_pyoxigraph(q, store)}
    assert "http://ex.org/Margherita" in rows


@pytest.mark.xfail(
    reason="Anonymous targets containing intersection/union/oneOf now match "
    "operands as an unordered set (rdf:rest*/rdf:first + FILTER NOT EXISTS). "
    "owlready2's built-in SPARQL engine does not support property paths or "
    "NOT EXISTS, so this query must run on rdflib/pyoxigraph/an endpoint "
    "instead (see test_anonymous_equiv_pyoxigraph_select).",
    raises=ValueError,
    strict=True,
)
def test_anonymous_equiv_owlready2_select():
    onto = _pizza_onto()
    expr = omny.parse_expression(
        "hasTopping only (Cheese or Tomato)", onto, prefixes=_PIZZA_NS
    )
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    from omny.store import run_owlready2
    rows = {r[0].iri for r in run_owlready2(q, onto.world)}
    assert "http://ex.org/Margherita" in rows


def test_equiv_both_directions():
    q = class_relations_query("<http://ex.org/A>", relations=("equiv",), construct=False)
    g = rdflib.Graph()
    g.parse(data="""
        @prefix ex: <http://ex.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        ex:A owl:equivalentClass ex:B .
        ex:C owl:equivalentClass ex:A .
    """, format="turtle")
    iris = {str(r[0]) for r in run_rdflib(q, g)}
    assert {"http://ex.org/B", "http://ex.org/C"} <= iris
