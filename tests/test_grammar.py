import pytest
from omny.grammar import MANCHESTER_GRAMMAR


@pytest.mark.parametrize("expr", [
    "Cheese",
    "hasTopping some Cheese",
    "hasTopping only Cheese",
    "hasTopping min 2 Cheese",
    "hasTopping value myCheese",
    "hasTopping Self",
    "A and (B or not C)",
    "{ a , b , c }",
    "inverse hasTopping some Cheese",
    "hasAge some xsd:integer[>= 18]",
    "<http://ex.org/A> and <http://ex.org/B>",
])
def test_grammar_parses_expression(expr):
    # parsimonious raises ParseError/IncompleteParseError on failure
    tree = MANCHESTER_GRAMMAR.parse(expr.strip())
    assert tree is not None
