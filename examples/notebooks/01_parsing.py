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
