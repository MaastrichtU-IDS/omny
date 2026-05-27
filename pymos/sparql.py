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
    c = _target_iri(target)
    rels = list(relations)
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
            blocks.append(f"{{ {union} }}")
    if want_individual:
        if construct:
            blocks.append(f"{{ {_relation_clause('individual', c, '?ind')} "
                          f"?ind {STRUCTURAL_PATH}* ?s . ?s ?p ?o . }}")
        else:
            blocks.append(f"{{ {_relation_clause('individual', c, '?ind')} }}")

    where = " UNION ".join(blocks)
    head = "CONSTRUCT { ?s ?p ?o }" if construct else (
        "SELECT DISTINCT ?rel ?ind" if want_individual and class_rels
        else "SELECT DISTINCT ?ind" if want_individual else "SELECT DISTINCT ?rel")
    return f"{prefix_header()}\n{head}\nWHERE {{\n{where}\n}}"
