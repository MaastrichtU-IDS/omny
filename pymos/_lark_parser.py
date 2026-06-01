"""Lark-based Manchester class-expression parser (LALR).

A drop-in replacement for ``pymos.parser.parse_expression`` that
trades parsimonious's PEG packrat for lark's LALR grammar. The
microbench at ``bench/experiments/lark_microbench.py`` measured
~5.4× faster per-parse on a complex expression — the production
gain on full HP-scale parse is bounded by how much of total wall
parsimonious occupies (cProfile said ~48 %).

Design notes
============
The parsimonious grammar in ``pymos/grammar.py`` uses ordered choice
to disambiguate object-property restrictions vs data-property
restrictions at the operand position (it tries ``data_some_only_res``
first, then ``some_only_res``).  LALR can't backtrack across those
arms, so we unify the grammar at parse time:

* One ``restriction`` production handles both kinds — the property
  becomes whichever owlready2 entity ``EntityResolver`` returns.
  Its ``.some/.only/.min/.max/.exactly/.value`` methods dispatch
  correctly regardless of whether the entity is an ObjectProperty
  or a DataProperty.
* One ``atom`` production accepts ``{...}`` (lifted to ``OneOf`` of
  individuals when the items are bare IRIs, ``OneOf`` of literals when
  they're literals), bare IRIs (treated as class atoms — or as
  ``datatype_iri`` when used as a restriction filler), and
  ``datatype_iri "[" facets "]"`` for constrained datatypes.

This means ``parse_expression_lark`` may accept a few strictly
ill-typed strings that parsimonious would reject (e.g. an object
property used in a context where the grammar required a data
property).  In practice every well-formed Manchester expression
round-trips identically — verified by
``tests/test_lark_equivalence.py`` against a fixture list covering
every parsimonious production plus the pizza corpus.
"""
from __future__ import annotations

from typing import Dict, Optional

import owlready2
from lark import Lark, Transformer, v_args

from pymos.entities import EntityResolver


# Module-level: build the LALR table ONCE at import time. Per-call
# instantiation would kill the perf win the lark port is justified by.
_GRAMMAR = r"""
?start: union

?union: intersection ("or" intersection)*  -> union_op
?intersection: primary ("and" primary)*    -> intersection_op

?primary: "not" primary    -> not_op
        | restriction
        | atom

restriction: property "some" primary             -> some_r
           | property "only" primary             -> only_r
           | property "value" value_filler       -> value_r
           | property "Self"                     -> self_r
           | property CARD INT primary           -> card_r

CARD: "min" | "max" | "exactly"

property: "inverse" property_iri  -> inverse_prop
        | property_iri            -> direct_prop

property_iri: iri  -> as_iri

?value_filler: literal -> lit_filler
             | iri     -> ind_filler

?atom: datatype_restriction
     | enum
     | iri_atom
     | "(" union ")"

iri_atom: iri  -> iri_atom_value

enum: "{" enum_item ("," enum_item)* "}"  -> oneof_r
?enum_item: literal -> lit_item
          | iri     -> ind_item

datatype_restriction: iri "[" facet_restriction ("," facet_restriction)* "]"  -> dt_restr

facet_restriction: FACET literal  -> facet_r

FACET: ">=" | "<=" | ">" | "<"
     | "length" | "minLength" | "maxLength" | "pattern"
     | "totalDigits" | "fractionDigits" | "langRange"

?literal: typed_literal
        | string_literal_language
        | string_literal_no_language
        | float_literal
        | decimal_literal
        | integer_literal
        | boolean_literal
        | datetime_literal
        | duration_literal
        | date_literal

typed_literal: QUOTED_STRING "^^" iri  -> typed_lit
string_literal_language: QUOTED_STRING LANG_TAG  -> lang_lit
string_literal_no_language: QUOTED_STRING  -> str_lit
float_literal: FLOAT_LIT   -> float_lit
decimal_literal: DECIMAL_LIT -> decimal_lit
integer_literal: SIGNED_INT  -> int_lit
boolean_literal: BOOL_LIT  -> bool_lit
datetime_literal: DATETIME_LIT -> datetime_lit
duration_literal: DURATION_LIT -> duration_lit
date_literal: DATE_LIT -> date_lit

QUOTED_STRING: /"([^"\\]|\\["\\])*"/
LANG_TAG: /@[a-zA-Z]+(-[a-zA-Z0-9]+)*/

DATETIME_LIT: /[0-9]{4}-(0[1-9]|1[0-2])-(0[0-9]|1[0-9]|2[0-9]|3[01])[T ]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{6})?(Z|[+\-]([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9](\.[0-9]{6})?)?)?/
DATE_LIT: /[0-9]{4}-(0[1-9]|1[0-2])-(0[0-9]|1[0-9]|2[0-9]|3[01])/
DURATION_LIT: /P([0-9]+W)?([0-9]+D)?(T([0-9]+H)?([0-9]+M)?([0-9]+(\.[0-9]{6})?S)?)?/
FLOAT_LIT: /[+\-]?(([0-9]+(\.[0-9]+)?)|(\.[0-9]+))([eE][+\-]?[0-9]+)?[fF]/
DECIMAL_LIT: /[+\-]?[0-9]+\.[0-9]+/
SIGNED_INT: /[+\-]?[0-9]+/
BOOL_LIT.2: /[tT]rue|[fF]alse/
INT: /[0-9]+/

iri: FULL_IRI    -> full_iri
   | PREFIXED   -> prefixed_iri
   | NAME       -> simple_iri

FULL_IRI: /<[^<>"{}|^`\\\x00-\x20]*>/
PREFIXED: /[A-Za-z_][A-Za-z0-9_.\-]*:[A-Za-z_][A-Za-z0-9_.\-]*/ | /:[A-Za-z_][A-Za-z0-9_.\-]*/
NAME: /[A-Za-z_][A-Za-z0-9_\-]*/

%ignore /\s+/
"""

