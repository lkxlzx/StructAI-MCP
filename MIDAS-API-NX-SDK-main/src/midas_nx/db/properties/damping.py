"""Source: docs/manual/04_DB_Properties.md, item 30 (/db/GRDP)."""
from __future__ import annotations

from typing import List, TypedDict

from ..base import DbResource


class GroupDampingItem(TypedDict, total=False):
    GROUP_TYPE: str  # "MATERIAL" / "STRUCTURE" / "BOUNDARY", required
    GROUP_NAME: str  # Damping Ratio Name, required
    DAMPING_RATIO: float  # required


class GroupDampingRayleighItem(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #30 — /db/GRDP "GROUP_DAMPING_ITEMS[]"
    entry (per-group override of the Element Mass & Stiffness Proportional
    / Rayleigh-damping "..._DEFAULT" fields on GroupDampingPayload).

    Added 2026-08-27 — see GroupDampingPayload's docstring. Same field
    meanings as the top-level "..._DEFAULT" fields, minus the suffix, plus
    the GROUP_TYPE/GROUP_NAME pair that picks which group this override
    applies to (same 3-way rule as GroupDampingItem above).
    """

    GROUP_TYPE: str  # "MATERIAL" / "STRUCTURE" / "BOUNDARY", required
    GROUP_NAME: str  # Material ID or Structure/Boundary group name, required
    STIFF_COEF: float  # Stiffness Proportional value, required
    OPT_STIFF_PROP: bool  # Stiffness Proportional option, default false, optional
    MASS_COEF: float  # Mass Proportional value, required
    OPT_MASS_PROP: bool  # Mass Proportional option, default false, optional
    DIRECT_CALC_MODE: int  # Direct=0, Calculate from Modal Damping=1; required
    FREQ_PERIOD_MODE: int  # Frequency=0, Period=1; required
    FREQ_MODE_1: float  # Frequency Mode 1, required
    FREQ_MODE_2: float  # Frequency Mode 2, required
    PERIOD_MODE_1: float  # Period Mode 1, required
    PERIOD_MODE_2: float  # Period Mode 2, required
    DAMPING_RATIO_MODE: int  # required, meaning not further specified by the manual (see DAMPING_RATIO_MODE_1/2)
    DAMPING_RATIO_MODE_1: float  # Damping Ratio Mode 1, required
    DAMPING_RATIO_MODE_2: float  # Damping Ratio Mode 2, required


class GroupDampingPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #30 — /db/GRDP Specifications table.

    ⚠️ 2026-08-27 re-verified against the manual (article id
    `35944577940633`): this endpoint covers two independent damping-ratio
    schemes and the previous version of this TypedDict only had part of
    one. Strain Energy Proportional (bExistStrain/STRAIN_GROUP_ITEMS/
    OPT_CALC_WHEN_USED) was already typed but missing its two priority
    fields (STRAIN_GROUP_PRIORITY/STRAIN_VALUE_PRIORITY). The entire
    Element Mass & Stiffness Proportional (Rayleigh damping) scheme --
    bExistElement plus 17 more top-level fields, the per-group override
    array GROUP_DAMPING_ITEMS (13 sub-fields each, see
    GroupDampingRayleighItem), and its own two priority fields -- was
    missing outright. The four "..._DEFAULT" coefficient/option fields this
    class already carried as `Any` (STIFF_COEF_DEFAULT/MASS_COEF_DEFAULT/
    OPT_MASS_PROP_DEFAULT/OPT_STIFF_PROP_DEFAULT) are now precisely typed
    and marked per the manual's own requiredness column instead. Both
    schemes can be active at once (bExistStrain and bExistElement are
    independent flags) -- the manual's own worked example sets both true
    simultaneously. Manual-sourced, not independently live-tested.
    """

    bExistStrain: bool  # Strain Energy Proportional in use, required
    STRAIN_GROUP_ITEMS: List[GroupDampingItem]  # required
    OPT_CALC_WHEN_USED: bool  # Calculate Only When Used, required
    STRAIN_GROUP_PRIORITY: int  # Priority: Material Data vs Structure Group. Material=0, Structure Group=1; required
    STRAIN_VALUE_PRIORITY: int  # Priority between Structure Groups. Smallest=0, Largest=1; required
    bExistElement: bool  # Element Mass & Stiffness Proportional (Rayleigh damping) in use, required
    OPT_MASS_PROP_DEFAULT: bool  # (unassigned elements) Mass Proportional option, default false, optional
    OPT_STIFF_PROP_DEFAULT: bool  # (unassigned elements) Stiffness Proportional option, default false, optional
    DIRECT_CALC_MODE_DEFAULT: int  # Direct=0, Calculate from Modal Damping=1; required
    MASS_COEF_DEFAULT: float  # Mass Proportional value, required
    STIFF_COEF_DEFAULT: float  # Stiffness Proportional value, required
    FREQ_PERIOD_MODE_DEFAULT: int  # Coefficient basis: Frequency=0, Period=1; required
    FREQ_MODE_1_DEFAULT: float  # Frequency Mode 1, required
    FREQ_MODE_2_DEFAULT: float  # Frequency Mode 2, required
    PERIOD_MODE_1_DEFAULT: float  # Period Mode 1, required
    PERIOD_MODE_2_DEFAULT: float  # Period Mode 2, required
    DAMPING_MODE_1_DEFAULT: float  # Damping Ratio Mode 1, required
    DAMPING_MODE_2_DEFAULT: float  # Damping Ratio Mode 2, required
    GROUP_DAMPING_ITEMS: List[GroupDampingRayleighItem]  # Per-group Rayleigh damping override, required
    ELEM_GROUP_PRIORITY: int  # Priority: Material Data vs Structure Group (element side), required
    ELEM_VALUE_PRIORITY: int  # Priority between Structure Groups (element side), required


class GroupDamping(DbResource):
    ENDPOINT = "/db/GRDP"
    NAME = "Group Damping"
    PRODUCTS = frozenset({"gen", "civil"})
