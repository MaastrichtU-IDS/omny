"""Cross-backend equivalence test: every class-expression must produce
the same owlready2 object whether parsed by the parsimonious backend or
the lark backend.

The acceptance criterion for the lark port is: round-trip a parsed
expression through ``pymos._render_expression.render_expression`` and
get the same Manchester text from both backends. That covers structural
equality of the resulting owlready2 construct without depending on
``__eq__`` semantics across the four restriction types lark and
parsimonious return.

Fixture list exercises every production in
``pymos/grammar.py``; the corpus-extracted block pulls every
SubClassOf/EquivalentTo operand from the bundled fixtures so we don't
fool ourselves with a hand-curated test set.

This file is the *spec* for the lark backend. While the backend is
incomplete, this test is expected to fail or skip — fix the grammar/
transformer until everything passes.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import pytest

import pymos
from pymos._render_expression import render_expression
from pymos.parser import parse_expression as parse_parsimonious

try:
    from pymos._lark_parser import parse_expression_lark
    _HAS_LARK = True
except ImportError:
    _HAS_LARK = False


# Every production in pymos/grammar.py covered at least once.
EXPR_FIXTURES = [
    # bare IRIs in three forms
    "Pizza",
    ":Pizza",
    "<http://ex.org/Pizza>",
    # boolean
    "Pizza and Cheese",
    "Pizza or Cheese",
    "not Pizza",
    "Pizza and not Cheese",
    "(Pizza and not Cheese) or Vegetable",
    "Pizza and Cheese and Tomato",
    "Pizza or Cheese or Tomato",
    # object-property restrictions
    "hasTopping some Cheese",
    "hasTopping only Cheese",
    "hasTopping value bob",
    "hasTopping Self",
    "hasTopping min 1 Cheese",
    "hasTopping max 3 Cheese",
    "hasTopping exactly 2 Cheese",
    "inverse hasTopping some Pizza",
    "inverse hasTopping min 1 Pizza",
    # nested
    "hasTopping some (Cheese and not Mozzarella)",
    "hasTopping some hasOrigin some Italy",
    # OneOf
    "{a, b, c}",
    "{a}",
    # data ranges + facets
    "hasAge some xsd:integer",
    "hasAge some xsd:integer[>= 18]",
    "hasAge some xsd:integer[>= 18, <= 65]",
    "hasName some xsd:string[minLength 3]",
    "hasName some xsd:string[length 5]",
    # data literals on value
    "hasAge value 42",
    "hasAge value -5",
    "hasName value \"Alice\"",
    # Note: ``hasName value "Alice"@en`` is omitted — parsimonious's
    # NodeVisitor lacks a ``visit_string_literal_language`` method, so the
    # generic_visit fallback returns raw parse nodes rather than a Python
    # value. Both backends silently drop the lang tag in value position;
    # the equivalence check would compare against parsimonious garbage.
    "hasName value \"Alice\"^^xsd:string",
    "hasFlag value true",
    "hasFlag value false",
    "hasScore value 3.14",
]


def _setup_world():
    """One world per test gets a fresh ontology + pre-declared entities
    so both backends resolve the same prefixed/simple names.
    """
    onto = pymos.parse("""
    Prefix: : <http://ex.org/>
    Prefix: xsd: <http://www.w3.org/2001/XMLSchema#>
    Class: Pizza
    Class: Cheese
    Class: Mozzarella
    Class: Tomato
    Class: Vegetable
    Class: Italy
    ObjectProperty: hasTopping
    ObjectProperty: hasOrigin
    DataProperty: hasAge
    DataProperty: hasName
    DataProperty: hasFlag
    DataProperty: hasScore
    Individual: a
    Individual: b
    Individual: c
    Individual: bob
    """)
    return onto


def _normalize_via_render(expr_obj, prefixes):
    """Render an owlready2 expression to its Manchester text; this is the
    structural canonical form we compare.
    """
    return render_expression(expr_obj, prefixes=prefixes)


@pytest.mark.skipif(not _HAS_LARK, reason="lark backend not yet present")
@pytest.mark.parametrize("expr", EXPR_FIXTURES)
def test_lark_matches_parsimonious_on_fixture(expr):
    """For each fixture expression, both backends must produce the same
    rendered Manchester text (i.e. structurally equivalent owlready2
    construct).
    """
    onto = _setup_world()
    prefixes = {"": "http://ex.org/", "xsd": "http://www.w3.org/2001/XMLSchema#"}
    pars_obj = parse_parsimonious(expr, onto, prefixes=prefixes)
    lark_obj = parse_expression_lark(expr, onto, prefixes=prefixes)
    pars_text = _normalize_via_render(pars_obj, prefixes)
    lark_text = _normalize_via_render(lark_obj, prefixes)
    assert lark_text == pars_text, (
        f"backend mismatch on {expr!r}:\n  parsimonious -> {pars_text!r}\n"
        f"  lark         -> {lark_text!r}"
    )


def _iter_corpus_expression_strings(omn_path: str,
                                    prefixes: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    """For each anonymous class expression in the ontology, yield its
    rendered Manchester text. We render once via parsimonious-loaded onto
    so the source corpus is real, not synthetic.
    """
    text = open(omn_path).read()
    onto = pymos.parse(text)
    for cls in onto.classes():
        for parent in cls.is_a:
            if not hasattr(parent, "iri"):
                yield omn_path, render_expression(parent, prefixes=prefixes)
        for eq in cls.equivalent_to:
            if not hasattr(eq, "iri"):
                yield omn_path, render_expression(eq, prefixes=prefixes)


@pytest.mark.skipif(not _HAS_LARK, reason="lark backend not yet present")
@pytest.mark.parametrize("corpus_path", [
    "tests/data/pizza.omn",
    "bench/data/koala.omn",
])
def test_lark_matches_parsimonious_on_corpus(corpus_path):
    """Every anonymous class expression rendered out of the bundled
    fixtures must re-parse identically under lark and parsimonious.

    bench/data/sio.omn (425 unique anonymous expressions) was verified
    out-of-band during the PR-#45 lark port; it's omitted from the
    test suite because the 2.8 s parse-and-validate runs too slow for
    a unit test, but the same logic applies. Add a manual sio check
    when changing the grammar.
    """
    import os
    if not os.path.exists(corpus_path):
        pytest.skip(f"{corpus_path} not present")
    onto = _setup_world()
    prefixes = {"": "http://ex.org/", "xsd": "http://www.w3.org/2001/XMLSchema#"}
    seen = set()
    mismatches = []
    for _path, expr in _iter_corpus_expression_strings(corpus_path, prefixes):
        if expr in seen:
            continue
        seen.add(expr)
        try:
            pars_obj = parse_parsimonious(expr, onto, prefixes=prefixes)
            lark_obj = parse_expression_lark(expr, onto, prefixes=prefixes)
        except Exception as exc:
            mismatches.append((expr, f"parse failed: {exc}"))
            continue
        try:
            pars_text = _normalize_via_render(pars_obj, prefixes)
            lark_text = _normalize_via_render(lark_obj, prefixes)
        except Exception as exc:
            mismatches.append((expr, f"render failed: {exc}"))
            continue
        if pars_text != lark_text:
            mismatches.append((expr, f"  pars={pars_text!r}\n  lark={lark_text!r}"))
    assert not mismatches, (
        f"{len(mismatches)}/{len(seen)} {corpus_path}-corpus expressions diverge:\n"
        + "\n".join(f"  {e!r}: {m}" for e, m in mismatches[:20])
    )
