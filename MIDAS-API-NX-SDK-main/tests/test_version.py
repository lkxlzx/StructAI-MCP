"""The installed distribution's version and midas_nx.__version__ must agree.

They didn't between v0.10.0 and v0.11.2: the release procedure bumped only
pyproject.toml, so `pip install midas-nx==0.11.2` shipped a package reporting
`__version__ == "0.10.0"`. pyproject.toml now declares dynamic = ["version"]
and hatchling reads __init__.py, making that drift impossible — this test is
the guard that keeps it that way.
"""
from importlib import metadata

import midas_nx


def test_dunder_version_matches_installed_distribution():
    assert midas_nx.__version__ == metadata.version("midas-nx")
