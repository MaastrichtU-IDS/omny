"""Manchester document/frame loader: populates an owlready2 ontology."""
import re
from typing import Dict, List, Optional, Tuple

import owlready2

from pymos.entities import EntityResolver
from pymos.parser import ManchesterParser

_PREFIX_RE = re.compile(r"^\s*Prefix:\s*(\w*):\s*<([^>]+)>", re.M)
_ONTOLOGY_IRI_RE = re.compile(r"^\s*Ontology:\s*<([^>]+)>", re.M)

_FRAME_RE = re.compile(
    r"^\s*(Class|ObjectProperty|DataProperty|Individual|Datatype|AnnotationProperty):",
    re.M,
)

# Axiom keywords that introduce operand lists inside a frame body
_AXIOM_KEYWORDS = (
    "SubClassOf", "EquivalentTo", "DisjointWith", "Domain", "Range",
    "Characteristics", "SubPropertyOf", "InverseOf", "Types", "Facts",
    "SameAs", "DifferentFrom", "Annotations",
)
_SECTION_RE = re.compile(
    r"^\s*(" + "|".join(_AXIOM_KEYWORDS) + r"):",
    re.M,
)


def parse(text: str, onto: Optional[owlready2.Ontology] = None,
          prefixes: Optional[Dict[str, str]] = None) -> owlready2.Ontology:
    """Parse a Manchester document and return a populated owlready2 Ontology.

    If *onto* is None a fresh World + Ontology is created using the IRI from
    the ``Ontology:`` header in the document, or a default IRI if absent.
    """
    # Collect prefixes from the document first (we need them to resolve the
    # Ontology IRI too).
    doc_prefixes: Dict[str, str] = {}
    for m in _PREFIX_RE.finditer(text):
        doc_prefixes[m.group(1)] = m.group(2)

    if onto is None:
        # Try to pick up the ontology IRI from the Ontology: header.
        m = _ONTOLOGY_IRI_RE.search(text)
        base_iri = (m.group(1).rstrip("/") + "/") if m else "http://pymos.test/onto.owl"
        onto = owlready2.World().get_ontology(base_iri)

    prefixes = dict(prefixes or {})
    prefixes.update(doc_prefixes)

    resolver = EntityResolver(onto, prefixes)
    FrameLoader(resolver, ManchesterParser(resolver)).load(text)
    return onto


class FrameLoader:
    def __init__(self, resolver: EntityResolver, parser: ManchesterParser):
        self.r = resolver
        self.parser = parser

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def load(self, text: str) -> None:
        """Parse *text* as a Manchester document and populate the ontology."""
        for frame_type, subject, body in self._split_frames(text):
            sections = self._split_sections(body)
            if frame_type == "Class":
                self._handle_class(subject, sections)
            elif frame_type == "ObjectProperty":
                self._handle_object_property(subject, sections)
            elif frame_type == "DataProperty":
                self._handle_data_property(subject, sections)
            elif frame_type == "Individual":
                self._handle_individual(subject, sections)
            elif frame_type == "AnnotationProperty":
                self._handle_annotation_property(subject, sections)
            elif frame_type == "Datatype":
                self._handle_datatype(subject, sections)
            # Unknown frame types are silently ignored.

    # ------------------------------------------------------------------
    # Frame-splitting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_subject(header_rest: str) -> str:
        """Extract the subject name/IRI from the text after ``FrameType:``.

        Handles simple names, prefixed names, and full IRIs ``<...>``.
        """
        s = header_rest.lstrip()
        if s.startswith("<"):
            end = s.index(">")
            return s[: end + 1]
        # Simple name or prefixed: take up to the first whitespace
        return s.split()[0]

    def _split_frames(self, text: str) -> List[Tuple[str, str, str]]:
        """Return [(frame_type, subject, body_text), ...] for every frame in *text*.

        Anything before the first frame keyword (preamble: Prefix/Ontology/Import
        lines) is silently skipped — prefixes have already been extracted in
        ``parse()``.
        """
        matches = list(_FRAME_RE.finditer(text))
        frames = []
        for i, m in enumerate(matches):
            frame_type = m.group(1)
            # Everything from end-of-match to start-of-next-frame (or end of text)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            rest = text[m.end(): end]
            subject = self._extract_subject(rest)
            # Body is everything after the subject token in *rest*
            if rest.lstrip().startswith("<"):
                # Full-IRI subject ends at ">"
                after_subj = rest[rest.index(">") + 1:]
            else:
                # Simple or prefixed subject — skip past first whitespace-delimited token
                stripped = rest.lstrip()
                token = stripped.split()[0] if stripped.split() else ""
                after_subj = rest[rest.index(token) + len(token):] if token else rest
            frames.append((frame_type, subject, after_subj))
        return frames

    def _split_sections(self, body: str) -> Dict[str, List[str]]:
        """Split a frame body into ``{axiom_keyword: [operand, ...]}``.

        Example body::

            SubClassOf: hasTopping some Cheese, Thing
            Domain: Pizza

        Result::

            {"SubClassOf": ["hasTopping some Cheese", "Thing"], "Domain": ["Pizza"]}
        """
        sections: Dict[str, List[str]] = {}
        matches = list(_SECTION_RE.finditer(body))
        for i, m in enumerate(matches):
            keyword = m.group(1)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            block = body[m.end(): end].strip()
            operands = self._split_commas(block)
            if operands:
                sections[keyword] = operands
        return sections

    @staticmethod
    def _split_commas(text: str) -> List[str]:
        """Split *text* on top-level commas (ignoring commas inside parens/braces)."""
        out: List[str] = []
        depth = 0
        buf = ""
        for ch in text:
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
            if ch == "," and depth == 0:
                if buf.strip():
                    out.append(buf.strip())
                buf = ""
            else:
                buf += ch
        if buf.strip():
            out.append(buf.strip())
        return out

    # ------------------------------------------------------------------
    # Expression helper
    # ------------------------------------------------------------------

    def _parse_ce(self, expr_string: str):
        return self.parser.parse_expression(expr_string)

    @staticmethod
    def _py_name(prop) -> str:
        return getattr(prop, "python_name", None) or prop.name

    # ------------------------------------------------------------------
    # Frame handlers
    # ------------------------------------------------------------------

    def _handle_class(self, subject: str, sections: dict) -> None:
        """Task 9 STUB: create the class; axioms added in Task 10."""
        self.r.get_class(subject)

    def _handle_object_property(self, subject: str, sections: dict) -> None:
        """Task 11: create the object property; axioms added later."""
        self.r.get_object_property(subject)

    def _handle_data_property(self, subject: str, sections: dict) -> None:
        """Task 11: create the data property; axioms added later."""
        self.r.get_data_property(subject)

    def _handle_individual(self, subject: str, sections: dict) -> None:
        """Task 12: create the individual; axioms added later."""
        self.r.get_individual(subject)

    def _handle_annotation_property(self, subject: str, sections: dict) -> None:
        """Task 13: create the annotation property."""
        iri = self.r.expand(subject)
        existing = self.r.world[iri]
        if existing is None:
            ns_base, local = self.r._split(iri)
            namespace = self.r.onto.get_namespace(ns_base)
            with namespace:
                import types as _types
                _types.new_class(local, (owlready2.AnnotationProperty,))

    def _handle_datatype(self, subject: str, sections: dict) -> None:
        """Task 13: datatype frames; no-op for now."""
        pass
