"""Run a generated SPARQL query against various backends. Each runner imports its
backend lazily so pymos has no hard dependency on any of them."""


def run_rdflib(query: str, graph):
    """rdflib Graph. CONSTRUCT -> rdflib.Graph; SELECT -> list of result rows."""
    result = graph.query(query)
    return result.graph if result.type == "CONSTRUCT" else list(result)


def run_pyoxigraph(query: str, store):
    """pyoxigraph Store. CONSTRUCT -> QueryTriples iterator; SELECT -> QuerySolutions."""
    return store.query(query)


def run_owlready2(query: str, world):
    """owlready2 World. Uses its native SPARQL engine."""
    return list(world.sparql(query))


def run_endpoint(query: str, url: str):
    """Remote SPARQL endpoint via SPARQLWrapper."""
    from SPARQLWrapper import SPARQLWrapper, TURTLE
    sw = SPARQLWrapper(url)
    sw.setQuery(query)
    sw.setReturnFormat(TURTLE)
    return sw.query().convert()
