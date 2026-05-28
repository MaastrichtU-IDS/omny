# Interactive MOS Notebook — Design

**Date:** 2026-05-28
**Status:** Approved

## Goal

A Jupyter notebook where the user **just writes MOS (Manchester OWL Syntax)
statements** to incrementally build an ontology, **reasons** over it (HermiT),
and **queries** it (SPARQL via pymos), all from within MOS-flavoured cells. Ship
with **syntax highlighting** and **Tab autocomplete** for MOS, runnable from the
existing `examples/` docker-compose stack.

## Worktree

Implementation happens in `/data/dumontier/pymos-mos-notebook` on branch
`feat/mos-notebook` (branched from master `8bdd7a9`). The branch eventually
merges via PR.

## UX — IPython cell magics

```text
%load_ext pymos.jupyter                 # first cell of the notebook

%%mos                                   # parse MOS, merge into the active ontology
Class: Pizza
Class: Margherita
    EquivalentTo: Pizza and (hasTopping some Cheese)

%reason                                 # run HermiT → materialize inferences

%%mos_query equiv                       # query with an anonymous MOS expression
Pizza and (hasTopping some Cheese)

%mos_show Margherita                    # render one class's axioms back to MOS
%mos_save mypizza.omn                   # round-trip the whole ontology to MOS
```

Five magics in total. Reasoner default is **HermiT**; switching to Pellet is a
one-line swap (`sync_reasoner_pellet`) — documented in the notebook.

## Components

```
pymos/
├── jupyter.py                 # NEW — magics + custom completer + highlight injector
└── ...                        # existing modules used as-is

examples/
├── Dockerfile                 # MODIFY — add default-jre-headless for HermiT
└── notebooks/
    └── 05_interactive_mos.ipynb   # NEW — the deliverable

tests/
└── test_jupyter_magics.py     # NEW — drive magics via IPython.testing
```

`pymos/jupyter.py` owns:
- a module-level `_state` (singleton `World` + `Ontology` bound to a default IRI),
- the five `@line_magic` / `@cell_magic` functions,
- a custom completer registered via `get_ipython().set_custom_completer`,
- a one-shot `_inject_codemirror_mode()` that runs at `%load_ext` time.

It depends on already-shipped modules: `pymos.frames.parse`, `pymos.parser.parse_expression`,
`pymos.sparql.class_relations_query`, `pymos.store.run_rdflib`, `pymos.render`.

## Data flow

1. `%load_ext pymos.jupyter` instantiates `_state.world` and `_state.onto`, registers
   the five magics, registers the custom completer, and injects the CodeMirror mode.
2. `%%mos <body>` calls `pymos.parse(body, onto=_state.onto)` — additive merge into the
   live ontology.
3. `%reason` calls `with _state.onto: owlready2.sync_reasoner(_state.world)`. After this,
   `.is_a` / `.equivalent_to` on classes include HermiT's inferences, and SPARQL queries
   over the rdflib view reflect any materialized triples.
4. `%%mos_query <relation> <body>` parses the body as an anonymous class expression via
   `parse_expression`, builds `class_relations_query(expr, relations=(relation,),
   construct=False)`, runs through `run_rdflib`, prints the resulting IRIs (one per line).
5. `%mos_show <Name>` resolves the named entity in `_state.onto` and renders its axioms
   via `pymos.render`.
6. `%mos_save <path>` writes the full rendered ontology to `<path>` as a `.omn` file.

## Syntax highlighting

**Path A (default, light):** at `%load_ext` time, `_inject_codemirror_mode()` calls
`IPython.display.display(IPython.display.Javascript(...))` with a JS payload that
registers a Manchester-syntax language with CodeMirror. The mode is regex-based and
covers frame keywords, restriction operators, IRIs, prefixed names, and comments.
JupyterLab is told to apply the language to cells whose first line is `%%mos` or
`%%mos_query`.

JupyterLab 4 uses CodeMirror 6, whose API for runtime mode registration is stricter
than CM5. The smoke test (Task 8 in the plan) verifies the mode actually takes effect
in the running container.

**Path B (documented fallback):** if Path A silently no-ops under JupyterLab 4, ship
a prebuilt JupyterLab extension (`pymos-jupyterlab` Python wheel, TS source) that
registers the language properly. Spec defers this to a follow-up if needed.

## Autocomplete

Tab completion via `get_ipython().set_custom_completer(_mos_completer)`. The
completer is invoked on Tab and returns candidates whose prefix matches the partial
token under the cursor.

**Gating:** the completer is registered globally but only returns MOS candidates
when the current cell's first line is `%%mos` or `%%mos_query`. Otherwise it
returns `None`, letting the default Python completer run unaffected.

**Context resolution:** a small state machine scans backward from the cursor through
the cell text to determine which class of token is expected:

