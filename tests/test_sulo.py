"""MIE/SULO DL-query tests for omny, on the proper-OWL ``mie-07-pre.owl``.

Recreated from the owlready2-fork script ``test_dl_mie.py``. Unlike SNOMED CT
(flat triples), the MIE-SULO ontology uses real OWL restriction axioms and
NamedIndividuals, so it exercises omny's *structural* matching (the default
``role_encoding="structural"``) on genuine ``owl:Restriction`` blank nodes.

The ontology is vendored as ``tests/data/sulo-clinical-cases.owl`` (the
sulo-tutorial ``mie-07-pre.owl``); its SULO and PRO ``owl:imports`` resolve to
the sibling ``tests/data/sulo.owl`` and ``tests/data/pro.owl`` via owlready2's
``onto_path`` (set in the fixture), so the tests run offline with no network
fetch and the ontology keeps its proper IRI + prefix declarations. Override the
path with ``OMNY_MIE_OWL`` if needed. The reasoner section of the original
script (Pellet / inferred types) is intentionally omitted — omny does no
reasoning.
"""
import io
import os

import pytest

_DEFAULT_OWL = os.path.join(os.path.dirname(__file__), "data", "sulo-clinical-cases.owl")
MIE_OWL = os.environ.get("OMNY_MIE_OWL", _DEFAULT_OWL)

pytestmark = pytest.mark.skipif(
    not os.path.exists(MIE_OWL),
    reason=f"SULO clinical-cases ontology not found at {MIE_OWL}")

SULO = "https://w3id.org/sulo/"
MIE = "https://w3id.org/ontostart/mie/"
PRO = "https://w3id.org/ontostart/pro/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
PFX = {"sulo": SULO, "mie": MIE, "pro": PRO,
       "owl": "http://www.w3.org/2002/07/owl#", "rdfs": RDFS}


@pytest.fixture(scope="module")
def mie():
    import owlready2
    import pyoxigraph

    owlready2.onto_path.append(os.path.dirname(MIE_OWL))
    w = owlready2.World()
    onto = w.get_ontology("file://" + os.path.abspath(MIE_OWL)).load()
    buf = io.BytesIO()
    for o in w.ontologies.values():
        try:
            o.save(file=buf, format="ntriples")
        except Exception:  # noqa: BLE001
            pass
    store = pyoxigraph.Store()
    store.load(io.BytesIO(buf.getvalue()), format=pyoxigraph.RdfFormat.N_TRIPLES)
    return w, onto, store


def _short(iri):
    return iri.strip("<>").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _run(q, store):
    from omny.store import run_pyoxigraph
    res = run_pyoxigraph(q, store)
    var = res.variables[0]
    return {_short(str(sol[var])) for sol in res}


def _count(store, sparql):
    return sum(1 for _ in store.query(sparql))


def _expr(text, onto):
    from omny import parse_expression
    return parse_expression(text, onto, prefixes=PFX)


# ── sanity ──────────────────────────────────────────────────────────────────────
def test_loaded(mie):
    w, _, store = mie
    assert sum(1 for _ in w.classes()) > 50
    assert sum(1 for _ in w.individuals()) > 20


# ── SIMPLE: named-class instances (ABox, direct rdf:type) ───────────────────────
def test_named_class_instances(mie):
    _, onto, store = mie
    from omny import class_relations_query
    q = class_relations_query(f"<{MIE}Breast>", relations=["individual"], construct=False)
    assert _run(q, store) == {"mary_left_breast", "mary_right_breast"}


# ── MEDIUM: TBox subclass hierarchy matches reference SPARQL ────────────────────
def test_subclass_hierarchy(mie):
    _, onto, store = mie
    from omny import class_relations_query
    q = class_relations_query(f"<{SULO}Process>", relations=["sub"], construct=False)
    omny_subs = _run(q, store)
    ground = _count(store, f"SELECT DISTINCT ?s WHERE {{ ?s <{RDFS}subClassOf>+ <{SULO}Process> }}")
    assert len(omny_subs) == ground and ground > 0
    assert "BreastCancer" in omny_subs


# ── HARD: structural equivalent-class matching on real OWL ──────────────────────
# Breast EquivalentTo: SpatialObject and hasDirectPart some {Nipple, MammaryGland,
#                      AdiposeTissue, SkinOfBreast}   (a 5-conjunct intersection)
_BREAST_FULL = (
    "sulo:SpatialObject and (sulo:hasDirectPart some mie:Nipple) "
    "and (sulo:hasDirectPart some mie:MammaryGland) "
    "and (sulo:hasDirectPart some mie:AdiposeTissue) "
    "and (sulo:hasDirectPart some mie:SkinOfBreast)")
_BREAST_PERMUTED = (
    "(sulo:hasDirectPart some mie:SkinOfBreast) and (sulo:hasDirectPart some mie:MammaryGland) "
    "and sulo:SpatialObject and (sulo:hasDirectPart some mie:AdiposeTissue) "
    "and (sulo:hasDirectPart some mie:Nipple)")


def test_structural_equiv_full_pattern(mie):
    _, onto, store = mie
    from omny import class_relations_query
    q = class_relations_query(_expr(_BREAST_FULL, onto), relations=["equiv"], construct=False)
    assert "Breast" in _run(q, store)


def test_structural_equiv_is_operand_order_independent(mie):
    """Same 5 conjuncts in a different order still match Breast (unordered fix)."""
    _, onto, store = mie
    from omny import class_relations_query
    q = class_relations_query(_expr(_BREAST_PERMUTED, onto), relations=["equiv"], construct=False)
    assert "Breast" in _run(q, store)


def test_cardinality_guard_rejects_subset(mie):
    """A 3-conjunct subset must NOT match Breast's 5-conjunct definition."""
    _, onto, store = mie
    from omny import class_relations_query
    subset = ("sulo:SpatialObject and (sulo:hasDirectPart some mie:Nipple) "
              "and (sulo:hasDirectPart some mie:MammaryGland)")
    q = class_relations_query(_expr(subset, onto), relations=["equiv"], construct=False)
    assert "Breast" not in _run(q, store)


def test_subexpression_containment_not_supported(mie):
    """Known limitation: omny matches a class's *whole* equivalentClass, not a
    nested sub-expression. The fork's classes_matching finds Breast for
    'hasDirectPart some Nipple' (containment); omny's class_relations_query does
    not, because that restriction is only a member of Breast's intersection."""
    _, onto, store = mie
    from omny import class_relations_query
    q = class_relations_query(_expr("sulo:hasDirectPart some mie:Nipple", onto),
                              relations=["equiv", "super"], construct=False)
    assert "Breast" not in _run(q, store)


# ── Round-trip of SULO/MIE Manchester expressions ───────────────────────────────
def test_expression_roundtrip(mie):
    _, onto, store = mie
    from omny import render_expression
    for text in [
        "sulo:Process and (sulo:hasParticipant some owl:Thing)",
        "mie:Tissue and (sulo:hasFeature some mie:ERPositive)",
        "mie:Tissue and (sulo:hasFeature some (mie:TumourGrade2 or mie:TumourGrade3))",
    ]:
        ce = _expr(text, onto)
        assert _expr(render_expression(ce, prefixes=PFX), onto) == ce
