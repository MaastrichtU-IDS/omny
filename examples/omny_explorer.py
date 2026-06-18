"""omny Explorer — a Streamlit UI for exploring ontologies with omny.

Run:
    pip install omny[pyoxigraph] streamlit
    streamlit run examples/omny_explorer.py

Mirrors the spirit of owlready2's ui_explorer.py, but built entirely on omny's
public API so it works on *stock* owlready2 with no Java:

  * Load        — parse Manchester (.omn) with ``omny.parse`` or load any
                  owlready2-readable file (.owl/.ttl/.rdf/.nt).
  * Browse      — list classes / properties / individuals; render any entity
                  back to Manchester with ``omny.render_frame``.
  * Relations   — sub / super / direct_* / equiv / individual of a class via
                  ``omny.class_relations_query`` (store-agnostic).
  * Expression  — match an anonymous Manchester class expression (e.g.
                  ``treats some Disease``) with ``omny.parse_expression`` +
                  a structural ``class_relations_query`` (unordered operand match).
  * SPARQL      — run any SPARQL SELECT/ASK against the loaded graph.

(``render_document`` / ``render_entity`` remain as importable helpers for
rendering an ontology or entity back to Manchester.)

All SPARQL runs against an in-memory pyoxigraph Store (default) or rdflib Graph,
built once from the world's N-Triples and cached. The core functions below are
import-safe (no Streamlit), so they can be unit-tested headlessly.
"""
from __future__ import annotations

import os
import re
from io import BytesIO

import omny

# omny_fork_shim is a no-op on stock owlready2; if the pyoxigraph owlready2 fork
# is on the path it makes render / rdflib paths work there too. Optional.
try:  # pragma: no cover - best effort
    import omny_fork_shim  # noqa: F401
except Exception:
    pass

_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
_OWL = "http://www.w3.org/2002/07/owl#"
_XSD = "http://www.w3.org/2001/XMLSchema#"

RELATION_CHOICES = [
    "sub", "super", "direct_sub", "direct_super", "equiv", "individual",
]


# ── core: loading ──────────────────────────────────────────────────────────────
def load_from_text(omn_text: str):
    """Parse a Manchester document; return (world, onto)."""
    onto = omny.parse(omn_text)
    return onto.world, onto


def load_from_path(path: str):
    """Load an ontology file; .omn via omny.parse, else via owlready2."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".omn":
        with open(path, encoding="utf-8") as f:
            return load_from_text(f.read())
    import owlready2

    # Resolve owl:imports from sibling files in the same directory (e.g. a
    # vendored ontology + its imports) instead of fetching them over the web.
    folder = os.path.dirname(os.path.abspath(path))
    if folder not in owlready2.onto_path:
        owlready2.onto_path.append(folder)

    world = owlready2.World()
    fmt = {".ttl": "turtle", ".nt": "ntriples", ".rdf": "rdfxml",
           ".owl": "rdfxml", ".xml": "rdfxml"}.get(ext)
    onto = world.get_ontology("file://" + os.path.abspath(path))
    with open(path, "rb") as fobj:
        onto.load(fileobj=fobj, format=fmt) if fmt else onto.load(fileobj=fobj)
    return world, onto


def prefixes_for(onto) -> dict:
    """A sensible default prefix map for rendering this ontology."""
    base = onto.base_iri or ""
    return {"": base, "rdfs": _RDFS, "owl": _OWL, "xsd": _XSD}


# ── core: entity listing & rendering ────────────────────────────────────────────
def _entities(iterable):
    out = []
    for e in iterable:
        iri = getattr(e, "iri", None)
        if iri:
            out.append({"name": getattr(e, "name", iri), "iri": iri})
    return sorted(out, key=lambda d: d["name"].lower())


def list_entities(onto) -> dict:
    """Return {classes, object_properties, data_properties, individuals}."""
    return {
        "classes": _entities(onto.classes()),
        "object_properties": _entities(onto.object_properties()),
        "data_properties": _entities(onto.data_properties()),
        "individuals": _entities(onto.individuals()),
    }


def render_entity(world, iri: str, prefixes: dict) -> str:
    """Render one entity's Manchester frame."""
    entity = world[iri]
    if entity is None:
        return f"# <{iri}> not found"
    return omny.render_frame(entity, prefixes=prefixes)


def render_document(onto, prefixes: dict) -> str:
    return omny.render(onto, prefixes=prefixes)


