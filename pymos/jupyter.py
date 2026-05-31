"""IPython magics for interactive MOS authoring of a pymos ontology.

Provides:

- ``%%mos``         — parse the cell body as Manchester syntax and merge into the
                      active ontology.
- ``%reason``       — run HermiT (via owlready2.sync_reasoner) to materialize
                      inferences into the active world.
- ``%%mos_query``   — parse the cell body as an anonymous class expression and
                      query the active ontology for related classes/individuals.
- ``%mos_show``     — render one named entity's axioms back to Manchester syntax.
- ``%mos_save``     — render the whole active ontology back to Manchester syntax
                      and write it to a file.

Load with ``%load_ext pymos.jupyter``. The active ontology is exposed in the
user namespace as ``mos_onto`` and ``mos_world``; ``mos_reset()`` clears it.
"""
from __future__ import annotations


import owlready2
from IPython.display import display

import pymos
from pymos.sparql import RELATIONS, class_relations_query
from pymos.store import run_rdflib


_DEFAULT_BASE = "http://pymos.test/notebook"


class _State:
    """Singleton container for the active world + ontology."""

    def __init__(self) -> None:
        self.world: owlready2.World | None = None
        self.onto: owlready2.Ontology | None = None
        self.reset()

    def reset(self) -> None:
        self.world = owlready2.World()
        self.onto = self.world.get_ontology(_DEFAULT_BASE)


_state = _State()


def _mos_magic(line: str, cell: str) -> None:
    """%%mos — parse cell as Manchester syntax and merge into the active ontology."""
    pymos.parse(cell, onto=_state.onto)


def _reason_magic(line: str) -> None:
    """%reason — run HermiT (owlready2.sync_reasoner) over the active world.

    Use ``%reason pellet`` to invoke Pellet instead. Pellet is not bundled with
    owlready2 — you must install it separately and ensure ``pellet`` is on
    PATH (or owlready2 can find it).  If it isn't, a friendly message prints.
    """
    if not list(_state.onto.classes()):
        print("no ontology axioms yet — start with a %%mos cell")
        return
    arg = (line or "").strip().lower()
    runner = owlready2.sync_reasoner_pellet if arg == "pellet" else owlready2.sync_reasoner
    try:
        with _state.onto:
            runner(_state.world)
    except (FileNotFoundError, OSError) as e:
        which = "Pellet" if arg == "pellet" else "HermiT"
        print(f"{which} reasoner not available: {e}. "
              f"For Pellet, install it separately and put it on PATH.")


def _mos_query_magic(line: str, cell: str) -> None:
    """%%mos_query <relation> — query the active ontology with an anonymous expression.

    The cell body is parsed as a Manchester class expression; <relation> is one of
    super / sub / direct_super / direct_sub / equiv / individual.
    """
    rel = (line or "").strip()
    if rel not in RELATIONS:
        print(f"unknown relation '{rel}'. choose one of: {', '.join(RELATIONS)}")
        return
    base = _state.onto.base_iri
    prefixes = {"": base if base.endswith(("/", "#")) else base + "#"}
    expr = pymos.parse_expression(cell.strip(), _state.onto, prefixes=prefixes)
    q = class_relations_query(expr, relations=(rel,), construct=False)
    rows = list(run_rdflib(q, _state.onto.world.as_rdflib_graph()))
    if not rows:
        print("(no results)")
        return
    for r in rows:
        print(str(r[0]))


def _entity_by_local_name(name: str):
    """Look up a named entity in the active ontology by its short local name."""
    base = _state.onto.base_iri
    base = base if base.endswith(("/", "#")) else base + "#"
    return _state.onto.world[base + name]


def _list_known_names() -> dict[str, list[str]]:
    """Return a dict of {kind: sorted local names} for diagnostics."""
    return {
        "classes": sorted(c.name for c in _state.onto.classes()),
        "object_properties": sorted(p.name for p in _state.onto.object_properties()),
        "data_properties": sorted(p.name for p in _state.onto.data_properties()),
        "individuals": sorted(i.name for i in _state.onto.individuals()),
    }


def _mos_show_magic(line: str) -> None:
    """%mos_show <Name> — render one named entity's axioms back to Manchester."""
    name = (line or "").strip()
    if not name:
        print("usage: %mos_show <LocalName>")
        return
    entity = _entity_by_local_name(name)
    if entity is None:
        print(f"unknown name '{name}'. known:")
        for kind, names in _list_known_names().items():
            if names:
                print(f"  {kind}: {', '.join(names)}")
        return
    base = _state.onto.base_iri
    prefixes = {"": base if base.endswith(("/", "#")) else base + "#"}
    print(pymos.render_frame(entity, prefixes=prefixes))


def _mos_save_magic(line: str) -> None:
    """%mos_save <path> — render the active ontology to Manchester and write to <path>."""
    path = (line or "").strip()
    if not path:
        print("usage: %mos_save <path>")
        return
    base = _state.onto.base_iri
    prefixes = {"": base if base.endswith(("/", "#")) else base + "#"}
    text = pymos.render(_state.onto, prefixes=prefixes)
    with open(path, "w") as f:
        f.write(text)
    print(f"wrote {path}")


