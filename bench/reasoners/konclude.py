"""Konclude reasoner via docker. Per `rustdl-konclude-input` memory: input
must be OWL/XML (.owx); the bench runner pre-converts via robot_docker."""
import subprocess
from pathlib import Path


class KoncludeReasoner:
    name = "konclude"
    profile = "DL"
    wrapper = "konclude-docker"

    def __init__(self, image: str = "konclude/konclude:latest"):
        self.image = image

    def materialise(self, source: Path) -> Path:
        if source.suffix != ".owx":
            raise ValueError("Konclude requires .owx input; convert first")
        out = source.with_suffix(".konclude.owx")
        subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{source.parent.resolve()}:/work", "-w", "/work",
             self.image, "classification",
             "-i", source.name, "-o", out.name],
            check=True, capture_output=True,
        )
        return out
