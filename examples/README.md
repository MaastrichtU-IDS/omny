# omny demonstration notebooks

Five Jupyter notebooks that demonstrate `omny`, packaged with Docker Compose so
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

`02`, `03`, and `04` use `data/biomed.omn`, a small hand-written biomedical ontology.

## Notes

- omny is installed **editable** from the mounted repo, so the notebooks always run
  against your live working copy.
- Notebook sources are kept as jupytext percent-format `.py` files (paired with the
  `.ipynb`) for clean diffs; edit either and they stay in sync.
- omny queries the **asserted** graph only — no reasoning. See the project README
  caveats.