# ── core: SPARQL store ──────────────────────────────────────────────────────────
def world_to_nt(world) -> bytes:
    """Serialize every ontology in the world to a single N-Triples blob.

    Uses owlready2's native serializer so it works identically on stock
    owlready2 and the pyoxigraph fork (concatenated N-Triples is valid N-Triples).
    """
    buf = BytesIO()
    for onto in list(world.ontologies.values()):
        try:
            onto.save(file=buf, format="ntriples")
        except Exception:
            pass
    return buf.getvalue()


def build_store(nt: bytes, kind: str = "pyoxigraph"):
    """Build a queryable store from N-Triples. kind: 'pyoxigraph' | 'rdflib'."""
    if kind == "pyoxigraph":
        import pyoxigraph

        store = pyoxigraph.Store()
        store.load(BytesIO(nt), format=pyoxigraph.RdfFormat.N_TRIPLES)
        return store
    if kind == "rdflib":
        import rdflib

        g = rdflib.Graph()
        g.parse(data=nt, format="nt")
        return g
    raise ValueError(f"unknown store kind: {kind}")


def _fmt_term(t) -> str:
    if t is None:
        return ""
    v = getattr(t, "value", None)  # pyoxigraph NamedNode/Literal/BlankNode
    return v if v is not None else str(t)  # rdflib terms are str subclasses


def execute_select(query: str, store, kind: str):
    """Run a SELECT/ASK; return (columns, rows) of strings."""
    if kind == "pyoxigraph":
        import pyoxigraph

        res = store.query(query)
        if isinstance(res, pyoxigraph.QueryBoolean):
            return ["result"], [[str(bool(res))]]
        cols = [str(v) for v in res.variables]
        rows = [[_fmt_term(sol[v]) for v in res.variables] for sol in res]
        return cols, rows
    # rdflib
    res = store.query(query)
    if res.type == "ASK":
        return ["result"], [[str(bool(res.askAnswer))]]
    cols = [str(v) for v in res.vars]
    rows = [[_fmt_term(r[v]) for v in res.vars] for r in res]
    return cols, rows


# ── core: relation & expression queries (omny's headline features) ──────────────
def relations_query(iri: str, relations) -> str:
    return omny.class_relations_query(f"<{iri}>", relations=list(relations),
                                      construct=False)


def run_relations(iri: str, relations, store, kind: str):
    """Build + run a class-relation query; return (sparql, columns, rows)."""
    q = relations_query(iri, relations)
    cols, rows = execute_select(q, store, kind)
    return q, cols, rows


_SCT_PREFIXED = re.compile(r"\b([A-Za-z][\w.-]*):(\d[\w.-]*)")


def _expand_numeric_prefixes(text: str, prefixes: dict) -> str:
    """Expand prefixed names with a numeric local part (e.g. ``sct:363698007``)
    to full IRIs — omny's Manchester lexer rejects those, but SNOMED uses them."""
    def sub(m):
        pfx, local = m.group(1), m.group(2)
        ns = prefixes.get(pfx)
        return f"<{ns}{local}>" if ns else m.group(0)
    return _SCT_PREFIXED.sub(sub, text)


_XMLNS_RE = re.compile(r'xmlns:([A-Za-z][\w.-]*)\s*=\s*"([^"]+)"')
_TTL_PREFIX_RE = re.compile(r'(?:@?[Pp]refix:?)\s+([A-Za-z][\w.-]*):\s*<([^>]+)>')


def extract_prefixes(text: str) -> dict:
    """Best-effort prefix map from an ontology document's declarations:
    RDF/XML ``xmlns:p="..."`` and Turtle/Manchester ``@prefix p: <...>`` /
    ``Prefix: p: <...>``. owlready2 does not surface these, so the explorer scans
    the source so users can type ``sulo:`` / ``mie:`` etc."""
    out = {}
    for m in _XMLNS_RE.finditer(text):
        out[m.group(1)] = m.group(2)
    for m in _TTL_PREFIX_RE.finditer(text):
        out[m.group(1)] = m.group(2)
    out.pop("xml", None)  # not a usable Manchester prefix
    return out


