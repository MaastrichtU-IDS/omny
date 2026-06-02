from omny import parse
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


from bench.backends.pyoxigraph_rocksdb import PyoxigraphRocksdbBackend


def test_pyoxigraph_rocksdb_persists(pizza_text, tmp_path):
    onto = parse(pizza_text)
    db = tmp_path / "pizza.ox"

    b1 = PyoxigraphRocksdbBackend(db)
    b1.load(onto)
    n1 = list(b1.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))[0]["n"].value
    b1.close()

    b2 = PyoxigraphRocksdbBackend(db)
    n2 = list(b2.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))[0]["n"].value
    assert n1 == n2
    assert b2.is_persistent is True
    b2.close()


from bench.backends.endpoint_oxigraph import EndpointOxigraphBackend
from bench.tests.conftest import requires_docker


@requires_docker
def test_endpoint_oxigraph_load_and_query(pizza_text):
    onto = parse(pizza_text)
    b = EndpointOxigraphBackend()  # spins up an ephemeral container on a random port
    try:
        b.load(onto)
        rows = list(b.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))
        assert int(rows[0]["n"]) > 0
    finally:
        b.close()


def test_pyoxigraph_sanitizer_joins_multiline_iri_and_drops_invalid():
    """Pre-fix: owlready2 sometimes emits N-Triples with multi-line IRIs
    (caused upstream by an unknown axiom keyword leaking into the next
    subject — see sio.omn + SubPropertyChain). Pyoxigraph is strict and
    rejects them, aborting the entire load. The sanitiser must
    (a) collapse continuation lines until the terminating ``" ."`` and
    (b) drop any line whose ``<...>`` still contains a forbidden code
    point (whitespace, control char, etc.).
    """
    from bench.backends.pyoxigraph_mem import _sanitize_ntriples

    raw = (
        b'<http://ex.org/A> <http://ex.org/p> <http://ex.org/B> .\n'
        # Two malformed sequences below — both span multiple lines and end
        # up containing whitespace inside the IRI:
        b'<http://ex.org/C\n'
        b'    SubPropertyChain:\n'
        b'        x o y> <http://ex.org/p> <http://ex.org/D> .\n'
        # A clean line after the malformed group must still be kept:
        b'<http://ex.org/E> <http://ex.org/p> <http://ex.org/F> .\n'
    )
    out = _sanitize_ntriples(raw)
    lines = [l for l in out.split(b'\n') if l.strip()]
    # The two valid triples survive; the malformed multi-line block is dropped.
    assert b'<http://ex.org/A>' in out
    assert b'<http://ex.org/E>' in out
    # No surviving line contains the leaked Manchester text:
    assert b'SubPropertyChain' not in out
    assert len(lines) == 2


def test_pyoxigraph_sanitizer_preserves_clean_input_unchanged():
    """A well-formed N-Triples input must pass through losslessly
    (modulo trailing newline normalisation)."""
    from bench.backends.pyoxigraph_mem import _sanitize_ntriples
    raw = (
        b'<http://ex.org/A> <http://ex.org/p> <http://ex.org/B> .\n'
        b'<http://ex.org/C> <http://ex.org/p> "literal" .\n'
    )
    out = _sanitize_ntriples(raw)
    assert b'<http://ex.org/A>' in out
    assert b'<http://ex.org/C>' in out
    assert b'"literal"' in out
