from pathlib import Path

import pytest

from bench.corpus import CorpusEntry
from bench.download import (
    cached_omn_path,
    download_one,
    sha256_of,
)


def test_sha256_of_known_bytes(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello\n")
    # echo "hello" | sha256sum
    assert sha256_of(f) == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"


def test_cached_omn_path_uses_bench_data(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    e = CorpusEntry(
        name="x", tier="tiny", url="http://example.org/x.owl",
        sha256="skip-checksum", approx_axioms=10, fmt="rdfxml",
    )
    assert cached_omn_path(e) == tmp_path / "x.omn"


def test_download_one_short_circuits_when_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_DATA_DIR", str(tmp_path))
    e = CorpusEntry(
        name="cheese", tier="tiny", url="http://example.org/x.owl",
        sha256="skip-checksum", approx_axioms=10, fmt="rdfxml",
    )
    (tmp_path / "cheese.omn").write_text("Prefix: : <http://ex.org/>\nClass: Cheese\n")
    out = download_one(e)
    assert out == tmp_path / "cheese.omn"
