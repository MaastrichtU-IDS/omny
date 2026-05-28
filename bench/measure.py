"""Wall + CPU + memory measurement primitives, in-process and subprocess.

Every bench cell uses `measure_in_subprocess` so peak RSS is clean (the parent
process's heap doesn't leak in). `measure_in_process` exists only for the unit
tests of this module.
"""
from __future__ import annotations

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
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
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
    if not already_tracing:
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
        env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [os.getcwd(), os.environ.get("PYTHONPATH", "")]))},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"subprocess failed: {proc.stderr}")
    return Measurement.from_dict(json.loads(proc.stdout))
