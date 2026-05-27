# pymos Demonstration Notebooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained `examples/` directory of three Jupyter notebooks that demonstrate pymos, runnable with a single `docker compose up`, including a live Oxigraph triplestore service.

**Architecture:** A `notebook` service (JupyterLab built on python:3.12-slim, pymos installed editable from the mounted repo with all extras) and a `triplestore` service (Oxigraph SPARQL server) share a compose network. Notebooks are authored as jupytext percent-format `.py` sources (clean diffs, plannable code) and converted to committed `.ipynb` deliverables. A hand-written biomedical Manchester ontology drives notebooks 02 and 03.

**Tech Stack:** Docker Compose, JupyterLab, jupytext, python:3.12-slim, Oxigraph server, pymos (parsimonious + owlready2 + rdflib + pyoxigraph + SPARQLWrapper).

---

## File Structure

```
pymos/examples/
├── docker-compose.yml          # notebook + triplestore services
├── Dockerfile                  # JupyterLab + jupytext + pymos extras
├── README.md                   # launch instructions + notebook summaries
├── jupytext.toml               # pair .py percent <-> .ipynb
├── data/
│   └── biomed.omn              # hand-written biomedical Manchester ontology
├── tests/
│   └── test_biomed.py          # validates biomed.omn parses + relations
└── notebooks/
    ├── 01_parsing.py           # jupytext source
    ├── 01_parsing.ipynb        # generated deliverable
    ├── 02_class_relations.py
    ├── 02_class_relations.ipynb
    ├── 03_remote_endpoint.py
    └── 03_remote_endpoint.ipynb
```

**Responsibilities:**
- `data/biomed.omn` — the single example ontology; multi-level class hierarchy + restrictions + individuals.
- `tests/test_biomed.py` — guards that the ontology parses and yields the relations the notebooks rely on.
- `Dockerfile` — reproducible JupyterLab environment with pymos editable + extras + jupytext.
- `docker-compose.yml` — wires notebook + triplestore on a shared network.
- `notebooks/*.py` — source of truth; `notebooks/*.ipynb` — committed rendered deliverable.

All commands below run from the repo root `/data/dumontier/pymos` unless stated otherwise.

---

### Task 1: Biomedical example ontology

**Files:**
- Create: `examples/data/biomed.omn`
- Test: `examples/tests/test_biomed.py`

- [ ] **Step 1: Write the failing test**

Create `examples/tests/test_biomed.py`:

```python
from pathlib import Path

import pymos
from pymos import class_relations_query
from pymos.store import run_owlready2

OMN = Path(__file__).resolve().parents[1] / "data" / "biomed.omn"
NS = "http://example.org/biomed#"


def _load():
    return pymos.parse(OMN.read_text())


def _select_iris(onto, target, relations):
    q = class_relations_query(f"<{target}>", relations=relations, construct=False)
    return {str(r[0]) for r in run_owlready2(q, onto.world)}


def test_classes_present():
    onto = _load()
    for local in ("Disease", "InfectiousDisease", "BacterialInfection",
                  "ViralInfection", "GeneticDisease", "Drug", "Antibiotic",
                  "Antiviral", "Gene", "BiologicalEntity", "ChemicalEntity"):
        assert onto.world[NS + local] is not None, local


def test_disease_subclasses():
    onto = _load()
    subs = _select_iris(onto, NS + "Disease", ("sub",))
    assert {NS + "InfectiousDisease", NS + "BacterialInfection",
            NS + "ViralInfection", NS + "GeneticDisease"} <= subs


def test_disease_direct_subclasses():
    onto = _load()
    direct = _select_iris(onto, NS + "Disease", ("direct_sub",))
    assert NS + "InfectiousDisease" in direct
    assert NS + "GeneticDisease" in direct
    assert NS + "BacterialInfection" not in direct  # grandchild, filtered out


def test_disease_superclasses():
    onto = _load()
    supers = _select_iris(onto, NS + "Disease", ("super",))
    assert NS + "BiologicalEntity" in supers


def test_bacterial_infection_individual():
    onto = _load()
    inds = _select_iris(onto, NS + "BacterialInfection", ("individual",))
    assert NS + "strep_throat" in inds


def test_antibiotic_equivalent_restriction():
    onto = _load()
    antibiotic = onto.world[NS + "Antibiotic"]
    # EquivalentTo restriction is present (anonymous class expression)
    assert len(antibiotic.equivalent_to) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest examples/tests/test_biomed.py -q`
