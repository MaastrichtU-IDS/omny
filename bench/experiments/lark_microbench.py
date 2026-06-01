"""Lark vs parsimonious microbenchmark on a single Manchester expression.

Result on this host (2026-06-01, master at 1ca6765):
  parsimonious: ~2400 µs per parse
  lark (LALR):  ~444  µs per parse
  ratio: ~5.4×

Interpretation
--------------
At 5.4×, swapping parsimonious for lark would buy us roughly
``0.48 × 0.81 ≈ 39%`` reduction on total parse wall (parsimonious
is 48% of pymos.parse per cProfile of HP; lark replaces 80% of
that fraction). On HP: ~270 s → ~165 s. Real but not
transformative; the next ceiling is owlready2's per-axiom
``_class_is_a_changed`` callback (11%).

Why this lark grammar isn't already shipped
-------------------------------------------
* This file covers a focused **subset** (boolean, restrictions,
  OneOf, IRI forms). The production grammar also includes data
  ranges, facets, typed/lang/datetime/duration literals, and
  inverse-property syntax in cardinality positions — all of which
  must be ported and corpus-validated before swapping.
* The pymos visitor (``pymos/parser.py``) is a parsimonious
  ``NodeVisitor`` with parsimonious-specific child-shape unwrapping;
  porting to lark ``Transformer`` is a separate rewrite. The
  201-test corpus must pass byte-for-byte against the new
  visitor's owlready2 output.
* A reasonable estimate is 3-4 hours of focused porting + corpus
  validation, with risk of subtle differences in operator
  precedence and IRI tokenisation.

Run with::

    .venv/bin/python -m bench.experiments.lark_microbench
"""
from __future__ import annotations

import time

from lark import Lark


GRAMMAR = r"""
?start: union

?union: intersection ("or" intersection)*  -> union_op
?intersection: primary ("and" primary)*    -> intersection_op
?primary: "not" primary                    -> not_op
        | restriction
        | atom

restriction: object_property "some" primary                            -> some
           | object_property "only" primary                            -> only
           | object_property "value" individual                        -> value_res
           | object_property "Self"                                    -> has_self
           | object_property ("min"|"max"|"exactly") INT primary       -> cardinality

object_property: "inverse" iri  -> inverse_prop
               | iri            -> direct_prop

?atom: class_iri
     | individual_list
     | "(" union ")"

class_iri: iri
individual: iri
individual_list: "{" individual ("," individual)* "}"  -> oneof

?iri: IRI_REF -> full_iri
    | PNAME   -> prefixed_iri
    | NAME    -> simple_iri

IRI_REF: /<[^<>\"{}|^`\\\x00-\x20]*>/
PNAME:   /[A-Za-z_][A-Za-z0-9_-]*:[A-Za-z_][A-Za-z0-9_-]*/
NAME:    /[A-Za-z_][A-Za-z0-9_-]*/
INT:     /[0-9]+/

%ignore /\s+/
"""

EXPR = "(hasTopping some Cheese) and (not (hasTopping some Meat)) and {a, b, c}"


def main(iters: int = 10_000, runs: int = 3) -> None:
    from pymos.grammar import MANCHESTER_GRAMMAR
    parser = Lark(GRAMMAR, parser="lalr", start="start")

    # Sanity: both parse the same expression
    parser.parse(EXPR)
    MANCHESTER_GRAMMAR.parse(EXPR)

    print(f"expression: {EXPR!r}")
    print(f"runs: {runs}, iters per run: {iters}")
    print()
    for label, parse_fn in [
        ("parsimonious", MANCHESTER_GRAMMAR.parse),
        ("lark LALR",    parser.parse),
    ]:
        for run in range(runs):
            t = time.perf_counter()
            for _ in range(iters):
                parse_fn(EXPR)
            elapsed = time.perf_counter() - t
            print(f"  {label:<14} run {run + 1}: {elapsed * 1000:7.0f} ms total  "
                  f"({elapsed / iters * 1e6:6.0f} µs/parse)")


if __name__ == "__main__":
    main()
