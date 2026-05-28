# Anonymous-Expression Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `class_relations_query` accept an anonymous owlready2 class construct as `target`, generating SPARQL that structurally matches the corresponding blank-node subgraph and binds a fresh variable to it.

**Architecture:** A new `pymos/pattern.py` module walks an owlready2 construct and emits a SPARQL graph pattern (plus the bound variable name). `pymos/sparql.py` renames `_target_iri` → `_target_term` and routes anonymous constructs through the new walker; the emitted structural pattern is prepended inside the WHERE clause so the bound variable substitutes for the named IRI in existing relation clauses. All matching is structural over the asserted graph (consistent with pymos's no-reasoner posture). Operand order is matched as declared.

**Tech Stack:** owlready2 (construct introspection), rdflib (test parsing/validation), pyoxigraph (e2e), pytest. Pure Python, no new dependencies.

---

## File Structure

```
pymos/
├── pattern.py          # NEW — expression_to_pattern(expr) -> (var_str, pattern_str)
└── sparql.py           # MODIFY — _target_iri renamed, anonymous-construct branch added
tests/
├── test_pattern.py     # NEW — unit tests per construct kind
├── test_sparql.py      # MODIFY — anonymous target produces correct query
└── test_e2e.py         # MODIFY — round-trip through three backends on pizza.omn
README.md               # MODIFY — caveats updated
```

Responsibilities:
- `pymos/pattern.py` — single public function; owns the walker and the fresh-variable counter. Knows nothing about the relation table.
- `pymos/sparql.py` — owns the query assembly; only consults pattern.py when the target is anonymous.

All commands below run from `/data/dumontier/pymos` with the venv active (`source .venv/bin/activate`).

---

### Task 1: Module skeleton + `R some C` (someValuesFrom)

**Files:**
- Create: `pymos/pattern.py`
- Create: `tests/test_pattern.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pattern.py`:

```python
import owlready2

import pymos
from pymos.pattern import expression_to_pattern


def _norm(s):
    return " ".join(s.split())


def _parse(expr_text):
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: treats
        ObjectProperty: hasTopping
        Class: Drug
        Class: Disease
        Class: Cheese
        Class: Tomato
    """)
    return onto, pymos.parse_expression(expr_text, onto)


def test_some_values_from():
    onto, expr = _parse("treats some Drug")
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Drug> ."
    )
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m pytest tests/test_pattern.py::test_some_values_from -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pymos.pattern'`.

- [ ] **Step 3: Implement minimal `pymos/pattern.py`**

Create `pymos/pattern.py`:

```python
"""Build SPARQL structural patterns from owlready2 anonymous class constructs.

The walker emits triple patterns that bind a fresh variable (``?t0``) to any blank
node whose outgoing structure matches the input construct. Used by
:func:`pymos.sparql.class_relations_query` when the target is an anonymous
expression rather than a named IRI.
"""
import owlready2


class _Walker:
    def __init__(self):
        self._counter = 0

    def fresh(self) -> str:
        v = f"?t{self._counter}"
        self._counter += 1
        return v

    def operand(self, op) -> tuple[str, str]:
        """Return (sparql_term, extra_pattern) for a single operand.

        Named entities (`.iri`) become ``<iri>`` with no extra pattern. Anonymous
        constructs recurse and contribute their structural pattern.
        """
        if hasattr(op, "iri"):
            return f"<{op.iri}>", ""
        var, pattern = self._walk(op)
        return var, pattern

    def _walk(self, expr) -> tuple[str, str]:
        if isinstance(expr, owlready2.Restriction):
            return self._restriction(expr)
        raise ValueError(
            f"anonymous target of type {type(expr).__name__} is not supported"
        )

    def _restriction(self, r: "owlready2.Restriction") -> tuple[str, str]:
        var = self.fresh()
        prop_iri = f"<{r.property.iri}>"
        if r.type == owlready2.SOME:
            filler_term, extra = self.operand(r.value)
            pattern = (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:someValuesFrom {filler_term} . "
                f"{extra}"
            )
            return var, pattern
        raise ValueError(
            f"restriction type {r.type} is not supported"
        )


def expression_to_pattern(expr) -> tuple[str, str]:
    """Return ``(var, pattern)`` for an anonymous owlready2 construct.

    *var* is the SPARQL variable bound to the matching blank node; *pattern* is
    a string of SPARQL triple patterns (no surrounding braces) ready to be
    inserted into a WHERE block.
    """
    return _Walker()._walk(expr)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `python -m pytest tests/test_pattern.py::test_some_values_from -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): scaffold expression_to_pattern with someValuesFrom"
