"""In-process tests for pymos.jupyter magics.

Uses IPython.testing.globalipapp to obtain a real (singleton) InteractiveShell,
loads the extension, and exercises each magic. No notebook server is needed.
"""
import shutil

import IPython
import pytest
from IPython.testing.globalipapp import get_ipython as _bootstrap_ipython


_HAS_JAVA = shutil.which("java") is not None


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


@pytest.mark.skipif(not _HAS_JAVA, reason="HermiT needs Java on PATH")
def test_reason_materializes_inferred_subclass():
    ip = _ip()
    # Margherita ≡ Pizza ⊓ (hasTopping some Cheese) — HermiT should infer
    # Margherita ⊑ Pizza (without it being asserted as a SubClassOf).
    ip.run_cell_magic("mos", "", (
        "ObjectProperty: hasTopping\n"
        "Class: Pizza\n"
        "Class: Cheese\n"
        "Class: Margherita\n"
        "    EquivalentTo: Pizza and (hasTopping some Cheese)\n"
    ))
    ip.run_line_magic("reason", "")
    onto = ip.user_ns["mos_onto"]
    pizza = onto.world["http://pymos.test/notebook#Pizza"]
    margherita = onto.world["http://pymos.test/notebook#Margherita"]
    # After reasoning, Margherita's transitive parents include Pizza.
    parents = set(margherita.ancestors())
    assert pizza in parents, (
        f"expected Pizza in Margherita.ancestors() after %reason, got {parents}"
    )


def test_mos_query_equiv_finds_named_class(capsys):
    ip = _ip()
    ip.run_cell_magic("mos", "", (
        "ObjectProperty: hasTopping\n"
        "Class: Pizza\n"
        "Class: Cheese\n"
        "Class: Margherita\n"
        "    EquivalentTo: Pizza and (hasTopping some Cheese)\n"
    ))
    ip.run_cell_magic("mos_query", "equiv", "Pizza and (hasTopping some Cheese)")
    out = capsys.readouterr().out
    assert "http://pymos.test/notebook#Margherita" in out


def test_mos_show_renders_one_class(capsys):
    ip = _ip()
    ip.run_cell_magic("mos", "", (
        "ObjectProperty: hasTopping\n"
        "Class: Pizza\n"
        "Class: Cheese\n"
        "Class: Margherita\n"
        "    SubClassOf: Pizza\n"
        "    EquivalentTo: Pizza and (hasTopping some Cheese)\n"
    ))
    ip.run_line_magic("mos_show", "Margherita")
    out = capsys.readouterr().out
    assert "Class:" in out
    assert "Margherita" in out
    assert "SubClassOf" in out
    assert "EquivalentTo" in out


def test_mos_show_unknown_lists_known(capsys):
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza\nClass: Cheese")
    ip.run_line_magic("mos_show", "Banana")
    out = capsys.readouterr().out
    assert "Banana" in out
    assert "Pizza" in out  # listed in suggestions
    assert "Cheese" in out


def test_mos_save_writes_file(tmp_path):
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza\nClass: Cheese")
    target = tmp_path / "out.omn"
    ip.run_line_magic("mos_save", str(target))
    text = target.read_text()
    assert "Class:" in text
    # Round-trip: parsing the saved file recovers the classes.
    import pymos
    onto2 = pymos.parse(text)
    names = {c.name for c in onto2.classes()}
    assert {"Pizza", "Cheese"} <= names


def test_completer_offers_frame_keywords_at_line_start():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza")
    # The completer is exported as `_mos_complete(cell_text, line, cursor_col)`
    # for testability — IPython invokes it through set_custom_completer.
    from pymos.jupyter import _mos_complete
    cands = _mos_complete(cell_text="%%mos\nC", line="C", cursor_col=1)
    assert "Class:" in cands


def test_completer_offers_known_class_after_subclassof():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza\nClass: Cheese")
    from pymos.jupyter import _mos_complete
    cell = "%%mos\nClass: Margherita\n    SubClassOf: P"
    line = "    SubClassOf: P"
    cands = _mos_complete(cell_text=cell, line=line, cursor_col=len(line))
    assert "Pizza" in cands


def test_completer_offers_restriction_operators_after_property():
    ip = _ip()
    ip.run_cell_magic("mos", "",
                     "ObjectProperty: hasTopping\nClass: Pizza\nClass: Cheese")
    from pymos.jupyter import _mos_complete
    cell = "%%mos_query equiv\nPizza and (hasTopping s"
    line = "Pizza and (hasTopping s"
    cands = _mos_complete(cell_text=cell, line=line, cursor_col=len(line))
    assert "some" in cands


def test_completer_returns_none_outside_mos_cells():
    ip = _ip()
    from pymos.jupyter import _mos_complete
    # No %%mos magic on the first line → completer should yield None
    # so the default Python completer runs instead.
    cands = _mos_complete(cell_text="x = 1\nCl", line="Cl", cursor_col=2)
    assert cands is None
