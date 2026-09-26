"""One save-path contract for every harness that calls ``/doc/NEW``.

Four harnesses discard the open document, and until 2026-09-21 each asked for
somewhere to put a checkpoint in its own way: ``live_manual_feedback.py``
required ``--save-dir``, ``packages/typescript/scripts/live-crud.mjs`` required
it unless the caller waived the checkpoint, ``live_crud_check.py``'s
``--save-as`` was optional, and ``live_smoke.py`` had no such flag at all. Four
destructive tools, four rules, and the weakest of them was the one that runs
the longest.

The rule is now the same in all four, and it is the npm harness's:

    --save-dir DIR       where this run's checkpoints go, **on the NX machine**
    --no-save-before     waive the checkpoint. It removes the safety net, not
                         the /doc/NEW.

Neither one given is refused before a single call goes out.

Two stated departures, both about what a checkpoint *is* for that harness:
``live_crud_check.py`` also takes ``--save-as``, an exact path, because it had
one and callers have it in their fingers; and ``live_manual_feedback.py`` has
no waiver, because its per-probe saves are the evidence the run produces
rather than a safety net. A departure with a reason is a different thing from
the four rules this replaced, which differed for none.

Why a directory and not a path: the checkpoint's **extension** decides whether
the product accepts the save at all, and this repo got that wrong twice. The
NX pair is Gen ``.mgbx`` / Civil ``.mcbz``, and the pre-NX pair (``.mgb`` /
``.mcb``) is the one ``/doc/STAGAS`` wants instead. Deriving the name from the
product removes that choice from the caller.

Why it is required rather than guessed: every path resolves on the machine
running NX, not the one running the script. A directory that does not exist
there raises a modal dialog *there* while the HTTP call still answers
``{"message": "... command complete"}``, and the whole API session blocks
until a human dismisses it. Deriving one from ``verify_connection()["user"]``
was tried and disproved on 2026-08-31: that field is the MAPI account's email,
not the host's Windows profile.

The shape check runs while arguments are parsed rather than at the save, so a
malformed path costs nothing -- not even a connection.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

#: Product-native NX extensions, author-confirmed 2026-08-31.
PRODUCT_EXTENSION = {"gen": "mgbx", "civil": "mcbz"}

#: An absolute Windows directory, which is what a path on the NX host is.
#: Same rule as `isAbsoluteHostDirectory` in live-crud.mjs.
_ABSOLUTE_HOST_DIRECTORY = re.compile(r"^[A-Za-z]:/[^\0]*$")

_SAVE_DIR_HELP = (
    "directory ON THE NX MACHINE for this run's checkpoints, e.g. C:/temp. "
    "Every path here resolves on the host running NX, not on this one, and a "
    "directory that does not exist there raises a blocking dialog while the "
    "HTTP call still answers like a success -- so it is named, never guessed."
)
_NO_SAVE_HELP = (
    "skip the checkpoint of the currently open document. This removes the "
    "safety net, not the /doc/NEW: the open document is still discarded."
)
MISSING_SAVE_DIR = (
    "this harness calls /doc/NEW and writes a checkpoint per probe. Give "
    "--save-dir a writable directory on the NX machine; those files are the "
    "run's evidence, so there is no waiver for them."
)
MISSING_SAVE_TARGET = (
    "this harness calls /doc/NEW and discards the open document. Give "
    "--save-dir a writable directory on the NX machine, or pass "
    "--no-save-before to waive the checkpoint (which does not waive the "
    "/doc/NEW)."
)


def add_arguments(parser: argparse.ArgumentParser, *, waivable: bool = True) -> None:
    """Add the shared ``--save-dir`` / ``--no-save-before`` pair.

    ``waivable=False`` leaves ``--no-save-before`` off, for a harness whose
    checkpoints are not only a safety net. ``live_manual_feedback.py`` is the
    one: each probe saves the document it built, and those files *are* the
    evidence the run exists to produce, so there is nothing there to waive.
    An exception that is stated is a different thing from the four rules this
    module replaced, which differed for no recorded reason.
    """
    parser.add_argument("--save-dir", help=_SAVE_DIR_HELP)
    if waivable:
        parser.add_argument("--no-save-before", action="store_true", help=_NO_SAVE_HELP)


def normalize_directory(save_dir: str) -> str:
    """A host directory with separators and trailing slashes settled."""
    return save_dir.replace("\\", "/").rstrip("/")


def is_absolute_host_directory(save_dir: str) -> bool:
    return bool(_ABSOLUTE_HOST_DIRECTORY.match(normalize_directory(save_dir)))


def require(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    *,
    exact_path: str | None = None,
) -> None:
    """Refuse the run unless a save target is named or explicitly waived.

    ``exact_path`` is for a harness that also accepts a full file path of its
    own (``live_crud_check.py``'s ``--save-as``); naming one satisfies the
    requirement, and its extension is the caller's to get right.
    """
    if getattr(args, "no_save_before", False):
        return
    if not args.save_dir and not exact_path:
        parser.error(
            MISSING_SAVE_TARGET if hasattr(args, "no_save_before")
            else MISSING_SAVE_DIR
        )
    if args.save_dir and not is_absolute_host_directory(args.save_dir):
        parser.error(
            f"--save-dir must be an absolute directory on the NX machine, "
            f"got {args.save_dir!r}."
        )


def checkpoint_prefix(save_dir: str, label: str, product: str) -> str:
    """A unique, extension-less checkpoint stem inside ``save_dir``.

    Stamped so a re-run never lands on an existing file: an overwrite prompt
    on the NX host is another modal dialog blocking the session.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{normalize_directory(save_dir)}/{label}-{product}-{stamp}"


def checkpoint(save_dir: str, label: str, product: str) -> str:
    """``checkpoint_prefix`` with the product's own NX extension."""
    return f"{checkpoint_prefix(save_dir, label, product)}.{PRODUCT_EXTENSION[product]}"
