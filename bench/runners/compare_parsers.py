"""Head-to-head pymos parser-backend comparison: lark vs parsimonious.

Companion to ``bench/runners/snapshot.py`` for a single dimension —
which parser backend is faster on which ontology — so future
regressions in either backend are visible from a single command.

Usage::

    .venv/bin/python -m bench.runners.compare_parsers --tier tiny,small
    .venv/bin/python -m bench.runners.compare_parsers --tier all --hp-timeout 900

Output:
* ``bench/results/<date>-parsers/results.json`` — full Measurement per cell.
* ``bench/results/<date>-parsers/results.md`` — table-form summary
  suitable for pasting into a docs/perf-*.md.

Notes:
* HP parsimonious runs ~5 min on the original-host bench; the
  per-cell ``--hp-timeout`` cap (default 600 s) leaves headroom.
* lark is the default pymos backend post-PR #45; the snapshot runner's
  ``parse`` cell already measures it. This script's contribution is
  the *parsimonious counterpart* on the same workload, so the two
  numbers come from identical subprocess shapes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from bench.corpus import CORPUS, CorpusEntry
from bench.download import cached_omn_path, download_one
from bench.workloads.parse import bench_parse_backend


def _resolve(entry: CorpusEntry) -> Path:
    p = cached_omn_path(entry)
    return p if p.exists() else download_one(entry)


def run_comparison(
    *, ontologies: list[str], out_dir: Path,
    hot_iters: int = 2, warmup: int = 0,
    per_cell_timeout: float = 600.0,
) -> Path:
    """Run lark + parsimonious cells across ``ontologies``, write
    results.{json,md} into ``out_dir``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    by_entry = {e.name: e for e in CORPUS}
    cells = []

    for name in ontologies:
        if name not in by_entry:
            cells.append({"ontology": name, "error": "unknown corpus entry"})
            continue
        try:
            omn = _resolve(by_entry[name])
        except Exception as exc:
            cells.append({"ontology": name, "error": f"resolve: {exc}"})
            continue
        for backend in ("lark", "parsimonious"):
            try:
                m = bench_parse_backend(str(omn), backend,
                                        hot_iters=hot_iters, warmup=warmup,
                                        timeout=per_cell_timeout)
                cells.append({
                    "ontology": name,
                    "backend": backend,
                    "bytes": m.extras["bytes"],
                    "wall_cold": m.wall_cold,
                    "wall_hot_median": m.wall_hot_median,
                    "wall_hot_samples": m.wall_hot_samples,
                    "peak_rss_bytes": m.peak_rss_bytes,
                })
            except Exception as exc:
                cells.append({
                    "ontology": name, "backend": backend,
                    "error": f"{type(exc).__name__}: {exc}",
                })
            # Persist after every cell — HP parsimonious is slow; a crash
            # mid-run shouldn't lose the lark results we already paid for.
            _write(out_dir, cells)
    return out_dir / "results.json"


def _write(out_dir: Path, cells: list) -> None:
    """Atomic-rename JSON + markdown table; both rewritten each cell."""
    json_path = out_dir / "results.json"
    md_path = out_dir / "results.md"

    json_tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    json_tmp.write_text(json.dumps({"cells": cells}, indent=2))
    os.replace(json_tmp, json_path)

    md_tmp = md_path.with_suffix(md_path.suffix + ".tmp")
    md_tmp.write_text(_render_table(cells))
    os.replace(md_tmp, md_path)


def _render_table(cells: list) -> str:
    """Pair lark + parsimonious rows per ontology, emit a speedup column."""
    paired: dict[str, dict[str, dict]] = {}
    for c in cells:
        if "backend" not in c:
            continue
        paired.setdefault(c["ontology"], {})[c["backend"]] = c

    lines = [
        "# Parser-backend comparison",
        "",
        "| ontology | bytes | parsimonious (hot median) | lark (hot median) | speed-up |",
        "|---|---:|---:|---:|---:|",
    ]
    for ont, by_backend in paired.items():
        pars = by_backend.get("parsimonious")
        lark = by_backend.get("lark")
        b = (pars or lark or {}).get("bytes")
        p_hot = (pars or {}).get("wall_hot_median")
        l_hot = (lark or {}).get("wall_hot_median")
        ratio = f"{p_hot / l_hot:.2f}×" if p_hot and l_hot else "—"
        b_str = f"{b:,}" if b is not None else "—"
        p_str = f"{p_hot:.2f} s" if p_hot is not None else _short_error(pars)
        l_str = f"{l_hot:.2f} s" if l_hot is not None else _short_error(lark)
        lines.append(f"| {ont} | {b_str} | {p_str} | {l_str} | {ratio} |")
    return "\n".join(lines) + "\n"


def _short_error(cell: dict | None) -> str:
    """Compact error blurb for the table — TimeoutExpired traces are huge
    and useless inline."""
    if cell is None:
        return "—"
    err = cell.get("error") or ""
    if "TimeoutExpired" in err:
        return "_timeout_"
    if not err:
        return "—"
    # First two words of the exception name + message, capped.
    return err.split(":", 1)[0]


def _cli() -> None:
    p = argparse.ArgumentParser(description="parser-backend head-to-head")
    p.add_argument("--tier", default="tiny",
                   help="comma-separated tiers (tiny,small,medium,large,huge) or 'all'")
    p.add_argument("--ontologies", default="",
                   help="comma-separated explicit names; overrides --tier")
    p.add_argument("--hot-iters", type=int, default=2)
    p.add_argument("--warmup", type=int, default=0)
    p.add_argument("--per-cell-timeout", type=float, default=600.0,
                   help="seconds; default 600 (HP parsimonious is ~310 s)")
    p.add_argument("--out", type=Path,
                   default=Path(f"bench/results/{dt.date.today().isoformat()}-parsers"))
    args = p.parse_args()

    if args.ontologies:
        ontos = args.ontologies.split(",")
    elif args.tier == "all":
        ontos = [e.name for e in CORPUS]
    else:
        wanted = set(args.tier.split(","))
        ontos = [e.name for e in CORPUS if e.tier in wanted]

    out = run_comparison(
        ontologies=ontos,
        out_dir=args.out,
        hot_iters=args.hot_iters,
        warmup=args.warmup,
        per_cell_timeout=args.per_cell_timeout,
    )
    print(f"results: {out}")
    print(f"table  : {out.with_name('results.md')}")


if __name__ == "__main__":
    _cli()