Expected: FAIL — file `examples/data/biomed.omn` does not exist (FileNotFoundError).

- [ ] **Step 3: Write the ontology**

Create `examples/data/biomed.omn`:

```
Prefix: : <http://example.org/biomed#>
Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>

Ontology: <http://example.org/biomed>

AnnotationProperty: rdfs:label

ObjectProperty: treats
    Domain: Drug
    Range: Disease

ObjectProperty: causes

ObjectProperty: associatedWith

ObjectProperty: hasTarget

Class: BiologicalEntity
    Annotations: rdfs:label "Biological Entity"

Class: ChemicalEntity
    Annotations: rdfs:label "Chemical Entity"

Class: Disease
    Annotations: rdfs:label "Disease"
    SubClassOf: BiologicalEntity

Class: InfectiousDisease
    Annotations: rdfs:label "Infectious Disease"
    SubClassOf: Disease

Class: BacterialInfection
    Annotations: rdfs:label "Bacterial Infection"
    SubClassOf: InfectiousDisease

Class: ViralInfection
    Annotations: rdfs:label "Viral Infection"
    SubClassOf: InfectiousDisease

Class: GeneticDisease
    Annotations: rdfs:label "Genetic Disease"
    SubClassOf: Disease

Class: Gene
    Annotations: rdfs:label "Gene"
    SubClassOf: BiologicalEntity

Class: Drug
    Annotations: rdfs:label "Drug"
    SubClassOf: ChemicalEntity

Class: Antibiotic
    Annotations: rdfs:label "Antibiotic"
    SubClassOf: Drug
    EquivalentTo: Drug and (treats some BacterialInfection)

Class: Antiviral
    Annotations: rdfs:label "Antiviral"
    SubClassOf: Drug
    EquivalentTo: Drug and (treats some ViralInfection)

Individual: amoxicillin
    Types: Antibiotic

Individual: strep_throat
    Types: BacterialInfection

Individual: influenza
    Types: ViralInfection

Individual: oseltamivir
    Types: Antiviral
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest examples/tests/test_biomed.py -q`
Expected: PASS (6 passed). If `test_antibiotic_equivalent_restriction` fails, inspect with `python -c "import pymos,pathlib; o=pymos.parse(pathlib.Path('examples/data/biomed.omn').read_text()); print(o.world['http://example.org/biomed#Antibiotic'].equivalent_to)"` and adjust the ontology, not the test.

- [ ] **Step 5: Commit**

```bash
git add examples/data/biomed.omn examples/tests/test_biomed.py
git commit -m "feat(examples): biomedical Manchester ontology + validation test"
```

---

### Task 2: JupyterLab Dockerfile

**Files:**
- Create: `examples/Dockerfile`
- Create: `examples/jupytext.toml`

- [ ] **Step 1: Write the jupytext pairing config**

Create `examples/jupytext.toml`:

```toml
# Pair every notebook with a percent-format .py script in the same folder.
formats = "ipynb,py:percent"
```

- [ ] **Step 2: Write the Dockerfile**

Create `examples/Dockerfile`:

```dockerfile
FROM python:3.12-slim

# System deps: git is needed by some owlready2 paths; build-essential is a safety
# net for any wheel that lacks a manylinux build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

# JupyterLab + jupytext + an HTTP client for the remote-endpoint notebook.
RUN pip install --no-cache-dir jupyterlab==4.* jupytext==1.* requests

WORKDIR /workspace

# pymos is installed editable at container start (see compose command), because
# the repo is bind-mounted. We pre-install the heavy extras here so startup is fast.
RUN pip install --no-cache-dir \
    "parsimonious>=0.10" "owlready2>=0.46" \
    "rdflib>=7.0" "pyoxigraph>=0.4" "SPARQLWrapper>=2.0"

EXPOSE 8888

# Install pymos editable, then launch JupyterLab with no token (demo only).
# NOTE: do NOT run `jupytext --sync` here — the .ipynb files are committed WITH
# executed outputs (Task 8), and a startup sync from the output-less .py would
# blank them. The jupytext.toml pairing handles sync when editing inside Jupyter.
CMD ["bash", "-lc", "pip install -e . && jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --ServerApp.token='' --ServerApp.password='' --notebook-dir=/workspace"]
```

