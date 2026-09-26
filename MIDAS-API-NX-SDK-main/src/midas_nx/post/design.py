"""Source: docs/manual/23_POST_Design.md, items 1-10.

Design results use three URI patterns: /post/PM and /post/STEELCODECHECK are
POST-only with an empty "Argument" body (plain functions, like doc.py); the
remaining 8 "design forces" tables share the /post/TABLE endpoint used by
chapters 18-21 (see post/base.py's get_table()).
"""
from __future__ import annotations

from typing import List, Optional

from ..client import MidasClient
from ..client import post_argument as _post
from .base import NodeElemsSelector, TableStyles, TableUnit, get_table


def get_pm_interaction_diagram(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/23_POST_Design.md #1 — /post/PM — P-M Interaction Diagram.

    Takes no arguments; returns the current model's full P-M interaction
    (axial force-moment) curve dataset for RC/SRC columns and members. The
    manual doesn't publish a fixed response HEAD/DATA shape for this one —
    the response keys depend on the active design code configuration.
    """
    return _post("/post/PM", {}, client)


def get_steel_code_check(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/23_POST_Design.md #2 — /post/STEELCODECHECK — Steel Code Check.

    Takes no arguments; returns ``{"vSECT": [...], "vELEM": [...]}`` — each
    entry has SECT/ELEM id, RAT (combined strength ratio), SLN (slenderness
    ratio), DEF (deflection), DEFA (allowable deflection).
    """
    return _post("/post/STEELCODECHECK", {}, client)


# 3. Concrete Design - Beam Design Forces
TABLE_TYPE_BEAM_DESIGN_FORCES = "BEAMDESIGNFORCES"

# 4. Concrete Design - Column Design Forces
TABLE_TYPE_COLUMN_DESIGN_FORCES = "COLUMNDESIGNFORCES"

# 5. Concrete Design - Brace Design Forces
TABLE_TYPE_BRACE_DESIGN_FORCES = "BRACEDESIGNFORCES"

# 6. Concrete Design - Wall Design Forces
TABLE_TYPE_WALL_DESIGN_FORCES = "WALLDESIGNFORCES"

# 7. Steel Design - Steel Member Design Forces
TABLE_TYPE_STEEL_MEMBER_DESIGN_FORCES = "STEELMEMBERDESIGNFORCES"

# 8. SRC Design - SRC Beam Design Forces
TABLE_TYPE_SRC_BEAM_DESIGN_FORCES = "SRCBEAMDESIGNFORCES"

# 9. SRC Design - SRC Column Design Forces
TABLE_TYPE_SRC_COLUMN_DESIGN_FORCES = "SRCCOLUMNDESIGNFORCES"

# 10. Cold Formed Design - Cold Formed Steel Member Design Forces
TABLE_TYPE_COLD_FORMED_STEEL_MEMBER_DESIGN_FORCES = "COLDFORMEDSTEELMEMBERDESIGNFORCES"


def _get_design_forces_table(
    table_type: str,
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    return get_table(
        table_type,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_beam_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #3 — Concrete Design - Beam Design Forces.

    Requires analysis and design to already be complete (see 24_DB_Design.md
    for design-code/member setup). parts: member end selection, e.g.
    ["PartI", "PartJ"].

    ⚠️ Confirmed crashing Gen NX, reproduced twice (once pre-patch during a
    broader ``post/*`` sweep, once 2026-08-07 post-patch on build
    08/06/2026 against a blank ``/doc/NEW`` document): the call hangs, then
    ``verify_connection()`` shows disconnected and every ``/db/*`` call
    404s. Same failure signature as the Column Design Forces crash —
    but that crash was reproduced against a *different* endpoint,
    ``/DESIGN/RC/KDS-41-20-2022/TABLE`` in
    :func:`midas_nx.design.rc_kds.checks.get_column_design_forces_table`,
    which has its own separate ``_post`` call, not this module's
    ``/post/TABLE``. The two only share the ``TABLE_TYPE`` string
    convention, not a code path — treat them as independently-crashing
    siblings, not one shared root cause. **Confirmed NOT reproducing on
    Civil NX** — same-day retest against a real model answered a clean
    ``"there was an error creating utbl (ex PostMode ...)"`` error every
    time, session stayed healthy. Every other
    ``get_*_design_forces_table()`` function in this module shares this
    same ``/post/TABLE`` helper and is presumed equally at risk on Gen
    until independently confirmed.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), same blank
    ``/doc/NEW`` document shape as the confirmed crash above: this time a
    clean ``{"message": ""}`` response, no crash, session stayed healthy.
    A single clean pass does **not** confirm a fix for a
    historically-confirmed crash — could be intermittent/non-deterministic
    rather than fixed; needs an independent second re-test before drawing
    any conclusion.

    That independent second blank-document re-test completed 2026-09-05 on
    Gen NX v2.1 build 09/02/2026: ``{"message": ""}``, followed by a
    successful ``GET /db/NODE``. Civil NX v2.2 on the same build returned its
    established no-result error and also stayed responsive. The old blank-
    document crash no longer reproduces on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_BEAM_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_column_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #4 — Concrete Design - Column Design Forces.

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — the same
    ``TABLE_TYPE`` crashes Gen NX via the sibling
    ``/DESIGN/RC/KDS-41-20-2022/TABLE`` endpoint too. Not
    independently tested via this exact route on Gen; confirmed clean on
    Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass is not independent proof that risk is
    gone — treat as reduced-but-not-cleared until a real-model
    retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the old blank-document repro on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_COLUMN_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_brace_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #5 — Concrete Design - Brace Design Forces.

    Response shape matches Column Design Forces.

    ⚠️ Confirmed crashing Gen NX (2026-08-10, build 08/06/2026, blank
    ``/doc/NEW`` document): no response, then ``verify_connection()``
    shows disconnected and every ``/db/*`` call 404s — same signature as
    :func:`get_beam_design_forces_table`'s independently-confirmed crash.
    Confirmed clean on Civil NX (2026-08-07/2026-08-10 retests).

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), same blank
    ``/doc/NEW`` document shape as the confirmed crash: this time a clean
    ``{"message": ""}`` response, no crash, session stayed healthy. A
    single clean pass does **not** confirm a fix for a
    historically-confirmed crash — could be intermittent/non-deterministic
    rather than fixed; needs an independent second re-test before drawing
    any conclusion.

    That independent second blank-document re-test completed 2026-09-05 on
    Gen NX v2.1 build 09/02/2026: clean empty response and a successful
    liveness GET. Civil NX v2.2 on the same build returned its established
    no-result error and stayed responsive. The old blank-document crash no
    longer reproduces on the current build; a populated, analysed and
    designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_BRACE_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_wall_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    story_names: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #6 — Concrete Design - Wall Design Forces.

    Adds WID (wall id) and Story columns instead of a "Memb" column; no
    PARTS filter documented (uses Part values "Top"/"Bottom" from the wall's
    own geometry instead of member-end selection).

    story_names: restrict to specific story names, e.g. ["1F", "2F"];
    omitting it selects all stories. Added in the 2026-08-06 manual
    update, whose own request example used the key "STORY",
    but the shipped param is "STORY_NAMES", matching ch20/ch21's naming.

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — not independently
    tested on Gen; confirmed clean on Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass against a call that shares this
    module's confirmed-crashing helper is not independent proof the risk
    is gone — treat as reduced-but-not-cleared until a real-model retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the blank-document risk on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return get_table(
        TABLE_TYPE_WALL_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        unit=unit,
        styles=styles,
        components=components,
        story_names=story_names,
        client=client,
    )


def get_steel_member_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #7 — Steel Design - Steel Member Design Forces.

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — not independently
    tested on Gen; confirmed clean on Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass against a call that shares this
    module's confirmed-crashing helper is not independent proof the risk
    is gone — treat as reduced-but-not-cleared until a real-model retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the blank-document risk on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_STEEL_MEMBER_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_src_beam_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #8 — SRC Design - SRC Beam Design Forces.

    Column order differs from RC Beam Design Forces: "My(+)" precedes
    "My(-)" here (RC beam forces list "My(-)" first).

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — not independently
    tested on Gen; confirmed clean on Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass against a call that shares this
    module's confirmed-crashing helper is not independent proof the risk
    is gone — treat as reduced-but-not-cleared until a real-model retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the blank-document risk on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_SRC_BEAM_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_src_column_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #9 — SRC Design - SRC Column Design Forces.

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — not independently
    tested on Gen; confirmed clean on Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass against a call that shares this
    module's confirmed-crashing helper is not independent proof the risk
    is gone — treat as reduced-but-not-cleared until a real-model retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the blank-document risk on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_SRC_COLUMN_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


def get_cold_formed_steel_member_design_forces_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/23_POST_Design.md #10 — Cold Formed Design - Cold Formed Steel Member Design Forces.

    ⚠️ Shares the ``/post/TABLE`` helper with :func:`get_beam_design_forces_table`
    (confirmed crashing Gen NX, clean on Civil NX) — not independently
    tested on Gen; confirmed clean on Civil NX 2026-08-07.

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass against a call that shares this
    module's confirmed-crashing helper is not independent proof the risk
    is gone — treat as reduced-but-not-cleared until a real-model retest.

    Re-tested independently 2026-09-05 on Gen NX v2.1 build 09/02/2026:
    clean empty response and a successful liveness GET. Civil NX v2.2 on the
    same build returned its established no-result error and stayed responsive.
    This clears the blank-document risk on the current build; a populated,
    analysed and designed-model path was not re-tested.
    """
    return _get_design_forces_table(
        TABLE_TYPE_COLD_FORMED_STEEL_MEMBER_DESIGN_FORCES,
        table_name,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )
