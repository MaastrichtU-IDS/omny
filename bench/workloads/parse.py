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
