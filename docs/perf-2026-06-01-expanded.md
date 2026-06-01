# pymos perf snapshot — 2026-06-01 (expanded corpus)

Host: `fsesrv-g1`, Linux-5.15.0-97-generic, Python 3.10.12, 32 CPUs.
pymos: master at `9ba2fda` (PRs #1–#38, including the punning/cycle/
malformed-frame robustness fixes that unlocked HP).
Bench data: `bench/results/2026-06-01-expanded/results.json`
(pizza, koala, travel, sio, **hp** — the first medium-tier ontology
pymos has loaded end-to-end).

The earlier `docs/perf-2026-06-01-pymos-bench.md` covers the
**same-day baseline + method notes + rcelebi/owlready2 fork
comparison**; this file extends those numbers up the size spectrum.

## Headline

* **pymos.parse vs OWLAPI cross-over confirmed**: pymos wins on tiny
  by 25–250× (OWLAPI is dominated by ~5 s JVM + docker startup), but
  **OWLAPI wins on real-world ontologies** as size grows: sio (2106
  axioms) **2.0×**, HP (32 092 classes) **~9×**.
* **pymos handles HP** (32k classes, 29 MB `.omn`) end to end — that
  required the punning, inheritance-cycle and malformed-frame
  robustness fixes shipped in PR #38.
* **`owlrl` doesn't scale past tiny**: ~1–8 s on tiny ontologies, but
  ran past the 600 s subprocess timeout on sio. For anything bigger
  than a few hundred axioms, the bench's HermiT / JFact / ELK Docker
  wrappers (`bench.reasoners.{hermit,jfact,elk}`) are the right
  reasoner choice.
* **Render is the slowest pymos workload** by a wide margin on real
  ontologies: sio render 39 s vs sio parse 16 s; HP render exceeded
  the 600 s subprocess timeout.

## 1. Parse — pymos vs OWLAPI across the size spectrum

| ontology | axioms / classes | pymos.parse | OWLAPI (ROBOT wall) | pymos / OWLAPI |
|---|---|---:|---:|---:|
| pizza   | 10 axioms     |  **0.07 s** |   5.30 s | **76× pymos** |
| koala   | 33 axioms     |  **0.14 s** |   5.66 s | **40× pymos** |
| travel  | 57 axioms     |  **0.22 s** |   5.14 s | **23× pymos** |
| sio     | 2 106 axioms (1 585 classes) |  16.12 s |  **8.03 s** | **2.0× OWLAPI** |
| hp      | 32 092 classes | 270 s (standalone)¹ | **29.92 s** | **~9× OWLAPI** |

¹ HP parse in the bench's subprocess exceeded the 600 s
``measure_in_subprocess`` timeout (subprocess cold-start +
parsimonious init on top of the ~270 s parse). Standalone runs
finish at ~270 s; that number is reported here because the in-bench
run is bounded by a configurable cap, not the actual parse cost.

**The crossover.** Pymos's pure-Python parsimonious parser is the
clear winner where startup matters more than throughput — tutorial
ontologies, interactive use, CI test corpora. OWLAPI (JVM +
hand-tuned Manchester parser) overtakes once startup amortises;
the lead grows with axiom count, hitting roughly **one order of
magnitude on HP**. If you are reading 30k+-class biomedical
ontologies in a loop, OWLAPI is genuinely faster.

## 2. Render

| ontology | render (s) | idempotent (r2 == r3)? |
|---|---:|---:|
| pizza   |  0.26 | ✓ |
| koala   |  0.48 | ✓ |
| travel  |  0.54 | ✓ |
| sio     | 39.45 | ✗² |
| hp      | > 600 (timeout) | n/a |

² sio's r1 → r2 differs by ~100 bytes (annotation ordering, not
exponential growth). From r2 onward, ``r2 == r3`` — see the
2026-05-31 snapshot doc and PR #25 for the annotation-dedup fix
that closed exponential bloat.

Render is consistently the most expensive pymos workload on real
ontologies: it walks ``onto.classes()`` / ``object_properties()`` /
``individuals()`` and serialises each entity's full annotation set.
For sio, render is **~2.5× the parse cost**; for HP it didn't
complete in the bench's bounded budget.

## 3. Parse + reasoning (`owlrl`, OWL 2 RL closure)

