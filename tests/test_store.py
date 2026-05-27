import rdflib
from pymos.store import run_rdflib, run_pyoxigraph


def _graph():
    g = rdflib.Graph()
    g.parse(data="""
        @prefix ex: <http://ex.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        ex:Margherita rdfs:subClassOf ex:Pizza .
        ex:Pizza rdfs:subClassOf ex:Food .
        ex:Food a owl:Class .
    """, format="turtle")
    return g


def test_run_rdflib_construct_returns_graph():
    from pymos.sparql import class_relations_query
    q = class_relations_query("<http://ex.org/Margherita>", relations=("super",))
    result = run_rdflib(q, _graph())
    assert isinstance(result, rdflib.Graph)
    subjects = {str(s) for s, _, _ in result}
    assert "http://ex.org/Pizza" in subjects
    assert "http://ex.org/Food" in subjects
