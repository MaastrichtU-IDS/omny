from pathlib import Path

from bench.workloads.parse import bench_parse


def test_bench_parse_returns_extras_with_axiom_count(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_parse(str(p), hot_iters=2, warmup=1)
    assert m.wall_cold > 0
    assert m.extras["axiom_count"] > 0
    assert m.extras["bytes"] == len(pizza_text.encode())


from bench.workloads.render import bench_render


def test_bench_render_idempotent(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_render(str(p), hot_iters=2, warmup=1)
    assert m.wall_cold > 0
    assert m.extras["idempotent_second_pass"] is True
    assert m.extras["bytes_emitted"] > 0


from bench.workloads.targets import pick_targets
from bench.workloads.query import bench_query
from bench.backends.pyoxigraph_mem import PyoxigraphMemBackend


def test_pick_targets_returns_three(pizza_text):
    import pymos
    onto = pymos.parse(pizza_text)
    targets = pick_targets(onto, k=3)
    assert len(targets) == 3
    assert all(t.startswith("http") for t in targets)


def test_bench_query_super_construct(pizza_text):
    import pymos
    onto = pymos.parse(pizza_text)
    targets = pick_targets(onto, k=1)
    backend = PyoxigraphMemBackend()
    backend.load(onto)
    m = bench_query(
        backend_name="pyoxigraph_mem",
        target_iri=targets[0],
        relation="super",
        construct=True,
        hot_iters=2,
        warmup=1,
    )
    assert m.wall_cold >= 0
    assert m.extras["relation"] == "super"
    backend.close()


def test_bench_parse_then_reason_returns_extras(pizza_text, tmp_path):
    from bench.workloads.parse_reason import bench_parse_then_reason
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    m = bench_parse_then_reason(str(p), hot_iters=1, warmup=0)
    # The combined wall is reported in `wall_cold`. owlrl on tiny pizza is
    # measurable but small; just check we got non-zero numbers back.
    assert m.wall_cold > 0
