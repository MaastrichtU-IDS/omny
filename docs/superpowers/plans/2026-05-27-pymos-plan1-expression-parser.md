# pymos Plan 1 — Scaffolding + Manchester Expression Parser

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `pymos` package and parse a single Manchester OWL *class expression* string into an owlready2 class-expression object.

**Architecture:** Vendor owlapy's MIT `parsimonious` PEG grammar verbatim into `pymos/grammar.py`. A fresh `NodeVisitor` in `pymos/parser.py` walks the parse tree and emits **owlready2** constructs, resolving every IRI (full `<…>`, prefixed `p:local`, or simple `local`) to a full IRI and getting-or-creating the corresponding owlready2 entity in a target ontology. Object-vs-data property is disambiguated by the grammar's alternative ordering (a data-range filler routes to the `data_*` productions).

**Tech Stack:** Python 3.10+, `parsimonious` (PEG), `owlready2` 0.50, `pytest`. No Java, no native build.

**Plan set:** This is **Plan 1 of 3**. Plan 2 adds the Manchester frame/document loader; Plan 3 adds the class-relation SPARQL converter. Plan 1 produces working software: `pymos.parse_expression("hasTopping some Cheese", onto)` → an owlready2 `Restriction`.

**Reference material (present locally, gitignored):** `_ref_owlapy/owlapy/parser.py` holds the original MIT grammar + visitor. owlapy is MIT © 2024 Caglar Demir.

---

## File structure (created in this plan)

```
pyproject.toml          # project metadata + deps (setuptools backend)
NOTICE                  # owlapy MIT attribution for the vendored grammar
README.md               # one-paragraph description
pymos/
  __init__.py           # public API surface: parse_expression
  grammar.py            # vendored MANCHESTER_GRAMMAR (parsimonious)
  iri.py                # IRI token → full IRI string resolution
  entities.py           # EntityFactory: get-or-create owlready2 entities by IRI
  parser.py             # ManchesterExpressionParser(NodeVisitor) → owlready2
tests/
  __init__.py
  test_grammar.py
  test_iri.py
  test_entities.py
  test_parser_classes.py
  test_parser_restrictions.py
  test_parser_boolean.py
  test_parser_data.py
  test_parse_expression.py
```

Note: `.venv/` and `_ref_*/` are already in `.gitignore`. Each module has one responsibility (`grammar` = PEG text, `iri` = name resolution, `entities` = owlready2 entity lifecycle, `parser` = tree→objects) and is tested in isolation.

---

## Task 1: Scaffold the package

