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
        if isinstance(expr, owlready2.And):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.Classes)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:intersectionOf {list_head} . "
                f"{list_triples}"
            )
        raise ValueError(
            f"anonymous target of type {type(expr).__name__} is not supported"
        )

    def _restriction(self, r: owlready2.Restriction) -> tuple[str, str]:
        var = self.fresh()
        prop_iri = f"<{r.property.iri}>"
        if r.type == owlready2.HAS_SELF:
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:hasSelf true ."
            )
        if r.type == owlready2.SOME:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:someValuesFrom {filler_term} . {extra}"
            )
        if r.type == owlready2.ONLY:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:allValuesFrom {filler_term} . {extra}"
            )
        if r.type == owlready2.VALUE:
            if not hasattr(r.value, "iri"):
                raise ValueError(
                    "hasValue with a literal target is not supported "
                    "(use a named individual)"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"owl:hasValue <{r.value.iri}> ."
            )
        CARD_MAP = {
            owlready2.MIN: ("owl:minCardinality", "owl:minQualifiedCardinality"),
            owlready2.MAX: ("owl:maxCardinality", "owl:maxQualifiedCardinality"),
            owlready2.EXACTLY: ("owl:cardinality", "owl:qualifiedCardinality"),
        }
        if r.type in CARD_MAP:
            n = int(r.cardinality)
            n_lit = f'"{n}"^^xsd:nonNegativeInteger'
            qualified = not (r.value is owlready2.Thing or r.value is None)
            unq_pred, q_pred = CARD_MAP[r.type]
            if qualified:
                filler_term, extra = self.operand(r.value)
                return var, (
                    f"{var} a owl:Restriction ; "
                    f"owl:onProperty {prop_iri} ; "
                    f"{q_pred} {n_lit} ; "
                    f"owl:onClass {filler_term} . {extra}"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_iri} ; "
                f"{unq_pred} {n_lit} ."
            )
        raise ValueError(
            f"restriction type {r.type} is not supported"
        )

    def _list_pattern(self, items) -> tuple[str, str]:
        """Return (head_var, pattern) for an rdf:List of operands.

        Emits a fixed-length, ordered list pattern that matches the canonical
        rdf:first/rdf:rest spine owlready2 writes for intersection/union/oneOf.
        Nested anonymous operands contribute their own structural triples.
        """
        head = self.fresh()
        triples = []
        current = head
        for i, item in enumerate(items):
            item_term, extra = self.operand(item)
            if i < len(items) - 1:
                nxt = self.fresh()
                triples.append(f"{current} rdf:first {item_term} ; rdf:rest {nxt} .")
                if extra:
                    triples.append(extra)
                current = nxt
            else:
                triples.append(f"{current} rdf:first {item_term} ; rdf:rest rdf:nil .")
                if extra:
                    triples.append(extra)
        return head, " ".join(triples)


def expression_to_pattern(expr) -> tuple[str, str]:
    """Return ``(var, pattern)`` for an anonymous owlready2 construct.

    *var* is the SPARQL variable bound to the matching blank node; *pattern* is
    a string of SPARQL triple patterns (no surrounding braces) ready to be
    inserted into a WHERE block.
    """
    var, pattern = _Walker()._walk(expr)
    return var, " ".join(pattern.split())
