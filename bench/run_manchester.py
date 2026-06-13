"""Run the Manchester read/write comparison across the corpus and emit raw.csv.

Read cells:  ours: horned-{omn,ofn,owx,rdf}; fastobo-omn; omny; owlapi(ROBOT)
Write cells: ours: horned-{omn,ofn,owx}; omny
Every cell is wrapped — a failing reader (e.g. our omn reader on sio/hp) records
status='fail' with the error, never aborts the run.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # ensure 'bench' importable

from bench.workloads.parse_horned import bench_parse_horned
from bench.workloads.render_horned import bench_render_horned
from bench.workloads.parse import bench_parse as omny_parse
from bench.workloads.render import bench_render as omny_render
from bench.workloads.parse_owlapi import bench_parse_owlapi

DATA = Path("bench/data")
OUT = Path("bench/results/2026-06-13-manchester")
OUT.mkdir(parents=True, exist_ok=True)

# Ontologies for the full cross-format comparison (small/medium).
# sio/hp are included ONLY for selected read cells to document our reader's
# conformance gaps — failures there are expected findings, not crashes.
FULL = ["koala", "pizza", "travel", "obi-core"]
OMN_ONLY = ["sio", "hp"]  # our omn reader fails; owlapi/fastobo should succeed


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def row(onto: str, mode: str, backend: str, m=None, status: str = "ok", err: str = "") -> dict:
    if m is not None:
        return dict(
            ontology=onto,
            mode=mode,
            backend=backend,
            wall_hot_median_s=m.wall_hot_median,
            peak_rss_bytes=m.peak_rss_bytes,
            bytes=m.extras.get("bytes", ""),
            component_count=m.extras.get("component_count", ""),
            status=status,
            error="",
        )
    return dict(
        ontology=onto,
        mode=mode,
        backend=backend,
        wall_hot_median_s="",
        peak_rss_bytes="",
        bytes="",
        component_count="",
        status=status,
        error=err[:300],
    )


def safe(onto: str, mode: str, backend: str, fn) -> dict:
    """Run fn() -> Measurement, return a row dict; never raise."""
    try:
        m = fn()
        r = row(onto, mode, backend, m)
        print(f"  [ok]   {onto} {mode} {backend}: {m.wall_hot_median:.4f}s")
        return r
    except Exception as e:
        short = f"{type(e).__name__}: {e}"
        print(f"  [fail] {onto} {mode} {backend}: {short[:120]}")
        return row(onto, mode, backend, status="fail", err=short)


# ---------------------------------------------------------------------------
# Format generation via ROBOT
# ---------------------------------------------------------------------------

def ensure_ofn_owx(stem: str) -> None:
    """Generate bench/data/<stem>.ofn and .owx via ROBOT docker if missing.

    For sources whose extension ROBOT can't infer (.rdfxml), stage a copy
    as 'in.owl' (ROBOT defaults to RDF/XML for .owl). Falls back to .omn
    if no .rdfxml exists (pizza case).
    """
    rdf = DATA / f"{stem}.rdfxml"
    omn = DATA / f"{stem}.omn"

    # Choose the best source: rdfxml first, then omn
    if rdf.exists():
        src = rdf
        in_name = "in.owl"   # ROBOT infers RDF/XML from .owl extension
    elif omn.exists():
        src = omn
        in_name = "in.omn"
    else:
        print(f"  [genfmt skip] {stem}: no .rdfxml or .omn source")
        return

    for fmt in ("ofn", "owx"):
        target = DATA / f"{stem}.{fmt}"
        if target.exists():
            print(f"  [genfmt exists] {target.name}")
            continue

        tmp = Path(f"/tmp/genfmt-{stem}-{fmt}")
        tmp.mkdir(exist_ok=True)
        staged = tmp / in_name
        shutil.copy(src, staged)
        out_file = tmp / f"out.{fmt}"
        try:
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{tmp}:/w", "-w", "/w",
                    "obolibrary/robot:v1.9.6",
                    "robot", "convert",
                    "-i", staged.name,
                    "--format", fmt,
                    "-o", out_file.name,
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )
            shutil.copy(out_file, target)
            print(f"  [genfmt ok]    generated {target.name}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace")[:200] if e.stderr else ""
            print(f"  [genfmt fail]  {stem}.{fmt}: CalledProcessError: {stderr}")
        except Exception as e:
            print(f"  [genfmt fail]  {stem}.{fmt}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Generating .ofn / .owx for FULL set ===")
    for stem in FULL:
        print(f"-- ensure_ofn_owx({stem})")
        ensure_ofn_owx(stem)

    rows: list[dict] = []

    for stem in FULL + OMN_ONLY:
        omn = DATA / f"{stem}.omn"
        rdf = DATA / f"{stem}.rdfxml"
        print(f"\n== {stem} ==")

        # ------------------------------------------------------------------
        # READ cells
        # ------------------------------------------------------------------
        if omn.exists():
            # Our horned omn reader (expected to FAIL on sio/hp)
            rows.append(safe(stem, "read", "horned-omn",
                             lambda p=omn: bench_parse_horned(str(p), "omn")))
            # fastobo Manchester reader
            rows.append(safe(stem, "read", "fastobo-omn",
                             lambda p=omn: bench_parse_horned(str(p), "fastobo-omn")))
            # OWLAPI via ROBOT (reference Manchester parser)
            rows.append(safe(stem, "read", "owlapi",
                             lambda p=omn: bench_parse_owlapi(str(p))))
            # omny (pure-Python) — only for FULL (manageable sizes)
            if stem in FULL:
                rows.append(safe(stem, "read", "omny",
                                 lambda p=omn: omny_parse(str(p))))

        for fmt in ("ofn", "owx"):
            f = DATA / f"{stem}.{fmt}"
            if f.exists():
                rows.append(safe(stem, "read", f"horned-{fmt}",
                                 lambda p=f, x=fmt: bench_parse_horned(str(p), x)))

        if rdf.exists():
            rows.append(safe(stem, "read", "horned-rdf",
                             lambda p=rdf: bench_parse_horned(str(p), "rdf")))

        # ------------------------------------------------------------------
        # WRITE cells
        # ------------------------------------------------------------------
        if omn.exists() and stem in FULL:
            rows.append(safe(stem, "write", "horned-omn",
                             lambda p=omn: bench_render_horned(str(p), "omn")))
            rows.append(safe(stem, "write", "omny",
                             lambda p=omn: omny_render(str(p))))

        for fmt in ("ofn", "owx"):
            f = DATA / f"{stem}.{fmt}"
            if f.exists():
                rows.append(safe(stem, "write", f"horned-{fmt}",
                                 lambda p=f, x=fmt: bench_render_horned(str(p), x)))

    # Write CSV
    cols = [
        "ontology", "mode", "backend",
        "wall_hot_median_s", "peak_rss_bytes",
        "bytes", "component_count",
        "status", "error",
    ]
    csv_path = OUT / "raw.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    ok = sum(1 for r in rows if r["status"] == "ok")
    failed = len(rows) - ok
    print(f"\nwrote {csv_path}: {len(rows)} cells, {ok} ok, {failed} failed/skipped")

    # Quick sanity: report per-ontology ok counts
    from collections import Counter
    by_onto: Counter = Counter()
    for r in rows:
        if r["status"] == "ok":
            by_onto[r["ontology"]] += 1
    print("ok counts by ontology:", dict(by_onto))


if __name__ == "__main__":
    main()
