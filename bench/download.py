"""Download corpus entries, verify checksums, convert sources to .omn.

The conversion step shells out to `robot convert` for non-Manchester sources
(OBO and RDF/XML); cached `.omn` files live under `BENCH_DATA_DIR`
(default `bench/data/`). Idempotent: re-running short-circuits when the
target file exists.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import requests

from bench.corpus import CORPUS, CorpusEntry


def data_dir() -> Path:
    p = Path(os.environ.get("BENCH_DATA_DIR", "bench/data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def cached_omn_path(entry: CorpusEntry) -> Path:
    return data_dir() / f"{entry.name}.omn"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _http_get(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)


def _robot_convert(src: Path, dest_omn: Path) -> None:
    """Use ROBOT (via docker or local install) to convert src → .omn."""
    if shutil.which("robot"):
        cmd = ["robot", "convert", "--input", str(src), "--output", str(dest_omn)]
    elif shutil.which("docker"):
        # mount the data dir; ROBOT image is the same as the reasoner image
        d = src.parent.resolve()
        cmd = [
            "docker", "run", "--rm", "-v", f"{d}:/work",
            "obolibrary/robot:v1.9.6",
            "robot", "convert",
            "--input", f"/work/{src.name}",
            "--output", f"/work/{dest_omn.name}",
        ]
    else:
        raise RuntimeError("Need either `robot` or `docker` to convert ontologies")
    subprocess.run(cmd, check=True, capture_output=True)


def download_one(entry: CorpusEntry) -> Path:
    """Download + (optionally) convert + cache. Returns path to .omn."""
    omn = cached_omn_path(entry)
    if omn.exists():
        return omn

    raw = data_dir() / f"{entry.name}.{entry.fmt}"
    if not raw.exists():
        _http_get(entry.url, raw)
        if entry.sha256 != "skip-checksum":
            actual = sha256_of(raw)
            if actual != entry.sha256:
                raise RuntimeError(
                    f"checksum mismatch for {entry.name}: "
                    f"expected {entry.sha256}, got {actual}"
                )
        # Always record the downloaded SHA so the run can pin retroactively
        (data_dir() / f"{entry.name}.sha256").write_text(sha256_of(raw))

    if entry.fmt == "omn":
        shutil.copyfile(raw, omn)
    else:
        _robot_convert(raw, omn)
    return omn


def download_all(tier: str | None = None) -> list[Path]:
    entries = CORPUS if tier is None else [e for e in CORPUS if e.tier == tier]
    return [download_one(e) for e in entries]
