"""Lark vs parsimonious microbenchmark on a single Manchester expression.

This file is the **historical exploration** that motivated PR #45
(``omny/_lark_parser.py``). The production swap is done — keep this
around as a regression check on the parser-internal cost only.

Result on this host (2026-06-01, master at 1ca6765):
  parsimonious: ~2400 µs per parse
  lark (LALR):  ~444  µs per parse
  ratio: ~5.4× on this one expression

Why the in-the-wild number is smaller
-------------------------------------
PR #45 measured the production parse:
  * sio: 4.97 s → 2.79 s = 1.78×
  * hp:  310 s  → 164 s  = 1.89×
The 5.4× microbench is a single complex expression; real ontologies
parse ~100 k short axiom operands, where lark's per-parse fixed
costs (contextual lexer + tree alloc + transformer dispatch) dilute
the structural advantage.

For a same-shape comparison across the full corpus, use the
:mod:`bench.runners.compare_parsers` runner instead — it pairs lark
and parsimonious cells per ontology via ``measure_in_subprocess`` so
RSS and JIT effects don't leak between cells.

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
    from omny.grammar import MANCHESTER_GRAMMAR
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
