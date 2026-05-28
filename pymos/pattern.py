"""Build SPARQL structural patterns from owlready2 anonymous class constructs.

The walker emits triple patterns that bind a fresh variable (``?t0``) to any blank
node whose outgoing structure matches the input construct. Used by
:func:`pymos.sparql.class_relations_query` when the target is an anonymous
expression rather than a named IRI.
"""
import owlready2


class _Walker:
    def __init__(self):
        self._counter = 0

    def fresh(self) -> str:
        v = f"?t{self._counter}"
        self._counter += 1
        return v

    def operand(self, op) -> tuple[str, str]:
        """Return (sparql_term, extra_pattern) for a single operand.

        Named entities (`.iri`) become ``<iri>`` with no extra pattern. Anonymous
        constructs recurse and contribute their structural pattern.
        """
        if hasattr(op, "iri"):
            return f"<{op.iri}>", ""
        var, pattern = self._walk(op)
        return var, pattern

    def _walk(self, expr) -> tuple[str, str]:
        if isinstance(expr, owlready2.Restriction):
            return self._restriction(expr)
        raise ValueError(
            f"anonymous target of type {type(expr).__name__} is not supported"
        )

    def _restriction(self, r: "owlready2.Restriction") -> tuple[str, str]:
        var = self.fresh()
        prop_iri = f"<{r.property.iri}>"
        if r.type == owlready2.SOME:
            filler_term, extra = self.operand(r.value)
            pattern = (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:someValuesFrom {filler_term} . "
                f"{extra}"
            )
            return var, pattern
        raise ValueError(
            f"restriction type {r.type} is not supported"
        )


def expression_to_pattern(expr) -> tuple[str, str]:
    """Return ``(var, pattern)`` for an anonymous owlready2 construct.

    *var* is the SPARQL variable bound to the matching blank node; *pattern* is
    a string of SPARQL triple patterns (no surrounding braces) ready to be
    inserted into a WHERE block.
    """
    return _Walker()._walk(expr)
