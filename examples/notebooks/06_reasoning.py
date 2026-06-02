# %% [markdown]
# # 06 — Reasoning over a omny-parsed ontology
#
# `omny.parse()` returns a regular `owlready2.Ontology`, so any reasoner that
# integrates with owlready2 or with an RDF graph works on it.  This notebook
# walks through two reasoners side-by-side on the same ontology and compares
# their effect on `.descendants()` / `.ancestors()` / `.instances()`:
#
# 1. **owlrl** — pure-Python OWL 2 RL closure (no Java, runs in-process).
# 2. **HermiT** — Java-backed OWL 2 DL reasoner, called via owlready2's
#    `sync_reasoner_hermit()` JPype bridge.
#
# The bench harness also wraps **ELK, JFact, Konclude** under `bench/reasoners/`
# (ROBOT-docker and konclude-docker); the same pattern applies if you want to
# add those reasoners to your own pipeline.
#
# **No reasoning by default.**  omny itself is reasoner-free — `omny.parse()`
# produces only the asserted axioms.  Any inference below is the reasoner's
# work, not omny's.

# %%
import io
import omny
import owlready2

print("omny:    ", omny.__version__)
print("owlready2:", owlready2.VERSION)

# %% [markdown]
# ## A small example ontology
#
# Three pizza subclasses, a transitive `partOf` property, and one individual.
# We hint at inferences a DL reasoner should derive (an `EquivalentTo`
# definition that no asserted axiom states directly).

# %%
DOC = """
Prefix: : <http://ex.org/>
Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>

Ontology: <http://ex.org/reason-demo>

ObjectProperty: hasTopping
    Domain: Pizza
    Range: Topping

ObjectProperty: partOf
    Characteristics: Transitive

Class: Food
Class: Topping
    SubClassOf: Food
Class: Cheese
    SubClassOf: Topping
Class: Mozzarella
    SubClassOf: Cheese

Class: Pizza
    SubClassOf: Food
Class: MozzarellaPizza
    EquivalentTo: Pizza and (hasTopping some Mozzarella)
Class: MyPizza
    SubClassOf: Pizza
    SubClassOf: hasTopping some Mozzarella

Individual: myPizza1
    Types: MyPizza
"""

onto = omny.parse(DOC)
NS = "http://ex.org/"

Pizza            = onto.world[NS + "Pizza"]
MozzarellaPizza  = onto.world[NS + "MozzarellaPizza"]
MyPizza          = onto.world[NS + "MyPizza"]
myPizza1         = onto.world[NS + "myPizza1"]

# %% [markdown]
# ## Baseline — asserted graph only (no reasoning)

# %%
def snapshot(label):
    return {
        "label": label,
        "Pizza.descendants": [c.name for c in Pizza.descendants()],
        "MozzarellaPizza.descendants": [c.name for c in MozzarellaPizza.descendants()],
        "MyPizza.ancestors": [c.name for c in MyPizza.ancestors()],
        "MozzarellaPizza.instances": [i.name for i in MozzarellaPizza.instances()],
    }


def show(s):
    print(f"--- {s['label']} ---")
    for k, v in s.items():
        if k == "label":
            continue
        print(f"  {k:38s} = {v}")


asserted = snapshot("asserted (no reasoner)")
show(asserted)

# %% [markdown]
# A DL reasoner should infer that **MyPizza is a MozzarellaPizza** (because the
# defining EquivalentTo on MozzarellaPizza matches the asserted SubClassOf
# axioms on MyPizza), and therefore that **myPizza1 is an instance of
# MozzarellaPizza too**.  Watch how these change below.

# %% [markdown]
# ## 1. owlrl — pure-Python OWL 2 RL
#
# `owlrl` operates on an `rdflib.Graph`.  Round-trip the owlready2 ontology
# through N-Triples, expand under OWL 2 RL semantics, then check what the
# omny `class_relations_query` returns against the saturated graph.
#
# **Note**: owlrl is an OWL 2 RL reasoner, not full DL.  Some DL-flavoured
# inferences (notably equivalent-class chains via existential restrictions)
# will not fire — see the comparison below.

