from pymos.vocab import STRUCTURAL_PATH, PREFIXES


def test_structural_path_is_a_property_path_alternation():
    assert "owl:someValuesFrom" in STRUCTURAL_PATH
    assert "rdf:first" in STRUCTURAL_PATH
    assert "rdf:rest" in STRUCTURAL_PATH
    assert "|" in STRUCTURAL_PATH  # it's an alternation


def test_prefixes_define_owl_rdf_rdfs():
    assert PREFIXES["owl"] == "http://www.w3.org/2002/07/owl#"
    assert PREFIXES["rdfs"] == "http://www.w3.org/2000/01/rdf-schema#"
