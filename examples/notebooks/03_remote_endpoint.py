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
# the SPARQL 1.1 JSON results object (a dict with `head` and `results`). For a
# SELECT, the rows live under `results.bindings`, each keyed by the query's
# projected variable (here `?rel`).

# %%
from pymos.store import run_endpoint

q = class_relations_query(f"<{NS}Disease>", relations=("sub",), construct=False)
results = run_endpoint(q, f"{OXI}/query")
var = results["head"]["vars"][0]
bindings = results["results"]["bindings"]
print(f"Subclasses of Disease (from remote Oxigraph) — {len(bindings)} found:")
for b in bindings:
    print("  ", b[var]["value"])

# %% [markdown]
# ## Takeaway
#
# pymos parsed Manchester syntax with no Java, and the very same query builder drove
# a real remote SPARQL triplestore. Swap the URL for any SPARQL endpoint
# (Fuseki, GraphDB, Wikidata, …) and nothing else changes.