```

---

### Task 2: `R only C`, `R value v`, `R Self`

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pattern.py`:

```python
def test_all_values_from():
    onto, expr = _parse("treats only Drug")
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:allValuesFrom <http://ex.org/Drug> ."
    )


def test_has_value_individual():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
        Individual: myCheese Types: Cheese
    """)
    expr = pymos.parse_expression("hasTopping value myCheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:hasValue <http://ex.org/myCheese> ."
    )


def test_self_restriction():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasPart
    """)
    expr = pymos.parse_expression("hasPart Self", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasPart> ; "
        "owl:hasSelf true ."
    )
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 3 fails (the new tests) — all with `restriction type N is not supported` for whichever type isn't yet wired up.

- [ ] **Step 3: Extend `_restriction` in `pymos/pattern.py`**

In `pymos/pattern.py`, replace the body of `_restriction` with:

```python
    def _restriction(self, r: "owlready2.Restriction") -> tuple[str, str]:
        var = self.fresh()
        prop_iri = f"<{r.property.iri}>"
        if r.type == owlready2.SOME:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:someValuesFrom {filler_term} . {extra}"
            )
        if r.type == owlready2.ONLY:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:allValuesFrom {filler_term} . {extra}"
            )
        if r.type == owlready2.VALUE:
            if not hasattr(r.value, "iri"):
                raise ValueError(
                    "hasValue with a literal target is not supported "
                    "(use a named individual)"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:hasValue <{r.value.iri}> ."
            )
        # Self: owlready2 represents Self by r.type == SOME with r.value is the
        # property itself; older versions used a separate signal. owlready2 0.46
        # serialises Self as owl:hasSelf "true"^^xsd:boolean. Probe by inspecting
        # the rdflib graph if behaviour differs. Here we match the documented
        # serialisation: any restriction whose type is SOME and whose value IS
        # the property is treated as Self by owlready2's parser, but pymos's
        # parse_expression sets r.type=SOME and r.value=property for Self too.
        # Detect Self via r.value being the same property object.
        raise ValueError(f"restriction type {r.type} is not supported")
```

Quick interactive check before adding Self handling:

```bash
python -c "
import pymos, owlready2 as o
onto = pymos.parse('Prefix: : <http://ex.org/>\nObjectProperty: hasPart')
e = pymos.parse_expression('hasPart Self', onto)
print(type(e).__name__, 'type=', e.type, 'value=', e.value, 'value is property?', e.value is onto.world['http://ex.org/hasPart'])
"
```

Use the printed `e.type` and `e.value` to extend `_restriction` accordingly. Likely outcome: `r.value is r.property` is the Self marker. If so, prepend this branch to the dispatcher (BEFORE the SOME branch, since Self uses SOME internally):

```python
        if r.value is r.property:
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:hasSelf true ."
            )
```

If the probe shows a different marker, branch on that instead — adjust the test's expected pattern to match what owlready2 actually serialises (check via `onto.world.as_rdflib_graph().serialize(format='turtle')` after asserting `Class: X EquivalentTo: hasPart Self` and inspecting the blank node).

- [ ] **Step 4: Run tests, verify all green**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): allValuesFrom, hasValue, Self restrictions"
```

---

### Task 3: Cardinality (min/max/exactly, qualified + unqualified)

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

owlready2 serialises:
- Unqualified (no filler): `[ a owl:Restriction; owl:onProperty <p>; owl:cardinality "N"^^xsd:nonNegativeInteger ]`
- Qualified (with filler): `[ a owl:Restriction; owl:onProperty <p>; owl:qualifiedCardinality "N"^^xsd:nonNegativeInteger; owl:onClass <C> ]`

(min/max use `owl:minCardinality` / `owl:maxCardinality` / `owl:minQualifiedCardinality` / `owl:maxQualifiedCardinality`.)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pattern.py`:

```python
def test_qualified_exactly():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
    """)
    expr = pymos.parse_expression("hasTopping exactly 2 Cheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:qualifiedCardinality \"2\"^^xsd:nonNegativeInteger ; "
        "owl:onClass <http://ex.org/Cheese> ."
    )


def test_unqualified_min():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasTopping
    """)
    expr = pymos.parse_expression("hasTopping min 1", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:minCardinality \"1\"^^xsd:nonNegativeInteger ."
    )