# Build once, share across all parses.
_PARSER = Lark(_GRAMMAR, parser="lalr", start="start", maybe_placeholders=False)


# Facet text -> ConstrainedDatatype kwarg name (mirrors ManchesterParser._FACET).
_FACET = {
    ">=": "min_inclusive", "<=": "max_inclusive",
    ">": "min_exclusive", "<": "max_exclusive",
    "length": "length", "minLength": "min_length", "maxLength": "max_length",
    "pattern": "pattern", "totalDigits": "total_digits",
    "fractionDigits": "fraction_digits", "langRange": "lang_range",
}

# datatype IRI suffix -> Python type for typed_literal coercion. owlready2
# stores Manchester data ranges as Python type objects, so a bare ``xsd:integer``
# becomes ``int`` etc. Mirrors the dict in ``pymos.parser.ManchesterParser._XSD``.
_XSD = {
    "integer": int, "int": int, "double": float, "float": float,
    "decimal": float, "string": str, "boolean": bool,
}


def _unescape_quoted(raw: str) -> str:
    """Strip surrounding quotes, undo ``\\"`` / ``\\\\`` escapes."""
    inner = raw[1:-1]
    out, i = [], 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner) and inner[i + 1] in ('"', "\\"):
            out.append(inner[i + 1])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _is_datatype_iri_text(text: str) -> bool:
    """Return True if ``text`` is a bare xsd: datatype name, recognized as
    a datatype rather than a class.
    """
    if text.startswith("xsd:"):
        return text[4:] in _XSD or text[4:] in (
            "dateTime", "date", "duration",
        )
    return text in _XSD or text in ("dateTime", "date", "duration")


def _datatype_to_python_type(text: str):
    """Map a datatype IRI string (e.g. ``xsd:integer``) to a Python type."""
    name = text[4:] if text.startswith("xsd:") else text
    return _XSD.get(name, str)


