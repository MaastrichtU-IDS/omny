import pytest

import omny
from omny.pattern import expression_to_pattern


def _norm(s):
    return " ".join(s.split())


def _parse(expr_text):
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        ObjectProperty: hasTopping
        Class: Drug
        Class: Disease
        Class: Cheese
        Class: Tomato
    """)
    return onto, omny.parse_expression(expr_text, onto)


def test_some_values_from():
    onto, expr = _parse("treats some Drug")
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Drug> ."
    )


def test_all_values_from():
    onto, expr = _parse("treats only Drug")
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:allValuesFrom <http://ex.org/Drug> ."
    )


def test_has_value_individual():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
        Individual: myCheese Types: Cheese
    """)
    expr = omny.parse_expression("hasTopping value myCheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:hasValue <http://ex.org/myCheese> ."
    )


def test_self_restriction():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasPart
    """)
    expr = omny.parse_expression("hasPart Self", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasPart> ; "
        "owl:hasSelf true ."
    )


def test_qualified_exactly():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
    """)
    expr = omny.parse_expression("hasTopping exactly 2 Cheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        '?t0 a owl:Restriction ; '
        'owl:onProperty <http://ex.org/hasTopping> ; '
        'owl:qualifiedCardinality "2"^^xsd:nonNegativeInteger ; '
        'owl:onClass <http://ex.org/Cheese> .'
    )


def test_unqualified_min():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
    """)
    with onto:
        p = onto.search_one(iri="http://ex.org/hasTopping")
        expr = p.min(1)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        '?t0 a owl:Restriction ; '
        'owl:onProperty <http://ex.org/hasTopping> ; '
        'owl:minCardinality "1"^^xsd:nonNegativeInteger .'
    )


def test_qualified_max():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
    """)
    expr = omny.parse_expression("hasTopping max 3 Cheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        '?t0 a owl:Restriction ; '
        'owl:onProperty <http://ex.org/hasTopping> ; '
        'owl:maxQualifiedCardinality "3"^^xsd:nonNegativeInteger ; '
        'owl:onClass <http://ex.org/Cheese> .'
    )


def test_intersection_two_named():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        Class: A
        Class: B
    """)
    expr = omny.parse_expression("A and B", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:intersectionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/A> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/B> ; rdf:rest rdf:nil ."
    )


def test_intersection_named_and_anonymous():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
        Class: Disease
    """)
    expr = omny.parse_expression("Drug and (treats some Disease)", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    # ?t0 = intersection node; ?t1 / ?t2 = list spine; ?t3 = nested someValuesFrom restriction.
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:intersectionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/Drug> ; rdf:rest ?t2 . "
        "?t2 rdf:first ?t3 ; rdf:rest rdf:nil . "
        "?t3 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Disease> ."
    )


def test_union_two_named():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        Class: A
        Class: B
    """)
    expr = omny.parse_expression("A or B", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:unionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/A> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/B> ; rdf:rest rdf:nil ."
    )


def test_complement_named():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        Class: A
    """)
    expr = omny.parse_expression("not A", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:complementOf <http://ex.org/A> ."
    )


def test_complement_anonymous():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
    """)
    expr = omny.parse_expression("not (treats some Drug)", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:complementOf ?t1 . "
        "?t1 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Drug> ."
    )


def test_inverse_property_some():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasPart
        Class: A
    """)
    expr = omny.parse_expression("inverse hasPart some A", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    # ?t1 is the inverse-property blank node bound to owl:onProperty.
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty ?t1 ; "
        "owl:someValuesFrom <http://ex.org/A> . "
        "?t1 owl:inverseOf <http://ex.org/hasPart> ."
    )


def test_one_of():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        Class: Cheese
        Class: Tomato
        Individual: a Types: Cheese
        Individual: b Types: Tomato
    """)
    expr = omny.parse_expression("{a, b}", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:oneOf ?t1 . "
        "?t1 rdf:first <http://ex.org/a> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/b> ; rdf:rest rdf:nil ."
    )


def test_unsupported_construct_raises_value_error():
    # ConstrainedDatatype is deferred per the design spec — must raise ValueError.
    import owlready2
    cd = owlready2.ConstrainedDatatype(int, min_inclusive=0, max_inclusive=10)
    with pytest.raises(ValueError, match="not supported"):
        expression_to_pattern(cd)


def test_has_value_with_literal_raises():
    onto = omny.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        DataProperty: age
    """)
    expr = omny.parse_expression("age value 42", onto)
    with pytest.raises(ValueError, match="literal"):
        expression_to_pattern(expr)
