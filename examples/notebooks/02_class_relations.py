# %% [markdown]
# # 02 — Class-relation SPARQL retrieval
#
# `class_relations_query` builds a SPARQL query (CONSTRUCT or SELECT) that walks the
# asserted graph for a class's related classes. The same query runs across **any**
# SPARQL-capable backend. Here we load the biomedical ontology and compare three
# in-process runners.
#
# > **Asserted graph only.** omny does not run a reasoner; it queries the explicitly
# > stated axioms.

# %%
from pathlib import Path

import omny
from omny import class_relations_query

omn = Path("/workspace/examples/data/biomed.omn").read_text()
onto = omny.parse(omn)
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
from omny.store import run_owlready2

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
from omny.store import run_rdflib, run_pyoxigraph

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
