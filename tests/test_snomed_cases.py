"""SNOMED CT conformance tests for omny.

These exercise the SNOMED CT test cases from the owlready2 benchmarks
(benchmark_manchester.py / benchmark_snomed.py) against omny's public API:

  * named-class subsumption  -> class_relations_query(<iri>, relations=[...])
  * role-restriction DL       -> parse_expression(...) +
                                 class_relations_query(expr, role_encoding="flat")

For each case the EXPECTED count is computed live from a reference flat-triple
SPARQL query (the answer the owlready2 fork produces) and compared to omny's
result, so the assertions hold regardless of the exact SNOMED CT release.

SNOMED CT data is large and machine-specific, so the whole module is SKIPPED
unless the prebuilt store exists. Build it once with:

    python3 benchmark_snomed.py        # creates the world cache + pyoxigraph store

Then run:

    pytest tests/test_snomed_cases.py
"""
import os
import re

import pytest

# Paths to the prebuilt SNOMED CT artifacts; override via env vars to point at
# your own build. Defaults match the owlready2 benchmark harness output.
WORLD_CACHE = os.environ.get("OMNY_SNOMED_WORLD", "/tmp/snomed_benchmark_world.sqlite3")
OX_STORE = os.environ.get("OMNY_SNOMED_OX_STORE", "/tmp/snomed_ox_store")
B = "http://snomed.info/id/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
PFX = {"sct": B, "owl": OWL, "rdfs": RDFS,
       "xsd": "http://www.w3.org/2001/XMLSchema#"}

pytestmark = pytest.mark.skipif(
    not (os.path.exists(WORLD_CACHE) and os.path.exists(OX_STORE + "/.ready")),
    reason="SNOMED CT prebuilt store not present "
    "(set OMNY_SNOMED_WORLD / OMNY_SNOMED_OX_STORE, or build the benchmark store)",
)

# ── concept ids ────────────────────────────────────────────────────────────────
BODY_STRUCTURE = "123037004"
ADVERSE_REACTION = "281647001"
DISEASE = "64572001"
FINDING_SITE = "363698007"
ASSOC_MORPH = "116676008"
METHOD = "260686004"
HEART_STRUCTURE = "80891009"

SUB = f"<{RDFS}subClassOf>"


@pytest.fixture(scope="module")
def snomed():
    import owlready2
    import pyoxigraph

    world = owlready2.World()
    world.set_backend(filename=WORLD_CACHE)
    onto = next(iter(world.ontologies.values()), None)
    try:
        store = pyoxigraph.Store.read_only(OX_STORE)
    except Exception:  # noqa: BLE001 - fall back to read/write open
        store = pyoxigraph.Store(OX_STORE)
    return world, onto, store


def _count(store, sparql):
    return sum(1 for _ in store.query(sparql))


def _expand_sct(text):
    # omny's Manchester lexer rejects numeric prefixed names (sct:363698007),
    # so expand them to full IRIs first.
    return re.sub(r"\bsct:(\d+)\b", lambda m: f"<{B}{m.group(1)}>", text)


# ── named-class subsumption cases ───────────────────────────────────────────────
# (id, concept-id, relation, reference SPARQL)
NAMED_CASES = [
    ("body_structure_direct", BODY_STRUCTURE, "direct_sub",
     f"SELECT DISTINCT ?s WHERE {{ ?s {SUB} <{B}{BODY_STRUCTURE}> }}"),
    ("adverse_reaction_transitive", ADVERSE_REACTION, "sub",
     f"SELECT DISTINCT ?s WHERE {{ ?s {SUB}+ <{B}{ADVERSE_REACTION}> }}"),
    ("disease_transitive", DISEASE, "sub",
     f"SELECT DISTINCT ?s WHERE {{ ?s {SUB}+ <{B}{DISEASE}> }}"),
]


@pytest.mark.parametrize("cid,concept,rel,ref", NAMED_CASES,
                         ids=[c[0] for c in NAMED_CASES])
