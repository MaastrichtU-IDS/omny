# Interactive MOS Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Jupyter notebook where the user writes MOS in cell magics to incrementally build an ontology, reason over it with HermiT, and query it via SPARQL — with syntax highlighting and Tab autocomplete inside MOS cells.

**Architecture:** A new `pymos/jupyter.py` registers five IPython magics (`%%mos`, `%reason`, `%%mos_query`, `%mos_show`, `%mos_save`) that share a module-level singleton World/Ontology. At extension-load time the module also registers a context-aware custom completer and injects a CodeMirror language definition for Manchester syntax. Reasoning shells out to HermiT via `owlready2.sync_reasoner`; querying reuses `class_relations_query` + `run_rdflib`; rendering reuses `pymos.render` and `pymos.render_frame`. The existing `examples/` docker-compose stack hosts the deliverable notebook; the Dockerfile gains `default-jre-headless` for Java.

**Tech Stack:** Python 3.12, IPython (cell magics + custom completer), owlready2 (ontology model + HermiT shell-out), pymos (parse + render + sparql), JupyterLab 4 (CodeMirror 6), pytest with `IPython.testing.globalipapp`. No new package dependencies beyond `ipython`.

---

## File Structure

```
pymos/
└── jupyter.py                            # NEW — magics, completer, codemirror injection

tests/
└── test_jupyter_magics.py                # NEW — drive magics + completer in-process

examples/
├── Dockerfile                            # MODIFY — add default-jre-headless + ipython
└── notebooks/
    ├── 05_interactive_mos.py             # NEW — jupytext source
    └── 05_interactive_mos.ipynb          # NEW — generated, executed deliverable

pyproject.toml                            # MODIFY — add ipython to [project.optional-dependencies] dev

README.md                                 # MODIFY — point at the notebook + launch steps
```

Responsibilities:
- `pymos/jupyter.py` — owns the singleton `_state` (World + Ontology), the five magic functions, the completer, and the highlighting injector. Knows nothing about the existing query/render internals beyond their public entry points (`pymos.parse`, `pymos.parse_expression`, `class_relations_query`, `run_rdflib`, `pymos.render`, `pymos.render_frame`).
- Tests live in `tests/test_jupyter_magics.py` and run via `python -m pytest`. Java-dependent reasoning tests are skipped when Java is missing.

All commands below run from `/data/dumontier/pymos-mos-notebook` (the worktree on branch `feat/mos-notebook`). Activate the venv first: `source ../pymos/.venv/bin/activate` (the venv is shared from the primary worktree). If `python -c "import IPython"` fails after Task 1, re-source the venv (Task 1 installs IPython into it).

---

### Task 1: Dependencies + Dockerfile

Add IPython to the dev extras so tests can run locally; add `default-jre-headless` to the examples Docker image so HermiT can launch.

**Files:**
- Modify: `pyproject.toml`
- Modify: `examples/Dockerfile`

- [ ] **Step 1: Add IPython to dev extras**

Read `pyproject.toml`. Locate the `[project.optional-dependencies]` block. The `dev` extra currently reads:

```toml
dev = ["pytest>=8.0", "pyoxigraph>=0.4", "rdflib>=7.0", "ruff>=0.6"]
```

Replace that single line with:

```toml
dev = ["pytest>=8.0", "pyoxigraph>=0.4", "rdflib>=7.0", "ruff>=0.6", "ipython>=8.0"]
```

- [ ] **Step 2: Install the updated extras into the venv**

```bash
source ../pymos/.venv/bin/activate
pip install -e ".[dev]" -q
python -c "import IPython; print(IPython.__version__)"
```
Expected: prints a version like `8.x`. If pip fails through the proxy, re-source the venv first (env vars).

- [ ] **Step 3: Add Java to examples/Dockerfile**

Open `examples/Dockerfile`. The first `RUN apt-get install` line reads:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
```

Add `default-jre-headless` to the install list:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential default-jre-headless \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 4: Build the updated image and verify Java is present**

```bash
docker build -t pymos-notebook -f examples/Dockerfile examples/
docker run --rm pymos-notebook bash -lc "java -version 2>&1 | head -1"
```
Expected: prints a Java version (`openjdk version "17..."` or similar).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml examples/Dockerfile
git commit -m "feat(deps): IPython dev extra + Java in examples image for HermiT"
```

