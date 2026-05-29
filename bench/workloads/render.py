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
