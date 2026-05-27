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