def test_named_class_subsumption(snomed, cid, concept, rel, ref):
    from omny import class_relations_query
    from omny.store import run_pyoxigraph

    _, _, store = snomed
    expected = _count(store, ref)
    assert expected > 0  # sanity: the concept exists in this SNOMED release
    q = class_relations_query(f"<{B}{concept}>", relations=[rel], construct=False)
    actual = sum(1 for _ in run_pyoxigraph(q, store))
    assert actual == expected


# ── role-restriction DL cases (flat encoding) ───────────────────────────────────
# (id, manchester expression, reference SPARQL)
ROLE_CASES = [
    ("fs_value_heart",
     f"sct:{FINDING_SITE} value sct:{HEART_STRUCTURE}",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{FINDING_SITE}> <{B}{HEART_STRUCTURE}> }}"),
    ("fs_some",
     f"sct:{FINDING_SITE} some owl:Thing",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{FINDING_SITE}> ?v }}"),
    ("am_some",
     f"sct:{ASSOC_MORPH} some owl:Thing",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{ASSOC_MORPH}> ?v }}"),
    ("fs_and_am",
     f"(sct:{FINDING_SITE} some owl:Thing) and (sct:{ASSOC_MORPH} some owl:Thing)",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{FINDING_SITE}> ?a . ?s <{B}{ASSOC_MORPH}> ?b }}"),
    ("fs_and_method_empty",
     f"(sct:{FINDING_SITE} some owl:Thing) and (sct:{METHOD} some owl:Thing)",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{FINDING_SITE}> ?a . ?s <{B}{METHOD}> ?b }}"),
    ("am_and_not_method",
     f"(sct:{ASSOC_MORPH} some owl:Thing) and not (sct:{METHOD} some owl:Thing)",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{ASSOC_MORPH}> ?a . "
     f"FILTER NOT EXISTS {{ ?s <{B}{METHOD}> ?m }} }}"),
    ("fs_value_heart_and_am",
     f"(sct:{FINDING_SITE} value sct:{HEART_STRUCTURE}) and (sct:{ASSOC_MORPH} some owl:Thing)",
     f"SELECT DISTINCT ?s WHERE {{ ?s <{B}{FINDING_SITE}> <{B}{HEART_STRUCTURE}> . "
     f"?s <{B}{ASSOC_MORPH}> ?am }}"),
    ("fs_min_2",
     f"sct:{FINDING_SITE} min 2 owl:Thing",
     f"SELECT ?s WHERE {{ ?s <{B}{FINDING_SITE}> ?v }} "
     f"GROUP BY ?s HAVING (COUNT(DISTINCT ?v) >= 2)"),
]


@pytest.mark.parametrize("cid,manchester,ref", ROLE_CASES,
                         ids=[c[0] for c in ROLE_CASES])
def test_role_restriction_flat(snomed, cid, manchester, ref):
    from omny import class_relations_query, parse_expression
    from omny.store import run_pyoxigraph

    _, onto, store = snomed
    expected = _count(store, ref)
    expr = parse_expression(_expand_sct(manchester), onto, prefixes=PFX)
    q = class_relations_query(expr, construct=False, role_encoding="flat")
    actual = sum(1 for _ in run_pyoxigraph(q, store))
    assert actual == expected


def test_structural_mode_finds_no_roles_on_flat_snomed(snomed):
    """Counterpart to flat mode: the default structural matcher looks for
    owl:Restriction bnodes, which SNOMED's flat encoding has none of -> 0."""
    from omny import class_relations_query, parse_expression
    from omny.store import run_pyoxigraph

    _, onto, store = snomed
    expr = parse_expression(f"<{B}{FINDING_SITE}> some owl:Thing", onto, prefixes=PFX)
    q = class_relations_query(expr, relations=["sub"], construct=False)  # structural
    assert sum(1 for _ in run_pyoxigraph(q, store)) == 0


@pytest.mark.skip(
    reason="omny direct_sub is O(n^2) (FILTER NOT EXISTS); times out beyond a "
    "few thousand children on SNOMED (Clinical finding 5317, Procedure 16253). "
    "Use the owlready2 native .subclasses() for direct children at scale."
)
def test_direct_sub_at_scale():  # pragma: no cover - documents a known limit
    pass
