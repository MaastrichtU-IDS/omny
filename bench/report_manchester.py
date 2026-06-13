"""Aggregate raw.csv into performance-report.md (per-ontology tables + ratios + headline)."""
from __future__ import annotations
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

OUT = Path("bench/results/2026-06-13-manchester")


def load():
    with open(OUT / "raw.csv") as fh:
        return list(csv.DictReader(fh))


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def geomean(xs):
    xs = [x for x in xs if x and x > 0]
    if not xs:
        return float("nan")
    return statistics.geometric_mean(xs)


def main():
    rows = load()
    ok = [r for r in rows if r["status"] == "ok"]
    fails = [r for r in rows if r["status"] != "ok"]
    by = defaultdict(dict)  # (onto, mode) -> {backend: row}
    for r in ok:
        by[(r["ontology"], r["mode"])][r["backend"]] = r

    md = ["# Manchester `io/omn` Performance Report\n"]

    # Headline: horned-omn vs omny / owlapi / fastobo-omn (geomean of read ratios)
    omny_speedups, owlapi_speedups, fastobo_ratios = [], [], []
    for (onto, mode), cells in by.items():
        if mode != "read" or "horned-omn" not in cells:
            continue
        ho = fnum(cells["horned-omn"]["wall_hot_median_s"])
        if ho is None or ho <= 0:
            continue
        if "omny" in cells:
            omny_t = fnum(cells["omny"]["wall_hot_median_s"])
            if omny_t:
                omny_speedups.append(omny_t / ho)
        if "owlapi" in cells:
            owlapi_t = fnum(cells["owlapi"]["wall_hot_median_s"])
            if owlapi_t:
                owlapi_speedups.append(owlapi_t / ho)
        if "fastobo-omn" in cells:
            fastobo_t = fnum(cells["fastobo-omn"]["wall_hot_median_s"])
            if fastobo_t:
                fastobo_ratios.append(fastobo_t / ho)

    omny_gm = geomean(omny_speedups)
    owlapi_gm = geomean(owlapi_speedups)
    fastobo_gm = geomean(fastobo_ratios)

    md.append("## Headline\n")
    if not math.isnan(omny_gm):
        md.append(
            f"- `horned-omn` read is **{omny_gm:.1f}× faster than omny** "
            f"(geomean over {len(omny_speedups)} ontologies)."
        )
    if not math.isnan(owlapi_gm):
        md.append(
            f"- `horned-omn` read is **{owlapi_gm:.1f}× faster than OWL-API/ROBOT** "
            f"(geomean over {len(owlapi_speedups)}; ROBOT carries docker+JVM overhead — see caveats)."
        )
    if not math.isnan(fastobo_gm):
        md.append(
            f"- `horned-omn` vs `fastobo-omn` (other Rust impl): geomean ratio "
            f"{fastobo_gm:.2f}× (>1 = fastobo slower; fastobo-omn excludes sio/hp which failed)."
        )
    md.append("")

    # Per (ontology, mode) tables
    for (onto, mode) in sorted(by):
        cells = by[(onto, mode)]
        md.append(f"## {onto} — {mode}\n")
        md.append("| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |")
        md.append("|---|---|---|---|---|")
        base = fnum(cells.get("owlapi", {}).get("wall_hot_median_s")) if "owlapi" in cells else None
        for backend, r in sorted(
            cells.items(), key=lambda kv: fnum(kv[1]["wall_hot_median_s"]) or 9e9
        ):
            med = fnum(r["wall_hot_median_s"])
            rss = fnum(r["peak_rss_bytes"])
            nbytes = fnum(r["bytes"])
            med_ms = f"{med * 1e3:.2f}" if med is not None else ""
            # Fix: compute rss_mb as a string before the f-string
            rss_mb = f"{rss / 1e6:.1f}" if rss is not None else ""
            thru = f"{nbytes / 1e6 / med:.1f}" if (nbytes and med) else ""
            ratio = f"{med / base:.2f}×" if (base and med) else ""
            md.append(f"| {backend} | {med_ms} | {rss_mb} | {thru} | {ratio} |")
        md.append("")

    if fails:
        md.append("## Conformance failures (excluded from timing)\n")
        md.append("| ontology | mode | backend | error |")
        md.append("|---|---|---|---|")
        for r in fails:
            error_snippet = r["error"][:120].replace("|", "/")
            md.append(f"| {r['ontology']} | {r['mode']} | {r['backend']} | {error_snippet} |")
        md.append("")

    md.append("## Caveats\n")
    md.append("- Rust timings are in-process hot medians (cold-start ~2 ms excluded).")
    md.append(
        "- OWL-API via ROBOT docker: hot median carries per-call docker overhead "
        "(~1.5 s startup in cold)."
    )
    md.append("- omny is pure-Python; fastobo-omn (horned-owl 0.14) is read-only (no serializer).")
    md.append(
        "- Component counts differ across formats (declaration handling); "
        "this measures per-format parse/serialize SPEED, not identical-axiom-set parsing."
    )
    md.append("")

    out_path = OUT / "performance-report.md"
    out_path.write_text("\n".join(md) + "\n")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
