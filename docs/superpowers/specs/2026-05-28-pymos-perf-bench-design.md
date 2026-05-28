# pymos performance benchmark — design

**Date:** 2026-05-28
**Status:** Approved, ready for implementation planning

## 1. Goal

Quantify pymos's parse / render / query performance across a spectrum of real-world
OWL DL ontologies, against multiple stores (in-memory and persistent), with and
without reasoning. Output: a single reproducible snapshot report in the
`docs/perf-YYYY-MM-DD-pymos-bench.md` narrative style established by
[`rustdl/docs/perf-*.md`](/data/dumontier/rustdl/docs/perf-2026-05-24-new-server.md).

The bench is a **one-shot snapshot** — not a continuous service — but the scripts
are deterministic, re-runnable, and structured so an `asv` wrapper could be added
later without rewriting them.

## 2. Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Bench scope | One-shot snapshot report (rustdl pattern); scripts re-runnable manually |
| Reasoner ambition | Full suite: owlrl (in-process) + HermiT / Pellet / ELK (ROBOT docker) + Konclude (konclude docker) |
| Ontology corpus | Size sweep across OBO Foundry ontologies, downloaded + cached locally |
| Backends tested | owlready2 (`:memory:` + SQLite file), pyoxigraph (in-memory + RocksDB), rdflib in-memory, remote Oxigraph (docker) |
| Fairness rule | All JVM reasoners under the same ROBOT-docker wrapper; JVM/docker startup floor **reported separately**, never silently subtracted |
| Statistical model | Best-of-3 cold, median-of-3 hot, with stddev; one cold + three hot per workload × backend × reasoner cell |
| Reasoning model | Materialise once (saturate the graph), then run pymos queries against the materialised store — both phases timed independently |
| Java in pymos itself | **None** (unchanged) — Java/docker live in the bench harness only, as SUT dependencies |

## 3. Architecture

```
bench/                         (gitignored from PyPI build; not part of the runtime package)
  __init__.py
  conftest.py                  pytest fixtures: corpus, backend factories, reasoner factories
  data/                        downloaded ontologies (gitignored)
  cache/                       per-backend persistent-store fixtures (gitignored)
  download.py                  fetch + verify-checksum + cache the corpus from OBO Foundry
  corpus.py                    declarative corpus manifest (name, IRI, expected axiom count, size tier)
  measure.py                   timing + tracemalloc + psutil RSS helpers; statistical aggregation
  backends/
    owlready2_mem.py    owlready2_sqlite.py
    pyoxigraph_mem.py   pyoxigraph_rocksdb.py
    rdflib_mem.py       endpoint_oxigraph.py
  reasoners/
    none.py             owlrl.py
    hermit.py           pellet.py             elk.py        konclude.py
    robot_docker.py                                                # shared wrapper for HermiT/Pellet/ELK
  workloads/
    parse.py            render.py             query.py
  runners/
    pytest_bench.py     # pytest-benchmark entry point (sanity / dev loop)
    snapshot.py         # full sweep → results.json + docs/perf-*.md
  results/              YYYY-MM-DD-run/                            (gitignored)
docs/perf-2026-05-28-pymos-bench.md          # the narrative report (committed)
```

Each module has one responsibility; cells of the cross-product
(`workload × backend × reasoner × ontology`) are independent execution units the
snapshot runner schedules as serial subprocess invocations (so peak memory per
cell is measured cleanly).

## 4. Ontology corpus (size sweep)

All from public OBO Foundry / standard W3C examples. `bench/corpus.py` declares
them with download IRI, SHA256, declared logical-axiom count, and tier.

| Tier | Ontology | IRI suffix | Axioms (approx) | Notes |
|---|---|---|---|---|
| Tiny | Pizza | `pizza/pizza.owl` (Manchester tutorial) | ~250 | tutorial ontology, full DL |
| Tiny | Wine | W3C `wine.rdf` | ~700 | classic DL test ontology |
| Tiny | Family | OWL-API `family.owl` | ~150 | |
| Small | SIO (core) | `sio.owl` | ~3 k | Semanticscience Integrated Ontology |
| Small | OBI core | `obi/dev/obi.owl` (subset) | ~5 k | |
| Small | DOID | `doid/doid.owl` | ~10 k | Human Disease Ontology |
| Medium | GO core | `go/go-basic.obo` → owx | ~30 k | basic Gene Ontology, no inverses |
| Medium | ChEBI lite | `chebi/chebi_lite.owl` | ~50 k | |
| Medium | HPO | `hp/hp.owl` | ~20 k | Human Phenotype Ontology |
| Large | GO full | `go/go.owl` | ~80 k | with relations |
| Large | ChEBI full | `chebi/chebi.owl` | ~140 k | |
| Large | NCIT | `ncit/ncit.owl` | ~170 k | |
| Huge (gated) | SNOMED CT | requires UMLS license | > 1 M | only run if `BENCH_SNOMED=1` and license file present |

