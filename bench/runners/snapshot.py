"""Snapshot orchestrator: iterate (ontology × backend × reasoner × workload)
cells, run each in a fresh subprocess, write results.json + .csv."""
from __future__ import annotations

import csv
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import pymos

from bench.corpus import CORPUS, CorpusEntry
from bench.download import cached_omn_path, download_one
from bench.measure import Measurement
from bench.workloads.parse import bench_parse
from bench.workloads.render import bench_render
from bench.workloads.query import bench_query
from bench.workloads.targets import pick_targets


@dataclass
class Cell:
    ontology: str
    workload: str
    backend: str | None
    reasoner: str
    relation: str | None
    construct: bool | None
    target: str | None
    measurement: dict | None = None
    error: str | None = None
    skipped_reason: str | None = None


def _env_header() -> dict:
    import platform
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "pymos_sha": _git_sha(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_count": os.cpu_count(),
    }


def _git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
        ).stdout.strip()[:12]
    except Exception:
        return "unknown"


def _entry(name: str) -> CorpusEntry:
    for e in CORPUS:
        if e.name == name:
            return e
    raise KeyError(f"unknown ontology: {name}")


def _resolve_omn(name: str) -> Path:
    """Path to the ontology .omn — download if needed unless BENCH_DATA_DIR
    already has it (covers the test fast-path)."""
    e = _entry(name)
    p = cached_omn_path(e)
    if p.exists():
        return p
    return download_one(e)


def run_snapshot(
    *,
    out_dir: Path,
    ontologies: list[str],
    backends: list[str],
    reasoners: list[str],
    relations: Iterable[str] = ("super", "sub", "direct_super", "direct_sub", "equiv", "individual"),
    construct_modes: Iterable[bool] = (True, False),
    targets_per_ontology: int = 3,
    hot_iters: int = 3,
    warmup: int = 1,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cells: list[Cell] = []

    # Compute the env header once so every flush reuses it (a git-sha lookup
    # spawns a subprocess; doing it per cell would dominate the snapshot cost).
    env_header = _env_header()

    def _add(cell: Cell) -> None:
        """Append a cell and flush results.{json,csv} so that a timeout or
        crash mid-run preserves everything completed so far. The write is
        atomic per file (temp + rename on the same filesystem)."""
        cells.append(cell)
        _flush_results(out_dir, env_header, cells)

    def _err_cell(workload: str, exc: BaseException, *,
                  backend=None, reasoner="none", relation=None,
                  construct=None, target=None) -> Cell:
        return Cell(
            ontology=onto_name, workload=workload,
            backend=backend, reasoner=reasoner, relation=relation,
            construct=construct, target=target,
            error=f"{type(exc).__name__}: {exc}",
        )

    for onto_name in ontologies:
        # Resolve the .omn (may need download + ROBOT convert).
        try:
            omn = _resolve_omn(onto_name)
        except Exception as exc:
            _add(_err_cell("resolve", exc))
            continue  # cannot run any workload without the .omn

        # Parse workload — non-blocking: a failure here is recorded and we
        # move on, since render/query each open the file themselves.
        try:
            parse_m = bench_parse(str(omn), hot_iters=hot_iters, warmup=warmup).to_dict()
            _add(Cell(
                ontology=onto_name, workload="parse",
                backend=None, reasoner="none", relation=None, construct=None, target=None,
                measurement=parse_m,
            ))
        except Exception as exc:
            _add(_err_cell("parse", exc))

        # Render workload — non-blocking too.
        try:
            render_m = bench_render(str(omn), hot_iters=hot_iters, warmup=warmup).to_dict()
            _add(Cell(
                ontology=onto_name, workload="render",
                backend=None, reasoner="none", relation=None, construct=None, target=None,
                measurement=render_m,
            ))
        except Exception as exc:
            _add(_err_cell("render", exc))

        # Target picking — needed for the query loop. If pymos.parse() or
        # pick_targets() raise (e.g. ontology has zero classes), record the
        # failure once and skip the query matrix for this ontology rather
        # than emit N empty rows.
        try:
            onto = pymos.parse(omn.read_text())
            targets = pick_targets(onto, k=targets_per_ontology)
        except Exception as exc:
            _add(_err_cell("target_pick", exc))
            continue

        for backend_name in backends:
            for reasoner_name in reasoners:
                for construct in construct_modes:
                    if construct and backend_name.startswith("owlready2"):
                        for relation in relations:
                            for target in targets:
                                _add(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    skipped_reason="owlready2 SPARQL engine does not support CONSTRUCT",
                                ))
                        continue
                    for relation in relations:
                        for target in targets:
                            try:
                                m = bench_query(
                                    onto_path=str(omn),
                                    backend_name=backend_name,
                                    target_iri=target,
                                    relation=relation,
                                    construct=construct,
                                    hot_iters=hot_iters,
                                    warmup=warmup,
                                )
                                _add(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    measurement=m.to_dict(),
                                ))
                            except Exception as exc:
                                _add(Cell(
                                    ontology=onto_name, workload="query",
                                    backend=backend_name, reasoner=reasoner_name,
                                    relation=relation, construct=construct, target=target,
                                    error=f"{type(exc).__name__}: {exc}",
                                ))

    # Final flush is implicit in _add — every appended cell already wrote to
    # disk. The redundant call here is a no-op safety net for runs with zero
    # cells (e.g. all ontologies failed at _resolve_omn) so the empty results
    # files still exist.
    if not cells:
        _flush_results(out_dir, env_header, cells)

    return out_dir / "results.json"


