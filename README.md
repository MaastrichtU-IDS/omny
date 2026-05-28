# pymos

Pure-Python Manchester OWL Syntax **parser and renderer** for
[owlready2](https://owlready2.readthedocs.io/), plus a store-agnostic SPARQL query
builder for class-relation retrieval.  No Java required.

`pymos` lets you:

1. **Parse** a `.omn` (Manchester OWL) document directly into an owlready2 ontology.
2. **Query** the asserted graph for a class's superclasses, subclasses, equivalent
   classes, or instances — across any SPARQL-capable backend (rdflib, pyoxigraph,
   owlready2's built-in engine, or a remote endpoint).
3. **Render** an owlready2 ontology back to a Manchester document — full round-trip,
   precedence-aware, deterministic output.

---

## Install

```bash
pip install -e .
```

Optional extras:

| Extra | What it adds |
|-------|--------------|
| `.[rdflib]` | rdflib ≥ 7.0 for `run_rdflib` |
| `.[pyoxigraph]` | pyoxigraph ≥ 0.4 for `run_pyoxigraph` |
| `.[endpoint]` | SPARQLWrapper ≥ 2.0 for `run_endpoint` |
| `.[dev]` | all of the above + pytest + ruff |

Core dependencies are `parsimonious` and `owlready2` only.

---

## Usage A — Parse a Manchester document

```python
import pymos

doc = """
Prefix: : <http://example.org/>

Class: Food

Class: Pizza
    SubClassOf: Food

Class: MargheritaPizza
    SubClassOf: Pizza
    EquivalentTo: Pizza and (hasTopping some MozzarellaTopping)
"""

onto = pymos.parse(doc)

# Look up classes by full IRI
food       = onto.world["http://example.org/Food"]
pizza      = onto.world["http://example.org/Pizza"]
margherita = onto.world["http://example.org/MargheritaPizza"]

print(pizza.is_a)
# [owl.Thing, example.org.Food]

print(margherita.equivalent_to)
# [example.org.Pizza & example.org.hasTopping.some(example.org.MozzarellaTopping)]
```

`parse` returns an `owlready2.Ontology`.  Pass an existing ontology as the `onto`
argument to populate it in-place.

---

## Usage B — Parse a single class expression

```python
import owlready2
import pymos

onto = owlready2.World().get_ontology("http://example.org/onto.owl")
with onto:
    class hasTopping(owlready2.ObjectProperty): pass
    class Cheese(owlready2.Thing): pass

expr = pymos.parse_expression("hasTopping some Cheese", onto)
print(expr)        # onto.hasTopping.some(onto.Cheese)
print(type(expr))  # <class 'owlready2.class_construct.Restriction'>
```

`parse_expression` returns an owlready2 construct (a `Restriction`, `And`, `Or`,
`Not`, `OneOf`, `ConstrainedDatatype`, or a named class) that can be appended
directly to `.is_a` or `.equivalent_to` lists.

---

## Usage C — Class-relation SPARQL retrieval

### CONSTRUCT — retrieve the full RDF subgraph of related classes

```python
import pymos
from pymos import class_relations_query
from pymos.store import run_rdflib

doc = """
Prefix: : <http://example.org/>
Class: Food
Class: Pizza
    SubClassOf: Food
Class: MargheritaPizza
    SubClassOf: Pizza
"""
onto = pymos.parse(doc)

# Build a CONSTRUCT query for the superclasses and subclasses of Pizza
q = class_relations_query(
    "<http://example.org/Pizza>",
    relations=("super", "sub"),
    construct=True,           # default
)

# Run against the owlready2 world via the rdflib adapter
result_graph = run_rdflib(q, onto.world.as_rdflib_graph())
# result_graph is an rdflib.Graph containing the subgraph of Food and
# MargheritaPizza (all their structural triples).
print({str(s) for s, p, o in result_graph})
# {'http://example.org/Food', 'http://example.org/Pizza',
#  'http://example.org/MargheritaPizza'}
```

### SELECT — retrieve related IRIs only

```python
from pymos.store import run_owlready2

q_select = class_relations_query(
    "<http://example.org/Pizza>",
    relations=("super", "sub"),
    construct=False,
)

rows = run_owlready2(q_select, onto.world)
print([str(r[0]) for r in rows])
# ['owl.Thing', 'example.org.Food', 'example.org.MargheritaPizza']
```

### Running against a pyoxigraph store

```python
import io
import pyoxigraph
from pymos.store import run_pyoxigraph

# Serialise the owlready2 world to N-Triples and load into pyoxigraph
nt_bytes = onto.world.as_rdflib_graph().serialize(format="nt").encode()

store = pyoxigraph.Store()
store.load(io.BytesIO(nt_bytes), format=pyoxigraph.RdfFormat.N_TRIPLES)

results = list(run_pyoxigraph(q_select, store))
print([str(s["rel"]) for s in results])
# ['<http://www.w3.org/2002/07/owl#Thing>',
#  '<http://example.org/Food>',
#  '<http://example.org/MargheritaPizza>']
```

---

## Usage D — Render back to Manchester

`pymos.render(onto, prefixes=...)` produces a Manchester OWL syntax document
from an owlready2 ontology — the round-trip companion to `parse`.

```python
import pymos

doc = """
Prefix: : <http://example.org/>
Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>

Class: Pizza
    Annotations: rdfs:label "Pizza"
    SubClassOf: Food
    DisjointWith: IceCream

ObjectProperty: hasTopping
    Domain: Pizza
    Range: Topping
    Characteristics: Transitive

Individual: margherita1
    Types: Pizza
    Facts: hasTopping cheese1
"""

onto = pymos.parse(doc)
text = pymos.render(onto, prefixes={
    "": "http://example.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
})
print(text)
```

`render` emits frames in stable order (Datatype → AnnotationProperty →
ObjectProperty → DataProperty → Class → Individual), each sorted by IRI.
Annotations, `Facts:`, `SameAs:`, `DifferentFrom:`, property `Characteristics:`,
and `InverseOf:` are all rendered.  A second pass is byte-identical — useful
for deterministic diff-friendly output.

### Render a single class expression

```python
from pymos import parse_expression, render_expression

prefixes = {"": "http://example.org/"}
ce = parse_expression("hasTopping some (Cheese or Tomato)", onto, prefixes=prefixes)
print(render_expression(ce, prefixes=prefixes))
# :hasTopping some (:Cheese or :Tomato)
```

`render_expression` is precedence-aware: lower-precedence operands (`or`) are
parenthesised inside higher-precedence parents (`and`) automatically.

### Round-trip

```python
text1 = pymos.render(pymos.parse(doc), prefixes=prefixes)
text2 = pymos.render(pymos.parse(text1), prefixes=prefixes)
assert text1 == text2   # idempotent
```

`parse → render → parse` preserves the set of class / property / individual
IRIs and the count of axioms per entity.

---

## Relation table

| Relation | Semantics |
|----------|-----------|
| `super` | Transitive superclasses — all classes reachable via `rdfs:subClassOf+` upward from the target. |
| `sub` | Transitive subclasses — all classes reachable via `rdfs:subClassOf+` downward from the target. |
| `direct_super` | Immediate superclasses — one `rdfs:subClassOf` step up, with intermediate classes filtered out. |
| `direct_sub` | Immediate subclasses — one `rdfs:subClassOf` step down, with intermediate classes filtered out. |
| `equiv` | Equivalent classes — both directions of `owl:equivalentClass`. |
| `individual` | Instances of the target class — subjects of `rdf:type` triples. |

---

## Anonymous expression targets

`class_relations_query` accepts an anonymous Manchester class expression as its
target. Parse the expression first with `parse_expression`, then pass the returned
owlready2 construct directly:

```python
import pymos
from pymos import class_relations_query
from pymos.store import run_rdflib

onto = pymos.parse(open("pizza.omn").read())
expr = pymos.parse_expression(
    "hasTopping only (Cheese or Tomato)",
    onto,
    prefixes={"": "http://ex.org/"},   # see note below
)

q = class_relations_query(expr, relations=("equiv",), construct=False)
rows = [str(r[0]) for r in run_rdflib(q, onto.world.as_rdflib_graph())]
print(rows)
# ['http://ex.org/Margherita']
```

The generated SPARQL contains a structural sub-pattern that matches the
blank-node shape owlready2 writes for the expression, binding a fresh variable
(`?t0`) to any matching node. The relation clauses then use that variable.

**Supported constructs**: `R some C`, `R only C`, `R value v`, `R Self`,
`R min/max/exactly N [C]` (qualified + unqualified), `A and B`, `A or B`,
`not A`, `{a, b, ...}`, `inverse R`, and arbitrary nesting.

**Limitations**

- **Operand order matters.** Two structurally equivalent expressions with
  permuted intersection/union operands do not match each other. (`A and B` and
  `B and A` produce different patterns; only the as-declared order matches the
  blank-node spine.)
- **Structural identity only.** With no reasoning, semantically equivalent
  but structurally distinct expressions do not match (e.g. an `EquivalentTo`
  axiom defined via an intermediate named class is invisible to the structural
  pattern).
- **Data ranges (`ConstrainedDatatype`) and literal `hasValue` targets are
  not supported.** Use a named individual (`hasTopping value myCheese`) rather
  than a literal (`age value 42`).

**Namespace note**

`parse_expression` resolves bare names (e.g. `Cheese`, `hasTopping`) against
`onto.base_iri`, NOT against the document's `Prefix: :` declaration. If your
ontology declares a `Prefix: :` that differs from its `Ontology: <...>` IRI —
which is common — pass the empty-prefix mapping explicitly:

```python
expr = pymos.parse_expression(
    "hasTopping only (Cheese or Tomato)",
    onto,
    prefixes={"": "http://ex.org/"},
)
```

Without this override, bare names resolve to fresh entities under
`onto.base_iri` that don't exist in the loaded graph, and the query returns
no rows.

---

## Caveats

- **No Java required.** `pymos` is pure Python; it does not call a DL reasoner or
  require an OWL API JVM.
- **Asserted graph only, no reasoning.** `pymos` loads and queries only the explicitly
  stated axioms.  Inferred subclass / equivalence relations are not visible unless
  a reasoner has already materialised them into the graph.
- **CONSTRUCT returns full outgoing subgraphs.** A CONSTRUCT query retrieves not just
  the related class IRI but the *entire* structural outgoing subgraph of that class
  (i.e. all its restriction blank-nodes, list nodes, etc.).  This is intentional —
  it allows a client to reconstruct anonymous class expressions without further
  round-trips.  Use `construct=False` if you only need the IRIs.
- **`run_owlready2` is SELECT-only.** owlready2's built-in SPARQL engine cannot
  parse CONSTRUCT queries.  For CONSTRUCT against owlready2 data use
  `run_rdflib(q, world.as_rdflib_graph())`.
- **Frame tokeniser is not string-aware.** A token that looks like `Keyword:` at the
  start of a line *inside a multi-line quoted literal* can cause incorrect frame
  splitting.  Single-line operands and standard Manchester frame forms work correctly.
  `Import:` directives in the ontology preamble are recorded as `owl:imports`
  declarations (visible via `onto.imported_ontologies`) but the imported ontologies
  are **not fetched** — only the declaration is stored.

---

## Attribution

The Manchester OWL Syntax PEG grammar is vendored from
[owlapy](https://github.com/dice-group/owlapy) (MIT licence, © 2024 Caglar Demir).
See [`NOTICE`](NOTICE) and [`licenses/owlapy-LICENSE.txt`](licenses/owlapy-LICENSE.txt).
