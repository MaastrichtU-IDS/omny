"""Smoke/regression tests: re-parse Manchester corpus strings from owlapy's test suite.

Each expression is parsed with pymos and asserted to return a non-None owlready2 object
without raising. Structural match to owlapy's model is NOT checked here.

DL-syntax strings (using ∃, ⊓, ⊔, ≥, ≤, =, ¬, ⊤, ⊥) are excluded as pymos
targets Manchester syntax only.
"""
import pytest
from pymos.parser import parse_expression

# Namespace matching the corpus strings (mutagenesis)
NS = "http://dl-learner.org/mutagenesis#"

# All Manchester-syntax strings extracted from _ref_owlapy/tests/test_owlapy_conversions.py
# ManchesterOWLSyntaxParserTest section. DL-syntax strings (⊓, ⊔, ∃, ∀, etc.) excluded.
CORPUS = [
    # test_union_intersection
    "Atom or Bond and Compound",
    "(Atom or Bond) and Compound",
    "((Atom or Bond) and Atom) and Compound or Bond",
    # test_thing_nothing
    "(hasBond some (Thing and Nothing)) and Nothing or Thing",
    # test_object_properties
    "inBond some Bond",
    "hasBond only Atom",
    "inBond some (hasBond some (Bond and Atom))",
    "inBond max 5 Bond",
    "inBond min 124 Atom",
    "inBond exactly 11 Bond",
    "inBond value d91_32",
    "inBond Self",
    "inverse inBond some Atom",
    "hasBond only {d91_32, d91_17, bond5225}",
    "(not (Atom or Bond) and Atom) and not Compound or (hasBond some (inBond max 4 Bond))",
    # test_data_properties_numeric
    "charge some xsd:integer[> 4]",
    "act only double",
    "charge some <http://www.w3.org/2001/XMLSchema#double>[> \"4.4\"^^xsd:double ⊓ < -32.5]",
    # Note: the ⊓ in facet_restrictions is intentional (grammar uses it there)
    "charge max 4 not (integer[> +4] and integer or xsd:integer[< \"1\"^^integer])",
    "charge min 25 (not (xsd:integer[> 9] and (xsd:integer or not xsd:integer[< \"6\"^^integer])))",
    "act exactly 11 xsd:integer[totalDigits \"5\"^^xsd:integer ⊓ > -100]",
    "charge value -11.1e100f",
    "charge only {.10e-001F, 1.1e0010f, 10f, 5}",
    # test_data_properties_boolean
    "hasFifeExamplesOfAcenthrylenes value \"true\"^^boolean",
    "hasFifeExamplesOfAcenthrylenes value false",
    "hasFifeExamplesOfAcenthrylenes some {true, false, \"false\"^^xsd:boolean}",
    # test_data_properties_string
    "charge value \"Test123\"^^xsd:string",
    'charge value "Test\\"123456"',
    # test_full_iri (Manchester-syntax subset)
    "<http://dl-learner.org/mutagenesis#hasBond> only <http://dl-learner.org/mutagenesis#Atom>",
    (
        "<http://dl-learner.org/mutagenesis#inBond> some "
        "(<http://dl-learner.org/mutagenesis#hasBond> some "
        "(<http://dl-learner.org/mutagenesis#Bond> and "
        "<http://dl-learner.org/mutagenesis#Atom>))"
    ),
    (
        "<http://dl-learner.org/mutagenesis#charge> value "
        '"Test123"^^<http://www.w3.org/2001/XMLSchema#string>'
    ),
    (
        "<http://dl-learner.org/mutagenesis#charge> max 4 not "
        "(<http://www.w3.org/2001/XMLSchema#integer>[> +4] and "
        "<http://www.w3.org/2001/XMLSchema#integer> or "
        "<http://www.w3.org/2001/XMLSchema#integer>[< "
        '"1"^^<http://www.w3.org/2001/XMLSchema#integer>])'
    ),
    (
        "<http://dl-learner.org/mutagenesis#hasBond> only "
        "{<http://dl-learner.org/mutagenesis#d91_32>, "
        "<http://dl-learner.org/mutagenesis#d91_17>, "
        "<http://dl-learner.org/mutagenesis#bond5225>}"
    ),
    # test_whitespace
    "    inBond   some    Bond",
    "( \n Atom or Bond\t)  and\nCompound  ",
    "hasBond only { \n\t d91_32,d91_17  ,    bond5225  }",
    "act only { \n\t 1.2f  ,    3.2f  }",
    "act some (  xsd:double[  > 5f ⊓ < 4.2f \n ⊓ <  -1.8e10f  ]\t and  integer )",
]


@pytest.mark.parametrize("expr", CORPUS)
def test_corpus_parses(onto, expr):
    """Each Manchester expression should parse to a non-None owlready2 object."""
    result = parse_expression(expr, onto,
                              prefixes={"xsd": "http://www.w3.org/2001/XMLSchema#"})
    assert result is not None
