# pymos performance benchmark — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-shot snapshot perf bench for pymos covering parse / render / query across 12 OBO ontologies, 6 storage backends, and 6 reasoning configurations — producing `docs/perf-YYYY-MM-DD-pymos-bench.md` in the established rustdl narrative style.

**Architecture:** A `bench/` package under the repo root (sibling of `pymos/`, *not* shipped on PyPI) with: a corpus loader, six backend factories, six reasoner factories (one in-process, four ROBOT-docker-wrapped, one konclude-docker), three workload modules, a subprocess-per-cell measurement layer, and a snapshot runner that emits raw JSON/CSV, scaling plots, and the narrative report. Each cell runs in a fresh subprocess so peak RSS is clean. JVM/docker dependencies are bench-only — pymos itself stays Java-free.

**Tech Stack:** Python 3.10+, pytest, pytest-benchmark (dev loop only), `psutil`, `tracemalloc` (stdlib), `matplotlib`, `owlrl`, `rdflib`, `pyoxigraph`, `owlready2`. Docker for `obolibrary/robot:v1.9.6` and `konclude/konclude`. `ROBOT` for the size-tier `.obo→.omn` conversion at corpus download time.

**Source spec:** `docs/superpowers/specs/2026-05-28-pymos-perf-bench-design.md` — read it first.

