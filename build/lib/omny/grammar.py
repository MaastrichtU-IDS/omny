# Manchester OWL Syntax PEG grammar vendored from owlapy (MIT, (c) 2024 Caglar Demir).
# See NOTICE and licenses/owlapy-LICENSE.txt. Source: owlapy/parser.py.
# NOTE: this file is mostly verbatim. Intentional divergences from upstream are
# recorded in NOTICE under "Grammar policy" — do not add new divergences without
# updating that section.
from parsimonious.grammar import Grammar

# --- begin verbatim copy of owlapy MANCHESTER_GRAMMAR ---
MANCHESTER_GRAMMAR = Grammar(r"""
    union = intersection (must_ws "or" must_ws intersection)*
    intersection = primary (must_ws "and" must_ws primary)*

    # Main entry point + object properties
    primary = ("not" must_ws)? (data_some_only_res / some_only_res / data_cardinality_res / cardinality_res
                           / data_value_res / value_res / has_self / class_expression)
    some_only_res = object_property must_ws ("some"/"only") must_ws primary
    cardinality_res = object_property must_ws ("max"/"min"/"exactly") must_ws non_negative_integer must_ws primary
    value_res = object_property must_ws "value" must_ws individual_iri
    has_self = object_property must_ws "Self"
    object_property = ("inverse" must_ws)? object_property_iri
    class_expression = class_iri / individual_list / parentheses
    individual_list = "{" maybe_ws individual_iri (maybe_ws "," maybe_ws individual_iri)* maybe_ws "}"

    # Back to start symbol (first production rule)
    parentheses = "(" maybe_ws union maybe_ws ")"

    # Data properties
    data_some_only_res = data_property_iri must_ws ("some"/"only") must_ws data_primary
    data_cardinality_res = data_property_iri must_ws ("max"/"min"/"exactly")
                           must_ws non_negative_integer must_ws data_primary
    data_value_res = data_property_iri must_ws "value" must_ws literal
    data_primary = ("not" must_ws)? data_range
    data_range = datatype_restriction / datatype_iri / literal_list / data_parentheses
    literal_list = "{" maybe_ws literal (maybe_ws "," maybe_ws literal)* maybe_ws "}"
    data_parentheses = "(" maybe_ws data_union maybe_ws ")"
    data_union = data_intersection (must_ws "or" must_ws data_intersection)*
    data_intersection = data_primary (must_ws "and" must_ws data_primary)*
    datatype_restriction = datatype_iri "[" maybe_ws facet_restrictions maybe_ws "]"
    facet_restrictions = facet_restriction (maybe_ws ("," / "⊓") maybe_ws facet_restriction)*
    facet_restriction = facet must_ws literal
    facet = "length" / "minLength" / "maxLength" / "pattern" / "langRange"
            / "totalDigits" / "fractionDigits" / "<=" / ">=" / "<" / ">"
    datatype_iri = ("<http://www.w3.org/2001/XMLSchema#" datatype ">") / ("xsd:"? datatype)
    datatype = "double" / "integer" / "boolean" / "string" / "dateTime" / "date" / "duration"

    # Literals
    literal = typed_literal / string_literal_language / string_literal_no_language / datetime_literal /
              duration_literal / date_literal / float_literal / decimal_literal / integer_literal /
              boolean_literal
    typed_literal = quoted_string "^^" datatype_iri
    string_literal_language = quoted_string language_tag
    string_literal_no_language = quoted_string / no_match
    quoted_string = ~"\"([^\"\\\\]|\\\\[\"\\\\])*\""
    language_tag = "@" ~"[a-zA-Z]+" ("-" ~"[a-zA-Z0-9]+")*
    float_literal = sign (float_with_integer_part / float_no_integer_part) ("f"/"F")
    float_with_integer_part = non_negative_integer ("." ~"[0-9]+")? exponent?
    float_no_integer_part = "." ~"[0-9]+" exponent?
    exponent = ("e"/"E") sign ~"[0-9]+"
    decimal_literal = sign non_negative_integer "." ~"[0-9]+"
    integer_literal = sign non_negative_integer
    boolean_literal = ~"[tT]rue" / ~"[fF]alse"
    date_literal = ~"[0-9]{4}-((0[1-9])|(1[0-2]))-(([0-2][0-9])|(3[01]))"
    datetime_literal = ~"[0-9]{4}-((0[1-9])|(1[0-2]))-(([0-2][0-9])|(3[01]))[T\u0020]"
                       ~"(([0-1][0-9])|(2[0-3])):[0-5][0-9]:[0-5][0-9](\\.[0-9]{6})?"
                       ~"(Z|([+-](([0-1][0-9])|(2[0-3])):[0-5][0-9](:[0-5][0-9](\\.[0-9]{6})?)?))?"
    duration_literal = ~"P([0-9]+W)?([0-9]+D)?(T([0-9]+H)?([0-9]+M)?([0-9]+(\\.[0-9]{6})?S)?)?"
    sign = ("+"/"-")?
    non_negative_integer = ~"0|([1-9][0-9]*)"

    # IRIs / Characters
    class_iri = iri / no_match
    individual_iri = iri / no_match
    object_property_iri = iri / no_match
    data_property_iri = iri / no_match
    iri = full_iri / abbreviated_iri / simple_iri
    full_iri = iri_ref / no_match
    abbreviated_iri = pname_ln / no_match
    simple_iri = pn_local / no_match

    iri_ref = "<" ~"[^<>\"{}|^`\\\\\u0000-\u0020]*" ">"
    pname_ln = pname_ns pn_local
    pname_ns = pn_prefix? ":"
    pn_prefix = pn_chars_base ("."* pn_chars)*
    pn_local = (pn_chars_u / ~"[0-9]") ("."* pn_chars)*
    pn_chars = pn_chars_u / "-" / ~"[0-9]" / ~"\u00B7" / ~"[\u0300-\u036F]" / ~"[\u203F-\u2040]"
    pn_chars_u = pn_chars_base / "_"
    pn_chars_base = ~"[a-zA-Z]" / ~"[\u00C0-\u00D6]" / ~"[\u00D8-\u00F6]" / ~"[\u00F8-\u02FF]" /
                    ~"[\u0370-\u037D]" / ~"[\u037F-\u1FFF]" / ~"[\u200C-\u200D]" / ~"[\u2070-\u218F]" /
                    ~"[\u2C00-\u2FEF]" / ~"[\u3001-\uD7FF]" / ~"[\uF900-\uFDCF]" / ~"[\uFDF0-\uFFFD]" /
                    ~"[\U00010000-\U000EFFFF]"

    must_ws = ~"[\u0020\u000D\u0009\u000A]+"
    maybe_ws = ~"[\u0020\u000D\u0009\u000A]*"

    # hacky workaround: can be added to a pass through production rule that is semantically important
    # so nodes are not combined which makes the parsing cleaner
    no_match = ~"(?!a)a"
    """)
# --- end verbatim copy ---
