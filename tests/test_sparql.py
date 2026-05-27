from pymos.sparql import _relation_clause


def _norm(s):
    return " ".join(s.split())


def test_super_transitive():
    c = _relation_clause("super", "<http://ex.org/Pizza>", "?rel")
    assert _norm(c) == _norm("<http://ex.org/Pizza> rdfs:subClassOf+ ?rel .")


def test_sub_transitive():
    c = _relation_clause("sub", "<http://ex.org/Pizza>", "?rel")
    assert _norm(c) == _norm("?rel rdfs:subClassOf+ <http://ex.org/Pizza> .")


def test_direct_super_has_redundancy_filter():
    c = _relation_clause("direct_super", "<http://ex.org/Pizza>", "?rel")
    assert "rdfs:subClassOf ?rel" in _norm(c)
    assert "FILTER NOT EXISTS" in c
    assert "?mid" in c


def test_equiv_both_directions():
    c = _relation_clause("equiv", "<http://ex.org/Pizza>", "?rel")
    assert "owl:equivalentClass ?rel" in c
    assert "?rel owl:equivalentClass" in c


def test_individual_rdf_type():
    c = _relation_clause("individual", "<http://ex.org/Pizza>", "?ind")
    assert _norm(c) == _norm("?ind rdf:type <http://ex.org/Pizza> .")


import rdflib  # noqa: F401
from pymos.sparql import class_relations_query


def test_construct_query_is_valid_sparql():
    q = class_relations_query("<http://ex.org/Pizza>", relations=("super", "equiv"))
    assert q.strip().startswith("PREFIX")
    assert "CONSTRUCT { ?s ?p ?o }" in q
    assert "rdfs:subClassOf+ ?rel" in q
    from rdflib.plugins.sparql import prepareQuery
    prepareQuery(q)


def test_select_mode_projects_iris():
    q = class_relations_query("<http://ex.org/Pizza>", relations=("sub",), construct=False)
    assert "SELECT DISTINCT ?rel" in q
    from rdflib.plugins.sparql import prepareQuery
    prepareQuery(q)


def test_named_class_accepts_owlready_class(onto):
    from pymos import parse_expression
    pizza = parse_expression("Pizza", onto)
    q = class_relations_query(pizza, relations=("super",))
    assert "<http://pymos.test/onto.owl#Pizza>" in q
