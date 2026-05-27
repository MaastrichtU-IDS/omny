import io
import pyoxigraph
import rdflib

from pymos import parse, class_relations_query
from pymos.store import run_rdflib, run_pyoxigraph


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
