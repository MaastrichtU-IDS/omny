"""owlready2 -> Manchester rendering: frame and document layers.

The class-expression layer lives in ``omny._render_expression`` and is
re-exported here so ``from omny.render import render_expression`` keeps
working for existing callers.
"""
from typing import Dict, Iterable, Optional

import owlready2

from omny._render_expression import (
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


def _build_disjoint_map(onto) -> Dict[str, list]:
    """One-pass scan of ``onto.disjoint_classes()`` → ``{class.iri: [partners]}``.

    Used by :func:`render` to avoid the previous O(classes × disjoint_groups)
    blowup where every class re-scanned every disjoint group.  On sio
    (1 585 classes) this cut render from 16 s to ~3 s — the disjoint scan
    was 80 % of total render wall time per the 2026-06-01 profile.
    """
    m: Dict[str, list] = {}
    for d in onto.disjoint_classes():
        ents = list(d.entities)
        for e1 in ents:
            partners = m.setdefault(e1.iri, [])
            seen = {p.iri for p in partners}
            for e2 in ents:
                if e2 is e1 or e2.iri in seen:
                    continue
                seen.add(e2.iri)
                partners.append(e2)
    return m


def _build_disjoint_property_map(onto) -> Dict[str, list]:
    """One-pass scan of ``onto.disjoint_properties()`` → ``{prop.iri: [partners]}``.

    The object/data-property analogue of :func:`_build_disjoint_map`. A
    partner may be an ``Inverse(...)`` expression (no ``.iri``), so only named
    properties are used as map *keys*, while partners are kept as-is (rendered
    via :func:`_name`, which prints ``inverse <name>``).
    """
    m: Dict[str, list] = {}
    for d in onto.disjoint_properties():
        ents = list(d.entities)
        for e1 in ents:
            if not hasattr(e1, "iri"):
                continue
            partners = m.setdefault(e1.iri, [])
            for e2 in ents:
                if e2 is not e1 and e2 not in partners:
                    partners.append(e2)
    return m


def _find_disjoint_partners(cls, disjoint_map: Optional[Dict[str, list]] = None) -> list:
    """Return classes appearing in any AllDisjoint group together with `cls`.

    When called from :func:`render` a precomputed ``disjoint_map`` is passed in
    for O(1) lookup; standalone callers (rare) pay the slow per-class scan.
    """
    if disjoint_map is not None:
        return list(disjoint_map.get(cls.iri, []))
    partners: list = []
    seen: set = set()
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


def _annotation_properties_for_world(world) -> list:
    """All annotation properties to check, in stable render order:
    built-ins first, then any AnnotationProperty registered in the world."""
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


def _annotation_properties_for(entity) -> list:
    """Per-entity wrapper for :func:`_annotation_properties_for_world`."""
    return _annotation_properties_for_world(entity.namespace.world)


def _render_rdflib_term(v, p: Dict[str, str], world) -> str:
    """Format an rdflib term as a Manchester annotation value.

    Mirrors :func:`_render_annotation_value` but starts from rdflib's
    URIRef/Literal/BNode rather than owlready2 Python objects, so the
    bulk-fetch path in :func:`_build_annotation_map` doesn't need to
    rehydrate every value through owlready2.
    """
    import rdflib
    if isinstance(v, rdflib.URIRef):
        e = world[str(v)]
        if e is not None and hasattr(e, "iri"):
            return _name(e, p)
        return f"<{v}>"
    if isinstance(v, rdflib.Literal):
        text = str(v)
        escaped = _escape_str(text)
        if v.language:
            return f'"{escaped}"@{v.language}'
        if v.datatype:
            # Let _render_literal handle typed literals via Python coercion;
            # falling back to a plain quoted form preserves round-trip safety.
            try:
                return _render_literal(v.toPython())
            except Exception:
                return f'"{escaped}"'
        return f'"{escaped}"'
    return repr(v)


def _build_annotation_map(onto, p: Dict[str, str]) -> Dict[str, list]:
    """Precompute `{entity_iri: ["ap_name value", ...]}` in one bulk scan.

    Replaces the per-entity ``getattr(entity, ap_attr, None)`` loop in
    :func:`_annotations_line`, which on HP was 97 % of total render wall
    (9 M getattr calls = 32 k entities × ~280 annotation properties).
    One ``rdflib.Graph.triples((None, ap, None))`` per annotation property
    collapses that to O(properties + pairs), matching the disjoint-map
    optimisation pattern.
    """
    import rdflib
    out: Dict[str, list] = {}
    world = onto.world
    g = world.as_rdflib_graph()
    for ap in _annotation_properties_for_world(world):
        ap_uri = rdflib.URIRef(ap.iri)
        ap_name = _name(ap, p)
        for s, _, v in g.triples((None, ap_uri, None)):
            val_str = _render_rdflib_term(v, p, world)
            out.setdefault(str(s), []).append(f"{ap_name} {val_str}")
    return out


def _render_annotation_value(v, p: Dict[str, str]) -> str:
    if hasattr(v, "iri"):
        return _name(v, p)
    if isinstance(v, owlready2.locstr):
        escaped = _escape_str(str(v))
        return f'"{escaped}"@{v.lang}' if v.lang else f'"{escaped}"'
    return _render_literal(v)


def _annotations_line(entity, p: Dict[str, str], indent: str = "    ",
                      *, _annotation_map: Optional[Dict[str, list]] = None) -> str:
    """Collect (ap, value) pairs and emit a single `Annotations:` line.

    When :func:`render` passes ``_annotation_map`` we look pairs up in O(1)
    instead of issuing ~280 ``getattr`` probes per entity (was 97 % of HP
    render wall — see :func:`_build_annotation_map`).
    """
    if _annotation_map is not None:
        pairs = _annotation_map.get(entity.iri, [])
        if not pairs:
            return ""
        return f"{indent}Annotations: {', '.join(pairs)}\n"
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


def render_frame(entity, prefixes: Optional[Dict[str, str]] = None,
                 *, _disjoint_map: Optional[Dict[str, list]] = None,
                 _disjoint_prop_map: Optional[Dict[str, list]] = None,
                 _annotation_map: Optional[Dict[str, list]] = None) -> str:
    """Render one owlready2 entity to its Manchester frame text.

    ``_disjoint_map``, ``_disjoint_prop_map`` and ``_annotation_map`` are
    internal optimisation kwargs passed by :func:`render` so we avoid
    re-scanning disjoint groups (classes / properties respectively) and
    re-probing every annotation property per entity. Standalone callers
    should leave them ``None``.
    """
    p = dict(prefixes or {})
    iri = getattr(entity, "iri", None)
    if iri is None:
        raise ValueError(f"cannot render frame for {entity!r}")
    name = _shorten(iri, p)

    if isinstance(entity, owlready2.ThingClass):
        out = f"Class: {name}\n"
        out += _annotations_line(entity, p, _annotation_map=_annotation_map)
        out += _kw_line("SubClassOf", _class_supers_excluding_thing(entity), p)
        out += _kw_line("EquivalentTo", list(entity.equivalent_to), p)
        out += _kw_line("DisjointWith", _find_disjoint_partners(entity, _disjoint_map), p)
        return out

    if isinstance(entity, owlready2.AnnotationPropertyClass):
        out = f"AnnotationProperty: {name}\n"
        out += _annotations_line(entity, p, _annotation_map=_annotation_map)
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        return out

    if isinstance(entity, owlready2.ObjectPropertyClass):
        out = f"ObjectProperty: {name}\n"
        out += _annotations_line(entity, p, _annotation_map=_annotation_map)
        out += _kw_line("Domain", list(entity.domain), p)
        out += _kw_line("Range",  list(entity.range), p)
        chars = _characteristic_labels(entity)
        if chars:
            out += f"    Characteristics: {', '.join(chars)}\n"
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        for chain in getattr(entity, "property_chain", []) or []:
            links = " o ".join(_name(link, p) for link in chain.properties)
            out += f"    SubPropertyChain: {links}\n"
        out += _kw_line("EquivalentTo", list(entity.equivalent_to), p)
        out += _kw_line("DisjointWith",
                        _find_disjoint_partners(entity, _disjoint_prop_map), p)
        if entity.inverse_property is not None:
            out += f"    InverseOf: {_name(entity.inverse_property, p)}\n"
        return out

    if isinstance(entity, owlready2.DataPropertyClass):
        out = f"DataProperty: {name}\n"
        out += _annotations_line(entity, p, _annotation_map=_annotation_map)
        out += _kw_line("Domain", list(entity.domain), p)
        out += _kw_line("Range",  list(entity.range), p)
        chars = _characteristic_labels(entity)
        if chars:
            out += f"    Characteristics: {', '.join(chars)}\n"
        sups = _user_super_properties(entity)
        if sups:
            out += _kw_line("SubPropertyOf", sups, p)
        out += _kw_line("EquivalentTo", list(entity.equivalent_to), p)
        out += _kw_line("DisjointWith",
                        _find_disjoint_partners(entity, _disjoint_prop_map), p)
        return out

    if isinstance(entity, owlready2.Thing):  # individuals
        out = f"Individual: {name}\n"
        out += _annotations_line(entity, p, _annotation_map=_annotation_map)
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

    # Precompute the {entity_iri: ["ap_name value", ...]} map once
    # (was 97 % of HP render wall pre-fix — 9 M getattr probes for empty
    # annotations).  One rdflib triples() scan per annotation property.
    annotation_map = _build_annotation_map(onto, p)
    disjoint_prop_map = _build_disjoint_property_map(onto)
    for ap in sorted(onto.world.annotation_properties(), key=lambda e: e.iri):
        parts.append(render_frame(ap, p, _annotation_map=annotation_map))
    for op in sorted(onto.object_properties(), key=lambda e: e.iri):
        parts.append(render_frame(op, p, _annotation_map=annotation_map,
                                  _disjoint_prop_map=disjoint_prop_map))
    for dp in sorted(onto.data_properties(), key=lambda e: e.iri):
        parts.append(render_frame(dp, p, _annotation_map=annotation_map,
                                  _disjoint_prop_map=disjoint_prop_map))
    # Skip classes whose IRI was declared as a Datatype (avoid duplicate frames).
    datatype_set = set(datatype_iris)
    # Precompute the {class_iri: [partners]} map once (was 80% of render
    # wall on sio per the 2026-06-01 profile; per-class scans were O(N^2)).
    disjoint_map = _build_disjoint_map(onto)
    for cls in sorted(onto.classes(), key=lambda e: e.iri):
        if cls.iri in datatype_set:
            continue
        parts.append(render_frame(cls, p, _disjoint_map=disjoint_map,
                                  _annotation_map=annotation_map))
    for ind in sorted(onto.individuals(), key=lambda e: e.iri):
        parts.append(render_frame(ind, p, _annotation_map=annotation_map))

    return "\n".join(parts).rstrip() + "\n"