- [ ] **Step 3: Build the image to verify it compiles**

Run: `docker build -t pymos-notebook -f examples/Dockerfile examples/`
Expected: build succeeds; final layer creates the CMD. (Build uses the rootless daemon's proxy config automatically.)

- [ ] **Step 4: Verify the toolchain inside the image**

Run: `docker run --rm pymos-notebook bash -lc "python -c 'import rdflib, pyoxigraph, owlready2, parsimonious, SPARQLWrapper; import jupytext; print(\"ok\")'"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add examples/Dockerfile examples/jupytext.toml
git commit -m "feat(examples): JupyterLab Dockerfile + jupytext pairing"
```

---

### Task 3: Docker Compose with Oxigraph triplestore

**Files:**
- Create: `examples/docker-compose.yml`

- [ ] **Step 1: Write the compose file**

Create `examples/docker-compose.yml`:

```yaml
services:
  notebook:
    build:
      context: .
      dockerfile: Dockerfile
    working_dir: /workspace
    volumes:
      # Mount the repo root so `pip install -e .` targets the live working copy.
      - ..:/workspace
    ports:
      - "8888:8888"
    depends_on:
      - triplestore

  triplestore:
    image: ghcr.io/oxigraph/oxigraph:latest
    command: ["serve", "--location", "/data", "--bind", "0.0.0.0:7878"]
    ports:
      - "7878:7878"
```

Notes: the notebook container reaches the triplestore at `http://triplestore:7878`
over the shared default compose network. The host can reach JupyterLab at
`http://localhost:8888` and the SPARQL endpoint at `http://localhost:7878`.

- [ ] **Step 2: Validate compose config**

Run: `docker compose -f examples/docker-compose.yml config`
Expected: prints the resolved config with both `notebook` and `triplestore` services, no errors.

- [ ] **Step 3: Bring up the triplestore alone and probe it**

Run:
```bash
docker compose -f examples/docker-compose.yml up -d triplestore
sleep 5
curl -s "http://localhost:7878/query?query=ASK%7B%7D"
```
Expected: a SPARQL JSON/XML response containing `true` (an `ASK {}` is always true). If `curl` is unavailable, use `docker run --rm --network container:$(docker compose -f examples/docker-compose.yml ps -q triplestore) curlimages/curl -s "http://localhost:7878/query?query=ASK%7B%7D"`.

- [ ] **Step 4: Tear down**

Run: `docker compose -f examples/docker-compose.yml down`
Expected: both services removed.

- [ ] **Step 5: Commit**

```bash
git add examples/docker-compose.yml
git commit -m "feat(examples): docker compose with notebook + oxigraph triplestore"
```

---

### Task 4: Notebook 01 — Parsing Manchester syntax

**Files:**
- Create: `examples/notebooks/01_parsing.py`
- Create (generated): `examples/notebooks/01_parsing.ipynb`

- [ ] **Step 1: Write the notebook source**

Create `examples/notebooks/01_parsing.py`:

```python
# %% [markdown]
# # 01 — Parsing Manchester syntax with pymos
#
# `pymos` loads a Manchester OWL Syntax (`.omn`) document directly into an
# [owlready2](https://owlready2.readthedocs.io/) ontology — **pure Python, no Java,
# no OWL API JVM**. This notebook covers the two parsing entry points:
#
# 1. `pymos.parse(doc)` — parse a whole document into an ontology.
# 2. `pymos.parse_expression(expr, onto)` — parse a single class expression.

# %%
import pymos

print("pymos version:", pymos.__version__)

# %% [markdown]
# ## Parse a document
#
# We define a tiny biomedical ontology inline and parse it.

# %%
doc = """
Prefix: : <http://example.org/biomed#>

ObjectProperty: treats

Class: Disease
Class: BacterialInfection
    SubClassOf: Disease

Class: Drug
Class: Antibiotic
    SubClassOf: Drug
    EquivalentTo: Drug and (treats some BacterialInfection)
"""

onto = pymos.parse(doc)
type(onto)  # owlready2.namespace.Ontology

# %% [markdown]
# ## Inspect the parsed classes
#
# Look up classes by full IRI through the owlready2 world, then read their
# asserted axioms.

# %%
NS = "http://example.org/biomed#"
disease = onto.world[NS + "Disease"]
bacterial = onto.world[NS + "BacterialInfection"]
antibiotic = onto.world[NS + "Antibiotic"]

print("BacterialInfection.is_a       :", bacterial.is_a)
print("Antibiotic.is_a               :", antibiotic.is_a)
print("Antibiotic.equivalent_to      :", antibiotic.equivalent_to)
print("Disease.subclasses()          :", list(disease.subclasses()))

# %% [markdown]
# The `EquivalentTo` restriction parsed into an owlready2 class construct — a
# conjunction of `Drug` and a `treats some BacterialInfection` restriction.

# %% [markdown]
# ## Parse a single class expression
#
# `parse_expression` returns an owlready2 construct you can append directly to a
# class's `.is_a` or `.equivalent_to` list. It needs an ontology context so the
# referenced entities resolve.

# %%
import owlready2

w = owlready2.World()
expr_onto = w.get_ontology("http://example.org/biomed")
with expr_onto:
    class treats(owlready2.ObjectProperty):
        pass

    class Disease(owlready2.Thing):
        pass

expr = pymos.parse_expression("treats some Disease", expr_onto)
print(expr)
print(type(expr))  # owlready2 Restriction

# %% [markdown]
# ## Takeaway
#
# A `.omn` file becomes a fully navigable owlready2 ontology with one call —
# no external reasoner, no Java toolchain. Next: querying class relations with
# SPARQL.
```

- [ ] **Step 2: Convert to ipynb**

Run: `docker run --rm -v "$PWD":/workspace -w /workspace pymos-notebook jupytext --to ipynb examples/notebooks/01_parsing.py`
Expected: creates `examples/notebooks/01_parsing.ipynb`.

- [ ] **Step 3: Execute the notebook headless to verify it runs clean**

Run: `docker run --rm -v "$PWD":/workspace -w /workspace pymos-notebook bash -lc "pip install -e . -q && jupyter nbconvert --to notebook --execute --inplace examples/notebooks/01_parsing.ipynb"`
Expected: completes with no cell errors (exit code 0).

- [ ] **Step 4: Commit**

```bash
git add examples/notebooks/01_parsing.py examples/notebooks/01_parsing.ipynb
git commit -m "feat(examples): notebook 01 — parsing Manchester syntax"
```

---

### Task 5: Notebook 02 — Class-relation SPARQL retrieval

**Files:**
- Create: `examples/notebooks/02_class_relations.py`
- Create (generated): `examples/notebooks/02_class_relations.ipynb`

- [ ] **Step 1: Write the notebook source**

Create `examples/notebooks/02_class_relations.py`:

```python
# %% [markdown]
# # 02 — Class-relation SPARQL retrieval
#
# `class_relations_query` builds a SPARQL query (CONSTRUCT or SELECT) that walks the
# asserted graph for a class's related classes. The same query runs across **any**
# SPARQL-capable backend. Here we load the biomedical ontology and compare three
# in-process runners.
#
# > **Asserted graph only.** pymos does not run a reasoner; it queries the explicitly
# > stated axioms.

# %%
from pathlib import Path

import pymos
from pymos import class_relations_query

omn = Path("/workspace/examples/data/biomed.omn").read_text()
onto = pymos.parse(omn)
NS = "http://example.org/biomed#"
print("Loaded", len(list(onto.classes())), "classes")

# %% [markdown]
# ## The relation table
#
# | Relation | Meaning |
# |----------|---------|
# | `super` / `sub` | all transitive super/subclasses |
# | `direct_super` / `direct_sub` | immediate super/subclasses only |
# | `equiv` | equivalent classes |
# | `individual` | instances of the class |

# %% [markdown]
# ## SELECT — related IRIs only
#
# We use the owlready2 built-in engine (SELECT-only) as the first runner.

# %%
from pymos.store import run_owlready2

def select_iris(target_local, relations):
    q = class_relations_query(f"<{NS}{target_local}>", relations=relations, construct=False)
    # owlready2 SELECT rows are entity objects; .iri gives the full IRI
    # (str() would give the short form like `biomed.Disease`).
    return sorted(r[0].iri for r in run_owlready2(q, onto.world))

print("Disease sub        :", select_iris("Disease", ("sub",)))
print("Disease direct_sub :", select_iris("Disease", ("direct_sub",)))
print("Disease super      :", select_iris("Disease", ("super",)))
print("BacterialInfection individuals:", select_iris("BacterialInfection", ("individual",)))

# %% [markdown]
# Note how `direct_sub` of `Disease` omits the grandchildren
# (`BacterialInfection`, `ViralInfection`) that `sub` includes.

# %% [markdown]
# ## Same query, three backends
#
# The query is just a string — store-agnostic. We run an identical SELECT through
# owlready2, rdflib, and pyoxigraph and confirm the IRIs match.

# %%
import io

import pyoxigraph
from pymos.store import run_rdflib, run_pyoxigraph

q = class_relations_query(f"<{NS}Disease>", relations=("sub",), construct=False)

# owlready2 (.iri normalises entity objects to full IRIs)
owl_rows = {r[0].iri for r in run_owlready2(q, onto.world)}

# rdflib (via the owlready2 world's rdflib view)
rdflib_graph = onto.world.as_rdflib_graph()
rdflib_rows = {str(r[0]) for r in run_rdflib(q, rdflib_graph)}

# pyoxigraph (serialise the world to N-Triples, load into a Store)
nt = rdflib_graph.serialize(format="nt").encode()
store = pyoxigraph.Store()
store.load(io.BytesIO(nt), format=pyoxigraph.RdfFormat.N_TRIPLES)
oxi_rows = {str(s["rel"]).strip("<>") for s in run_pyoxigraph(q, store)}

print("owlready2 :", sorted(owl_rows))
print("rdflib    :", sorted(rdflib_rows))
print("pyoxigraph:", sorted(oxi_rows))
assert owl_rows == rdflib_rows == oxi_rows, "backends disagree!"
print("\nAll three backends returned identical results.")

# %% [markdown]
# ## CONSTRUCT — the full subgraph
#
# `construct=True` (the default) returns not just the related IRIs but their entire
# outgoing structural subgraph, so a client can rebuild anonymous class expressions
# without extra round-trips. owlready2's engine can't parse CONSTRUCT, so we use the
# rdflib runner.

# %%
q_construct = class_relations_query(f"<{NS}Antibiotic>", relations=("super",), construct=True)
result_graph = run_rdflib(q_construct, onto.world.as_rdflib_graph())
subjects = {str(s) for s, p, o in result_graph}
print("Triples in CONSTRUCT result:", len(result_graph))
print("Distinct subjects:", len(subjects))

# %% [markdown]
# ## Takeaway
#
# One query builder, identical results across owlready2 / rdflib / pyoxigraph.
# Next: run the same builder against a **remote** triplestore over HTTP.
```

- [ ] **Step 2: Convert to ipynb**

Run: `docker run --rm -v "$PWD":/workspace -w /workspace pymos-notebook jupytext --to ipynb examples/notebooks/02_class_relations.py`
Expected: creates `examples/notebooks/02_class_relations.ipynb`.

- [ ] **Step 3: Execute headless to verify**

Run: `docker run --rm -v "$PWD":/workspace -w /workspace pymos-notebook bash -lc "pip install -e . -q && jupyter nbconvert --to notebook --execute --inplace examples/notebooks/02_class_relations.ipynb"`
Expected: completes with no cell errors. The `assert` confirms backend agreement at runtime.

- [ ] **Step 4: Commit**

```bash
git add examples/notebooks/02_class_relations.py examples/notebooks/02_class_relations.ipynb
git commit -m "feat(examples): notebook 02 — class-relation SPARQL retrieval"
```

---

### Task 6: Notebook 03 — Remote endpoint showcase

**Files:**
- Create: `examples/notebooks/03_remote_endpoint.py`
- Create (generated): `examples/notebooks/03_remote_endpoint.ipynb`

This notebook requires the `triplestore` service to be running; it is therefore
executed during the integration task (Task 8), not standalone here.

- [ ] **Step 1: Write the notebook source**

Create `examples/notebooks/03_remote_endpoint.py`:

```python
# %% [markdown]
# # 03 — Remote endpoint showcase
#
# The end-to-end story: parse Manchester syntax in pure Python, push the resulting
# triples into a **live Oxigraph SPARQL server**, then drive that server with the
# same `class_relations_query` builder via `run_endpoint`.
#
# The Oxigraph service is reachable inside the compose network at
# `http://triplestore:7878`.

# %%
from pathlib import Path

import pymos
from pymos import class_relations_query

onto = pymos.parse(Path("/workspace/examples/data/biomed.omn").read_text())
NS = "http://example.org/biomed#"

# %% [markdown]
# ## Serialise the ontology to N-Triples

# %%
nt_bytes = onto.world.as_rdflib_graph().serialize(format="nt").encode()
print("Serialised", nt_bytes.count(b"\n"), "triples")

# %% [markdown]
# ## Load the triples into the Oxigraph server
#
# Oxigraph accepts an RDF upload via HTTP POST to `/store`. We replace the default
# graph so re-running the notebook is idempotent.

# %%
import requests

OXI = "http://triplestore:7878"

# Clear then load the default graph.
requests.post(f"{OXI}/update",
              data="DROP DEFAULT",
              headers={"Content-Type": "application/sparql-update"}).raise_for_status()

resp = requests.post(f"{OXI}/store?default",
                     data=nt_bytes,
                     headers={"Content-Type": "application/n-triples"})
resp.raise_for_status()
print("Upload status:", resp.status_code)

# %% [markdown]
# ## Confirm the data landed

# %%
count_q = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
r = requests.get(f"{OXI}/query",
                 params={"query": count_q},
                 headers={"Accept": "application/sparql-results+json"})
r.raise_for_status()
print("Triples in store:", r.json()["results"]["bindings"][0]["n"]["value"])

# %% [markdown]
# ## Query the remote endpoint with pymos
#
# `run_endpoint` sends the generated SPARQL to the live HTTP endpoint and returns
# the bindings.

# %%
from pymos.store import run_endpoint

q = class_relations_query(f"<{NS}Disease>", relations=("sub",), construct=False)
rows = run_endpoint(q, f"{OXI}/query")
print("Subclasses of Disease (from remote Oxigraph):")
for row in rows:
    print("  ", row)

# %% [markdown]
# ## Takeaway
#
# pymos parsed Manchester syntax with no Java, and the very same query builder drove
# a real remote SPARQL triplestore. Swap the URL for any SPARQL endpoint
# (Fuseki, GraphDB, Wikidata, …) and nothing else changes.
```

- [ ] **Step 2: Convert to ipynb**

Run: `docker run --rm -v "$PWD":/workspace -w /workspace pymos-notebook jupytext --to ipynb examples/notebooks/03_remote_endpoint.py`
Expected: creates `examples/notebooks/03_remote_endpoint.ipynb`.

- [ ] **Step 3: Commit (execution deferred to Task 8)**

```bash
git add examples/notebooks/03_remote_endpoint.py examples/notebooks/03_remote_endpoint.ipynb
git commit -m "feat(examples): notebook 03 — remote endpoint showcase"
```

---

### Task 7: examples README

**Files:**
- Create: `examples/README.md`

- [ ] **Step 1: Write the README**

Create `examples/README.md`:

````markdown
# pymos demonstration notebooks

Three Jupyter notebooks that demonstrate `pymos`, packaged with Docker Compose so
every dependency is contained.

## Launch

```bash
cd examples
docker compose up --build
```

Then open **http://localhost:8888** (no token required — demo configuration).
The notebooks live under `notebooks/` in the JupyterLab file browser.

A live Oxigraph SPARQL server also starts and is reachable:
- from the notebook container at `http://triplestore:7878`
- from your host at `http://localhost:7878`

Stop everything with `docker compose down`.

## Notebooks

| Notebook | What it shows |
|----------|---------------|
| `01_parsing.ipynb` | Parse a Manchester `.omn` document into an owlready2 ontology with `pymos.parse`; parse single class expressions with `pymos.parse_expression`. Pure Python, no Java. |
| `02_class_relations.ipynb` | Build SPARQL with `class_relations_query`; walk the relation table (super/sub/direct/equiv/individual); run the same query across the owlready2, rdflib, and pyoxigraph backends. |
| `03_remote_endpoint.ipynb` | Serialise the ontology, load it into the live Oxigraph server, and query it through `run_endpoint` — the full end-to-end remote-triplestore story. |

`02` and `03` use `data/biomed.omn`, a small hand-written biomedical ontology.

## Notes

- pymos is installed **editable** from the mounted repo, so the notebooks always run
  against your live working copy.
- Notebook sources are kept as jupytext percent-format `.py` files (paired with the
  `.ipynb`) for clean diffs; edit either and they stay in sync.
- pymos queries the **asserted** graph only — no reasoning. See the project README
  caveats.
````

- [ ] **Step 2: Verify it renders (basic sanity)**

Run: `python -c "import pathlib; t=pathlib.Path('examples/README.md').read_text(); assert 'docker compose up' in t and '8888' in t and 'triplestore:7878' in t; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add examples/README.md
git commit -m "docs(examples): README with launch steps and notebook summaries"
```

---

### Task 8: Full end-to-end integration

**Files:** none created — this task verifies the whole system.

- [ ] **Step 1: Build and start the full stack**

Run: `docker compose -f examples/docker-compose.yml up -d --build`
Expected: both `notebook` and `triplestore` start; no build errors.

- [ ] **Step 2: Wait for JupyterLab to be ready**

Run: `sleep 15 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/api`
Expected: `200`.

- [ ] **Step 3: Execute all three notebooks inside the running notebook container**

Run:
```bash
docker compose -f examples/docker-compose.yml exec -T notebook bash -lc \
  "jupyter nbconvert --to notebook --execute --inplace \
     examples/notebooks/01_parsing.ipynb \
     examples/notebooks/02_class_relations.ipynb \
     examples/notebooks/03_remote_endpoint.ipynb"
```
Expected: all three execute with exit code 0 and no cell errors. Notebook 03
specifically must reach the triplestore and print "Subclasses of Disease (from
remote Oxigraph)" with non-empty rows.

