"""OWL structural predicates for walking class-expression blank-node subgraphs."""

PREFIXES = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

_STRUCTURAL_PREDICATES = [
    "owl:onProperty", "owl:someValuesFrom", "owl:allValuesFrom", "owl:hasValue",
    "owl:hasSelf", "owl:onClass", "owl:onDataRange", "owl:onDatatype",
    "owl:withRestrictions", "owl:intersectionOf", "owl:unionOf", "owl:complementOf",
    "owl:oneOf", "owl:minCardinality", "owl:maxCardinality", "owl:cardinality",
    "owl:minQualifiedCardinality", "owl:maxQualifiedCardinality",
    "owl:qualifiedCardinality",
    # owl:inverseOf is included to capture inverse-property expressions in class axioms.
    "owl:inverseOf",
    # rdfs:subClassOf is deliberately EXCLUDED: walking it would traverse the class
    # hierarchy and over-collect triples from ancestor/descendant classes instead of
    # limiting the walk to the blank-node sub-graph of a single class expression.
    "rdf:first", "rdf:rest", "rdf:type",
]

# A SPARQL property-path alternation; wrap with * at the call site to walk closures.
STRUCTURAL_PATH = "(" + "|".join(_STRUCTURAL_PREDICATES) + ")"


def prefix_header() -> str:
    return "\n".join(f"PREFIX {p}: <{iri}>" for p, iri in PREFIXES.items())
