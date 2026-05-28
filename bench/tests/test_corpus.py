from bench.corpus import CORPUS, CorpusEntry, by_tier, TIERS


def test_tiers_known():
    assert TIERS == ("tiny", "small", "medium", "large", "huge")


def test_corpus_has_entries_in_each_tier_except_huge():
    for tier in ("tiny", "small", "medium", "large"):
        assert len(by_tier(tier)) >= 2, f"{tier} should have at least 2 entries"


def test_every_entry_has_minimum_fields():
    for e in CORPUS:
        assert isinstance(e, CorpusEntry)
        assert e.name
        assert e.url.startswith(("http://", "https://"))
        assert e.tier in TIERS
        assert e.approx_axioms > 0
        # SHA256 is 64 hex chars OR the literal "skip-checksum" for unpinned upstreams
        assert len(e.sha256) == 64 or e.sha256 == "skip-checksum"


def test_pizza_is_tiny():
    pizza = next(e for e in CORPUS if e.name == "pizza")
    assert pizza.tier == "tiny"