def expression_query(expr_text: str, onto, relations,
                     role_encoding: str = "structural", extra_prefixes=None) -> str:
    """Parse a Manchester expression and build a relation query.

    role_encoding="structural" matches OWL owl:Restriction bnodes; "flat" reads
    roles as direct ?concept <prop> <value> triples (SNOMED-style)."""
    if not (expr_text and expr_text.strip()):
        raise ValueError("Enter a class expression, e.g. `treats some Disease`.")
    pfx = prefixes_for(onto)
    pfx.update(extra_prefixes or {})
    pfx.setdefault("sct", "http://snomed.info/id/")
    construct = omny.parse_expression(_expand_numeric_prefixes(expr_text, pfx),
                                      onto, prefixes=pfx)
    return omny.class_relations_query(construct, relations=list(relations),
                                      construct=False, role_encoding=role_encoding)


def detect_role_encoding(store, kind: str) -> str:
    """Probe the store to choose how role/restriction expressions are matched.

    If the graph contains any ``owl:Restriction`` class axioms, the standard OWL
    serialization is in use -> "structural". Otherwise roles are stored as flat
    ``concept prop value`` triples (e.g. SNOMED CT) -> "flat"."""
    ask = ("PREFIX owl: <http://www.w3.org/2002/07/owl#> "
           "ASK { ?r a owl:Restriction }")
    _, rows = execute_select(ask, store, kind)
    has_restrictions = bool(rows) and str(rows[0][0]).strip().lower() == "true"
    return "structural" if has_restrictions else "flat"


def run_expression(expr_text: str, onto, relations, store, kind: str,
                   role_encoding: str = "structural", extra_prefixes=None):
    q = expression_query(expr_text, onto, relations, role_encoding, extra_prefixes)
    cols, rows = execute_select(q, store, kind)
    return q, cols, rows


