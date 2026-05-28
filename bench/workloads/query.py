"""Query workload: time class_relations_query over a chosen backend."""
import importlib

from pymos import class_relations_query

from bench.measure import Measurement, measure_in_subprocess


_BACKEND_FACTORIES = {
    "owlready2_mem": ("bench.backends.owlready2_mem", "OwlreadyMemBackend"),
    "pyoxigraph_mem": ("bench.backends.pyoxigraph_mem", "PyoxigraphMemBackend"),
    "rdflib_mem": ("bench.backends.rdflib_mem", "RdflibMemBackend"),
}


def _do_query(
    onto_path: str, backend_name: str, target_iri: str,
    relation: str, construct: bool,
) -> None:
    import pymos
    onto = pymos.parse(open(onto_path).read())
    mod_name, cls_name = _BACKEND_FACTORIES[backend_name]
    cls = getattr(importlib.import_module(mod_name), cls_name)
    b = cls()
    b.load(onto)
    q = class_relations_query(f"<{target_iri}>", relations=(relation,), construct=construct)
    method = b.construct if construct else b.select
    try:
        list(method(q))
    except NotImplementedError:
        pass  # owlready2 + CONSTRUCT — handled by the runner via per-cell n/a check
    b.close()


def bench_query(
    *, onto_path: str = "", backend_name: str = "pyoxigraph_mem",
    target_iri: str, relation: str, construct: bool = True,
    hot_iters: int = 3, warmup: int = 1,
) -> Measurement:
    if not onto_path:
        # Inline-only path is used by unit tests: build a tiny ontology inline
        import pymos
        onto = pymos.parse(open("tests/data/pizza.omn").read())
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".omn", delete=False, mode="w") as f:
            f.write(open("tests/data/pizza.omn").read())
            onto_path = f.name

    m = measure_in_subprocess(
        "bench.workloads.query", "_do_query",
        args=(onto_path, backend_name, target_iri, relation, construct),
        hot_iters=hot_iters, warmup=warmup,
    )
    m.extras["relation"] = relation
    m.extras["construct"] = construct
    m.extras["backend"] = backend_name
    m.extras["target"] = target_iri
    return m