# %%
import owlrl
import rdflib

from omny import class_relations_query
from omny.store import run_rdflib

# owlready2 → ntriples → rdflib.Graph
buf = io.BytesIO()
onto.save(file=buf, format="ntriples")
g = rdflib.Graph()
g.parse(data=buf.getvalue(), format="nt")

print("triples before owlrl:", len(g))
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
print("triples after  owlrl:", len(g))

# Query the saturated graph with the same SPARQL omny would build for
# Pizza's subclasses — anything the reasoner inferred shows up here.
q = class_relations_query(f"<{NS}Pizza>", relations=("sub",), construct=False)
inferred_subs = sorted(str(r[0]).rsplit("/", 1)[-1] for r in run_rdflib(q, g))
print("owlrl Pizza subclasses (via SPARQL):", inferred_subs)

# %% [markdown]
# ## 2. HermiT — OWL 2 DL via owlready2's JPype bridge
#
# `owlready2.sync_reasoner_hermit()` materializes inferences **into the
# owlready2 world itself** — after it runs, `.descendants()` / `.ancestors()`
# / `.instances()` reflect the inferred hierarchy, not just the asserted one.
#
# Requires Java on the host.  The default ontology in this notebook is small
# enough that HermiT completes in well under a second.

# %%
# Run HermiT.  Pass `onto.world` explicitly — `omny.parse()` creates a
# fresh `World()` rather than mutating owlready2's `default_world`, so the
# default-world `sync_reasoner_hermit()` call would be a no-op against our
# ontology.  `infer_property_values=True` materializes inferred property
# assertions on individuals; `debug=0` quiets the console.
with onto:
    owlready2.sync_reasoner_hermit(onto.world, infer_property_values=True, debug=0)

# %%
after_hermit = snapshot("after HermiT")
show(after_hermit)

# %% [markdown]
# ## Compare side-by-side
#
# Run the three snapshots together so the deltas are obvious.

# %%
print(f"{'metric':40s}  asserted  →  after HermiT")
keys = [k for k in asserted if k != "label"]
for k in keys:
    a = asserted[k]
    h = after_hermit[k]
    same = "(same)" if a == h else "(different)"
    print(f"{k:40s}  {len(a):2d}  →  {len(h):2d}  {same}")

# %% [markdown]
# Expected: HermiT classifies `MyPizza` under `MozzarellaPizza` (via the
# EquivalentTo definition), so `MozzarellaPizza.descendants` grows from
# `[MozzarellaPizza]` to include `MyPizza`, and `MozzarellaPizza.instances`
# now contains `myPizza1`.
#
# ## Other reasoners omny integrates with
#
# - **`owlready2.sync_reasoner_pellet()`** — same JPype pattern as HermiT, full
#   DL.
# - **ROBOT docker** (`HermiT` / `JFact` / `ELK`) — useful when you want
#   reproducible inference materialization without bundling a JDK in your
#   Python environment.  `bench/reasoners/robot_docker.py` shows the wrapper.
# - **Konclude docker** — fastest OWL 2 DL reasoner on this corpus
#   (`bench/reasoners/konclude.py`).
#
# All four are implemented and unit-tested in the perf-bench harness; the
# integration pattern is the same — call the reasoner on an .omn/.owx file,
# load the result back via `omny.parse` (or directly into an RDF store) and
# query with `class_relations_query`.

# %% [markdown]
# ## Takeaway
#
# - omny itself does no reasoning — every inference above is the reasoner's.
# - Because `omny.parse()` returns an `owlready2.Ontology`, you get the full
#   `.descendants()` / `.ancestors()` / `.instances()` / `.equivalent_to` API
#   and any reasoner integration owlready2 already supports.
# - The same `omny.class_relations_query` works against asserted graphs,
#   owlrl-saturated graphs, and HermiT-saturated worlds — pick the reasoner
#   that fits your profile (RL / EL / DL) and runtime constraints (Python
#   only / JDK / docker).