Pymos's parser is Manchester syntax; OBO ontologies are typically RDF/XML or OBO
format. The download step converts each to `.omn` via `robot convert --output X.omn`
once at download time and caches the result (the conversion is itself measured for
the Tiny tier as a one-off sanity figure but not on the critical path).

## 5. Backends

Each backend is a factory in `bench/backends/` exposing the uniform interface:

```python
class Backend:
    name: str
    is_persistent: bool
    def load(self, ontology: Ontology) -> Handle: ...     # populate store from owlready2 ontology
    def query(self, sparql: str) -> Iterable: ...          # run SPARQL (CONSTRUCT or SELECT)
    def close(self) -> None: ...
```

| Backend | Persistence | Notes |
|---|---|---|
| `owlready2_mem` | in-memory | `World()` default — SQLite `:memory:` under the hood |
| `owlready2_sqlite` | on-disk | `World(filename="bench/cache/<onto>.sqlite3")` |
| `pyoxigraph_mem` | in-memory | `pyoxigraph.Store()` |
| `pyoxigraph_rocksdb` | on-disk | `pyoxigraph.Store("bench/cache/<onto>.ox/")` |
| `rdflib_mem` | in-memory | default `rdflib.Graph()`; for SELECT only on huge tiers |
| `endpoint_oxigraph` | on-disk (server) | docker-compose oxigraph from `examples/`; HTTP load + query |

`rdflib_mem` is in for completeness but on the Large and Huge tiers it's expected
to OOM or thrash; the runner marks it as `n/a` past the size at which it
allocates more than 4 GB RSS.

## 6. Reasoners

```python
class Reasoner:
    name: str
    profile: str           # "none", "RL", "EL", "DL"
    wrapper: str           # "in-process", "robot-docker", "konclude-docker"
    def materialise(self, ontology_path: Path) -> Path:
        """Run the reasoner, return the path to the saturated ontology
        (typically .owx) that the backend then loads."""
```

| Reasoner | Profile | Wrapper | Output format |
|---|---|---|---|
| `none` | — | — | (input verbatim) |
| `owlrl` | RDFS+OWL2 RL | in-process (pure Python on an rdflib graph) | RDF/XML or N-Triples |
| `hermit` | DL | `obolibrary/robot:v1.9.6` docker, `robot reason --reasoner HermiT` | OWX |
| `pellet` | DL | same docker, `--reasoner Pellet` | OWX |
| `elk` | EL | same docker, `--reasoner ELK` | OWX |
| `konclude` | DL | `konclude/konclude` docker, `classify` (per `rustdl-konclude-input` memory: input must be `.owx`) | OWX |

Fairness rules (from `rustdl-reasoner-bench`):
- All four JVM reasoners use the **same** ROBOT-docker image and the same input format (RDF/XML or OWX), exposed via a single `robot_docker.py` helper.
- The startup floor of each wrapper is measured separately with a no-op input
  (`robot --version` for ROBOT, `Konclude --version` for Konclude) and **reported
  alongside** the workload time. No silent subtraction.
- All cells are run on the same host; the report's header records CPU, RAM,
  Docker version, host architecture.

`owlrl` runs in-process: the runner loads the ontology into an `rdflib.Graph`,
calls `owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)`, and the resulting
saturated graph is the materialised store handed to each backend.

For DL reasoners (HermiT, Pellet, Konclude), `materialise()` returns a path to
the inferred ontology. Each backend loads that file. The asserted+inferred graph
is what pymos queries hit.

## 7. Workloads

Three workload modules, each exposing `bench(ontology, backend, reasoner)` and
returning a `Measurement`:

### 7.1 Parse

```python
text = ontology.read_text()             # measured: filesystem read excluded
t = time(); onto = pymos.parse(text)    # measured: parse only
```

Parameterised over ontology only (parse is not a backend or reasoner test).
Reports: wall-time, peak Python heap (`tracemalloc`), peak RSS (`psutil`), axiom
count of the resulting ontology, and per-axiom microseconds.

### 7.2 Render

```python
t = time(); text = pymos.render(onto, prefixes)                    # render once
t2 = time(); text2 = pymos.render(pymos.parse(text), prefixes)     # parse + render again
assert text == text2                                                # idempotency invariant
```

Reports first-render time + second-pass-idempotency time + bytes emitted.

### 7.3 Query

Six relation queries × two query modes (CONSTRUCT / SELECT) × N target classes
(per ontology, three target classes are picked from corpus.py: the
highest-degree class, a leaf, and a mid-depth interior class).

```python
q = class_relations_query(target, relations=(relation,), construct=mode)
t = time(); result = backend.query(q)
```

Reports: query latency, result cardinality, and (for CONSTRUCT) returned-triple count.

