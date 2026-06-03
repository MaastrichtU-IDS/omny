# omny demonstration notebooks

Six Jupyter notebooks that demonstrate `omny`, packaged with Docker Compose so
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
| `01_parsing.ipynb` | Parse a Manchester `.omn` document into an owlready2 ontology with `omny.parse`; parse single class expressions with `omny.parse_expression`. Pure Python, no Java. |
| `02_class_relations.ipynb` | Build SPARQL with `class_relations_query`; walk the relation table (super/sub/direct/equiv/individual); run the same query across the owlready2, rdflib, and pyoxigraph backends. |
| `03_remote_endpoint.ipynb` | Serialise the ontology, load it into the live Oxigraph server, and query it through `run_endpoint` — the full end-to-end remote-triplestore story. |
| `04_rendering.ipynb` | Render owlready2 ontologies back to Manchester syntax with `omny.render`, `omny.render_frame`, and `omny.render_expression`. Demonstrates precedence-aware expression rendering, frame rendering for each entity kind, and the `parse → render → parse` round-trip / idempotency contract on `biomed.omn`. |
| `05_interactive_mos.ipynb` | Write MOS in `%%mos` cells; **reason** with HermiT (`%reason`); query the asserted+inferred graph with `%%mos_query`; round-trip via `%mos_show` / `%mos_save`. Includes syntax highlighting and Tab autocomplete inside MOS cells. Requires Java in the image (already installed). |
| `06_reasoning.ipynb` | Reason over an omny-parsed ontology with four reasoners and compare the inferred class hierarchy: **owlrl** (OWL 2 RL, in-process) and **HermiT** (OWL 2 DL, via owlready2's JPype bridge) run out of the box; **ROBOT** (HermiT/ELK/JFact) and **Konclude** run as docker containers and are opt-in — see [Reasoning with ROBOT / Konclude](#reasoning-with-robot--konclude-notebook-06). |

`02`, `03`, and `04` use `data/biomed.omn`, a small hand-written biomedical ontology.

## Reasoning with ROBOT / Konclude (notebook 06)

`06_reasoning.ipynb` runs four reasoners. **owlrl** and **HermiT** work with a
plain `docker compose up`. **ROBOT** and **Konclude** run as their own docker
containers, which the notebook drives by shelling out to `docker run …` — so
they need access to a docker daemon. By default the notebook container has none,
and those cells detect the missing daemon and **skip cleanly**.

To run the ROBOT / Konclude cells *inside* the notebook, start the stack with
the opt-in override. It mounts the host docker socket and a shared scratch
directory (`.reason-scratch/`) so `docker run -v …` mounts resolve on the host:

```bash
docker compose -f docker-compose.yml -f docker-compose.reasoners.yml up --build
```

> ⚠️ **Security:** mounting the host docker socket gives the notebook container
> root-equivalent control of your docker daemon. Use this override only for
> local demos you trust. The first run also pulls the `obolibrary/robot` and
> `konclude/konclude` images.

Alternatively, run `06_reasoning.ipynb` directly on a host that has docker and
the omny dependencies installed.

## Notes

- omny is installed **editable** from the mounted repo, so the notebooks always run
  against your live working copy.
- Notebook sources are kept as jupytext percent-format `.py` files (paired with the
  `.ipynb`) for clean diffs; edit either and they stay in sync.
- omny itself does **no reasoning** — `omny.parse` and `class_relations_query`
  work on the asserted graph only. Any inference in notebooks `05`/`06` is the
  work of an external reasoner (HermiT, owlrl, ROBOT, Konclude), not omny. See
  the project README caveats.