**Files:**
- Create: `pyproject.toml`, `pymos/__init__.py`, `NOTICE`, `README.md`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "pymos"
version = "0.0.1"
description = "Pure-Python Manchester OWL syntax parser to the owlready2 model, with a class-relation SPARQL converter."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Michel Dumontier" }]
dependencies = [
    "parsimonious>=0.10",
    "owlready2>=0.46",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
include = ["pymos*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `pymos/__init__.py`**

```python
"""pymos — Manchester OWL syntax → owlready2 model + class-relation SPARQL."""

__version__ = "0.0.1"
```

- [ ] **Step 3: Create `tests/__init__.py` (empty) and `README.md`**

`tests/__init__.py`: empty file.

`README.md`:

```markdown
# pymos

Pure-Python (no Java) Manchester OWL syntax parser targeting the
[owlready2](https://owlready2.readthedocs.io) object model, plus a store-agnostic
converter from a class to a SPARQL `CONSTRUCT` query that retrieves its
sub/super/equivalent classes and individuals.

The Manchester grammar is vendored from [owlapy](https://github.com/dice-group/owlapy)
(MIT). See `NOTICE`.
```

- [ ] **Step 4: Create `NOTICE`**

```
pymos includes a Manchester OWL syntax PEG grammar (pymos/grammar.py) derived from
owlapy (https://github.com/dice-group/owlapy), which is licensed under the MIT License:

    MIT License
    Copyright (c) 2024 Caglar Demir

The full MIT license text applies to the derived grammar.
```

- [ ] **Step 5: Create the virtualenv and install (proxy env vars already set on this host)**

Run:
```bash
python3 -m venv .venv
.venv/bin/pip install -q -e ".[dev]"
```
Expected: installs `parsimonious`, `owlready2`, `pytest` without error.

- [ ] **Step 6: Run pytest to confirm the harness works**

Run: `.venv/bin/pytest -q`
Expected: `no tests ran` (exit code 5) — the harness is wired up.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml pymos/ tests/ NOTICE README.md
git commit -m "chore: scaffold pymos package"
```

---

## Task 2: Vendor the Manchester grammar

**Files:**
- Create: `pymos/grammar.py`
- Test: `tests/test_grammar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grammar.py
from parsimonious.nodes import Node
from parsimonious.exceptions import ParseError
import pytest

from pymos.grammar import MANCHESTER_GRAMMAR


def test_grammar_parses_simple_restriction():
    tree = MANCHESTER_GRAMMAR.parse("hasTopping some Cheese")
    assert isinstance(tree, Node)


def test_grammar_parses_boolean_and_parentheses():
    assert MANCHESTER_GRAMMAR.parse("A and (B or C)") is not None


def test_grammar_rejects_garbage():
    with pytest.raises(ParseError):
        MANCHESTER_GRAMMAR.parse("some some some")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_grammar.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pymos.grammar'`.

- [ ] **Step 3: Create `pymos/grammar.py` by vendoring the grammar verbatim**

Extract the `MANCHESTER_GRAMMAR = Grammar(r"""…""")` block (the Manchester one, **not** `DL_GRAMMAR`) from `_ref_owlapy/owlapy/parser.py` and place it in `pymos/grammar.py` with this header. The block to copy is the grammar literal that begins with `MANCHESTER_GRAMMAR = Grammar(r"""` and ends at its closing `""")`.

```python
# pymos/grammar.py
"""Manchester OWL syntax PEG grammar.

Vendored verbatim from owlapy (https://github.com/dice-group/owlapy), MIT License,
Copyright (c) 2024 Caglar Demir. See NOTICE.

Grammar reference: https://www.w3.org/TR/owl2-manchester-syntax
"""
from parsimonious.grammar import Grammar

# <<< paste the MANCHESTER_GRAMMAR = Grammar(r""" ... """) block here verbatim >>>
```

The grammar text (for reference — must match `_ref_owlapy/owlapy/parser.py`):

```
union = intersection (must_ws "or" must_ws intersection)*
intersection = primary (must_ws "and" must_ws primary)*
primary = ("not" must_ws)? (data_some_only_res / some_only_res / data_cardinality_res / cardinality_res
                       / data_value_res / value_res / has_self / class_expression)
some_only_res = object_property must_ws ("some"/"only") must_ws primary
cardinality_res = object_property must_ws ("max"/"min"/"exactly") must_ws non_negative_integer must_ws primary
value_res = object_property must_ws "value" must_ws individual_iri
has_self = object_property must_ws "Self"
object_property = ("inverse" must_ws)? object_property_iri
class_expression = class_iri / individual_list / parentheses
individual_list = "{" maybe_ws individual_iri (maybe_ws "," maybe_ws individual_iri)* maybe_ws "}"
parentheses = "(" maybe_ws union maybe_ws ")"
... (data ranges, facets, literals, IRIs, ws, no_match — exactly as in the reference)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_grammar.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pymos/grammar.py tests/test_grammar.py
git commit -m "feat: vendor Manchester PEG grammar from owlapy (MIT)"
```

---

## Task 3: IRI resolution

Resolve a raw IRI token from the grammar — full (`<http://…>`), prefixed (`p:local`), or
simple (`local`) — to a full IRI string. `Thing`/`Nothing` map to the OWL built-ins.

**Files:**
- Create: `pymos/iri.py`
- Test: `tests/test_iri.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_iri.py
import pytest
from pymos.iri import resolve_iri

OWL = "http://www.w3.org/2002/07/owl#"
BASE = "http://ex.org/o#"
PREFIXES = {"": "http://ex.org/o#", "foaf": "http://xmlns.com/foaf/0.1/"}


def test_full_iri():
    assert resolve_iri("<http://ex.org/o#Pizza>", PREFIXES, BASE) == "http://ex.org/o#Pizza"


def test_prefixed_iri():
    assert resolve_iri("foaf:Person", PREFIXES, BASE) == "http://xmlns.com/foaf/0.1/Person"


def test_empty_prefix():
    assert resolve_iri(":Pizza", PREFIXES, BASE) == "http://ex.org/o#Pizza"


def test_simple_iri_uses_base():
    assert resolve_iri("Pizza", PREFIXES, BASE) == "http://ex.org/o#Pizza"


def test_thing_nothing():
    assert resolve_iri("Thing", PREFIXES, BASE) == OWL + "Thing"
    assert resolve_iri("Nothing", PREFIXES, BASE) == OWL + "Nothing"


def test_unknown_prefix_raises():
    with pytest.raises(ValueError):
        resolve_iri("bogus:X", PREFIXES, BASE)


def test_simple_without_base_raises():
    with pytest.raises(ValueError):
        resolve_iri("Pizza", {}, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_iri.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pymos.iri'`.

- [ ] **Step 3: Implement `pymos/iri.py`**

```python
# pymos/iri.py
"""Resolve Manchester IRI tokens (full / prefixed / simple) to full IRI strings."""
from typing import Mapping, Optional

OWL = "http://www.w3.org/2002/07/owl#"
_BUILTINS = {"Thing": OWL + "Thing", "Nothing": OWL + "Nothing"}


def resolve_iri(token: str, prefixes: Mapping[str, str], base: Optional[str]) -> str:
    """Return the full IRI for a Manchester IRI token.

    token forms:
      <http://...>   full IRI (returned as-is, brackets stripped)
      prefix:local   abbreviated IRI (prefix looked up in `prefixes`, "" is the default)
      local          simple name (resolved against `base`; Thing/Nothing are built-ins)
    """
    token = token.strip()
    if token.startswith("<") and token.endswith(">"):
        return token[1:-1]
    if token in _BUILTINS:
        return _BUILTINS[token]
    if ":" in token:
        prefix, local = token.split(":", 1)
        if prefix not in prefixes:
            raise ValueError(f"Unknown prefix {prefix!r} in {token!r}")
        return prefixes[prefix] + local
    if base is None:
        raise ValueError(
            f"Simple name {token!r} requires a base IRI (set the ontology base or a default prefix)."
        )
    return base + token
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_iri.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add pymos/iri.py tests/test_iri.py
git commit -m "feat: IRI token resolution"
```

---

## Task 4: Entity factory (get-or-create owlready2 entities)

**Files:**
- Create: `pymos/entities.py`
- Test: `tests/test_entities.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_entities.py
import owlready2 as o2
from pymos.entities import EntityFactory


def make():
    world = o2.World()
    onto = world.get_ontology("http://ex.org/o#")
    return world, onto, EntityFactory(world, onto)


def test_create_and_lookup_class():
    world, onto, f = make()
    c = f.get_class("http://ex.org/o#Pizza")
    assert c.iri == "http://ex.org/o#Pizza"
    assert o2.Thing in c.mro()
    # idempotent: second call returns the same entity
    assert f.get_class("http://ex.org/o#Pizza") is c


def test_object_vs_data_property():
    world, onto, f = make()
    op = f.get_object_property("http://ex.org/o#hasTopping")
    dp = f.get_data_property("http://ex.org/o#hasCalories")
    assert o2.ObjectProperty in op.mro()
    assert o2.DataProperty in dp.mro()


def test_individual():
    world, onto, f = make()
    i = f.get_individual("http://ex.org/o#mozzarella")
    assert i.iri == "http://ex.org/o#mozzarella"


def test_foreign_namespace():
    world, onto, f = make()
    c = f.get_class("http://other.org/x#Foo")
    assert c.iri == "http://other.org/x#Foo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_entities.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pymos.entities'`.

- [ ] **Step 3: Implement `pymos/entities.py`**

```python
# pymos/entities.py
"""Get-or-create owlready2 entities (classes, properties, individuals) by full IRI."""
import types as _types

import owlready2 as o2
from owlready2 import Thing


def _split(iri: str):
    """Split a full IRI into (namespace_iri, local_name)."""
    if "#" in iri:
        head, local = iri.rsplit("#", 1)
        return head + "#", local
    head, local = iri.rsplit("/", 1)
    return head + "/", local


class EntityFactory:
    """Resolve full IRIs to owlready2 entities, creating them on first use.

    Entities are looked up in the World first (so existing entities are reused) and
    otherwise created in the ontology/namespace matching their IRI.
    """

    def __init__(self, world: o2.World, base_onto: o2.Ontology):
        self.world = world
        self.base_onto = base_onto

    def _namespace(self, iri: str):
        ns_iri, local = _split(iri)
        if ns_iri == self.base_onto.base_iri:
            return self.base_onto, local
        return self.world.get_ontology(ns_iri), local

    def _get_or_create(self, iri: str, parent):
        existing = self.world[iri]
        if existing is not None:
            return existing
        ns, local = self._namespace(iri)
        with ns:
            return _types.new_class(local, (parent,))

    def get_class(self, iri: str):
        return self._get_or_create(iri, Thing)

    def get_object_property(self, iri: str):
        return self._get_or_create(iri, o2.ObjectProperty)

    def get_data_property(self, iri: str):
        return self._get_or_create(iri, o2.DataProperty)

    def get_individual(self, iri: str):
        existing = self.world[iri]
        if existing is not None:
            return existing
        ns, local = self._namespace(iri)
        with ns:
            return Thing(local, namespace=ns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_entities.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pymos/entities.py tests/test_entities.py
git commit -m "feat: owlready2 entity factory (get-or-create by IRI)"
```

---

## Task 5: Visitor — named classes + object some/only

Build `pymos/parser.py` incrementally. Start with named classes and `some`/`only`.

**Files:**
- Create: `pymos/parser.py`
- Test: `tests/test_parser_classes.py`, `tests/test_parser_restrictions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_classes.py
import owlready2 as o2
from owlready2 import Restriction
from pymos.parser import ManchesterExpressionParser

BASE = "http://ex.org/o#"


def parse(text, prefixes=None):
    world = o2.World()
    onto = world.get_ontology(BASE)
    p = ManchesterExpressionParser(world, onto, prefixes=prefixes or {"": BASE})
    return p.parse(text), onto


def test_named_class():
    expr, onto = parse("Pizza")
    assert expr.iri == BASE + "Pizza"


def test_some_restriction():
    expr, onto = parse("hasTopping some Cheese")
    assert isinstance(expr, Restriction)
    assert expr.property.iri == BASE + "hasTopping"
    assert expr.type == o2.SOME
    assert expr.value.iri == BASE + "Cheese"


def test_only_restriction():
    expr, onto = parse("hasTopping only Cheese")
    assert expr.type == o2.ONLY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parser_classes.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pymos.parser'`.

- [ ] **Step 3: Implement the visitor skeleton + class/some/only**

```python
# pymos/parser.py
"""Manchester class-expression parser → owlready2 objects."""
from parsimonious.nodes import NodeVisitor

import owlready2 as o2

from .grammar import MANCHESTER_GRAMMAR
from .entities import EntityFactory
from .iri import resolve_iri


def _text(node):
    return node.text.strip()


class ManchesterExpressionParser(NodeVisitor):
    """Parse a single Manchester class expression into an owlready2 construct."""

    grammar = MANCHESTER_GRAMMAR

    def __init__(self, world, onto, prefixes=None):
        self.world = world
        self.onto = onto
        self.prefixes = prefixes or {}
        self.base = onto.base_iri
        self.entities = EntityFactory(world, onto)

    def parse(self, text):
        return self.visit(self.grammar.parse(text.strip()))

    # --- structure ---
    def visit_class_expression(self, node, children):
        return children[0]

    def visit_some_only_res(self, node, children):
        property_, _, kind, _, filler = children
        kind = _text(kind[0]) if isinstance(kind, list) else _text(kind)
        return property_.some(filler) if kind == "some" else property_.only(filler)

    def visit_object_property(self, node, children):
        inverse, property_ = children
        return o2.Inverse(property_) if isinstance(inverse, list) else property_

    # --- IRIs / entities ---
    def visit_class_iri(self, node, children):
        return self.entities.get_class(resolve_iri(_text(node), self.prefixes, self.base))

    def visit_object_property_iri(self, node, children):
        return self.entities.get_object_property(resolve_iri(_text(node), self.prefixes, self.base))

    def generic_visit(self, node, children):
        return children or node
```

Note: `visit_object_property`'s `children[0]` (`inverse`) is a list only when the optional
`("inverse" must_ws)?` matched. The `kind` capture handles parsimonious wrapping the
`("some"/"only")` ordered-choice node.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parser_classes.py -q`
Expected: PASS (3 passed). If `kind`/`inverse` unwrapping mismatches, print `children` in the visitor to inspect parsimonious's shape and adjust the index — the test pins the correct behaviour.

- [ ] **Step 5: Commit**

```bash
git add pymos/parser.py tests/test_parser_classes.py
git commit -m "feat: parse named classes and some/only restrictions"
```

---

## Task 6: Visitor — value, Self, cardinality

**Files:**
- Modify: `pymos/parser.py`
- Test: `tests/test_parser_restrictions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_restrictions.py
import owlready2 as o2
from pymos.parser import ManchesterExpressionParser

BASE = "http://ex.org/o#"


def parse(text):
    world = o2.World()
    onto = world.get_ontology(BASE)
    return ManchesterExpressionParser(world, onto, prefixes={"": BASE}).parse(text)


def test_value():
    expr = parse("hasTopping value mozzarella")
    assert expr.type == o2.VALUE
    assert expr.value.iri == BASE + "mozzarella"


def test_min_cardinality():
    expr = parse("hasTopping min 2 Cheese")
    assert expr.type == o2.MIN
    assert expr.cardinality == 2
    assert expr.value.iri == BASE + "Cheese"


def test_max_cardinality():
    expr = parse("hasTopping max 3 Cheese")
    assert expr.type == o2.MAX and expr.cardinality == 3


def test_exactly_cardinality():
    expr = parse("hasTopping exactly 1 Cheese")
    assert expr.type == o2.EXACTLY and expr.cardinality == 1


def test_has_self():
    expr = parse("likes Self")
    assert expr.type == o2.HAS_SELF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parser_restrictions.py -q`
Expected: FAIL — `value`/cardinality/`Self` not yet handled (AttributeError or wrong type).

- [ ] **Step 3: Add the visit methods to `ManchesterExpressionParser`**

```python
    def visit_value_res(self, node, children):
        property_, _, _, _, individual = children
        return property_.value(individual)

    def visit_has_self(self, node, children):
        property_, *_ = children
        return property_.has_self()

    def visit_cardinality_res(self, node, children):
        property_, _, kind, _, cardinality, _, filler = children
        kind = _text(kind[0]) if isinstance(kind, list) else _text(kind)
        if kind == "min":
            return property_.min(cardinality, filler)
        if kind == "max":
            return property_.max(cardinality, filler)
        return property_.exactly(cardinality, filler)

    def visit_individual_iri(self, node, children):
        from .iri import resolve_iri
        return self.entities.get_individual(resolve_iri(_text(node), self.prefixes, self.base))

    def visit_non_negative_integer(self, node, children):
        return int(_text(node))
```

(Move the `resolve_iri` import to module top if you prefer; it's already imported there.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parser_restrictions.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pymos/parser.py tests/test_parser_restrictions.py
git commit -m "feat: parse value, Self, and cardinality restrictions"
```

---

## Task 7: Visitor — and / or / not / parentheses / OneOf

**Files:**
- Modify: `pymos/parser.py`
- Test: `tests/test_parser_boolean.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_boolean.py
import owlready2 as o2
from owlready2 import And, Or, Not, OneOf
from pymos.parser import ManchesterExpressionParser

BASE = "http://ex.org/o#"


def parse(text):
    world = o2.World()
    onto = world.get_ontology(BASE)
    return ManchesterExpressionParser(world, onto, prefixes={"": BASE}).parse(text)


def test_and():
    expr = parse("Pizza and Cheese")
    assert isinstance(expr, And)


def test_or():
    expr = parse("Pizza or Cheese")
    assert isinstance(expr, Or)


def test_not():
    expr = parse("not Pizza")
    assert isinstance(expr, Not)


def test_parentheses_and_precedence():
    expr = parse("Pizza and (Cheese or Tomato)")
    assert isinstance(expr, And)
    assert any(isinstance(part, Or) for part in expr.Classes)


def test_one_of():
    expr = parse("{ mozzarella , cheddar }")
    assert isinstance(expr, OneOf)
    assert len(expr.instances) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parser_boolean.py -q`
Expected: FAIL — boolean/OneOf not handled.

- [ ] **Step 3: Add the visit methods**

owlready2 builds n-ary And/Or from `&`/`|`. `functools.reduce` over the operand list
produces the correct nested/normalised owlready2 object.

```python
import functools

    def visit_union(self, node, children):
        first, rest = children[0], children[1]
        operands = [first] + [r[-1] for r in rest] if isinstance(rest, list) else [first]
        return functools.reduce(lambda a, b: a | b, operands) if len(operands) > 1 else first

    def visit_intersection(self, node, children):
        first, rest = children[0], children[1]
        operands = [first] + [r[-1] for r in rest] if isinstance(rest, list) else [first]
        return functools.reduce(lambda a, b: a & b, operands) if len(operands) > 1 else first

    def visit_primary(self, node, children):
        match_not, expr = children
        inner = expr[0] if isinstance(expr, list) else expr
        return o2.Not(inner) if isinstance(match_not, list) else inner

    def visit_parentheses(self, node, children):
        # "(" maybe_ws union maybe_ws ")"
        return children[2]

    def visit_individual_list(self, node, children):
        # "{" maybe_ws individual_iri (maybe_ws "," maybe_ws individual_iri)* maybe_ws "}"
        first = children[2]
        rest = children[3]
        inds = [first] + ([r[-1] for r in rest] if isinstance(rest, list) else [])
        return o2.OneOf(inds)
```

`import functools` goes at the top of the module.

Note on `visit_union`/`visit_intersection`: parsimonious passes `children = [primary, repetition_list]`. Each item of the repetition is the sequence `(must_ws "and"/"or" must_ws primary)`, so the operand is its last element (`r[-1]`). Verify the exact shape by printing `children` once if a test fails; the tests pin the result.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parser_boolean.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pymos/parser.py tests/test_parser_boolean.py
git commit -m "feat: parse and/or/not, parentheses, OneOf"
```

---

## Task 8: Visitor — data ranges, datatypes, facets, literals

Handles `data_some_only_res`, `data_cardinality_res`, `data_value_res`, datatypes,
facet restrictions (`xsd:integer[>= 5]`), and literals. owlready2 maps a constrained
datatype via `ConstrainedDatatype(base_type, facet=value, …)` and a bare datatype to a
Python type (`int`, `float`, `str`, `bool`).

**Files:**
- Modify: `pymos/parser.py`
- Test: `tests/test_parser_data.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_data.py
import owlready2 as o2
from owlready2 import Restriction, ConstrainedDatatype
from pymos.parser import ManchesterExpressionParser

BASE = "http://ex.org/o#"


def parse(text):
    world = o2.World()
    onto = world.get_ontology(BASE)
    return ManchesterExpressionParser(world, onto, prefixes={"": BASE}).parse(text)


def test_data_some_datatype():
    expr = parse("hasAge some xsd:integer")
    assert isinstance(expr, Restriction)
    assert expr.type == o2.SOME
    assert expr.value is int
    assert o2.DataProperty in expr.property.mro()


def test_data_facet_restriction():
    expr = parse("hasAge some xsd:integer[>= 18]")
    assert isinstance(expr.value, ConstrainedDatatype)
    assert expr.value.base_datatype is int
    assert expr.value.min_inclusive == 18


def test_data_value_literal():
    expr = parse('hasName value "Alice"')
    assert expr.type == o2.VALUE
    assert expr.value == "Alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parser_data.py -q`
Expected: FAIL — data productions not handled.

- [ ] **Step 3: Add data-range handling**

```python
_XSD_TO_PYTHON = {
    "integer": int, "double": float, "boolean": bool, "string": str,
    # date/dateTime/duration handled as str fallback (owlready2 datetime types optional)
    "date": str, "dateTime": str, "duration": str,
}

_FACET_KEYWORD = {
    ">=": "min_inclusive", "<=": "max_inclusive", ">": "min_exclusive", "<": "max_exclusive",
    "length": "length", "minLength": "min_length", "maxLength": "max_length",
    "pattern": "pattern", "totalDigits": "total_digits", "fractionDigits": "fraction_digits",
}

    # data restrictions mirror the object ones but route to data properties
    def visit_data_some_only_res(self, node, children):
        property_, _, kind, _, filler = children
        kind = _text(kind[0]) if isinstance(kind, list) else _text(kind)
        return property_.some(filler) if kind == "some" else property_.only(filler)

    def visit_data_cardinality_res(self, node, children):
        property_, _, kind, _, cardinality, _, filler = children
        kind = _text(kind[0]) if isinstance(kind, list) else _text(kind)
        if kind == "min":
            return property_.min(cardinality, filler)
        if kind == "max":
            return property_.max(cardinality, filler)
        return property_.exactly(cardinality, filler)

    def visit_data_value_res(self, node, children):
        property_, _, _, _, literal = children
        return property_.value(literal)

    def visit_data_property_iri(self, node, children):
        return self.entities.get_data_property(resolve_iri(_text(node), self.prefixes, self.base))

    def visit_data_primary(self, node, children):
        match_not, expr = children
        inner = expr[0] if isinstance(expr, list) else expr
        return o2.Not(inner) if isinstance(match_not, list) else inner

    def visit_datatype(self, node, children):
        return _XSD_TO_PYTHON[_text(node)]

    def visit_datatype_iri(self, node, children):
        # both grammar alternatives wrap the datatype keyword; recover it from the text
        for key, py in _XSD_TO_PYTHON.items():
            if _text(node).endswith(key) or _text(node).endswith(key + ">"):
                return py
        raise ValueError(f"Unsupported datatype: {_text(node)}")

    def visit_datatype_restriction(self, node, children):
        base = children[0]
        facets = children[3]
        facet_list = facets if isinstance(facets, list) else [facets]
        kwargs = {}
        for facet_kw, value in facet_list:
            kwargs[_FACET_KEYWORD[facet_kw]] = value
        return o2.ConstrainedDatatype(base, **kwargs)

    def visit_facet_restrictions(self, node, children):
        first = children[0]
        rest = children[1]
        return [first] + ([r[-1] for r in rest] if isinstance(rest, list) else [])

    def visit_facet_restriction(self, node, children):
        facet, _, literal = children
        return (_text(facet), literal)

    def visit_facet(self, node, children):
        return _text(node)

    # literals
    def visit_integer_literal(self, node, children):
        return int(_text(node))

    def visit_decimal_literal(self, node, children):
        return float(_text(node))

    def visit_float_literal(self, node, children):
        return float(_text(node).rstrip("fF"))

    def visit_boolean_literal(self, node, children):
        return _text(node).lower() == "true"

    def visit_string_literal_no_language(self, node, children):
        return _text(node)[1:-1]  # strip surrounding quotes

    def visit_quoted_string(self, node, children):
        return _text(node)
```

Note: `visit_datatype_restriction` indexing follows the grammar
`datatype_iri "[" maybe_ws facet_restrictions maybe_ws "]"`; if parsimonious's child
shape differs, print `children` once and adjust — the tests pin the result. Single
facet vs list is normalised in `visit_facet_restrictions`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parser_data.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite + commit**

Run: `.venv/bin/pytest -q`
Expected: all green.

```bash
git add pymos/parser.py tests/test_parser_data.py
git commit -m "feat: parse data ranges, datatypes, facets, literals"
```

---

## Task 9: Public API `parse_expression` + inverse/data property regression

Expose a one-call helper and lock in the remaining behaviours (inverse property, data
property kind) end-to-end.

**Files:**
- Modify: `pymos/__init__.py`
- Test: `tests/test_parse_expression.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parse_expression.py
import owlready2 as o2
from owlready2 import Restriction, Inverse
import pymos

BASE = "http://ex.org/o#"


def test_parse_expression_creates_ontology_entities():
    world = o2.World()
    onto = world.get_ontology(BASE)
    expr = pymos.parse_expression("hasTopping some Cheese", onto, prefixes={"": BASE})
    assert isinstance(expr, Restriction)
    # the referenced entities now exist in the world
    assert world[BASE + "hasTopping"] is not None
    assert world[BASE + "Cheese"] is not None


def test_parse_expression_inverse():
    world = o2.World()
    onto = world.get_ontology(BASE)
    expr = pymos.parse_expression("inverse hasTopping some Pizza", onto, prefixes={"": BASE})
    assert isinstance(expr.property, Inverse)


def test_parse_expression_full_iri():
    world = o2.World()
    onto = world.get_ontology(BASE)
    expr = pymos.parse_expression(
        "<http://ex.org/o#hasTopping> some <http://ex.org/o#Cheese>", onto
    )
    assert expr.property.iri == BASE + "hasTopping"


def test_parse_expression_default_prefix_from_base():
    # with no prefixes, simple names resolve against the ontology base
    world = o2.World()
    onto = world.get_ontology(BASE)
    expr = pymos.parse_expression("Pizza", onto)
    assert expr.iri == BASE + "Pizza"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parse_expression.py -q`
Expected: FAIL — `AttributeError: module 'pymos' has no attribute 'parse_expression'`.

- [ ] **Step 3: Implement `parse_expression` in `pymos/__init__.py`**

```python
"""pymos — Manchester OWL syntax → owlready2 model + class-relation SPARQL."""
from .parser import ManchesterExpressionParser

__version__ = "0.0.1"
__all__ = ["parse_expression", "ManchesterExpressionParser"]


def parse_expression(text, onto, prefixes=None):
    """Parse a Manchester class expression into an owlready2 construct.

    Args:
        text: a Manchester class expression, e.g. "hasTopping some Cheese".
        onto: an owlready2 Ontology; referenced entities are created here (or in the
              namespace matching a full/prefixed IRI) if they do not already exist.
        prefixes: optional {prefix: namespace_iri} map. "" is the default prefix.
                  If omitted, simple names resolve against `onto.base_iri`.
    Returns:
        an owlready2 class expression (ThingClass, Restriction, And, Or, Not, OneOf, …).
    """
    if prefixes is None:
        prefixes = {"": onto.base_iri}
    parser = ManchesterExpressionParser(onto.world, onto, prefixes=prefixes)
    return parser.parse(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parse_expression.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite + commit**

Run: `.venv/bin/pytest -q`
Expected: all tests green.

```bash
git add pymos/__init__.py tests/test_parse_expression.py
git commit -m "feat: public parse_expression API"
```

---

## Done criteria for Plan 1

- `.venv/bin/pytest -q` is fully green.
- `pymos.parse_expression("hasTopping some (Cheese and not Vegetable)", onto)` returns a
  correctly-structured owlready2 object with all referenced entities created.
- The grammar is vendored with MIT attribution in `NOTICE`.

Plan 2 (frame/document loader) and Plan 3 (class-relation SPARQL converter) build on this.
