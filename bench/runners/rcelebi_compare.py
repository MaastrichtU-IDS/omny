"""One-off head-to-head: upstream owlready2 (0.50, Cython-optimised parser)
vs the ``rcelebi/owlready2`` fork (0.25, pure-Python parser + pyoxigraph
SPARQL backend) — for **parse** and **SPARQL query** wall time.

This is **not** wired into ``run_snapshot``. The reason: rcelebi/owlready2
publishes under the same PyPI name as upstream owlready2, so the two
cannot coexist in one venv. We carry rcelebi in a sibling
``.venv_rcelebi/`` and shell out to it for its measurements. Building a
full subprocess-and-multi-venv backend layer would add infrastructure
that benefits only this one comparison; a focused one-off script is
the honest middle ground.

Run with:

    python -m bench.runners.rcelebi_compare \\
        --ontologies sio,obi-core \\
        --rcelebi-python .venv_rcelebi/bin/python

It prints a table per ontology and exits.
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Workers — each is a one-shot script run in the target venv via -c.
#
# We pass a JSON-encoded ``{op, path}`` on argv and print a JSON
# ``{wall: float, ...extras}`` on stdout. Stays self-contained so it can
# run inside .venv_rcelebi without importing anything from the parent
# omny package (rcelebi's owlready2 has the same module name as
# upstream's; omny's compatibility with rcelebi is not part of the
# claim here).
# ---------------------------------------------------------------------------

_WORKER = r"""
import io, json, os, sys, time
op, path = sys.argv[1], sys.argv[2]
import owlready2
# `get_ontology` wants a URI; tolerate plain filesystem paths.
ref = path if "://" in path else "file://" + os.path.abspath(path)
t = time.perf_counter()
if op == "parse":
    onto = owlready2.get_ontology(ref).load()
    wall = time.perf_counter() - t
    out = {"wall": wall, "classes": sum(1 for _ in onto.classes())}
elif op == "parse_then_query":
    onto = owlready2.get_ontology(ref).load()
    parse_wall = time.perf_counter() - t
    # Same SPARQL body in both venvs so the comparison is apples-to-apples.
    # Upstream owlready2 (0.50) exposes ``world.sparql``; rcelebi (0.25 +
    # pyoxigraph) exposes ``world.sparql_query`` — try the modern one
    # first, fall back to the legacy name.
    q = (
        "SELECT (COUNT(*) AS ?n) WHERE { "
        "  ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?d . "
        "  FILTER(isIRI(?c) && isIRI(?d)) "
        "}"
    )
    runner = getattr(onto.world, "sparql", None) or getattr(onto.world, "sparql_query", None)
    if runner is None:
        out = {"error": "no SPARQL method on World (neither .sparql nor .sparql_query)"}
    else:
        t2 = time.perf_counter()
        rows = list(runner(q))
        query_wall = time.perf_counter() - t2
        # Row shape differs: upstream gives [[int]]; rcelebi via pyoxigraph
        # gives pyoxigraph QuerySolution objects. Just check non-empty.
        out = {"wall": parse_wall + query_wall,
               "parse_wall": parse_wall, "query_wall": query_wall,
               "row_count": len(rows)}
else:
    out = {"error": "unknown op: " + op}
print(json.dumps(out))
"""


def _run_worker(python: str, op: str, path: str) -> dict:
    proc = subprocess.run(
        [python, "-c", _WORKER, op, path],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr.strip().splitlines()[-1] if proc.stderr else "nonzero exit"}
    # rcelebi prints a stderr warning about the missing Cython parser; ignore it.
    last_line = proc.stdout.strip().splitlines()[-1]
    return json.loads(last_line)


def _detect_rdf_input(ontology_name: str) -> Path:
    """Both forks of owlready2 load RDF/XML directly; .omn is omny's
    natural input but not owlready2's. Standardise on .rdfxml for the
    head-to-head when both versions are present."""
    data_dir = Path(__file__).resolve().parents[1] / "data"
    rdf = data_dir / f"{ontology_name}.rdfxml"
    omn = data_dir / f"{ontology_name}.omn"
    if rdf.exists():
        return rdf
    if omn.exists():
        return omn
    raise FileNotFoundError(f"no .rdfxml or .omn found for {ontology_name!r} in {data_dir}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ontologies", default="pizza,koala,travel,sio",
                   help="comma-separated ontology names from the bench corpus")
    p.add_argument("--rcelebi-python",
                   default=str(Path(__file__).resolve().parents[2] / ".venv_rcelebi" / "bin" / "python"),
                   help="path to a Python interpreter where rcelebi/owlready2 is installed")
    args = p.parse_args(argv)

    upstream_python = sys.executable
    rcelebi_python = args.rcelebi_python

    if not Path(rcelebi_python).exists():
        print(f"error: rcelebi venv python not found at {rcelebi_python!r}", file=sys.stderr)
        print("       create it with:", file=sys.stderr)
        print("         python3 -m venv .venv_rcelebi", file=sys.stderr)
        print("         .venv_rcelebi/bin/pip install git+https://github.com/rcelebi/owlready2.git pyoxigraph", file=sys.stderr)
        return 1

    rows = []
    for name in args.ontologies.split(","):
        name = name.strip()
        try:
            inp = _detect_rdf_input(name)
        except FileNotFoundError as e:
            print(f"  skip {name}: {e}")
            continue

        up = _run_worker(upstream_python, "parse_then_query", str(inp))
        rc = _run_worker(rcelebi_python, "parse_then_query", str(inp))
        rows.append((name, inp.stat().st_size, up, rc))

    # Pretty-print
    print()
    print(f"{'ontology':<12} {'bytes':>9}  "
          f"{'upstream parse':>15} {'rcelebi parse':>15}  "
          f"{'upstream sparql':>16} {'rcelebi sparql':>16}")
    print("-" * 95)
    for name, sz, up, rc in rows:
        if "error" in up or "error" in rc:
            print(f"{name:<12} {sz:>9}  err up: {up.get('error','')[:30]:30} rc: {rc.get('error','')[:30]:30}")
            continue
        print(f"{name:<12} {sz:>9}  "
              f"{up['parse_wall']*1000:>13.0f}ms {rc['parse_wall']*1000:>13.0f}ms  "
              f"{up['query_wall']*1000:>14.0f}ms {rc['query_wall']*1000:>14.0f}ms")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