---

### Task 2: Module scaffold + `%%mos` cell magic

Create `pymos/jupyter.py` with the singleton state, the extension-load entry point, and the first magic. TDD via `IPython.testing.globalipapp`.

**Files:**
- Create: `pymos/jupyter.py`
- Create: `tests/test_jupyter_magics.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_jupyter_magics.py`:

```python
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
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: `ModuleNotFoundError: No module named 'pymos.jupyter'` or extension load error.

- [ ] **Step 3: Create `pymos/jupyter.py`**

Create the file with this content:

```python
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
        self.onto = self.world.get_ontology(_DEFAULT_BASE).load() if False else \
            self.world.get_ontology(_DEFAULT_BASE)
        # Set a base_iri so parse_expression resolves bare names correctly.
        # owlready2's get_ontology already sets base_iri; nothing else needed.


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
```

- [ ] **Step 4: Run the test, verify it passes**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): module scaffold + %%mos cell magic with incremental merge"
```

---

### Task 3: `%reason` magic (HermiT)

Add a line magic that runs `owlready2.sync_reasoner` on the active world. Tests are skipped when Java is unavailable.

**Files:**
- Modify: `pymos/jupyter.py`
- Modify: `tests/test_jupyter_magics.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_jupyter_magics.py`:

```python
import shutil

import pytest


_HAS_JAVA = shutil.which("java") is not None


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
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
python -m pytest tests/test_jupyter_magics.py::test_reason_materializes_inferred_subclass -v
```
Expected: FAIL — `%reason` magic isn't registered yet. (If Java isn't on the host, the test is skipped — Step 3 still proceeds; the smoke test in Task 9 covers the in-container path.)

- [ ] **Step 3: Implement `%reason`**

Edit `pymos/jupyter.py`. After the `_mos_magic` function, add:

```python
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
```

Then add a registration line inside `load_ipython_extension`, immediately after the existing `register_magic_function(...mos...)` call:

```python
    ip.register_magic_function(_reason_magic, magic_kind="line", magic_name="reason")
```

- [ ] **Step 4: Run the test**

If Java is on PATH:
```bash
python -m pytest tests/test_jupyter_magics.py::test_reason_materializes_inferred_subclass -v
```
Expected: PASS.

If Java is not on PATH (the test will skip — that's expected). The docker-compose smoke test in Task 9 exercises this end-to-end inside the image where Java IS installed.

Either outcome (PASS or SKIPPED) is acceptable; do not mark the test xfail.

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): %reason runs HermiT (or Pellet) on the active world"
```

---

### Task 4: `%%mos_query` magic

Parse the cell as an anonymous class expression, build a `class_relations_query`, run via `run_rdflib`, print IRIs.

**Files:**
- Modify: `pymos/jupyter.py`
- Modify: `tests/test_jupyter_magics.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_jupyter_magics.py`:

```python
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
```

- [ ] **Step 2: Run, verify fail**

```bash
python -m pytest tests/test_jupyter_magics.py::test_mos_query_equiv_finds_named_class -v
```
Expected: FAIL — magic not registered.

- [ ] **Step 3: Implement `%%mos_query`**

Add to `pymos/jupyter.py`, after `_reason_magic`:

```python
from pymos.sparql import RELATIONS, class_relations_query
from pymos.store import run_rdflib


def _mos_query_magic(line: str, cell: str) -> None:
    """%%mos_query <relation> — query the active ontology with an anonymous expression.

    The cell body is parsed as a Manchester class expression; <relation> is one of
    super / sub / direct_super / direct_sub / equiv / individual.
    """
    rel = (line or "").strip()
    if rel not in RELATIONS:
        print(f"unknown relation '{rel}'. choose one of: {', '.join(RELATIONS)}")
        return
    # Use the ontology's base_iri as the empty prefix so bare names resolve.
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
```

Register it inside `load_ipython_extension`:

```python
    ip.register_magic_function(_mos_query_magic, magic_kind="cell", magic_name="mos_query")
```

- [ ] **Step 4: Run, verify pass**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 4 passed (or 3 passed + 1 skipped if no Java).

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): %%mos_query runs SPARQL with an anonymous MOS target"
```

---

### Task 5: `%mos_show` and `%mos_save` magics