def test_qualified_max():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasTopping
        Class: Cheese
    """)
    expr = pymos.parse_expression("hasTopping max 3 Cheese", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/hasTopping> ; "
        "owl:maxQualifiedCardinality \"3\"^^xsd:nonNegativeInteger ; "
        "owl:onClass <http://ex.org/Cheese> ."
    )
```

Before writing patterns, run a probe to confirm how owlready2 distinguishes qualified from unqualified at the Python level:

```bash
python -c "
import pymos, owlready2 as o
onto = pymos.parse('Prefix: : <http://ex.org/>\nObjectProperty: p\nClass: C')
e_q = pymos.parse_expression('p exactly 2 C', onto)
e_u = pymos.parse_expression('p min 1', onto)
print('qualified:', e_q.type, e_q.cardinality, 'value=', e_q.value)
print('unqualified:', e_u.type, e_u.cardinality, 'value=', e_u.value)
"
```

Expected: qualified `r.value` is the named class `C` (or another anonymous construct); unqualified `r.value` is `owlready2.Thing` (or None). The distinction in code: `r.value is owlready2.Thing` (or `r.value is None`) → unqualified.

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 3 new tests fail with "restriction type N is not supported".

- [ ] **Step 3: Extend `_restriction` with cardinality handling**

Add this block to `_restriction` in `pymos/pattern.py` BEFORE the final `raise ValueError`:

```python
        CARD_MAP = {
            owlready2.MIN: ("owl:minCardinality", "owl:minQualifiedCardinality"),
            owlready2.MAX: ("owl:maxCardinality", "owl:maxQualifiedCardinality"),
            owlready2.EXACTLY: ("owl:cardinality", "owl:qualifiedCardinality"),
        }
        if r.type in CARD_MAP:
            n = int(r.cardinality)
            n_lit = f"\"{n}\"^^xsd:nonNegativeInteger"
            qualified = not (r.value is owlready2.Thing or r.value is None)
            unq_pred, q_pred = CARD_MAP[r.type]
            if qualified:
                filler_term, extra = self.operand(r.value)
                return var, (
                    f"{var} a owl:Restriction ; "
                    f"owl:onProperty {prop_iri} ; "
                    f"{q_pred} {n_lit} ; "
                    f"owl:onClass {filler_term} . {extra}"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"{unq_pred} {n_lit} ."
            )
```

`xsd:` prefix must already be declared in `pymos.vocab.prefix_header()`. (It is — pymos already emits xsd in its prefix header per [pymos/vocab.py](pymos/vocab.py).) Pattern strings embed prefixed forms that resolve against that header at query time.

If the probe in Step 1 showed a different qualified/unqualified marker (e.g. `r.value is None`), adjust the `qualified = ...` line to match.

- [ ] **Step 4: Run tests, verify all green**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 7/7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): cardinality restrictions (qualified + unqualified)"
```

---

### Task 4: Intersection (`A and B [and …]`)

owlready2 emits `[ a owl:Class; owl:intersectionOf ( <A> <B> … ) ]`; the `( … )` is an `rdf:List` (blank-node chain of `rdf:first`/`rdf:rest` terminated by `rdf:nil`).

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pattern.py`:

```python
def test_intersection_two_named():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Class: A
        Class: B
    """)
    expr = pymos.parse_expression("A and B", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:intersectionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/A> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/B> ; rdf:rest rdf:nil ."
    )


