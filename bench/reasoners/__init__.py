"""Reasoner protocol and registry."""
from typing import Protocol
from pathlib import Path


class Reasoner(Protocol):
    name: str
    profile: str   # "none" | "RL" | "EL" | "DL"
    wrapper: str   # "in-process" | "robot-docker" | "konclude-docker"

    def materialise(self, source: Path) -> Path:
        """Run the reasoner; return path to a saturated artefact that
        a Backend.load() will consume. May be the source verbatim (NoneReasoner)."""