Two render-based magics. `%mos_show <Name>` prints one entity's axioms via `pymos.render_frame`; `%mos_save <path>` writes the whole ontology via `pymos.render`.

**Files:**
- Modify: `pymos/jupyter.py`
- Modify: `tests/test_jupyter_magics.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
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
    onto2 = pymos.parse(text)
    names = {c.name for c in onto2.classes()}
    assert {"Pizza", "Cheese"} <= names
```

- [ ] **Step 2: Run, verify 3 new fails**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 3 new fails for the show/save tests.

- [ ] **Step 3: Implement the two magics**

Add to `pymos/jupyter.py`, after `_mos_query_magic`:

```python
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
```

Register both in `load_ipython_extension`:

```python
    ip.register_magic_function(_mos_show_magic, magic_kind="line", magic_name="mos_show")
    ip.register_magic_function(_mos_save_magic, magic_kind="line", magic_name="mos_save")
```

- [ ] **Step 4: Run all tests, verify pass**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 6 (or 5 + 1 skipped) passed.

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): %mos_show renders one frame; %mos_save round-trips the ontology"
```

---

### Task 6: Custom completer (Tab autocomplete)

Register a custom completer that fires on Tab. It gates itself to `%%mos` and `%%mos_query` cells and returns context-aware candidates from a static keyword set plus the dynamic content of `_state.onto`.

**Files:**
- Modify: `pymos/jupyter.py`
- Modify: `tests/test_jupyter_magics.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
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
```

- [ ] **Step 2: Run, verify 4 new fails**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 4 new fails (`ImportError: cannot import name '_mos_complete'`).

- [ ] **Step 3: Implement the completer**

Add to `pymos/jupyter.py`, after the existing magic functions:

```python
import re


_FRAME_KEYWORDS = [
    "Class:", "ObjectProperty:", "DataProperty:", "Individual:",
    "Datatype:", "AnnotationProperty:", "Ontology:", "Prefix:", "Import:",
]
_VALUE_KEYWORDS = {
    "SubClassOf:", "EquivalentTo:", "DisjointWith:",
    "Domain:", "Range:", "SubPropertyOf:",
    "Types:", "SameAs:", "DifferentFrom:", "Facts:",
    "Characteristics:",
}
_RESTRICTION_OPS = ["some", "only", "value", "min", "max", "exactly", "Self"]
_BOOL_OPS = ["and", "or", "not", "inverse"]
_CHAR_KEYWORDS = [
    "Functional", "InverseFunctional", "Transitive",
    "Symmetric", "Asymmetric", "Reflexive", "Irreflexive",
]


def _last_value_keyword(cell_text: str, up_to_line_index: int) -> str | None:
    """Return the most recent value-keyword (e.g. SubClassOf:) within the current frame."""
    lines = cell_text.splitlines()[:up_to_line_index + 1]
    for raw in reversed(lines):
        s = raw.strip()
        # Stop scanning at a frame boundary.
        if any(s.startswith(k) for k in _FRAME_KEYWORDS):
            # The same line may contain BOTH a frame keyword AND a value keyword
            # (rare in practice) — but treat the frame boundary as stopping the scan.
            break
        for k in _VALUE_KEYWORDS:
            if s.startswith(k):
                return k
    return None


def _last_frame_keyword(cell_text: str, up_to_line_index: int) -> str | None:
    """Return the most recent frame-keyword (Class:, ObjectProperty:, …)."""
    lines = cell_text.splitlines()[:up_to_line_index + 1]
    for raw in reversed(lines):
        s = raw.strip()
        for k in _FRAME_KEYWORDS:
            if s.startswith(k):
                return k
    return None


def _is_mos_cell(cell_text: str) -> bool:
    """True iff the cell's first line is a %%mos or %%mos_query magic."""
    first = (cell_text.splitlines() + [""])[0].strip()
    return first.startswith("%%mos") or first.startswith("%%mos_query")


def _candidate_pool(context: str) -> list[str]:
    """Return raw candidates appropriate for the given context label."""
    if context == "line_start":
        return list(_FRAME_KEYWORDS)
    if context == "class":
        return [c.name for c in _state.onto.classes()] + _BOOL_OPS + ["("]
    if context == "object_property_or_class":
        return ([c.name for c in _state.onto.classes()]
                + [p.name for p in _state.onto.object_properties()]
                + _BOOL_OPS + _RESTRICTION_OPS)
    if context == "individual":
        return [i.name for i in _state.onto.individuals()]
    if context == "characteristic":
        return list(_CHAR_KEYWORDS)
    if context == "restriction_op":
        return list(_RESTRICTION_OPS)
    return []


