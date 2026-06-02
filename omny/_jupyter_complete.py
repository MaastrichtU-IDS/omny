"""Tab-completion for MOS cells.

Pure (mostly) text-classification of the active line/cell + a state-aware
candidate pool. ``omny.jupyter`` imports ``_mos_complete`` from here and
registers it with IPython; tests likewise import via ``omny.jupyter``.

The one state touch — listing classes/properties/individuals from the active
ontology — uses a lazy import of ``omny.jupyter._state`` to avoid a circular
import at module load time.
"""
import re

_FRAME_KEYWORDS = [
    "Class:", "ObjectProperty:", "DataProperty:", "Individual:",
    "Datatype:", "AnnotationProperty:", "Ontology:", "Prefix:", "Import:",
]
_VALUE_KEYWORDS = {
    "SubClassOf:", "EquivalentTo:", "DisjointWith:",
    "Domain:", "Range:", "SubPropertyOf:",
    "Types:", "SameAs:", "DifferentFrom:", "Facts:",
    "Characteristics:",
}
_RESTRICTION_OPS = ["some", "only", "value", "min", "max", "exactly", "Self"]
_BOOL_OPS = ["and", "or", "not", "inverse"]
_CHAR_KEYWORDS = [
    "Functional", "InverseFunctional", "Transitive",
    "Symmetric", "Asymmetric", "Reflexive", "Irreflexive",
]


def _last_value_keyword(cell_text: str, up_to_line_index: int) -> str | None:
    """Return the most recent value-keyword (e.g. SubClassOf:) within the current frame."""
    lines = cell_text.splitlines()[:up_to_line_index + 1]
    for raw in reversed(lines):
        s = raw.strip()
        # Stop scanning at a frame boundary.
        if any(s.startswith(k) for k in _FRAME_KEYWORDS):
            break
        for k in _VALUE_KEYWORDS:
            if s.startswith(k):
                return k
    return None


def _last_frame_keyword(cell_text: str, up_to_line_index: int) -> str | None:
    """Return the most recent frame-keyword (Class:, ObjectProperty:, …)."""
    lines = cell_text.splitlines()[:up_to_line_index + 1]
    for raw in reversed(lines):
        s = raw.strip()
        for k in _FRAME_KEYWORDS:
            if s.startswith(k):
                return k
    return None


def _is_mos_cell(cell_text: str) -> bool:
    """True iff the cell's first line is a %%mos or %%mos_query magic."""
    first = (cell_text.splitlines() + [""])[0].strip()
    return first.startswith("%%mos") or first.startswith("%%mos_query")


def _candidate_pool(context: str) -> list[str]:
    """Return raw candidates appropriate for the given context label."""
    # Lazy import: the state lives in ``omny.jupyter`` (where the magics own
    # the active ontology/world). Importing at module top would be circular.
    from omny.jupyter import _state

    if context == "line_start":
        return list(_FRAME_KEYWORDS)
    if context == "class":
        return [c.name for c in _state.onto.classes()] + _BOOL_OPS + ["("]
    if context == "object_property_or_class":
        return ([c.name for c in _state.onto.classes()]
                + [p.name for p in _state.onto.object_properties()]
                + _BOOL_OPS + _RESTRICTION_OPS)
    if context == "individual":
        return [i.name for i in _state.onto.individuals()]
    if context == "characteristic":
        return list(_CHAR_KEYWORDS)
    if context == "restriction_op":
        return list(_RESTRICTION_OPS)
    return []


def _classify_context(cell_text: str, line: str, cursor_col: int) -> str:
    """Decide which candidate pool applies at the cursor."""
    lines = cell_text.splitlines()
    line_idx = max(0, len(lines) - 1)
    head = line[:cursor_col]
    stripped_head = head.lstrip()
    column_after_indent = len(head) - len(stripped_head)
    last_value = _last_value_keyword(cell_text, line_idx)
    last_frame = _last_frame_keyword(cell_text, line_idx)
    if column_after_indent == cursor_col and last_value is None:
        return "line_start"
    if last_value in {"SubClassOf:", "EquivalentTo:", "DisjointWith:"}:
        return "object_property_or_class"
    if last_value in {"Domain:", "Range:"}:
        return "class"
    if last_value in {"Types:", "SameAs:", "DifferentFrom:"}:
        return "individual"
    if last_value == "Characteristics:":
        return "characteristic"
    if last_frame in {"Class:", "ObjectProperty:", "DataProperty:", "Individual:"}:
        return "line_start"
    # %%mos_query cells contain a single class expression — default to operators/classes/properties.
    first = (cell_text.splitlines() + [""])[0].strip()
    if first.startswith("%%mos_query"):
        return "object_property_or_class"
    return "line_start"


def _mos_complete(cell_text: str, line: str, cursor_col: int) -> list[str] | None:
    """Return Tab candidates for an MOS cell, or ``None`` to fall through to Python."""
    if not _is_mos_cell(cell_text):
        return None
    context = _classify_context(cell_text, line, cursor_col)
    pool = _candidate_pool(context)
    head = line[:cursor_col]
    m = re.search(r"([A-Za-z_:][\w:]*)$", head)
    partial = m.group(1) if m else ""
    if not partial:
        return sorted(set(pool))
    return sorted({c for c in pool if c.startswith(partial)})
