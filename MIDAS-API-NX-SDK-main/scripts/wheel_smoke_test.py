"""Smoke-test an *installed* midas-nx (not the source tree).

Run against a venv that has the built wheel installed, from a directory that
does not contain ./src — CI does both. Catches the class of bug that unit
tests structurally cannot: something that works in the repo but is missing
from, or broken in, the distributed artifact.

    python -m venv /tmp/smoke
    /tmp/smoke/bin/pip install dist/*.whl
    cd / && /tmp/smoke/bin/python scripts/wheel_smoke_test.py

Exits non-zero on the first failure. No network, no MIDAS NX session — every
check here is local, and the one call it makes is expected to be refused by a
client-side guard before any HTTP happens.
"""
import pathlib
import sys
from importlib import metadata

# Windows consoles default to cp949; keep this readable there too.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

failures = []


def check(name, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a smoke test reports, it doesn't handle
        failures.append(f"{name}: {type(exc).__name__}: {exc}")
        print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    else:
        print(f"ok   {name}")


import midas_nx  # noqa: E402
from midas_nx import DestructiveOperationError, MidasClient, Product  # noqa: E402


def _imported_from_installed_package():
    path = pathlib.Path(midas_nx.__file__).resolve()
    assert "site-packages" in path.parts, (
        f"imported the source tree, not the installed wheel: {path}"
    )


def _py_typed_shipped():
    # Without this marker in the wheel, downstream type checking of this SDK
    # silently degrades to Any, and no unit test would notice.
    marker = pathlib.Path(midas_nx.__file__).parent / "py.typed"
    assert marker.is_file(), f"py.typed missing from the installed package at {marker}"


def _version_matches_distribution():
    installed = metadata.version("midas-nx")
    assert midas_nx.__version__ == installed, (
        f"__version__ is {midas_nx.__version__} but the installed "
        f"distribution is {installed}"
    )


def _subpackages_import():
    # 'import midas_nx' alone does not exercise these.
    from midas_nx.db.node_element import Node  # noqa: F401
    from midas_nx.design.rc_kds import checks  # noqa: F401
    from midas_nx.post.base import unwrap_table  # noqa: F401


def _destructive_guard_is_armed():
    from midas_nx.db.node_element import Node

    client = MidasClient(mapi_key="not-a-real-key", product=Product.GEN)
    try:
        Node.delete_all(client=client)
    except DestructiveOperationError:
        return
    raise AssertionError("delete_all() proceeded without confirm=True")


check("imported from the installed wheel", _imported_from_installed_package)
check("py.typed is packaged", _py_typed_shipped)
check("__version__ matches the distribution", _version_matches_distribution)
check("subpackages import", _subpackages_import)
check("delete_all() guard is armed", _destructive_guard_is_armed)

if failures:
    print(f"\n{len(failures)} check(s) failed")
    sys.exit(1)

print(f"\nall checks passed for midas-nx {midas_nx.__version__}")