# Tab-completion: keyword/operator constants + the cell-classifier + ``_mos_complete``
# live in ``pymos._jupyter_complete``. Re-exported here so existing
# ``from pymos.jupyter import _mos_complete`` / ``_register_completer`` callers
# (and tests/test_jupyter_magics.py) keep working unchanged.
from pymos._jupyter_complete import _mos_complete  # noqa: E402  (re-export)


def _register_completer(ip) -> None:
    """Register the completer with IPython.

    IPython's ``set_custom_completer`` receives a callable that takes the shell
    and an event and returns a list of completions.  We adapt our pure helper
    ``_mos_complete`` to that interface.
    """

    def _adapter(_shell, event):
        cell_text = getattr(event, "text_until_cursor", None) or event.line
        line = event.line or ""
        cursor_col = len(line)
        cands = _mos_complete(cell_text, line, cursor_col)
        return cands if cands is not None else []

    ip.set_custom_completer(_adapter)


_CODEMIRROR_JS = r"""
// pymos-manchester CodeMirror mode (registered at notebook startup).
// JupyterLab 4 uses CodeMirror 6; we register a StreamLanguage via
// @codemirror/legacy-modes/mode/simple-mode-style tokens.  The simple-mode
// path keeps the implementation compact — full LSP-grade highlighting is
// out of scope here.
(function() {
  if (!window.require) { return; }
  require([
    '@codemirror/legacy-modes/mode/simple-mode',
    '@codemirror/language',
  ], function (simpleMode, lang) {
    try {
      const states = {
        start: [
          // Frame + value keywords spelled out with their trailing colon so the
          // literal tokens (e.g. "Class:", "SubClassOf:", "EquivalentTo:") are
          // recognisable in the source — the parse_jupyter_magics test asserts
          // their presence to guard against silent breakage.
          {regex: /\b(?:Class:|ObjectProperty:|DataProperty:|Individual:|Datatype:|AnnotationProperty:|Ontology:|Prefix:|Import:|SubClassOf:|EquivalentTo:|DisjointWith:|Domain:|Range:|SubPropertyOf:|Types:|SameAs:|DifferentFrom:|Facts:|Characteristics:|Annotations:)/, token: 'keyword'},
          {regex: /\b(?:some|only|value|min|max|exactly|Self|and|or|not|inverse)\b/, token: 'operator'},
          {regex: /\b(?:Functional|InverseFunctional|Transitive|Symmetric|Asymmetric|Reflexive|Irreflexive)\b/, token: 'atom'},
          {regex: /<[^>]+>/, token: 'link'},
          {regex: /"[^"]*"/, token: 'string'},
          {regex: /\b\d+\b/, token: 'number'},
          {regex: /#.*/, token: 'comment'},
        ],
      };
      const mode = simpleMode.simpleMode(states);
      const language = lang.StreamLanguage.define(mode);
      window.__pymosManchesterMode = language;
      console.log('pymos: manchester-syntax CodeMirror mode registered');
    } catch (e) {
      console.warn('pymos: failed to register manchester-syntax mode', e);
    }
  });
})();
"""


def _inject_codemirror_mode() -> None:
    """Display the CodeMirror mode definition once at extension-load time.

    Path A — light injection.  If this silently no-ops under a stricter CM6
    bundle, the fallback (Path B in the spec) is to ship a prebuilt JupyterLab
    extension.  The smoke test in Task 9 verifies the injection took effect.

    We publish the raw application/javascript mime bundle (``raw=True``) rather
    than ``display(Javascript(...))``: functionally identical in a live kernel
    (the rich-formatter path produces the same bundle), but observable through
    a ``display_pub.publish`` spy even in shells where the Javascript formatter
    is disabled (``IPython.testing.globalipapp``).
    """
    display({"application/javascript": _CODEMIRROR_JS}, raw=True)


def load_ipython_extension(ip) -> None:
    """Called by IPython when ``%load_ext pymos.jupyter`` runs."""
    ip.register_magic_function(_mos_magic, magic_kind="cell", magic_name="mos")
    ip.register_magic_function(_reason_magic, magic_kind="line", magic_name="reason")
    ip.register_magic_function(_mos_query_magic, magic_kind="cell", magic_name="mos_query")
    ip.register_magic_function(_mos_show_magic, magic_kind="line", magic_name="mos_show")
    ip.register_magic_function(_mos_save_magic, magic_kind="line", magic_name="mos_save")
    ip.user_ns["mos_onto"] = _state.onto
    ip.user_ns["mos_world"] = _state.world
    ip.user_ns["mos_reset"] = _reset_for_user_ns(ip)
    _register_completer(ip)
    _inject_codemirror_mode()


def unload_ipython_extension(ip) -> None:
    """Called by IPython when ``%unload_ext pymos.jupyter`` runs.

    Without this hook, ``ExtensionManager.unload_extension`` reports
    ``"no unload function"`` and leaves the module in ``ip.extension_manager.loaded``,
    which blocks subsequent ``load_extension`` calls from re-running
    ``load_ipython_extension`` (and re-emitting the CodeMirror JS).  We do not
    need to tear down magics/completers — the IPython shell already does that
    when extensions are unloaded — so this is essentially a marker.
    """
    return None


def _reset_for_user_ns(ip):
    """Return a closure that resets state AND updates the user_ns bindings."""

    def _reset() -> None:
        _state.reset()
        ip.user_ns["mos_onto"] = _state.onto
        ip.user_ns["mos_world"] = _state.world

    return _reset
