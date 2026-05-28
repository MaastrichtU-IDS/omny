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
