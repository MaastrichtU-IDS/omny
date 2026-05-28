"""owlready2 -> Manchester rendering. Mirrors pymos.parser."""
from typing import Dict, Iterable, Optional

import owlready2

# Manchester operator precedence (higher binds tighter)
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
    return _render(ce, p, _PREC_ATOM)


_FACET_REV = {
    "min_inclusive": ">=", "max_inclusive": "<=",
    "min_exclusive": ">",  "max_exclusive": "<",
    "length": "length", "min_length": "minLength", "max_length": "maxLength",
    "pattern": "pattern",
    "total_digits": "totalDigits", "fraction_digits": "fractionDigits",
}

_XSD_PY = {int: "xsd:integer", float: "xsd:double", str: "xsd:string", bool: "xsd:boolean"}


def _render_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
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


# --- Frame rendering ----------------------------------------------------------

_CHAR_NAMES = (
    (owlready2.FunctionalProperty, "Functional"),
    (owlready2.InverseFunctionalProperty, "InverseFunctional"),
    (owlready2.TransitiveProperty, "Transitive"),
    (owlready2.SymmetricProperty, "Symmetric"),
    (owlready2.AsymmetricProperty, "Asymmetric"),
    (owlready2.ReflexiveProperty, "Reflexive"),
    (owlready2.IrreflexiveProperty, "Irreflexive"),
)

# Base property classes owlready2 inserts in `is_a` that are not characteristics
# nor user-declared superproperties — filter them out when rendering.
_PROP_BASES = (
    owlready2.ObjectProperty,
    owlready2.DataProperty,
    owlready2.AnnotationProperty,
)


def _kw_line(label: str, operands: Iterable, p: Dict[str, str], indent: str = "    ") -> str:
    items = list(operands)
    if not items:
        return ""
    rendered = ", ".join(_render(o, p, _PREC_ATOM) for o in items)
    return f"{indent}{label}: {rendered}\n"


def _find_disjoint_partners(cls) -> list:
    """Return classes appearing in any AllDisjoint group together with `cls`."""
    partners = []
    seen = set()
    for d in cls.namespace.ontology.disjoint_classes():
        ents = list(d.entities)
        if cls in ents:
            for e in ents:
                if e is cls or e.iri in seen:
                    continue
                seen.add(e.iri)
                partners.append(e)
    return partners


def _characteristic_labels(prop) -> list:
    labels = []
    for char_cls, label in _CHAR_NAMES:
        if char_cls in prop.is_a:
            labels.append(label)
    return labels


def _user_super_properties(prop) -> list:
    """Properties in `prop.is_a` that are neither base kinds nor characteristics."""
    chars = {c for c, _ in _CHAR_NAMES}
    return [
        s for s in prop.is_a
        if s not in _PROP_BASES and s not in chars and s is not prop
    ]


def _class_supers_excluding_thing(cls) -> list:
    return [s for s in cls.is_a if s is not owlready2.Thing]


def _individual_types_excluding_thing(ind) -> list:
    return [t for t in ind.is_a if t is not owlready2.Thing]


def render_frame(entity, prefixes: Optional[Dict[str, str]] = None) -> str:
    """Render one owlready2 entity to its Manchester frame text."""
    p = dict(prefixes or {})
    iri = getattr(entity, "iri", None)
    if iri is None:
        raise ValueError(f"cannot render frame for {entity!r}")
    name = _shorten(iri, p)

    if isinstance(entity, owlready2.ThingClass):
        out = f"Class: {name}\n"
        out += _kw_line("SubClassOf", _class_supers_excluding_thing(entity), p)
        out += _kw_line("EquivalentTo", list(entity.equivalent_to), p)
        out += _kw_line("DisjointWith", _find_disjoint_partners(entity), p)
        return out

    if isinstance(entity, owlready2.ObjectPropertyClass):
        out = f"ObjectProperty: {name}\n"
        out += _kw_line("Domain", list(entity.domain), p)
        out += _kw_line("Range",  list(entity.range), p)
        chars = _characteristic_labels(entity)
        if chars:
            out += f"    Characteristics: {', '.join(chars)}\n"
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        if entity.inverse_property is not None:
            out += f"    InverseOf: {_name(entity.inverse_property, p)}\n"
        return out

    if isinstance(entity, owlready2.DataPropertyClass):
        out = f"DataProperty: {name}\n"
        out += _kw_line("Domain", list(entity.domain), p)
        out += _kw_line("Range",  list(entity.range), p)
        chars = _characteristic_labels(entity)
        if chars:
            out += f"    Characteristics: {', '.join(chars)}\n"
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        return out

    if isinstance(entity, owlready2.Thing):  # individuals
        out = f"Individual: {name}\n"
        out += _kw_line("Types", _individual_types_excluding_thing(entity), p)
        return out

    raise ValueError(f"cannot render frame for {entity!r}")
