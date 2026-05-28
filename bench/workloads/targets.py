"""Pick three representative target classes per ontology: highest-degree
(most super-/subclass references), a leaf (no subclasses), and a mid-depth
interior class."""
from typing import List


def pick_targets(onto, *, k: int = 3) -> List[str]:
    import owlready2

    classes = [c for c in onto.classes() if c is not owlready2.Thing]
    if not classes:
        return []

    # Degree = |subclasses asserted| + |superclasses asserted (excluding Thing)|
    def degree(c) -> int:
        subs = [x for x in onto.world.sparql(
            f"SELECT (COUNT(?s) AS ?n) WHERE {{ ?s <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{c.iri}> }}"
        )]
        n_sub = int(subs[0][0]) if subs else 0
        supers = [s for s in c.is_a if s is not owlready2.Thing]
        return n_sub + len(supers)

    scored = sorted(classes, key=degree, reverse=True)
    if len(scored) <= k:
        return [c.iri for c in scored]

    leaves = [c for c in classes if not list(c.subclasses())]
    leaf = leaves[0] if leaves else scored[-1]

    return [
        scored[0].iri,
        scored[len(scored) // 2].iri,
        leaf.iri,
    ][:k]
