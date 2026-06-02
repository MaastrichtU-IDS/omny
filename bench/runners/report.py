"""Narrative markdown report — mirrors rustdl perf-*.md style."""
import json
from pathlib import Path
from typing import Dict


def _fmt(x, n: int = 3) -> str:
    return "n/a" if x is None else f"{float(x):.{n}f}"


def write_report(results_json: Path, out_md: Path, *, floors: Dict[str, float] | None = None) -> None:
    payload = json.loads(Path(results_json).read_text())
    env = payload["env"]
    cells = payload["cells"]
    floors = floors or {}

    lines: list[str] = []
    date = env["timestamp"].split()[0]
    lines.append(f"# Perf snapshot — {date}, omny")
    lines.append("")
    lines.append(f"Host: {env['host']}, {env['platform']}, python {env['python']}.")
    lines.append(f"omny: {env['omny_sha']}.  CPU count: {env['cpu_count']}.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("_TODO: hand-write a one-paragraph summary after reading the tables._")
    lines.append("")

    parse_cells = [c for c in cells if c["workload"] == "parse" and c.get("measurement")]
    if parse_cells:
        lines.append("## 1. Parse")
        lines.append("")
        lines.append("| ontology | axioms | bytes | cold (s) | hot median (s) | peak RSS (MB) |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for c in parse_cells:
            m = c["measurement"]; e = m["extras"]
            lines.append(
                f"| {c['ontology']} | {e['axiom_count']} | {e['bytes']} | "
                f"{_fmt(m['wall_cold'])} | {_fmt(m['wall_hot_median'])} | "
                f"{m['peak_rss_bytes']//1_000_000} |"
            )
        lines.append("")

    render_cells = [c for c in cells if c["workload"] == "render" and c.get("measurement")]
    if render_cells:
        lines.append("## 2. Render")
        lines.append("")
        lines.append("| ontology | bytes emitted | cold (s) | hot median (s) | idempotent? |")
        lines.append("|---|---:|---:|---:|:---:|")
        for c in render_cells:
            m = c["measurement"]; e = m["extras"]
            lines.append(
                f"| {c['ontology']} | {e['bytes_emitted']} | "
                f"{_fmt(m['wall_cold'])} | {_fmt(m['wall_hot_median'])} | "
                f"{'yes' if e['idempotent_second_pass'] else 'no'} |"
            )
        lines.append("")

    q_cells = [c for c in cells if c["workload"] == "query" and c.get("measurement")]
    if q_cells:
        lines.append("## 3. Query — summary (median hot across relations × targets)")
        lines.append("")
        lines.append("| ontology | backend | reasoner | median hot (s) | cells |")
        lines.append("|---|---|---|---:|---:|")
        groups: dict[tuple, list[float]] = {}
        for c in q_cells:
            key = (c["ontology"], c["backend"], c["reasoner"])
            groups.setdefault(key, []).append(c["measurement"]["wall_hot_median"])
        for (o, b, r), walls in sorted(groups.items()):
            import statistics
            lines.append(f"| {o} | {b} | {r} | {_fmt(statistics.median(walls))} | {len(walls)} |")
        lines.append("")

    if floors:
        lines.append("## 4. Wrapper startup floors")
        lines.append("")
        lines.append("| wrapper | floor (s) |")
        lines.append("|---|---:|")
        for k, v in sorted(floors.items()):
            lines.append(f"| {k} | {_fmt(v, 2)} |")
        lines.append("")

    n_skip = sum(1 for c in cells if c.get("skipped_reason"))
    n_err = sum(1 for c in cells if c.get("error"))
    lines.append("## 5. Coverage")
    lines.append("")
    lines.append(f"- Total cells: {len(cells)}")
    lines.append(f"- Skipped (structurally n/a): {n_skip}")
    lines.append(f"- Errored: {n_err}")
    lines.append("")

    out_md.write_text("\n".join(lines))
