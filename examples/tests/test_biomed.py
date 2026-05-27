from pathlib import Path

import pymos
from pymos import class_relations_query
from pymos.store import run_owlready2

OMN = Path(__file__).resolve().parents[1] / "data" / "biomed.omn"
NS = "http://example.org/biomed#"


def _load():
    return pymos.parse(OMN.read_text())


def _select_iris(onto, target, relations):
    q = class_relations_query(f"<{target}>", relations=relations, construct=False)
    return {r[0].iri for r in run_owlready2(q, onto.world)}


def test_classes_present():
    onto = _load()
    for local in ("Disease", "InfectiousDisease", "BacterialInfection",
                  "ViralInfection", "GeneticDisease", "Drug", "Antibiotic",
                  "Antiviral", "Gene", "BiologicalEntity", "ChemicalEntity"):
        assert onto.world[NS + local] is not None, local


def test_disease_subclasses():
    onto = _load()
    subs = _select_iris(onto, NS + "Disease", ("sub",))
    assert {NS + "InfectiousDisease", NS + "BacterialInfection",
            NS + "ViralInfection", NS + "GeneticDisease"} <= subs


def test_disease_direct_subclasses():
    onto = _load()
    direct = _select_iris(onto, NS + "Disease", ("direct_sub",))
    assert NS + "InfectiousDisease" in direct
    assert NS + "GeneticDisease" in direct
    assert NS + "BacterialInfection" not in direct  # grandchild, filtered out


def test_disease_superclasses():
    onto = _load()
    supers = _select_iris(onto, NS + "Disease", ("super",))
    assert NS + "BiologicalEntity" in supers


def test_bacterial_infection_individual():
    onto = _load()
    inds = _select_iris(onto, NS + "BacterialInfection", ("individual",))
    assert NS + "strep_throat" in inds


def test_antibiotic_equivalent_restriction():
    onto = _load()
    antibiotic = onto.world[NS + "Antibiotic"]
    assert len(antibiotic.equivalent_to) >= 1
