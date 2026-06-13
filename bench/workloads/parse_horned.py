"""Parse workload for the Rust horned-bench binary (any --format)."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from bench.measure import Measurement

BIN = Path(__file__).resolve().parents[1] / "horned-bench" / "target" / "release" / "horned-bench"


def bench_parse_horned(
    path: str,
    fmt: str = "omn",
    *,
    hot: int = 5,
    warmup: int = 1,
    timeout: float = 600.0,
) -> Measurement:
    """Parse an ontology file using the Rust horned-bench binary.

    Args:
        path:    Path to the ontology file.
        fmt:     horned-bench --format value (omn, ofn, owx, rdf, fastobo-omn).
        hot:     Number of hot (measured) iterations after warmup.
        warmup:  Number of warmup iterations (discarded).
        timeout: Subprocess timeout in seconds.

    Returns:
        A Measurement populated from the JSON line printed by horned-bench.
        peak_python_bytes is 0 (Rust process; no Python heap measured).
        cpu_hot_median mirrors wall_hot_median (Rust subprocess; no per-iter CPU split).
    """
    cmd = [
        str(BIN),
        "--format", fmt,
        "--mode", "parse",
        "--hot", str(hot),
        "--warmup", str(warmup),
        path,
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    d = json.loads(out.stdout.strip().splitlines()[-1])
    return Measurement(
        wall_cold=d["wall_cold_s"],
        wall_hot_samples=[d["wall_hot_min_s"], d["wall_hot_median_s"]],
        wall_hot_median=d["wall_hot_median_s"],
        wall_hot_stddev=0.0,
        peak_rss_bytes=d["peak_rss_bytes"],
        peak_python_bytes=0,          # Rust subprocess; no Python heap measurement
        cpu_cold=d["wall_cold_s"],    # subprocess; no fine-grained CPU split
        cpu_hot_median=d["wall_hot_median_s"],
        extras={
            "backend": f"horned-{fmt}",
            "component_count": d["component_count"],
            "bytes": d["bytes"],
        },
    )
