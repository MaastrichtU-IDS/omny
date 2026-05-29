"""Declarative corpus manifest. Each entry describes one ontology download."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tier = Literal["tiny", "small", "medium", "large", "huge"]
TIERS: tuple[Tier, ...] = ("tiny", "small", "medium", "large", "huge")


@dataclass(frozen=True)
class CorpusEntry:
    name: str                      # short identifier, e.g. "go-core"
    tier: Tier
    url: str                       # canonical download URL
    sha256: str                    # 64-hex SHA256 OR "skip-checksum" for moving upstreams
    approx_axioms: int             # documented in design spec §4
    fmt: Literal["owx", "rdfxml", "obo"]  # source format
    notes: str = ""


CORPUS: tuple[CorpusEntry, ...] = (
    # Tiny tier — DL tutorial ontologies
    CorpusEntry(
        name="pizza", tier="tiny",
        url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        sha256="skip-checksum", approx_axioms=250, fmt="rdfxml",
        notes="Manchester / Protege pizza tutorial ontology",
    ),
    CorpusEntry(
        name="wine", tier="tiny",
        url="https://www.w3.org/TR/owl-guide/wine.rdf",
        sha256="skip-checksum", approx_axioms=700, fmt="rdfxml",
        notes="W3C OWL Guide wine example",
    ),
    CorpusEntry(
        name="family", tier="tiny",
        url="https://raw.githubusercontent.com/owlcs/owlapi/version5/contract/src/test/resources/family.owl",
        sha256="skip-checksum", approx_axioms=150, fmt="rdfxml",
        notes="OWL-API family.owl test fixture",
    ),
    # Small tier
    CorpusEntry(
        name="sio", tier="small",
        url="https://raw.githubusercontent.com/MaastrichtU-IDS/semanticscience/master/ontology/sio/release/sio-release.owl",
        sha256="skip-checksum", approx_axioms=3_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="obi-core", tier="small",
        url="http://purl.obolibrary.org/obo/obi/dev/obi.owl",
        sha256="skip-checksum", approx_axioms=5_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="doid", tier="small",
        url="http://purl.obolibrary.org/obo/doid.owl",
        sha256="skip-checksum", approx_axioms=10_000, fmt="rdfxml",
    ),
    # Medium tier
    CorpusEntry(
        name="go-core", tier="medium",
        url="http://purl.obolibrary.org/obo/go/go-basic.obo",
        sha256="skip-checksum", approx_axioms=30_000, fmt="obo",
        notes="GO basic; converted to .owx via ROBOT at download time",
    ),
    CorpusEntry(
        name="chebi-lite", tier="medium",
        url="http://purl.obolibrary.org/obo/chebi/chebi_lite.owl",
        sha256="skip-checksum", approx_axioms=50_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="hp", tier="medium",
        url="http://purl.obolibrary.org/obo/hp.owl",
        sha256="skip-checksum", approx_axioms=20_000, fmt="rdfxml",
    ),
    # Large tier
    CorpusEntry(
        name="go-full", tier="large",
        url="http://purl.obolibrary.org/obo/go.owl",
        sha256="skip-checksum", approx_axioms=80_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="chebi-full", tier="large",
        url="http://purl.obolibrary.org/obo/chebi.owl",
        sha256="skip-checksum", approx_axioms=140_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="ncit", tier="large",
        url="http://purl.obolibrary.org/obo/ncit.owl",
        sha256="skip-checksum", approx_axioms=170_000, fmt="rdfxml",
    ),
    # Huge tier — license-gated, requires BENCH_SNOMED=1 + UMLS file on disk
    # (no entry committed; loader emits a note when BENCH_SNOMED is set)
)


def by_tier(tier: Tier) -> list[CorpusEntry]:
    return [e for e in CORPUS if e.tier == tier]
