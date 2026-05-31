"""owlready2 -> Manchester rendering: frame and document layers.

The class-expression layer lives in ``pymos._render_expression`` and is
re-exported here so ``from pymos.render import render_expression`` keeps
working for existing callers.
"""
from typing import Dict, Iterable, Optional

import owlready2

from pymos._render_expression import (
    render_expression,
    _escape_str,
    _name,
    _render,
    _render_literal,
    _render_value_filler,
    _shorten,
    _PREC_TOP,
)

__all__ = ["render", "render_expression", "render_frame"]


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

_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_OWL = "http://www.w3.org/2002/07/owl#"
_BUILTIN_ANNOTATION_IRIS = (
    _RDFS + "label",
    _RDFS + "comment",
    _RDFS + "seeAlso",
    _RDFS + "isDefinedBy",
    _OWL + "versionInfo",
    _OWL + "deprecated",
    _OWL + "incompatibleWith",
    _OWL + "backwardCompatibleWith",
    _OWL + "priorVersion",
)


def _kw_line(label: str, operands: Iterable, p: Dict[str, str], indent: str = "    ") -> str:
    items = list(operands)
    if not items:
        return ""
    # Axiom operands are top-level — no outer parens around an And/Or/Not.
    rendered = ", ".join(_render(o, p, _PREC_TOP) for o in items)
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


def _python_attr_for(prop) -> str:
    return getattr(prop, "python_name", None) or prop.name


def _annotation_properties_for(entity) -> list:
    """All annotation properties to check for values on `entity`: built-ins
    plus any AnnotationProperty registered in the world."""
    world = entity.namespace.world
    aps = []
    seen = set()
    for iri in _BUILTIN_ANNOTATION_IRIS:
        e = world[iri]
        if e is not None and e.iri not in seen:
            aps.append(e)
            seen.add(e.iri)
    for ap in world.annotation_properties():
        if ap.iri not in seen:
            aps.append(ap)
            seen.add(ap.iri)
    return aps


def _render_annotation_value(v, p: Dict[str, str]) -> str:
    if hasattr(v, "iri"):
        return _name(v, p)
    if isinstance(v, owlready2.locstr):
        escaped = _escape_str(str(v))
        return f'"{escaped}"@{v.lang}' if v.lang else f'"{escaped}"'
    return _render_literal(v)


def _annotations_line(entity, p: Dict[str, str], indent: str = "    ") -> str:
    """Collect (ap, value) pairs and emit a single `Annotations:` line."""
    pairs = []
    for ap in _annotation_properties_for(entity):
        vals = getattr(entity, _python_attr_for(ap), None)
        if not vals:
            continue
        for v in (vals if isinstance(vals, list) else [vals]):
            pairs.append(f"{_name(ap, p)} {_render_annotation_value(v, p)}")
    if not pairs:
        return ""
    return f"{indent}Annotations: {', '.join(pairs)}\n"


def _individual_facts(ind, p: Dict[str, str]) -> list:
    """Return rendered `prop filler` strings for each asserted property value."""
    world = ind.namespace.world
    out = []
    for prop in list(world.object_properties()) + list(world.data_properties()):
        vals = getattr(ind, _python_attr_for(prop), None)
        if not vals:
            continue
        for v in (vals if isinstance(vals, list) else [vals]):
            out.append(f"{_name(prop, p)} {_render_value_filler(v, p)}")
    return out


def _individual_sameas(ind) -> list:
    """Other individuals declared owl:sameAs to `ind` (via equivalent_to)."""
    return [e for e in ind.equivalent_to if hasattr(e, "iri") and e is not ind]


def _individual_different_partners(ind) -> list:
    """Individuals appearing in any AllDifferent group with `ind`."""
    partners = []
    seen = set()
    for d in ind.namespace.ontology.different_individuals():
        ents = list(d.entities)
        if ind in ents:
            for e in ents:
                if e is ind or e.iri in seen:
                    continue
                seen.add(e.iri)
                partners.append(e)
    return partners


