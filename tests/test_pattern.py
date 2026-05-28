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
