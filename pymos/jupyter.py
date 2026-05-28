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

    Use ``%reason pellet`` to invoke Pellet instead (owlready2 also ships
    ``sync_reasoner_pellet``).
    """
    if not list(_state.onto.classes()):
        print("no ontology axioms yet — start with a %%mos cell")
        return
    arg = (line or "").strip().lower()
    runner = owlready2.sync_reasoner_pellet if arg == "pellet" else owlready2.sync_reasoner
    with _state.onto:
        runner(_state.world)


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


def _reset_for_user_ns(ip):
    """Return a closure that resets state AND updates the user_ns bindings."""

    def _reset() -> None:
        _state.reset()
        ip.user_ns["mos_onto"] = _state.onto
        ip.user_ns["mos_world"] = _state.world

    return _reset
