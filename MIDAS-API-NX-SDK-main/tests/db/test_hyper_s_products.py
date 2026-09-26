"""Hyper-S (`-M1`) endpoints are Civil NX only.

Hyper-S is the solver MIDASIT introduced with Civil NX. The SDK originally
declared these endpoints as gen+civil, which live testing on 2026-07-26
contradicted: all 13 answered under Civil NX 2026 (v2.1) and all 13 returned
404 under Gen NX 2026 (v2.1). This guards the whole family at once, so a new
`-M1` endpoint can't quietly land with the wrong PRODUCTS.

2026-07-29: the remaining 8 undocumented `-M1` stubs (STYP-M1, MATL-M1,
IMFM-M1, EPMT-M1, IEHG-{BEAM,TRUSS,GL,PSS}-M1) were implemented from `GET
/info/db/...` server introspection instead of a manual Specifications table
(none exists for these), resolving the v1.0.0 gate's Hyper-S-stub item. Total
is now 21, not 13.

If MIDASIT brings Hyper-S to Gen NX, widen `HYPER_S_ONLY` in db/base.py and
this test follows automatically - see that constant's docstring.
"""
import importlib
import pkgutil

import pytest

import midas_nx
from midas_nx.db.base import HYPER_S_ONLY, DbResource


def _all_resources():
    for _, name, _ in pkgutil.walk_packages(midas_nx.__path__, prefix="midas_nx."):
        importlib.import_module(name)
    seen, stack, found = set(), list(DbResource.__subclasses__()), []
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        if "ENDPOINT" in cls.__dict__:
            found.append(cls)
    return found


HYPER_S = sorted(
    (cls for cls in _all_resources() if cls.ENDPOINT.endswith("-M1")),
    key=lambda c: c.ENDPOINT,
)


def test_the_hyper_s_family_is_discoverable():
    assert len(HYPER_S) == 21, [c.ENDPOINT for c in HYPER_S]


@pytest.mark.parametrize("cls", HYPER_S, ids=lambda c: c.ENDPOINT)
def test_hyper_s_endpoint_is_civil_only(cls):
    assert cls.PRODUCTS == HYPER_S_ONLY == frozenset({"civil"})


def test_gen_client_refuses_a_hyper_s_resource_before_any_http_call(gen_client):
    from midas_nx.client import ProductMismatchError
    from midas_nx.db.analysis_control import MainControlDataHyperS

    with pytest.raises(ProductMismatchError):
        MainControlDataHyperS.get(client=gen_client)
