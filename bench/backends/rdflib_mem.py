"""In-memory rdflib backend. Expected to OOM past ChEBI-core; runner marks
oversized cells n/a via memory cap."""
import io

import rdflib


class RdflibMemBackend:
    name = "rdflib_mem"
    is_persistent = False

    def __init__(self):
        self._graph = rdflib.Graph()

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._graph.parse(data=buf.getvalue(), format="nt")
        return self._graph

    def construct(self, sparql: str):
        return self._graph.query(sparql).graph

    def select(self, sparql: str):
        return list(self._graph.query(sparql))

    def close(self):
        self._graph.close()