def _classify_context(cell_text: str, line: str, cursor_col: int) -> str:
    """Decide which candidate pool applies at the cursor."""
    lines = cell_text.splitlines()
    line_idx = max(0, len(lines) - 1)
    # Approximate: cursor sits on the last line of cell_text.
    # Logical line-start when the partial token before the cursor is at column 0
    # ignoring indent.
    head = line[:cursor_col]
    stripped_head = head.lstrip()
    column_after_indent = len(head) - len(stripped_head)
    last_value = _last_value_keyword(cell_text, line_idx)
    last_frame = _last_frame_keyword(cell_text, line_idx)
    if column_after_indent == cursor_col and last_value is None:
        # We're at the start of a logical line, no value-keyword pending → frame keyword.
        return "line_start"
    if last_value in {"SubClassOf:", "EquivalentTo:", "DisjointWith:"}:
        return "object_property_or_class"
    if last_value in {"Domain:", "Range:"}:
        return "class"
    if last_value in {"Types:", "SameAs:", "DifferentFrom:"}:
        return "individual"
    if last_value == "Characteristics:":
        return "characteristic"
    if last_frame in {"Class:", "ObjectProperty:", "DataProperty:", "Individual:"}:
        # Inside the expression-body of a frame, before any value keyword:
        # most common is line_start (introducing SubClassOf:/etc.).
        return "line_start"
    return "line_start"


def _mos_complete(cell_text: str, line: str, cursor_col: int) -> list[str] | None:
    """Return Tab candidates for an MOS cell, or ``None`` to fall through to Python."""
    if not _is_mos_cell(cell_text):
        return None
    context = _classify_context(cell_text, line, cursor_col)
    pool = _candidate_pool(context)
    # Prefix-filter against the partial token under the cursor.
    head = line[:cursor_col]
    m = re.search(r"([A-Za-z_:][\w:]*)$", head)
    partial = m.group(1) if m else ""
    if not partial:
        return sorted(set(pool))
    return sorted({c for c in pool if c.startswith(partial)})


def _register_completer(ip) -> None:
    """Register the completer with IPython.

    IPython's ``set_custom_completer`` receives a callable that takes the shell
    and an event and returns a list of completions.  We adapt our pure helper
    ``_mos_complete`` to that interface.
    """

    def _adapter(_shell, event):
        # event.line is the current input line; event.symbol is the partial token.
        cell_text = getattr(event, "text_until_cursor", None) or event.line
        line = event.line or ""
        cursor_col = len(line)
        cands = _mos_complete(cell_text, line, cursor_col)
        return cands if cands is not None else []

    ip.set_custom_completer(_adapter)
```

Also register the completer inside `load_ipython_extension`, after the last `register_magic_function`:

```python
    _register_completer(ip)
```

- [ ] **Step 4: Run, verify pass**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 10 (or 9 + 1 skipped) passed.

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): Tab autocomplete inside %%mos cells (keywords + dynamic names)"
```

---

### Task 7: Syntax highlighting (Path A — CodeMirror JS injection)

Inject a CodeMirror language definition at extension-load time. JupyterLab 4 uses CodeMirror 6; for a regex-based mode the cleanest interop is via `@codemirror/legacy-modes/mode/simple-mode`, accessed by JupyterLab's exposed registry.

**Files:**
- Modify: `pymos/jupyter.py`

- [ ] **Step 1: Add a test that the JS payload contains the expected hooks**

This task is hard to assert behaviorally in a unit test (no real CodeMirror in a headless IPython shell). The behavioral verification happens in Task 9's smoke test (rendered HTML inspection). Here we test only that `load_ipython_extension` emits a JS payload containing the Manchester keyword list — a regression guard against accidentally stripping the highlighter.

Append to `tests/test_jupyter_magics.py`:

```python
def test_load_extension_emits_codemirror_js(capsys):
    """The injected JS payload must mention the Manchester keywords; if it doesn't,
    highlighting is silently lost. Behavioral check happens in the docker smoke test.
    """
    from IPython.testing.globalipapp import get_ipython
    ip = get_ipython()
    if "pymos.jupyter" in ip.extension_manager.loaded:
        ip.extension_manager.unload_extension("pymos.jupyter")
    # Capture displayed Javascript via the rich-display registry.
    captured = []
    orig_publish = ip.display_pub.publish

    def _spy(data, metadata=None, **kwargs):
        captured.append(data)
        return orig_publish(data, metadata=metadata, **kwargs)

    ip.display_pub.publish = _spy
    try:
        ip.extension_manager.load_extension("pymos.jupyter")
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
```

- [ ] **Step 2: Run, verify fail**

```bash
python -m pytest tests/test_jupyter_magics.py::test_load_extension_emits_codemirror_js -v
```
Expected: FAIL — no JS is emitted yet.

- [ ] **Step 3: Implement the injector**

Add to `pymos/jupyter.py`, after the completer code:

```python
from IPython.display import Javascript, display


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
          {regex: /\b(?:Class|ObjectProperty|DataProperty|Individual|Datatype|AnnotationProperty|Ontology|Prefix|Import|SubClassOf|EquivalentTo|DisjointWith|Domain|Range|SubPropertyOf|Types|SameAs|DifferentFrom|Facts|Characteristics|Annotations):/, token: 'keyword'},
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
      // Make it available under the well-known mime type so cell-magic
      // detection can find it.
      if (window.jupyterapp) {
        const editorTracker = window.jupyterapp.shell.widgets('main');
        // Tagging happens via metadata on the cell; user opts in by setting
        // the cell metadata "codemirror_mode" to "manchester-syntax".
      }
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
    """
    display(Javascript(_CODEMIRROR_JS))
```

Register it at the END of `load_ipython_extension`:

```python
    _inject_codemirror_mode()
```

- [ ] **Step 4: Run the test, verify it passes**

```bash
python -m pytest tests/test_jupyter_magics.py -v
```
Expected: 11 (or 10 + 1 skipped) passed.

- [ ] **Step 5: Commit**

```bash
git add pymos/jupyter.py tests/test_jupyter_magics.py
git commit -m "feat(jupyter): inject CodeMirror manchester-syntax mode at load_ext time"
```

---

### Task 8: The deliverable notebook

Write `examples/notebooks/05_interactive_mos.py` (jupytext percent) and convert to the executed `.ipynb`. The notebook tells a short pizza-→-biomedical story exercising every magic.

**Files:**
- Create: `examples/notebooks/05_interactive_mos.py`
- Create (generated): `examples/notebooks/05_interactive_mos.ipynb`

- [ ] **Step 1: Write `05_interactive_mos.py`**

Create `examples/notebooks/05_interactive_mos.py`:

```python
# %% [markdown]
# # 05 — Interactive MOS notebook
#
# Build, reason about, and query an ontology by writing **Manchester OWL Syntax**
# directly in cells. Magics handle the rest.
#
# - `%%mos` — parse cell body as MOS, merge into the active ontology.
# - `%reason` — run **HermiT** over the active world (materializes inferences).
# - `%%mos_query <relation>` — query the active ontology with an anonymous MOS expression.
# - `%mos_show <Name>` — render one entity's axioms back to MOS.
# - `%mos_save <path>` — round-trip the active ontology to a `.omn` file.
#
# Tab inside a `%%mos` cell completes keywords, class names, properties, and individuals.

# %%
%load_ext pymos.jupyter

# %% [markdown]
# ## Build a small pizza ontology

# %%mos
ObjectProperty: hasTopping
Class: Pizza
Class: Cheese
Class: Tomato
Class: Margherita
    SubClassOf: Pizza
    EquivalentTo: Pizza and (hasTopping some Cheese)

# %% [markdown]
# ## Reason
#
# HermiT runs over the asserted graph and materializes inferences back into the world.

# %reason

# %% [markdown]
# ## Query
#
# Ask: which named class is equivalent to `Pizza and (hasTopping some Cheese)`?

# %%mos_query equiv
Pizza and (hasTopping some Cheese)

# %% [markdown]
# ## Render one class back to MOS

# %mos_show Margherita

# %% [markdown]
# ## Extend the ontology
#
# Manchester cells merge incrementally — re-running `%%mos` adds, it doesn't replace.

# %%mos
Class: Vegetarian
    EquivalentTo: Pizza and not (hasTopping some Meat)
Class: Meat

# %% [markdown]
# Re-run reasoning to pick up the new axioms, then query subclasses of Pizza.

# %reason

# %%mos_query sub
Pizza

# %% [markdown]
# ## Save the whole ontology

# %mos_save /tmp/pizza-built.omn

# %% [markdown]
# ## Takeaway
#
# You wrote MOS, asked HermiT to reason, queried via SPARQL, and round-tripped to
# disk — without leaving Manchester syntax. The live ontology is also exposed in
# the user namespace as `mos_onto` (and the world as `mos_world`) for any Python
# follow-up you want.

# %%
print("classes:", [c.name for c in mos_onto.classes()])
print("properties:", [p.name for p in mos_onto.object_properties()])
```

