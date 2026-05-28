# pymos — Manchester OWL Syntax → owlready2 + class-relation SPARQL

**Date:** 2026-05-27
**Status:** Approved — ready for implementation planning

## 1. Problem & goal

Python projects have no native, Java-free way to parse **Manchester OWL syntax**.
The existing options each fall short:

- **owlready2** loads RDF/XML, OWL/XML, NTriples — but *not* Manchester.
- **owlapy** has a pure-Python Manchester *expression* parser (`parsimonious` PEG) and
  an OWL→SPARQL converter, but: (a) its converter generates **instance/membership**
  queries (`?x rdf:type …`), not class-hierarchy retrieval; (b) it parses class
  *expressions* only, not full Manchester documents; (c) the `owlapy` package is a
  **hard** Java dependency (`JPype1`, ships `.jar` files) plus a large ML/web stack.
- **horned-owl / horned-manchester** (Rust) are Java-free but require native builds;
  `horned-manchester` also targets an incompatible `horned-owl 0.14` and is unreleased.
- **pyoxigraph** is RDF/SPARQL (triples) only, by deliberate scope — it cannot ingest
  OWL structural syntaxes directly.

**pymos** fills the gap with a **pure-Python, Java-free** package that:

1. Parses Manchester OWL syntax (expressions *and* full document frames) into the
   **owlready2** object model.
2. Converts a class (named, or a parsed expression) into a **store-agnostic
   `CONSTRUCT` SPARQL query** that retrieves the full RDF subgraph of its related
   classes — (transitive) super/subclasses, **direct** super/subclasses, equivalent
   classes — and its **individuals** (instances), **including the blank-node structure
   of any anonymous class expressions**.

3. **Renders** an owlready2 ontology (or class expression) back to a Manchester OWL
   document/string — full round-trip with the parser, preserving prefix declarations,
   frames, and operator precedence.

### Non-goals (YAGNI)

- Reasoning / entailment. pymos queries **asserted** RDF only; no inference. Inferred
  sub/super/equivalent is the caller's reasoner's job.
- Reimplementing RDF/Turtle/OWL-XML parsing — owlready2/rdflib/pyoxigraph already do that.

## 2. Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Language / runtime | Pure-Python, **no Java**, no native build |
| Parser source | **Vendor** owlapy's MIT `parsimonious` PEG grammar (with attribution), retarget visitor to owlready2 |
| Output model | **owlready2** class-expression / axiom objects |
| Query form | **`CONSTRUCT`** full RDF subgraph (primary); `SELECT` IRIs (secondary toggle) |
| Retrieval semantics | (all) sub / (all) super / **direct sub** / **direct super** / equivalent class **and their (nested) expressions**, plus **individuals** (instances) |
| Store coupling | **Store-agnostic** — emit portable SPARQL; thin optional runners for owlready2 / pyoxigraph / rdflib / endpoint |
| Input granularity | **Full Manchester frames** (`Class:`/`ObjectProperty:`/`Individual:`/`Datatype:` …) **and** bare class expressions |
| Rendering | **owlready2 → Manchester** for expressions and full documents; round-trip with the parser |
| Dependencies | `parsimonious`, `owlready2` (core); backends import-guarded |

## 3. Architecture & package layout

```
pymos/
  __init__.py     # public API: parse, parse_expression, class_relations_query, run_*
  grammar.py      # vendored owlapy expression PEG + ADDED frame-level productions
  parser.py       # ManchesterParser: NodeVisitor → owlready2 objects (+ frame loader)
  sparql.py       # class-relation CONSTRUCT/SELECT converter (the novel deliverable)
  render.py       # owlready2 → Manchester rendering (expressions, frames, documents)
  vocab.py        # OWL structural-predicate alphabet for blank-node subgraph walking
  store.py        # store-agnostic runners (owlready2 / pyoxigraph / rdflib / endpoint)
docs/superpowers/specs/   # this spec + plan
tests/
NOTICE          # owlapy MIT attribution (grammar + test fixtures derived from owlapy)
pyproject.toml  # parsimonious + owlready2; extras: pyoxigraph, rdflib, sparqlwrapper
```

Each module has one purpose, a small public surface, and is testable in isolation:
`grammar` (the PEG text), `parser` (text→objects), `sparql` (target→query string),
`store` (query string→RDF graph). `sparql` does **not** depend on `parser`; it accepts
an owlready2 class/expression or an IRI, so the converter is usable without parsing.

## 4. Parser (`grammar.py` + `parser.py`)

### 4.1 Expression layer (vendored)

Lift owlapy's `MANCHESTER_GRAMMAR` verbatim. It already covers, per
<https://www.w3.org/TR/owl2-manchester-syntax>:

