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

    _RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    _OWL_NAMED_INDIVIDUAL = "http://www.w3.org/2002/07/owl#NamedIndividual"

    def __init__(self, onto: owlready2.Ontology, prefixes: Optional[Dict[str, str]] = None):
        self.onto = onto
        self.world = onto.world
        self.prefixes = dict(prefixes or {})
        self.base = onto.base_iri  # e.g. "http://omny.test/onto.owl#"
        # nodeID label -> owlready2 anonymous individual, so repeated ``_:x``
        # references within one parse resolve to the same blank node.
        self._blank_individuals: Dict[str, owlready2.Thing] = {}

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

    @staticmethod
    def _is_node_id(name: str) -> bool:
        """True if *name* is a Manchester ``nodeID`` (blank node, ``_:label``)."""
        return name.startswith("_:")

    def get_individual(self, name: str) -> owlready2.Thing:
        if self._is_node_id(name):
            return self._get_or_create_anonymous(name[2:])
        iri = self.expand(name)
        existing = self.world[iri]
        if existing is not None:
            return existing
        ns_base, local = self._split(iri)
        namespace = self.onto.get_namespace(ns_base)
        with namespace:
            return owlready2.Thing(local, namespace=namespace)

    def _get_or_create_anonymous(self, label: str) -> owlready2.Thing:
        """Return the owlready2 anonymous individual (blank node) for nodeID
        *label*, creating it on first reference.

        owlready2 has no public constructor for an anonymous individual, so we
        mint a fresh blank-node storid, anchor it with an
        ``rdf:type owl:NamedIndividual`` triple (which makes owlready2
        materialise a ``Thing`` with that negative storid and an empty IRI),
        and hand back the materialised object. The loader then applies
        ``Types:``/``Facts:``/``Annotations:`` to it exactly as for a named
        individual. Repeated ``_:label`` references in one document reuse the
        same blank node (cached by *label*).
        """
        existing = self._blank_individuals.get(label)
        if existing is not None:
            return existing
        bnode = self.world.new_blank_node()
        rdf_type = self.world._abbreviate(self._RDF_TYPE)
        named_individual = self.world._abbreviate(self._OWL_NAMED_INDIVIDUAL)
        self.onto.graph._add_obj_triple_raw_spo(bnode, rdf_type, named_individual)
        ind = self.world._get_by_storid(bnode)
        self._blank_individuals[label] = ind
        return ind
