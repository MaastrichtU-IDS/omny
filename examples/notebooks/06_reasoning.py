# %% [markdown]
# # 06 — Reasoning over a omny-parsed ontology
#
# `omny.parse()` returns a regular `owlready2.Ontology`, so any reasoner that
# integrates with owlready2 or with an RDF graph works on it.  This notebook
# walks through four reasoners on the same ontology and compares their effect
# on `.descendants()` / `.ancestors()` / `.instances()` (and on the SPARQL
# `class_relations_query`):
#
# 1. **owlrl** — pure-Python OWL 2 RL closure (no Java, runs in-process).
# 2. **HermiT** — Java-backed OWL 2 DL reasoner, called via owlready2's
#    `sync_reasoner_hermit()` JPype bridge.
# 3. **ROBOT docker** — HermiT / ELK / JFact run inside the `obolibrary/robot`
#    container, reusing `bench/reasoners/robot_docker.py`.
# 4. **Konclude docker** — OWL 2 DL classification via `bench/reasoners/konclude.py`.
#
# Sections 3–4 need a reachable host docker daemon and skip cleanly without one.
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

# %% [markdown]
# ## 3. ROBOT docker — HermiT / ELK / JFact on the `obolibrary/robot` image
#
# The reasoners above run *in-process* (owlrl) or via a bundled JDK (HermiT
# through owlready2's JPype bridge).  The bench harness also drives reasoners as
# **docker containers**, which is handy when you'd rather not ship a JDK in your
# Python image: `bench/reasoners/robot_docker.py` wraps
# `docker run obolibrary/robot reason …` and `bench/reasoners/konclude.py` wraps
# Konclude.  We reuse those exact helpers here.
#
# These cells need a reachable **docker daemon**.  Plain `docker compose up`
# gives the `notebook` container no docker socket, so they detect its absence
# and skip cleanly.  To actually run them inside the container, start the stack
# with the opt-in override that mounts the host socket + a shared scratch dir:
#
# ```bash
# docker compose -f docker-compose.yml -f docker-compose.reasoners.yml up --build
# ```
#
# (Or run this notebook directly on a host that has docker.)

# %%
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import rdflib

from omny import class_relations_query
from omny.store import run_rdflib

# Make the repo-root `bench` package importable regardless of the kernel's cwd
# (Jupyter starts kernels in the notebook's own directory, not the repo root).
REPO_ROOT = Path.cwd()
while not (REPO_ROOT / "bench").is_dir() and REPO_ROOT != REPO_ROOT.parent:
    REPO_ROOT = REPO_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _docker_reachable():
    """True only if a docker CLI exists *and* a daemon answers — so an image
    that ships the CLI but has no socket mounted still skips cleanly."""
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    except OSError:
        return False


HAVE_DOCKER = _docker_reachable()

# The docker reasoners consume a file, not the in-memory owlready2 world, so
# serialize once to RDF/XML (owlready2's native format).  ROBOT converts this to
# OWL/XML for Konclude below.
#
# `docker run -v` paths are resolved by the *host* daemon, so when we're inside
# the compose container the scratch dir must be a path the host sees at the same
# location — `docker-compose.reasoners.yml` bind-mounts `OMNY_REASON_DIR` to an
# identical path on both sides.  On a docker host (no env var) a private tempdir
# is fine.
reason_dir = os.environ.get("OMNY_REASON_DIR")
if reason_dir:
    workdir = Path(reason_dir)
    workdir.mkdir(parents=True, exist_ok=True)
else:
    workdir = Path(tempfile.mkdtemp(prefix="omny-reason-"))
src = workdir / "reason-demo.owl"
onto.save(file=str(src), format="rdfxml")


def subclasses_of(graph, cls_iri):
    """Local names of the subclasses of `cls_iri` in `graph`, via the same
    SPARQL omny built for the owlrl section above."""
    q = class_relations_query(f"<{cls_iri}>", relations=("sub",), construct=False)
    return sorted(str(r[0]).rsplit("/", 1)[-1] for r in run_rdflib(q, graph))


def load_graph(path, fmt="turtle"):
    g_ = rdflib.Graph()
    g_.parse(str(path), format=fmt)
    return g_


# The DL inference to watch: MyPizza ⊑ MozzarellaPizza (via the EquivalentTo
# definition).  owlrl (OWL 2 RL) does NOT derive it; the DL reasoners below do.
# `g` is the owlrl-saturated graph from section 1.
print("owlrl    MozzarellaPizza subclasses:", subclasses_of(g, NS + "MozzarellaPizza"))
print("docker reachable:", HAVE_DOCKER)

# %%
# ROBOT `reason` materializes the inferred class hierarchy into a new artefact.
# We ask for Turtle output so it loads straight into rdflib and reuses the same
# `class_relations_query` as every section above.
if HAVE_DOCKER:
    from bench.reasoners.robot_docker import RobotDocker

    robot = RobotDocker()
    try:
        print("ROBOT:", robot.version().splitlines()[0])
        hermit_ttl = robot.reason(src, reasoner="HermiT", out=src.with_suffix(".hermit.ttl"))
        g_robot = load_graph(hermit_ttl)
        print("ROBOT/HermiT MozzarellaPizza subclasses:",
              subclasses_of(g_robot, NS + "MozzarellaPizza"))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("ROBOT run failed (image not pulled / daemon down?):", e)
else:
    print("ROBOT requires a host docker daemon — see bench/reasoners/robot_docker.py")

# %% [markdown]
# ## 4. Konclude docker — OWL 2 DL classification
#
# Konclude requires **OWL/XML** input (see `bench/reasoners/konclude.py`), so we
# use ROBOT to convert RDF/XML → OWL/XML first, classify, then convert the
# inferred result back to Turtle for the same rdflib query.  Konclude is the
# fastest OWL 2 DL reasoner on the bench corpus.

# %%
if HAVE_DOCKER:
    from bench.reasoners.konclude import KoncludeReasoner
    from bench.reasoners.robot_docker import RobotDocker

    robot = RobotDocker()
    try:
        owx = robot.convert(src, src.with_suffix(".owx"))             # RDF/XML → OWL/XML
        classified = KoncludeReasoner().materialise(owx)              # → *.konclude.owx
        konclude_ttl = robot.convert(classified, classified.with_suffix(".ttl"))
        g_konclude = load_graph(konclude_ttl)
        print("Konclude MozzarellaPizza subclasses:",
              subclasses_of(g_konclude, NS + "MozzarellaPizza"))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("Konclude run failed (image not pulled / daemon down?):", e)
else:
    print("Konclude requires a host docker daemon — see bench/reasoners/konclude.py")

# %% [markdown]
# ## Other reasoners omny integrates with
#
# - **`owlready2.sync_reasoner_pellet()`** — same in-process JPype pattern as
#   HermiT (section 2), full OWL 2 DL.
# - **ELK / JFact** — swap the `reasoner=` argument in the ROBOT cell
#   (`"ELK"`, `"JFact"`); `bench/reasoners/elk.py` and `jfact.py` are thin
#   wrappers over the same `RobotDocker.reason`.
#
# All of these are implemented and unit-tested in the perf-bench harness under
# `bench/reasoners/`.  The integration pattern is uniform: materialize
# inferences to a file, load that file back (owlready2 for the in-process
# reasoners, rdflib for the docker artefacts), and query with
# `class_relations_query`.

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
