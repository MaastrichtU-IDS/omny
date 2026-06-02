"""Resolve Manchester IRIs/names to owlready2 entities, creating them on demand."""
import types
from typing import Dict, Optional

import owlready2


class EntityResolver:
    """Maps Manchester class/property/individual names to owlready2 entities.

    Names may be full IRIs (``http://...``), prefixed (``pre:local``), or simple
    (``local``, resolved against the ontology base IRI). Referenced entities are
    created in the target ontology if they do not yet exist.
    """

    def __init__(self, onto: owlready2.Ontology, prefixes: Optional[Dict[str, str]] = None):
        self.onto = onto
        self.world = onto.world
        self.prefixes = dict(prefixes or {})
        self.base = onto.base_iri  # e.g. "http://omny.test/onto.owl#"

    def expand(self, name: str) -> str:
        """Return the full IRI for a Manchester name."""
        if name.startswith("<") and name.endswith(">"):
            return name[1:-1]
        if name.startswith("http://") or name.startswith("https://") or name.startswith("urn:"):
            return name
        if ":" in name:
            prefix, _, local = name.partition(":")
            if prefix in self.prefixes:
                return self.prefixes[prefix] + local
            raise ValueError(f"Unknown prefix {prefix!r} in {name!r}")
        if "" in self.prefixes:
            return self.prefixes[""] + name
        return self.base + name

    def _split(self, iri: str):
        """Split an IRI into (namespace_base, local_name)."""
        sep = max(iri.rfind("#"), iri.rfind("/"))
        return iri[: sep + 1], iri[sep + 1:]

    def _get_or_create(self, name: str, parent) -> owlready2.EntityClass:
        iri = self.expand(name)
        existing = self.world[iri]
        if existing is not None:
            return existing
        ns_base, local = self._split(iri)
        namespace = self.onto.get_namespace(ns_base)
        with namespace:
            return types.new_class(local, (parent,))

    def get_class(self, name: str) -> owlready2.ThingClass:
        return self._get_or_create(name, owlready2.Thing)

    def get_object_property(self, name: str) -> owlready2.ObjectPropertyClass:
        return self._get_or_create(name, owlready2.ObjectProperty)

    def get_data_property(self, name: str) -> owlready2.DataPropertyClass:
        return self._get_or_create(name, owlready2.DataProperty)

    def get_annotation_property(self, name: str):
        """Return (or create) an annotation property by name.

        OWL 2 punning allows the same IRI to be used as both an object
        property and an annotation property (real example: OBO's
        ``RO_0002433`` in the Human Phenotype Ontology). When the IRI is
        already declared as a non-annotation entity we **return that
        existing entity** rather than raise — the value is then stored
        via ``prop[entity].append(value)`` in ``_apply_annotations``,
        which is IRI-keyed and works for any property kind. The earlier
        raise was added in PR #25 to prevent same-local-name collisions
        between two distinct annotation properties (``rdfs:comment`` vs
        ``schema.org/comment``); that collision is now prevented by the
        IRI-keyed write itself, so the raise is no longer needed.
        """
        iri = self.expand(name)
        existing = self.world[iri]
        if existing is not None:
            return existing
        return self._get_or_create(name, owlready2.AnnotationProperty)

    def get_individual(self, name: str) -> owlready2.Thing:
        iri = self.expand(name)
        existing = self.world[iri]
        if existing is not None:
            return existing
        ns_base, local = self._split(iri)
        namespace = self.onto.get_namespace(ns_base)
        with namespace:
            return owlready2.Thing(local, namespace=namespace)