**Reference shape:** `/data/dumontier/rustdl/docs/perf-2026-05-24-new-server.md` (committed; gives the narrative-report layout we're targeting).

---

## File structure (locked)

```
bench/
  __init__.py
  conftest.py                 pytest fixtures: pizza ontology path, fresh subprocess helper
  corpus.py                   declarative corpus manifest + Corpus.entries iterator
  download.py                 fetch + SHA256-verify + ROBOT-convert each entry to .omn
  measure.py                  Measurement dataclass + run_in_subprocess + timing/memory helpers
  backends/
    __init__.py               Backend protocol
    owlready2_mem.py    owlready2_sqlite.py
    pyoxigraph_mem.py   pyoxigraph_rocksdb.py
    rdflib_mem.py       endpoint_oxigraph.py
  reasoners/
    __init__.py               Reasoner protocol
    none.py             owlrl.py
    robot_docker.py           shared invocation helper for HermiT / Pellet / ELK
    hermit.py           pellet.py             elk.py
    konclude.py
    floors.py                 per-wrapper startup-floor measurement
  workloads/
    __init__.py               Measurement helpers shared across workloads
    parse.py            render.py             query.py
    targets.py                pick 3 target classes per ontology
  runners/
    __init__.py
    snapshot.py               orchestrate cells → results.json + .csv + plots + report
    report.py                 narrative-markdown emitter
    plots.py                  matplotlib scaling curves
  results/                    YYYY-MM-DD-run/ (gitignored)
  data/                       downloaded ontologies (gitignored)
  cache/                      per-backend persistent stores (gitignored)

bench/tests/                  unit tests for the bench harness itself (NOT in main pytest path)
  test_corpus.py    test_measure.py    test_backends.py
  test_reasoners.py test_workloads.py  test_snapshot.py

docs/perf-2026-05-28-pymos-bench.md   the report (committed when M8 runs)
```

**Test isolation:** `bench/tests/` runs under its own `pytest bench/tests/` invocation. The main `pytest -q` (109+ existing tests) does **not** pick them up — they're slower and have docker dependencies. CI keeps running just the main suite.

**Conventions used throughout:**
- All bench code runs from the repo root with `bench` on `sys.path` (no install). The bench is an internal harness, not a library.
- Every cell runs in a fresh subprocess via `bench.measure.run_in_subprocess(target, args)` so `psutil.Process().memory_info().rss` is clean.
- Tests that require Docker use the `requires_docker` pytest mark and skip cleanly when `docker info` fails.
- Tests that require a downloaded ontology fall back to the committed `examples/data/biomed.omn` fixture so unit tests don't depend on network access.

---

## Milestone 0 — Scaffolding

### Task 0: Package skeleton, gitignore, dev extras

**Files:**
- Create: `bench/__init__.py`, `bench/tests/__init__.py`, `bench/conftest.py`, `bench/tests/conftest.py`
- Modify: `.gitignore`, `pyproject.toml`

- [ ] **Step 1: Add bench dirs to `.gitignore`**

Append to `.gitignore`:

```
bench/results/
bench/data/
bench/cache/
```

- [ ] **Step 2: Add `bench` extra to pyproject**

Edit `pyproject.toml`, in `[project.optional-dependencies]`, add:

```toml
bench = [
  "psutil>=5.9",
  "matplotlib>=3.8",
  "owlrl>=6.0",
  "rdflib>=7.0",
  "pyoxigraph>=0.4",
  "requests>=2.31",
  "pytest>=8.0",
]
```

- [ ] **Step 3: Create empty package markers**

Create empty `bench/__init__.py` containing only `"""pymos performance benchmark harness."""`.
Create empty `bench/tests/__init__.py`.

- [ ] **Step 4: Create `bench/conftest.py`**

```python
"""Shared fixtures for the bench harness (not the unit-test suite)."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PIZZA_OMN = REPO_ROOT / "tests" / "data" / "pizza.omn"
BIOMED_OMN = REPO_ROOT / "examples" / "data" / "biomed.omn"


@pytest.fixture
def pizza_text() -> str:
    return PIZZA_OMN.read_text()


@pytest.fixture
def biomed_text() -> str:
    return BIOMED_OMN.read_text()
```

- [ ] **Step 5: Create `bench/tests/conftest.py`**

```python
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
```

- [ ] **Step 6: Install the extra in the dev venv**

Run: `source .venv/bin/activate && pip install -e ".[dev,bench]"`
Expected: psutil, matplotlib, owlrl, requests resolve and install.

- [ ] **Step 7: Smoke test**

Run: `python -c "import bench; from bench.tests.conftest import requires_docker; print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Commit**

```bash
git add bench .gitignore pyproject.toml
git commit -m "bench: scaffold package, gitignore data/cache/results, add bench extra"
```

---

### Task 1: `measure.py` — timing + memory + subprocess primitives

**Files:**
- Create: `bench/measure.py`, `bench/tests/test_measure.py`

- [ ] **Step 1: Write failing tests**

`bench/tests/test_measure.py`:

```python
import statistics
import time

from bench.measure import (
    Measurement,
    measure_in_process,
    measure_in_subprocess,
)


def _slow_workload(n: int = 50_000) -> int:
    """A workload with a known small allocation + measurable wall time."""
    data = [i * i for i in range(n)]
    time.sleep(0.01)
    return sum(data)


def test_measure_in_process_returns_measurement():
    m = measure_in_process(_slow_workload, args=(10_000,), hot_iters=3, warmup=1)
    assert isinstance(m, Measurement)
    assert m.wall_cold > 0
    assert m.wall_hot_median > 0
    assert m.peak_rss_bytes > 0
    assert m.peak_python_bytes > 0
    assert len(m.wall_hot_samples) == 3
    assert m.wall_hot_stddev == statistics.pstdev(m.wall_hot_samples)


def test_measure_in_subprocess_runs_isolated_process():
    m = measure_in_subprocess(
        "bench.tests.test_measure", "_slow_workload", args=(10_000,),
        hot_iters=3, warmup=1,
    )
    assert isinstance(m, Measurement)
    assert m.wall_cold > 0
    # subprocess RSS will be much smaller than the parent for a small workload
    assert m.peak_rss_bytes > 0


def test_measurement_to_dict_round_trips():
    m = Measurement(
        wall_cold=1.0, wall_hot_samples=[0.5, 0.5, 0.5], wall_hot_median=0.5,
        wall_hot_stddev=0.0, peak_rss_bytes=1_000_000, peak_python_bytes=100_000,
        cpu_cold=0.9, cpu_hot_median=0.45, extras={"axiom_count": 250},
    )
    d = m.to_dict()
    assert d["wall_cold"] == 1.0
    assert d["extras"]["axiom_count"] == 250
    assert Measurement.from_dict(d) == m
```

- [ ] **Step 2: Run tests and confirm they fail**

Run: `pytest bench/tests/test_measure.py -v`
Expected: FAIL — `bench.measure` module does not exist.

- [ ] **Step 3: Implement `bench/measure.py`**

```python
"""Wall + CPU + memory measurement primitives, in-process and subprocess.

Every bench cell uses `measure_in_subprocess` so peak RSS is clean (the parent
process's heap doesn't leak in). `measure_in_process` exists only for the unit
tests of this module.
"""
from __future__ import annotations

import importlib
import json
import os
import statistics
import subprocess
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

import psutil


@dataclass
class Measurement:
    wall_cold: float                 # seconds; first full execution
    wall_hot_samples: list[float]    # seconds; post-warmup hot iterations
    wall_hot_median: float
    wall_hot_stddev: float
    peak_rss_bytes: int              # OS-level resident set peak
    peak_python_bytes: int           # tracemalloc peak
    cpu_cold: float                  # CPU seconds for the cold run
    cpu_hot_median: float            # CPU seconds, median of hot iters
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Measurement":
        return cls(**d)


def _run_once(target: Callable, args: Sequence[Any]) -> tuple[float, float]:
    """One execution, returns (wall_seconds, cpu_seconds)."""
    t0_wall, t0_cpu = time.perf_counter(), time.process_time()
    target(*args)
    return time.perf_counter() - t0_wall, time.process_time() - t0_cpu


def measure_in_process(
    target: Callable, *, args: Sequence[Any] = (), hot_iters: int = 3, warmup: int = 1,
) -> Measurement:
    """Run `target(*args)` once cold + `warmup` discarded + `hot_iters` measured.

    Use only from this module's own tests; bench cells should use
    `measure_in_subprocess` so RSS is clean.
    """
    proc = psutil.Process()
    tracemalloc.start()

    rss_before = proc.memory_info().rss
    wall_cold, cpu_cold = _run_once(target, args)
    rss_peak = max(rss_before, proc.memory_info().rss)

    for _ in range(warmup):
        _run_once(target, args)

    hot_walls: list[float] = []
    hot_cpus: list[float] = []
    for _ in range(hot_iters):
        w, c = _run_once(target, args)
        hot_walls.append(w)
        hot_cpus.append(c)
        rss_peak = max(rss_peak, proc.memory_info().rss)

    _, peak_python = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return Measurement(
        wall_cold=wall_cold,
        wall_hot_samples=hot_walls,
        wall_hot_median=statistics.median(hot_walls),
        wall_hot_stddev=statistics.pstdev(hot_walls),
        peak_rss_bytes=rss_peak,
        peak_python_bytes=peak_python,
        cpu_cold=cpu_cold,
        cpu_hot_median=statistics.median(hot_cpus),
    )


_SUBPROC_RUNNER = """
import importlib, json, sys
from bench.measure import measure_in_process

mod_name, func_name, args_json, hot, warmup = sys.argv[1:6]
mod = importlib.import_module(mod_name)
func = getattr(mod, func_name)
args = tuple(json.loads(args_json))
m = measure_in_process(func, args=args, hot_iters=int(hot), warmup=int(warmup))
sys.stdout.write(json.dumps(m.to_dict()))
"""


def measure_in_subprocess(
    module: str, func: str, *, args: Sequence[Any] = (),
    hot_iters: int = 3, warmup: int = 1, timeout: float = 600.0,
) -> Measurement:
    """Run measurement in a fresh Python subprocess so RSS is clean."""
    proc = subprocess.run(
        [sys.executable, "-c", _SUBPROC_RUNNER, module, func, json.dumps(list(args)),
         str(hot_iters), str(warmup)],
        capture_output=True, text=True, timeout=timeout,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"subprocess failed: {proc.stderr}")
    return Measurement.from_dict(json.loads(proc.stdout))
```

- [ ] **Step 4: Run tests and confirm they pass**

Run: `pytest bench/tests/test_measure.py -v`
Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/measure.py bench/tests/test_measure.py
git commit -m "bench: Measurement dataclass + in-process and subprocess primitives"
```

---

## Milestone 1 — Corpus

### Task 2: `corpus.py` — declarative manifest

**Files:**
- Create: `bench/corpus.py`, `bench/tests/test_corpus.py`

- [ ] **Step 1: Write failing tests**

`bench/tests/test_corpus.py`:

```python
from bench.corpus import CORPUS, CorpusEntry, by_tier, TIERS


def test_tiers_known():
    assert TIERS == ("tiny", "small", "medium", "large", "huge")


def test_corpus_has_entries_in_each_tier_except_huge():
    for tier in ("tiny", "small", "medium", "large"):
        assert len(by_tier(tier)) >= 2, f"{tier} should have at least 2 entries"


def test_every_entry_has_minimum_fields():
    for e in CORPUS:
        assert isinstance(e, CorpusEntry)
        assert e.name
        assert e.url.startswith(("http://", "https://"))
        assert e.tier in TIERS
        assert e.approx_axioms > 0
        # SHA256 is 64 hex chars OR the literal "skip-checksum" for unpinned upstreams
        assert len(e.sha256) == 64 or e.sha256 == "skip-checksum"


def test_pizza_is_tiny():
    pizza = next(e for e in CORPUS if e.name == "pizza")
    assert pizza.tier == "tiny"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest bench/tests/test_corpus.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `bench/corpus.py`**

```python
"""Declarative corpus manifest. Each entry describes one ontology download."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tier = Literal["tiny", "small", "medium", "large", "huge"]
TIERS: tuple[Tier, ...] = ("tiny", "small", "medium", "large", "huge")


@dataclass(frozen=True)
class CorpusEntry:
    name: str                      # short identifier, e.g. "go-core"
    tier: Tier
    url: str                       # canonical download URL
    sha256: str                    # 64-hex SHA256 OR "skip-checksum" for moving upstreams
    approx_axioms: int             # documented in design spec §4
    fmt: Literal["owx", "rdfxml", "obo"]  # source format
    notes: str = ""


CORPUS: tuple[CorpusEntry, ...] = (
    # Tiny tier — DL tutorial ontologies
    CorpusEntry(
        name="pizza", tier="tiny",
        url="https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        sha256="skip-checksum", approx_axioms=250, fmt="rdfxml",
        notes="Manchester / Protege pizza tutorial ontology",
    ),
    CorpusEntry(
        name="wine", tier="tiny",
        url="https://www.w3.org/TR/owl-guide/wine.rdf",
        sha256="skip-checksum", approx_axioms=700, fmt="rdfxml",
        notes="W3C OWL Guide wine example",
    ),
    CorpusEntry(
        name="family", tier="tiny",
        url="https://raw.githubusercontent.com/owlcs/owlapi/version5/contract/src/test/resources/family.owl",
        sha256="skip-checksum", approx_axioms=150, fmt="rdfxml",
        notes="OWL-API family.owl test fixture",
    ),
    # Small tier
    CorpusEntry(
        name="sio", tier="small",
        url="https://raw.githubusercontent.com/MaastrichtU-IDS/semanticscience/master/ontology/sio/release/sio-release.owl",
        sha256="skip-checksum", approx_axioms=3_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="obi-core", tier="small",
        url="http://purl.obolibrary.org/obo/obi/dev/obi.owl",
        sha256="skip-checksum", approx_axioms=5_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="doid", tier="small",
        url="http://purl.obolibrary.org/obo/doid.owl",
        sha256="skip-checksum", approx_axioms=10_000, fmt="rdfxml",
    ),
    # Medium tier
    CorpusEntry(
        name="go-core", tier="medium",
        url="http://purl.obolibrary.org/obo/go/go-basic.obo",
        sha256="skip-checksum", approx_axioms=30_000, fmt="obo",
        notes="GO basic; converted to .owx via ROBOT at download time",
    ),
    CorpusEntry(
        name="chebi-lite", tier="medium",
        url="http://purl.obolibrary.org/obo/chebi/chebi_lite.owl",
        sha256="skip-checksum", approx_axioms=50_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="hp", tier="medium",
        url="http://purl.obolibrary.org/obo/hp.owl",
        sha256="skip-checksum", approx_axioms=20_000, fmt="rdfxml",
    ),
    # Large tier
    CorpusEntry(
        name="go-full", tier="large",
        url="http://purl.obolibrary.org/obo/go.owl",
        sha256="skip-checksum", approx_axioms=80_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="chebi-full", tier="large",
        url="http://purl.obolibrary.org/obo/chebi.owl",
        sha256="skip-checksum", approx_axioms=140_000, fmt="rdfxml",
    ),
    CorpusEntry(
        name="ncit", tier="large",
        url="http://purl.obolibrary.org/obo/ncit.owl",
        sha256="skip-checksum", approx_axioms=170_000, fmt="rdfxml",
    ),
    # Huge tier — license-gated, requires BENCH_SNOMED=1 + UMLS file on disk
    # (no entry committed; loader emits a note when BENCH_SNOMED is set)
)


def by_tier(tier: Tier) -> list[CorpusEntry]:
    return [e for e in CORPUS if e.tier == tier]
```

> The `"skip-checksum"` sentinel is intentional: OBO Foundry ontologies update
> monthly without versioned URLs. The first real bench snapshot pins a SHA per
> entry (we record the downloaded SHA256 in `bench/data/<name>.sha256` and the
> report header documents which corpus IRIs were pinned).

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest bench/tests/test_corpus.py -v`
Expected: 4 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/corpus.py bench/tests/test_corpus.py
git commit -m "bench: declarative corpus manifest (12 ontologies, tiered)"
```

---

### Task 3: `download.py` — fetch, verify, convert to `.omn`

**Files:**
- Create: `bench/download.py`, `bench/tests/test_download.py`

- [ ] **Step 1: Write failing tests**

`bench/tests/test_download.py`:

```python
from pathlib import Path

import pytest

from bench.corpus import CorpusEntry
from bench.download import (
    cached_omn_path,
    download_one,
    sha256_of,
)


def test_sha256_of_known_bytes(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello\n")
    # echo "hello" | sha256sum
    assert sha256_of(f) == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"


def test_cached_omn_path_uses_bench_data(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    e = CorpusEntry(
        name="x", tier="tiny", url="http://example.org/x.owl",
        sha256="skip-checksum", approx_axioms=10, fmt="rdfxml",
    )
    assert cached_omn_path(e) == tmp_path / "x.omn"


def test_download_one_short_circuits_when_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    e = CorpusEntry(
        name="cheese", tier="tiny", url="http://example.org/x.owl",
        sha256="skip-checksum", approx_axioms=10, fmt="rdfxml",
    )
    (tmp_path / "cheese.omn").write_text("Prefix: : <http://ex.org/>\nClass: Cheese\n")
    out = download_one(e)
    assert out == tmp_path / "cheese.omn"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest bench/tests/test_download.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `bench/download.py`**

```python
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
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest bench/tests/test_download.py -v`
Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/download.py bench/tests/test_download.py
git commit -m "bench: downloader with SHA256 verify + ROBOT-convert to .omn"
```

---

## Milestone 2 — Backends

### Task 4: Backend protocol + `owlready2_mem`

**Files:**
- Create: `bench/backends/__init__.py`, `bench/backends/owlready2_mem.py`, `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing tests**

`bench/tests/test_backends.py`:

```python
from pymos import parse
from bench.backends.owlready2_mem import OwlreadyMemBackend


def test_owlready_mem_load_and_select(pizza_text):
    onto = parse(pizza_text)
    b = OwlreadyMemBackend()
    handle = b.load(onto)
    assert handle is not None
    # owlready2 SPARQL is SELECT-only; CONSTRUCT is not supported by it
    rows = list(b.select(
        "SELECT DISTINCT ?c WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    assert len(rows) > 0
    b.close()


def test_owlready_mem_name_and_persistence_flag():
    b = OwlreadyMemBackend()
    assert b.name == "owlready2_mem"
    assert b.is_persistent is False
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest bench/tests/test_backends.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement the protocol and the backend**

`bench/backends/__init__.py`:

```python
"""Backend protocol and registry."""
from __future__ import annotations

from typing import Iterable, Protocol


class Backend(Protocol):
    name: str
    is_persistent: bool

    def load(self, ontology) -> object:
        """Populate the store from an owlready2 Ontology. Returns a handle
        (opaque; for endpoint backends it's a session)."""

    def construct(self, sparql: str) -> Iterable:
        """Run a CONSTRUCT query; return iterable of triples. May raise
        NotImplementedError for backends that don't support CONSTRUCT
        (notably owlready2's native engine)."""

    def select(self, sparql: str) -> Iterable:
        """Run a SELECT query; return iterable of result rows."""

    def close(self) -> None: ...
```

`bench/backends/owlready2_mem.py`:

```python
"""In-memory owlready2 backend (SQLite :memory:)."""
import io

import owlready2


class OwlreadyMemBackend:
    name = "owlready2_mem"
    is_persistent = False

    def __init__(self):
        self._world = owlready2.World()

    def load(self, ontology):
        # owlready2 ontologies live in their own World; copy via N-Triples.
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        buf.seek(0)
        # the World.get_ontology + load_file route round-trips axioms
        ont_iri = ontology.base_iri.rstrip("#").rstrip("/")
        new_onto = self._world.get_ontology(ont_iri)
        # write to a temp file because owlready2's load wants a path/file object
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".nt", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        new_onto.load(only_local=True, fileobj=open(path, "rb"))
        return new_onto

    def construct(self, sparql: str):
        raise NotImplementedError("owlready2's native SPARQL engine does not support CONSTRUCT")

    def select(self, sparql: str):
        return self._world.sparql(sparql)

    def close(self):
        self._world.close()
```

> Implementation note: owlready2's `World.sparql` does not parse CONSTRUCT. The
> bench cell logic must skip CONSTRUCT-on-owlready2 cells with a structured
> `n/a` reason ("backend does not support CONSTRUCT") in `results.json`.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest bench/tests/test_backends.py -v`
Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/backends bench/tests/test_backends.py
git commit -m "bench: Backend protocol + owlready2_mem (in-memory SQLite)"
```

---

### Task 5: `pyoxigraph_mem` backend

**Files:**
- Create: `bench/backends/pyoxigraph_mem.py`
- Modify: `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

Append to `bench/tests/test_backends.py`:

```python
from bench.backends.pyoxigraph_mem import PyoxigraphMemBackend


def test_pyoxigraph_mem_load_and_construct(pizza_text):
    onto = parse(pizza_text)
    b = PyoxigraphMemBackend()
    b.load(onto)
    triples = list(b.construct(
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5"
    ))
    assert len(triples) > 0
    rows = list(b.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))
    assert int(rows[0]["n"].value) > 0
    b.close()
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_backends.py -v -k pyoxigraph`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`bench/backends/pyoxigraph_mem.py`:

```python
"""In-memory pyoxigraph backend."""
import io
import tempfile

import pyoxigraph


class PyoxigraphMemBackend:
    name = "pyoxigraph_mem"
    is_persistent = False

    def __init__(self):
        self._store = pyoxigraph.Store()

    def load(self, ontology):
        # owlready2 → N-Triples (native, no rdflib hop) → pyoxigraph
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._store.load(buf.getvalue(), format=pyoxigraph.RdfFormat.N_TRIPLES)
        return self._store

    def construct(self, sparql: str):
        return self._store.query(sparql)

    def select(self, sparql: str):
        return self._store.query(sparql)

    def close(self):
        # in-memory store has no explicit close
        pass
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_backends.py -v -k pyoxigraph`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/backends/pyoxigraph_mem.py bench/tests/test_backends.py
git commit -m "bench: pyoxigraph_mem backend (in-memory Store, native N-Triples bridge)"
```

---

### Task 6: `rdflib_mem` backend

**Files:**
- Create: `bench/backends/rdflib_mem.py`
- Modify: `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.backends.rdflib_mem import RdflibMemBackend


def test_rdflib_mem_load_and_construct(pizza_text):
    onto = parse(pizza_text)
    b = RdflibMemBackend()
    b.load(onto)
    g = b.construct("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5")
    triples = list(g)
    assert len(triples) > 0
    b.close()
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_backends.py -v -k rdflib`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/backends/rdflib_mem.py`:

```python
"""In-memory rdflib backend. Expected to OOM past ChEBI-core; runner marks
oversized cells n/a via memory cap."""
import io

import rdflib


class RdflibMemBackend:
    name = "rdflib_mem"
    is_persistent = False

    def __init__(self):
        self._graph = rdflib.Graph()

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._graph.parse(data=buf.getvalue(), format="nt")
        return self._graph

    def construct(self, sparql: str):
        return self._graph.query(sparql).graph

    def select(self, sparql: str):
        return list(self._graph.query(sparql))

    def close(self):
        self._graph.close()
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_backends.py -v -k rdflib`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/backends/rdflib_mem.py bench/tests/test_backends.py
git commit -m "bench: rdflib_mem backend"
```

---

## Milestone 3 — Persistent backends

### Task 7: `owlready2_sqlite` backend

**Files:**
- Create: `bench/backends/owlready2_sqlite.py`
- Modify: `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

```python
from bench.backends.owlready2_sqlite import OwlreadySqliteBackend


def test_owlready_sqlite_persists_across_handles(pizza_text, tmp_path):
    onto = parse(pizza_text)
    db = tmp_path / "pizza.sqlite3"

    b1 = OwlreadySqliteBackend(db)
    b1.load(onto)
    rows1 = list(b1.select(
        "SELECT (COUNT(?c) AS ?n) WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    b1.close()

    # Open a fresh handle on the same SQLite file — data must survive.
    b2 = OwlreadySqliteBackend(db)
    rows2 = list(b2.select(
        "SELECT (COUNT(?c) AS ?n) WHERE { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?p }"
    ))
    assert rows1 == rows2
    assert b2.is_persistent is True
    b2.close()
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_backends.py -v -k sqlite`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/backends/owlready2_sqlite.py`:

```python
"""SQLite-on-disk owlready2 backend. Cold opens read from the file."""
import io
import tempfile
from pathlib import Path

import owlready2


class OwlreadySqliteBackend:
    is_persistent = True

    def __init__(self, db_path: Path):
        self.name = f"owlready2_sqlite[{db_path.name}]"
        self._world = owlready2.World(filename=str(db_path))

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        ont_iri = ontology.base_iri.rstrip("#").rstrip("/")
        new_onto = self._world.get_ontology(ont_iri)
        with tempfile.NamedTemporaryFile(suffix=".nt", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        new_onto.load(only_local=True, fileobj=open(path, "rb"))
        self._world.save()
        return new_onto

    def construct(self, sparql: str):
        raise NotImplementedError("owlready2's native SPARQL engine does not support CONSTRUCT")

    def select(self, sparql: str):
        return self._world.sparql(sparql)

    def close(self):
        self._world.save()
        self._world.close()
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_backends.py -v -k sqlite`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/backends/owlready2_sqlite.py bench/tests/test_backends.py
git commit -m "bench: owlready2_sqlite backend (file-backed SQLite)"
```

---

### Task 8: `pyoxigraph_rocksdb` backend

**Files:**
- Create: `bench/backends/pyoxigraph_rocksdb.py`
- Modify: `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

```python
from bench.backends.pyoxigraph_rocksdb import PyoxigraphRocksdbBackend


def test_pyoxigraph_rocksdb_persists(pizza_text, tmp_path):
    onto = parse(pizza_text)
    db = tmp_path / "pizza.ox"

    b1 = PyoxigraphRocksdbBackend(db)
    b1.load(onto)
    n1 = list(b1.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))[0]["n"].value
    b1.close()

    b2 = PyoxigraphRocksdbBackend(db)
    n2 = list(b2.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))[0]["n"].value
    assert n1 == n2
    assert b2.is_persistent is True
    b2.close()
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_backends.py -v -k rocksdb`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/backends/pyoxigraph_rocksdb.py`:

```python
"""RocksDB-backed pyoxigraph store."""
import io
from pathlib import Path

import pyoxigraph


class PyoxigraphRocksdbBackend:
    is_persistent = True

    def __init__(self, db_path: Path):
        self.name = f"pyoxigraph_rocksdb[{db_path.name}]"
        db_path.mkdir(parents=True, exist_ok=True)
        self._store = pyoxigraph.Store(str(db_path))

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        self._store.load(buf.getvalue(), format=pyoxigraph.RdfFormat.N_TRIPLES)
        self._store.flush()
        return self._store

    def construct(self, sparql: str):
        return self._store.query(sparql)

    def select(self, sparql: str):
        return self._store.query(sparql)

    def close(self):
        self._store.flush()
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_backends.py -v -k rocksdb`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/backends/pyoxigraph_rocksdb.py bench/tests/test_backends.py
git commit -m "bench: pyoxigraph_rocksdb backend (file-backed RocksDB)"
```

---

## Milestone 4 — Endpoint backend (docker)

### Task 9: `endpoint_oxigraph` via docker

**Files:**
- Create: `bench/backends/endpoint_oxigraph.py`
- Modify: `bench/tests/test_backends.py`

- [ ] **Step 1: Write failing test**

```python
from bench.backends.endpoint_oxigraph import EndpointOxigraphBackend
from bench.tests.conftest import requires_docker


@requires_docker
def test_endpoint_oxigraph_load_and_query(pizza_text):
    onto = parse(pizza_text)
    b = EndpointOxigraphBackend()  # spins up an ephemeral container on a random port
    try:
        b.load(onto)
        rows = list(b.select("SELECT (COUNT(?s) AS ?n) WHERE { ?s ?p ?o }"))
        assert int(rows[0]["n"]) > 0
    finally:
        b.close()
```

- [ ] **Step 2: Run, confirm fail or skip**

Run: `pytest bench/tests/test_backends.py -v -k endpoint`
Expected: FAIL (no module) — or SKIPPED if docker is unavailable.

- [ ] **Step 3: Implement**

`bench/backends/endpoint_oxigraph.py`:

```python
"""Remote SPARQL endpoint backed by a docker-managed Oxigraph server.

Spawns its own container so tests don't depend on docker-compose state.
"""
import io
import socket
import subprocess
import time
import uuid

import requests


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EndpointOxigraphBackend:
    is_persistent = True

    def __init__(self, image: str = "oxigraph/oxigraph:0.4.4"):
        self.name = f"endpoint_oxigraph[{image}]"
        self._port = _free_port()
        self._container = f"bench-oxigraph-{uuid.uuid4().hex[:8]}"
        self._url = f"http://127.0.0.1:{self._port}"
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", self._container,
             "-p", f"{self._port}:7878", image, "serve", "--bind", "0.0.0.0:7878"],
            check=True, capture_output=True,
        )
        self._wait_ready(timeout=30.0)

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if requests.get(f"{self._url}/", timeout=2).status_code in (200, 404):
                    return
            except requests.RequestException:
                time.sleep(0.5)
        raise RuntimeError("oxigraph endpoint did not become ready in time")

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        r = requests.post(
            f"{self._url}/store",
            data=buf.getvalue(),
            headers={"Content-Type": "application/n-triples"},
            timeout=300,
        )
        r.raise_for_status()

    def construct(self, sparql: str):
        r = requests.post(
            f"{self._url}/query",
            data={"query": sparql},
            headers={"Accept": "application/n-triples"},
            timeout=300,
        )
        r.raise_for_status()
        return r.text.splitlines()

    def select(self, sparql: str):
        r = requests.post(
            f"{self._url}/query",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
            timeout=300,
        )
        r.raise_for_status()
        return r.json().get("results", {}).get("bindings", [])

    def close(self):
        subprocess.run(["docker", "rm", "-f", self._container],
                       check=False, capture_output=True)
