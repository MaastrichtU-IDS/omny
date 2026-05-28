import pymos
from pymos.pattern import expression_to_pattern


def _norm(s):
    return " ".join(s.split())


def _parse(expr_text):
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: treats
        ObjectProperty: hasTopping
        Class: Drug
        Class: Disease
        Class: Cheese
        Class: Tomato
    """)
    return onto, pymos.parse_expression(expr_text, onto)


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
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
        Individual: myCheese Types: Cheese
    """)
    expr = pymos.parse_expression("hasTopping value myCheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:hasValue <http://ex.org/myCheese> ."
    )


def test_self_restriction():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Ontology: <http://ex.org/>
        ObjectProperty: hasPart
    """)
    expr = pymos.parse_expression("hasPart Self", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasPart> ; "
        "owl:hasSelf true ."
    )