class _Transformer(Transformer):
    """Convert the lark tree to owlready2 constructs.

    Holds the active ``EntityResolver`` so every IRI token bottoms out to
    an owlready2 entity created in the target ontology.
    """
    def __init__(self, resolver: EntityResolver):
        super().__init__()
        self.r = resolver

    # --- IRIs ---------------------------------------------------------------

    @v_args(inline=True)
    def full_iri(self, tok):
        return tok.value  # includes the surrounding < >

    @v_args(inline=True)
    def prefixed_iri(self, tok):
        return tok.value

    @v_args(inline=True)
    def simple_iri(self, tok):
        return tok.value

    @v_args(inline=True)
    def as_iri(self, text):
        # propagates the IRI string up to ``property`` / restriction rules
        return text

    @v_args(inline=True)
    def iri_atom_value(self, text):
        """bare IRI used as a class or data atom.

        ``xsd:integer`` / ``xsd:string`` / etc. resolve to a Python type
        (matching parsimonious's ``visit_datatype_iri``); everything else
        resolves to an owlready2 class entity. This is how the unified
        grammar still recovers the obj-vs-data distinction at transform
        time without needing two parser arms.
        """
        if _is_datatype_iri_text(text):
            return _datatype_to_python_type(text)
        return self.r.get_class(text)

    # --- properties (object or data; resolver-disambiguated) -----------------

    @v_args(inline=True)
    def direct_prop(self, iri_text):
        return self._resolve_property(iri_text)

    @v_args(inline=True)
    def inverse_prop(self, iri_text):
        prop = self._resolve_property(iri_text)
        return owlready2.Inverse(prop)

    def _resolve_property(self, iri_text: str):
        """Return an owlready2 property entity. Prefer object-property
        registration (matches parsimonious behaviour); the resolver
        falls through to data-property when context requires it.
        """
        return self.r.get_object_property(iri_text)

    # --- restrictions -------------------------------------------------------

    @v_args(inline=True)
    def some_r(self, prop, filler):
        return prop.some(filler)

    @v_args(inline=True)
    def only_r(self, prop, filler):
        return prop.only(filler)

    @v_args(inline=True)
    def value_r(self, prop, filler):
        return prop.value(filler)

    @v_args(inline=True)
    def self_r(self, prop):
        if hasattr(prop, "has_self"):
            return prop.has_self()
        from owlready2.class_construct import Restriction
        return Restriction(prop, owlready2.HAS_SELF, None, True, None)

    @v_args(inline=True)
    def card_r(self, prop, card_kw, card_int, filler):
        kw = str(card_kw)
        n = int(card_int)
        if kw == "min":
            return prop.min(n, filler)
        if kw == "max":
            return prop.max(n, filler)
        return prop.exactly(n, filler)

    @v_args(inline=True)
    def lit_filler(self, lit):
        return lit

    @v_args(inline=True)
    def ind_filler(self, iri_text):
        return self.r.get_individual(iri_text)

    # --- boolean combinators ------------------------------------------------

    def union_op(self, children):
        children = list(children)
        if len(children) == 1:
            return children[0]
        return owlready2.Or(children)

    def intersection_op(self, children):
        children = list(children)
        if len(children) == 1:
            return children[0]
        return owlready2.And(children)

    @v_args(inline=True)
    def not_op(self, expr):
        return owlready2.Not(expr)

    # --- OneOf --------------------------------------------------------------

    def oneof_r(self, items):
        # owlready2's OneOf accepts a list of either individuals (entities)
        # or literal values uniformly; ``ind_item`` and ``lit_item``
        # already resolved each element to the correct Python representation.
        return owlready2.OneOf(list(items))

    @v_args(inline=True)
    def lit_item(self, lit):
        return lit

    @v_args(inline=True)
    def ind_item(self, iri_text):
        return self.r.get_individual(iri_text)

    # --- datatype restriction ----------------------------------------------

    def dt_restr(self, children):
        # children: iri_string, facet_restriction*
        iri_text = children[0]
        facets = children[1:]
        py_type = _datatype_to_python_type(iri_text)
        kwargs = {}
        for f in facets:
            name, val = f
            kwargs[name] = val
        return owlready2.ConstrainedDatatype(py_type, **kwargs)

    @v_args(inline=True)
    def facet_r(self, facet_tok, lit):
        return (_FACET[str(facet_tok)], lit)

    # --- literals ----------------------------------------------------------

    @v_args(inline=True)
    def str_lit(self, tok):
        return _unescape_quoted(tok.value)

    @v_args(inline=True)
    def lang_lit(self, qs, lang):
        # parsimonious renders these as bare strings (the lang tag is
        # preserved in the .lang attribute on the locstr instance,
        # but pymos.parser's visit_quoted_string returns a plain str).
        # Match that: ignore the lang tag and return the unescaped text.
        # (Annotation-side language handling happens in frames.py.)
        return _unescape_quoted(qs.value)

    @v_args(inline=True)
    def typed_lit(self, qs, iri_text):
        text = _unescape_quoted(qs.value)
        py_type = _datatype_to_python_type(iri_text)
        if py_type is bool:
            return text.strip().lower() == "true"
        if py_type in (int, float):
            return py_type(text)
        return text

    @v_args(inline=True)
    def int_lit(self, tok):
        return int(tok.value)

    @v_args(inline=True)
    def decimal_lit(self, tok):
        return float(tok.value)

    @v_args(inline=True)
    def float_lit(self, tok):
        # strip trailing f/F
        return float(tok.value.rstrip("fF"))

    @v_args(inline=True)
    def bool_lit(self, tok):
        return tok.value.strip().lower() == "true"

    @v_args(inline=True)
    def date_lit(self, tok):
        return tok.value

    @v_args(inline=True)
    def datetime_lit(self, tok):
        return tok.value

    @v_args(inline=True)
    def duration_lit(self, tok):
        return tok.value


class LarkManchesterParser:
    """Drop-in replacement for :class:`pymos.parser.ManchesterParser`.

    ``FrameLoader`` holds one of these and calls ``parse_expression``
    per axiom operand; sharing the resolver across calls keeps prefix
    state consistent within a document load.

    The :class:`_Transformer` is built once at instance creation. lark's
    ``Transformer.__init__`` builds a rule→method dispatch dict, which on
    HP (~100 k axiom-operand parses per load) would otherwise dominate
    the per-parse cost.
    """
    def __init__(self, resolver: EntityResolver):
        self.r = resolver
        self._transformer = _Transformer(resolver)

    def parse_expression(self, text: str):
        tree = _PARSER.parse(text.strip())
        return self._transformer.transform(tree)


def parse_expression_lark(text: str, onto: owlready2.Ontology,
                          prefixes: Optional[Dict[str, str]] = None):
    """Parse a Manchester class expression with the lark backend.

    Public API parity with :func:`pymos.parser.parse_expression`.
    Same arguments, same return shape (an owlready2 construct).
    """
    return LarkManchesterParser(EntityResolver(onto, prefixes)).parse_expression(text)