- Boolean: `and`, `or`, `not`, parentheses (with correct precedence)
- Object restrictions: `some`, `only`, `value`, `Self`, `min`/`max`/`exactly` (qualified)
- `inverse` properties
- `{ a, b, … }` enumerations (OneOf)
- Data ranges: datatypes, `[ facet literal ⊓ … ]` facet restrictions, literal enumerations
- IRIs: full `<…>`, prefixed `pre:local`, simple `local`; typed/lang/datetime/duration literals

We rewrite **only the visitor** so each production emits owlready2 constructs:

| Manchester | owlready2 construct |
|---|---|
| `p some C` / `p only C` | `p.some(C)` / `p.only(C)` |
| `p value i` | `p.value(i)` |
| `p Self` | `p.has_self()` |
| `p min n C` / `p max n C` / `p exactly n C` | `p.min(n, C)` / `p.max(n, C)` / `p.exactly(n, C)` |
| `A and B` / `A or B` / `not A` | `A & B` / `A \| B` / `Not(A)` |
| `{ a, b }` | `OneOf([a, b])` |
| `inverse p` | `Inverse(p)` |
| `dt [ >= 5 ]` | `ConstrainedDatatype(dt, min_inclusive=5)` etc. |
| typed/lang literal | Python value / `locstr` |

### 4.2 Entity resolution against owlready2

owlready2 entities live in a `World`/ontology and must exist to be referenced. The
parser therefore operates against a target ontology and a prefix map:

```python
parse_expression(text, onto, prefixes=None) -> <owlready2 class expression>
```

