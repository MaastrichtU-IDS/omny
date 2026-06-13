"""Pure tokeniser/regex helpers for the Manchester OWL document parser.

These are module-level constants and stateless functions extracted from
``omny/frames.py``. They have no dependency on ``FrameLoader``,
``EntityResolver``, or owlready2, so they can be tested and reasoned about
in isolation.
"""
import re

_PREFIX_RE = re.compile(r"^\s*Prefix:\s*(\w*):\s*<([^>]+)>", re.M)
_ONTOLOGY_RE = re.compile(r"^\s*Ontology:\s*<([^>]+)>", re.M)
_IMPORT_RE = re.compile(r"^\s*Import:\s*<([^>]+)>", re.M)

# Per W3C OWL2 Manchester syntax, "misc" axiom keywords appear at the document
# level (not inside a frame). They take a comma-separated list of operands.
_MISC_KEYWORDS = (
    "EquivalentClasses", "DisjointClasses",
    "EquivalentProperties", "DisjointProperties",
    "SameIndividual", "DifferentIndividuals",
)

_FRAME_RE = re.compile(
    r"^\s*(Class|ObjectProperty|DataProperty|Individual|Datatype|AnnotationProperty|"
    + "|".join(_MISC_KEYWORDS) + r"):",
    re.M,
)

# Axiom keywords that introduce operand lists inside a frame body
_AXIOM_KEYWORDS = (
    "SubClassOf", "EquivalentTo", "DisjointUnionOf", "DisjointWith",
    "Domain", "Range", "Characteristics", "SubPropertyChain", "SubPropertyOf",
    "InverseOf", "Types", "Facts", "SameAs", "DifferentFrom", "Annotations",
    "HasKey",
)
_SECTION_RE = re.compile(
    r"^\s*(" + "|".join(_AXIOM_KEYWORDS) + r"):",
    re.M,
)

# All keywords that are valid at the document level (frame keywords + preamble keywords).
# Used to suppress false-positive unknown-keyword warnings for top-level tokens.
_FRAME_KEYWORDS = frozenset({
    "Class", "ObjectProperty", "DataProperty", "Individual",
    "Datatype", "AnnotationProperty",
    "Prefix", "Ontology", "Import",
    *_MISC_KEYWORDS,
})
_ALL_KNOWN_KEYWORDS = frozenset(_AXIOM_KEYWORDS) | _FRAME_KEYWORDS

# Regex that matches lines whose first token looks like "Word:" (an axiom or frame keyword).
# Uses \w+ so prefixed names such as "rdfs:label" do NOT match (the colon is inside the name).
_CANDIDATE_KW_RE = re.compile(r"^\s*(\w+):\s", re.M)


# Match one ``"..."`` literal (with ``\"`` / ``\\`` escapes), non-greedy.
# Compiled once and reused — the body of this regex is what every
# ``_build_string_mask`` call is doing in a Python char loop today.
_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)


def _build_string_mask(text: str) -> bytearray:
    """Return a per-character mask: 1 inside a ``"..."`` literal, 0 outside.

    Tokenisers must consult this mask before treating a regex match as a real
    frame or axiom keyword — otherwise text like ``"... November 2012, 26th: ..."``
    inside an annotation literal can be mis-split. Recognises backslash-escaped
    quotes (``\\"``) so the closing quote of a normal literal is detected
    correctly.

    Uses ``re.finditer`` to locate literals in one C-level pass, then bulk
    bytearray slice-assigns the runs to 1 — vastly faster than the previous
    Python char-by-char loop on documents with many short literals (HP:
    32 k frames, ~30 MB total). cProfile of HP parse 2026-06-01 had this
    function at ~8 % of total parse wall.
    """
    mask = bytearray(len(text))
    for m in _STRING_LITERAL_RE.finditer(text):
        s, e = m.start(), m.end()
        mask[s:e] = b"\x01" * (e - s)
    return mask


def _finditer_outside_strings(pattern, text, mask):
    """Yield only those regex matches whose start position is outside a quoted literal."""
    for m in pattern.finditer(text):
        if not mask[m.start()]:
            yield m
