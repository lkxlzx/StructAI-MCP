"""Compatibility shim - the driver now lives in :mod:`midas_mcp.frame`.

This module used to hold the whole eighteen-step driver.  It moved into the
package so that one implementation can be reached three ways::

    python -m midas_mcp.frame --spec specs/portal-frame.json   # the command
    midas_frame_run                                            # the MCP tool

and so that tests can import it.  Keeping the driver in ``tests/`` meant the
tool had to re-implement it or shell out to a file that is not shipped with the
package; both drift.

Nothing is reimplemented here.  New code should call ``python -m
midas_mcp.frame`` or the ``midas_frame_run`` tool.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Running this file directly puts ``tests/`` on sys.path, not ``src/``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from midas_mcp import frame as _frame  # noqa: E402
from midas_mcp.frame import *  # noqa: F401,F403,E402


if __name__ == "__main__":
    sys.exit(_frame.main())
