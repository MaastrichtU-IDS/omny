"""Backend protocol and registry."""
from __future__ import annotations

from typing import Iterable, Protocol


class Backend(Protocol):
    name: str
    is_persistent: bool

    def load(self, ontology) -> object:
        """Populate the store from an owlready2 Ontology. Returns a handle
        (opaque; for endpoint backends it's a session)."""

    def construct(self, sparql: str) -> Iterable:
        """Run a CONSTRUCT query; return iterable of triples. May raise
        NotImplementedError for backends that don't support CONSTRUCT
        (notably owlready2's native engine)."""

    def select(self, sparql: str) -> Iterable:
        """Run a SELECT query; return iterable of result rows."""

    def close(self) -> None: ...
