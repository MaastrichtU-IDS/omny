"""Manchester OWL Syntax -> owlready2 object model.
Visitor structure adapted from owlapy (MIT); output retargeted to owlready2.
"""
from typing import Dict, Optional

import owlready2
from parsimonious.nodes import Node, NodeVisitor

from pymos.entities import EntityResolver
from pymos.grammar import MANCHESTER_GRAMMAR


# --- VERBATIM from _ref_owlapy/owlapy/parser.py ---

def _transform_children(nary_visit_function):
    def transform(self, node, visited_children):
        if len(visited_children) > 2:
            *_, first_operand, operands, _, _ = visited_children
        else:
            first_operand, operands = visited_children
        children = first_operand if isinstance(operands, Node) else [first_operand] + [node[-1] for node in operands]
        return nary_visit_function(self, node, children)
    return transform


def _node_text(node) -> str:
    return node.text.strip()

# --- end verbatim copy ---


class ManchesterParser(NodeVisitor):
    grammar = MANCHESTER_GRAMMAR

    def __init__(self, resolver: EntityResolver):
        self.r = resolver

    def parse_expression(self, text: str):
        return self.visit(self.grammar.parse(text.strip()))

    # --- IRI visitors ---

    def visit_class_iri(self, node, children):
        return self.r.get_class(node.text.strip())

    def visit_object_property_iri(self, node, children):
        return self.r.get_object_property(node.text.strip())

    def visit_data_property_iri(self, node, children):
        return self.r.get_data_property(node.text.strip())

    def visit_individual_iri(self, node, children):
        return self.r.get_individual(node.text.strip())

    # --- class expression chain (Task 3: single-operand pass-through) ---

    def visit_class_expression(self, node, children):
        return children[0]

    def visit_primary(self, node, children):
        match_not, expr = children
        inner = expr[0]
        return owlready2.Not(inner) if isinstance(match_not, list) else inner

    @_transform_children
    def visit_union(self, node, children):
        return children if not isinstance(children, list) else owlready2.Or(children)

    @_transform_children
    def visit_intersection(self, node, children):
        return children if not isinstance(children, list) else owlready2.And(children)

    def visit_parentheses(self, node, children):
        *_, expr, _, _ = children
        return expr

    # --- object property restrictions (Task 5) ---

    def visit_some_only_res(self, node, children):
        property_, _, type_, _, filler = children
        kind = _node_text(type_[0])
        return property_.some(filler) if kind == "some" else property_.only(filler)

    def visit_cardinality_res(self, node, children):
        property_, _, type_, _, cardinality, _, filler = children
        kind = _node_text(type_[0])
        if kind == "min":
            return property_.min(cardinality, filler)
        if kind == "max":
            return property_.max(cardinality, filler)
        return property_.exactly(cardinality, filler)

    def visit_value_res(self, node, children):
        property_, *_, individual = children
        return property_.value(individual)

    def visit_has_self(self, node, children):
        property_, *_ = children
        if hasattr(property_, "has_self"):
            return property_.has_self()
        from owlready2.class_construct import Restriction
        return Restriction(property_, owlready2.HAS_SELF, None, True, None)

    def visit_object_property(self, node, children):
        inverse, property_ = children
        return owlready2.Inverse(property_) if isinstance(inverse, list) else property_

    # --- OneOf enumerations (Task 7) ---

    @_transform_children
    def visit_individual_list(self, node, children):
        return owlready2.OneOf(children if isinstance(children, list) else [children])

    # --- data property restrictions (Task 8) ---

    def visit_data_primary(self, node, children):
        match_not, expr = children
        return owlready2.Not(expr[0]) if isinstance(match_not, list) else expr[0]

    def visit_data_some_only_res(self, node, children):
        property_, _, type_, _, filler = children
        kind = _node_text(type_[0])
        return property_.some(filler) if kind == "some" else property_.only(filler)

    def visit_data_cardinality_res(self, node, children):
        property_, _, type_, _, cardinality, _, filler = children
        kind = _node_text(type_[0])
        if kind == "min":
            return property_.min(cardinality, filler)
        if kind == "max":
            return property_.max(cardinality, filler)
        return property_.exactly(cardinality, filler)

    def visit_data_value_res(self, node, children):
        property_, *_, literal = children
        return property_.value(literal)

    _XSD = {
        "integer": int, "int": int, "double": float, "float": float,
        "decimal": float, "string": str, "boolean": bool,
    }
    _FACET = {
        ">=": "min_inclusive", "<=": "max_inclusive",
        ">": "min_exclusive", "<": "max_exclusive",
        "length": "length", "minLength": "min_length", "maxLength": "max_length",
        "pattern": "pattern", "totalDigits": "total_digits",
        "fractionDigits": "fraction_digits",
    }

    def visit_datatype(self, node, children):
        return self._XSD.get(node.text.strip(), str)

    def visit_datatype_iri(self, node, children):
        # Grammar: ("<http://...#" datatype ">") / ("xsd:"? datatype)
        # children[0] is the matched alternative (a list), position [1] is the datatype
        return children[0][1]

    def visit_datatype_restriction(self, node, children):
        # grammar: datatype_iri "[" maybe_ws facet_restrictions maybe_ws "]"
        datatype, *_, facet_restrictions, _, _ = children
        facets = facet_restrictions if isinstance(facet_restrictions, list) else [facet_restrictions]
        kwargs = {}
        for item in facets:
            if isinstance(item, tuple):
                name, val = item
                kwargs[name] = val
        return owlready2.ConstrainedDatatype(datatype, **kwargs)

    @_transform_children
    def visit_facet_restrictions(self, node, children):
        return children if isinstance(children, list) else [children]

    def visit_facet_restriction(self, node, children):
        facet_node, _, literal = children
        # facet is an alternation -> arrives wrapped in a 1-element list
        facet_text = _node_text(facet_node[0]) if isinstance(facet_node, list) else _node_text(facet_node)
        return (self._FACET[facet_text], literal)

    def visit_non_negative_integer(self, node, children):
        return int(node.text)

    def visit_integer_literal(self, node, children):
        return int(node.text.strip())

    def visit_quoted_string(self, node, children):
        return node.text[1:-1]  # strip surrounding quotes

    def visit_literal(self, node, children):
        return children[0]

    def visit_string_literal_no_language(self, node, children):
        return children[0]

    def visit_typed_literal(self, node, children):
        value, _, datatype = children
        if datatype is bool:
            return value.strip().lower() == "true"
        if datatype in (int, float):
            return datatype(value)
        return value

    def visit_float_literal(self, node, children):
        text = node.text.strip()
        # strip trailing f/F
        return float(text[:-1])

    def visit_decimal_literal(self, node, children):
        return float(node.text.strip())

    def visit_boolean_literal(self, node, children):
        text = node.text.strip().lower()
        return text == "true"

    def visit_date_literal(self, node, children):
        return node.text.strip()

    def visit_datetime_literal(self, node, children):
        return node.text.strip()

    def visit_duration_literal(self, node, children):
        return node.text.strip()

    def visit_data_parentheses(self, node, children):
        *_, expr, _, _ = children
        return expr

    @_transform_children
    def visit_data_union(self, node, children):
        return children if not isinstance(children, list) else owlready2.Or(children)

    @_transform_children
    def visit_data_intersection(self, node, children):
        return children if not isinstance(children, list) else owlready2.And(children)

    @_transform_children
    def visit_literal_list(self, node, children):
        return owlready2.OneOf(children if isinstance(children, list) else [children])

    def generic_visit(self, node, children):
        return children or node


def parse_expression(text: str, onto: owlready2.Ontology,
                     prefixes: Optional[Dict[str, str]] = None):
    """Parse a single Manchester class expression into an owlready2 object."""
    return ManchesterParser(EntityResolver(onto, prefixes)).parse_expression(text)
