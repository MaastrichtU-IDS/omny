# Anonymous-Expression Targets for `class_relations_query` — Design

**Date:** 2026-05-28
**Status:** Approved

## Goal

Allow `pymos.class_relations_query` to accept an **anonymous Manchester OWL class
expression** as its `target` (in addition to the existing named-IRI / SPARQL
variable / owlready2 entity inputs). The resulting query retrieves classes that
relate to that anonymous expression as defined by the asserted graph — most
usefully, the named class that is `owl:equivalentClass` to it.

Closes the gap explicitly flagged by [pymos/sparql.py:93-94](../../pymos/sparql.py)
("Anonymous-expression targets are not supported; target must resolve to a named
IRI or SPARQL variable").

## Approach

**Structural match.** Anonymous expressions live in the asserted graph as standard
OWL blank-node structures (`owl:Restriction`, `owl:intersectionOf`,
`owl:unionOf`, `owl:complementOf`, `owl:oneOf`). The builder takes an owlready2
construct, walks it, and emits SPARQL triple patterns that bind a fresh variable
(`?target`) to any blank node whose outgoing structure matches the construct.
That bound variable then substitutes for the named IRI in the existing relation
clauses.

This stays faithful to pymos's "asserted graph only, no reasoning" posture.

**Skolemization (rejected):** assigning a synthetic IRI to the anonymous node
would either mutate the data graph (intrusive, lossy) or require a side-table the
SPARQL engine cannot see.

## API

`class_relations_query` accepts an owlready2 construct as `target`:

```python
expr = pymos.parse_expression("Drug and (treats some BacterialInfection)", onto)
q = class_relations_query(expr, relations=("equiv",))
rows = run_rdflib(q, onto.world.as_rdflib_graph())   # → finds Antibiotic
```

CONSTRUCT mode still works; the returned subgraph contains the outgoing structure
of the related class (which is what links it to the anonymous expression).

`_target_iri` is renamed `_target_term`. When `target` is an owlready2 construct
without an `.iri` attribute (anonymous), it dispatches to a new module
`pymos/pattern.py` and returns a structural pattern plus the bound variable
`?target`. The query assembler prepends that structural pattern inside the WHERE
block so `?target` is bound before each relation clause uses it.

## Components

| File | Responsibility |
|------|----------------|
| `pymos/pattern.py` (new) | One public function `expression_to_pattern(expr) -> (pattern_str, var_str)` that walks an owlready2 construct and emits SPARQL triple patterns binding a fresh variable to any matching blank node. Recursive for nested anonymous operands. |
| `pymos/sparql.py` (edit) | Rename `_target_iri` → `_target_term`; branch on anonymous construct → call `expression_to_pattern`; prepend the structural pattern inside the WHERE assembly. |
| `tests/test_pattern.py` (new) | Unit tests for each construct kind. |
| `tests/test_sparql.py` (edit) | Assert generated SPARQL for anonymous targets contains the expected structural pattern and binds `?target` correctly. |
| `tests/test_e2e.py` (edit) | End-to-end: parse an anonymous expression that matches a definition in `tests/data/pizza.omn`, run via each store runner, assert the named class is returned. |

## Scope of supported constructs

Initial support covers everything pymos already parses:

- Restrictions: `R some C`, `R only C`, `R value v`, `R Self`
- Cardinality: `R min N`, `R max N`, `R exactly N`, qualified variants `R min N C` etc.
- Conjunction: `A and B [and …]` → `owl:intersectionOf` with `rdf:List`
- Disjunction: `A or B [or …]` → `owl:unionOf` with `rdf:List`
- Negation: `not A` → `owl:complementOf`
- Enumeration: `{a, b, …}` → `owl:oneOf` with `rdf:List`
- Inverse-property restrictions (the inverse property is itself a blank node with
  `owl:inverseOf`)
- Arbitrary nesting — any operand may itself be anonymous; the walker recurses.

## Out of scope (documented limitations)

- **Operand order is matched as declared.** Two semantically equivalent expressions
  with permuted intersection/union operands do not match each other. Adding
  permutation tolerance requires N! patterns or post-SPARQL filtering and is left
  as a future enhancement.
- **No reasoning.** Structural identity only; equivalent but structurally distinct
  expressions (e.g. `A and B` vs a class equivalent to that conjunction defined
  elsewhere) do not match.
- **Data ranges / `ConstrainedDatatype`** as a *target* is deferred. (They remain
  supported as restriction fillers nested inside object restrictions.)

## Relation semantics with an anonymous target

All six relations remain mechanically valid, but their practical utility differs:

| Relation | With an anonymous target |
|----------|-------------------------|
| `equiv`        | **Primary use case** — find named classes whose definition matches the expression. |
| `super` / `direct_super` | Find classes the anonymous expression is asserted under (rare in practice). |
| `sub` / `direct_sub`     | Mechanically supported; rarely meaningful — OWL ontologies do not usually assert subclasses *of* an anonymous node. |
| `individual` | Mechanically supported; rarely meaningful for the same reason. |

The library does not restrict relations by target kind; documentation makes the
practical guidance explicit.

## Error handling

- Construct types outside the supported scope (e.g. `ConstrainedDatatype` as a
  top-level target) raise `ValueError("anonymous target of type X is not
  supported")` with the offending Python type.
- A `target` that is none of {string, variable, IRI, owlready2 entity, owlready2
  construct} raises `TypeError`.
- No silent fallback — invalid inputs fail loudly.

## Testing

- **`tests/test_pattern.py`** — exhaustive unit tests for `expression_to_pattern`:
  one named class; each restriction kind; each cardinality kind; intersection;
  union; complement; oneOf; nested combinations; inverse-property restriction.
  Each test asserts on the emitted pattern string (or its triple set) and the
  freshness of bound variables across recursion.
- **`tests/test_sparql.py`** — for one nontrivial anonymous expression, snapshot
  the generated query and verify: the structural pattern appears before the
  relation clause, `?target` is the variable substituted into the relation, and
  all named operands are emitted as IRIs (not literals).
- **`tests/test_e2e.py`** — round-trip via rdflib, pyoxigraph, and owlready2
  backends (SELECT) against `tests/data/pizza.omn`:
  - `Margherita EquivalentTo: hasTopping only (Cheese or Tomato)` — query
    `equiv` of the parsed `hasTopping only (Cheese or Tomato)` returns
    `Margherita`'s IRI.
  - One nested-restriction case to exercise recursion.

## Success criteria

1. `class_relations_query(expr, relations=("equiv",))` where `expr` is a parsed
   anonymous owlready2 construct produces a runnable SPARQL query.
2. The query, executed against the asserted graph that defines `expr` as the
   equivalent class of some named class `X`, returns `X`'s IRI from all three
   in-process backends.
3. The new unit tests pass; the existing 109-test suite continues to pass.
4. `_target_term` rejects unsupported / wrong-type targets with clear messages.
5. README's "Caveats" section is updated to remove the "Named-class / IRI targets
   only" line and add a paragraph documenting the new capability plus the
   operand-order limitation.
