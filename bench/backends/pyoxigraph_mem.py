"""In-memory pyoxigraph backend."""
import io

import pyoxigraph


class PyoxigraphMemBackend:
    name = "pyoxigraph_mem"
    is_persistent = False

    def __init__(self):
        self._store = pyoxigraph.Store()

    def load(self, ontology):
        # owlready2 → N-Triples (native, no rdflib hop) → pyoxigraph
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._store.load(buf.getvalue(), format=pyoxigraph.RdfFormat.N_TRIPLES)
        return self._store

    def construct(self, sparql: str):
        return self._store.query(sparql)

    def select(self, sparql: str):
        return self._store.query(sparql)

    def close(self):
        # in-memory store has no explicit close
        pass
