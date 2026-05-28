from pathlib import Path

from bench.reasoners.none import NoneReasoner
from bench.reasoners.owlrl import OwlrlReasoner


def test_none_reasoner_returns_input(pizza_text, tmp_path):
    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    r = NoneReasoner()
    out = r.materialise(p)
    assert out == p


def test_owlrl_reasoner_adds_inferred_triples(pizza_text, tmp_path):
    import rdflib

    p = tmp_path / "pizza.omn"
    p.write_text(pizza_text)
    r = OwlrlReasoner()
    out = r.materialise(p)
    assert out != p
    g_in = rdflib.Graph()
    import pymos
    import io
    buf = io.BytesIO()
    pymos.parse(pizza_text).save(file=buf, format="ntriples")
    g_in.parse(data=buf.getvalue(), format="nt")

    g_out = rdflib.Graph()
    g_out.parse(out)

    assert len(g_out) > len(g_in)


from bench.reasoners.robot_docker import RobotDocker
from bench.tests.conftest import requires_docker


@requires_docker
def test_robot_docker_version_smoke():
    rd = RobotDocker(image="obolibrary/robot:v1.9.6")
    v = rd.version()
    assert "ROBOT" in v or "robot" in v.lower()
