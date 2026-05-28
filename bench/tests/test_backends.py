from pymos import parse
from bench.backends.owlready2_mem import OwlreadyMemBackend
from bench.backends.pyoxigraph_mem import PyoxigraphMemBackend


def test_owlready_mem_load_and_select(pizza_text):
    onto = parse(pizza_text)
    b = OwlreadyMemBackend()
    handle = b.load(onto)
    assert handle is not None
    # owlready2 SPARQL is SELECT-only; CONSTRUCT is not supported by it
    rows = list(b.select(
        "SELECT DISTINCT ?c WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    assert len(rows) > 0
    b.close()


def test_owlready_mem_name_and_persistence_flag():
    b = OwlreadyMemBackend()
    assert b.name == "owlready2_mem"
    assert b.is_persistent is False


def test_pyoxigraph_mem_load_and_construct(pizza_text):
    onto = parse(pizza_text)
    b = PyoxigraphMemBackend()
    b.load(onto)
    triples = list(b.construct(
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5"
    ))
    assert len(triples) > 0
    rows = list(b.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))
    assert int(rows[0]["n"].value) > 0
    b.close()
