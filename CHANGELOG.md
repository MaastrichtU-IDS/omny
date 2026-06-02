# Changelog

All notable changes to this project will be documented in this file.

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