def render_frame(entity, prefixes: Optional[Dict[str, str]] = None) -> str:
    """Render one owlready2 entity to its Manchester frame text."""
    p = dict(prefixes or {})
    iri = getattr(entity, "iri", None)
    if iri is None:
        raise ValueError(f"cannot render frame for {entity!r}")
    name = _shorten(iri, p)

    if isinstance(entity, owlready2.ThingClass):
        out = f"Class: {name}\n"
        out += _annotations_line(entity, p)
        out += _kw_line("SubClassOf", _class_supers_excluding_thing(entity), p)
        out += _kw_line("EquivalentTo", list(entity.equivalent_to), p)
        out += _kw_line("DisjointWith", _find_disjoint_partners(entity), p)
        return out

    if isinstance(entity, owlready2.AnnotationPropertyClass):
        out = f"AnnotationProperty: {name}\n"
        out += _annotations_line(entity, p)
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        return out

    if isinstance(entity, owlready2.ObjectPropertyClass):
        out = f"ObjectProperty: {name}\n"
        out += _annotations_line(entity, p)
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
        out += _annotations_line(entity, p)
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
        out += _annotations_line(entity, p)
        out += _kw_line("Types", _individual_types_excluding_thing(entity), p)
        facts = _individual_facts(entity, p)
        if facts:
            out += f"    Facts: {', '.join(facts)}\n"
        sames = _individual_sameas(entity)
        if sames:
            out += _kw_line("SameAs", sames, p)
        diffs = _individual_different_partners(entity)
        if diffs:
            out += _kw_line("DifferentFrom", diffs, p)
        return out

    raise ValueError(f"cannot render frame for {entity!r}")


# --- Document rendering ------------------------------------------------------

def _declared_datatype_iris(onto) -> list:
    """IRIs declared as rdfs:Datatype in this ontology's world.

    owlready2 surfaces some internal storids (bare integer strings) as
    pseudo-subjects in ``as_rdflib_graph``; those aren't real datatype IRIs
    and emitting them creates ``Datatype: <378>`` frames that round-trip
    back as new entities, growing the document on every parse/render cycle.
    Keep only proper IRIs (must contain a scheme).
    """
    import rdflib
    g = onto.world.as_rdflib_graph()
    dt = rdflib.URIRef(_RDFS + "Datatype")
    return sorted({str(s) for s in g.subjects(rdflib.RDF.type, dt)
                   if ":" in str(s) and not str(s).isdigit()})


def render(onto, prefixes: Optional[Dict[str, str]] = None,
           include_imports: bool = True) -> str:
    """Render an owlready2 ontology as a Manchester OWL syntax document.

    Emits Prefix declarations + Ontology header, then frames in stable order:
    Datatype, AnnotationProperty, ObjectProperty, DataProperty, Class, Individual
    (each group sorted by IRI for diff-stability). Includes Annotations,
    Individual Facts/SameAs/DifferentFrom, Object/DataProperty characteristics
    + InverseOf, and DisjointWith partners.
    """
    p = dict(prefixes or {})
    parts = []

    for prefix, base in sorted(p.items()):
        parts.append(f"Prefix: {prefix}: <{base}>")

    base_iri = onto.base_iri.rstrip("#").rstrip("/")
    parts.append(f"Ontology: <{base_iri}>")

    if include_imports:
        for imp in getattr(onto, "imported_ontologies", []) or []:
            parts.append(f"Import: <{imp.base_iri}>")

    parts.append("")  # blank line before frames

    datatype_iris = _declared_datatype_iris(onto)
    for dt_iri in datatype_iris:
        parts.append(f"Datatype: {_shorten(dt_iri, p)}\n")

    for ap in sorted(onto.world.annotation_properties(), key=lambda e: e.iri):
        parts.append(render_frame(ap, p))
    for op in sorted(onto.object_properties(), key=lambda e: e.iri):
        parts.append(render_frame(op, p))
    for dp in sorted(onto.data_properties(), key=lambda e: e.iri):
        parts.append(render_frame(dp, p))
    # Skip classes whose IRI was declared as a Datatype (avoid duplicate frames).
    datatype_set = set(datatype_iris)
    for cls in sorted(onto.classes(), key=lambda e: e.iri):
        if cls.iri in datatype_set:
            continue
        parts.append(render_frame(cls, p))
    for ind in sorted(onto.individuals(), key=lambda e: e.iri):
        parts.append(render_frame(ind, p))

    return "\n".join(parts).rstrip() + "\n"
