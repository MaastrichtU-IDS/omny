"""Scaling-curve plots: axioms vs wall-time, per workload."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_scaling_plots(results_json: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(Path(results_json).read_text())

    parse_cells = [c for c in payload["cells"] if c["workload"] == "parse" and c.get("measurement")]
    if parse_cells:
        xs = [c["measurement"]["extras"]["axiom_count"] for c in parse_cells]
        ys = [c["measurement"]["wall_hot_median"] for c in parse_cells]
        labels = [c["ontology"] for c in parse_cells]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(xs, ys)
        for x, y, label in zip(xs, ys, labels):
            ax.annotate(label, (x, y), fontsize=8)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("axioms")
        ax.set_ylabel("parse wall (s, median of hot iters)")
        ax.set_title("omny parse scaling")
        fig.tight_layout()
        fig.savefig(out_dir / "parse_scaling.png", dpi=120)
        plt.close(fig)
