"""OWLAPI parse workload: load an ontology via ROBOT (which uses OWLAPI
internally) and report the wall time.

ROBOT is a thin wrapper around the OWL API — its ``robot convert``
command loads the input ontology with OWLAPI's
``OWLManager.createOWLOntologyManager().loadOntologyFromOntologyDocument(...)``
and writes the result. We use it as a stand-in for "OWLAPI parse time"
without needing to add JPype1 + an OWLAPI jar to the bench's Python
side.

The number includes ROBOT's JVM startup (≥ 1 s) and an output-write
step we can't skip. So:

  * Treat the absolute wall as a *ceiling* for OWLAPI's parse cost, not
    a tight measurement.
  * The startup cost is reported separately by
    ``bench.reasoners.floors.measure_wrapper_floors(include_docker=True)``
    under ``"robot-docker"`` — subtract it from this number to estimate
    OWLAPI's pure-parse time, or just report both alongside the pymos
    numbers so the comparison is honest about what's included.

We measure ``robot convert --input X --output X.tmp.owx`` because:

  * ``convert`` is the cheapest ROBOT command that exercises a full load.
  * Writing to ``.owx`` keeps OWLAPI's structural-axiom representation
    (no RDF round-tripping in the output writer).
"""
import shutil
import subprocess
import time
from pathlib import Path

from bench.measure import Measurement


def _do_owlapi_parse(input_path: str, image: str = "obolibrary/robot:v1.9.6") -> float:
    """Run one ROBOT convert. Returns wall seconds (just this call)."""
    src = Path(input_path).resolve()
    mount = src.parent
    out_name = src.stem + ".owlapi-bench.owx"
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{mount}:/work", "-w", "/work",
        image, "robot", "convert",
        "--input", src.name,
        "--output", out_name,
    ]
    t0 = time.perf_counter()
    subprocess.run(cmd, check=True, capture_output=True)
    elapsed = time.perf_counter() - t0
    # Best-effort cleanup of the output file.
    try:
        (mount / out_name).unlink(missing_ok=True)
    except OSError:
        pass
    return elapsed


def bench_parse_owlapi(
    input_path: str, *, hot_iters: int = 1, warmup: int = 0,
) -> Measurement:
    """Median wall over ``hot_iters`` ROBOT-convert runs (each spawns docker).

    Defaults to ``hot_iters=1, warmup=0`` — docker startup is the dominant
    cost and is already amortised by the OS file cache after the first
    pull. Asking for more iterations is honest but expensive.

    Returns a ``Measurement`` whose ``wall_cold`` is the first run and
    ``wall_hot_median`` is the median of ``hot_iters`` further runs (or
    ``wall_cold`` again if ``hot_iters <= 1``).
    """
    if shutil.which("docker") is None:
        raise RuntimeError(
            "OWLAPI workload needs docker on PATH (used to spawn the "
            "obolibrary/robot container)."
        )

    cold = _do_owlapi_parse(input_path)

    if hot_iters <= 1:
        hot_samples: list[float] = []
        hot_median = cold
        hot_stddev = 0.0
    else:
        hot_samples = [_do_owlapi_parse(input_path) for _ in range(hot_iters)]
        sorted_samples = sorted(hot_samples)
        hot_median = sorted_samples[len(sorted_samples) // 2]
        # population stddev — same convention as the rest of the bench
        mean = sum(hot_samples) / len(hot_samples)
        hot_stddev = (sum((s - mean) ** 2 for s in hot_samples) / len(hot_samples)) ** 0.5

    return Measurement(
        wall_cold=cold,
        wall_hot_samples=hot_samples,
        wall_hot_median=hot_median,
        wall_hot_stddev=hot_stddev,
        peak_rss_bytes=0,        # docker hides the JVM's RSS from the parent
        peak_python_bytes=0,     # n/a — JVM, not Python
        cpu_cold=cold,           # docker subprocess; no fine-grained CPU split
        cpu_hot_median=hot_median,
        extras={"backend": "owlapi-via-robot", "image": "obolibrary/robot:v1.9.6"},
    )