def test_intersection_named_and_anonymous():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
        Class: Disease
    """)
    expr = pymos.parse_expression("Drug and (treats some Disease)", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    # ?t0 is the intersection node, ?t1 / ?t2 are the list spine,
    # ?t3 is the nested someValuesFrom restriction.
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:intersectionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/Drug> ; rdf:rest ?t2 . "
        "?t2 rdf:first ?t3 ; rdf:rest rdf:nil . "
        "?t3 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Disease> ."
    )
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 2 fails — `anonymous target of type And is not supported`.

- [ ] **Step 3: Add `And` handling**

Add a helper and an `And` branch in `pymos/pattern.py`:

```python
    def _list_pattern(self, items) -> tuple[str, str]:
        """Return (head_var, pattern) for an rdf:List of operands."""
        head = self.fresh()
        triples = []
        current = head
        for i, item in enumerate(items):
            item_term, extra = self.operand(item)
            if i < len(items) - 1:
                nxt = self.fresh()
                triples.append(
                    f"{current} rdf:first {item_term} ; rdf:rest {nxt} ."
                )
                if extra:
                    triples.append(extra)
                current = nxt
            else:
                triples.append(
                    f"{current} rdf:first {item_term} ; rdf:rest rdf:nil ."
                )
                if extra:
                    triples.append(extra)
        return head, " ".join(triples)
```

Modify `_walk` to dispatch `And` before raising:

```python
    def _walk(self, expr) -> tuple[str, str]:
        if isinstance(expr, owlready2.Restriction):
            return self._restriction(expr)
        if isinstance(expr, owlready2.And):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.Classes)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:intersectionOf {list_head} . "
                f"{list_triples}"
            )
        raise ValueError(
            f"anonymous target of type {type(expr).__name__} is not supported"
        )
```

- [ ] **Step 4: Run tests, verify all green**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 9/9 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): intersectionOf with rdf:List operand chain"
```

---

### Task 5: Union (`A or B [or …]`)

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_pattern.py`:

```python
def test_union_two_named():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Class: A
        Class: B
    """)
    expr = pymos.parse_expression("A or B", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:unionOf ?t1 . "
        "?t1 rdf:first <http://ex.org/A> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/B> ; rdf:rest rdf:nil ."
    )
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_pattern.py::test_union_two_named -v`
Expected: FAIL — `anonymous target of type Or is not supported`.

- [ ] **Step 3: Add `Or` branch**

In `pymos/pattern.py`, add to `_walk` (after `And` branch):

```python
        if isinstance(expr, owlready2.Or):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.Classes)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:unionOf {list_head} . "
                f"{list_triples}"
            )
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 10/10 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): unionOf with rdf:List operand chain"
```

---

### Task 6: Complement (`not A`)

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pattern.py`:

```python
def test_complement_named():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Class: A
    """)
    expr = pymos.parse_expression("not A", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:complementOf <http://ex.org/A> ."
    )


def test_complement_anonymous():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
    """)
    expr = pymos.parse_expression("not (treats some Drug)", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:complementOf ?t1 . "
        "?t1 a owl:Restriction ; "
        "owl:onProperty <http://ex.org/treats> ; "
        "owl:someValuesFrom <http://ex.org/Drug> ."
    )
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 2 new fails.

- [ ] **Step 3: Add `Not` branch**

In `pymos/pattern.py`, add to `_walk`:

```python
        if isinstance(expr, owlready2.Not):
            var = self.fresh()
            operand_term, extra = self.operand(expr.Class)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:complementOf {operand_term} . {extra}"
            )
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 12/12 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): complementOf"
```

---

### Task 7: Enumeration (`{a, b, …}`)

owlready2 serialises `{a, b}` as `[ a owl:Class; owl:oneOf ( <a> <b> ) ]`. The owlready2 construct is `owlready2.OneOf` with `.instances` listing the named individuals.

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_pattern.py`:

```python
def test_one_of():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        Class: Cheese
        Class: Tomato
        Individual: a Types: Cheese
        Individual: b Types: Tomato
    """)
    expr = pymos.parse_expression("{a, b}", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    assert _norm(pattern) == _norm(
        "?t0 a owl:Class ; "
        "owl:oneOf ?t1 . "
        "?t1 rdf:first <http://ex.org/a> ; rdf:rest ?t2 . "
        "?t2 rdf:first <http://ex.org/b> ; rdf:rest rdf:nil ."
    )
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_pattern.py::test_one_of -v`
Expected: FAIL — `anonymous target of type OneOf is not supported`.

- [ ] **Step 3: Add `OneOf` branch**

In `pymos/pattern.py`, add to `_walk`:

```python
        if isinstance(expr, owlready2.OneOf):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.instances)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:oneOf {list_head} . "
                f"{list_triples}"
            )
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 13/13 PASS.

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): oneOf enumeration"
```

---

### Task 8: Inverse property in restrictions (`inverse R some C`)

owlready2 represents an inverse property as `owlready2.Inverse(P)`, which does NOT have an `.iri` attribute (the previous probe confirmed this). In RDF it serialises as `[ owl:inverseOf <P> ]` — a fresh blank node typed implicitly.

**Files:**
- Modify: `pymos/pattern.py`
- Modify: `tests/test_pattern.py`

- [ ] **Step 1: Add failing test**

First confirm owlready2's exact serialisation:

```bash
python -c "
import pymos
onto = pymos.parse('Prefix: : <http://ex.org/>\nObjectProperty: hasPart\nClass: A\nClass: B EquivalentTo: inverse hasPart some A')
print(onto.world.as_rdflib_graph().serialize(format='turtle'))
"
```

Expected: the blank-node restriction's `owl:onProperty` points at another blank node `[ owl:inverseOf <http://ex.org/hasPart> ]`. If the serialisation differs, adjust the test expectation below to match the actual triples observed.

