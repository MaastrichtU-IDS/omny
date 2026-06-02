# pymos perf snapshot — 2026-06-02 (post-PR-#45)

Host: `fsesrv-g1`, Linux-5.15.0-97-generic, Python 3.10.12, 32 CPUs.
pymos: master at `c47a6c2` (PRs #1–#45). The recent perf series
landed PRs #40 (render disjoint precompute), #41 (string-mask
vectorisation), #43 (lark microbench), #44 (render annotation
bulk-fetch), and #45 (parsimonious → lark parser swap). This doc
collects the numbers that landed across that series so the
`2026-06-01-*` docs don't need cross-reading to see the current
state.

## Headline

* **Parser swap PR #45 is the largest in-flight win on parse**:
  HP 310 s → 164 s (1.89×), sio 4.97 s → 2.79 s (1.78×).
* **Render is up to 24× faster cumulative** on HP since the
  pre-fix baseline (>600 s timeout → 25 s). Disjoint precompute and
  annotation bulk-fetch carry that win.
* **OWLAPI lead on parsing has narrowed**: pre-lark, OWLAPI was ~9×
  on HP; post-lark, OWLAPI's 30 s vs pymos's 164 s is ~5.5× — still
  the right tool for batch loads of 30 k+-class ontologies, but the
  gap is shrinking. Pymos still wins on tiny/small ontologies due to
  JVM + docker startup cost.

## 1. Parse — pymos lark vs parsimonious head-to-head

Same-shape comparison via `bench/runners/compare_parsers.py` — each
cell is a fresh subprocess running the same `pymos.parse(text)` with
either the lark backend (now default) or parsimonious (legacy).

| ontology | bytes | parsimonious (hot median) | lark (hot median) | speed-up |
|---|---:|---:|---:|---:|
| pizza   |    897 |  0.05 s | 0.02 s | **3.13×** |
| koala   |  8,952 |  0.07 s | 0.05 s | **1.42×** |
| travel  | 15,634 |  0.06 s | 0.08 s | **0.73×** |
| sio     | 756,132 | 12.13 s | 4.58 s | **2.65×** |
| hp      | 30 MB | _timeout (>1200 s in subprocess)_ | 223 s | n/a here |

For HP parsimonious, the bench harness's per-cell subprocess budget
(20 min) was insufficient on this host — fresh-subprocess parses on
HP run ~600 s per iteration whereas in-process they're ~310 s. The
PR #45 in-process measurement (275 / 345 s, mean 310 s) is the
right ceiling. With that, **HP parse 310 s → 164 s in-process = 1.89×**
or 310 s → 223 s through the bench harness shape.

Observations:

* The 5.4× microbench from PR #43 was a single complex expression;
  HP's ~100 k short axiom operands dilute the per-parse structural
  advantage with lark's contextual lexer + transformer dispatch.
* Tiny ontologies (pizza/koala/travel) show a smaller multiplier
  because cell startup (subprocess fork + Python import + Lark
  table build) dominates the workload — and travel actually
  measured 0.73× (lark slower on this 16 KB file) because Lark's
  LALR table build is now the bottleneck.
* The win grows with ontology size — sio (1.5 MB) is at 2.65×;
  HP at the same shape would be ~1.5-2× in subprocess form
  (limited by import+startup that parsimonious also pays, but
  with smaller proportional dilution).
* The takeaway: lark is the right default for the parse-many-axiom
  use case pymos is built for; parsimonious is now legacy.

## 2. Parse — pymos lark vs OWLAPI

The cross-over from `docs/perf-2026-06-01-expanded.md`, updated for
the post-lark parse numbers. OWLAPI's wall is unchanged (no new
OWLAPI runs in this round).

| ontology | axioms / classes | pymos.parse (lark) | OWLAPI (ROBOT wall) | pymos / OWLAPI |
|---|---|---:|---:|---:|
| pizza   | 10 axioms     |  **0.02 s**  |  5.30 s | **265× pymos** |
| koala   | 33 axioms     |  **0.05 s**  |  5.66 s | **113× pymos** |
| travel  | 57 axioms     |  **0.08 s**  |  5.14 s | **64× pymos**  |
| sio     | 2 106 axioms (1 585 classes) | **2.79 s** | 8.03 s | **2.9× pymos** |
| hp      | 32 092 classes | **164 s**  | **29.92 s** | **~5.5× OWLAPI** |

Cross-over point hasn't moved (still around the sio scale) but
post-lark pymos extends its lead on small ontologies and narrows
OWLAPI's on large ones.

## 3. Render — cumulative wins (PRs #40, #41, #44)

Pre-PR-#40 baseline → current master. See `docs/perf-2026-06-01-fixes.md`
for the per-PR breakdown.

| ontology | render before | render after | speed-up |
|---|---:|---:|---:|
| pizza  |  0.26 s |  0.26 s |  ~1× |
| koala  |  0.48 s |  0.48 s |  ~1× |
| travel |  0.54 s |  0.54 s |  ~1× |
| sio    | 16.09 s |  0.82 s | **19.6×** |
| hp     | > 600 s (timeout) | **25.3 s** | **>24×** |

Render is now in the same order of magnitude as parse for sio and
HP (was 2-5× slower than parse pre-fixes; now ~1.5× slower).

## 4. What changed since 2026-06-01

