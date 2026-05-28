"""In-memory owlready2 backend (SQLite :memory:)."""
import io

import owlready2


class OwlreadyMemBackend:
    name = "owlready2_mem"
    is_persistent = False

    def __init__(self):
        self._world = owlready2.World()

    def load(self, ontology):
        # owlready2 ontologies live in their own World; copy via N-Triples.
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        buf.seek(0)
        # the World.get_ontology + load_file route round-trips axioms
        ont_iri = ontology.base_iri.rstrip("#").rstrip("/")
        new_onto = self._world.get_ontology(ont_iri)
        # write to a temp file because owlready2's load wants a path/file object
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".nt", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        new_onto.load(only_local=True, fileobj=open(path, "rb"))
        return new_onto

    def construct(self, sparql: str):
        raise NotImplementedError("owlready2's native SPARQL engine does not support CONSTRUCT")

    def select(self, sparql: str):
        return self._world.sparql(sparql)

    def close(self):
        self._world.close()
