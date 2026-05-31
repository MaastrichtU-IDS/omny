"""owlready2 class expression -> Manchester syntax string.

The expression-rendering layer. The frame/document layer in ``pymos.render``
imports from this module; users normally call ``pymos.render_expression``
(re-exported via ``pymos.render`` for backward compatibility).
"""
from typing import Dict, Optional

import owlready2

# Manchester operator precedence (higher binds tighter).
# `_PREC_TOP` is the parent context for top-level expressions and axiom operands —
# they sit at the bottom of the precedence chain, so no operator child needs parens.
_PREC_TOP = 0
_PREC_OR = 1
_PREC_AND = 2
_PREC_NOT = 3
_PREC_ATOM = 4


def _shorten(iri: str, prefixes: Dict[str, str]) -> str:
    """Render an IRI as a prefixed name when a prefix matches, else `<full IRI>`."""
    for prefix, base in sorted(prefixes.items(), key=lambda kv: -len(kv[1])):
        if iri.startswith(base):
            return f"{prefix}:{iri[len(base):]}"
    return f"<{iri}>"


def _name(entity, prefixes: Dict[str, str]) -> str:
    """Render any single owlready2 entity reference (class / property / individual / Inverse)."""
    if isinstance(entity, owlready2.Inverse):
        return f"inverse {_name(entity.property, prefixes)}"
    iri = getattr(entity, "iri", None)
    if iri is None:
        return repr(entity)
    return _shorten(iri, prefixes)


def _prec(ce) -> int:
    if isinstance(ce, owlready2.Or):
        return _PREC_OR
    if isinstance(ce, owlready2.And):
        return _PREC_AND
    if isinstance(ce, owlready2.Not):
        return _PREC_NOT
    return _PREC_ATOM


def _paren_if(text: str, child_prec: int, parent_prec: int) -> str:
    return f"({text})" if child_prec < parent_prec else text


def render_expression(ce, prefixes: Optional[Dict[str, str]] = None) -> str:
    """Render an owlready2 class expression to a Manchester-syntax string."""
    p = dict(prefixes or {})
    return _render(ce, p, _PREC_TOP)


_FACET_REV = {
    "min_inclusive": ">=", "max_inclusive": "<=",
    "min_exclusive": ">",  "max_exclusive": "<",
    "length": "length", "min_length": "minLength", "max_length": "maxLength",
    "pattern": "pattern",
    "total_digits": "totalDigits", "fraction_digits": "fractionDigits",
}

_XSD_PY = {int: "xsd:integer", float: "xsd:double", str: "xsd:string", bool: "xsd:boolean"}


def _escape_str(s: str) -> str:
    """Escape a string for Manchester ``quoted_string`` syntax.

    The grammar accepts ``\\\\`` (escaped backslash) and ``\\"`` (escaped quote)
    inside double-quoted literals (see the ``quoted_string`` rule). A raw ``"``
    or ``\\`` in ``s`` would otherwise terminate the literal early or be
    consumed as the start of a different escape, breaking the parser's
    frame/section boundaries.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{_escape_str(value)}"'
    return repr(value)


def _render_constrained_datatype(cdt, p: Dict[str, str]) -> str:
    base = _render(cdt.base_datatype, p, _PREC_ATOM)
    facets = []
    for attr, op in _FACET_REV.items():
        v = getattr(cdt, attr, None)
        if v is None:
            continue
        facets.append(f"{op} {_render_literal(v)}")
    return f"{base}[{', '.join(facets)}]"


def _render(ce, p: Dict[str, str], parent_prec: int) -> str:
    # owlready2 Restriction covers some/only/value/has_self/min/max/exactly
    if isinstance(ce, owlready2.Restriction):
        prop = _name(ce.property, p)
        t = ce.type
        if t == owlready2.SOME:
            return f"{prop} some {_render(ce.value, p, _PREC_ATOM)}"
        if t == owlready2.ONLY:
            return f"{prop} only {_render(ce.value, p, _PREC_ATOM)}"
        if t == owlready2.VALUE:
            return f"{prop} value {_render_value_filler(ce.value, p)}"
        if t == owlready2.HAS_SELF:
            return f"{prop} Self"
        if t == owlready2.MIN:
            return f"{prop} min {ce.cardinality} {_render(ce.value, p, _PREC_ATOM)}"
        if t == owlready2.MAX:
            return f"{prop} max {ce.cardinality} {_render(ce.value, p, _PREC_ATOM)}"
        if t == owlready2.EXACTLY:
            return f"{prop} exactly {ce.cardinality} {_render(ce.value, p, _PREC_ATOM)}"
        raise ValueError(f"unknown Restriction type: {t!r}")

    if isinstance(ce, owlready2.And):
        body = " and ".join(_render(c, p, _PREC_AND) for c in ce.Classes)
        return _paren_if(body, _PREC_AND, parent_prec)
    if isinstance(ce, owlready2.Or):
        body = " or ".join(_render(c, p, _PREC_OR) for c in ce.Classes)
        return _paren_if(body, _PREC_OR, parent_prec)
    if isinstance(ce, owlready2.Not):
        return f"not {_render(ce.Class, p, _PREC_NOT)}"

    if isinstance(ce, owlready2.OneOf):
        return "{ " + " , ".join(_name(i, p) for i in ce.instances) + " }"

    if isinstance(ce, owlready2.ConstrainedDatatype):
        return _render_constrained_datatype(ce, p)

    # xsd python-type fillers
    if isinstance(ce, type) and ce in _XSD_PY:
        return _XSD_PY[ce]

    # Named class / individual / property reference
    return _name(ce, p)


def _render_value_filler(value, p: Dict[str, str]) -> str:
    """`value` clause filler may be an individual (entity) or a literal."""
    if hasattr(value, "iri"):
        return _name(value, p)
    return _render_literal(value)
