"""Parse-then-reason workload: pymos.parse() followed by a reasoner's
``materialise()`` step. Reports a single combined wall time per cell, so
the snapshot table can answer "what is the cost of parse + inference?"
alongside "what is the cost of parse alone?".

Currently only ``owlrl`` is wired here — it's pure Python, no Java, no
Docker, so it runs anywhere the rest of the bench runs. ``HermiT`` /
``JFact`` / ``ELK`` materialisation is available via the
``bench/reasoners/`` wrappers but requires Docker; adding those to the
parse+reason workload is a small extension once the docker reasoners
are wanted in this slot.
"""
from pathlib import Path

import pymos

from bench.measure import Measurement, measure_in_subprocess
from bench.reasoners.owlrl import OwlrlReasoner


def _do_parse_then_reason(path: str) -> None:
    """Side-effect target: parse the ontology and run the OWL 2 RL closure."""
    onto = pymos.parse(Path(path).read_text())
    OwlrlReasoner().materialise(Path(path))
    # `materialise` re-parses internally (it accepts a path, not an ontology),
    # so this is "parse + reason from scratch" — the realistic cost of taking
    # a `.omn` file from disk to a reasoned RDF graph. Holding `onto` keeps
    # the parsed value live so the parse half stays in peak RSS.
    del onto


def bench_parse_then_reason(
    path: str, *, hot_iters: int = 1, warmup: int = 0,
) -> Measurement:
    """Measure ``pymos.parse(path) + owlrl.materialise(path)`` in a subprocess.

    Defaults to ``hot_iters=1, warmup=0`` because the owlrl closure on
    real ontologies is dominated by a single expensive iteration; warmup
    rarely changes the picture and doubles the wall budget per cell.
    Callers passing a larger ``hot_iters`` get the median over that many
    fresh-subprocess runs.
    """
    return measure_in_subprocess(
        "bench.workloads.parse_reason", "_do_parse_then_reason",
        args=(path,), hot_iters=hot_iters, warmup=warmup,
    )
