"""Build SPARQL structural patterns from owlready2 anonymous class constructs.

The walker emits triple patterns that bind a fresh variable (``?t0``) to any blank
node whose outgoing structure matches the input construct. Used by
:func:`omny.sparql.class_relations_query` when the target is an anonymous
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
        if isinstance(expr, owlready2.Or):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.Classes)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:unionOf {list_head} . "
                f"{list_triples}"
            )
        if isinstance(expr, owlready2.Not):
            var = self.fresh()
            operand_term, extra = self.operand(expr.Class)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:complementOf {operand_term} . {extra}"
            )
        if isinstance(expr, owlready2.OneOf):
            var = self.fresh()
            list_head, list_triples = self._list_pattern(expr.instances)
            return var, (
                f"{var} a owl:Class ; "
                f"owl:oneOf {list_head} . "
                f"{list_triples}"
            )
        raise ValueError(
            f"anonymous target of type {type(expr).__name__} is not supported"
        )

    def _property_term(self, prop) -> tuple[str, str]:
        """Return (sparql_term, extra_pattern) for a property in onProperty position.

        A named property becomes ``<iri>`` with no extra. An inverse property
        becomes a fresh blank-node variable bound by an ``owl:inverseOf`` triple.
        """
        if hasattr(prop, "iri"):
            return f"<{prop.iri}>", ""
        if isinstance(prop, owlready2.Inverse):
            var = self.fresh()
            return var, f"{var} owl:inverseOf <{prop.property.iri}> ."
        raise ValueError(
            f"unsupported property kind: {type(prop).__name__}"
        )

    def _restriction(self, r: owlready2.Restriction) -> tuple[str, str]:
        var = self.fresh()
        prop_term, prop_extra = self._property_term(r.property)
        if r.type == owlready2.HAS_SELF:
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_term} ; "
                f"owl:hasSelf true . {prop_extra}"
            )
        if r.type == owlready2.SOME:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_term} ; "
                f"owl:someValuesFrom {filler_term} . {extra} {prop_extra}"
            )
        if r.type == owlready2.ONLY:
            filler_term, extra = self.operand(r.value)
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_term} ; "
                f"owl:allValuesFrom {filler_term} . {extra} {prop_extra}"
            )
        if r.type == owlready2.VALUE:
            if not hasattr(r.value, "iri"):
                raise ValueError(
                    "hasValue with a literal target is not supported "
                    "(use a named individual)"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_term} ; "
                f"owl:hasValue <{r.value.iri}> . {prop_extra}"
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
                    f"owl:onProperty {prop_term} ; "
                    f"{q_pred} {n_lit} ; "
                    f"owl:onClass {filler_term} . {extra} {prop_extra}"
                )
            return var, (
                f"{var} a owl:Restriction ; "
                f"owl:onProperty {prop_term} ; "
                f"{unq_pred} {n_lit} . {prop_extra}"
            )
        raise ValueError(
            f"restriction type {r.type} is not supported"
        )

    def _list_pattern(self, items) -> tuple[str, str]:
        """Return (list_var, pattern) for an rdf:List of operands, matched as an
        UNORDERED set.

        ``owl:intersectionOf`` / ``owl:unionOf`` / ``owl:oneOf`` are set-valued;
        the rdf:first/rdf:rest serialization order is incidental, so a query must
        match regardless of how the operands were written. Each operand must
        appear somewhere in the list (``rdf:rest*/rdf:first``), and a cardinality
        guard rejects any extra members — so ``A and B`` matches a stored
        ``(B A)`` but not ``(A B C)``. Nested anonymous operands contribute their
        own structural triples.
        """
        list_var = self.fresh()
        triples = []
        member_terms = []
        for item in items:
            item_term, extra = self.operand(item)
            triples.append(f"{list_var} rdf:rest*/rdf:first {item_term} .")
            if extra:
                triples.append(extra)
            member_terms.append(item_term)
        if member_terms:
            m = self.fresh()
            ineqs = " && ".join(f"{m} != {t}" for t in member_terms)
            triples.append(
                f"FILTER NOT EXISTS {{ {list_var} rdf:rest*/rdf:first {m} . "
                f"FILTER({ineqs}) }}"
            )
        return list_var, " ".join(triples)


def expression_to_pattern(expr) -> tuple[str, str]:
    """Return ``(var, pattern)`` for an anonymous owlready2 construct.

    *var* is the SPARQL variable bound to the matching blank node; *pattern* is
    a string of SPARQL triple patterns (no surrounding braces) ready to be
    inserted into a WHERE block.
    """
    var, pattern = _Walker()._walk(expr)
    return var, " ".join(pattern.split())


class _FlatWalker:
    """Translate an anonymous class expression into a SPARQL body that selects
    the concepts which satisfy it in a FLAT role encoding.

    Where :class:`_Walker` matches OWL ``owl:Restriction`` blank nodes (the RDF
    serialization of a class axiom), ``_FlatWalker`` instead reads roles as
    direct triples ``?concept <prop> <value>`` — the encoding used by e.g.
    SNOMED CT loaded as flat triples. A restriction therefore becomes a
    constraint on the candidate concept itself:

      ``prop some owl:Thing``  -> ``?c <prop> ?v .``
      ``prop some Filler``     -> ``?c <prop> ?v . ?v rdfs:subClassOf* <Filler> .``
      ``prop value <ind>``     -> ``?c <prop> <ind> .``
      ``prop min/max/exactly N`` -> aggregate sub-SELECT with COUNT(DISTINCT ?v)
      a named class ``C``      -> ``?c rdfs:subClassOf+ <C> .``
      ``A and B``              -> conjunction (positive operands first, NOT last)
      ``A or B``               -> ``{ … } UNION { … }``
      ``not A``                -> ``FILTER NOT EXISTS { … }``
      ``{a, b}``               -> ``VALUES ?c { <a> <b> }``

    This is the asserted-graph analogue of a DL role query; it does no
    reasoning beyond the transitive ``rdfs:subClassOf`` paths it emits.
    """

    def __init__(self):
        self._n = 0

    def _fresh(self) -> str:
        self._n += 1
        return f"?v{self._n}"

    def _role_triple(self, prop, s: str, o: str) -> str:
        if hasattr(prop, "iri"):
            return f"{s} <{prop.iri}> {o} ."
        if isinstance(prop, owlready2.Inverse):
            return f"{o} <{prop.property.iri}> {s} ."
        raise ValueError(f"unsupported property kind: {type(prop).__name__}")

    def _filler(self, value, v: str) -> str:
        """Qualified-filler constraint: ``?v`` must be the filler or a subclass.
        Empty for an unqualified restriction (owl:Thing / no filler)."""
        if value is not None and value is not owlready2.Thing and hasattr(value, "iri"):
            return f" {v} rdfs:subClassOf* <{value.iri}> ."
        return ""

    def walk(self, expr, s: str) -> str:
        if isinstance(expr, owlready2.Restriction):
            return self._restriction(expr, s)
        if isinstance(expr, owlready2.And):
            ops = list(expr.Classes)
            pos = [o for o in ops if not isinstance(o, owlready2.Not)]
            neg = [o for o in ops if isinstance(o, owlready2.Not)]
            return " ".join(self.walk(o, s) for o in (pos + neg))
        if isinstance(expr, owlready2.Or):
            return "{ " + " } UNION { ".join(self.walk(o, s) for o in expr.Classes) + " }"
        if isinstance(expr, owlready2.Not):
            return f"FILTER NOT EXISTS {{ {self.walk(expr.Class, s)} }}"
        if isinstance(expr, owlready2.OneOf):
            vals = " ".join(f"<{i.iri}>" for i in expr.instances)
            return f"VALUES {s} {{ {vals} }}"
        if hasattr(expr, "iri"):
            return f"{s} rdfs:subClassOf+ <{expr.iri}> ."
        raise ValueError(f"flat mode: unsupported construct {type(expr).__name__}")

    def _restriction(self, r: owlready2.Restriction, s: str) -> str:
        t = r.type
        if t == owlready2.VALUE:
            if not hasattr(r.value, "iri"):
                raise ValueError("flat mode: hasValue requires a named individual")
            return self._role_triple(r.property, s, f"<{r.value.iri}>")
        if t == owlready2.HAS_SELF:
            return self._role_triple(r.property, s, s)
        if t == owlready2.SOME:
            v = self._fresh()
            return self._role_triple(r.property, s, v) + self._filler(r.value, v)
        if t == owlready2.ONLY:
            raise NotImplementedError(
                "flat mode: 'only'/allValuesFrom is not expressible over an "
                "asserted flat graph (open-world assumption); use a reasoner."
            )
        if t in (owlready2.MIN, owlready2.MAX, owlready2.EXACTLY):
            n = int(r.cardinality)
            v = self._fresh()
            op = {owlready2.MIN: ">=", owlready2.MAX: "<=", owlready2.EXACTLY: "="}[t]
            body = self._role_triple(r.property, s, v) + self._filler(r.value, v)
            return (f"{{ SELECT {s} WHERE {{ {body} }} GROUP BY {s} "
                    f"HAVING(COUNT(DISTINCT {v}) {op} {n}) }}")
        raise ValueError(f"flat mode: unsupported restriction type {t}")


def expression_to_flat_pattern(expr, var: str = "?rel") -> str:
    """Return a SPARQL WHERE-body constraining *var* to the concepts that
    satisfy *expr* over a flat role encoding (see :class:`_FlatWalker`)."""
    return " ".join(_FlatWalker().walk(expr, var).split())
