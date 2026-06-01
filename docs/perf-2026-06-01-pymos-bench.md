# pymos perf snapshot — 2026-06-01

Host: `fsesrv-g1`, Linux-5.15.0-97-generic, Python 3.10.12, 32 CPUs.
pymos: master at `ad9d7be` (PRs #1–#36, including the new parse+reason and
OWLAPI-via-ROBOT workloads).
Bench data: `bench/results/2026-06-01-combined/` (tiny + small ontologies,
pyoxigraph_mem + owlready2_mem backends, `none` reasoner for query, owlrl
for `parse_reason`) and the one-off
`bench/runners/rcelebi_compare.py` output (sio comparison).
Wrapper floors on this host: owlrl 103 ms, robot-docker 1.14 s, konclude-docker 0.44 s.

## Headline

* **pymos.parse beats OWLAPI on tiny ontologies (10–500 axioms) by ~25–250×**,
  not because pymos's parser is faster but because OWLAPI eats a ~4 s
  JVM + docker startup floor and pymos's parser is in-process Python.
* **OWLAPI beats pymos on large ontologies**: on sio (1.5 MB, 1585 classes,
  ~17k axioms) ROBOT/OWLAPI loads in **2.2 s** vs pymos's **8.8 s** — a
  **~3.9× lead** that grows with size (the JVM startup amortises and
  OWLAPI's Manchester parser is faster per token).
* **`owlrl` materialisation costs scale super-linearly**: tiny ~500 ms
  but sio takes **~4.3 minutes** for an OWL 2 RL closure on the
  asserted graph. For ontologies past the small tier, plan for HermiT
  (via owlready2's `sync_reasoner_hermit()` JPype bridge) or ELK in a
  reasoner Docker container instead.
* **Query backends are close on the asserted graph**: `pyoxigraph_mem`
  is consistently equal-to-or-faster than `owlready2_mem` (SELECT,
  asserted, on this corpus) — by a comfortable factor on small ontologies
  but converging on sio (both ~6 s for SELECT `super`/`individual`).

## 1. Parse — pymos vs OWLAPI (via ROBOT-docker)

`pymos.parse` is in-process Python. `parse_owlapi` shells out to
`obolibrary/robot:v1.9.6`, which uses OWLAPI's
`OWLManager.loadOntologyFromOntologyDocument(...)` internally — the
wall therefore includes JVM + docker startup (~1.1 s floor measured
above; in practice 4 s of cold-start on this host) and a small write
of the converted output. Subtract the floor for a JVM-pure estimate.

| ontology | axioms (approx) | pymos.parse | OWLAPI (ROBOT wall) | OWLAPI − floor | ratio (pymos / OWLAPI) |
|---|---:|---:|---:|---:|---:|
| pizza   |    10 |   20 ms | 5 070 ms | ~4 s | **254×** in pymos's favour |
| koala   |    33 |  161 ms | 4 024 ms | ~3 s | **25×** in pymos's favour |
| travel  |    57 |  150 ms | 4 907 ms | ~3.8 s | **33×** in pymos's favour |
| sio     | ~17 000 | 8 775 ms | 2 243 ms | ~1.1 s | **3.9× in OWLAPI's favour** |

Read this as a crossover, not a winner. Below ~1k axioms pymos wins on
startup; above ~10k axioms OWLAPI wins on raw parsing throughput. There
is a sweet spot near sio where pymos is still fine for interactive use
(8.8 s) but OWLAPI is genuinely faster.

## 2. Render

`pymos.render` is in-process Python. No fair external comparator (OWLAPI
+ Manchester renderer would also pay the JVM startup; we'd be
benchmarking JVM-start, not the renderer).

| ontology | wall_cold |
|---|---:|
| pizza   |  188 ms |
| koala   |  430 ms |
| travel  |  631 ms |
| sio     | 16.7 s  |

Roughly 2–10× slower than parse on the same ontology. The renderer is
single-pass over `owlready2.classes()` / `.object_properties()` / `.individuals()`
plus an annotation-walk; cost scales with axiom count.

## 3. Parse + reasoning (`owlrl`, OWL 2 RL closure)

The `parse_reason` cell is `pymos.parse(path) + owlrl.materialise(path)`
in one subprocess. `owlrl` is a pure-Python OWL 2 RL forward-chaining
closure; no Java, no Docker.

| ontology | parse alone | parse + owlrl | inference cost | ratio |
|---|---:|---:|---:|---:|
| pizza   |   20 ms |     519 ms |    499 ms |  25×  parse |
| koala   |  161 ms |   1 989 ms |  1 828 ms |  11×  parse |
| travel  |  150 ms |   5 785 ms |  5 635 ms |  37×  parse |
| sio     | 8.8 s   | **259 s (4.3 min)** | 250 s | 28× parse |

Past the tiny tier `owlrl` becomes the wall-clock dominator. For sio
this is impractical for interactive use; the bench's HermiT / JFact /
ELK Docker wrappers (`bench.reasoners.{hermit,jfact,elk}`) are the
right call there but were not run as part of this snapshot.

## 4. Query (SPARQL via pymos.class_relations_query)

Median hot wall in ms, SELECT mode (CONSTRUCT was skipped in this
combined snapshot to bound wall budget; see the May 29 snapshot doc
for the CONSTRUCT numbers, which are typically ~2× the SELECT numbers).

| ontology | pyoxigraph_mem | owlready2_mem | pyoxigraph / owlready2 |
|---|---:|---:|---:|
| pizza   |    31 ms |    47 ms | 0.66 |
| koala   |   100 ms |   190 ms | 0.53 |
| travel  |   104 ms |   108 ms | 0.97 |
| sio     | 5 994 ms | 6 160 ms | 0.97 |

`pyoxigraph_mem` is consistently as fast or faster, with the lead
shrinking as ontology size grows (load-into-store cost dominates on
sio for both engines).

## 5. rcelebi/owlready2 fork — head-to-head (one-off)

Separate `.venv_rcelebi/` containing `rcelebi/owlready2 0.25 + pyoxigraph`;
upstream venv has `owlready2 0.50`. Measured by
`bench/runners/rcelebi_compare.py`. Input: `.rdfxml`
(owlready2's natural input; pymos isn't involved in this comparison).
Query: `SELECT (COUNT(*) AS ?n) WHERE { ?c rdfs:subClassOf ?d . FILTER(isIRI(?c) && isIRI(?d)) }`.

| ontology | upstream parse | rcelebi parse | upstream SPARQL | rcelebi SPARQL |
|---|---:|---:|---:|---:|
| koala  |   4 ms |   3 ms |   394 ms |  **23 ms** (17×) |
| travel |   5 ms |   5 ms |   510 ms |  **25 ms** (20×) |
| sio    | 451 ms | 536 ms | **301 ms** | 1 005 ms (3.3×) |

* Parse: roughly equivalent — small overhead for rcelebi (older base,
  no Cython parser optimisation) but in the noise on this corpus.
* SPARQL: rcelebi's pyoxigraph backend is **~17–20× faster** on
  small ontologies. On sio it is **~3× slower** for this particular
  `COUNT(*)` query — pyoxigraph rebuilds an in-memory graph then scans,
  while upstream's indexed SQLite quadstore answers small-result
  aggregations efficiently on a 1.5 MB ontology.
* For pure pymos→pyoxigraph SPARQL (no owlready2 wrapper) the existing
  `bench/backends/pyoxigraph_mem` is the closer apples-to-apples
  comparator and is included in §4 above.

## 6. Method notes & honest caveats

* **OWLAPI wall includes startup.** We subtract the measured docker+JVM
  floor in §1's "OWLAPI − floor" column; treat the bare ROBOT wall as a
  ceiling and the floor-subtracted number as a lower bound on OWLAPI's
  in-process parse.
* **owlrl materialisation includes the parse** (`bench_parse_then_reason`
  does parse + materialise in one cell, both starting from the path).
  Subtract the parse-alone number for an isolated reasoner cost.
* **Render is round-trip + idempotency-checked** but the wall reported
  here is just `pymos.render(parse(text))`; the idempotency assertion is
  a side check.
* **No reasoning was applied to query cells in this snapshot** —
  `reasoner="none"` was the only setting run. The `parse_reason`
  cells exist as a separate workload; wiring `reasoner.materialise()`
  into the query workload is its own (separate) follow-up.
* **rcelebi comparison uses `.rdfxml` input**, not `.omn`, because
  owlready2 (both forks) loads RDF/XML natively while pymos's natural
  input is Manchester. Both inputs encode the same logical ontology.
* **Wall floor for `owlrl` is ~100 ms** — its `DeductiveClosure.expand`
  has near-fixed overhead even on a 1-triple graph, then scales with
  closure size.

## 7. Reproducing

```bash
# Refresh the combined snapshot (tiny + sio, ~5 min):
.venv/bin/python -c "
from pathlib import Path
from bench.runners.snapshot import run_snapshot
run_snapshot(out_dir=Path('bench/results/REPRO'),
             ontologies=['pizza','koala','travel','sio'],
             backends=['pyoxigraph_mem','owlready2_mem'],
             reasoners=['none'], relations=('super','individual'),
             construct_modes=(False,), targets_per_ontology=1,
             hot_iters=1, warmup=0)"

# rcelebi comparison (~5 min; needs separate venv with rcelebi/owlready2):
python3 -m venv .venv_rcelebi
.venv_rcelebi/bin/pip install git+https://github.com/rcelebi/owlready2.git pyoxigraph
.venv/bin/python -m bench.runners.rcelebi_compare \
    --ontologies koala,travel,sio
```
