from pathlib import Path

from bench.workloads.parse import bench_parse


def test_bench_parse_returns_extras_with_axiom_count(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_parse(str(p), hot_iters=2, warmup=1)
    assert m.wall_cold > 0
    assert m.extras["axiom_count"] > 0
    assert m.extras["bytes"] == len(pizza_text.encode())
