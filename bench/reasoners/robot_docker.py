"""Shared ROBOT-docker invocation helper used by HermiT, Pellet, ELK reasoners.

Per the rustdl-reasoner-bench memory: same wrapper across reasoners for fairness.
"""
import subprocess
from pathlib import Path


class RobotDocker:
    """Thin shell over `docker run obolibrary/robot:v1.9.6 robot ...`."""

    def __init__(self, image: str = "obolibrary/robot:v1.9.6"):
        self.image = image

    def _run(self, args: list[str], mount: Path | None = None) -> subprocess.CompletedProcess:
        cmd = ["docker", "run", "--rm"]
        if mount is not None:
            cmd += ["-v", f"{mount.resolve()}:/work", "-w", "/work"]
        cmd += [self.image, "robot", *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def version(self) -> str:
        return self._run(["--version"]).stdout.strip()

    def reason(self, src: Path, *, reasoner: str, out: Path) -> Path:
        if src.parent.resolve() != out.parent.resolve():
            raise ValueError("src and out must share a parent directory for docker mount")
        mount = src.parent
        self._run(
            ["reason", "--reasoner", reasoner,
             "--input", src.name, "--output", out.name],
            mount=mount,
        )
        return out
