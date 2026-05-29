# Perf snapshot — 2026-05-29, pymos

Host: fsesrv-g1, Linux-5.15.0-97-generic-x86_64-with-glibc2.35, python 3.10.12.
pymos: a83debb66eed.  CPU count: 32.

## Headline

This snapshot extends v1 (pizza-only) to all three tiny-tier ontologies: pizza (10 axioms,
897 bytes), koala (33 axioms, 8952 bytes), and travel (57 axioms, 15634 bytes). Parse wall
time scales sublinearly with file size: moving from pizza to travel (17.5× larger) costs only
3.1× more parse time (18 ms → 56 ms), consistent with the parser's per-token rather than
per-file overhead. Render follows a similar curve (23 ms → 82 ms hot median). Query times
scale near-linearly with axiom count: `pyoxigraph_mem` leads at 19 ms / 38 ms / 59 ms across
the three ontologies, `owlready2_mem` runs at roughly 2× pyoxigraph's cost (42 ms / 63 ms /
86 ms), and `rdflib_mem` is consistently slowest at 107 ms / 138 ms / 174 ms. The backend
ranking is stable across all three ontologies and all six relation types. All 276 executable
cells completed without errors; 54 cells were structurally skipped (owlready2 CONSTRUCT
not supported).

### v1 scope note (carried forward)

- **Ontologies**: tiny tier only. Small-tier ontologies (sio, obi-core) were downloaded but
  failed the pymos parser: sio contains data range facets (`[>= "0.0"^^xsd:double]`) that
  trigger an `IncompleteParseError`; obi-core contains an `Unknown prefix '26th'` that
  triggers a `ValueError`. Both failures are pymos parser gaps, not harness issues. doid
  (28 MB RDF/XML) was downloaded but ROBOT conversion exceeded the 5-minute budget and was
  skipped. corpus.py was updated: wine replaced with koala (W3C wine.rdf caused ROBOT
  import-hang in all attempted modes); family replaced with travel (owlapi family.owl 404).
- **Reasoners**: `none` only. The snapshot runner does not yet wire `reasoner.materialise()`
  into the query workload — v2 follow-up.
- **Backends**: `pyoxigraph_mem`, `owlready2_mem`, `rdflib_mem`. Backends
  `pyoxigraph_rocksdb` and `owlready2_sqlite` are not registered in
  `bench/workloads/query.py::_BACKEND_FACTORIES` — v2 follow-up.

## 1. Parse

| ontology | axioms | bytes | cold (s) | hot median (s) | peak RSS (MB) |
|---|---:|---:|---:|---:|---:|
| pizza | 10 | 897 | 0.018 | 0.018 | 37 |
| koala | 33 | 8952 | 0.035 | 0.035 | 37 |
| travel | 57 | 15634 | 0.055 | 0.056 | 38 |

## 2. Render

| ontology | bytes emitted | cold (s) | hot median (s) | idempotent? |
|---|---:|---:|---:|:---:|
| pizza | 1427 | 0.100 | 0.023 | yes |
| koala | 7964 | 0.125 | 0.047 | yes |
| travel | 13656 | 0.153 | 0.082 | yes |

## 3. Query — summary (median hot across relations × targets)

| ontology | backend | reasoner | median hot (s) | cells |
|---|---|---|---:|---:|
| koala | owlready2_mem | none | 0.063 | 18 |
| koala | pyoxigraph_mem | none | 0.038 | 36 |
| koala | rdflib_mem | none | 0.138 | 36 |
| pizza | owlready2_mem | none | 0.042 | 18 |
| pizza | pyoxigraph_mem | none | 0.019 | 36 |
| pizza | rdflib_mem | none | 0.107 | 36 |
| travel | owlready2_mem | none | 0.086 | 18 |
| travel | pyoxigraph_mem | none | 0.059 | 36 |
| travel | rdflib_mem | none | 0.174 | 36 |

## 4. Wrapper startup floors

| wrapper | floor (s) |
|---|---:|
| konclude-docker | 0.64 |
| owlrl | 0.12 |
| robot-docker | 1.33 |

## 5. Coverage

- Total cells: 330
- Skipped (structurally n/a): 54
- Errored: 0
