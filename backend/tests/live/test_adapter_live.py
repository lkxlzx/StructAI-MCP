"""Live end-to-end test against a running MIDAS Gen/Civil NX instance.

**Skipped by default.** Enable explicitly:

```powershell
$env:STRUCTAI_LIVE_MIDAS_URL = "http://localhost:3030"
$env:STRUCTAI_LIVE_MAPI_KEY = "<key>"
$env:STRUCTAI_LIVE_PRODUCT  = "gen"          # or "civil"
..\\.venv\\Scripts\\python.exe -m pytest tests/live -q
```

What it proves (and why it is worth keeping):

* the whole chain **build → analyse → read results** works through the adapter,
* the numbers agree with the **closed-form solution** of a cantilever,
  which is the only assertion that can catch a silently-wrong model
  (对接规范 §11.6 — a mis-placed load produced *plausible* reactions with zero
  displacement, and only the analytical check exposed it).

**It writes to the open document.** It deletes `/db/CNLD`, `/db/NODE`, `/db/ELEM`,
`/db/CONS`, `/db/STLD`, `/db/MATL`, `/db/SECT` keys 1–2 first. Only point it at a
disposable model.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from app.adapters.midas_gen.adapter import MidasNxAdapter
from app.core.midas_config import MidasConnection, MidasProduct

_LIVE_URL = os.environ.get("STRUCTAI_LIVE_MIDAS_URL")
_LIVE_KEY = os.environ.get("STRUCTAI_LIVE_MAPI_KEY")
_LIVE_PRODUCT = os.environ.get("STRUCTAI_LIVE_PRODUCT", "gen")

pytestmark = pytest.mark.skipif(
    not (_LIVE_URL and _LIVE_KEY),
    reason=(
        "live MIDAS test — set STRUCTAI_LIVE_MIDAS_URL and STRUCTAI_LIVE_MAPI_KEY "
        "to enable (it writes to the open document)"
    ),
)

# --- the reference problem -------------------------------------------------
# Cantilever column, C32 concrete 600x600, L = 3.2 m, fixed at the base,
# P = 10000 kN lateral at the tip.  Closed-form:
#   tip deflection  PL^3 / 3EI
#   tip rotation    PL^2 / 2EI
#   base moment     P * L
_LENGTH_M = 3.2
_LOAD_KN = 10000.0
_E_KN_M2 = 30_100_000.0
_I_M4 = 0.6**4 / 12.0  # 0.0108

_EXPECT_DX_MM = _LOAD_KN * _LENGTH_M**3 / (3 * _E_KN_M2 * _I_M4) * 1000.0
_EXPECT_RY_RAD = _LOAD_KN * _LENGTH_M**2 / (2 * _E_KN_M2 * _I_M4)
_EXPECT_MY_KNMM = -_LOAD_KN * _LENGTH_M * 1000.0


def _connection() -> MidasConnection:
    return MidasConnection(
        name="live",
        software="MIDAS Gen NX" if _LIVE_PRODUCT == "gen" else "MIDAS Civil NX",
        product=MidasProduct(_LIVE_PRODUCT),
        base_url=_LIVE_URL,
        mapi_key=_LIVE_KEY,
        timeout_seconds=120,
        verify_tls=False,
    )


def _columns(data: dict) -> tuple[dict[str, int], list]:
    """`/post/TABLE` returns HEAD-aligned **lists**, not dicts."""
    return {name: i for i, name in enumerate(data["HEAD"])}, data["DATA"]


def _run(coro):
    return asyncio.run(coro)


def test_health_and_liveness() -> None:
    """`/mapikey/verify` at the host root, plus the real-data liveness probe."""

    async def body():
        adapter = MidasNxAdapter(_connection())
        try:
            health = await adapter.health_check()
            assert health.success, health.error_message
            assert health.data["keyVerified"] is True
            assert health.data["program"] == _LIVE_PRODUCT

            # §2.5.2: health_check cannot see a modal-dialog-blocked session,
            # so a real data call is the only reliable liveness probe.
            alive = await adapter.probe_alive()
            assert alive.success, alive.error_message
            return health
        finally:
            await adapter.aclose()

    _run(body())


def test_introspection_reads_the_argument_wrapper() -> None:
    """§5.0.1: `/info` wraps the schema under `Argument`, never the resource name."""

    async def body():
        adapter = MidasNxAdapter(_connection())
        try:
            result = await adapter.introspect("NODE")
            assert result.success, result.error_message
            props = result.data["properties"]
            assert set(props) == {"X", "Y", "Z"}
            # §5.1: design-code endpoints are NOT introspectable.
            assert MidasNxAdapter.is_introspectable("NODE") is True
            assert MidasNxAdapter.is_introspectable("/DESIGN/RC/KDS-41-20-2022/DCTL") is False
        finally:
            await adapter.aclose()

    _run(body())


def test_cantilever_build_analyse_and_read_matches_closed_form() -> None:
    """The full chain, asserted against the analytical solution.

    This is the test that caught the `/db/CNLD` outer-key trap (对接规范 §11.6):
    with the load placed on the *fixed* node, reactions were perfect while
    displacement and internal force were identically zero.  Only the closed-form
    comparison made that visible.
    """

    async def body():
        adapter = MidasNxAdapter(_connection())
        try:
            # --- clean (per-id deletes only — §3.5 #1) --------------------
            for resource, ids in (
                ("CNLD", ["1", "2"]), ("NODE", ["1", "2"]), ("ELEM", ["1"]),
                ("CONS", ["1"]), ("STLD", ["1"]), ("MATL", ["1"]), ("SECT", ["1"]),
            ):
                await adapter.delete(resource, ids)

            # --- build ----------------------------------------------------
            for resource, data in (
                ("MATL", {"1": {"TYPE": "CONC", "NAME": "C32",
                                "PARAM": [{"P_TYPE": 1, "STANDARD": "AS17(RC)",
                                           "DB": "C32"}]}}),
                ("SECT", {"1": {"SECTTYPE": "DBUSER", "SECT_NAME": "C600",
                                "SECT_BEFORE": {"SHAPE": "SB", "DATATYPE": 2,
                                                "SECT_I": {"vSIZE": [0.6, 0.6]}}}}),
                ("NODE", {"1": {"X": 0, "Y": 0, "Z": 0},
                          "2": {"X": 0, "Y": 0, "Z": _LENGTH_M}}),
                ("ELEM", {"1": {"TYPE": "BEAM", "MATL": 1, "SECT": 1,
                                "NODE": [1, 2], "ANGLE": 0}}),
                ("CONS", {"1": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}),
                ("STLD", {"1": {"NAME": "LC1", "TYPE": "D", "DESC": "dead"}}),
            ):
                written = await adapter.create_or_update(resource, data)
                assert written.success, f"{resource}: {written.error_message}"

            # --- the load: outer Assign key is the NODE number (§4.1) -----
            assign = adapter.build_assign("2", {"ITEMS": [
                {"ID": 1, "LCNAME": "LC1", "GROUP_NAME": "",
                 "FX": _LOAD_KN, "FY": 0.0, "FZ": 0.0,
                 "MX": 0.0, "MY": 0.0, "MZ": 0.0}]})
            assert set(assign["Assign"]) == {"2"}, "CNLD outer key must be the node number"
            loaded = await adapter.create_or_update("CNLD", assign["Assign"])
            assert loaded.success, loaded.error_message

            # --- analyse --------------------------------------------------
            analysed = await adapter.doc_anal()
            assert analysed.success, analysed.error_message

            # --- read -----------------------------------------------------
            disp = await adapter.get_table(
                "DISPLACEMENTG",
                ["Node", "Load", "DX", "DY", "DZ", "RX", "RY", "RZ"],
                load_case_names=["LC1(ST)"],
                unit={"FORCE": "kN", "DIST": "mm"},
                styles={"FORMAT": "Fixed", "PLACE": 6},
            )
            assert disp.success, disp.error_message
            cols, rows = _columns(disp.data)
            tip = next(r for r in rows if str(r[cols["Node"]]) == "2")
            dx_mm = float(tip[cols["DX"]])
            ry_rad = float(tip[cols["RY"]])

            react = await adapter.get_table(
                "REACTIONG", ["Node", "Load", "FX", "FZ", "MY", "MZ"],
                load_case_names=["LC1(ST)"],
                unit={"FORCE": "kN", "DIST": "mm"},
                styles={"FORMAT": "Fixed", "PLACE": 6},
            )
            assert react.success, react.error_message
            rcols, rrows = _columns(react.data)
            base = rrows[0]
            fx_kn = float(base[rcols["FX"]])
            my_knmm = float(base[rcols["MY"]])

            # --- assert against the closed form --------------------------
            for label, expected, got in (
                ("tip DX (mm)", _EXPECT_DX_MM, dx_mm),
                ("tip RY (rad)", _EXPECT_RY_RAD, ry_rad),
                ("base FX (kN)", -_LOAD_KN, fx_kn),
                ("base MY (kN*mm)", _EXPECT_MY_KNMM, my_knmm),
            ):
                tolerance = max(abs(expected) * 1e-4, 1e-6)
                assert abs(got - expected) <= tolerance, (
                    f"{label}: closed form {expected!r}, MIDAS {got!r}"
                )
        finally:
            await adapter.aclose()

    _run(body())


def test_live_session_diagnosis_reports_healthy() -> None:
    """对接规范 §11.5.13 / §11.5.14 — the diagnosis against a real instance.

    The offline suite drives every state through ``httpx.MockTransport``, which
    proves the *classification* but not that the probes are the right ones
    against a live server.  This asserts the positive case end to end: two real
    probes, both answering, verdict ``healthy`` and ``confirmed``.

    It is also the guard against the failure mode that produced the false
    positive: if the diagnosis ever reported ``session_unresponsive`` for a
    perfectly healthy instance, this test would be the first to say so.
    """

    async def body() -> None:
        adapter = MidasNxAdapter(_connection())
        try:
            result = await adapter.diagnose_session()
            assert result.success is True, result.error_message
            data = result.data if isinstance(result.data, dict) else {}
            assert data["state"] == "healthy", data
            assert data["confirmed"] is True
            assert data["usable"] is True
            assert data["requires_human"] is False
            assert not data["candidates"]
            # both probes really ran, and both answered
            for name in ("verify", "unit"):
                probe = data["probes"][name]
                assert probe["ok"] is True, (name, probe)
                assert probe["http_status"] == 200, (name, probe)
                assert probe["phase"] is None, (name, probe)
        finally:
            await adapter.aclose()

    _run(body())
