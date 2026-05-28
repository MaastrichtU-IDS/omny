"""SQLite-on-disk owlready2 backend. Cold opens read from the file."""
import io
import tempfile
from pathlib import Path

import owlready2


class OwlreadySqliteBackend:
    is_persistent = True

    def __init__(self, db_path: Path):
        self.name = f"owlready2_sqlite[{db_path.name}]"
        self._world = owlready2.World(filename=str(db_path))

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        ont_iri = ontology.base_iri.rstrip("#").rstrip("/")
        new_onto = self._world.get_ontology(ont_iri)
        with tempfile.NamedTemporaryFile(suffix=".nt", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        new_onto.load(only_local=True, fileobj=open(path, "rb"))
        self._world.save()
        return new_onto

    def construct(self, sparql: str):
        raise NotImplementedError("owlready2's native SPARQL engine does not support CONSTRUCT")

    def select(self, sparql: str):
        return self._world.sparql(sparql)

    def close(self):
        self._world.save()
        self._world.close()