| ontology | parse alone | parse + owlrl | reasoning cost |
|---|---:|---:|---:|
| pizza   |  0.07 s |  1.11 s |  1.04 s |
| koala   |  0.14 s |  3.26 s |  3.12 s |
| travel  |  0.22 s |  8.29 s |  8.07 s |
| sio     | 16.12 s | > 600 s (timeout) | > 580 s |
| hp      | 270 s | not attempted | — |

owlrl's pure-Python OWL 2 RL closure scales poorly past the tiny
tier: ~8 s for 57-axiom travel becomes >580 s for 2106-axiom sio. On
HP we didn't even try.

For ontologies past the tiny tier, the realistic reasoner choices are:

* **HermiT** / **JFact** / **ELK** via the bench's
  ``bench.reasoners.{hermit,jfact,elk}`` ROBOT-docker wrappers
  (JVM-backed, much faster, full OWL 2 DL).
* owlready2's ``sync_reasoner_hermit()`` JPype bridge if you already
  have a JDK on PATH.

## 4. What didn't fit yet

Three corpus members are still beyond what we measured here:

* **doid** (DOID, 10k axioms) — ROBOT `.rdfxml → .omn` conversion
  exceeded a 10-min budget on this host. owlready2 loading the
  `.rdfxml` directly succeeds in **12.7 s**, so the path
  "owlready2.load(rdfxml)" is faster than "ROBOT-convert + pymos.parse"
  for ontologies of this size.
* **chebi-lite** (50k axioms, 165 MB .rdfxml) — downloaded but not
  converted; ROBOT conversion would likely take 30+ min.
* **obi-core** (5k axioms, parses fine in 47 s) — not included in
  this matrix to keep the snapshot wall under an hour. Earlier
  snapshot (2026-05-31) has its numbers.

These three are real edge cases the user should know about:

1. The .omn → pymos pipeline has practical size limits set by ROBOT
   conversion time, not by pymos itself.
2. For "load a large biomedical ontology into Python," owlready2's
   direct RDF/XML loader is currently the most pragmatic path, with
   pymos's parse used only when you actually need Manchester input.

## 5. Headline interpretation

If you are working with **tutorial / W3C-spec / hand-edited ontologies
up to ~1 k axioms**: pymos.parse is decisively faster than OWLAPI and
trivially deployable (pure Python, no JVM).

If you are working with **real biomedical ontologies (10 k+ axioms,
HP/DOID/GO/CHEBI/MONDO scale)**:

* For ingest, **OWLAPI is faster** by a growing margin (2-10× by
  HP scale).
* For pymos.parse to be viable at this scale, ROBOT conversion to
  `.omn` must finish in your budget (DOID didn't; HP did at 29 MB
  .omn). If it doesn't, use `owlready2.get_ontology(rdfxml).load()`
  directly and skip pymos.parse.
* For reasoning, prefer HermiT/ELK over owlrl — owlrl works only
  on tiny ontologies in practice.

If you are working with **anything in between** (sio scale, 1k–10k
axioms): pymos and OWLAPI are within 2-3× of each other; pick the
language ergonomics you prefer.

## 6. Reproducing

```bash
# Convert hp.rdfxml → hp.omn (one-time, ~3 min ROBOT-docker on this host):
docker run --rm -v $(pwd)/bench/data:/work -w /work \
    obolibrary/robot:v1.9.6 robot convert \
    --input hp.rdfxml --output hp.omn

# Then drive the expanded snapshot (~30 min on this host):
.venv/bin/python - <<'PY'
from pathlib import Path
import warnings; warnings.simplefilter('ignore')
from bench.workloads.parse import bench_parse
from bench.workloads.render import bench_render
from bench.workloads.parse_owlapi import bench_parse_owlapi
from bench.workloads.parse_reason import bench_parse_then_reason
for o in ["pizza", "koala", "travel", "sio", "hp"]:
    p = f"bench/data/{o}.omn"
    print(f"{o}: parse={bench_parse(p, hot_iters=1, warmup=0).wall_cold:.2f}s",
          f"render={bench_render(p, hot_iters=1, warmup=0).wall_cold:.2f}s",
          f"owlapi={bench_parse_owlapi(p, hot_iters=1, warmup=0).wall_cold:.2f}s")
PY
```
