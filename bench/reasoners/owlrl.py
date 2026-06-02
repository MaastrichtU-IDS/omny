"""Pure-Python OWL2 RL reasoner via rdflib + owlrl."""
import io
from pathlib import Path

import owlrl
import rdflib

import omny


class OwlrlReasoner:
    name = "owlrl"
    profile = "RL"
    wrapper = "in-process"

    def materialise(self, source: Path) -> Path:
        onto = omny.parse(source.read_text())
        buf = io.BytesIO()
        onto.save(file=buf, format="ntriples")
        g = rdflib.Graph()
        g.parse(data=buf.getvalue(), format="nt")

        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)

        out = source.with_suffix(".owlrl.ttl")
        g.serialize(destination=str(out), format="turtle")
        return out