Append to `tests/test_pattern.py`:

```python
def test_inverse_property_some():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: hasPart
        Class: A
    """)
    expr = pymos.parse_expression("inverse hasPart some A", onto)
    var, pattern = expression_to_pattern(expr)
    assert var == "?t0"
    # ?t1 is the inverse-property blank node.
    assert _norm(pattern) == _norm(
        "?t0 a owl:Restriction ; "
        "owl:onProperty ?t1 ; "
        "owl:someValuesFrom <http://ex.org/A> . "
        "?t1 owl:inverseOf <http://ex.org/hasPart> ."
    )
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_pattern.py::test_inverse_property_some -v`
Expected: FAIL — probably `AttributeError: 'Inverse' object has no attribute 'iri'` when `_restriction` builds `prop_iri`.

- [ ] **Step 3: Add inverse-property handling**

In `pymos/pattern.py`, replace the `prop_iri = ...` line in `_restriction` with a helper call, and add the helper:

```python
    def _property_term(self, prop) -> tuple[str, str]:
        """Return (sparql_term, extra_pattern) for a property in onProperty position.

        A named property becomes ``<iri>`` with no extra. An inverse property
        becomes a fresh blank-node variable with an ``owl:inverseOf`` triple.
        """
        if hasattr(prop, "iri"):
            return f"<{prop.iri}>", ""
        if isinstance(prop, owlready2.Inverse):
            var = self.fresh()
            return var, f"{var} owl:inverseOf <{prop.property.iri}> ."
        raise ValueError(
            f"unsupported property kind: {type(prop).__name__}"
        )
```

Then in `_restriction`, replace `prop_iri = f"<{r.property.iri}>"` with:

```python
        prop_term, prop_extra = self._property_term(r.property)
```

…and append `{prop_extra}` to the end of every returned pattern in `_restriction` (i.e., `… owl:someValuesFrom {filler_term} . {extra} {prop_extra}` etc.). Use `prop_term` everywhere `prop_iri` was used.

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: 14/14 PASS (the new test plus all earlier ones — make sure the older tests still pass; the `{prop_extra}` for named properties is the empty string so existing patterns are unchanged after whitespace normalisation).

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "feat(pattern): inverse-property restrictions"
```

---

### Task 9: Integration — wire `expression_to_pattern` into `class_relations_query`

**Files:**
- Modify: `pymos/sparql.py`
- Modify: `tests/test_sparql.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_sparql.py`:

```python
import pymos
from pymos.sparql import _target_term


def test_target_term_named_string():
    var, extra = _target_term("<http://ex.org/Pizza>")
    assert var == "<http://ex.org/Pizza>"
    assert extra == ""


def test_target_term_owlready_entity():
    onto = pymos.parse("Prefix: : <http://ex.org/>\nClass: Pizza")
    pizza = onto.world["http://ex.org/Pizza"]
    var, extra = _target_term(pizza)
    assert var == "<http://ex.org/Pizza>"
    assert extra == ""


def test_target_term_anonymous_construct():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
    """)
    expr = pymos.parse_expression("treats some Drug", onto)
    var, extra = _target_term(expr)
    assert var.startswith("?t")
    assert "owl:Restriction" in extra
    assert "owl:someValuesFrom <http://ex.org/Drug>" in extra


def test_anonymous_target_query_builds_and_parses():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        ObjectProperty: treats
        Class: Drug
        Class: Disease
    """)
    expr = pymos.parse_expression("Drug and (treats some Disease)", onto)
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    # Generated SPARQL must parse.
    from rdflib.plugins.sparql import prepareQuery
    prepareQuery(q)
    # The structural pattern must be present (the target var binds the intersection node).
    assert "owl:intersectionOf" in q
    assert "owl:someValuesFrom <http://ex.org/Disease>" in q
    # And the equiv clause must use the bound variable, not a literal IRI.
    assert "?t0 owl:equivalentClass" in q or "owl:equivalentClass ?t0" in q


