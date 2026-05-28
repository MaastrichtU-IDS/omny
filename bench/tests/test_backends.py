from pymos import parse
from bench.backends.owlready2_mem import OwlreadyMemBackend


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
