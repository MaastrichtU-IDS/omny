"""RocksDB-backed pyoxigraph store.

pyoxigraph 0.5.8 holds an exclusive RocksDB lock for the lifetime of the
``Store`` Python object. ``flush()`` alone does NOT release that lock —
the Rust ``Arc<Store>`` must be dropped. Under CPython's refcounting,
setting the only reference to ``None`` drops the Rust object synchronously
and releases the LOCK file immediately.
"""
import io
from pathlib import Path

import pyoxigraph


class PyoxigraphRocksdbBackend:
    is_persistent = True

    def __init__(self, db_path: Path):
        self.name = f"pyoxigraph_rocksdb[{db_path.name}]"
        db_path.mkdir(parents=True, exist_ok=True)
        self._store = pyoxigraph.Store(str(db_path))

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._store.load(buf.getvalue(), format=pyoxigraph.RdfFormat.N_TRIPLES)
        self._store.flush()
        return self._store

    def construct(self, sparql: str):
        return self._store.query(sparql)

    def select(self, sparql: str):
        return self._store.query(sparql)

    def close(self) -> None:
        # flush() persists in-flight writes; setting `self._store = None`
        # then releases the RocksDB lock via CPython refcounting so a second
        # handle on the same path can be opened.
        if self._store is not None:
            self._store.flush()
            self._store = None
