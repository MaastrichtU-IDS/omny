# Perf snapshot — 2026-05-29, pymos

Host: fsesrv-g1, Linux-5.15.0-97-generic-x86_64-with-glibc2.35, python 3.10.12.
pymos: 7db3ba484317.  CPU count: 32.

## Headline

This is the first end-to-end execution of the pymos perf-bench harness (Task 22, v1). Using the
pizza test fixture (10 axioms, 897 bytes), the harness completes all parse, render, and query
workloads without errors across three in-memory backends. Parse and hot-render are fast (17 ms and
21 ms respectively). For query, `pyoxigraph_mem` leads at 18 ms median hot time, `owlready2_mem`
follows at 39 ms (CONSTRUCT cells skipped — owlready2 SPARQL engine does not support CONSTRUCT),
and `rdflib_mem` is slowest at 99 ms. All 92 executable cells succeeded; 18 cells were
structurally skipped (owlready2 CONSTRUCT).

### v1 scope note

- **Ontologies**: pizza only (test fixture, 10 axioms). Wine download succeeded but ROBOT OWL/XML
  conversion hung on network import resolution and was aborted; family.owl returned HTTP 404.
- **Reasoners**: `none` only. The snapshot runner does not yet wire `reasoner.materialise()` into
  the query workload — v2 follow-up. Running `owlrl` with the current code would produce duplicate
  asserted-graph measurements under a different label, which is misleading.
- **Backends**: `pyoxigraph_mem`, `owlready2_mem`, `rdflib_mem`. Backends `pyoxigraph_rocksdb` and
  `owlready2_sqlite` are not registered in `bench/workloads/query.py::_BACKEND_FACTORIES` and
  would error on every cell — v2 follow-up to wire them in.

## 1. Parse

| ontology | axioms | bytes | cold (s) | hot median (s) | peak RSS (MB) |
|---|---:|---:|---:|---:|---:|
| pizza | 10 | 897 | 0.017 | 0.017 | 37 |

## 2. Render

| ontology | bytes emitted | cold (s) | hot median (s) | idempotent? |
|---|---:|---:|---:|:---:|
| pizza | 1427 | 0.094 | 0.021 | yes |

## 3. Query — summary (median hot across relations × targets)

| ontology | backend | reasoner | median hot (s) | cells |
|---|---|---|---:|---:|
| pizza | owlready2_mem | none | 0.039 | 18 |
| pizza | pyoxigraph_mem | none | 0.018 | 36 |
| pizza | rdflib_mem | none | 0.099 | 36 |

## 4. Wrapper startup floors

| wrapper | floor (s) | notes |
|---|---:|:---|
| owlrl | 0.10 | in-process Python import |
| konclude-docker | 0.46 | rootless docker, image already pulled |
| robot-docker | 1.13 | rootless docker, image already pulled |

## 5. Coverage

- Total cells: 110
- Skipped (structurally n/a): 18
- Errored: 0