| date | PR | what shipped | win |
|---|---|---|---|
| 2026-06-01 | #40 | render disjoint precompute        | sio render 13.8× |
| 2026-06-01 | #41 | `_build_string_mask` vectorisation | parse 8% on HP   |
| 2026-06-01 | #43 | lark microbench                    | exploration only |
| 2026-06-01 | #44 | render annotation bulk-fetch        | HP render 4.9×   |
| 2026-06-02 | #45 | parsimonious → lark parser          | HP parse 1.89×   |
| 2026-06-02 | #46 | bench harness polish (this doc)     | n/a — observability |
| 2026-06-02 | #47 | `_split_commas` vectorisation        | HP parse 1.09×   |
| 2026-06-02 | #48 | doc: extend-batching negative result | n/a — record     |
| 2026-06-02 | #49 | direct-write SubClassOf (named parents) | HP parse+render 1.21-1.31× |
| 2026-06-02 | #50 | `unescape_quoted_string` vectorise   | HP parse 1.05×   |

## 5. Open levers (unchanged from `2026-06-01-fixes.md`)

* **owlready2 `_class_is_a_changed` batching** (~11 % of HP parse
  wall, but on the pre-lark profile — likely a larger share of the
  post-lark wall since the parser's slice shrank). Requires touching
  owlready2 internals; fragile.
* **Parser python_name collapse**: pymos's frame parser collides
  alias-shared annotation predicates at parse time. Render now
  disagrees with parse on these — see PR #44's regression test.
* **Re-profile HP parse post-lark** (`bench/profiles/parse_hp_lark.prof`,
  run 2026-06-02 with cProfile overhead = 188 s wall). Top items
  by cumulative time:

  | rank | function | cumtime | share |
  |---|---|---:|---:|
  | 1 | `owlready2/util.py:append` (via `is_a.append`) | 68.7 s | **37 %** |
  | 2 | `owlready2/entity.py:_class_is_a_changed` callback | 50.7 s | **27 %** |
  | 3 | `pymos/_lark_parser.py:parse_expression` | 46.4 s | **25 %** |
  | 4 | `pymos/frames.py:_apply_annotations` | 38.0 s | 20 % |
  | 5 | `pymos/frames.py:_split_commas` | 24.6 s | **13 %** |

  The pre-lark profile had parsimonious at 48 %; post-lark, lark
  itself is at 25 % and the owlready2 callback chain
  (`append` + `_class_is_a_changed`) totals ~64 %.

  One of those candidates landed:

  * **`_split_commas` vectorisation (PR #47)**. Per-frame comma-split
    rewritten to use the existing `_build_string_mask` helper and
    slice the segments out in one batch rather than accumulate a
    `buf += ch` per character. Microbench on real HP annotation rows:
    1.6-3.8× per call. Same-host HP parse control: **123.5 s → 113.0 s
    (1.09×)** — real but smaller than the 13 % function share suggested
    (most of the savings get re-absorbed by the owlready2 callback
    chain that dominates the remaining wall).
  * **owlready2 `_class_is_a_changed` batching** still the largest
    documented lever: now demonstrably 27 % of wall (was 11 % on the
    pre-lark profile). Requires owlready2-internals work.

    Attempted 2026-06-02 (pymos-level) via `is_a.extend(parents)` in
    place of per-item `is_a.append(parent)` — owlready2 fires
    `_class_is_a_changed` once per `extend` instead of once per
    item, so 56 k callback fires would drop to 32 k.  Microbench
    on freshly-created classes looked promising (1.1× at k=2,
    4.3× at k=10), but the same-host HP control showed a
    **1.6× regression** (113 s → 185 s) — confirmed across 2 runs
    each side.  The per-call extend overhead in owlready2's
    CallbackList is heavier than expected on the dominant
    real-world case (k=1 single-parent SubClassOf, ~55 % of HP
    classes), enough to overwhelm the savings from batching the
    minority k≥3 cases.  Approach abandoned; see PR #48.

    **Solved in PR #49** by a different angle: direct-write
    `(cls, rdfs:subClassOf, parent)` triples via
    `o.graph._add_obj_triple_raw_spo` for **named-class** parents,
    skipping owlready2's CallbackList entirely, and invalidate the
    Python cache for those classes at end-of-parse so the next
    `world[iri]` rebuilds `is_a` from triples in one callback fire
    per class instead of one per axiom.  Anonymous restrictions still
    go through the per-item `_safe_append_is_a` path (they have no
    storid and need the Python construct chain).  Same-host HP
    parse+render control: **135.7 s → 103.5 s = 1.31×** (POC) or
    **112 s on the real branch = 1.21×** across separate runs; the
    range is honest day-to-day variance on this host.

## Reproduction

```bash
# Lark vs parsimonious head-to-head:
.venv/bin/python -m bench.runners.compare_parsers \
    --ontologies pizza,koala,travel,sio,hp \
    --hot-iters 2 --per-cell-timeout 900 \
    --out bench/results/$(date +%F)-parsers

# Full snapshot (parse + render + query + reasoning):
.venv/bin/python -m bench.runners.snapshot \
    --tier tiny,small --hot-iters 3
```

## Files referenced

* `bench/runners/compare_parsers.py` — head-to-head runner introduced in PR #46.
* `bench/runners/snapshot.py` — full perf snapshot.
* `bench/experiments/lark_microbench.py` — single-expression
  parser-internal benchmark (historical exploration).
* `pymos/_lark_parser.py` — the production parser, since PR #45.
* `pymos/parser.py` — legacy parsimonious backend, kept importable.
