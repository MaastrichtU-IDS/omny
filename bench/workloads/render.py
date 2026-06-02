"""Render workload: omny.render() round-trip + idempotency check."""
from pathlib import Path

import omny

from bench.measure import Measurement, measure_in_subprocess


def _do_render(path: str) -> None:
    onto = omny.parse(Path(path).read_text())
    omny.render(onto)


def _check_idempotent(path: str) -> tuple[bool, int]:
    text = Path(path).read_text()
    rendered1 = omny.render(omny.parse(text))
    rendered2 = omny.render(omny.parse(rendered1))
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
