"""Run a generated SPARQL query against various backends. Each runner imports its
backend lazily so pymos has no hard dependency on any of them."""
import re

_CONSTRUCT_RE = re.compile(r"\bCONSTRUCT\b", re.IGNORECASE)


def _is_construct(query: str) -> bool:
    return bool(_CONSTRUCT_RE.search(query))


def run_rdflib(query: str, graph):
    """rdflib Graph. CONSTRUCT -> rdflib.Graph; SELECT -> list of result rows."""
    result = graph.query(query)
    return result.graph if result.type == "CONSTRUCT" else list(result)


def run_pyoxigraph(query: str, store):
    """pyoxigraph Store. CONSTRUCT -> QueryTriples iterator; SELECT -> QuerySolutions."""
    return store.query(query)


def run_owlready2(query: str, world):
    """owlready2 World, via its native SPARQL engine. SELECT-only.

    owlready2's engine does not support CONSTRUCT; for a CONSTRUCT (subgraph)
    query against owlready2 data, use ``run_rdflib(query, world.as_rdflib_graph())``.
    """
    if _is_construct(query):
        raise ValueError(
            "run_owlready2 supports SELECT queries only (owlready2's SPARQL engine "
            "cannot parse CONSTRUCT). For CONSTRUCT, use "
            "run_rdflib(query, world.as_rdflib_graph()).")
    return list(world.sparql(query))


def run_endpoint(query: str, url: str):
    """Remote SPARQL endpoint via SPARQLWrapper. CONSTRUCT -> Turtle graph; SELECT -> JSON results."""
    from SPARQLWrapper import SPARQLWrapper, TURTLE, JSON
    sw = SPARQLWrapper(url)
    sw.setQuery(query)
    sw.setReturnFormat(TURTLE if _is_construct(query) else JSON)
    return sw.query().convert()
