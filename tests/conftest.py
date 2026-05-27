import owlready2
import pytest


@pytest.fixture
def onto():
    """A fresh, isolated owlready2 ontology in its own World per test."""
    world = owlready2.World()
    ontology = world.get_ontology("http://pymos.test/onto.owl")
    yield ontology
    world.close()
