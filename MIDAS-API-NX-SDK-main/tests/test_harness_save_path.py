"""Every harness that calls `/doc/NEW` asks for a save location the same way.

Until 2026-09-21 the four disagreed: one required a directory, one required it
unless the caller waived the checkpoint, one had an optional path and one had
no flag at all -- and the weakest of them was the one that runs the longest.
`scripts/harness_save_path.py` is the single rule; these hold that each
harness actually applies it, and that the npm harness has not drifted from it.

Nothing here reaches a product: every case is refused while arguments are
parsed, which is the point of checking the path's shape there.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NPM_HARNESS = ROOT / "packages" / "typescript" / "scripts" / "live-crud.mjs"


def _module():
    spec = importlib.util.spec_from_file_location(
        "harness_save_path_under_test",
        ROOT / "scripts" / "harness_save_path.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parsed(module, argv, *, waivable=True):
    parser = argparse.ArgumentParser(prog="harness")
    module.add_arguments(parser, waivable=waivable)
    return parser, parser.parse_args(argv)


@pytest.mark.parametrize("save_dir,absolute", [
    ("C:/temp", True),
    ("C:\\temp", True),
    ("c:/NX Scratch/checkpoints/", True),
    ("scratch", False),
    ("./scratch", False),
    ("/tmp/scratch", False),          # POSIX: this script's machine, not NX's
    ("\\\\server\\share", False),     # UNC: not a drive-letter path
])
def test_only_an_absolute_host_directory_is_a_usable_save_directory(
    save_dir, absolute
) -> None:
    """A path resolves on the NX host, which is a Windows machine.

    A relative one resolves against whatever that host's working directory
    happens to be, which is the guess this flag exists to prevent.
    """
    assert _module().is_absolute_host_directory(save_dir) is absolute


def test_naming_nothing_is_refused_before_any_call_goes_out() -> None:
    module = _module()
    parser, args = _parsed(module, [])
    with pytest.raises(SystemExit):
        module.require(parser, args)


def test_waiving_the_checkpoint_is_accepted_and_waives_the_shape_check_too() -> None:
    """--no-save-before removes the safety net, not the /doc/NEW."""
    module = _module()
    parser, args = _parsed(module, ["--no-save-before"])
    module.require(parser, args)  # does not raise


def test_an_exact_path_satisfies_the_requirement_in_place_of_a_directory() -> None:
    """live_crud_check.py's --save-as; its extension is the caller's to get right."""
    module = _module()
    parser, args = _parsed(module, [])
    module.require(parser, args, exact_path="C:/temp/scratch.mcbz")


def test_a_harness_with_no_waiver_has_no_waiver_flag_to_pass() -> None:
    """live_manual_feedback.py's per-probe saves are the run's evidence."""
    module = _module()
    parser, args = _parsed(module, [], waivable=False)
    assert not hasattr(args, "no_save_before")
    with pytest.raises(SystemExit):
        module.require(parser, args)


@pytest.mark.parametrize("product,extension", [("gen", "mgbx"), ("civil", "mcbz")])
def test_the_checkpoint_carries_the_product_s_own_nx_extension(
    product, extension
) -> None:
    """Deriving it is the point: this repo got the two pairs wrong twice.

    Gen NX writes `.mgbx` and Civil NX `.mcbz`; the pre-NX `.mgb`/`.mcb` pair
    is what `/doc/STAGAS` wants instead, and `/doc/SAVEAS` rejects the wrong
    spelling outright.
    """
    module = _module()
    path = module.checkpoint("C:\\temp\\", "run", product)
    assert path.startswith("C:/temp/run-" + product + "-")
    assert path.endswith("." + extension)
    assert module.checkpoint_prefix("C:/temp", "run", product) == path[: -len(extension) - 1]


@pytest.mark.parametrize("script,argv,expected", [
    ("scripts/live_smoke.py", ["--product", "gen"], "--no-save-before to waive"),
    ("scripts/live_smoke.py", ["--product", "gen", "--save-dir", "scratch"],
     "must be an absolute directory"),
    ("scripts/live_crud_check.py", ["--product", "gen", "--tier", "core"],
     "--no-save-before to waive"),
    ("scripts/live_crud_check.py",
     ["--product", "gen", "--tier", "core", "--save-dir", "scratch"],
     "must be an absolute directory"),
    ("scripts/live_manual_feedback.py", ["--product", "gen", "--out", "unused.json"],
     "no waiver for them"),
])
def test_each_destructive_harness_refuses_to_start_without_one(
    script, argv, expected
) -> None:
    """`live_crud_check.py` checks the selection first on purpose.

    A typo in `--tier` or `--endpoints` is reported as a typo rather than as a
    missing save directory, so the cases here name a selection that resolves.
    Both refusals still happen before a client exists.
    """
    result = subprocess.run(
        [sys.executable, script, *argv],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0, result.stdout
    assert expected in result.stderr, result.stderr


def test_the_npm_harness_still_applies_the_same_two_rules() -> None:
    """One fixture, two harnesses, and one save-path rule between them.

    live-crud.mjs cannot import the Python module, so the rule is duplicated
    there. Both halves of it are asserted rather than trusted: the
    drive-letter test and the product-to-extension mapping.
    """
    module = _module()
    source = NPM_HARNESS.read_text(encoding="utf-8")
    # The same pattern, written as a JS regex literal: `/` is escaped there.
    as_js_literal = module._ABSOLUTE_HOST_DIRECTORY.pattern.replace("/", r"\/")
    assert as_js_literal in source
    assert 'product === "civil" ? "mcbz" : "mgbx"' in source
    # And it refuses before connecting, the same as the Python three.
    assert "isAbsoluteHostDirectory(args.saveDir)" in source
