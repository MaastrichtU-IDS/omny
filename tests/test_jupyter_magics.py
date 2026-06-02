"""In-process tests for omny.jupyter magics.

Uses IPython.testing.globalipapp to obtain a real (singleton) InteractiveShell,
loads the extension, and exercises each magic. No notebook server is needed.
"""
import shutil

import IPython
import pytest
from IPython.testing.globalipapp import get_ipython as _bootstrap_ipython


_HAS_JAVA = shutil.which("java") is not None


def _ip():
    """Fresh-ish IPython shell with the extension loaded; resets omny state.

    ``globalipapp.get_ipython()`` is a one-shot installer: it returns the
    singleton on the first call only. Subsequent calls return ``None`` and the
    same singleton must be retrieved via ``IPython.get_ipython()`` — which the
    installer registered globally during its first invocation.
    """
    ip = _bootstrap_ipython() or IPython.get_ipython()
    if "omny.jupyter" in ip.extension_manager.loaded:
        ip.extension_manager.reload_extension("omny.jupyter")
    else:
        ip.extension_manager.load_extension("omny.jupyter")
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
    pizza = onto.world["http://omny.test/notebook#Pizza"]
    margherita = onto.world["http://omny.test/notebook#Margherita"]
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
    assert "http://omny.test/notebook#Margherita" in out


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
    import omny
    onto2 = omny.parse(text)
    names = {c.name for c in onto2.classes()}
    assert {"Pizza", "Cheese"} <= names


def test_completer_offers_frame_keywords_at_line_start():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza")
    # The completer is exported as `_mos_complete(cell_text, line, cursor_col)`
    # for testability — IPython invokes it through set_custom_completer.
    from omny.jupyter import _mos_complete
    cands = _mos_complete(cell_text="%%mos\nC", line="C", cursor_col=1)
    assert "Class:" in cands


def test_completer_offers_known_class_after_subclassof():
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza\nClass: Cheese")
    from omny.jupyter import _mos_complete
    cell = "%%mos\nClass: Margherita\n    SubClassOf: P"
    line = "    SubClassOf: P"
    cands = _mos_complete(cell_text=cell, line=line, cursor_col=len(line))
    assert "Pizza" in cands


def test_completer_offers_restriction_operators_after_property():
    ip = _ip()
    ip.run_cell_magic("mos", "",
                     "ObjectProperty: hasTopping\nClass: Pizza\nClass: Cheese")
    from omny.jupyter import _mos_complete
    cell = "%%mos_query equiv\nPizza and (hasTopping s"
    line = "Pizza and (hasTopping s"
    cands = _mos_complete(cell_text=cell, line=line, cursor_col=len(line))
    assert "some" in cands


def test_completer_returns_none_outside_mos_cells():
    _ip()  # load extension + reset state (return value unused)
    from omny.jupyter import _mos_complete
    # No %%mos magic on the first line → completer should yield None
    # so the default Python completer runs instead.
    cands = _mos_complete(cell_text="x = 1\nCl", line="Cl", cursor_col=2)
    assert cands is None


def test_reason_with_no_axioms_prints_friendly_message(capsys):
    ip = _ip()
    # No %%mos cell — ontology is empty.
    ip.run_line_magic("reason", "")
    out = capsys.readouterr().out
    assert "no ontology axioms" in out.lower()


def test_mos_query_unknown_relation_lists_valid(capsys):
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza")
    ip.run_cell_magic("mos_query", "bogus_relation", "Pizza")
    out = capsys.readouterr().out
    assert "bogus_relation" in out
    assert "super" in out  # one of the valid relations listed
    assert "sub" in out
    assert "equiv" in out


def test_register_completer_adapter_forwards_to_mos_complete():
    """Verify the IPython adapter glue translates event objects correctly."""
    from types import SimpleNamespace
    from omny.jupyter import _register_completer
    # Reset state then add a class so dynamic candidates are non-empty.
    ip = _ip()
    ip.run_cell_magic("mos", "", "Class: Pizza")
    # Capture the adapter callable via set_custom_completer.
    captured_adapter = []
    orig = ip.set_custom_completer

    def _capture(fn, *args, **kwargs):
        captured_adapter.append(fn)
        return orig(fn, *args, **kwargs)

    ip.set_custom_completer = _capture
    try:
        _register_completer(ip)
    finally:
        ip.set_custom_completer = orig
    assert captured_adapter, "_register_completer should call set_custom_completer"
    adapter = captured_adapter[-1]
    event = SimpleNamespace(
        text_until_cursor="%%mos\nClass: Margherita\n    SubClassOf: P",
        line="    SubClassOf: P",
        symbol="P",
    )
    result = adapter(ip, event)
    assert "Pizza" in result, f"expected Pizza in adapter result, got {result}"


def test_load_extension_emits_codemirror_js(capsys):
    """The injected JS payload must mention the Manchester keywords; if it doesn't,
    highlighting is silently lost. Behavioral check happens in the docker smoke test.
    """
    ip = _bootstrap_ipython() or IPython.get_ipython()
    if "omny.jupyter" in ip.extension_manager.loaded:
        ip.extension_manager.unload_extension("omny.jupyter")
    captured = []
    orig_publish = ip.display_pub.publish

    def _spy(data, metadata=None, **kwargs):
        captured.append(data)
        return orig_publish(data, metadata=metadata, **kwargs)

    ip.display_pub.publish = _spy
    try:
        ip.extension_manager.load_extension("omny.jupyter")
    finally:
        ip.display_pub.publish = orig_publish
    js_blobs = [
        d.get("application/javascript") or d.get("text/javascript")
        for d in captured if d
    ]
    js_blobs = [b for b in js_blobs if b]
    assert js_blobs, "expected at least one Javascript display blob"
    combined = "\n".join(js_blobs)
    for kw in ("Class:", "SubClassOf:", "EquivalentTo:", "some", "only", "manchester"):
        assert kw in combined, f"missing {kw!r} in injected JS"
