# pymos

Pure-Python Manchester OWL Syntax **parser and renderer** for
[owlready2](https://owlready2.readthedocs.io/), plus a store-agnostic SPARQL query
builder for class-relation retrieval.  No Java required.

---

## Features

**Parser — full Manchester documents → owlready2**

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
- `\\"` and `\\\\` escapes inside string literals are honoured (lossless
  round-trip with the renderer).
- Returns a real `owlready2.Ontology` — the full owlready2 Python API
  (class hierarchy, axioms, instances, characteristics) applies; pymos
  adds no separate object model of its own.

**Renderer — owlready2 → Manchester, round-trip stable**

- `render(onto)` — full document; `render_frame(entity)` — one entity;
  `render_expression(ce)` — one class expression.
- Operator-precedence aware (`A and B or C` round-trips correctly).
- Properly escapes `"` and `\` per the W3C grammar.
- Idempotent from the second render onward — `r2 == r3` for arbitrary input.
- Faithful to property characteristics (`Functional`, `Transitive`, …),
  inverse properties, sub-property hierarchies, annotation properties
  (IRI-keyed, so same-local-name properties stay distinct), individuals'
  `Types` / `Facts` / `SameAs` / `DifferentFrom`, and datatypes.

**SPARQL — class-relation retrieval, store-agnostic**

- Six relations: `super` / `sub` (transitive `rdfs:subClassOf+`),
  `direct_super` / `direct_sub` (immediate, with redundancy filter),
  `equiv` (both directions), `individual` (`rdf:type` instances).
- `CONSTRUCT` mode returns the full RDF subgraph of related classes —
  **including the blank-node structure of anonymous class expressions**
  (restrictions, intersections, RDF lists).
- `SELECT` mode returns related IRIs only (anonymous nodes filtered out).
- Target can be a full IRI, a prefixed name, an owlready2 entity, or a
  parsed anonymous class expression — any of those produce portable SPARQL.

**Runners — pick a backend, no hard dependency**

- `run_rdflib(q, graph)` — rdflib `Graph` (CONSTRUCT → `Graph`; SELECT → rows).
- `run_pyoxigraph(q, store)` — pyoxigraph `Store` (sanitises owlready2's
  N-Triples export at the bridge so strict pyoxigraph accepts it).
- `run_owlready2(q, world)` — owlready2's native engine (SELECT-only;
  raises clearly on CONSTRUCT with guidance).
- `run_endpoint(q, url)` — remote SPARQL endpoint via SPARQLWrapper;
  `Turtle` for CONSTRUCT, `JSON` for SELECT.
- Each runner imports its backend lazily — pymos itself depends only on
  `parsimonious` + `owlready2`.

**Jupyter — interactive MOS authoring (optional)**

- `%load_ext pymos.jupyter` enables:
  `%%mos` (parse a cell as Manchester and merge into the active ontology),
  `%%mos_query <relation>` (run a class-relation SPARQL),
  `%reason [pellet]` (materialise inferences via owlready2's reasoner bridge),
  `%mos_show <Name>` (render one entity), `%mos_save <path>` (render whole onto).
- Tab-completion is context-aware (frame keywords, axiom keywords,
  property characteristics, classes/properties/individuals already in scope).

**Quality / packaging**

- **201 tests** (parser, frames, renderer, SPARQL, store, e2e) on
  Python 3.10 + 3.12, CI-enforced; **37 bench tests** for the perf harness.
- Pure Python, no native build step; only required runtime deps are
  `parsimonious` and `owlready2`.
- MIT-licensed.  Grammar is vendored from
  [owlapy](https://github.com/dice-group/owlapy) (MIT) — see `NOTICE` for the
  one intentional divergence (W3C-conformant `,` facet separator).
- Asserted-graph only — no reasoner is invoked unless you call one
  explicitly (`%reason` / `owlrl` / HermiT via `sync_reasoner_hermit()`).

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

## Usage E — Navigating the owlready2 model

`pymos.parse()` returns a real **`owlready2.Ontology`**, so the full
[owlready2 Python OWL API](https://owlready2.readthedocs.io/) applies — pymos
adds no separate object API of its own.  Once an ontology is parsed you can
walk the class hierarchy, inspect axioms, list instances, and read property
characteristics directly.

```python
import pymos

doc = """
Prefix: : <http://example.org/>

Class: Food
Class: Pizza
    SubClassOf: Food
Class: Margherita
    SubClassOf: Pizza
Class: Capricciosa
    SubClassOf: Pizza

ObjectProperty: hasTopping
    Domain: Pizza
    Range: Food

Individual: m1
    Types: Margherita
"""
onto = pymos.parse(doc)
Pizza = onto.world["http://example.org/Pizza"]
hasT  = onto.world["http://example.org/hasTopping"]

# --- class navigation ---
Pizza.is_a               # [owl.Thing, example.org.Food] (direct supers + restrictions)
list(Pizza.subclasses())  # [Margherita, Capricciosa] (direct only)
list(Pizza.descendants()) # [Pizza, Margherita, Capricciosa] (incl. self, transitive)
list(Pizza.ancestors())   # [Pizza, owl.Thing, Food] (incl. self, transitive)
Pizza.equivalent_to       # equivalent classes (writable list)
list(Pizza.instances())   # [m1] — direct instances (no reasoning)

# --- property navigation ---
list(hasT.domain)   # [Pizza]
list(hasT.range)    # [Food]
hasT.is_a           # superproperties + characteristic mixins

# --- individuals carry their own attribute accessors ---
m1 = onto.world["http://example.org/m1"]
m1.is_a               # [owl.Thing, Margherita]
type(m1).__name__     # 'Margherita'   (owlready2 maps individuals to their Python class)
```

**No reasoning runs by default.** `.descendants()` / `.ancestors()` /
`.instances()` walk only **asserted** axioms.  To pick up inferred relations,
materialise them first — see *Reasoning* below and notebook
`examples/notebooks/06_reasoning.ipynb`.

---

## Reasoning

pymos itself is reasoner-free, but the owlready2 ontology it returns can be
fed to any reasoner that integrates with owlready2 or with an RDF graph:

| Reasoner | Profile | Wrapper | Java? |
|---|---|---|---|
| `owlrl` | OWL 2 RL | pure-Python (rdflib) | no |
| `HermiT` / `Pellet` | OWL 2 DL | owlready2 + JPype bridge | yes |
| `HermiT` / `JFact` / `ELK` | DL / EL | ROBOT docker (`robot reason`) | yes (docker) |
| `Konclude` | OWL 2 DL | konclude docker | no JVM (C++) |

The simplest pattern uses **owlrl** in-process — pure Python, no Java:

```python
import io, pymos, owlrl, rdflib

onto = pymos.parse(open("ontology.omn").read())

# owlready2 → rdflib graph → expand under OWL 2 RL semantics
buf = io.BytesIO(); onto.save(file=buf, format="ntriples")
g = rdflib.Graph(); g.parse(data=buf.getvalue(), format="nt")
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)

# Query the saturated graph with the same pymos.class_relations_query
from pymos import class_relations_query
from pymos.store import run_rdflib
q = class_relations_query("<http://example.org/Pizza>", relations=("sub",))
inferred = run_rdflib(q, g)
```

For DL reasoning use owlready2's `sync_reasoner_hermit()` (requires a JDK):

```python
import owlready2

with onto:
    owlready2.sync_reasoner_hermit(infer_property_values=True)

# Now Pizza.descendants() / .equivalent_to / .is_a reflect HermiT inferences.
```

See `examples/notebooks/06_reasoning.ipynb` for a runnable walk-through that
compares the asserted graph against owlrl + HermiT materialisations on the
same ontology.

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
