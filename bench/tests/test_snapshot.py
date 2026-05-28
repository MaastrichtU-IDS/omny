import json
from pathlib import Path

from bench.runners.snapshot import run_snapshot


def test_snapshot_pizza_no_reasoner_pyoxigraph_only(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    pizza_src = Path(__file__).resolve().parents[2] / "tests" / "data" / "pizza.omn"
    (tmp_path / "pizza.omn").write_text(pizza_src.read_text())

    out_dir = tmp_path / "run"
    run_snapshot(
        out_dir=out_dir,
        ontologies=["pizza"],
        backends=["pyoxigraph_mem"],
        reasoners=["none"],
        relations=("super",),
        construct_modes=(True,),
        targets_per_ontology=1,
        hot_iters=1,
        warmup=0,
    )
    results = json.loads((out_dir / "results.json").read_text())
    assert results["cells"]
    cell0 = results["cells"][0]
    assert cell0["ontology"] == "pizza"
    # Find a query cell
    query_cells = [c for c in results["cells"] if c["workload"] == "query"]
    assert query_cells, "expected at least one query cell"
    qc = query_cells[0]
    assert qc["backend"] == "pyoxigraph_mem"
    assert qc["reasoner"] == "none"
    assert "wall_cold" in qc["measurement"]
