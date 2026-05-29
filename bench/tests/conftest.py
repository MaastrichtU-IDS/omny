"""Bench unit-test fixtures. `requires_docker` mark skips if docker is absent."""
import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return r.returncode == 0


requires_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="docker not available on this host",
)
