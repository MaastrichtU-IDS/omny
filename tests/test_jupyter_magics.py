"""In-process tests for pymos.jupyter magics.

Uses IPython.testing.globalipapp to obtain a real (singleton) InteractiveShell,
loads the extension, and exercises each magic. No notebook server is needed.
"""
import IPython
from IPython.testing.globalipapp import get_ipython as _bootstrap_ipython


def _ip():
    """Fresh-ish IPython shell with the extension loaded; resets pymos state.

    ``globalipapp.get_ipython()`` is a one-shot installer: it returns the
    singleton on the first call only. Subsequent calls return ``None`` and the
    same singleton must be retrieved via ``IPython.get_ipython()`` — which the
    installer registered globally during its first invocation.
    """
    ip = _bootstrap_ipython() or IPython.get_ipython()
    if "pymos.jupyter" in ip.extension_manager.loaded:
        ip.extension_manager.reload_extension("pymos.jupyter")
    else:
        ip.extension_manager.load_extension("pymos.jupyter")
    # The extension exposes a reset hook via the user_ns "mos_reset" callable.
    ip.user_ns["mos_reset"]()
    return ip


def test_mos_cell_adds_classes():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza\nClass: Margherita\n    SubClassOf: Pizza")
    onto = ip.user_ns["mos_onto"]
    names = {c.name for c in onto.classes()}
    assert "Pizza" in names
    assert "Margherita" in names


def test_mos_cell_merges_incrementally():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza")
    ip.run_cell_magic("mos", "", "Class: Cheese")
    onto = ip.user_ns["mos_onto"]
    names = {c.name for c in onto.classes()}
    assert {"Pizza", "Cheese"} <= names