| Context | Candidate source |
|---|---|
| Logical-line start | Frame keywords: `Class:`, `ObjectProperty:`, `DataProperty:`, `Individual:`, `Datatype:`, `AnnotationProperty:`, `Ontology:`, `Prefix:`, `Import:` |
| After `SubClassOf:` / `EquivalentTo:` / `DisjointWith:` | Class names from `onto.classes()` + operators `and`, `or`, `not`, `(` |
| After `Domain:` / `Range:` (object property) | Class names |
| After `Domain:` / `Range:` (data property) | Datatype names: `xsd:integer`, `xsd:string`, … |
| After `Characteristics:` | `Functional`, `InverseFunctional`, `Transitive`, `Symmetric`, `Asymmetric`, `Reflexive`, `Irreflexive` |
| After `Types:` / `SameAs:` / `DifferentFrom:` | Individual names from `onto.individuals()` |
| Inside a class expression after a known property | Restriction keywords: `some`, `only`, `value`, `min`, `max`, `exactly`, `Self`, then class/individual names |

The completer reads `_state.onto` at every call, so completions reflect whatever has
been declared so far.

**Caveat:** IPython completion is Tab-triggered server-side; there is no
continuous-typing dropdown without an LSP server. That is out of scope.

## Reasoner & dependencies

- **HermiT** via `owlready2.sync_reasoner()` is the default. owlready2 ships
  `HermiT.jar` in its package; reasoning shells out to `java -jar`.
- The existing `examples/Dockerfile` is modified to install `default-jre-headless`.
  No other dependency changes.
- The existing `examples/docker-compose.yml` is reused as-is (no changes).

## Error handling

- `%reason` before any `%%mos`: friendly error "no ontology axioms yet — start with a
  `%%mos` cell".
- MOS parse errors surface the line / column from parsimonious.
- Unknown name in `%mos_show`: print the message and a sorted list of names of each
  kind (`onto.classes()`, `onto.object_properties()`, `onto.individuals()`).
- `%mos_query` with an unknown relation name: list the allowed six (`super`, `sub`,
  `direct_super`, `direct_sub`, `equiv`, `individual`).
- `%mos_save` to an unwritable path: standard `IOError` surfaced with the path.

## Out of scope (YAGNI)

- No multi-ontology / multi-world switching — single active `_state`.
- No continuous (as-you-type) completion — Tab only.
- No autocomplete inside Python cells — only inside `%%mos` / `%%mos_query`.
- No prebuilt JupyterLab extension (Path B) unless Path A demonstrably fails.
- No syntax highlighting for `%mos_show` output (the rendered MOS text is read-only).
- No diff-tool comparing asserted vs. inferred — `_state.onto` is exposed for any
  Python code the user wants to write.

## Testing

- **`tests/test_jupyter_magics.py`** — uses `IPython.testing.globalipapp.get_ipython()`
  to drive the magics in-process:
  - load the extension; run `%%mos` with a small ontology; assert classes are in
    `_state.onto`.
  - run a second `%%mos` cell; assert it merges (no clobber).
  - call the completer's helper directly with a known partial token in each context
    and assert the expected candidate set.
  - skip the `%reason` test if Java is unavailable (`@pytest.mark.skipif(not _java)`);
    on machines with Java, run `%reason` and assert at least one inferred relation
    appears in `Class.is_a` that wasn't asserted.
  - run `%%mos_query equiv` against an axiom, assert the expected IRI is printed.
  - run `%mos_show <Name>`, assert output contains the axiom text.
  - run `%mos_save` to a tmp_path, re-parse with `pymos.parse`, assert classes match.
- **Smoke test (Task 8 in the plan):** the demo docker-compose stack is brought up,
  the notebook is executed headless via `nbconvert --execute`, and the resulting
  `.ipynb` is inspected to confirm zero error outputs. A second check inspects the
  rendered HTML of a `%%mos` cell to confirm the CodeMirror Manchester mode took
  effect (look for the expected CSS class on a known keyword). If the HTML check
  fails, escalate to Path B and re-spec.

## Success criteria

1. `docker compose -f examples/docker-compose.yml up --build` launches JupyterLab; the
   user opens `notebooks/05_interactive_mos.ipynb`, presses Run All, every cell
   succeeds.
2. A `%%mos` cell renders with Manchester keywords highlighted (CodeMirror class on a
   known token).
3. Pressing Tab after `SubClassOf: P` (with a class `Pizza` already declared) offers
   `Pizza` among the candidates.
4. After a `%%mos` defining `Margherita EquivalentTo: Pizza and (hasTopping some
   Cheese)` and a `%reason`, `%%mos_query equiv` with `Pizza and (hasTopping some
   Cheese)` returns `http://.../Margherita`.
5. `pytest tests/test_jupyter_magics.py` passes; full suite passes; the e2e smoke
   test in the container passes.
