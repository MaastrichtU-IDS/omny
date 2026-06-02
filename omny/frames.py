"""Manchester document/frame loader: populates an owlready2 ontology."""
import warnings
from typing import Dict, List, Optional, Tuple

import owlready2

from omny._frame_tokeniser import (
    _ALL_KNOWN_KEYWORDS,
    _AXIOM_KEYWORDS,
    _build_string_mask,
    _CANDIDATE_KW_RE,
    _finditer_outside_strings,
    _FRAME_RE,
    _IMPORT_RE,
    _MISC_KEYWORDS,
    _ONTOLOGY_RE,
    _PREFIX_RE,
)
from omny.entities import EntityResolver
from omny._lark_parser import LarkManchesterParser as ManchesterParser


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
            (``http://omny.test/onto.owl``) are created and returned.
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
        iri = m.group(1) if m else "http://omny.test/onto.owl"
        onto = owlready2.World().get_ontology(iri)

    prefixes = dict(prefixes or {})
    prefixes.update(doc_prefixes)

    resolver = EntityResolver(onto, prefixes)
    loader = FrameLoader(resolver, ManchesterParser(resolver))
    loader.load(text)

    # Invalidate the Python cache for classes whose SubClassOf was
    # direct-written (see ``_handle_class``/``_direct_write_subclassof``);
    # the next ``world[iri]`` lookup lazy-reloads from triples and
    # rebuilds ``is_a`` in one ``_class_is_a_changed`` fire per class
    # instead of one per axiom. Net 1.31× on HP parse+render (status quo
    # 135.7 s → POC 103.5 s, same-host control). See
    # ``docs/perf-2026-06-02-omny-bench.md``.
    if loader._direct_write_dirty:
        ents = onto.world._entities
        for sid in loader._direct_write_dirty:
            if sid in ents:
                del ents[sid]

    for m in _IMPORT_RE.finditer(text):
        onto.imported_ontologies.append(onto.world.get_ontology(m.group(1)))

    return onto


class FrameLoader:
    def __init__(self, resolver: EntityResolver, parser: ManchesterParser):
        self.r = resolver
        self.parser = parser
        # Storids of classes whose SubClassOf was direct-written; ``parse()``
        # invalidates these so future ``world[iri]`` lookups lazy-reload
        # ``is_a`` from triples (one callback fire per class instead of one
        # per axiom).
        self._direct_write_dirty: set[int] = set()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def load(self, text: str) -> None:
        """Parse *text* as a Manchester document and populate the ontology.

        Each frame is dispatched in its own ``try`` block: a malformed
        frame (e.g. ROBOT's non-W3C-standard GCI emission
        ``Class: (expr) and (expr)``, where the "subject" isn't a name)
        warns and is skipped rather than aborting the whole load. Same
        posture as the existing unknown-keyword and inheritance-cycle
        handling.
        """
        for frame_type, subject, body in self._split_frames(text):
            try:
                if frame_type in _MISC_KEYWORDS:
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
            except (ValueError, TypeError) as e:
                warnings.warn(
                    f"frame {frame_type}: {subject!r} skipped — {type(e).__name__}: {e}",
                    stacklevel=2,
                )

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

        # Use EVERY keyword-like position (known + unknown) as a section
        # boundary. If we only used known _SECTION_RE matches, an unsupported
        # axiom keyword such as ``SubPropertyChain:`` would not terminate the
        # preceding known section — its content (and any subsequent unknown
        # keywords) would all be concatenated into the prior section's
        # operand list. With sio.omn that produced multi-line strings like
        # ``sio:SIO_000322\n    SubPropertyChain:\n        sio:SIO_000325 o sio:SIO_000068``
        # being handed to ``get_object_property`` and ultimately becoming
        # malformed entity IRIs (see PR #26 bridge sanitiser for the
        # downstream pyoxigraph failure that surfaced this).
        candidates = list(_finditer_outside_strings(_CANDIDATE_KW_RE, body, mask))
        for i, m in enumerate(candidates):
            keyword = m.group(1)
            end = candidates[i + 1].start() if i + 1 < len(candidates) else len(body)
            if keyword in _AXIOM_KEYWORDS:
                block = body[m.end(): end].strip()
                operands = self._split_commas(block)
                if operands:
                    # Repeated axiom keywords inside a frame are concatenated, not
                    # overwritten — e.g. two ``SubClassOf:`` lines on the same Class
                    # must both contribute to ``cls.is_a``.
                    sections.setdefault(keyword, []).extend(operands)

        # Warn about unknown keyword-like lines (their content is now correctly
        # dropped rather than bleeding into the preceding known section).
        for m in candidates:
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

        Reuses the C-level :func:`_build_string_mask` from PR #41 (no per-char
        string-escape state to track) and avoids the ``buf += ch`` accumulator
        that dominated the old loop on HP (138 k calls / 25 s = 13 % of the
        post-lark parse wall; see ``docs/perf-2026-06-02-omny-bench.md``).
        We walk the input once tracking bracket depth and recording top-level
        comma positions, then slice the segments out in one batch.
        """
        if not text or not text.strip():
            return []
        mask = _build_string_mask(text)
        splits = [-1]
        depth = 0
        n = len(text)
        i = 0
        while i < n:
            if mask[i]:
                i += 1
                continue
            ch = text[i]
            if ch == "," and depth == 0:
                splits.append(i)
            elif ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
            i += 1
        splits.append(n)
        out: List[str] = []
        for a, b in zip(splits, splits[1:]):
            seg = text[a + 1:b].strip()
            if seg:
                out.append(seg)
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

    # rdfs:subClassOf — IRI is fixed; the storid is per-world but stable
    # across all subsequent direct-writes (look up once per loader).
    _RDFS_SUB_CLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"

    def _direct_write_subclassof(self, cls, parent) -> None:
        """Write a single ``(cls, rdfs:subClassOf, parent)`` triple straight
        into the ontology graph, bypassing ``is_a.append`` (and therefore
        ``_class_is_a_changed``).

        The Python cache for ``cls`` is left stale until ``parse()``
        invalidates it at end-of-load, at which point the next
        ``world[cls.iri]`` rebuilds ``is_a`` from triples in one
        callback fire.

        Only safe for **named-class** parents — anonymous restrictions
        (``Restriction``, ``LogicalClassConstruct``, ``OneOf``, ``Not``)
        have no storid and must go through ``_safe_append_is_a``.
        """
        if not hasattr(self, "_sub_storid"):
            self._sub_storid = self.r.onto.world._abbreviate(self._RDFS_SUB_CLASS_OF)
        self.r.onto.graph._add_obj_triple_raw_spo(cls.storid, self._sub_storid, parent.storid)
        self._direct_write_dirty.add(cls.storid)

    @staticmethod
    def _is_named_class(parent) -> bool:
        """True iff ``parent`` is a named class (has a storid) — the
        precondition for :meth:`_direct_write_subclassof`."""
        if not hasattr(parent, "storid"):
            return False
        return not isinstance(parent, (
            owlready2.class_construct.Restriction,
            owlready2.class_construct.LogicalClassConstruct,
            owlready2.class_construct.OneOf,
            owlready2.class_construct.Not,
        ))

    def _handle_class(self, subject: str, sections: dict) -> None:
        cls = self.r.get_class(subject)
        for expr in sections.get("SubClassOf", []):
            parent = self._parse_ce(expr)
            if self._is_named_class(parent):
                # Direct-write path: ~1.31× HP parse+render vs per-item append.
                # Anonymous restrictions still need owlready2's Python
                # construct chain and fall through to _safe_append_is_a.
                self._direct_write_subclassof(cls, parent)
            else:
                self._safe_append_is_a(cls, parent, kind="SubClassOf", subject=subject)
        for expr in sections.get("EquivalentTo", []):
            try:
                cls.equivalent_to.append(self._parse_ce(expr))
            except TypeError as e:
                warnings.warn(
                    f"EquivalentTo on {subject!r} dropped: {e}",
                    stacklevel=2,
                )
        disjoints = [self.r.get_class(x) for x in sections.get("DisjointWith", [])]
        if disjoints:
            with self.r.onto:
                owlready2.AllDisjoint([cls, *disjoints])
        self._apply_annotations(cls, sections.get("Annotations", []))

    @staticmethod
    def _safe_append_is_a(entity, value, *, kind: str, subject: str) -> None:
        """``entity.is_a.append(value)`` with a TypeError catch for inheritance
        cycles. Real ontologies (HP, DOID, deprecated terms in OBO) sometimes
        declare ``X SubClassOf X`` directly or via a longer chain; owlready2
        rejects the resulting ``__bases__`` update with ``TypeError: a
        __bases__ item causes an inheritance cycle``. Treat it the same way
        we treat unknown keywords: warn and continue rather than abort the
        whole parse.
        """
        try:
            entity.is_a.append(value)
        except TypeError as e:
            if "inheritance cycle" not in str(e):
                raise
            warnings.warn(
                f"{kind} on {subject!r} dropped — would create an inheritance "
                f"cycle ({value!r}). The asserted axiom is preserved in the "
                f"underlying RDF graph but not in owlready2's class hierarchy.",
                stacklevel=2,
            )

    def _apply_annotations(self, entity, lines) -> None:
        """Apply annotation axioms from a list of 'prop_name "value"' strings."""
        from omny.parser import unescape_quoted_string
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

    def _append_property_value(self, entity, prop, value) -> None:
        """Add ``value`` to ``entity`` under property ``prop``.

        Uses owlready2's IRI-keyed view ``prop[entity].append(value)`` —
        keeping distinct properties with the same local name (e.g.
        ``rdfs:comment`` vs ``schema.org/comment``) from pooling values
        into the same attribute and doubling on round-trip.

        Punning fallback: if ``prop`` is an ObjectProperty but ``value``
        is a plain literal (str / int / bool / float — the OWL 2 punning
        case where the same IRI is used as both an object property and
        an annotation property; real example: HP's ``RO_0002433``),
        ``prop[entity].append`` triggers owlready2's
        ``_on_class_prop_changed`` callback which assumes the value is
        an entity and crashes with ``AttributeError: 'str' object has no
        attribute 'is_a'``. In that case we fall through to a low-level
        data-triple write so the annotation is recorded as
        ``<entity> <prop> "value"^^xsd:string`` without invoking the
        object-property machinery.
        """
        is_object_prop = isinstance(prop, owlready2.ObjectPropertyClass)
        is_entity_value = isinstance(value, owlready2.Thing)
        if is_object_prop and not is_entity_value:
            world = self.r.world
            xsd_string = world._abbreviate("http://www.w3.org/2001/XMLSchema#string")
            self.r.onto._add_data_triple_raw_spod(
                entity.storid, prop.storid, value, xsd_string,
            )
            return
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
