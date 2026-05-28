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


def load_ipython_extension(ip) -> None:
    """Called by IPython when ``%load_ext pymos.jupyter`` runs."""
    ip.register_magic_function(_mos_magic, magic_kind="cell", magic_name="mos")
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
