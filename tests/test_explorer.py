"""Tests for the omny Explorer example app (examples/omny_explorer.py).

Two layers:
  * core functions (streamlit-free) — always run; exercise load / list / store
    build / relations / expression / sparql / render against biomed.omn.
  * the Streamlit UI — run headlessly via streamlit.testing.v1.AppTest; skipped
    if streamlit / pandas are not installed.
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(__file__)
_EXPLORER = os.path.normpath(os.path.join(_HERE, "..", "examples", "omny_explorer.py"))
_BIOMED = os.path.normpath(os.path.join(_HERE, "..", "examples", "data", "biomed.omn"))
NS = "http://example.org/biomed#"


def _load_explorer_module():
    spec = importlib.util.spec_from_file_location("omny_explorer", _EXPLORER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # safe: streamlit is imported only inside main()
    return mod


E = _load_explorer_module()


# ── core functions (no Streamlit) ───────────────────────────────────────────────
def test_load_and_list_entities():
    world, onto = E.load_from_path(_BIOMED)
    ents = E.list_entities(onto)
    assert len(ents["classes"]) == 11
    assert len(ents["object_properties"]) == 4
    assert len(ents["individuals"]) == 4
    # every entry has a name + iri
    assert all(e["iri"].startswith("http") for e in ents["classes"])


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_relations_query(kind):
    world, onto = E.load_from_path(_BIOMED)
    store = E.build_store(E.world_to_nt(world), kind)
    sparql, cols, rows = E.run_relations(NS + "Disease", ["sub"], store, kind)
    names = sorted(r[0].split("#")[-1] for r in rows)
    assert names == ["BacterialInfection", "GeneticDisease",
                     "InfectiousDisease", "ViralInfection"]
    assert "subClassOf" in sparql


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_expression_query_unordered(kind):
    """Anonymous expression match, incl. flipped operand order (unordered fix)."""
    world, onto = E.load_from_path(_BIOMED)
    store = E.build_store(E.world_to_nt(world), kind)
    for expr in ("Drug and (treats some BacterialInfection)",
                 "(treats some BacterialInfection) and Drug"):
        _, _, rows = E.run_expression(expr, onto, ["equiv"], store, kind)
        assert sorted(r[0].split("#")[-1] for r in rows) == ["Antibiotic"]


@pytest.mark.parametrize("kind", ["pyoxigraph", "rdflib"])
def test_execute_select(kind):
    world, onto = E.load_from_path(_BIOMED)
    store = E.build_store(E.world_to_nt(world), kind)
    cols, rows = E.execute_select(
        "SELECT ?c WHERE { ?c a <http://www.w3.org/2002/07/owl#Class> }", store, kind)
    assert len(rows) >= 11


def test_render_entity_and_document():
    world, onto = E.load_from_path(_BIOMED)
    pfx = E.prefixes_for(onto)
    frame = E.render_entity(world, NS + "Antibiotic", pfx)
    assert "Antibiotic" in frame and "SubClassOf" in frame
    doc = E.render_document(onto, pfx)
    import omny
    assert omny.render(omny.parse(doc), prefixes=pfx) == doc  # idempotent round-trip


# ── Streamlit UI (headless AppTest) ─────────────────────────────────────────────
def _app_test():
    pytest.importorskip("streamlit")
    pytest.importorskip("pandas")
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(_EXPLORER, default_timeout=60)


def test_ui_loads_example_and_shows_tabs():
    at = _app_test()
    at.run()
    assert not at.exception
    assert any(i.value.startswith("Load an ontology") for i in at.info)
    # default source is "Example" (biomed.omn) -> click Load
    [b for b in at.button if b.label == "Load"][0].click().run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Browse", "Relations", "Expression", "SPARQL"]
    assert any("Loaded" in s.value for s in at.success)


def test_ui_relations_tab():
    at = _app_test()
    at.run()
    [b for b in at.button if b.label == "Load"][0].click().run()
    [s for s in at.selectbox if s.label == "Class"][0].set_value("Disease").run()
    [b for b in at.button if "Run relations" in b.label][0].click().run()
    assert not at.exception
    assert any("4 result(s)" in s.value for s in at.success)


def test_ui_expression_tab():
    at = _app_test()
    at.run()
    [b for b in at.button if b.label == "Load"][0].click().run()
    ex = [t for t in at.text_input if t.label == "Manchester expression"][0]
    ex.set_value("(treats some BacterialInfection) and Drug").run()
    [b for b in at.button if "Match expression" in b.label][0].click().run()
    assert not at.exception
    assert any("1 match(es)" in s.value for s in at.success)