def test_unsupported_target_type_raises():
    import pytest
    with pytest.raises(TypeError):
        class_relations_query(12345, relations=("equiv",))
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_sparql.py -v`
Expected: the 5 new tests fail — `_target_term` doesn't exist and `class_relations_query` doesn't accept constructs.

- [ ] **Step 3: Refactor `pymos/sparql.py`**

Open [pymos/sparql.py](pymos/sparql.py). Replace the existing `_target_iri` function and the body of `class_relations_query` with:

```python
def _target_term(target) -> tuple[str, str]:
    """Normalise *target* to ``(sparql_term, extra_pattern)``.

    *sparql_term* is what substitutes into relation clauses (a ``<iri>``, a
    ``?var`` reference, or a prefixed name). *extra_pattern* is a string of
    SPARQL triple patterns that must appear in the WHERE block to bind the
    variable (empty for named targets).

    Accepts:

    - Full IRI ``"<http://ex.org/Pizza>"`` → returned as-is.
    - Full IRI without brackets ``"http://ex.org/Pizza"`` → wrapped in ``<>``.
    - A SPARQL variable ``"?cls"`` → returned as-is.
    - An owlready2 named entity (anything with ``.iri``) → ``<entity.iri>``.
    - An owlready2 anonymous construct (``Restriction``, ``And``, ``Or``,
      ``Not``, ``OneOf``) → walked via :func:`pymos.pattern.expression_to_pattern`
      to produce a fresh variable and a structural pattern.
    - A prefixed name like ``"ex:Pizza"`` → passed through (the prefix must be
      declared in the query header).
    """
    from pymos.pattern import expression_to_pattern  # local import; avoids cycle

    if hasattr(target, "iri"):
        return f"<{target.iri}>", ""
    if isinstance(target, str):
        t = target.strip()
        if t.startswith("<") or t.startswith("?"):
            return t, ""
        if t.startswith("http"):
            return f"<{t}>", ""
        return t, ""
    # Anonymous owlready2 construct?
    import owlready2
    if isinstance(target, (owlready2.Restriction, owlready2.And,
                           owlready2.Or, owlready2.Not, owlready2.OneOf)):
        return expression_to_pattern(target)
    raise TypeError(
        f"unsupported target type for class_relations_query: {type(target).__name__}"
    )
```

Then update `class_relations_query` (around line 99-131) — change the line `c = _target_iri(target)` to:

```python
    c, target_pattern = _target_term(target)
```

…and update the WHERE-assembly tail (replace the final return statement) so the structural pattern is prepended once inside the WHERE block (it must be visible to all UNION arms; SPARQL UNION arms inherit bindings from outside their braces):

```python
    where = " UNION ".join(blocks)
    if target_pattern:
        where = f"{target_pattern} {where}"
    head = "CONSTRUCT { ?s ?p ?o }" if construct else (
        "SELECT DISTINCT ?rel ?ind" if want_individual and class_rels
        else "SELECT DISTINCT ?ind" if want_individual else "SELECT DISTINCT ?rel")
    return f"{prefix_header()}\n{head}\nWHERE {{\n{where}\n}}"
```

Update the function docstring's `target:` section to reflect anonymous-construct support and remove the line "Anonymous-expression targets are not supported; ``target`` must resolve to a named IRI or SPARQL variable." Replace it with:

```
- An owlready2 anonymous construct (``Restriction``, ``And``, ``Or``,
  ``Not``, ``OneOf``) — the query is built with a structural pattern that
  binds a fresh variable to any blank node whose outgoing structure matches.
  Operand order is matched as declared; permutations of intersection/union
  operands do not match.
```

Also remove the existing line `* Anonymous-expression targets are not supported; ``target`` must resolve to a named IRI or SPARQL variable.` from the Notes section.

- [ ] **Step 4: Run all tests, verify green**

Run: `python -m pytest -q`
Expected: 109 + 14 (pattern) + 5 (new sparql) = **128** passing. All existing tests still pass because `_target_term` returns the same `("<iri>", "")` shape for named inputs.

- [ ] **Step 5: Commit**

```bash
git add pymos/sparql.py tests/test_sparql.py
git commit -m "feat(sparql): accept anonymous owlready2 constructs as query target"
```

---

### Task 10: End-to-end across three runners

**Files:**
- Modify: `tests/test_e2e.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_e2e.py`:

```python
from pathlib import Path


def _pizza_onto():
    text = Path("tests/data/pizza.omn").read_text()
    return pymos.parse(text)


def _pyox_store(onto):
    nt = onto.world.as_rdflib_graph().serialize(format="nt").encode()
    store = pyoxigraph.Store()
    store.load(io.BytesIO(nt), format=pyoxigraph.RdfFormat.N_TRIPLES)
    return store


def test_anonymous_equiv_finds_named_class_rdflib():
    onto = _pizza_onto()
    # Margherita EquivalentTo: hasTopping only (Cheese or Tomato)
    expr = pymos.parse_expression("hasTopping only (Cheese or Tomato)", onto)
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    rows = {str(r[0]) for r in run_rdflib(q, onto.world.as_rdflib_graph())}
    assert "http://ex.org/Margherita" in rows


