"""Per-wrapper startup floor (cold time for a no-op invocation).

These are reported alongside reasoner cells in the snapshot — never
subtracted silently from cell times. See rustdl-reasoner-bench memory.
"""
import subprocess
import sys
import time
from typing import Dict


def _time(cmd: list[str]) -> float:
    t = time.perf_counter()
    subprocess.run(cmd, check=True, capture_output=True)
    return time.perf_counter() - t


def measure_wrapper_floors(include_docker: bool = True) -> Dict[str, float]:
    floors: Dict[str, float] = {}

    # Use the same interpreter pytest/bench was invoked with, not a bare
    # "python" — on Ubuntu/Debian without the "python" symlink (only python3)
    # the bare command raises FileNotFoundError.
    floors["owlrl"] = _time([sys.executable, "-c", "import owlrl"])

    if not include_docker:
        return floors

    floors["robot-docker"] = _time(
        ["docker", "run", "--rm", "obolibrary/robot:v1.9.6", "robot", "--version"]
    )
    floors["konclude-docker"] = _time(
        ["docker", "run", "--rm", "konclude/konclude:latest", "Konclude", "-v"]
    )
    return floors