Note: jupytext percent format permits cell magics inline with `# %%` markers; the magics convert into normal cells in `.ipynb` and execute as-is.

- [ ] **Step 2: Convert to `.ipynb`** (executed in the container so the Java is present)

Bring up the stack briefly and convert:

```bash
docker compose -f examples/docker-compose.yml up -d --build
sleep 15  # let JupyterLab finish pip install -e .

docker compose -f examples/docker-compose.yml exec -T notebook \
  jupytext --to ipynb examples/notebooks/05_interactive_mos.py
```
Expected: creates `examples/notebooks/05_interactive_mos.ipynb` (no outputs yet).

- [ ] **Step 3: Execute the notebook headless inside the container**

```bash
docker compose -f examples/docker-compose.yml exec -T notebook bash -lc \
  "jupyter nbconvert --to notebook --execute --inplace examples/notebooks/05_interactive_mos.ipynb"
```
Expected: exit 0. If `%reason` errors with a Java not found message, re-check Task 1 Step 3 (java should be present).

- [ ] **Step 4: Tear down**

```bash
docker compose -f examples/docker-compose.yml down
```

- [ ] **Step 5: Commit**

```bash
git add examples/notebooks/05_interactive_mos.py examples/notebooks/05_interactive_mos.ipynb
git commit -m "feat(examples): notebook 05 — interactive MOS with reason + query + render"
```

---

### Task 9: End-to-end smoke test (incl. highlighting verification)

Full-stack run that re-executes the notebook AND inspects the rendered HTML to confirm CodeMirror's Manchester mode took effect. If the HTML check fails, escalate per the spec's Path B.

**Files:** none — this task verifies the whole system.

- [ ] **Step 1: Bring up the stack**

```bash
docker compose -f examples/docker-compose.yml up -d --build
sleep 15
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8888/api
```
Expected: `200`.

- [ ] **Step 2: Execute the notebook headless**

```bash
docker compose -f examples/docker-compose.yml exec -T notebook bash -lc \
  "jupyter nbconvert --to notebook --execute --inplace examples/notebooks/05_interactive_mos.ipynb"
```
Expected: exit 0, zero error outputs. Verify with:

```bash
docker compose -f examples/docker-compose.yml exec -T notebook python -c "
import json
nb = json.load(open('examples/notebooks/05_interactive_mos.ipynb'))
errs = [o for c in nb['cells'] if c['cell_type']=='code'
        for o in c.get('outputs', []) if o.get('output_type')=='error']
print('error outputs:', len(errs))
"
```
Expected: `error outputs: 0`.

- [ ] **Step 3: Verify the CodeMirror injection produced a Javascript display blob**

```bash
docker compose -f examples/docker-compose.yml exec -T notebook python -c "
import json
nb = json.load(open('examples/notebooks/05_interactive_mos.ipynb'))
js_outputs = []
for c in nb['cells']:
    if c['cell_type']!='code': continue
    for o in c.get('outputs', []):
        data = o.get('data') or {}
        if 'application/javascript' in data or 'text/javascript' in data:
            js_outputs.append(data)
print('js display outputs:', len(js_outputs))
combined = ''.join(
    (d.get('application/javascript') or d.get('text/javascript') or '')
    for d in js_outputs
)
assert 'manchester' in combined.lower(), 'manchester not in JS payload'
assert 'SubClassOf' in combined, 'SubClassOf not in JS payload'
print('OK: manchester-syntax JS payload present')
"
```
Expected: prints `OK: ...`. If this fails, the JS injection didn't survive nbconvert — the data is lost on execute. This still doesn't mean highlighting failed live in JupyterLab; it just means we can't verify it from a non-interactive run. **Document the limitation and proceed**: log "Path A behavioural verification deferred to manual smoke" and add a note in the notebook's top markdown cell that highlighting only takes effect in interactive JupyterLab (not in nbconvert HTML).