def test_anonymous_equiv_finds_named_class_pyoxigraph():
    onto = _pizza_onto()
    expr = pymos.parse_expression("hasTopping only (Cheese or Tomato)", onto)
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    store = _pyox_store(onto)
    rows = {str(s["rel"]).strip("<>") for s in run_pyoxigraph(q, store)}
    assert "http://ex.org/Margherita" in rows


def test_anonymous_equiv_owlready2_select():
    onto = _pizza_onto()
    expr = pymos.parse_expression("hasTopping only (Cheese or Tomato)", onto)
    q = class_relations_query(expr, relations=("equiv",), construct=False)
    from pymos.store import run_owlready2
    rows = {r[0].iri for r in run_owlready2(q, onto.world)}
    assert "http://ex.org/Margherita" in rows
```

**Pre-check:** confirm `tests/data/pizza.omn` actually contains the `Margherita EquivalentTo: hasTopping only (Cheese or Tomato)` axiom verbatim:

```bash
grep -A1 "Margherita" tests/data/pizza.omn
```

If `Margherita`'s `EquivalentTo:` line differs, replace the test expression with whatever the file actually defines for some named class, and adjust the assertion accordingly. The test contract is: "for an axiom `X EquivalentTo: <expr>` in the loaded ontology, querying `equiv` of `<expr>` returns `X`."

- [ ] **Step 2: Run, verify fail OR see what happens**

Run: `python -m pytest tests/test_e2e.py -v`
Expected: 3 new tests run. Most likely outcomes:
- If they fail because no class matched: print the generated query and inspect whether the structural pattern matches the actual blank-node form owlready2 wrote (`onto.world.as_rdflib_graph().serialize(format='turtle')`). The discrepancy is informative — adjust the *pattern emitter*, not the test (the test only encodes the documented contract).
- If they pass on first try: great. Continue.

If `run_owlready2` fails on the structural pattern (owlready2's SPARQL engine is limited), document it: the existing notes already say `run_owlready2` cannot run CONSTRUCT; if it also struggles with the structural blank-node patterns we now emit for SELECT, mark `test_anonymous_equiv_owlready2_select` as `@pytest.mark.xfail(reason="owlready2 engine doesn't bind blank-node patterns for anonymous targets; use rdflib runner")` and add a note to the README/spec covering this constraint. Do this only after confirming via direct experiment — do not pre-emptively xfail.

- [ ] **Step 3: Iterate until green**

If the pattern emitter needs adjustment, update `pymos/pattern.py` and run unit tests + e2e. Possible cause: extra triples owlready2 writes that I missed (e.g. an `a owl:Class` on intersection nodes — already covered) or surface syntax (`true` vs `"true"^^xsd:boolean` for hasSelf).

Re-run: `python -m pytest -q`
Expected: all tests pass (with at most one documented xfail for owlready2's SPARQL limitation).

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py
# Plus any pattern.py adjustments made during iteration
git commit -m "test(e2e): anonymous-target equiv resolves to named class on three runners"
```

If a runner xfail was added:
```bash
git add pymos/pattern.py tests/test_e2e.py README.md
git commit -m "test(e2e): anonymous-target equiv (rdflib + pyoxigraph; owlready2 xfail)"
```

---

### Task 11: Error handling tests