# ── Streamlit UI ────────────────────────────────────────────────────────────────
def main():  # pragma: no cover - UI glue
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="omny Explorer", page_icon="🧩", layout="wide")
    st.title("🧩 omny Explorer")
    st.caption(f"Pure-Python Manchester + SPARQL, no Java — omny {omny.__version__}")

    ss = st.session_state
    ss.setdefault("world", None)
    ss.setdefault("onto", None)
    ss.setdefault("store", None)
    ss.setdefault("store_kind", "pyoxigraph")
    ss.setdefault("source_label", "")
    ss.setdefault("prefixes", {})

    _EXAMPLE = os.path.join(os.path.dirname(__file__), "data", "biomed.omn")

    # ── Sidebar: load + backend ──────────────────────────────────────────────
    with st.sidebar:
        st.header("1 · Load ontology")
        mode = st.radio("Source", ["Example", "Paste Manchester", "File path"])
        omn_text, path = None, None
        if mode == "Example":
            st.write(f"`{os.path.relpath(_EXAMPLE)}`")
            if os.path.exists(_EXAMPLE):
                with open(_EXAMPLE, encoding="utf-8") as f:
                    omn_text = f.read()
        elif mode == "Paste Manchester":
            omn_text = st.text_area("Manchester (.omn)", height=220,
                                    placeholder="Prefix: : <http://ex.org/>\nClass: Pizza")
        else:
            path = st.text_input("Path to .omn / .owl / .ttl / .rdf / .nt")

        kind = st.selectbox("SPARQL backend", ["pyoxigraph", "rdflib"])

        if st.button("Load", type="primary", width="stretch"):
            try:
                src_text = omn_text or ""
                if path:
                    world, onto = load_from_path(path)
                    label = path
                    if not src_text:
                        with open(path, encoding="utf-8", errors="ignore") as f:
                            src_text = f.read(65536)  # header holds the prefixes
                elif omn_text:
                    world, onto = load_from_text(omn_text)
                    label = mode
                else:
                    st.error("Nothing to load.")
                    st.stop()
                ss.world, ss.onto, ss.store_kind, ss.source_label = (
                    world, onto, kind, label)
                ss.prefixes = extract_prefixes(src_text)
                ss.store = build_store(world_to_nt(world), kind)
                st.success(f"Loaded {onto.base_iri}")
            except Exception as e:
                st.exception(e)

    if ss.onto is None:
        st.info("Load an ontology from the sidebar to begin.")
        st.stop()

    world, onto, store, kind = ss.world, ss.onto, ss.store, ss.store_kind
    pfx = prefixes_for(onto)
    ents = list_entities(onto)
    class_iris = {c["name"]: c["iri"] for c in ents["classes"]}

    cstats = " · ".join(f"{k}: {len(v)}" for k, v in ents.items())
    st.write(f"**{onto.base_iri}** — {cstats}  ·  backend: `{kind}`")

    tab_browse, tab_rel, tab_expr, tab_sparql = st.tabs(
        ["Browse", "Relations", "Expression", "SPARQL"])

    # ── Browse ───────────────────────────────────────────────────────────────
    with tab_browse:
        col1, col2 = st.columns([1, 2])
        with col1:
            group = st.selectbox("Entity type", list(ents.keys()))
            flt = st.text_input("Filter", placeholder="frac…")
            items = [e for e in ents[group]
                     if flt.lower() in e["name"].lower()] if flt else ents[group]
            names = [e["name"] for e in items]
            picked = st.selectbox(f"{len(items)} item(s)", names) if names else None
        with col2:
            if picked:
                iri = next(e["iri"] for e in items if e["name"] == picked)
                st.code(render_entity(world, iri, pfx), language="text")
                st.caption(iri)

    # ── Relations ────────────────────────────────────────────────────────────
    with tab_rel:
        c1, c2 = st.columns([1, 1])
        with c1:
            cls = st.selectbox("Class", list(class_iris.keys()),
                               key="rel_cls") if class_iris else None
        with c2:
            rels = st.multiselect("Relations", RELATION_CHOICES,
                                  default=["sub"], key="rel_kinds")
        if st.button("▶ Run relations", disabled=not (cls and rels)):
            sparql, cols, rows = run_relations(class_iris[cls], rels, store, kind)
            st.success(f"{len(rows)} result(s)")
            st.dataframe(pd.DataFrame(rows, columns=cols), width="stretch")
            with st.expander("Generated SPARQL"):
                st.code(sparql, language="sparql")

    # ── Expression ───────────────────────────────────────────────────────────
    with tab_expr:
        st.caption("Match an anonymous class expression. Mode **auto** probes the "
                   "graph: **structural** matches OWL `owl:Restriction` bnodes, "
                   "**flat-role** reads roles as direct `concept prop value` triples "
                   "(SNOMED-style). `sct:NNN` is expanded to a full IRI automatically.")
        expr = st.text_input(
            "Manchester expression",
            placeholder="sct:363698007 some owl:Thing   |   A and (treats some Disease)")
        c1, c2 = st.columns([1, 1])
        with c1:
            mode = st.selectbox("Match mode", ["auto", "structural", "flat-role"],
                                key="expr_mode",
                                help="auto probes the graph for owl:Restriction bnodes")
        with c2:
            rels = st.multiselect("Relations (structural only)", RELATION_CHOICES,
                                  default=["equiv"], key="expr_kinds")
        if mode == "auto":
            encoding = detect_role_encoding(store, kind)
            st.caption(f"Auto-detected encoding: **{encoding}** "
                       f"({'OWL owl:Restriction bnodes found' if encoding == 'structural' else 'no owl:Restriction bnodes — roles are flat triples'})")
        else:
            encoding = "flat" if mode == "flat-role" else "structural"
        extra = ss.get("prefixes", {})
        avail = sorted(set(extra) | {"", "sct", "rdfs", "owl", "xsd"})
        st.caption("Prefixes available: " + ", ".join(f"`{p or ':'}`" for p in avail))
        if st.button("▶ Match expression"):
            try:
                use_rels = rels or ["sub"]
                sparql, cols, rows = run_expression(expr, onto, use_rels, store,
                                                    kind, role_encoding=encoding,
                                                    extra_prefixes=extra)
                st.success(f"{len(rows)} match(es)")
                st.dataframe(pd.DataFrame(rows, columns=cols),
                             width="stretch")
                with st.expander("Generated SPARQL"):
                    st.code(sparql, language="sparql")
            except Exception as e:
                st.error(str(e))

    # ── SPARQL ───────────────────────────────────────────────────────────────
    with tab_sparql:
        default_q = (f"PREFIX owl: <{_OWL}>\n"
                     "SELECT ?c WHERE { ?c a owl:Class } LIMIT 100")
        q = st.text_area("SPARQL SELECT / ASK", value=default_q, height=160)
        if st.button("▶ Run SPARQL", disabled=not q.strip()):
            try:
                cols, rows = execute_select(q, store, kind)
                st.success(f"{len(rows)} row(s)")
                st.dataframe(pd.DataFrame(rows, columns=cols),
                             width="stretch")
            except Exception as e:
                st.exception(e)


if __name__ == "__main__":
    main()
