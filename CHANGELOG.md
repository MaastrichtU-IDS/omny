# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed

* **`inverse (P)` object-property expressions accepted outside property
  chains** (issue #68). A `SubPropertyOf:` operand of the form
  `inverse (P)` (OWL 2 `ObjectInverseOf`, used by RO, e.g.
  `SubPropertyOf: inverse (RO_0002376)`) was passed straight to the CURIE
  resolver, which raised `Unknown prefix 'inverse (obo'` and **dropped the
  whole `ObjectProperty:` frame** (taking its other axioms with it). The
  `SubPropertyOf:` operand resolver now recognises `inverse (P)` and records
  it as `is_a.append(Inverse(P))` (RDF: `p rdfs:subPropertyOf
  [ owl:inverseOf P ]`); it round-trips to `inverse <name>` on render. The
  rare `InverseOf: inverse (Q)` form (no owlready2 `inverse_property =
  Inverse(...)` representation; absent from SIO/RO/SULO) now warns and
  preserves the rest of the frame instead of dropping it.

* **Manchester reader no longer silently drops valid OWL 2 constructs**
  (issue #66). Two valid Manchester Syntax forms — accepted by the OWL
  API / ROBOT — were emitting a `UserWarning` and discarding the
  axiom/frame instead of parsing it:
  * **Typed/lang literals in `Facts:`** — a datatype literal such as
    `:hasBirthYear "1868"^^xsd:integer` was mis-tokenised by splitting on
    the last `:` (treating `"1868"^^xsd` as a CURIE prefix), which raised
    `Unknown prefix` and dropped the **entire `Individual:` frame**. The
    Facts value parser now recognises the three quoted-literal forms —
    plain `"…"`, typed `"…"^^datatypeIRI`, and language-tagged `"…"@lang`
    — splitting the `^^`/`@` separator after the closing quote. Lang tags
    are preserved as `locstr` and round-trip through `render`.
  * **`SubPropertyChain:`** — the standard object-property frame keyword
    was unrecognised and its axiom dropped. It is now parsed into a
    `SubObjectPropertyOf(ObjectPropertyChain(...), prop)` (owlready2
    `property_chain`) and rendered back out. Chain links may be
    `inverse (P)` expressions (used heavily by RO, e.g.
    `inverse (RO_0002176) o RO_0002176`); these are written as RDF
    (`owl:inverseOf` blank node in the `owl:propertyChainAxiom` list) since
    an `Inverse` link has no storid for owlready2's high-level API.

  Surfaced while validating against SIO, RO and SULO, the same family of
  silently-dropped construct was also fixed:

  * **`DisjointUnionOf:`** — was an unrecognised class-frame keyword (used
    by SULO, e.g. `Feature DisjointUnionOf: Capability, …`). Now recorded
    with OWL 2 semantics: the class is `EquivalentTo` the union of the
    members plus an `AllDisjoint` over them (owlready2 has no native
    disjoint-union construct).

## [0.2.2] — 2026-06-03

### Fixed

* **Example notebooks 02 / 03 / 04 are portable again** (PR #61).
  Pre-fix the three notebooks hardcoded either
  `/workspace/examples/data/biomed.omn` (a docker-compose bind-mount
  path) or a cwd-dependent `Path("..") / "data" / …`, so anyone
  trying to follow the notebooks outside the docker-compose context
  hit `FileNotFoundError`. The `.py` paired files now use
  `Path(__file__).resolve().parents[1] / "data" / "biomed.omn"`, and
  the `.ipynb` files use `Path("..") / "data" / "biomed.omn"` (works
  in Jupyter UI from either local or compose context). Notebooks 01,
  02, and 04 now run end-to-end as scripts; 03 still needs the live
  oxigraph triplestore; 05 needs Jupyter; 06 needs Java for HermiT.

## [0.2.1] — 2026-06-03

Skips `0.2.0` and `0.1.3` because the v0.2.0 and v0.1.3 tags were
pushed without bumping `pyproject.toml`; both `publish.yml` runs
built `omny-0.1.1.*` wheels which PyPI rejected as duplicates. PyPI
was never updated. This release bundles the fixes that were meant
to ship in those two tags + a CI guard that prevents the
tag-vs-pyproject mismatch from silently failing again.

### Correctness

* **`fix(parse)` — rdfs:label/comment shorthand routes under the
  actual rdfs IRIs** (PR #57). Pre-fix, an annotation written as
  `Annotations: rdfs:comment "X"` could be routed under
  `<http://schema.org/comment>` if the doc also declared
  `schema:comment` (both share owlready2's `python_name="comment"`).
  Closes the deferred lever from PR #44.

### Performance

* **`perf(parse)` — direct-write `(ind, rdf:type, type)` triples
  for named-class Individual Types** (PR #58). Same pattern as
  PR #49's SubClassOf direct-write; bypasses per-axiom owlready2
  individual callback on individual-heavy ontologies. Negligible on
  HP (few individuals); ~PR-#49-shape gain on OBI/SIO patterns.

### Docs

* **`docs(README)` — install info polish** (PR #56). Pointed
  `pip install` at PyPI (was `-e .`), reconciled extras table with
  current core deps, fixed Quick taste to not `import owlrl`
  upfront (would `ImportError` on fresh installs).

### CI / Release

* **`ci` — version-vs-tag consistency guard in `publish.yml`**
  (this release). When `publish.yml` runs on a tag push, it now
  asserts that the tag (`vX.Y.Z`) matches `pyproject.toml`'s
  `version = "X.Y.Z"` before attempting the build. A mismatch
  fails loudly with a clear error message — no more silently-failed
  PyPI uploads.

### Bookkeeping

* **`chore` — untrack `build/`** (PR #59). The directory was
  accidentally committed during the rename; persistent
  `M build/lib/omny/__init__.py` is gone.

## [0.1.1] — 2026-06-02 (packaging fix)

Bug fix: `rdflib` was in `[project.optional-dependencies]` but
`omny.render` requires it unconditionally (the datatype enumeration
in `_declared_datatype_iris` and the bulk annotation-fetch in
`_build_annotation_map` both call `world.as_rdflib_graph()`). A
fresh `pip install omny==0.1.0` could parse but not render.

Moved `rdflib>=7.0` to core dependencies. The optional `[rdflib]`
extra is kept for backward compatibility — installing it explicitly
is now a no-op but doesn't error.

No other behavioural changes.

## [0.1.0] — 2026-06-02 (first PyPI release as `omny`)

Initial PyPI release. The package was developed under the name `pymos`
at `MaastrichtU-IDS/pymos`; `omny` is the same library renamed for PyPI
(the `pymos` name was taken). All public API is unchanged in shape;
only the import name changes:

```python
# old
import pymos
from pymos.store import run_rdflib

# new
import omny
from omny.store import run_rdflib
```

### Features (as of 0.1.0)

Pure-Python Manchester OWL Syntax parser and renderer, no Java
required:

- **Parser** (`omny.parse`, `omny.parse_expression`): lark LALR
  backend covering the full Manchester syntax — class expressions,
  data ranges + facets, all literal forms (typed, language-tagged,
  datetime, duration, decimal, float, integer, boolean),
  inverse-property in cardinality positions, OneOf, prefixed and
  full IRIs. Parsimonious backend kept as a legacy import.
- **Renderer** (`omny.render`, `omny.render_frame`,
  `omny.render_expression`): owlready2 → Manchester text;
  round-trips parse → render → parse without loss on the supported
  axiom kinds.
- **SPARQL builder** (`omny.class_relations_query`): CONSTRUCT /
  SELECT for sub-, super-, equivalent-, direct-sub/super-,
  individual-of relations, with property paths and
  anonymous-expression block targets.
- **Store backends** (`omny.store.run_rdflib`, `run_pyoxigraph`,
  `run_owlready2`, `run_endpoint`): consistent interface over
  rdflib, pyoxigraph in-memory, owlready2's SPARQL engine, and
  remote HTTP endpoints.
- **Jupyter** (`omny.jupyter`): `%%mos` / `%mos_query` /
  `%reason` magics with autocomplete.
- **Performance**: 11-PR optimisation series (see
  `docs/perf-2026-06-02-session-summary.md`) brought HP (32 k
  classes, 30 MB) parse + render from > 900 s to ~125 s sum-of-parts
  (~100 s back-to-back) — about 7.2× cumulative.

### Why "omny"

Short, distinct, easy to type, and the `.omn` file extension is the
Manchester syntax file format this library is built around. The
original `pymos` name was taken on PyPI.

### Provenance

- Grammar vendored from [owlapy](https://github.com/dice-group/Ontolearn)
  (MIT, see NOTICE).
- Targets [owlready2](https://owlready2.readthedocs.io/) (LGPL).
