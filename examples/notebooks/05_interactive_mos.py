# %% [markdown]
# # 05 — Interactive MOS notebook
#
# Build, reason about, and query an ontology by writing **Manchester OWL Syntax**
# directly in cells. Magics handle the rest.
#
# - `%%mos` — parse cell body as MOS, merge into the active ontology.
# - `%reason` — run **HermiT** over the active world (materializes inferences).
# - `%%mos_query <relation>` — query the active ontology with an anonymous MOS expression.
# - `%mos_show <Name>` — render one entity's axioms back to MOS.
# - `%mos_save <path>` — round-trip the active ontology to a `.omn` file.
#
# Tab inside a `%%mos` cell completes keywords, class names, properties, and individuals.

# %%
%load_ext pymos.jupyter

# %% [markdown]
# ## Build a small pizza ontology

# %%
%%mos
ObjectProperty: hasTopping
Class: Pizza
Class: Cheese
Class: Tomato
Class: Margherita
    SubClassOf: Pizza
    EquivalentTo: Pizza and (hasTopping some Cheese)

# %% [markdown]
# ## Reason
#
# HermiT runs over the asserted graph and materializes inferences back into the world.

# %%
%reason

# %% [markdown]
# ## Query
#
# Ask: which named class is equivalent to `Pizza and (hasTopping some Cheese)`?

# %%
%%mos_query equiv
Pizza and (hasTopping some Cheese)

# %% [markdown]
# ## Render one class back to MOS

# %%
%mos_show Margherita

# %% [markdown]
# ## Extend the ontology
#
# Manchester cells merge incrementally — re-running `%%mos` adds, it doesn't replace.

# %%
%%mos
Class: Vegetarian
    EquivalentTo: Pizza and not (hasTopping some Meat)
Class: Meat

# %% [markdown]
# Re-run reasoning to pick up the new axioms, then query subclasses of Pizza.

# %%
%reason

# %%
%%mos_query sub
Pizza

# %% [markdown]
# ## Save the whole ontology

# %%
%mos_save /tmp/pizza-built.omn

# %% [markdown]
# ## Takeaway
#
# You wrote MOS, asked HermiT to reason, queried via SPARQL, and round-tripped to
# disk — without leaving Manchester syntax. The live ontology is also exposed in
# the user namespace as `mos_onto` (and the world as `mos_world`) for any Python
# follow-up you want.

# %%
print("classes:", [c.name for c in mos_onto.classes()])
print("properties:", [p.name for p in mos_onto.object_properties()])
