# %% [markdown]
# # 04 — Rendering owlready2 ontologies back to Manchester syntax
#
# `omny` is symmetric: the same package that **parses** a Manchester `.omn`
# document into owlready2 will also **render** an owlready2 ontology back to a
# Manchester document — full round-trip, pure Python, no Java.
#
# This notebook covers the three public rendering entry points:
#
# 1. `omny.render_expression(ce, prefixes)` — one class expression to a string,
#    precedence-aware (parentheses are inserted around lower-precedence operands).
# 2. `omny.render_frame(entity, prefixes)` — one Class / ObjectProperty /
#    DataProperty / Individual / AnnotationProperty frame.
# 3. `omny.render(onto, prefixes)` — a full document with Prefix declarations,
#    Ontology header, and frames in stable order.

# %%
from pathlib import Path

import omny

print("omny version:", omny.__version__)

# %% [markdown]
# ## A. Render a single class expression
#
# `render_expression` is the inverse of `parse_expression`. It takes any
# owlready2 class expression (a `Restriction`, `And`, `Or`, `Not`, `OneOf`,
# `ConstrainedDatatype`, or a named class) and produces a Manchester string.
#
# Precedence is handled automatically: `or` binds looser than `and`, which binds
# looser than `not`, so an `or` operand inside an `and` gets parenthesised.

# %%
import owlready2

w = owlready2.World()
onto = w.get_ontology("http://example.org/biomed#")
with onto:
    class treats(owlready2.ObjectProperty): pass
    class Disease(owlready2.Thing): pass
    class BacterialInfection(Disease): pass
    class ViralInfection(Disease): pass

PFX = {"": "http://example.org/biomed#"}

# A simple existential restriction
ce1 = omny.parse_expression("treats some BacterialInfection", onto, prefixes=PFX)
print(omny.render_expression(ce1, prefixes=PFX))

# Boolean nesting — note the parentheses around the `or`
ce2 = omny.parse_expression(
    "treats some (BacterialInfection or ViralInfection)", onto, prefixes=PFX
)
print(omny.render_expression(ce2, prefixes=PFX))

# Cardinality
ce3 = omny.parse_expression("treats min 2 Disease", onto, prefixes=PFX)
print(omny.render_expression(ce3, prefixes=PFX))

# %% [markdown]
# ## B. Render a single frame
#
# `render_frame` emits the header line and every populated axiom keyword for
# one entity. Empty axiom groups are omitted, so a class with no asserted
# axioms produces just `Class: Foo`.

# %%
doc = """
Prefix: : <http://example.org/biomed#>
Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>

Class: Antibiotic
    Annotations: rdfs:label "Antibiotic"
    SubClassOf: Drug
    EquivalentTo: Drug and (treats some BacterialInfection)

ObjectProperty: treats
    Domain: Drug
    Range: Disease
    Characteristics: Functional

Individual: penicillin
    Types: Antibiotic
    Facts: treats infection1
"""

PFX2 = {
    "": "http://example.org/biomed#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

onto2 = omny.parse(doc)

antibiotic = onto2.world["http://example.org/biomed#Antibiotic"]
print(omny.render_frame(antibiotic, prefixes=PFX2))

# %%
treats = onto2.world["http://example.org/biomed#treats"]
print(omny.render_frame(treats, prefixes=PFX2))

# %%
penicillin = onto2.world["http://example.org/biomed#penicillin"]
print(omny.render_frame(penicillin, prefixes=PFX2))

# %% [markdown]
# ## C. Render a full document
#
# `omny.render(onto, prefixes)` assembles the full Manchester document:
# Prefix declarations, Ontology header, then frames in stable order
# (Datatype → AnnotationProperty → ObjectProperty → DataProperty → Class →
# Individual, each sorted by IRI). The output is deterministic — running
# `render` on the same ontology twice yields byte-identical text.
#
# Below we load the `biomed.omn` fixture used by notebooks 02 and 03, and
# render the resulting owlready2 ontology back to Manchester.

# %%
# Resolve relative to this file so the script runs from any cwd.
OMN = Path(__file__).resolve().parents[1] / "data" / "biomed.omn"
biomed_doc = OMN.read_text()
biomed_onto = omny.parse(biomed_doc)

rendered = omny.render(biomed_onto, prefixes=PFX2)
print(rendered)

# %% [markdown]
# ## D. The round-trip contract
#
# Two guarantees:
#
# - **Structural equality**: `parse → render → parse` preserves the set of
#   class / property / individual IRIs and the count of axioms per entity.
# - **Idempotency**: the second pass of `render` produces byte-identical text.
#
# (The first pass is *not* guaranteed byte-identical to the source — the
# source may have differing whitespace, frame ordering, or use prefixes that
# omny doesn't have in its map. The second pass stabilises.)

# %%
text1 = omny.render(omny.parse(biomed_doc), prefixes=PFX2)
text2 = omny.render(omny.parse(text1), prefixes=PFX2)

print("byte-identical second pass?", text1 == text2)

# %%
onto_a = omny.parse(biomed_doc)
onto_b = omny.parse(text1)

iris_a = {c.iri for c in onto_a.classes()}
iris_b = {c.iri for c in onto_b.classes()}

print("class IRIs preserved?", iris_a == iris_b)
print("number of classes:", len(iris_a))

# %% [markdown]
# ## E. What `render` covers
#
# As of this notebook, `omny.render` emits:
#
# - **Header**: `Prefix:` declarations (from the prefix map you pass) and
#   `Ontology:` IRI; `Import:` directives if any are present.
# - **Datatype** frames for any IRI declared as `rdfs:Datatype`.
# - **AnnotationProperty** frames.
# - **ObjectProperty / DataProperty** frames with `Domain:`, `Range:`,
#   `Characteristics:` (`Functional`, `InverseFunctional`, `Transitive`,
#   `Symmetric`, `Asymmetric`, `Reflexive`, `Irreflexive`), `SubPropertyOf:`,
#   and `InverseOf:`.
# - **Class** frames with `Annotations:` (built-in `rdfs:label`/`rdfs:comment`/
#   `rdfs:seeAlso` and user-declared annotation properties), `SubClassOf:`,
#   `EquivalentTo:`, and `DisjointWith:`.
# - **Individual** frames with `Annotations:`, `Types:`, `Facts:` (object and
#   data property assertions), `SameAs:`, and `DifferentFrom:`.
#
# Class expressions inside any of those keywords are rendered with operator
# precedence preserved through parentheses.

# %% [markdown]
# ## Takeaway
#
# `omny.render` closes the loop: parse a `.omn` file, manipulate the
# ontology programmatically through owlready2, then re-emit a clean,
# deterministic Manchester document — all without leaving Python.
