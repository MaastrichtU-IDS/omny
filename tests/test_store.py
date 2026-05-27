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


def test_is_construct_helper():
    from pymos.store import _is_construct
    from pymos.sparql import class_relations_query
    assert _is_construct(class_relations_query("<http://ex.org/X>", relations=("super",)))
    assert not _is_construct(class_relations_query("<http://ex.org/X>", relations=("super",), construct=False))


def test_run_owlready2_select_works_and_construct_raises():
    import pytest
    import owlready2
    from pymos import parse, class_relations_query
    from pymos.store import run_owlready2
    onto = parse("""
    Prefix: : <http://ex.org/>
    Class: Food
    Class: Pizza SubClassOf: Food
    """)
    sel = class_relations_query("<http://ex.org/Pizza>", relations=("super",), construct=False)
    rows = run_owlready2(sel, onto.world)
    assert any("Food" in str(c) for r in rows for c in r)
    con = class_relations_query("<http://ex.org/Pizza>", relations=("super",))  # CONSTRUCT
    with pytest.raises(ValueError):
        run_owlready2(con, onto.world)


def test_run_rdflib_construct_returns_graph():
    from pymos.sparql import class_relations_query
    q = class_relations_query("<http://ex.org/Margherita>", relations=("super",))
    result = run_rdflib(q, _graph())
    assert isinstance(result, rdflib.Graph)
    subjects = {str(s) for s, _, _ in result}
    assert "http://ex.org/Pizza" in subjects
    assert "http://ex.org/Food" in subjects
