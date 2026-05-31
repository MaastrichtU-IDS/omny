"""Manchester document/frame loader: populates an owlready2 ontology."""
import warnings
from typing import Dict, List, Optional, Tuple

import owlready2

from pymos._frame_tokeniser import (
    _ALL_KNOWN_KEYWORDS,
    _build_string_mask,
    _CANDIDATE_KW_RE,
    _finditer_outside_strings,
    _FRAME_RE,
    _IMPORT_RE,
    _MISC_KEYWORDS,
    _ONTOLOGY_RE,
    _PREFIX_RE,
    _SECTION_RE,
)
from pymos.entities import EntityResolver
from pymos.parser import ManchesterParser


def parse(text: str, onto: Optional[owlready2.Ontology] = None,
          prefixes: Optional[Dict[str, str]] = None) -> owlready2.Ontology:
    """Parse a Manchester OWL document and return a populated owlready2 Ontology.

    Supports all standard Manchester frame types: ``Class``, ``ObjectProperty``,
    ``DataProperty``, ``Individual``, ``Datatype``, and ``AnnotationProperty``,
    with axiom keywords ``SubClassOf``, ``EquivalentTo``, ``DisjointWith``,
    ``Domain``, ``Range``, ``Characteristics``, ``SubPropertyOf``, ``InverseOf``,
    ``Types``, ``Facts``, ``SameAs``, ``DifferentFrom``, and ``Annotations``.

    Args:
        text: A complete Manchester OWL document as a string.
        onto: An existing owlready2 ``Ontology`` to populate.  If ``None``, a
            fresh ``World`` and ``Ontology`` with a default IRI
            (``http://pymos.test/onto.owl``) are created and returned.
        prefixes: Optional mapping of prefix label to base IRI that supplements
            any ``Prefix:`` declarations found in the document.

    Returns:
        The populated owlready2 ``Ontology`` (the same object as *onto* if
        supplied, otherwise a newly created one).

    Notes:
        * ``Prefix:`` declarations in the document are extracted automatically and
          merged with any caller-supplied *prefixes*.
        * When *onto* is ``None``, the ``Ontology: <iri>`` preamble line (if
          present) is used as the identity IRI of the newly created ontology.
        * ``Import: <iri>`` lines are recorded as ``owl:imports`` declarations in
          ``onto.imported_ontologies``; the imported ontologies are **not fetched**.
        * Only the **asserted** graph is populated — no reasoner is invoked.
    """
    # Collect prefixes from the document (needed to resolve entity IRIs).
    doc_prefixes: Dict[str, str] = {}
    for m in _PREFIX_RE.finditer(text):
        doc_prefixes[m.group(1)] = m.group(2)

    if onto is None:
        m = _ONTOLOGY_RE.search(text)
        iri = m.group(1) if m else "http://pymos.test/onto.owl"
        onto = owlready2.World().get_ontology(iri)

    prefixes = dict(prefixes or {})
    prefixes.update(doc_prefixes)

    resolver = EntityResolver(onto, prefixes)
    FrameLoader(resolver, ManchesterParser(resolver)).load(text)

    for m in _IMPORT_RE.finditer(text):
        onto.imported_ontologies.append(onto.world.get_ontology(m.group(1)))

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
            if frame_type in _MISC_KEYWORDS:
                # Misc axioms have no subject; `body` is "subject + body" concatenated.
                # Rejoin them, then comma-split into operand IRIs.
                operands = self._split_commas((subject + " " + body).strip())
                self._handle_misc(frame_type, operands)
                continue
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

        Frame keywords inside quoted annotation literals are ignored via a
        string mask so e.g. ``rdfs:comment "...the Class: prefix..."`` does not
        spuriously start a new frame.
        """
        mask = _build_string_mask(text)
        matches = list(_finditer_outside_strings(_FRAME_RE, text, mask))
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

        Known limitations:

        * ``Import:`` directives are currently ignored (not loaded).
        * The regex frame/section tokenizer is not string-aware: a line that begins
          with a ``Keyword:``-like token *inside a multi-line quoted literal* can be
          mis-split.  Single-line operands and the standard frame forms are fully
          supported.
        """
        sections: Dict[str, List[str]] = {}
        mask = _build_string_mask(body)
        matches = list(_finditer_outside_strings(_SECTION_RE, body, mask))
        for i, m in enumerate(matches):
            keyword = m.group(1)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            block = body[m.end(): end].strip()
            operands = self._split_commas(block)
            if operands:
                # Repeated axiom keywords inside a frame are concatenated, not
                # overwritten — e.g. two ``SubClassOf:`` lines on the same Class
                # must both contribute to ``cls.is_a``.
                sections.setdefault(keyword, []).extend(operands)

        # Warn about lines that look like "Keyword: ..." but aren't in the known set.
        # Uses a \w+-only match so prefixed names like "rdfs:label" are not flagged.
        # Also masked: skip candidates inside quoted literals.
        for m in _finditer_outside_strings(_CANDIDATE_KW_RE, body, mask):
            kw = m.group(1)
            if kw not in _ALL_KNOWN_KEYWORDS:
                warnings.warn(
                    f"Unknown axiom keyword {kw!r} in frame body; axioms under it "
                    "will be silently dropped.",
                    UserWarning,
                    stacklevel=4,
                )

        return sections

    @staticmethod
    def _split_commas(text: str) -> List[str]:
        """Split *text* on top-level commas, ignoring those inside parens/braces
        **or inside ``"..."`` quoted literals**. Backslash-escaped quotes inside
        a literal don't end the string.
        """
        out: List[str] = []
        depth = 0
        in_string = False
        buf = ""
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                buf += ch
                if ch == "\\" and i + 1 < len(text):
                    buf += text[i + 1]
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
                buf += ch
            elif ch in "({[":
                depth += 1
                buf += ch
            elif ch in ")}]":
                depth -= 1
                buf += ch
            elif ch == "," and depth == 0:
                if buf.strip():
                    out.append(buf.strip())
                buf = ""
            else:
                buf += ch
            i += 1
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
        cls = self.r.get_class(subject)
        for expr in sections.get("SubClassOf", []):
            cls.is_a.append(self._parse_ce(expr))
        for expr in sections.get("EquivalentTo", []):
            cls.equivalent_to.append(self._parse_ce(expr))
        disjoints = [self.r.get_class(x) for x in sections.get("DisjointWith", [])]
        if disjoints:
            with self.r.onto:
                owlready2.AllDisjoint([cls, *disjoints])
        self._apply_annotations(cls, sections.get("Annotations", []))

    def _apply_annotations(self, entity, lines) -> None:
        """Apply annotation axioms from a list of 'prop_name "value"' strings."""
        from pymos.parser import unescape_quoted_string
        for line in lines:
            prop_name, _, val = line.strip().partition(" ")
            raw = val.strip()
            if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
                # Honour ``\"`` / ``\\`` inside the literal — without this, a
                # rendered ``"a\"b"`` round-trips as ``a\"b`` and the next
                # render double-escapes it, growing the file every cycle and
                # eventually breaking the frame splitter (see PR following
                # snapshot 2026-05-31).
                value = unescape_quoted_string(raw[1:-1])
            else:
                value = raw.strip('"')
            if prop_name in ("rdfs:label", "label"):
                entity.label.append(value)
            elif prop_name in ("rdfs:comment", "comment"):
                entity.comment.append(value)
            else:
                prop = self.r.get_annotation_property(prop_name)
                self._append_property_value(entity, prop, value)

    @staticmethod
    def _append_property_value(entity, prop, value) -> None:
        """Add ``value`` to ``prop[entity]`` (the IRI-keyed list view).

        Why ``prop[entity]`` instead of ``getattr/setattr(entity, name, …)``?
        owlready2's Python attribute name for a property is the **local part**
        of its IRI. Two distinct properties whose IRIs differ only in
        namespace (e.g. ``rdfs:comment`` and ``schema.org#comment``) end up
        aliasing the same attribute ``entity.comment``. Round-tripping a
        rendered ontology would then store both properties' values in the
        same list, doubling them on every parse/render cycle (sio.omn:
        10 512 → 14 633 → 22 875 annotation pairs across three rounds).
        ``prop[entity]`` is a property-keyed view that stays isolated.

        FunctionalProperty values are stored as a scalar via the attribute
        API in owlready2; ``prop[entity].append`` accepts list-like
        semantics for both functional and non-functional properties.
        """
        prop[entity].append(value)

    _CHARS = {
        "Functional": owlready2.FunctionalProperty,
        "InverseFunctional": owlready2.InverseFunctionalProperty,
        "Transitive": owlready2.TransitiveProperty,
        "Symmetric": owlready2.SymmetricProperty,
        "Asymmetric": owlready2.AsymmetricProperty,
        "Reflexive": owlready2.ReflexiveProperty,
        "Irreflexive": owlready2.IrreflexiveProperty,
    }

    def _resolve_characteristic(self, ch: str):
        """Return the owlready2 property mixin for *ch*, or raise ValueError."""
        key = ch.strip()
        if key not in self._CHARS:
            raise ValueError(f"Unknown property characteristic {key!r}")
        return self._CHARS[key]

    def _handle_object_property(self, subject: str, sections: dict) -> None:
        p = self.r.get_object_property(subject)
        for d in sections.get("Domain", []):
            p.domain.append(self._parse_ce(d))
        for rng in sections.get("Range", []):
            p.range.append(self._parse_ce(rng))
        for ch in sections.get("Characteristics", []):
            p.is_a.append(self._resolve_characteristic(ch))
        for inv in sections.get("InverseOf", []):
            p.inverse_property = self.r.get_object_property(inv)
        for sup in sections.get("SubPropertyOf", []):
            p.is_a.append(self.r.get_object_property(sup))
        self._apply_annotations(p, sections.get("Annotations", []))

    def _handle_data_property(self, subject: str, sections: dict) -> None:
        p = self.r.get_data_property(subject)
        for d in sections.get("Domain", []):
            p.domain.append(self._parse_ce(d))
        for rng in sections.get("Range", []):
            p.range.append(self._parse_ce(rng))
        for ch in sections.get("Characteristics", []):
            p.is_a.append(self._resolve_characteristic(ch))
        for sup in sections.get("SubPropertyOf", []):
            p.is_a.append(self.r.get_data_property(sup))
        self._apply_annotations(p, sections.get("Annotations", []))

    def _handle_individual(self, subject: str, sections: dict) -> None:
        ind = self.r.get_individual(subject)
        for t in sections.get("Types", []):
            ind.is_a.append(self._parse_ce(t))
        for fact in sections.get("Facts", []):
            self._assert_fact(ind, fact)
        for same in sections.get("SameAs", []):
            self._assert_same_as(ind, self.r.get_individual(same))
        diff = [self.r.get_individual(x) for x in sections.get("DifferentFrom", [])]
        if diff:
            with self.r.onto:
                owlready2.AllDifferent([ind, *diff])
        self._apply_annotations(ind, sections.get("Annotations", []))

    def _assert_fact(self, ind, fact: str) -> None:
        """Assert a property fact on an individual. fact like 'hasAge 42' or 'hasFriend alice'."""
        prop_name, _, raw = fact.strip().partition(" ")
        raw = raw.strip()
        value = self._literal_or_individual(raw)
        if isinstance(value, owlready2.Thing):
            prop = self.r.get_object_property(prop_name)
        else:
            prop = self.r.get_data_property(prop_name)
        self._append_property_value(ind, prop, value)

    def _literal_or_individual(self, raw: str):
        """Parse a fact value: quoted string, boolean, int, float, or individual name."""
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        if raw.lower() in ("true", "false"):
            return raw.lower() == "true"
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return self.r.get_individual(raw)

    def _assert_same_as(self, a, b) -> None:
        """Assert owl:sameAs(a, b) via a low-level triple insert."""
        SAMEAS = "http://www.w3.org/2002/07/owl#sameAs"
        sameas_storid = self.r.world._abbreviate(SAMEAS)
        self.r.onto._add_obj_triple_raw_spo(a.storid, sameas_storid, b.storid)

    def _handle_annotation_property(self, subject: str, sections: dict) -> None:
        self.r.get_annotation_property(subject)

    def _handle_datatype(self, subject: str, sections: dict) -> None:
        iri = self.r.expand(subject)
        s = self.r.world._abbreviate(iri)
        p = self.r.world._abbreviate("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        o = self.r.world._abbreviate("http://www.w3.org/2000/01/rdf-schema#Datatype")
        self.r.onto._add_obj_triple_raw_spo(s, p, o)

    def _handle_misc(self, misc_type: str, operands: List[str]) -> None:
        """Handle document-level misc axioms: DisjointClasses, EquivalentClasses,
        DisjointProperties, EquivalentProperties, SameIndividual, DifferentIndividuals.

        Each takes a comma-separated list of entity references.
        """
        if not operands:
            return
        if misc_type == "EquivalentClasses":
            classes = [self.r.get_class(o) for o in operands]
            for c in classes[1:]:
                if c not in classes[0].equivalent_to:
                    classes[0].equivalent_to.append(c)
        elif misc_type == "DisjointClasses":
            classes = [self.r.get_class(o) for o in operands]
            if len(classes) >= 2:
                with self.r.onto:
                    owlready2.AllDisjoint(classes)
        elif misc_type == "EquivalentProperties":
            props = [self.r.get_object_property(o) for o in operands]
            for p in props[1:]:
                if p not in props[0].equivalent_to:
                    props[0].equivalent_to.append(p)
        elif misc_type == "DisjointProperties":
            props = [self.r.get_object_property(o) for o in operands]
            if len(props) >= 2:
                with self.r.onto:
                    owlready2.AllDisjoint(props)
        elif misc_type == "SameIndividual":
            inds = [self.r.get_individual(o) for o in operands]
            for i in inds[1:]:
                if i not in inds[0].equivalent_to:
                    inds[0].equivalent_to.append(i)
        elif misc_type == "DifferentIndividuals":
            inds = [self.r.get_individual(o) for o in operands]
            if len(inds) >= 2:
                with self.r.onto:
                    owlready2.AllDifferent(inds)
