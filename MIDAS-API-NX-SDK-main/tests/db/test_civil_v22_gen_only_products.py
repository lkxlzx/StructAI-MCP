"""21 endpoints confirmed Gen NX only after the 2026-07-29 Civil v2.2 sweep.

Two independent sessions against the same day's freshly patched builds — this
SDK's own `scripts/live_readonly_sweep.py --product civil` and a separately
run validation sweep (report removed from `docs/` 2026-09-17; git history at
`fa1332b`) from a different machine/session
— landed on the identical 20 endpoints: route-level 404 (including
`/info/db/...` schema introspection) under Civil NX, answering under Gen NX.
A same-day live re-check against both open sessions reproduced all 20 again
and additionally confirmed a 21st, `/db/REBC` (POST-only; `/info` is the only
probe available), pending as a candidate until that second confirmation.
See `db/base.py`'s `GEN_ONLY` docstring and `docs/live_verification_notes.md`
for the full evidence.

Unlike Hyper-S's `-M1` suffix, these endpoints share no naming convention, so
the family is hard-coded here rather than discovered by pattern.
"""
import pytest

from midas_nx.db.base import GEN_ONLY
from midas_nx.db.boundary import (
    DiaphragmDisconnect,
    SeismicDeviceHystereticIsolator,
    SeismicDeviceIsolator,
)
from midas_nx.db.design import BeamRebar, BraceRebar, ColumnRebar, WallRebar
from midas_nx.db.project import Story
from midas_nx.db.static_loads import (
    SoilProperty,
    StaticEarthPressure,
    StaticSeismicLoad,
    StaticWindLoad,
)
from midas_nx.design.rc_kds.rebar import (
    ModifyBeamRebarData,
    ModifyBraceRebarData,
    ModifyColumnRebarData,
    ModifyWallRebarData,
    TorsionReductionFactor,
)
from midas_nx.design.rc_kds.setup import (
    ModifyConcreteMaterial,
)
from midas_nx.design.rc_kds.setup import (
    UndergroundLoadCombinationType as RcUndergroundLoadCombinationType,
)
from midas_nx.design.src_aiksrc2k import SrcModifyMaterial
from midas_nx.design.steel_kds import (
    UndergroundLoadCombinationType as SteelUndergroundLoadCombinationType,
)

GEN_ONLY_CLASSES = [
    SoilProperty,
    StaticEarthPressure,
    StaticWindLoad,
    StaticSeismicLoad,
    SeismicDeviceHystereticIsolator,
    SeismicDeviceIsolator,
    DiaphragmDisconnect,
    Story,
    BeamRebar,
    BraceRebar,
    ColumnRebar,
    WallRebar,
    TorsionReductionFactor,
    ModifyBeamRebarData,
    ModifyBraceRebarData,
    ModifyColumnRebarData,
    ModifyWallRebarData,
    RcUndergroundLoadCombinationType,
    ModifyConcreteMaterial,
    SrcModifyMaterial,
    SteelUndergroundLoadCombinationType,
]


def test_the_gen_only_family_is_the_expected_size():
    assert len(GEN_ONLY_CLASSES) == 21, [c.ENDPOINT for c in GEN_ONLY_CLASSES]
    assert len({c.ENDPOINT for c in GEN_ONLY_CLASSES}) == 21


@pytest.mark.parametrize("cls", GEN_ONLY_CLASSES, ids=lambda c: c.ENDPOINT)
def test_endpoint_is_gen_only(cls):
    assert cls.PRODUCTS == GEN_ONLY == frozenset({"gen"})


def test_civil_client_refuses_a_gen_only_resource_before_any_http_call(civil_client):
    from midas_nx.client import ProductMismatchError

    with pytest.raises(ProductMismatchError):
        Story.get(client=civil_client)