```

- [ ] **Step 4: Run, confirm pass (when docker present)**

Run: `pytest bench/tests/test_backends.py -v -k endpoint`
Expected: 1 passing (or SKIPPED without docker).

- [ ] **Step 5: Commit**

```bash
git add bench/backends/endpoint_oxigraph.py bench/tests/test_backends.py
git commit -m "bench: endpoint_oxigraph backend (ephemeral docker container)"
```

---

## Milestone 5 — Workloads

### Task 10: `workloads/parse.py`

**Files:**
- Create: `bench/workloads/__init__.py`, `bench/workloads/parse.py`, `bench/tests/test_workloads.py`

- [ ] **Step 1: Write failing test**

`bench/tests/test_workloads.py`:

```python
from pathlib import Path

from bench.workloads.parse import bench_parse


def test_bench_parse_returns_extras_with_axiom_count(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_parse(str(p), hot_iters=2, warmup=1)
    assert m.wall_cold > 0
    assert m.extras["axiom_count"] > 0
    assert m.extras["bytes"] == len(pizza_text.encode())
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_workloads.py -v -k parse`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/workloads/__init__.py`:

```python
"""Workload modules: parse, render, query."""
```

`bench/workloads/parse.py`:

```python
"""Parse workload: pymos.parse() on an .omn file."""
from pathlib import Path

import pymos

from bench.measure import Measurement, measure_in_subprocess


def _do_parse(path: str) -> None:
    """Parse a .omn file. Side-effect target for measurement."""
    pymos.parse(Path(path).read_text())


def _count_axioms(path: str) -> int:
    onto = pymos.parse(Path(path).read_text())
    n = 0
    for c in onto.classes():
        n += len([s for s in c.is_a if s is not __import__("owlready2").Thing])
        n += len(list(c.equivalent_to))
    for p in onto.object_properties():
        n += len(list(p.domain)) + len(list(p.range))
    for p in onto.data_properties():
        n += len(list(p.domain)) + len(list(p.range))
    return n


def bench_parse(path: str, *, hot_iters: int = 3, warmup: int = 1) -> Measurement:
    m = measure_in_subprocess(
        "bench.workloads.parse", "_do_parse",
        args=(path,), hot_iters=hot_iters, warmup=warmup,
    )
    m.extras["axiom_count"] = _count_axioms(path)
    m.extras["bytes"] = Path(path).stat().st_size
    return m
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_workloads.py -v -k parse`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/workloads bench/tests/test_workloads.py
git commit -m "bench: parse workload with axiom-count + bytes extras"
```

---

### Task 11: `workloads/render.py`

**Files:**
- Create: `bench/workloads/render.py`
- Modify: `bench/tests/test_workloads.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.workloads.render import bench_render


def test_bench_render_idempotent(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_render(str(p), hot_iters=2, warmup=1)
    assert m.wall_cold > 0
    assert m.extras["idempotent_second_pass"] is True
    assert m.extras["bytes_emitted"] > 0
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_workloads.py -v -k render`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/workloads/render.py`:

```python
"""Render workload: pymos.render() round-trip + idempotency check."""
from pathlib import Path

import pymos

from bench.measure import Measurement, measure_in_subprocess


def _do_render(path: str) -> None:
    onto = pymos.parse(Path(path).read_text())
    pymos.render(onto)


def _check_idempotent(path: str) -> tuple[bool, int]:
    text = Path(path).read_text()
    rendered1 = pymos.render(pymos.parse(text))
    rendered2 = pymos.render(pymos.parse(rendered1))
    return (rendered1 == rendered2, len(rendered1.encode()))


def bench_render(path: str, *, hot_iters: int = 3, warmup: int = 1) -> Measurement:
    m = measure_in_subprocess(
        "bench.workloads.render", "_do_render",
        args=(path,), hot_iters=hot_iters, warmup=warmup,
    )
    idempotent, n_bytes = _check_idempotent(path)
    m.extras["idempotent_second_pass"] = idempotent
    m.extras["bytes_emitted"] = n_bytes
    return m
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_workloads.py -v -k render`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/workloads/render.py bench/tests/test_workloads.py
git commit -m "bench: render workload with parse→render→parse idempotency check"
```

---

### Task 12: `workloads/targets.py` + `workloads/query.py`

**Files:**
- Create: `bench/workloads/targets.py`, `bench/workloads/query.py`
- Modify: `bench/tests/test_workloads.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
from bench.workloads.targets import pick_targets
from bench.workloads.query import bench_query
from bench.backends.pyoxigraph_mem import PyoxigraphMemBackend


def test_pick_targets_returns_three(pizza_text):
    import pymos
    onto = pymos.parse(pizza_text)
    targets = pick_targets(onto, k=3)
    assert len(targets) == 3
    assert all(t.startswith("http") for t in targets)


def test_bench_query_super_construct(pizza_text):
    import pymos
    onto = pymos.parse(pizza_text)
    targets = pick_targets(onto, k=1)
    backend = PyoxigraphMemBackend()
    backend.load(onto)
    m = bench_query(
        backend_name="pyoxigraph_mem",
        target_iri=targets[0],
        relation="super",
        construct=True,
        hot_iters=2,
        warmup=1,
    )
    assert m.wall_cold >= 0
    assert m.extras["relation"] == "super"
    backend.close()
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_workloads.py -v -k targets`
Expected: FAIL.

- [ ] **Step 3: Implement `targets.py`**

```python
"""Pick three representative target classes per ontology: highest-degree
(most super-/subclass references), a leaf (no subclasses), and a mid-depth
interior class."""
from typing import List


def pick_targets(onto, *, k: int = 3) -> List[str]:
    import owlready2

    classes = [c for c in onto.classes() if c is not owlready2.Thing]
    if not classes:
        return []

    # Degree = |subclasses asserted| + |superclasses asserted (excluding Thing)|
    def degree(c) -> int:
        subs = [x for x in onto.world.sparql(
            f"SELECT (COUNT(?s) AS ?n) WHERE {{ ?s <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{c.iri}> }}"
        )]
        n_sub = int(subs[0][0]) if subs else 0
        supers = [s for s in c.is_a if s is not owlready2.Thing]
        return n_sub + len(supers)

    scored = sorted(classes, key=degree, reverse=True)
    if len(scored) <= k:
        return [c.iri for c in scored]

    leaves = [c for c in classes if not list(c.subclasses())]
    leaf = leaves[0] if leaves else scored[-1]

    return [
        scored[0].iri,
        scored[len(scored) // 2].iri,
        leaf.iri,
    ][:k]
```

- [ ] **Step 4: Implement `query.py`**

`bench/workloads/query.py`:

```python
"""Query workload: time class_relations_query over a chosen backend."""
import importlib

from pymos import class_relations_query

from bench.measure import Measurement, measure_in_subprocess


_BACKEND_FACTORIES = {
    "owlready2_mem": ("bench.backends.owlready2_mem", "OwlreadyMemBackend"),
    "pyoxigraph_mem": ("bench.backends.pyoxigraph_mem", "PyoxigraphMemBackend"),
    "rdflib_mem": ("bench.backends.rdflib_mem", "RdflibMemBackend"),
}


def _do_query(
    onto_path: str, backend_name: str, target_iri: str,
    relation: str, construct: bool,
) -> None:
    import pymos
    onto = pymos.parse(open(onto_path).read())
    mod_name, cls_name = _BACKEND_FACTORIES[backend_name]
    cls = getattr(importlib.import_module(mod_name), cls_name)
    b = cls()
    b.load(onto)
    q = class_relations_query(f"<{target_iri}>", relations=(relation,), construct=construct)
    method = b.construct if construct else b.select
    try:
        list(method(q))
    except NotImplementedError:
        pass  # owlready2 + CONSTRUCT — handled by the runner via per-cell n/a check
    b.close()


def bench_query(
    *, onto_path: str = "", backend_name: str = "pyoxigraph_mem",
    target_iri: str, relation: str, construct: bool = True,
    hot_iters: int = 3, warmup: int = 1,
) -> Measurement:
    if not onto_path:
        # Inline-only path is used by unit tests: build a tiny ontology inline
        import pymos
        onto = pymos.parse(open("tests/data/pizza.omn").read())
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".omn", delete=False, mode="w") as f:
            f.write(open("tests/data/pizza.omn").read())
            onto_path = f.name

    m = measure_in_subprocess(
        "bench.workloads.query", "_do_query",
        args=(onto_path, backend_name, target_iri, relation, construct),
        hot_iters=hot_iters, warmup=warmup,
    )
    m.extras["relation"] = relation
    m.extras["construct"] = construct
    m.extras["backend"] = backend_name
    m.extras["target"] = target_iri
    return m
```

- [ ] **Step 5: Run, confirm pass**

Run: `pytest bench/tests/test_workloads.py -v -k "targets or query"`
Expected: 2 passing.

- [ ] **Step 6: Commit**

```bash
git add bench/workloads/targets.py bench/workloads/query.py bench/tests/test_workloads.py
git commit -m "bench: target picker + query workload (CONSTRUCT/SELECT × relation × backend)"
```

---

## Milestone 6 — Reasoners

### Task 13: Reasoner protocol + `none` + `owlrl`

**Files:**
- Create: `bench/reasoners/__init__.py`, `bench/reasoners/none.py`, `bench/reasoners/owlrl.py`, `bench/tests/test_reasoners.py`

- [ ] **Step 1: Write failing tests**

`bench/tests/test_reasoners.py`:

```python
from pathlib import Path

from bench.reasoners.none import NoneReasoner
from bench.reasoners.owlrl import OwlrlReasoner


def test_none_reasoner_returns_input(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    r = NoneReasoner()
    out = r.materialise(p)
    assert out == p


def test_owlrl_reasoner_adds_inferred_triples(pizza_text, tmp_path):
    import rdflib

    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    r = OwlrlReasoner()
    out = r.materialise(p)
    assert out != p
    # owlrl writes N-Triples; the inferred-triple count must exceed the asserted count
    g_in = rdflib.Graph()
    import pymos
    # convert input via pymos → ntriples
    import io
    buf = io.BytesIO()
    pymos.parse(pizza_text).save(file=buf, format="ntriples")
    g_in.parse(data=buf.getvalue(), format="nt")

    g_out = rdflib.Graph()
    g_out.parse(out, format="nt")

    assert len(g_out) > len(g_in)
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_reasoners.py -v -k "none or owlrl"`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/reasoners/__init__.py`:

```python
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
```

`bench/reasoners/none.py`:

```python
from pathlib import Path


class NoneReasoner:
    name = "none"
    profile = "none"
    wrapper = "in-process"

    def materialise(self, source: Path) -> Path:
        return source
```

`bench/reasoners/owlrl.py`:

```python
"""Pure-Python OWL2 RL reasoner via rdflib + owlrl."""
import io
from pathlib import Path

import owlrl
import rdflib

import pymos


class OwlrlReasoner:
    name = "owlrl"
    profile = "RL"
    wrapper = "in-process"

    def materialise(self, source: Path) -> Path:
        onto = pymos.parse(source.read_text())
        buf = io.BytesIO()
        onto.save(file=buf, format="ntriples")
        g = rdflib.Graph()
        g.parse(data=buf.getvalue(), format="nt")

        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)

        out = source.with_suffix(".owlrl.nt")
        g.serialize(destination=str(out), format="nt")
        return out
```

> Backends will need to learn to load N-Triples directly (currently they go via
> owlready2 save). For owlrl outputs, the runner will need to detect `.nt`
> extension and load with the appropriate path. This is wired up in Task 17.

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_reasoners.py -v -k "none or owlrl"`
Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/reasoners bench/tests/test_reasoners.py
git commit -m "bench: reasoners protocol + NoneReasoner + OwlrlReasoner (in-process)"
```

---

### Task 14: `reasoners/robot_docker.py` — shared ROBOT wrapper

**Files:**
- Create: `bench/reasoners/robot_docker.py`
- Modify: `bench/tests/test_reasoners.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.reasoners.robot_docker import RobotDocker
from bench.tests.conftest import requires_docker


@requires_docker
def test_robot_docker_version_smoke():
    rd = RobotDocker(image="obolibrary/robot:v1.9.6")
    v = rd.version()
    assert "ROBOT" in v or "robot" in v.lower()
```

- [ ] **Step 2: Run, confirm fail or skip**

Run: `pytest bench/tests/test_reasoners.py -v -k robot_docker`
Expected: FAIL or SKIPPED.

- [ ] **Step 3: Implement**

`bench/reasoners/robot_docker.py`:

```python
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
        """Run `robot reason --reasoner X --input src --output out`.

        src and out MUST live under the same directory (which is mounted).
        """
        if src.parent.resolve() != out.parent.resolve():
            raise ValueError("src and out must share a parent directory for docker mount")
        mount = src.parent
        self._run(
            ["reason", "--reasoner", reasoner,
             "--input", src.name, "--output", out.name],
            mount=mount,
        )
        return out
```

- [ ] **Step 4: Run, confirm pass (with docker)**

Run: `pytest bench/tests/test_reasoners.py -v -k robot_docker`
Expected: 1 passing or SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add bench/reasoners/robot_docker.py bench/tests/test_reasoners.py
git commit -m "bench: shared ROBOT-docker wrapper for HermiT/Pellet/ELK fairness"
```

---

### Task 15: HermiT / Pellet / ELK reasoners

**Files:**
- Create: `bench/reasoners/hermit.py`, `bench/reasoners/pellet.py`, `bench/reasoners/elk.py`
- Modify: `bench/tests/test_reasoners.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
import pytest

from bench.reasoners.hermit import HermitReasoner
from bench.reasoners.pellet import PelletReasoner
from bench.reasoners.elk import ElkReasoner


@requires_docker
@pytest.mark.parametrize("Reasoner,name,profile", [
    (HermitReasoner, "hermit", "DL"),
    (PelletReasoner, "pellet", "DL"),
    (ElkReasoner,    "elk",    "EL"),
])
def test_robot_reasoner_materialises_pizza(Reasoner, name, profile, pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    r = Reasoner()
    assert r.name == name
    assert r.profile == profile
    out = r.materialise(p)
    assert out.exists()
    assert out != p
    # ROBOT reason writes a saturated OWL file; non-empty
    assert out.stat().st_size > 0
```

- [ ] **Step 2: Run, confirm fail or skip**

Run: `pytest bench/tests/test_reasoners.py -v -k "hermit or pellet or elk"`
Expected: FAIL or SKIPPED.

- [ ] **Step 3: Implement (three near-identical thin wrappers)**

`bench/reasoners/hermit.py`:

```python
from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class HermitReasoner:
    name = "hermit"
    profile = "DL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".hermit.owx")
        return self._robot.reason(source, reasoner="HermiT", out=out)
```

`bench/reasoners/pellet.py`:

```python
from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class PelletReasoner:
    name = "pellet"
    profile = "DL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".pellet.owx")
        return self._robot.reason(source, reasoner="Pellet", out=out)
```

`bench/reasoners/elk.py`:

```python
from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class ElkReasoner:
    name = "elk"
    profile = "EL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".elk.owx")
        return self._robot.reason(source, reasoner="ELK", out=out)
```

- [ ] **Step 4: Run, confirm pass (with docker)**

Run: `pytest bench/tests/test_reasoners.py -v -k "hermit or pellet or elk"`
Expected: 3 passing or SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add bench/reasoners/hermit.py bench/reasoners/pellet.py bench/reasoners/elk.py bench/tests/test_reasoners.py
git commit -m "bench: HermiT / Pellet / ELK reasoners (ROBOT-docker wrapper)"
```

---

### Task 16: `reasoners/konclude.py`

**Files:**
- Create: `bench/reasoners/konclude.py`
- Modify: `bench/tests/test_reasoners.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.reasoners.konclude import KoncludeReasoner


@requires_docker
def test_konclude_materialises_owx_input(pizza_text, tmp_path):
    # Konclude requires OWX; convert pizza.omn → pizza.owx first via robot_docker
    from bench.reasoners.robot_docker import RobotDocker
    rd = RobotDocker()
    omn = tmp_path / "pizza.omn"; omn.write_text(pizza_text)
    owx = tmp_path / "pizza.owx"
    rd._run(["convert", "--input", "pizza.omn", "--output", "pizza.owx"], mount=tmp_path)
    assert owx.exists()

    r = KoncludeReasoner()
    out = r.materialise(owx)
    assert out.exists()
    assert r.profile == "DL"
```

- [ ] **Step 2: Run, confirm fail or skip**

Run: `pytest bench/tests/test_reasoners.py -v -k konclude`
Expected: FAIL or SKIPPED.

- [ ] **Step 3: Implement**

`bench/reasoners/konclude.py`:

```python
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
```

- [ ] **Step 4: Run, confirm pass (with docker)**

Run: `pytest bench/tests/test_reasoners.py -v -k konclude`
Expected: 1 passing or SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add bench/reasoners/konclude.py bench/tests/test_reasoners.py
git commit -m "bench: Konclude reasoner (konclude-docker, OWX input)"
```

---

### Task 17: `reasoners/floors.py` — wrapper startup floors

**Files:**
- Create: `bench/reasoners/floors.py`
- Modify: `bench/tests/test_reasoners.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.reasoners.floors import measure_wrapper_floors


def test_measure_wrapper_floors_returns_dict():
    floors = measure_wrapper_floors(include_docker=False)
    assert "owlrl" in floors
    assert floors["owlrl"] >= 0


@requires_docker
def test_measure_wrapper_floors_with_docker():
    floors = measure_wrapper_floors(include_docker=True)
    for name in ("robot-docker", "konclude-docker"):
        assert name in floors
        assert floors[name] > 0
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_reasoners.py -v -k floors`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/reasoners/floors.py`:

```python
"""Per-wrapper startup floor (cold time for a no-op invocation).

These are reported alongside reasoner cells in the snapshot — never
subtracted silently from cell times. See rustdl-reasoner-bench memory.
"""
import subprocess
import time
from typing import Dict


def _time(cmd: list[str]) -> float:
    t = time.perf_counter()
    subprocess.run(cmd, check=True, capture_output=True)
    return time.perf_counter() - t


def measure_wrapper_floors(include_docker: bool = True) -> Dict[str, float]:
    floors: Dict[str, float] = {}

    # In-process Python import
    floors["owlrl"] = _time(["python", "-c", "import owlrl"])

    if not include_docker:
        return floors

    floors["robot-docker"] = _time(
        ["docker", "run", "--rm", "obolibrary/robot:v1.9.6", "robot", "--version"]
    )
    floors["konclude-docker"] = _time(
        ["docker", "run", "--rm", "konclude/konclude:latest", "Konclude", "-v"]
    )
    return floors
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_reasoners.py -v -k floors`
Expected: 2 passing (one SKIPPED without docker).

- [ ] **Step 5: Commit**

```bash
git add bench/reasoners/floors.py bench/tests/test_reasoners.py
git commit -m "bench: wrapper startup floor measurement (owlrl, robot, konclude)"
```

---

## Milestone 7 — Snapshot runner

### Task 18: `runners/snapshot.py` — orchestrate cells → `results.json`

**Files:**
- Create: `bench/runners/__init__.py`, `bench/runners/snapshot.py`, `bench/tests/test_snapshot.py`

- [ ] **Step 1: Write failing test**

`bench/tests/test_snapshot.py`:

```python
import json
from pathlib import Path

from bench.runners.snapshot import run_snapshot


def test_snapshot_pizza_no_reasoner_pyoxigraph_only(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    # Seed the corpus dir with pizza so download is a no-op
    pizza_src = Path(__file__).resolve().parents[2] / "tests" / "data" / "pizza.omn"
    (tmp_path / "pizza.omn").write_text(pizza_src.read_text())

    out_dir = tmp_path / "run"
    run_snapshot(
        out_dir=out_dir,
        ontologies=["pizza"],
        backends=["pyoxigraph_mem"],
        reasoners=["none"],
        relations=("super",),
        construct_modes=(True,),
        targets_per_ontology=1,
        hot_iters=1,
        warmup=0,
    )
    results = json.loads((out_dir / "results.json").read_text())
    assert results["cells"]
    cell0 = results["cells"][0]
    assert cell0["ontology"] == "pizza"
    assert cell0["backend"] == "pyoxigraph_mem"
    assert cell0["reasoner"] == "none"
    assert "wall_cold" in cell0["measurement"]
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_snapshot.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/runners/__init__.py`:

```python
"""Snapshot runner package."""
```

`bench/runners/snapshot.py`:

```python
"""Snapshot orchestrator: iterate (ontology × backend × reasoner × workload)
cells, run each in a fresh subprocess, write results.json + .csv."""
from __future__ import annotations

import csv
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import pymos

from bench.corpus import CORPUS, CorpusEntry
from bench.download import cached_omn_path, download_one
from bench.measure import Measurement
from bench.workloads.parse import bench_parse
from bench.workloads.render import bench_render
from bench.workloads.query import bench_query
from bench.workloads.targets import pick_targets


@dataclass
class Cell:
    ontology: str
    workload: str
    backend: str | None
    reasoner: str
    relation: str | None
    construct: bool | None
    target: str | None
    measurement: dict | None = None
    error: str | None = None
    skipped_reason: str | None = None


def _env_header() -> dict:
    import platform
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "pymos_sha": _git_sha(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_count": os.cpu_count(),
    }


def _git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
        ).stdout.strip()[:12]
    except Exception:
        return "unknown"


def _entry(name: str) -> CorpusEntry:
    for e in CORPUS:
        if e.name == name:
            return e
    raise KeyError(f"unknown ontology: {name}")


def _resolve_omn(name: str) -> Path:
    """Path to the ontology .omn — download if needed unless BENCH_DATA_DIR
    already has it (covers the test fast-path)."""
    e = _entry(name)
    p = cached_omn_path(e)
    if p.exists():
        return p
    return download_one(e)


def run_snapshot(
    *,
    out_dir: Path,
    ontologies: list[str],
    backends: list[str],
    reasoners: list[str],
    relations: Iterable[str] = ("super", "sub", "direct_super", "direct_sub", "equiv", "individual"),
    construct_modes: Iterable[bool] = (True, False),
    targets_per_ontology: int = 3,
    hot_iters: int = 3,
    warmup: int = 1,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cells: list[Cell] = []

    for onto_name in ontologies:
        omn = _resolve_omn(onto_name)
        # parse + render workloads run once per ontology (no backend/reasoner axis)
        cells.append(Cell(
            ontology=onto_name, workload="parse",
            backend=None, reasoner="none", relation=None, construct=None, target=None,
            measurement=bench_parse(str(omn), hot_iters=hot_iters, warmup=warmup).to_dict(),
        ))
        cells.append(Cell(
            ontology=onto_name, workload="render",
            backend=None, reasoner="none", relation=None, construct=None, target=None,
            measurement=bench_render(str(omn), hot_iters=hot_iters, warmup=warmup).to_dict(),
        ))

        # query workload: target × relation × mode × backend × reasoner
        onto = pymos.parse(omn.read_text())
        targets = pick_targets(onto, k=targets_per_ontology)

        for backend_name in backends:
            for reasoner_name in reasoners:
                # CONSTRUCT on owlready2 backends is structurally n/a
                for construct in construct_modes:
                    if construct and backend_name.startswith("owlready2"):
                        for relation in relations:
                            for target in targets:
                                cells.append(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    skipped_reason="owlready2 SPARQL engine does not support CONSTRUCT",
                                ))
                        continue
                    for relation in relations:
                        for target in targets:
                            try:
                                m = bench_query(
                                    onto_path=str(omn),
                                    backend_name=backend_name,
                                    target_iri=target,
                                    relation=relation,
                                    construct=construct,
                                    hot_iters=hot_iters,
                                    warmup=warmup,
                                )
                                cells.append(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    measurement=m.to_dict(),
                                ))
                            except Exception as exc:
                                cells.append(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    error=f"{type(exc).__name__}: {exc}",
                                ))

    payload = {"env": _env_header(), "cells": [asdict(c) for c in cells]}
    (out_dir / "results.json").write_text(json.dumps(payload, indent=2))

    # Also flat CSV
    with (out_dir / "results.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ontology", "workload", "backend", "reasoner",
                    "relation", "construct", "target", "wall_cold",
                    "wall_hot_median", "peak_rss_bytes", "error", "skipped_reason"])
        for c in cells:
            m = c.measurement or {}
            w.writerow([c.ontology, c.workload, c.backend, c.reasoner,
                        c.relation, c.construct, c.target,
                        m.get("wall_cold"), m.get("wall_hot_median"),
                        m.get("peak_rss_bytes"), c.error, c.skipped_reason])

    return out_dir / "results.json"
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_snapshot.py -v`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/runners bench/tests/test_snapshot.py
git commit -m "bench: snapshot runner — orchestrate cells, emit results.json + .csv"
```

---

### Task 19: `runners/plots.py` — scaling curves

**Files:**
- Create: `bench/runners/plots.py`
- Modify: `bench/tests/test_snapshot.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.runners.plots import write_scaling_plots


def test_write_scaling_plots_produces_png(tmp_path):
    results_json = tmp_path / "results.json"
    results_json.write_text(json.dumps({
        "env": {},
        "cells": [
            {"ontology": "pizza", "workload": "parse", "backend": None,
             "reasoner": "none", "relation": None, "construct": None, "target": None,
             "measurement": {"wall_cold": 0.1, "wall_hot_median": 0.08,
                             "wall_hot_samples": [0.08, 0.08, 0.08],
                             "wall_hot_stddev": 0.0, "peak_rss_bytes": 50_000_000,
                             "peak_python_bytes": 1_000_000, "cpu_cold": 0.09,
                             "cpu_hot_median": 0.07,
                             "extras": {"axiom_count": 250, "bytes": 5000}},
             "error": None, "skipped_reason": None},
            {"ontology": "wine", "workload": "parse", "backend": None,
             "reasoner": "none", "relation": None, "construct": None, "target": None,
             "measurement": {"wall_cold": 0.25, "wall_hot_median": 0.2,
                             "wall_hot_samples": [0.2, 0.2, 0.2],
                             "wall_hot_stddev": 0.0, "peak_rss_bytes": 80_000_000,
                             "peak_python_bytes": 2_000_000, "cpu_cold": 0.22,
                             "cpu_hot_median": 0.18,
                             "extras": {"axiom_count": 700, "bytes": 14000}},
             "error": None, "skipped_reason": None},
        ],
    }))

    out_dir = tmp_path / "plots"
    write_scaling_plots(results_json, out_dir)
    parse_png = out_dir / "parse_scaling.png"
    assert parse_png.exists()
    assert parse_png.stat().st_size > 0
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_snapshot.py -v -k plots`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/runners/plots.py`:

```python
"""Scaling-curve plots: axioms vs wall-time, per workload."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_scaling_plots(results_json: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(Path(results_json).read_text())

    parse_cells = [c for c in payload["cells"] if c["workload"] == "parse" and c.get("measurement")]
    if parse_cells:
        xs = [c["measurement"]["extras"]["axiom_count"] for c in parse_cells]
        ys = [c["measurement"]["wall_hot_median"] for c in parse_cells]
        labels = [c["ontology"] for c in parse_cells]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(xs, ys)
        for x, y, label in zip(xs, ys, labels):
            ax.annotate(label, (x, y), fontsize=8)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("axioms")
        ax.set_ylabel("parse wall (s, median of hot iters)")
        ax.set_title("pymos parse scaling")
        fig.tight_layout()
        fig.savefig(out_dir / "parse_scaling.png", dpi=120)
        plt.close(fig)
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_snapshot.py -v -k plots`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/runners/plots.py bench/tests/test_snapshot.py
git commit -m "bench: scaling-plot generator (matplotlib, log-log axioms vs wall)"
```

---

### Task 20: `runners/report.py` — narrative markdown emitter

**Files:**
- Create: `bench/runners/report.py`
- Modify: `bench/tests/test_snapshot.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from bench.runners.report import write_report


def test_write_report_emits_markdown(tmp_path):
    results_json = tmp_path / "results.json"
    results_json.write_text(json.dumps({
        "env": {"host": "h", "platform": "p", "python": "3.12.1",
                "pymos_sha": "abc1234", "timestamp": "2026-05-28 21:00:00",
                "cpu_count": 8},
        "cells": [
            {"ontology": "pizza", "workload": "parse",
             "backend": None, "reasoner": "none", "relation": None,
             "construct": None, "target": None,
             "measurement": {"wall_cold": 0.1, "wall_hot_median": 0.08,
                             "wall_hot_samples": [0.08]*3, "wall_hot_stddev": 0.0,
                             "peak_rss_bytes": 50_000_000, "peak_python_bytes": 1_000_000,
                             "cpu_cold": 0.09, "cpu_hot_median": 0.07,
                             "extras": {"axiom_count": 250, "bytes": 5000}},
             "error": None, "skipped_reason": None},
        ],
    }))

    md = tmp_path / "report.md"
    write_report(results_json, md, floors={"owlrl": 0.05, "robot-docker": 2.4})
    text = md.read_text()
    assert "# Perf snapshot — 2026-05-28" in text
    assert "## Headline" in text
    assert "pizza" in text
    assert "robot-docker" in text and "2.4" in text  # floors table
    assert "0.08" in text                            # parse wall
```

- [ ] **Step 2: Run, confirm fail**

Run: `pytest bench/tests/test_snapshot.py -v -k report`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bench/runners/report.py`:

```python
"""Narrative markdown report — mirrors rustdl perf-*.md style."""
import json
from pathlib import Path
from typing import Dict


def _fmt(x, n: int = 3) -> str:
    return "n/a" if x is None else f"{float(x):.{n}f}"


def write_report(results_json: Path, out_md: Path, *, floors: Dict[str, float] | None = None) -> None:
    payload = json.loads(Path(results_json).read_text())
    env = payload["env"]
    cells = payload["cells"]
    floors = floors or {}

    lines: list[str] = []
    date = env["timestamp"].split()[0]
    lines.append(f"# Perf snapshot — {date}, pymos")
    lines.append("")
    lines.append(f"Host: {env['host']}, {env['platform']}, python {env['python']}.")
    lines.append(f"pymos: {env['pymos_sha']}.  CPU count: {env['cpu_count']}.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("_TODO: hand-write a one-paragraph summary after reading the tables._")
    lines.append("")

    # Parse table
    parse_cells = [c for c in cells if c["workload"] == "parse" and c.get("measurement")]
    if parse_cells:
        lines.append("## 1. Parse")
        lines.append("")
        lines.append("| ontology | axioms | bytes | cold (s) | hot median (s) | peak RSS (MB) |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for c in parse_cells:
            m = c["measurement"]; e = m["extras"]
            lines.append(
                f"| {c['ontology']} | {e['axiom_count']} | {e['bytes']} | "
                f"{_fmt(m['wall_cold'])} | {_fmt(m['wall_hot_median'])} | "
                f"{m['peak_rss_bytes']//1_000_000} |"
            )
        lines.append("")

    # Render table
    render_cells = [c for c in cells if c["workload"] == "render" and c.get("measurement")]
    if render_cells:
        lines.append("## 2. Render")
        lines.append("")
        lines.append("| ontology | bytes emitted | cold (s) | hot median (s) | idempotent? |")
        lines.append("|---|---:|---:|---:|:---:|")
        for c in render_cells:
            m = c["measurement"]; e = m["extras"]
            lines.append(
                f"| {c['ontology']} | {e['bytes_emitted']} | "
                f"{_fmt(m['wall_cold'])} | {_fmt(m['wall_hot_median'])} | "
                f"{'yes' if e['idempotent_second_pass'] else 'no'} |"
            )
        lines.append("")

    # Query summary — one row per (ontology, backend, reasoner)
    q_cells = [c for c in cells if c["workload"] == "query" and c.get("measurement")]
    if q_cells:
        lines.append("## 3. Query — summary (median hot across relations × targets)")
        lines.append("")
        lines.append("| ontology | backend | reasoner | median hot (s) | cells |")
        lines.append("|---|---|---|---:|---:|")
        groups: dict[tuple, list[float]] = {}
        for c in q_cells:
            key = (c["ontology"], c["backend"], c["reasoner"])
            groups.setdefault(key, []).append(c["measurement"]["wall_hot_median"])
        for (o, b, r), walls in sorted(groups.items()):
            import statistics
            lines.append(f"| {o} | {b} | {r} | {_fmt(statistics.median(walls))} | {len(walls)} |")
        lines.append("")

    # Wrapper floors
    if floors:
        lines.append("## 4. Wrapper startup floors")
        lines.append("")
        lines.append("| wrapper | floor (s) |")
        lines.append("|---|---:|")
        for k, v in sorted(floors.items()):
            lines.append(f"| {k} | {_fmt(v, 2)} |")
        lines.append("")

    # Skipped / errored
    n_skip = sum(1 for c in cells if c.get("skipped_reason"))
    n_err = sum(1 for c in cells if c.get("error"))
    lines.append("## 5. Coverage")
    lines.append("")
    lines.append(f"- Total cells: {len(cells)}")
    lines.append(f"- Skipped (structurally n/a): {n_skip}")
    lines.append(f"- Errored: {n_err}")
    lines.append("")

    out_md.write_text("\n".join(lines))
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest bench/tests/test_snapshot.py -v -k report`
Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add bench/runners/report.py bench/tests/test_snapshot.py
git commit -m "bench: narrative markdown report (rustdl-style sections + floors + coverage)"
```

---

### Task 21: CLI entry — `python -m bench.runners.snapshot`

**Files:**
- Modify: `bench/runners/snapshot.py` (append `__main__`)

- [ ] **Step 1: Add CLI**

Append to `bench/runners/snapshot.py`:

```python
def _cli():
    import argparse, datetime as dt
    p = argparse.ArgumentParser(description="pymos perf snapshot runner")
    p.add_argument("--tier", default="tiny",
                   help="comma-separated tiers (tiny,small,medium,large,huge) or 'all'")
    p.add_argument("--backends", default="pyoxigraph_mem,owlready2_mem",
                   help="comma-separated backend names")
    p.add_argument("--reasoners", default="none,owlrl",
                   help="comma-separated reasoner names")
    p.add_argument("--relations", default="super,sub,direct_super,direct_sub,equiv,individual")
    p.add_argument("--targets-per-ontology", type=int, default=3)
    p.add_argument("--hot-iters", type=int, default=3)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--out", type=Path,
                   default=Path(f"bench/results/{dt.date.today().isoformat()}-run"))
    p.add_argument("--report-md", type=Path,
                   default=Path(f"docs/perf-{dt.date.today().isoformat()}-pymos-bench.md"))
    args = p.parse_args()

    if args.tier == "all":
        ontos = [e.name for e in CORPUS]
    else:
        wanted = set(args.tier.split(","))
        ontos = [e.name for e in CORPUS if e.tier in wanted]

    results_json = run_snapshot(
        out_dir=args.out,
        ontologies=ontos,
        backends=args.backends.split(","),
        reasoners=args.reasoners.split(","),
        relations=tuple(args.relations.split(",")),
        targets_per_ontology=args.targets_per_ontology,
        hot_iters=args.hot_iters,
        warmup=args.warmup,
    )

    from bench.runners.plots import write_scaling_plots
    from bench.runners.report import write_report
    from bench.reasoners.floors import measure_wrapper_floors

    write_scaling_plots(results_json, args.out / "plots")
    floors = measure_wrapper_floors(include_docker=False)
    write_report(results_json, args.report_md, floors=floors)
    print(f"results: {results_json}")
    print(f"report : {args.report_md}")


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 2: Smoke test CLI**

Run: `python -m bench.runners.snapshot --tier tiny --backends pyoxigraph_mem --reasoners none --hot-iters 1 --warmup 0`
Expected: writes `bench/results/<date>-run/results.json` + plots + `docs/perf-<date>-pymos-bench.md`.

> If the tiny tier requires actual downloads (pizza/wine/family from upstream),
> this smoke run may need network; on a fresh checkout copy
> `tests/data/pizza.omn` to `bench/data/pizza.omn` first to keep the smoke
> offline.

- [ ] **Step 3: Commit**

```bash
git add bench/runners/snapshot.py
git commit -m "bench: CLI entry for snapshot runner (python -m bench.runners.snapshot)"
```

---

## Milestone 8 — First snapshot report

### Task 22: Run first snapshot at small+medium tier, commit the report

**Files:**
- Create: `docs/perf-2026-05-28-pymos-bench.md` (or current date)
- Create: `bench/results/2026-05-28-run/` (gitignored — not committed)

- [ ] **Step 1: Download the small + medium corpus**

Run: `python -c "from bench.download import download_all; download_all('tiny'); download_all('small'); download_all('medium')"`
Expected: each ontology downloaded + ROBOT-converted to `.omn` under `bench/data/`. (Total ≈ 200 MB.)

- [ ] **Step 2: Measure wrapper floors (including docker)**

Run: `python -c "from bench.reasoners.floors import measure_wrapper_floors; import json; print(json.dumps(measure_wrapper_floors(include_docker=True), indent=2))"`
Expected: prints per-wrapper floors; record the docker floors in step 4.

- [ ] **Step 3: Run the snapshot**

Run:
```bash
python -m bench.runners.snapshot \
    --tier tiny,small,medium \
    --backends pyoxigraph_mem,pyoxigraph_rocksdb,owlready2_mem,owlready2_sqlite,rdflib_mem \
    --reasoners none,owlrl \
    --hot-iters 3 --warmup 1 \
    --out bench/results/$(date +%F)-run \
    --report-md docs/perf-$(date +%F)-pymos-bench.md
```

Expected: completes in ~30-60 min; emits `results.json`, `results.csv`,
`plots/parse_scaling.png`, and the narrative `.md`.

- [ ] **Step 4: Hand-edit the Headline section**

Open `docs/perf-$(date +%F)-pymos-bench.md`; replace the
`_TODO: hand-write a one-paragraph summary..._` placeholder with a one- or
two-paragraph headline summarising the most surprising scaling result (e.g.
"parse is linear to ~100k axioms then super-linear due to owlready2 SQLite
write amplification; rdflib OOMs past 50k; pyoxigraph CONSTRUCT is the
clear winner above 20k axioms").

Also paste in the docker wrapper floors from step 2 into the floors table
(the `--report-md` default only includes in-process floors).

- [ ] **Step 5: Verify the report renders**

Run: `python -c "import markdown; print(markdown.markdown(open('docs/perf-$(date +%F)-pymos-bench.md').read())[:200])"`
(If markdown isn't installed, just `cat` the file and eyeball it.)

- [ ] **Step 6: Run the full project test suite as a regression guard**

Run: `pytest -q`
Expected: still 171 / 171 passing (bench harness doesn't touch the runtime
package, but a sanity check is cheap).

- [ ] **Step 7: Commit the report only (not the results dir, which is gitignored)**

```bash
git add docs/perf-*-pymos-bench.md
git commit -m "docs(perf): first pymos perf snapshot — tiny + small + medium tiers

Backends: pyoxigraph (mem + rocksdb), owlready2 (mem + sqlite), rdflib (mem).
Reasoners: none, owlrl.

See docs/superpowers/specs/2026-05-28-pymos-perf-bench-design.md and
docs/superpowers/plans/2026-05-28-pymos-perf-bench.md for the methodology."
```

- [ ] **Step 8: Push**

```bash
git push -u origin bench/snapshot-v1
gh pr create --title "bench: pymos performance harness + first snapshot report" \
  --base master --head bench/snapshot-v1 \
  --body "Implements docs/superpowers/specs/2026-05-28-pymos-perf-bench-design.md.
First snapshot covers the tiny + small + medium tiers with the in-process
reasoners (none, owlrl). JVM/docker reasoners (HermiT/Pellet/ELK/Konclude)
are implemented but their cells were not included in this first run — they
will be added in a follow-up snapshot once docker images are pulled."
```

---

## Self-review

### Spec coverage

- §3 Architecture / package layout → File structure section (top) + Tasks 0–21 each create one of the declared files.
- §4 Corpus → Tasks 2 and 3.
- §5 Backends → Tasks 4 (owlready2_mem), 5 (pyoxigraph_mem), 6 (rdflib_mem), 7 (owlready2_sqlite), 8 (pyoxigraph_rocksdb), 9 (endpoint_oxigraph).
- §6 Reasoners → Tasks 13 (none + owlrl), 14 (robot_docker), 15 (HermiT/Pellet/ELK), 16 (Konclude), 17 (wrapper floors).
- §7 Workloads → Tasks 10 (parse), 11 (render), 12 (targets + query).
- §8 Measurement → Task 1.
- §9 Snapshot output → Tasks 18 (results.json + .csv), 19 (plots), 20 (report.md), 21 (CLI).
- §10 Reproducibility → Task 3 (SHA256 cache), Task 21 (CLI emits env header inside results.json).
- §11 Out of scope: no CI integration, no regression alerting, no multi-host — none of these have tasks, as intended.
- §12 Open follow-ups: by design, not in v1.

### Placeholder scan

- No `TBD`, `TODO`, "fill in details" in implementation steps.
- One intentional `_TODO: hand-write a one-paragraph summary..._` in the report template at Task 20 step 3 — this is **emitted in the generated report**, not the plan; it's the prompt for the human running the snapshot to write the headline. Task 22 step 4 explicitly handles it.
- No "similar to Task N" references; each task has full code.

### Type / signature consistency

- `Measurement` dataclass is defined once in Task 1 and consumed identically in Tasks 10, 11, 12, 18.
- `Backend` protocol declares `name`, `is_persistent`, `load`, `construct`, `select`, `close`; every backend (Tasks 4–9) implements exactly that surface.
- `Reasoner` protocol declares `name`, `profile`, `wrapper`, `materialise(source: Path) -> Path`; every reasoner (Tasks 13, 15, 16) implements exactly that surface.
- `bench_query`'s kwargs are referenced consistently in Tasks 12, 18, 21.
- `run_snapshot` parameter names match between Tasks 18 (definition) and 21 (CLI).
