# pymos perf series — session summary (2026-06-01 → 2026-06-02)

Host: `fsesrv-g1`, Linux-5.15.0-97-generic, Python 3.10.12, 32 CPUs.
pymos: master at `28e8f3f` (PRs #40-50).

This doc closes the 2026-06-01/02 perf series. Headline: **HP
parse+render ~7.2× cumulative** (>900 s → ~125 s); the remaining wall
is dominated by code pymos doesn't own (lark internals + owlready2's
sqlite execute), and the next factor would need either an owlready2
patch upstream or a non-Python parser — out of scope for in-repo work.

If you're looking for the per-PR details, the chronological table at
the end has links. If you're picking up where this series left off,
read the "Where we stopped" section.

## Headline (HP, the worst case in the corpus)

| state | parse | render | parse+render |
|---|---:|---:|---:|
| Session start (pre-PR-#40) | ~310 s | > 600 s (timeout) | > 900 s |
| Current master (post-PR-#50) | ~100 s | ~25 s | **~125 s (sum)** |
| Cumulative speed-up | **~3.1×** | **> 24×** | **~7.2×** |

The "125 s" parse+render is the sum of the parse-alone and render-alone
measurements, mirroring the "> 900 s" pre-fix figure for apples-to-apples
comparison. A back-to-back `pymos.parse(text); pymos.render(onto)` in
the same process benefits from shared warm state and measures **~100 s**
end-to-end on this host (PR #49 same-host control: 103.5 s).

* sio parse+render: ~33 s → ~4 s (~8×).
* Tiny ontologies (pizza, koala, travel): already fast pre-series,
  unchanged (~0.5 s each end-to-end).

## What landed

| # | PR | what shipped | win on HP |
|---:|---:|---|---|
| 1 | #40 | render: precompute `{class.iri: [disjoint_partners]}` once at top of `render()`; threaded through `render_frame` via private `_disjoint_map` kwarg | sio render 16 s → 1.16 s = **13.8×**; HP render: timeout → 123.6 s = unblocked |
| 2 | #41 | parse: `_build_string_mask` re.finditer + slice-assign instead of per-char Python loop | per-call ~130×, ~8 % of HP parse wall freed |
| 3 | #43 | bench: lark vs parsimonious microbench (exploration) | n/a — informs PR #45 |
| 4 | #44 | render: bulk `rdflib.triples((None, ap, None))` scan per annotation property + precomputed `{entity.iri: ["ap_name value", …]}` map; threaded through `render_frame` via private `_annotation_map` kwarg | HP render 123.6 s → 25.3 s = **4.9×**; corrects latent over/under-report on alias-shared annotation properties |
| 5 | #45 | parse: replace parsimonious with lark LALR; module-level `Lark(parser="lalr")` instance + cached `Transformer`; unified obj/data restriction grammar dispatched at transform time | sio parse 5 s → 2.8 s = **1.78×**; HP 310 s → 164 s = **1.89×** |
| 6 | #46 | bench: `compare_parsers.py` runner (head-to-head lark vs parsimonious); fresh perf snapshot | n/a — observability |
| 7 | #47 | parse: `_split_commas` mask-based (reuse `_build_string_mask`) + slice-segment-out instead of `buf += ch` per char | HP parse **1.09×** (~10 s saved) |
| 8 | #48 | docs only: extend-batching negative result | n/a — recorded |
| 9 | #49 | parse: direct-write `(cls, rdfs:subClassOf, parent)` triples for named-class parents via `o.graph._add_obj_triple_raw_spo`; invalidate Python cache at end-of-parse so first `world[iri]` lookup rebuilds `is_a` in one callback fire per class | HP parse+render 135.7 s → 103.5-112 s = **1.21-1.31×** |
| 10 | #50 | parse: `unescape_quoted_string` regex (fast path: `if "\\" not in raw: return raw`) | HP parse **1.05×** |

Two of those (#43 microbench, #48 negative result) are essentially
documentation — kept in the history so the next person to look at
this doesn't re-run the same experiment.

## What didn't work

PR #48 (extend-batching, never shipped as code). Microbench predicted
batched `is_a.extend([…])` would cut `_class_is_a_changed` fires from
56 k to 32 k on HP; same-host control showed a **1.6× regression**
(113 s → 185 s) because owlready2's `CallbackList.extend` has
per-call overhead that beats the savings on the dominant k=1 case
(~55 % of HP classes have one parent). PR #49 won the lever with
a different approach — direct-write triples + lazy reload — because
that path skips the CallbackList entirely.

Annotation direct-write POC (never shipped). Same direct-write
pattern applied to `_apply_annotations`: same-host control measured
~1 % win on parse+render with a 335-byte render output drift.
Investigation showed `_apply_annotations`'s 29 % cumtime was
dominated by **unavoidable sqlite execute** (the triple write
happens either way), not the CallbackList overhead the POC bypassed.

## Where the wall went

cProfile of HP parse post-PR-#49 (`bench/profiles/parse_hp_pr49.prof`)
sorted by tottime (the actual per-function CPU cost rather than
rolled-up cumulative). PR #50 (`unescape_quoted_string` vectorisation)
shaved ~5 % off the wall but isn't large enough to reshuffle this
table — `unescape_quoted_string` would drop a few positions, the rest
hold relative rank:

| function | tottime | share | who owns it |
|---|---:|---:|---|
| `sqlite3.Connection.execute` | 18.8 s | **14 %** | owlready2 / sqlite |
| `pymos/frames.py:_split_commas` | 10.4 s | 8 % | pymos (already vectorised in PR #47; further win marginal) |
| `lark/parsers/lalr_parser_state.py:feed_token` | 7.2 s | 5 % | lark |
| `pymos/_frame_tokeniser.py:_build_string_mask` | 5.2 s | 4 % | pymos (already C-level re.finditer; no further win) |
| `owlready2/prop.py:_callback` | 2.7 s | 2 % | owlready2 |
| `lark/lexer.py:next_token` | 2.1 s | 2 % | lark |
| _other lark internals_ | ~8 s | ~6 % | lark |
| _other owlready2_ | ~10 s | ~7 % | owlready2 |

**The dominant costs are now non-pymos code**: sqlite execute (~15 %),
lark internals (~13-15 %), owlready2 entity & callback machinery
(~10 %). The pymos-side hot spots that remain — `_split_commas`,
`_build_string_mask` — have already been vectorised; further wins
would need a different algorithm, not a different microoptimisation.

## Where we stopped

The remaining levers are all structurally large and outside the
"safe, profile-driven micro-fix" mode this series was run in:

1. **owlready2 `is_a` no-callback bulk-set API.** Would replace
   PR #49's direct-write + invalidate pattern with a single
   `cls.is_a.bulk_set(...)` call that skips the per-axiom callback
   entirely *and* keeps the Python cache in sync. ~22 s savings
   estimated; needs an upstream owlready2 patch.

2. **Non-Python parser.** Lark internals are 17 %+ of HP parse wall.
   A C-extension parser (or running lark in PyPy) would give another
   5-10 s. Major investment for marginal win.

3. **Parser python_name collapse fix.** Correctness, not perf.
   pymos's frame parser collides alias-shared annotation predicates
   (e.g. `rdfs:comment` + `schema:comment` → `.comment`). Render is
   now faithful (PR #44); parse drops predicate identity. Separate,
   deeper fix; see `test_render_annotation_aliased_python_names_no_duplicate`
   for the shape.

4. **Direct-write + invalidate for individuals' Types.**
   The lever from PR #49 applied to `_handle_individual`. Small win
   on individual-heavy ontologies (OBI, SIO patterns); negligible on
   HP. Mechanically straightforward — same helper, same dirty set —
   if a future use case justifies it. **Good first contribution**:
   PR #49 is the template; copy the `_direct_write_subclassof`
   pattern, point it at `rdf:type` instead of `rdfs:subClassOf`,
   thread through `_handle_individual` for Types operands that
   resolve to a named class.

## How to read the per-PR docs

* `docs/perf-2026-06-01-pymos-bench.md` — baseline + method notes +
  rcelebi/owlready2 fork comparison.
* `docs/perf-2026-06-01-expanded.md` — HP/medium-tier added; documents
  the OWLAPI cross-over.
* `docs/perf-2026-06-01-fixes.md` — per-PR profile-driven fix
  rationale for PRs #40/#41/#44.
* `docs/perf-2026-06-02-pymos-bench.md` — post-lark snapshot with
  head-to-head numbers + cProfile of HP post-lark.
* `bench/profiles/*.prof` — saved cProfile snapshots at each
  milestone; `pstats` over each to see the wall reshuffle.

## Methodology notes (for whoever picks this up next)

1. **Always run a same-host control before shipping.** Microbench can
   show 4× per-call and HP can regress 1.6× because of load-dependent
   behaviour the microbench doesn't capture. PRs #48 (extend) and
   the annotation POC are the cautionary tales.

2. **Run alternating cycles when measuring small wins.** Warm-cache
   effects between runs are big enough to swamp 5-10 % wins. PR #50
   used 3 cycles of NEW/OLD/NEW/OLD/… and took medians; without that,
   the first-run-vs-second-run ordering bias would have inverted the
   conclusion.

3. **Cumtime tells you *where* time is spent; tottime tells you what's
   *cheap to optimise*.** The annotation POC failed because the
   29 % cumtime in `_apply_annotations` was mostly unavoidable sqlite
   tottime, not pymos-replaceable Python overhead. Read tottime
   before writing optimisation code.

4. **The bench harness's `bench_parse` subprocess shape doesn't match
   in-process numbers.** Fresh-subprocess imports add overhead that
   distort small-ontology comparisons; HP parsimonious times out
   inside the harness's 20 min subprocess cap but completes in 5 min
   in-process. Report which mode you measured.
