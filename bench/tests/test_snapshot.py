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


def test_snapshot_records_render_failure_and_continues(tmp_path, monkeypatch):
    """A failing ``bench_render`` must record an ``error`` row, not abort the run.

    Before this guard, a per-cell render crash (e.g. an ``IncompleteParseError``
    from a real-world ontology) propagated up through ``run_snapshot`` and
    aborted before any results were written. The query workload — which is
    independent of render — was never reached. See snapshot 2026-05-31.
    """
    import bench.runners.snapshot as snap

    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    pizza_src = Path(__file__).resolve().parents[2] / "tests" / "data" / "pizza.omn"
    (tmp_path / "pizza.omn").write_text(pizza_src.read_text())

    def _boom(*a, **k):
        raise RuntimeError("simulated render failure")
    monkeypatch.setattr(snap, "bench_render", _boom)

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
    by_workload = {c["workload"]: c for c in results["cells"]}

    # Render row exists and carries the error
    assert "render" in by_workload
    assert "simulated render failure" in by_workload["render"]["error"]

    # And the run continued — parse + query both have measurements
    assert by_workload["parse"]["measurement"] is not None
    assert any(c["workload"] == "query" and c.get("measurement") for c in results["cells"]), \
        "query workload must still run when render fails"


from bench.runners.plots import write_scaling_plots


def test_write_scaling_plots_produces_png(tmp_path):
    results_json = tmp_path / "results.json"
    results_json.write_text(json.dumps({
        "env": {},
        "cells": [
            {"ontology": "pizza", "workload": "parse", "backend": None,
             "reasoner": "none", "relation": None, "construct": None, "target": None,
             "measurement": {"wall_cold": 0.1, "wall_hot_median": 0.08,
                             "wall_hot_samples": [0.08, 0.08, 0.08],
                             "wall_hot_stddev": 0.0, "peak_rss_bytes": 50_000_000,
                             "peak_python_bytes": 1_000_000, "cpu_cold": 0.09,
                             "cpu_hot_median": 0.07,
                             "extras": {"axiom_count": 250, "bytes": 5000}},
             "error": None, "skipped_reason": None},
            {"ontology": "wine", "workload": "parse", "backend": None,
             "reasoner": "none", "relation": None, "construct": None, "target": None,
             "measurement": {"wall_cold": 0.25, "wall_hot_median": 0.2,
                             "wall_hot_samples": [0.2, 0.2, 0.2],
                             "wall_hot_stddev": 0.0, "peak_rss_bytes": 80_000_000,
                             "peak_python_bytes": 2_000_000, "cpu_cold": 0.22,
                             "cpu_hot_median": 0.18,
                             "extras": {"axiom_count": 700, "bytes": 14000}},
             "error": None, "skipped_reason": None},
        ],
    }))

    out_dir = tmp_path / "plots"
    write_scaling_plots(results_json, out_dir)
    parse_png = out_dir / "parse_scaling.png"
    assert parse_png.exists()
    assert parse_png.stat().st_size > 0


from bench.runners.report import write_report


def test_write_report_emits_markdown(tmp_path):
    results_json = tmp_path / "results.json"
    results_json.write_text(json.dumps({
        "env": {"host": "h", "platform": "p", "python": "3.12.1",
                "pymos_sha": "abc1234", "timestamp": "2026-05-28 21:00:00",
                "cpu_count": 8},
        "cells": [
            {"ontology": "pizza", "workload": "parse",
             "backend": None, "reasoner": "none", "relation": None,
             "construct": None, "target": None,
             "measurement": {"wall_cold": 0.1, "wall_hot_median": 0.08,
                             "wall_hot_samples": [0.08]*3, "wall_hot_stddev": 0.0,
                             "peak_rss_bytes": 50_000_000, "peak_python_bytes": 1_000_000,
                             "cpu_cold": 0.09, "cpu_hot_median": 0.07,
                             "extras": {"axiom_count": 250, "bytes": 5000}},
             "error": None, "skipped_reason": None},
        ],
    }))

    md = tmp_path / "report.md"
    write_report(results_json, md, floors={"owlrl": 0.05, "robot-docker": 2.4})
    text = md.read_text()
    assert "# Perf snapshot — 2026-05-28" in text
    assert "## Headline" in text
    assert "pizza" in text
    assert "robot-docker" in text and "2.4" in text
    assert "0.08" in text
