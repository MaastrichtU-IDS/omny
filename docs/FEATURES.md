# pymos — full feature reference

For the gentle introduction, see the [README](../README.md).
This page is the *exhaustive* inventory: which Manchester constructs the
parser handles, which guarantees the renderer makes, every SPARQL relation,
every backend runner, every Jupyter magic.

---

## Parser — full Manchester documents → owlready2

- Every standard frame: `Class`, `ObjectProperty`, `DataProperty`,
  `Individual`, `Datatype`, `AnnotationProperty`, plus document-level
  `EquivalentClasses` / `DisjointClasses` / `SameIndividual` / `DifferentIndividuals` /
  `EquivalentProperties` / `DisjointProperties`.
- Every standard axiom keyword: `SubClassOf`, `EquivalentTo`, `DisjointWith`,
  `Domain`, `Range`, `Characteristics`, `SubPropertyOf`, `InverseOf`,
  `Types`, `Facts`, `SameAs`, `DifferentFrom`, `Annotations`, `HasKey`.
- All class-expression constructs: `and` / `or` / `not`, `some` / `only` /
  `value` / `Self`, `min` / `max` / `exactly` (qualified cardinality),
  `OneOf` (`{a, b}`), `inverse p`, `ConstrainedDatatype` facets
  (`xsd:integer[>= 0, <= 100]`).
- Header: `Prefix`, `Ontology`, `Import` (recorded as `owl:imports`, not fetched).
- String-aware tokeniser: commas and `Keyword:`-like tokens inside quoted
  annotation literals don't split frames or sections.
- `\"` and `\\` escapes inside string literals are honoured (lossless
  round-trip with the renderer).
- Returns a real `owlready2.Ontology` — the full owlready2 Python API
  (class hierarchy, axioms, instances, characteristics) applies; pymos
  adds no separate object model of its own.

## Renderer — owlready2 → Manchester, round-trip stable

- `render(onto)` — full document; `render_frame(entity)` — one entity;
  `render_expression(ce)` — one class expression.
- Operator-precedence aware (`A and B or C` round-trips correctly).
- Properly escapes `"` and `\` per the W3C grammar.
- Idempotent from the second render onward — `r2 == r3` for arbitrary input.
- Faithful to property characteristics (`Functional`, `Transitive`, …),
  inverse properties, sub-property hierarchies, annotation properties
  (IRI-keyed, so same-local-name properties stay distinct), individuals'
  `Types` / `Facts` / `SameAs` / `DifferentFrom`, and datatypes.

## SPARQL — class-relation retrieval, store-agnostic

- Six relations: `super` / `sub` (transitive `rdfs:subClassOf+`),
  `direct_super` / `direct_sub` (immediate, with redundancy filter),
  `equiv` (both directions), `individual` (`rdf:type` instances).
- `CONSTRUCT` mode returns the full RDF subgraph of related classes —
  **including the blank-node structure of anonymous class expressions**
  (restrictions, intersections, RDF lists).
- `SELECT` mode returns related IRIs only (anonymous nodes filtered out).
- Target can be a full IRI, a prefixed name, an owlready2 entity, or a
  parsed anonymous class expression — any of those produce portable SPARQL.

## Runners — pick a backend, no hard dependency

- `run_rdflib(q, graph)` — rdflib `Graph` (CONSTRUCT → `Graph`; SELECT → rows).
- `run_pyoxigraph(q, store)` — pyoxigraph `Store` (sanitises owlready2's
  N-Triples export at the bridge so strict pyoxigraph accepts it).
- `run_owlready2(q, world)` — owlready2's native engine (SELECT-only;
  raises clearly on CONSTRUCT with guidance).
- `run_endpoint(q, url)` — remote SPARQL endpoint via SPARQLWrapper;
  Turtle for CONSTRUCT, JSON for SELECT.
- Each runner imports its backend lazily — pymos itself depends only on
  `parsimonious` + `owlready2`.

## Jupyter — interactive MOS authoring (optional)

- `%load_ext pymos.jupyter` enables:
  `%%mos` (parse a cell as Manchester and merge into the active ontology),
  `%%mos_query <relation>` (run a class-relation SPARQL),
  `%reason [pellet]` (materialise inferences via owlready2's reasoner bridge),
  `%mos_show <Name>` (render one entity), `%mos_save <path>` (render whole onto).
- Tab-completion is context-aware (frame keywords, axiom keywords,
  property characteristics, classes/properties/individuals already in scope).

## Quality / packaging

- **201 tests** (parser, frames, renderer, SPARQL, store, e2e) on
  Python 3.10 + 3.12, CI-enforced; **37 bench tests** for the perf harness.
- Pure Python, no native build step; only required runtime deps are
  `parsimonious` and `owlready2`.
- MIT-licensed.  Grammar is vendored from
  [owlapy](https://github.com/dice-group/owlapy) (MIT) — see `NOTICE` for the
  one intentional divergence (W3C-conformant `,` facet separator).
- Asserted-graph only — no reasoner is invoked unless you call one
  explicitly (`%reason` / `owlrl` / HermiT via `sync_reasoner_hermit()`).