The 6 relations × 2 modes × 3 targets = **36 query cells per (ontology, backend,
reasoner)**. With 12 ontologies × 6 backends × 6 reasoners that is 15 552 query
cells; the runner skips cells by tier (e.g. ELK + Konclude on Tiny ontologies
where the JVM floor swamps the signal; `rdflib_mem` past ChEBI core where it
OOMs; `endpoint_oxigraph` is opt-in via `BENCH_ENDPOINT=1`). A pragmatic default
sweep is ≈ 3000 cells, ~30-60 min on the new server.

## 8. Measurement & statistical rigour

Each cell runs in a fresh Python subprocess so peak RSS is clean.

- 1 cold run (full process spin-up + workload).
- 3 hot iterations within the same process (after a 1-iteration warmup that is discarded).
- Reported: median of hot, stddev of hot, cold-time, and cold − median = `setup
  cost`.
- Wall-time via `time.perf_counter`; CPU time via `time.process_time`.
- Memory: `tracemalloc` peak (Python heap) and `psutil.Process().memory_info().rss` peak (resident).
- Per-reasoner-wrapper startup floor measured once at the top of the run
  (`robot --version`, `Konclude --version`, `python -c "import owlrl"`).

`measure.py` aggregates all cells into a flat `results.json` (one record per
cell) plus a wide `results.csv` for ad-hoc analysis.

## 9. Snapshot output

`bench/runners/snapshot.py --tier small,medium --reasoners none,owlrl,hermit
--backends owlready2_mem,pyoxigraph_mem --out docs/perf-2026-05-28-pymos-bench.md`

produces:

1. `bench/results/2026-05-28-run/results.json` (raw)
2. `bench/results/2026-05-28-run/results.csv`
3. `bench/results/2026-05-28-run/plots/*.png` (matplotlib: scaling curves)
4. `docs/perf-2026-05-28-pymos-bench.md` (narrative)

### Narrative report skeleton (mirrors rustdl perf-*.md)

```markdown
# Perf snapshot — 2026-05-28, pymos

Host: <CPU>, <RAM>, <kernel>, docker <version>, python <version>.
pymos: <git sha>.  Reasoners: owlrl <v>, HermiT/Pellet/ELK via ROBOT <v>, Konclude <v>.

## Headline
<one-paragraph summary: pymos parse scales ~linearly to N axioms; query latency
dominated by structural-path walk on Large+ ontologies; ELK/Konclude
materialisation 5–20× faster than HermiT on EL-shaped subsets of GO...>

## 1. Parse
table: ontology × parse wall, render wall, round-trip wall, per-axiom µs
scaling-plot: axioms vs parse-wall

## 2. Query — asserted only (no reasoning)
table per (ontology, relation), backend = pyoxigraph_mem
plot: query wall vs axioms, one line per relation

## 3. Query — with reasoning
same shape, one panel per reasoner; materialisation cost broken out

## 4. Backend comparison
pin one ontology (GO core), sweep all backends + reasoners
includes persistent vs in-memory cold-start cost

## 5. Wrapper floors
table: per-reasoner startup time (robot, konclude, owlrl import)

## 6. Caveats
- owlrl is incomplete for full DL (RL profile only)
- rdflib_mem OOMs above ChEBI core
- ELK / Konclude profile-incompatibility per ontology noted in cells as n/a
```

## 10. Reproducibility

- `bench/download.py` is idempotent, SHA256-verified, prints "cached" / "downloaded".
- The bench script header pins exact versions (`pymos@sha`, `pyoxigraph==`,
  `owlready2==`, `owlrl==`, docker images by digest not tag).
- Each `results/YYYY-MM-DD-run/` directory is self-contained (`env.txt`,
  `versions.txt`, `cmdline.txt`, `results.json`).
- Re-running the snapshot writes a new dated directory; existing reports are not
  overwritten — historical comparison is by-hand for now (asv could automate this
  later).

## 11. Out of scope (YAGNI)

- **No CI integration** of the perf bench. Bench runs are slow (minutes to hours
  per snapshot); they don't belong on every PR. CI stays as the existing fast
  `ruff + pytest` gate.
- **No live regression alerting.** Manual review of dated reports until asv is
  bolted on.
- **No multi-machine comparison.** Single-host snapshots only. Cross-host
  comparison is the report-reader's job.
- **No correctness benchmark.** Performance only — pymos's correctness is the
  unit test suite's job (171 tests on master).
- **No tuning recommendations in the report.** The report measures, it does not
  prescribe. Tuning patches come later as separate work referencing the report.

## 12. Open follow-ups (not blocking v1)

1. Add asv wrapper around the snapshot runner once two or three reports exist.
2. Wire the Huge tier (SNOMED CT, NCIT full) once a license-aware corpus loader
   is in place.
3. Add a "differential" mode that re-runs the previous snapshot's cells on the
   current pymos sha and reports deltas — useful for evaluating a perf patch.
4. Per-query memory profile (line-level) via `memray` for any cell whose RSS
   exceeds 1 GB.
