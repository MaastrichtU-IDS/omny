"""Parse workload: pymos.parse() on an .omn file.

Two functions surface here: the default ``_do_parse`` calls
:func:`pymos.parse` as a library user would — which, post-PR #45,
uses the lark backend internally. ``_do_parse_parsimonious`` monkey-
patches ``pymos.frames.ManchesterParser`` back to the legacy
parsimonious-based parser for head-to-head backend benchmarking.
"""
from pathlib import Path

import pymos

from bench.measure import Measurement, measure_in_subprocess


def _do_parse(path: str) -> None:
    """Parse a .omn file with the default backend (lark since PR #45)."""
    pymos.parse(Path(path).read_text())


def _do_parse_parsimonious(path: str) -> None:
    """Force the legacy parsimonious backend for one parse cycle.

    Used by :func:`bench_parse_backend` to measure the previous
    parser implementation on the same workload — anything in the
    snapshot CSV marked ``backend=parsimonious`` came through here.
    """
    import pymos.frames as fr
    from pymos.parser import ManchesterParser as _PP
    saved = fr.ManchesterParser
    fr.ManchesterParser = _PP
    try:
        pymos.parse(Path(path).read_text())
    finally:
        fr.ManchesterParser = saved


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


def bench_parse_backend(path: str, backend: str, *,
                        hot_iters: int = 3, warmup: int = 1,
                        timeout: float = 600.0) -> Measurement:
    """Run :func:`pymos.parse` with an explicit parser backend.

    Args:
        path: .omn file to parse.
        backend: ``"lark"`` (default) or ``"parsimonious"``.
        hot_iters / warmup: passed through to ``measure_in_subprocess``.
        timeout: per-cell subprocess timeout (HP parsimonious is ~5 min
            on this host).

    Returns:
        :class:`Measurement` with ``extras["backend"]`` set so the CSV
        emitted by the snapshot runner is self-describing.
    """
    func = {"lark": "_do_parse", "parsimonious": "_do_parse_parsimonious"}[backend]
    m = measure_in_subprocess(
        "bench.workloads.parse", func,
        args=(path,), hot_iters=hot_iters, warmup=warmup, timeout=timeout,
    )
    m.extras["backend"] = backend
    m.extras["bytes"] = Path(path).stat().st_size
    return m
