# Perf fixes — 2026-06-01 (post-profile-driven optimisation)

Host: `fsesrv-g1`, Linux-5.15.0-97-generic, Python 3.10.12, 32 CPUs.
pymos: master at `342e3b9` (PRs #40, #41 — the two profile-driven
optimisations described here).
Profiles: `bench/profiles/parse_hp.prof`, `bench/profiles/render_sio.prof`.

This file extends `docs/perf-2026-06-01-pymos-bench.md` (baseline) and
`docs/perf-2026-06-01-expanded.md` (HP/medium-tier) with the
**before/after numbers from a profile-driven round of optimisations**.

## What we profiled

cProfile on two cells from the perf snapshot picked by Pareto:

* `pymos.parse(hp.omn)` — pymos's slowest workload in absolute terms
  (~270 s standalone).
* `pymos.render(sio.omn)` — slowest workload as a ratio of its parse
  (sio render 39 s vs sio parse 16 s; HP render had timed out at 600 s).

## Hotspots found

| function | % of total wall | call count | character |
|---|---:|---:|---|
| **render:** `_find_disjoint_partners` | **80 %** of render(sio) | 1 585 (once per class) | per-class `O(disjoint_groups)` scan — algorithmic O(N²) |
| `parsimonious._uncached_match` (all matchers) | ~48 % of parse(HP) | 44 M / 5 M / 7.9 M | the parser itself |
| owlready2 `_class_is_a_changed` | 11 % of parse(HP) | 56 k | one callback per `is_a.append` (we can't easily batch) |
| **parse:** `_build_string_mask` | 8 % of parse(HP) | **32 460** (one per frame!) | pure-Python char loop |
| `_apply_annotations` | 8 % | 32 k | annotation walks |
| `_split_commas` | 5 % | 138 k | string scan |

Two of these were Pareto wins that didn't need a Tier 2/3
intervention: the disjoint-partner O(N²) and the per-frame mask
rebuild. The parsimonious 48 % is the next ceiling — addressing it is
a deliberate `lark` (or custom-parser) swap, not a micro-fix.

## Fix 1 — render disjoint-partner precompute (PR #40)

Build a `{class_iri: [partners]}` map **once** at the top of `render()`,
pass it through a private `_disjoint_map` kwarg on `render_frame`. The
existing per-class scan stays as a fallback for standalone
`render_frame` callers.

| ontology | render before | render after | speed-up |
|---|---:|---:|---:|
| pizza  |   0.26 s |    0.26 s |  ~1× (already negligible) |
| koala  |   0.48 s |    0.48 s |  ~1× |
| travel |   0.54 s |    0.54 s |  ~1× |
| **sio** | **16.09 s** | **1.16 s** | **13.8×** |
| **hp**  | **> 600 s (timeout)** | **123.6 s** | **>5×** (now feasible at all) |

The win scales with the number of `AllDisjoint` axioms — sio (~140
groups) and HP (~7 k groups) are where the old code spent most of
its time. Tiny ontologies have so few groups that the old scan was
already negligible.

## Fix 2 — `_build_string_mask` vectorisation (PR #41)

Replace the per-character Python loop with a single `re.finditer(r'"(?:[^"\\]|\\.)*"')`
and a bulk `mask[s:e] = b'\x01' * (e-s)` slice-assign.

| measurement | before | after | speed-up |
|---|---:|---:|---:|
| Single `_build_string_mask` on 30 MB hp.omn | unmeasured in profile (called 32 k times for 42 s total) | 1.4 s | n/a |
| Per-frame call (~600-byte body) | 1.3 ms | ~10 µs | **~130×** |
| `_build_string_mask` share of total parse wall (HP) | 8 % | not in top-20 hot functions | — |

End-to-end HP parse wall is now dominated by parsimonious + host
variance. Run-to-run variance (~25 % on this host) hides the absolute
gain, but the function is no longer a hot spot.

## Fix 3 — render annotations bulk-fetch (PR #44)

After the disjoint precompute landed, re-profiling HP render found
`_annotations_line` was **97 % of total wall (171 s of 176 s with
cProfile)** — 9 M ``getattr`` calls, one per (entity × annotation
property) pair, almost all returning ``None``.

The fix mirrors PR #40: precompute a
``{entity_iri: ["ap_name value", …]}`` map once at the top of
``render()`` via one ``rdflib.Graph.triples((None, ap, None))``
scan per annotation property, thread it through ``render_frame``
as a private ``_annotation_map`` kwarg.

| ontology | render before | render after | speed-up |
|---|---:|---:|---:|
| pizza/koala/travel | ~0.3-0.5 s | ~0.3-0.5 s | ~1× (already negligible) |
| **sio** | 1.16 s | 0.82 s | ~1.4× |
| **hp**  | **123.6 s** | **25.3 s** | **4.9×** |

The render now also fixes a latent correctness issue on real ontologies:
when two annotation properties share an owlready2 ``python_name`` (e.g.
``rdfs:comment`` and ``schema:comment`` both map to ``.comment``), the
old per-entity ``getattr`` path **double-counted** — emitting one
asserted triple as both ``rdfs:comment "X"`` and ``schema:comment "X"``.
And it **missed** some triples that owlready2's attribute layer didn't
surface (e.g. ``sio:subset`` on SIO_000001 is materialized in the
triple store but ``entity.subset`` returns ``[]``).

The bulk path walks the rdflib graph directly, so each rendered pair
corresponds to exactly one asserted triple — confirmed via:

```
parse(sio)                          → 7480 annotation triples
parse(render(parse(sio)))           → 7480 annotation triples
diff                                → 0 missing, 0 added
```

`tests/test_render.py::test_render_annotation_aliased_python_names_no_duplicate`
is the regression guard.

## What we *didn't* do

Stayed within the profile-driven Pareto for this round; everything
below is documented as a future option, not yet attempted:

* **parsimonious → lark swap** (Tier 2 in the original lever list).
  Would target the 48 % of parse wall that is parser-internal. Real
  work — needs grammar port + corpus re-validation. Expected gain:
  10-30× on parse based on published lark vs parsimonious
  benchmarks; the pymos visitor would also need a rewrite.
* **owlready2 `_class_is_a_changed` batching.** 11 % of parse wall on
  HP. Each `is_a.append` triggers a full `__bases__` recomputation;
  batching multiple appends per class before commit would halve this
  in principle. Implementation requires touching owlready2 internals —
  fragile.
* **Parser python_name collapse.** Pymos's parser also collides
  alias-shared annotation predicates (predicates with the same
  ``python_name`` get unified at parse time, losing the original IRI).
  Render now disagrees with parse on these — the renderer is faithful
  to the triple store, but parse drops the source predicate identity.
  Separate, deeper fix; see the regression test for the shape.

## Profiles on disk

```
bench/profiles/parse_hp.prof          # before — 517 s with cProfile overhead, 270 s wall
bench/profiles/render_sio.prof        # before — 16 s
bench/profiles/parse_hp_after.prof    # after Fix 2 (profile took >600s; not committed)
```

To re-profile after future changes:

```bash
.venv/bin/python -c "
import warnings, cProfile, pymos
warnings.simplefilter('ignore')
text = open('bench/data/hp.omn').read()
cProfile.run('pymos.parse(text)', 'bench/profiles/parse_hp_NEW.prof')"
.venv/bin/python -c "
import pstats
p = pstats.Stats('bench/profiles/parse_hp_NEW.prof')
p.sort_stats('cumulative').print_stats(25)"
```