- [ ] **Step 4: Manual highlighting check (one-time, by the operator)**

Document the manual step: open http://localhost:8888 in a browser, open `notebooks/05_interactive_mos.ipynb`, click into a `%%mos` cell, and confirm the keyword `Class:` is colored (any color distinct from the surrounding text counts). If it isn't, escalate per the spec's Path B — open a follow-up issue to ship a prebuilt JupyterLab extension. This is NOT a blocker for the PR; it's a known-fallback path.

- [ ] **Step 5: Tear down**

```bash
docker compose -f examples/docker-compose.yml down
```

- [ ] **Step 6: Commit the executed notebook (now with the live outputs)**

```bash
git add examples/notebooks/05_interactive_mos.ipynb
git commit -m "test(examples): execute notebook 05 end-to-end with HermiT in container"
```

(If `git status` shows no change to the .ipynb, that's fine — skip.)

---

### Task 10: README update

Tell users the notebook exists and how to launch it.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Locate the existing examples-related section**

```bash
grep -n "examples\|notebooks\|docker compose" README.md | head
```

Note the line numbers — the README already has launch instructions for the demo notebooks (from PR #2). The MOS notebook lives in the same stack, so the launch command is unchanged; we just add an entry for the new notebook.

- [ ] **Step 2: Edit README.md**

Find the table or list of notebooks in the README (likely in a section that mentions `01_parsing.ipynb`, `02_class_relations.ipynb`, `03_remote_endpoint.ipynb`). Add a new row/bullet:

```markdown
| `05_interactive_mos.ipynb` | Write MOS in `%%mos` cells; **reason** with HermiT (`%reason`); query the asserted+inferred graph with `%%mos_query`; round-trip via `%mos_show` / `%mos_save`. Includes syntax highlighting and Tab autocomplete inside MOS cells. Requires Java in the image (already added). |
```

If the existing notebook list is a bulleted list rather than a table, mirror the style of the existing entries.

- [ ] **Step 3: Verify the file is well-formed markdown**

```bash
python -c "
import pathlib
t = pathlib.Path('README.md').read_text()
assert '05_interactive_mos' in t
assert '%%mos' in t
assert '%reason' in t
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): point at interactive MOS notebook"
```

---

## Self-Review Notes

- **Spec coverage:** worktree (already set up before task list); magics `%%mos` (Task 2), `%reason` (Task 3), `%%mos_query` (Task 4), `%mos_show` + `%mos_save` (Task 5); autocomplete with the context table (Task 6); highlighting Path A with documented Path B fallback (Task 7, Task 9 Step 4); HermiT default + Pellet swap via `%reason pellet` (Task 3); deliverable notebook (Task 8); smoke test (Task 9); README (Task 10); Dockerfile JRE + IPython dev extra (Task 1). All success criteria map to a task.
- **Type consistency:** `_mos_complete(cell_text, line, cursor_col)` used identically in Task 6 tests and the adapter wrapping it; `_state.onto`, `_state.world` consistent across all magics; `pymos.render(onto, prefixes=...)` and `pymos.render_frame(entity, prefixes=...)` signatures match the verified probe.
- **Placeholder scan:** every step has full code or an exact command. Task 9's "if injection didn't survive nbconvert, document and proceed" is a concrete instruction, not a TBD: a one-line note in the notebook + a follow-up issue.
- **Known risk:** Path A (JS injection) is the lightweight choice; if JupyterLab 4's CodeMirror 6 module loader rejects the `require(...)` call, highlighting silently doesn't render. Task 9 Step 4 documents the manual check; the fallback is a prebuilt extension (deferred to a follow-up per spec).
- **Test-discovery note:** `tests/test_jupyter_magics.py` lives under `tests/` so `pyproject.toml`'s `testpaths = ["tests"]` picks it up automatically. No explicit-path invocation needed.
