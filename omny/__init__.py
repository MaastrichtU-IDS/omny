from importlib.metadata import PackageNotFoundError, version as _pkg_version

from omny.frames import parse
from omny._lark_parser import parse_expression_lark as parse_expression
from omny.render import render, render_expression, render_frame
from omny.sparql import class_relations_query

__all__ = [
    "parse",
    "parse_expression",
    "render",
    "render_expression",
    "render_frame",
    "class_relations_query",
    "__version__",
]

# Read version from installed-package metadata so it stays in sync with
# ``pyproject.toml`` automatically. Fallback for editable / un-installed
# checkouts (e.g. running tests against a source-only tree).
try:
    __version__ = _pkg_version("omny")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
