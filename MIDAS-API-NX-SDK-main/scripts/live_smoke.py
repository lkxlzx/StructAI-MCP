"""Live round-trip smoke test against a REAL, running Gen NX / Civil NX Open
API session: new project -> minimal cantilever-column model (unit, material,
section, node, element, support, load case, self-weight) -> analyze -> read
reaction/displacement/beam-force results back, and sanity-check the reaction
against a hand-calculated expected value.

This is PLAN.md's A1 tool. Unlike scripts/check_drift.py (schema
introspection only) this exercises a real solve and a real result-table
round trip — the same scenario first verified by hand and written up in
docs/live_verification_notes.md (2026-07-15). Re-run this whenever you want
to reconfirm write -> analyze -> read still works end to end on a current
NX build, without re-deriving the whole walk-through by hand.

⚠️ Calls /doc/NEW, which replaces whatever is open in that NX session.
Don't run this against a session with work you care about. The built model
is left open afterward (not saved, not closed) so you can inspect it in the
NX GUI.

⚠️ Corrected 2026-07-26: this used to say /doc/NEW discards the open
document "WITHOUT saving". Not reliably. It can instead raise NX's own
save-changes dialog, and **the whole API session blocks until a human
clicks it** - so the risk is a stall, not only silent data loss. The first
run of the day hit exactly that on a document opened from disk: the dialog
appeared, the session was blocked behind it, and the analysis that ran
after it came back {"message": "MIDAS CIVIL NX Analysis failed."}. The same
script passed immediately afterwards. Later /doc/NEW calls against scratch
documents did not prompt at all, so treat it as possible, not certain, and
don't run this unattended against a session you can't see.

Requires a running MIDAS Gen NX or Civil NX instance with the Open API
connected (see src/midas_nx/README.md Quick Start).

Usage:
    python scripts/live_smoke.py --product gen --save-dir C:/temp
    python scripts/live_smoke.py --product civil --save-dir C:/temp         --out /tmp/smoke_civil.json

--save-dir is a directory ON THE NX MACHINE and is required, because this
script calls /doc/NEW; --no-save-before waives the checkpoint but not the
/doc/NEW. See scripts/harness_save_path.py for why all four destructive
harnesses ask the same way.

Exit code 0 -> every step succeeded and the reaction matches the expected
                self-weight hand-calc within tolerance.
Exit code 1 -> a step failed, or the result didn't match the hand-calc.
Exit code 2 -> couldn't connect / misconfiguration.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness_save_path  # noqa: E402

from midas_nx import doc  # noqa: E402
from midas_nx.client import MidasAPIError, MidasClient  # noqa: E402
from midas_nx.db.boundary import Constraint  # noqa: E402
from midas_nx.db.node_element import Element, Node  # noqa: E402
from midas_nx.db.project import Unit  # noqa: E402
from midas_nx.db.properties.material import Material  # noqa: E402
from midas_nx.db.properties.section import Section  # noqa: E402
from midas_nx.db.static_loads import SelfWeight, StaticLoadCase  # noqa: E402
from midas_nx.post.result_1 import (  # noqa: E402
    get_beam_force_table,
    get_displacement_table,
    get_reaction_table,
)

# 0.6 x 0.6 m C24 concrete column, 3.2 m tall, fixed at the base — matches
# the Gen reproduction in docs/live_verification_notes.md so the expected
# reaction below is a known hand-calc, not a guess.
SECTION_SIZE = 0.6
HEIGHT = 3.2
UNIT_WEIGHT = 24.5  # kN/m^3, normal-weight concrete approximation


def _material_standard(product: str) -> str:
    # Live finding (docs/live_verification_notes.md): "KS01(RC)"/"C24" is
    # confirmed to work on Civil. Try the same code on Gen too rather than
    # guessing a Gen-specific one.
    return "KS01(RC)"


def _find_head_data(response: dict) -> tuple:
    """/post/TABLE's documented response key is the caller's table_name
    (default ""), but docs/live_verification_notes.md found result tables
    actually come back keyed "Result Table" regardless — scan values
    instead of hardcoding either key name."""
    for value in response.values():
        if isinstance(value, dict) and "HEAD" in value and "DATA" in value:
            return value["HEAD"], value["DATA"]
    return None, None


def run(client: MidasClient) -> dict:
    steps = []

    def step(name: str, fn):
        try:
            result = fn()
        except MidasAPIError as exc:
            steps.append({"step": name, "ok": False, "error": str(exc)})
            raise
        # A non-2xx status raises above, but the server also reports some
        # semantic failures as a 200 with an "error" key in the body (see
        # docs/live_verification_notes.md) — treat that as a failed step too.
        if isinstance(result, dict) and "error" in result:
            message = result["error"].get("message") if isinstance(result["error"], dict) else result["error"]
            steps.append({"step": name, "ok": False, "error": message})
            raise MidasAPIError(str(message))
        steps.append({"step": name, "ok": True, "result": result})
        return result

    try:
        step("new_project", lambda: doc.new_project(client=client))
        step("units", lambda: Unit.update({1: {"DIST": "M", "FORCE": "KN"}}, client=client))
        step("material", lambda: Material.create(
            {1: {"TYPE": "CONC", "NAME": "C24",
                 "PARAM": [{"P_TYPE": 1, "STANDARD": _material_standard(client.product.value), "DB": "C24"}]}},
            client=client,
        ))
        step("section", lambda: Section.create(
            {1: {"SECTTYPE": "DBUSER", "SECT_NAME": "Column",
                 "SECT_BEFORE": {"USE_SHEAR_DEFORM": True, "SHAPE": "SB", "DATATYPE": 2,
                                  "SECT_I": {"vSIZE": [SECTION_SIZE, SECTION_SIZE]}}}},
            client=client,
        ))
        step("nodes", lambda: Node.create(
            {1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 0, "Y": 0, "Z": HEIGHT}}, client=client,
        ))
        step("element", lambda: Element.create(
            {1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2]}}, client=client,
        ))
        step("support", lambda: Constraint.create(
            {1: {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}, client=client,
        ))
        step("load_case", lambda: StaticLoadCase.create(
            {1: {"NAME": "DL", "TYPE": "D", "DESC": "Dead Load"}}, client=client,
        ))
        step("self_weight", lambda: SelfWeight.create(
            {1: {"LCNAME": "DL", "FV": [0, 0, -1]}}, client=client,
        ))
        step("analyze", lambda: doc.analyze(client=client))
        reactions = step("reactions", lambda: get_reaction_table(load_case_names=["DL(ST)"], client=client))
        step("displacements", lambda: get_displacement_table(load_case_names=["DL(ST)"], client=client))
        step("beam_forces", lambda: get_beam_force_table(load_case_names=["DL(ST)"], client=client))
    except MidasAPIError:
        return {"product": client.product.value, "steps": steps, "reaction_matches_hand_calc": False}

    expected_fz = round(SECTION_SIZE * SECTION_SIZE * HEIGHT * UNIT_WEIGHT, 3)
    head, data = _find_head_data(reactions)
    actual_fz: Optional[float] = None
    if head and data and "FZ" in head:
        actual_fz = float(data[0][head.index("FZ")])

    within_tolerance = actual_fz is not None and abs(actual_fz - expected_fz) / expected_fz < 0.05

    return {
        "product": client.product.value,
        "steps": steps,
        "expected_reaction_fz_kn": expected_fz,
        "actual_reaction_fz_kn": actual_fz,
        "reaction_matches_hand_calc": within_tolerance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=["gen", "civil"], required=True)
    parser.add_argument("--mapi-key", help="defaults to MIDAS_MAPI_KEY env var")
    parser.add_argument("--base-url", help="defaults to MIDAS_BASE_URL env var")
    parser.add_argument("--out", help="path to write the report JSON (optional)")
    harness_save_path.add_arguments(parser)
    args = parser.parse_args()
    harness_save_path.require(parser, args)

    client = MidasClient(mapi_key=args.mapi_key, base_url=args.base_url, product=args.product)
    try:
        health = client.verify_connection()
    except MidasAPIError as exc:
        print(f"Could not reach the MIDAS NX Open API server: {exc}", file=sys.stderr)
        sys.exit(2)
    if health.get("status") != "connected":
        print(f"Server reachable but not connected: {health}", file=sys.stderr)
        sys.exit(2)

    # Before the /doc/NEW in run(), not after: the point of the checkpoint is
    # to give the operator the open document back if that call turns out to
    # have discarded something, and to keep a save-changes dialog from
    # blocking the session mid-run.
    if not args.no_save_before:
        checkpoint = harness_save_path.checkpoint(
            args.save_dir, "midas-nx-smoke", args.product,
        )
        print(f"Saving the open document to {checkpoint} first...")
        doc.save_as(checkpoint, client=client)

    report = run(client)

    sys.stdout.reconfigure(encoding="utf-8")
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")

    sys.exit(0 if report.get("reaction_matches_hand_calc") else 1)


if __name__ == "__main__":
    main()
