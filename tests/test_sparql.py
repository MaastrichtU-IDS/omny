import pytest
import rdflib  # noqa: F401

import omny
from omny.sparql import _relation_clause, _target_term, class_relations_query


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


def test_empty_relations_raises():
    with pytest.raises(ValueError):
        class_relations_query("<http://ex.org/X>", relations=())


def test_named_class_accepts_owlready_class(onto):
    from omny import parse_expression
    pizza = parse_expression("Pizza", onto)
    q = class_relations_query(pizza, relations=("super",))
    assert "<http://omny.test/onto.owl#Pizza>" in q


def test_target_term_named_string():
    var, extra = _target_term("<http://ex.org/Pizza>")
    assert var == "<http://ex.org/Pizza>"
    assert extra == ""


def test_target_term_owlready_entity():
    onto = omny.parse("Prefix: : <http://ex.org/>\nOntology: <http://ex.org/>\nClass: Pizza")
    pizza = onto.world["http://ex.org/Pizza"]
    var, extra = _target_term(pizza)
    assert var == "<http://ex.org/Pizza>"
    assert extra == ""


def test_target_term_anonymous_construct():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
    """)
    expr = omny.parse_expression("treats some Drug", onto)
    var, extra = _target_term(expr)
    assert var.startswith("?t")
    assert "owl:Restriction" in extra
    assert "owl:someValuesFrom <http://ex.org/Drug>" in extra


def test_anonymous_target_query_builds_and_parses():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
        Class: Disease
    """)
    expr = omny.parse_expression("Drug and (treats some Disease)", onto)
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    from rdflib.plugins.sparql import prepareQuery
    prepareQuery(q)  # must parse as valid SPARQL
    assert "owl:intersectionOf" in q
    assert "owl:someValuesFrom <http://ex.org/Disease>" in q
    # The equiv clause must use the bound target variable, not a literal IRI.
    assert "?t0 owl:equivalentClass" in q or "owl:equivalentClass ?t0" in q


def test_unsupported_target_type_raises():
    import pytest
    with pytest.raises(TypeError):
        class_relations_query(12345, relations=("equiv",))