**Files:**
- Modify: `tests/test_pattern.py`
- Modify: `tests/test_sparql.py` (already touched in Task 9; this adds focused tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pattern.py`:

```python
import pytest


def test_unsupported_construct_raises_value_error():
    # ConstrainedDatatype (data range) is deferred per the spec.
    import owlready2
    cd = owlready2.ConstrainedDatatype(int, min_inclusive=0, max_inclusive=10)
    with pytest.raises(ValueError, match="not supported"):
        expression_to_pattern(cd)


def test_has_value_with_literal_raises():
    onto = pymos.parse("""
        Prefix: : <http://ex.org/>
        DataProperty: age
    """)
    expr = pymos.parse_expression("age value 42", onto)
    with pytest.raises(ValueError, match="literal"):
        expression_to_pattern(expr)
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_pattern.py -k "unsupported or literal" -v`
Expected: 2 fails — currently the unsupported types raise different errors / wrong messages.

- [ ] **Step 3: Verify the existing error messages already match**

The implementation from Tasks 1–8 already raises:
- `ValueError("anonymous target of type X is not supported")` for unknown constructs.
- `ValueError("hasValue with a literal target is not supported …")` for literal hasValue.

If the tests still fail, check whether `pymos.parse_expression("age value 42", ...)` actually produces an owlready2 Restriction with a literal value (the parser may interpret `42` differently). Inspect with:

```bash
python -c "
import pymos
onto = pymos.parse('Prefix: : <http://ex.org/>\nDataProperty: age')
e = pymos.parse_expression('age value 42', onto)
print(type(e), 'value=', repr(e.value), 'value has iri?', hasattr(e.value, 'iri'))
"
```

If the literal-detection path isn't hit (e.g. owlready2 wraps `42` in something with `.iri`), adjust `_restriction`'s VALUE branch: the test of `not hasattr(r.value, 'iri')` may need to also check `isinstance(r.value, (int, float, str, bool))` to catch raw Python literals. Update the implementation to match what the probe shows.

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_pattern.py -v`
Expected: all pattern tests green (16 total).

- [ ] **Step 5: Commit**

```bash
git add pymos/pattern.py tests/test_pattern.py
git commit -m "test(pattern): error handling for unsupported targets and literal hasValue"
```

---

### Task 12: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current caveats section**

```bash
grep -n "Named-class\|asserted graph\|Anonymous" README.md
```

Note the line numbers of:
- "Named-class / IRI targets only." caveat (must be REMOVED)
- The "Asserted graph only" caveat (preserved; only structural matching depends on it)

- [ ] **Step 2: Edit README.md**

Remove the entire "Named-class / IRI targets only." bullet from the Caveats section.

Add a new section just after the Relation table titled `## Anonymous expression targets`, with this content:

```markdown
## Anonymous expression targets

`class_relations_query` accepts an anonymous Manchester class expression
as its target — parse it first with `parse_expression`:

```python
import pymos
from pymos import class_relations_query
from pymos.store import run_rdflib

onto = pymos.parse(open("pizza.omn").read())
expr = pymos.parse_expression("hasTopping only (Cheese or Tomato)", onto)
q = class_relations_query(expr, relations=("equiv",), construct=False)
print([str(r[0]) for r in run_rdflib(q, onto.world.as_rdflib_graph())])
# ['http://ex.org/Margherita']
```

The generated SPARQL contains a structural sub-pattern that matches the
blank-node shape owlready2 writes for the expression, binding a fresh
variable to any matching node. The relation clauses then use that
variable.

**Limitations:**

- **Operand order is matched as declared.** Two structurally equivalent
  expressions with permuted intersection/union operands do not match each
  other. (Future enhancement.)
- **Structural identity only.** With no reasoning, semantically equivalent
  but structurally distinct expressions do not match.
- **Data ranges (`ConstrainedDatatype`) and literal `hasValue` targets are
  not yet supported as the top-level target.** Use a named individual
  (`hasTopping value myCheese`) instead.
```

- [ ] **Step 3: Verify the change rendered correctly**

Run: `grep -n "Anonymous expression\|Named-class" README.md`
Expected: shows the new `## Anonymous expression targets` heading; no more "Named-class / IRI targets only" line.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document anonymous-expression targets and limitations"
```

---

## Self-Review Notes

- **Spec coverage:** structural-match approach (Tasks 1–8 build the walker); API accepting owlready2 construct (Task 9 wires it in); all listed construct kinds covered (Task 1=some, 2=only/value/Self, 3=cardinality, 4=intersection, 5=union, 6=complement, 7=oneOf, 8=inverse); end-to-end on three runners (Task 10); error handling for unsupported / literal hasValue (Task 11); README caveats update (Task 12). All spec sections map to a task.
- **Type consistency:** `expression_to_pattern(expr) → (var, pattern)` (tuple of two strings) used identically by every test and by `_target_term` in Task 9. `_target_term` consistently returns `(sparql_term, extra_pattern)` — the prepend pattern is empty string for named inputs and non-empty for anonymous ones. The single `_Walker` instance per call guarantees fresh variable names across nested recursion.
- **No placeholders:** every step has full code or an exact command. The two places where the plan depends on runtime probes (Self detection in Task 2, qualified/unqualified marker in Task 3, exact inverse serialisation in Task 8, literal-hasValue detection in Task 11) include the probe command and exactly which line to update from the result — they are not TBDs.
- **Known risk:** owlready2's built-in SPARQL engine may not support blank-node patterns the way rdflib/pyoxigraph do. Task 10 documents the mitigation: confirm empirically, xfail with a clear reason if needed. Do NOT pre-emptively xfail.
