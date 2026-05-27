"""Build store-agnostic SPARQL for class-relation retrieval (asserted graph only)."""
from typing import Iterable

from pymos.vocab import STRUCTURAL_PATH, prefix_header

RELATIONS = ("super", "sub", "direct_super", "direct_sub", "equiv", "individual")


def _relation_clause(rel: str, c: str, var: str) -> str:
    if rel == "super":
        return f"{c} rdfs:subClassOf+ {var} ."
    if rel == "sub":
        return f"{var} rdfs:subClassOf+ {c} ."
    if rel == "direct_super":
        return (f"{c} rdfs:subClassOf {var} . "
                f"FILTER NOT EXISTS {{ {c} rdfs:subClassOf+ ?mid . "
                f"?mid rdfs:subClassOf+ {var} . FILTER(?mid != {c} && ?mid != {var}) }}")
    if rel == "direct_sub":
        return (f"{var} rdfs:subClassOf {c} . "
                f"FILTER NOT EXISTS {{ {var} rdfs:subClassOf+ ?mid . "
                f"?mid rdfs:subClassOf+ {c} . FILTER(?mid != {c} && ?mid != {var}) }}")
    if rel == "equiv":
        return f"{{ {c} owl:equivalentClass {var} }} UNION {{ {var} owl:equivalentClass {c} }}"
    if rel == "individual":
        return f"{var} rdf:type {c} ."
    raise ValueError(f"unknown relation: {rel}")


def _target_iri(target) -> str:
    """Normalise *target* to a SPARQL term string.

    Accepts:
    - A full IRI with angle brackets: ``"<http://ex.org/Pizza>"`` — returned as-is.
    - A full IRI without brackets: ``"http://ex.org/Pizza"`` — wrapped in ``<>``.
    - A SPARQL variable: ``"?cls"`` — returned as-is.
    - An owlready2 entity (anything with a ``.iri`` attribute) — ``.iri`` is extracted
      and wrapped in ``<>``.
    - A prefixed name such as ``"ex:Pizza"`` — passed through as-is.  Only the prefixes
      declared in :data:`pymos.vocab.PREFIXES` (owl/rdf/rdfs/xsd) are available in the
      generated query header; a bare or unknown-prefixed name will fail at query
      parse/execution time.
    """
    if hasattr(target, "iri"):          # owlready2 entity
        return f"<{target.iri}>"
    t = str(target).strip()
    if t.startswith("<") or t.startswith("?"):
        return t
    if t.startswith("http"):
        return f"<{t}>"
    return t  # already a prefixed name


def class_relations_query(target, relations: Iterable[str] = ("super", "sub", "equiv"),
                          construct: bool = True) -> str:
    """Build a store-agnostic SPARQL query for class-relation retrieval (asserted graph only).

    Args:
        target: The class to query about.  Accepts:

            * An owlready2 class or entity (its ``.iri`` is used).
            * A full IRI string with angle brackets: ``"<http://ex.org/Pizza>"``.
            * A full IRI string without brackets: ``"http://ex.org/Pizza"``.
            * A SPARQL variable: ``"?cls"`` (returns queries involving that variable).
            * A prefixed name such as ``"ex:Pizza"`` (the prefix must be declared in
              the query header, which only includes owl/rdf/rdfs/xsd by default).

        relations: One or more of the six supported relation names (default:
            ``("super", "sub", "equiv")``):

            * ``"super"``        — transitive superclasses (``rdfs:subClassOf+``).
            * ``"sub"``          — transitive subclasses (``rdfs:subClassOf+``).
            * ``"direct_super"`` — immediate superclasses, redundancy-filtered.
            * ``"direct_sub"``   — immediate subclasses, redundancy-filtered.
            * ``"equiv"``        — equivalent classes (both directions of
              ``owl:equivalentClass``).
            * ``"individual"``   — instances of the class (``rdf:type``).

        construct: If ``True`` (default) emit a SPARQL CONSTRUCT query returning the
            full outgoing blank-node subgraph of every related class (structural
            predicates only — see :data:`pymos.vocab.STRUCTURAL_PATH`).  This is
            useful to materialise anonymous class-expression nodes attached to the
            related classes.  If ``False``, emit a SELECT query returning just the
            related IRIs (``?rel`` / ``?ind``).

    Returns:
        A SPARQL query string (starts with PREFIX declarations).

    Notes:
        * Only the **asserted** graph is queried — no reasoning/inference.
        * CONSTRUCT returns each related class's *full* outgoing structural subgraph,
          which includes its own ``subClassOf`` / restriction triples.  Use
          ``construct=False`` for plain IRI-only retrieval.
        * Anonymous-expression *targets* are not supported; ``target`` must resolve to
          a named IRI or SPARQL variable.
        * ``run_owlready2`` does not support CONSTRUCT; use
          ``run_rdflib(q, world.as_rdflib_graph())`` for CONSTRUCT against owlready2
          data.
    """
    c = _target_iri(target)
    rels = list(relations)
    if not rels:
        raise ValueError("at least one relation is required")
    unknown = set(rels) - set(RELATIONS)
    if unknown:
        raise ValueError(f"unknown relations: {sorted(unknown)}")

    class_rels = [r for r in rels if r != "individual"]
    want_individual = "individual" in rels

    TARGET_ORIGINATING = {"super", "direct_super", "equiv"}
    blocks = []
    if class_rels:
        union = " UNION ".join(f"{{ {_relation_clause(r, c, '?rel')} }}" for r in class_rels)
        if construct:
            blocks.append(f"{{ {union} ?rel {STRUCTURAL_PATH}* ?s . ?s ?p ?o . }}")
            if any(r in TARGET_ORIGINATING for r in class_rels):
                blocks.append(f"{{ {c} {STRUCTURAL_PATH}* ?s . ?s ?p ?o . }}")
        else:
            blocks.append(f"{{ {union} FILTER(isIRI(?rel)) }}")
    if want_individual:
        if construct:
            blocks.append(f"{{ {_relation_clause('individual', c, '?ind')} "
                          f"?ind {STRUCTURAL_PATH}* ?s . ?s ?p ?o . }}")
        else:
            blocks.append(f"{{ {_relation_clause('individual', c, '?ind')} FILTER(isIRI(?ind)) }}")

    where = " UNION ".join(blocks)
    head = "CONSTRUCT { ?s ?p ?o }" if construct else (
        "SELECT DISTINCT ?rel ?ind" if want_individual and class_rels
        else "SELECT DISTINCT ?ind" if want_individual else "SELECT DISTINCT ?rel")
    return f"{prefix_header()}\n{head}\nWHERE {{\n{where}\n}}"
