# pymos Demonstration Notebooks — Design

**Date:** 2026-05-27
**Status:** Approved

## Goal

A set of Jupyter notebooks that demonstrate the utility of `pymos`, packaged with
Docker Compose so every dependency is contained and the demos run with a single
`docker compose up`. The notebooks progress from a new-user tutorial into a
capability showcase.

## Audience

Both: a tutorial for newcomers (notebooks 01–02) flowing into a real-world
showcase (notebook 03). Explanatory prose in markdown cells throughout.

## Layout

A new self-contained `examples/` directory inside the pymos repo:

```
pymos/examples/
├── docker-compose.yml
├── Dockerfile              # JupyterLab + pymos extras
├── README.md               # how to launch + what each notebook shows
├── data/
│   └── biomed.omn          # hand-written biomedical Manchester ontology
└── notebooks/
    ├── 01_parsing.ipynb
    ├── 02_class_relations.ipynb
    └── 03_remote_endpoint.ipynb
```

## Compose Services

### `notebook`
- Built from `examples/Dockerfile`, based on `python:3.12-slim`.
- Installs JupyterLab and `pip install -e .[rdflib,pyoxigraph,endpoint]` against the
  mounted repo, so notebooks always run against the **live working copy** (editable
  install). This is the dogfooding choice the user selected.
- Mounts the pymos repo root (for the editable install) and the `notebooks/` +
  `data/` directories.
- Exposes JupyterLab (default container port 8888) on a host port.
- Inherits the rootless Docker daemon's HTTP proxy configuration for the build
  (pip needs the unimaas proxy). No extra proxy wiring required in the Dockerfile.

### `triplestore`
- Image: `ghcr.io/oxigraph/oxigraph` (Oxigraph SPARQL server).
- **Why Oxigraph, not Fuseki:** a lightweight single-binary SPARQL 1.1 endpoint with
  no Java — consistent with the "no Java required" ethos of pymos, and it matches the
  `pyoxigraph` backend the library already supports.
- Listens on container port 7878; SPARQL query endpoint at `/query`, RDF upload at
  `/store`.
- Notebook 03 loads data into it over HTTP and queries it via `run_endpoint`
  (the service is reachable from the notebook container as `http://triplestore:7878`).

Both services share a compose network so the notebook container can reach the
triplestore by service name.

## Notebook Progression

### 01 — Parsing Manchester syntax (tutorial)
- `pymos.parse(doc)` on a small inline Manchester document → an `owlready2.Ontology`.
- Inspect `.is_a`, `.equivalent_to`, `.subclasses()`, look up classes by IRI via
  `onto.world[...]`.
- `pymos.parse_expression("treats some Disease", onto)` returning an owlready2
  construct, and appending it to a class's `.is_a` / `.equivalent_to`.
- **Pitch:** load `.omn` directly into Python, no JVM / OWL API.

### 02 — Class-relation SPARQL retrieval (tutorial → showcase)
- Load `data/biomed.omn` via `pymos.parse`.
- Walk the full relation table: `super`, `sub`, `direct_super`, `direct_sub`,
  `equiv`, `individual` — using `class_relations_query`.
- Show CONSTRUCT (full subgraph) vs SELECT (IRIs only) and explain the difference.
- Run the **same** query through the three in-process runners — `run_rdflib`,
  `run_pyoxigraph`, `run_owlready2` — and compare results, demonstrating
  store-agnosticism. Note `run_owlready2` is SELECT-only (CONSTRUCT via rdflib).

### 03 — Remote endpoint showcase
- Serialize the parsed ontology to N-Triples (`onto.world.as_rdflib_graph()`).
- Push the N-Triples into the Oxigraph **server** over HTTP (POST to `/store`).
- Query the live HTTP SPARQL endpoint via `pymos.store.run_endpoint(query, url)`
  against `http://triplestore:7878/query`.
- **Pitch:** the full end-to-end story — parse Manchester in pure Python, then drive
  any remote SPARQL-capable triplestore with the same query builder.

## Example Ontology — `data/biomed.omn`

A hand-written Manchester-syntax biomedical ontology, original content, rich enough
to exercise every relation type in notebook 02:

- Class hierarchy with multiple levels (so `super`/`sub` differ from
  `direct_super`/`direct_sub`): e.g. `BiologicalEntity` ⊃ `Disease` ⊃ specific
  diseases; `ChemicalEntity` ⊃ `Drug`.
- Object properties: `treats`, `causes`, `associatedWith`, `hasTarget`.
- At least one `EquivalentTo` with a restriction, e.g.
  `TreatableDisease EquivalentTo: Disease and (inverse treats some Drug)` or
  `Antibiotic EquivalentTo: Drug and (treats some BacterialInfection)`.
- A couple of named individuals (so `individual` returns rows).

All offline — no external fetch.

## Out of Scope (YAGNI)

- No fetching of published ontologies (SIO/OBO) or ROBOT conversion in the demo path.
- No persistence/volumes for the triplestore beyond the container lifetime; demo data
  is reloaded by notebook 03 each run.
- No reasoning — pymos queries the asserted graph only (consistent with library
  caveats); notebooks state this explicitly where relevant.

## Success Criteria

- `docker compose up` (from `examples/`) starts JupyterLab and the Oxigraph server.
- All three notebooks run top-to-bottom without manual intervention and produce the
  shown outputs (Run All succeeds).
- Notebook 03 successfully round-trips data through the live triplestore service.
- README explains launch steps and what each notebook demonstrates.