_CSV_HEADER = ["ontology", "workload", "backend", "reasoner",
               "relation", "construct", "target", "wall_cold",
               "wall_hot_median", "peak_rss_bytes", "error", "skipped_reason"]


def _flush_results(out_dir: Path, env: dict, cells: list) -> None:
    """Write results.{json,csv} atomically (temp + rename on same fs).

    Called after every appended cell so that a timeout, crash, or Ctrl-C
    mid-run preserves everything completed so far. Both files are
    written via a sibling ``.tmp`` and ``os.replace``-d into place; the
    replacement is atomic per file on POSIX/NTFS (no half-written file
    ever observable to a concurrent reader).
    """
    json_path = out_dir / "results.json"
    csv_path = out_dir / "results.csv"

    json_tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    payload = {"env": env, "cells": [asdict(c) for c in cells]}
    json_tmp.write_text(json.dumps(payload, indent=2))
    os.replace(json_tmp, json_path)

    csv_tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with csv_tmp.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(_CSV_HEADER)
        for c in cells:
            m = c.measurement or {}
            w.writerow([c.ontology, c.workload, c.backend, c.reasoner,
                        c.relation, c.construct, c.target,
                        m.get("wall_cold"), m.get("wall_hot_median"),
                        m.get("peak_rss_bytes"), c.error, c.skipped_reason])
    os.replace(csv_tmp, csv_path)


def _cli():
    import argparse, datetime as dt
    p = argparse.ArgumentParser(description="pymos perf snapshot runner")
    p.add_argument("--tier", default="tiny",
                   help="comma-separated tiers (tiny,small,medium,large,huge) or 'all'")
    p.add_argument("--backends", default="pyoxigraph_mem,owlready2_mem",
                   help="comma-separated backend names")
    p.add_argument("--reasoners", default="none,owlrl",
                   help="comma-separated reasoner names")
    p.add_argument("--relations", default="super,sub,direct_super,direct_sub,equiv,individual")
    p.add_argument("--targets-per-ontology", type=int, default=3)
    p.add_argument("--hot-iters", type=int, default=3)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--out", type=Path,
                   default=Path(f"bench/results/{dt.date.today().isoformat()}-run"))
    p.add_argument("--report-md", type=Path,
                   default=Path(f"docs/perf-{dt.date.today().isoformat()}-pymos-bench.md"))
    args = p.parse_args()

    if args.tier == "all":
        ontos = [e.name for e in CORPUS]
    else:
        wanted = set(args.tier.split(","))
        ontos = [e.name for e in CORPUS if e.tier in wanted]

    results_json = run_snapshot(
        out_dir=args.out,
        ontologies=ontos,
        backends=args.backends.split(","),
        reasoners=args.reasoners.split(","),
        relations=tuple(args.relations.split(",")),
        targets_per_ontology=args.targets_per_ontology,
        hot_iters=args.hot_iters,
        warmup=args.warmup,
    )

    from bench.runners.plots import write_scaling_plots
    from bench.runners.report import write_report
    from bench.reasoners.floors import measure_wrapper_floors

    write_scaling_plots(results_json, args.out / "plots")
    floors = measure_wrapper_floors(include_docker=False)
    write_report(results_json, args.report_md, floors=floors)
    print(f"results: {results_json}")
    print(f"report : {args.report_md}")


if __name__ == "__main__":
    _cli()
