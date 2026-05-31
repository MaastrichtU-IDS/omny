"""In-memory pyoxigraph backend."""
import io
import re

import pyoxigraph


_BAD_IRI_CHAR = re.compile(rb"[\x00-\x20<>{}|^`\\]")


def _sanitize_ntriples(data: bytes) -> bytes:
    """Repair owlready2's occasional malformed N-Triples output.

    Pymos's parser, when it encounters an unsupported axiom keyword
    (e.g. ``SubPropertyChain:`` in sio.omn) inside an ObjectProperty
    frame, currently lets the unknown-keyword text bleed into the next
    entity's IRI. owlready2 then serialises that multi-line value as an
    ``<...>`` IRI containing literal newlines + Manchester text, e.g.::

        <http://semanticscience.org/resource/SIO_000322
            SubPropertyChain:
                sio:SIO_000325 o sio:SIO_000068> <pred> <obj> .

    Pyoxigraph is strict (W3C N-Triples conformant) and refuses to parse
    such IRIs, aborting the whole load. Until the upstream parser stops
    producing them, this bridge:

    1. Joins consecutive lines until a terminating ``" ."`` is seen
       (so a multi-line entry collapses to one logical N-Triple).
    2. Drops any joined line whose ``<…>`` segments still contain a
       disallowed code point (whitespace, control char, ``<``, ``>``,
       ``{``, ``}``, ``|``, ``^``, backtick, or backslash — the
       characters W3C explicitly excludes from ``IRIREF``). See
       https://www.w3.org/TR/n-triples/#grammar-production-IRIREF.

    The result is a sanitised byte stream that pyoxigraph will accept;
    malformed triples are silently dropped (consistent with the upstream
    parser already silently dropping the same axioms).
    """
    out: list[bytes] = []
    buf = b""
    for line in data.split(b"\n"):
        buf = (buf + line.lstrip()) if buf else line
        if buf.rstrip().endswith(b" ."):
            if not any(_BAD_IRI_CHAR.search(m) for m in re.findall(rb"<([^>]*)>", buf)):
                out.append(buf)
            buf = b""
    # Any trailing unterminated remainder is by definition not a valid triple — drop it.
    return b"\n".join(out)


class PyoxigraphMemBackend:
    name = "pyoxigraph_mem"
    is_persistent = False

    def __init__(self):
        self._store = pyoxigraph.Store()

    def load(self, ontology):
        # owlready2 → N-Triples (native, no rdflib hop) → sanitiser → pyoxigraph
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        nt = _sanitize_ntriples(buf.getvalue())
        self._store.load(nt, format=pyoxigraph.RdfFormat.N_TRIPLES)
        return self._store

    def construct(self, sparql: str):
        return self._store.query(sparql)

    def select(self, sparql: str):
        return self._store.query(sparql)

    def close(self):
        # in-memory store has no explicit close
        pass