- [ ] **Step 4: Tear down**

Run: `docker compose -f examples/docker-compose.yml down`
Expected: services removed.

- [ ] **Step 5: Commit the executed notebooks (with outputs)**

```bash
git add examples/notebooks/*.ipynb
git commit -m "test(examples): execute all notebooks end-to-end with live triplestore"
```

---

## Self-Review Notes

- **Spec coverage:** layout (Tasks 1–7), `notebook` service editable install (Tasks 2,8),
  `triplestore` Oxigraph (Tasks 3,6,8), notebooks 01/02/03 (Tasks 4/5/6), biomed.omn
  with multi-level hierarchy + restriction + individuals (Task 1), README (Task 7),
  end-to-end success criteria (Task 8). All spec sections map to a task.
- **Out-of-scope items** (no external fetch, no triplestore persistence, no reasoning)
  are respected: ontology is hand-written and local; Oxigraph uses ephemeral container
  storage; notebooks state "asserted graph only".
- **Type/name consistency:** `class_relations_query`, `run_owlready2`, `run_rdflib`,
  `run_pyoxigraph`, `run_endpoint`, `parse`, `parse_expression`, `__version__` all
  match the pymos public API verified in `pymos/__init__.py` and `pymos/store.py`.
  Namespace `http://example.org/biomed#` is consistent across ontology, tests, and
  notebooks. `pyoxigraph.RdfFormat.N_TRIPLES` matches the README usage example.
- **Oxigraph API verified** against `ghcr.io/oxigraph/oxigraph:latest` before
  finalising this plan: entrypoint is `oxigraph` (so compose `command: ["serve", ...]`
  is correct); `serve --location /data --bind 0.0.0.0:7878` ✓; `ASK{}` → boolean ✓;
  POST N-Triples to `/store?default` → HTTP 201 ✓; `SELECT (COUNT(*) ...)` ✓;
  `DROP DEFAULT` to `/update` → HTTP 204 ✓.
- **Note (non-blocking):** `examples/tests/test_biomed.py` lives outside the
  `testpaths = ["tests"]` configured in `pyproject.toml`, so a bare `pytest` from the
  repo root will not collect it. It is invoked by explicit path (Task 1) — intended,
  as it validates example data rather than the library.
```
