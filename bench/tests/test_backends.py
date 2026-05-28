from pymos import parse
from bench.backends.owlready2_mem import OwlreadyMemBackend
from bench.backends.pyoxigraph_mem import PyoxigraphMemBackend
from bench.backends.rdflib_mem import RdflibMemBackend
from bench.backends.owlready2_sqlite import OwlreadySqliteBackend


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


def test_rdflib_mem_load_and_construct(pizza_text):
    onto = parse(pizza_text)
    b = RdflibMemBackend()
    b.load(onto)
    g = b.construct("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5")
    triples = list(g)
    assert len(triples) > 0
    b.close()


def test_owlready_sqlite_persists_across_handles(pizza_text, tmp_path):
    onto = parse(pizza_text)
    db = tmp_path / "pizza.sqlite3"

    b1 = OwlreadySqliteBackend(db)
    b1.load(onto)
    rows1 = list(b1.select(
        "SELECT (COUNT(?c) AS ?n) WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    b1.close()

    # Open a fresh handle on the same SQLite file — data must survive.
    b2 = OwlreadySqliteBackend(db)
    rows2 = list(b2.select(
        "SELECT (COUNT(?c) AS ?n) WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    assert rows1 == rows2
    assert b2.is_persistent is True
    b2.close()