- IRIs resolved via `prefixes` (and the ontology's base IRI for simple names).
- Referenced classes / properties / individuals are **auto-declared** in `onto` if
  absent. Property kind (`ObjectProperty` vs `DataProperty`) is inferred from usage
  (a data range filler / literal value ⇒ data property; otherwise object property).
- This adds prefix resolution for *entities*, which owlapy's visitor lacks
  (owlapy resolves prefixes only for datatypes).

### 4.3 Frame layer (ADDED — beyond owlapy)

Extend the grammar with the W3C Manchester **document/frame** productions on top of the
expression productions. The frame loader populates owlready2 directly:

| Frame / keyword | owlready2 effect |
|---|---|
| `Prefix: p: <iri>` , `Ontology: <iri>` , `Import: <iri>` | namespace map; `onto.imported_ontologies` |
| `Class: C` | create/get class `C` |
| `SubClassOf: E1, E2` | `C.is_a.append(parse(Ei))` |
| `EquivalentTo: E` | `C.equivalent_to.append(parse(E))` |
| `DisjointWith: D` | `AllDisjoint([C, D])` |
| `ObjectProperty: p` / `DataProperty: p` | create property; `Domain:`, `Range:`, `SubPropertyOf:`, `InverseOf:`, `Characteristics:` (Functional, InverseFunctional, Transitive, Symmetric, Asymmetric, Reflexive, Irreflexive) → owlready2 mixins / attributes |
| `Individual: i` | `Types:` → `i.is_a`; `Facts:` → property assertions; `SameAs:`/`DifferentFrom:` |
| `Datatype: d` | declare datatype |
| `Annotations: …` (any frame) | annotation assertions |

A bare class expression (no frame keyword) is parsed by `parse_expression`; a frame
document is parsed by `parse(text, onto=None)` which creates a fresh ontology if none
given and returns it populated.

## 5. SPARQL converter (`sparql.py`) — core deliverable

```python
class_relations_query(
    target,                                  # IRI str | owlready2 ThingClass | parsed expression
    relations=("super", "sub", "equiv"),     # any subset of the relation set below
    construct=True,                          # True → CONSTRUCT subgraph; False → SELECT IRIs
    prefixes=None,                           # for serialising prefixed IRIs in the query
) -> str
```

### 5.0 Relation set

Each relation name binds a `?rel` (related class) or `?ind` (individual) to `target`
(`:C`). All are **asserted-graph** patterns — no reasoning. The caller picks any subset.

| Relation | Meaning | Pattern (bind `?rel`/`?ind` to `:C`) |
|---|---|---|
| `super` | all superclasses (transitive) | `:C rdfs:subClassOf+ ?rel` |
| `sub` | all subclasses (transitive) | `?rel rdfs:subClassOf+ :C` |
| `direct_super` | **direct** superclasses (one hop, no redundancy) | `:C rdfs:subClassOf ?rel .` `FILTER NOT EXISTS { :C rdfs:subClassOf+ ?mid . ?mid rdfs:subClassOf+ ?rel . FILTER(?mid != :C && ?mid != ?rel) }` |
| `direct_sub` | **direct** subclasses (one hop, no redundancy) | `?rel rdfs:subClassOf :C .` symmetric redundancy filter |
| `equiv` | equivalent classes (both directions) | `:C owl:equivalentClass ?rel` UNION `?rel owl:equivalentClass :C` |
| `individual` | individuals / instances | `?ind rdf:type :C` |

Notes:
- The **redundancy filter** makes `direct_*` correct even when the graph also asserts
  transitive edges; for ontologies that assert only immediate edges it is a no-op.
- `super`/`sub`/`direct_*` `?rel` may be a **named class or an anonymous expression**, so
  each still gets the structural-predicate subgraph walk (§5.2).
- `individual`: the CONSTRUCT returns the membership triple plus the individual's
  one-hop asserted facts (`?ind ?p ?o`); anonymous individuals get the bnode walk too.

### 5.1 Named-class target (primary case)

For `:Pizza`, `relations=("super","sub","direct_super","direct_sub","equiv","individual")`,
`construct=True` — one `UNION` block per requested relation, each binding `?rel`/`?ind`,
followed by the shared subgraph walk:

```sparql
CONSTRUCT { ?s ?p ?o }
WHERE {
  {
        { :Pizza rdfs:subClassOf+ ?rel }                    # super (transitive)
  UNION { ?rel  rdfs:subClassOf+ :Pizza }                   # sub (transitive)
  UNION { :Pizza rdfs:subClassOf  ?rel                      # direct_super
          FILTER NOT EXISTS { :Pizza rdfs:subClassOf+ ?mid .
                              ?mid rdfs:subClassOf+ ?rel .
                              FILTER(?mid != :Pizza && ?mid != ?rel) } }
  UNION { ?rel  rdfs:subClassOf  :Pizza                     # direct_sub (symmetric filter)
          FILTER NOT EXISTS { ?rel rdfs:subClassOf+ ?mid .
                              ?mid rdfs:subClassOf+ :Pizza .
                              FILTER(?mid != :Pizza && ?mid != ?rel) } }
  UNION { :Pizza owl:equivalentClass ?rel }                 # equiv (both directions)
  UNION { ?rel  owl:equivalentClass :Pizza }
  }
  ?rel <STRUCTURAL_PATH>* ?s . ?s ?p ?o .                   # walk expression bnodes / RDF lists
}
UNION-ed with the individual block:
  { ?ind rdf:type :Pizza . ?ind <STRUCTURAL_PATH>* ?s . ?s ?p ?o . }
```

(The builder assembles only the requested relations; `individual` is projected via the
same `CONSTRUCT { ?s ?p ?o }` head so one query returns the whole result graph.)

### 5.2 The structural-predicate property path (`vocab.py`) — the key technique

`<STRUCTURAL_PATH>` is the alternation of **only** OWL structural predicates, so the walk
reconstructs nested restrictions / intersections / lists and **stops at named classes**,
never leaking into unrelated graph data:

```
owl:onProperty | owl:someValuesFrom | owl:allValuesFrom | owl:hasValue | owl:hasSelf
| owl:onClass | owl:onDataRange | owl:onDatatype | owl:withRestrictions
| owl:intersectionOf | owl:unionOf | owl:complementOf | owl:oneOf
| owl:minCardinality | owl:maxCardinality | owl:cardinality
| owl:minQualifiedCardinality | owl:maxQualifiedCardinality | owl:qualifiedCardinality
| rdf:first | rdf:rest | rdf:type | rdfs:subClassOf?      (within the bnode closure)
```

This makes "retrieve the RDF serialisation (and their expressions)" both **correct**
(full subgraph) and **bounded** (no runaway traversal).

### 5.3 Anonymous-expression target (advanced, phase 2)

When `target` is an anonymous expression (e.g. parsed `hasTopping some Cheese`), emit a
graph pattern that matches that expression's blank-node structure, bind it to `?ce`, then
attach the relation clauses to `?ce`. Implementation order: **named-class targets first**
(robust, covers the stated examples), anonymous-expression matching second.

### 5.4 SELECT mode

`construct=False` projects the related IRIs (`SELECT DISTINCT ?rel`), dropping anonymous
nodes — falls out of the same clause builder.

## 5b. Renderer (`render.py`) — owlready2 → Manchester

The mirror of the parser, closing the round-trip. Public API:

```python
render_expression(ce, prefixes=None) -> str             # one class expression
render_frame(entity, prefixes=None) -> str              # one Class/Property/Individual/Datatype frame
render(onto, prefixes=None, include_imports=True) -> str  # full document
```

**Expression rendering.** Dispatch by owlready2 type:

| owlready2 | Manchester output |
|---|---|
| `ThingClass` (named) | prefixed name (if in `prefixes`) else `<full IRI>` |
| `Restriction` `SOME`/`ONLY`/`VALUE`/`HAS_SELF` | `prop some/only/value/Self filler` |
| `Restriction` `MIN`/`MAX`/`EXACTLY` | `prop min/max/exactly n filler` |
| `And([…])` / `Or([…])` | `A and B` / `A or B`, with **parentheses around lower-precedence operands** |
| `Not(X)` | `not X` |
| `OneOf([…])` | `{ a , b , … }` |
| `Inverse(p)` | `inverse p` |
| `ConstrainedDatatype` | `dt [facet val, …]` |

**Precedence (Manchester):** `not` > restriction/cardinality > `and` > `or`. A
`_prec(ce)` helper returns the operator level; a child whose level is lower than the
parent's gets wrapped in parentheses.

**Frame rendering.** For each entity kind, emit the frame header line and one keyword
line per non-empty axiom group: Class → `SubClassOf:`/`EquivalentTo:`/`DisjointWith:`;
ObjectProperty/DataProperty → `Domain:`/`Range:`/`Characteristics:`/`SubPropertyOf:`/
`InverseOf:`; Individual → `Types:`/`Facts:`/`SameAs:`/`DifferentFrom:`; Datatype +
`Annotations:` (any frame).

**Document rendering.** Emit `Prefix:` declarations from the prefix map (preferring
short prefixed names in expression output), `Ontology:` IRI, then frames in stable
order (Datatype → AnnotationProperty → ObjectProperty → DataProperty → Class →
Individual) so output is diff-friendly and round-trip is deterministic.

**Round-trip contract.** For any ontology produced by `parse(text)`, the sequence
`render(onto) → parse → render` must be **idempotent at the second step** (string-stable).
Structural equality on the first `parse → render → parse` round-trip is also required:
same class IRIs, same axiom sets per class, same property characteristics.

## 6. Store runners (`store.py`) — store-agnostic

The converter returns a **portable SPARQL string**. Optional, import-guarded adapters run
it and return an RDF graph (rdflib `Graph` for CONSTRUCT; rows for SELECT):

- `run_owlready2(query, world)` — owlready2's engine / `world.as_rdflib_graph()`
- `run_pyoxigraph(query, store)` — `pyoxigraph.Store.query`
- `run_rdflib(query, graph)` — rdflib
- `run_endpoint(query, url)` — remote SPARQL (SPARQLWrapper / httpx)

**Dependency policy.** The core (parser + `class_relations_query`, which returns a
string) hard-depends only on `parsimonious` + `owlready2`. **Neither rdflib nor
pyoxigraph is a hard dependency** — they are optional extras, each behind an
import-guarded runner, and kept mutually independent. In particular the
owlready2 → pyoxigraph path uses owlready2's **native N-Triples** export
(`onto.save(format="ntriples")`), *not* `as_rdflib_graph()`, so loading into pyoxigraph
never pulls in rdflib. owlready2 itself ships its own SQLite quadstore and SPARQL engine
and does not require rdflib.

## 7. Testing strategy

- **Parser (expression):** table of Manchester snippets → expected owlready2 structures;
  reuse owlapy's MIT test corpus as fixtures. Cover facets, qualified cardinality,
  OneOf, prefixed + full IRIs, inverse, data ranges.
- **Parser (frames):** small Manchester documents → assert resulting owlready2 ontology
  (`is_a`, `equivalent_to`, disjointness, property characteristics, individuals).
- **Converter:** golden SPARQL-string tests for each relation
  (`super`/`sub`/`direct_super`/`direct_sub`/`equiv`/`individual`) and CONSTRUCT/SELECT.
- **End-to-end:** build a small pizza ontology in owlready2 with a multi-level class
  hierarchy and a few individuals, serialise into a store, run the generated CONSTRUCT
  per relation, and assert: transitive `super`/`sub` return the full chain; `direct_*`
  return only immediate neighbours (redundancy filter drops the transitively-implied
  ones); `individual` returns instances; anonymous superclass expressions come back as
  full restriction blank-node subgraphs. Run e2e against **both** owlready2's store
  **and** pyoxigraph to prove store-agnosticism.

## 8. Licensing / attribution

owlapy is **MIT** (© 2024 Caglar Demir). The vendored grammar and any test fixtures
derived from owlapy are reproduced under MIT with a `NOTICE` file crediting owlapy.
pymos's own license: **MIT** (matches the vendored grammar).

## 9. Resolved decisions

1. **License:** MIT.
2. **Package / import name:** `pymos` (PyPI distribution and import package).
3. **Frame coverage:** **full frame set in v1** — all frames in §4.3 (Class,
   ObjectProperty/DataProperty with Domain/Range/Characteristics/SubPropertyOf/InverseOf,
   Individual with Types/Facts/SameAs/DifferentFrom, Datatype, Annotations, Prefix/Ontology/Import).
