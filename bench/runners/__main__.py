"""Allow `python -m bench.runners` as an alias for the snapshot CLI."""
from bench.runners.snapshot import _cli

_cli()
