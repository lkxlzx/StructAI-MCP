"""The npm live harness must consume the current Python case fixture."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "schema" / "live-cases.json"


@pytest.mark.parametrize(
    "endpoint,code",
    [("/db/LLANch", "CHINA"), ("/db/SLANch", "CHINA"),
     ("/db/LLANid", "INDIA"), ("/db/LLANtr", "TRANS"),
     ("/db/LLANop", "KSCE-LSD15"), ("/db/SLAN", "KSCE-LSD15"),
     ("/db/SLANop", "KSCE-LSD15")],
)
def test_manual_lane_fixture_keeps_its_own_code_and_model_references(endpoint, code) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = next(c for c in fixture["cases"] if c["endpoint"] == endpoint)
    seed = fixture["seeds"][f"lane_code_{code}"]
    assert seed["records"]["1"]["CODE"] == code
    assert case["setup"] == [{"seed": f"lane_code_{code}"}]
    if endpoint in {"/db/LLANch", "/db/LLANid"}:
        assert "LL_NAME" not in case["createPayload"]
        assert case["createPayload"]["COMMON"]["LL_NAME"]
    if endpoint.startswith("/db/SLAN"):
        payload = case["createPayload"]
        items = payload.get("ITEMS", payload.get("LANE_ITEMS"))
        assert {p.get("NODE_KEY", p.get("NODE")) for p in items} <= {5, 6, 7, 8}


@pytest.mark.parametrize(
    "endpoint,seed_names",
    [
        ("/db/TDMT", ["tdmt_seed"]),
        ("/db/TDME", ["tdme_seed"]),
        ("/db/GSTP", ["spring_types"]),
        ("/db/THFC", ["thfc_seed", "thfc_force_seed"]),
        ("/db/SPLC", ["spfc_seed"]),
    ],
    ids=["creep-sequential-ids", "strength-sequential-id", "spring-sequential-ids",
         "time-history-two-functions", "spectrum-function-reference"],
)
def test_shared_fixture_includes_required_tier_seeds(endpoint, seed_names) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = [case for case in fixture["cases"] if case["endpoint"] == endpoint]
    assert cases
    for case in cases:
        assert case["setup"] == [{"seed": name} for name in seed_names]
        assert all(name in case["needs"] for name in seed_names)
        for name in seed_names:
            assert fixture["seeds"][name]["records"]


def test_live_case_fixture_matches_python_source() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/live_crud_check.py", "--check-cases"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_live_case_fixture_uses_shared_base_node_for_confirmed_nmas() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    nmas = next(case for case in cases if case["endpoint"] == "/db/NMAS")
    node_step = next(step for step in fixture["baseModel"] if step["endpoint"] == "/db/NODE")

    assert nmas["confirmed"] is True
    assert nmas["createPayload"] == {"mX": 1.0, "mY": 1.0, "mZ": 1.0}
    assert "3" in node_step["records"]
    assert nmas["setup"] == []


def test_live_case_fixture_does_not_reseed_base_static_load_cases() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    stld = next(case for case in fixture["cases"] if case["endpoint"] == "/db/STLD")

    assert fixture["version"] == 6
    assert fixture["seeds"]["static_load_cases"] == {
        "endpoint": "/db/STLD",
        "records": {
            "1": {"NAME": "DL", "TYPE": "D", "DESC": "Dead Load"},
            "2": {"NAME": "LC_SCRATCH", "TYPE": "L", "DESC": "crud fixture"},
        },
    }
    assert stld["setup"] == []


def test_extras15_fixture_keeps_manual_dependencies_and_product_fields() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = [case for case in fixture["cases"] if case["tier"] == "extras15"]

    assert {case["endpoint"] for case in cases} == {
        "/db/IEPI", "/db/EXLD", "/db/PRST", "/db/POLC", "/db/MATD",
        "/db/IEHC", "/db/POLC-M1",
    }
    assert all(case["confirmed"] is True for case in cases)

    seed = fixture["seeds"]["prestress_load_cases"]
    assert seed["endpoint"] == "/db/STLD"
    assert seed["allowRenumbering"] is True
    assert {record["NAME"] for record in seed["records"].values()} == {
        "PS15_SEED", "PS16_SEED",
    }
    for endpoint in ("/db/EXLD", "/db/PRST"):
        case = next(case for case in cases if case["endpoint"] == endpoint)
        assert case["setup"] == [{"seed": "prestress_load_cases"}]

    polc = {case["products"][0]: case for case in cases if case["endpoint"] == "/db/POLC"}
    gen_only = {
        "bLIMITDEFORMANGLE", "LIMITDEFORMANGLE", "bDRIFTMAX",
        "bDRIFTCENTER", "bDRIFTAVER",
    }
    assert gen_only <= set(polc["gen"]["createPayload"])
    assert gen_only.isdisjoint(polc["civil"]["createPayload"])

    iehc = {case["products"][0]: case for case in cases if case["endpoint"] == "/db/IEHC"}
    wall_fields = {
        "WallConsOut", "WallDivNumZ", "WallDivNumY", "dR", "WAreaSize",
        "OPT_ConsiderRebarAreaWall", "WAreaSizeCover", "WallDivNumZCover",
        "WallDivNumYCover",
    }
    assert wall_fields <= set(iehc["gen"]["createPayload"])
    assert wall_fields.isdisjoint(iehc["civil"]["createPayload"])
    assert {case["createPayload"]["BEAM_LOC"] for case in iehc.values()} == {1}
    assert {case["updatePayload"]["BEAM_LOC"] for case in iehc.values()} == {2}

    matd = next(case for case in cases if case["endpoint"] == "/db/MATD")
    assert matd["expected"] == {"created": None, "updated": 500000}
    assert matd["updatePayload"]["MAINREBAR_B_FY"] == 500000

    polc_m1 = next(case for case in cases if case["endpoint"] == "/db/POLC-M1")
    assert polc_m1["products"] == ["civil"]
    assert polc_m1["methods"] == ["DELETE", "GET", "POST", "PUT"]
    assert polc_m1["createPayload"]["NLTYPE"] == "PDELTA"
    assert polc_m1["updatePayload"]["NLTYPE"] == "NONE"
    assert polc_m1["updatePayload"]["LOADPATTERNTYPE"] == "ACC"


def test_unconfirmed_fixture_repairs_follow_the_vendored_manual_examples() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    by_endpoint = {case["endpoint"]: case for case in cases}

    grdp = by_endpoint["/db/GRDP"]["createPayload"]
    assert grdp["DIRECT_CALC_MODE_DEFAULT"] == 1
    assert grdp["DAMPING_MODE_1_DEFAULT"] == 0.06
    assert grdp["GROUP_DAMPING_ITEMS"][0]["FREQ_MODE_2"] == 0.6
    assert grdp["STRAIN_GROUP_ITEMS"][0]["DAMPING_RATIO"] == 0.02
    assert grdp["STRAIN_GROUP_PRIORITY"] == 0
    assert by_endpoint["/db/GRDP"]["updatePayload"]["FREQ_MODE_1_DEFAULT"] == 0.5

    tdmf = by_endpoint["/db/TDMF"]["createPayload"]
    assert tdmf["FTYPE"] == "CREEP"
    assert tdmf["CTYPE"] == "CC"
    assert "RELAXATION" not in tdmf

    nlnk_m1 = by_endpoint["/db/NLNK-M1"]["createPayload"]
    assert nlnk_m1["REF_SYSTEM"] == 0
    assert nlnk_m1["BETA_ANGLE"] == 0
    assert "INPUT_METHOD" not in nlnk_m1

    mvct = by_endpoint["/db/MVCT"]
    assert mvct["setup"] == [{"seed": "lane_code_AASHTO LRFD"}]


def test_extras16_epmt_fixture_is_the_manual_von_mises_example() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    epmt_cases = [case for case in cases if case["endpoint"] == "/db/EPMT"]
    assert [case["products"] for case in epmt_cases] == [["gen"], ["civil"]]
    assert [case["confirmed"] for case in epmt_cases] == [True, False]
    epmt = epmt_cases[0]

    assert epmt["createPayload"] == {
        "NAME": "Steel_VonMises",
        "MODEL_TYPE": "VM",
        "VMISES": {
            "INIT_YIELD_STRESS": 235000,
            "OPT_HARDENING": 0,
            "HARDENING_TYPE": "ISO",
            "HARDENING_COEF": 21000,
        },
    }
    assert epmt["updatePayload"]["NAME"] == "Steel_VM"


def test_extras16_fimp_fixture_is_the_manual_kent_park_example() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    fimp = next(case for case in cases if case["endpoint"] == "/db/FIMP")

    assert fimp["id"] == 3
    assert fimp["createPayload"] == {
        "NAME": "Conc_Kent&Park",
        "MATL_TYPE": "CONC",
        "HYS_MODEL": "KPM",
        "CONC": {"KENPAR": {
            "FC": 30000,
            "PARTIAL_FACT": 1.0,
            "K": 1.0,
            "EC0": 0.002,
            "EC1_METHOD": 1,
            "EC1": 0.0035,
            "Z": 100,
            "ECU": 0.003,
            "STRENGTH_AFTER": 0,
        }},
    }
    assert fimp["updatePayload"]["NAME"] == "Concrete_KP"
    assert fimp["updatePayload"]["CONC"]["KENPAR"]["FC"] == 24000


def test_extras17_pushover_fixtures_use_documented_common_branches() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    extras17 = [case for case in cases if case["tier"] == "extras17"]
    assert {case["endpoint"] for case in extras17} == {
        "/db/PHGE", "/db/POGD", "/db/POGD-M1",
    }
    # 2026-09-19, both SDKs: POGD passed on Civil and answered "Wrong Field"
    # on Gen, so it is one case per product; POGD-M1 passed; PHGE did not.
    confirmed = {(case["endpoint"], tuple(case["products"])): case["confirmed"]
                 for case in extras17}
    assert confirmed == {
        ("/db/PHGE", ("gen", "civil")): False,
        ("/db/POGD", ("gen",)): False,
        ("/db/POGD", ("civil",)): True,
        ("/db/POGD-M1", ("civil",)): True,
    }

    phge = next(case for case in extras17 if case["endpoint"] == "/db/PHGE")
    assert phge["createPayload"] == {
        "ID": 1, "TYPE": "BEAM", "HINGE_TYPE": "Myz_15", "FIBER_KEY": 0,
    }
    assert phge["updatePayload"]["ID"] == 2

    pogd = next(case for case in extras17 if case["endpoint"] == "/db/POGD"
                and case["products"] == ["civil"])
    assert pogd["createPayload"]["NONL_OPT"]["MAXITER"] == 10
    assert pogd["updatePayload"]["NONL_OPT"]["MAXITER"] == 11
    assert "PHOP_OPT" not in pogd["createPayload"]

    pogd_m1 = next(case for case in extras17 if case["endpoint"] == "/db/POGD-M1")
    assert pogd_m1["products"] == ["civil"]
    assert pogd_m1["methods"] == ["DELETE", "GET", "PUT"]
    assert pogd_m1["createPayload"] == {}
    assert pogd_m1["updatePayload"]["ITER_CTRL"]["MAX_ITER"] == 31


def test_extras18_tendon_chain_seeds_each_step_it_depends_on() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    extras18 = [case for case in fixture["cases"] if case["tier"] == "extras18"]
    assert {case["endpoint"] for case in extras18} == {
        "/db/TDNT", "/db/TDNA", "/db/TDPL",
    }
    # 2026-09-19, both SDKs, both products: TDNT passed; TDNA answered an
    # unregistered IS_DB_TDNA_NOTENSIONCALC error, which blocks TDPL.
    assert {case["endpoint"]: case["confirmed"] for case in extras18} == {
        "/db/TDNT": True, "/db/TDNA": False, "/db/TDPL": False,
    }

    # Each case takes an id its own seed does not own, so a case deleting
    # itself cannot take a later case's prerequisite with it.
    ids = {case["endpoint"]: case["id"] for case in extras18}
    assert ids == {"/db/TDNT": 2, "/db/TDNA": 2, "/db/TDPL": 1}
    assert list(fixture["seeds"]["tdnt_seed"]["records"]) == ["1"]
    assert list(fixture["seeds"]["tdna_seed"]["records"]) == ["1"]
    # TDNA's TDN_GRUP 1 must exist: the product answers "Tendon Group 1
    # does not exist." without it. The seed is extras1's confirmed TDGR shape.
    assert fixture["seeds"]["tdgr_seed"] == {
        "endpoint": "/db/TDGR", "records": {"1": {"NAME": "TDGR_SEED"}},
    }

    # /db/STLD renumbers, so the load-case seed has to say so or the npm
    # harness reads the server's own id as a mismatch.
    assert fixture["seeds"]["tdpl_prestress_case"]["allowRenumbering"] is True
    assert fixture["seeds"]["tdpl_prestress_case"]["endpoint"] == "/db/STLD"

    tdnt = next(case for case in extras18 if case["endpoint"] == "/db/TDNT")
    assert tdnt["needs"] == []
    # The manual's own KSCE LSD15 example omits FT, FPK and TDMFNAME, which
    # its relaxation-code table scopes to other RM values.
    assert tdnt["createPayload"]["RM"] == 6
    assert {"FT", "FPK", "TDMFNAME"}.isdisjoint(tdnt["createPayload"])
    assert tdnt["expected"] == {"created": 0.006, "updated": 0.012}

    tdna = next(case for case in extras18 if case["endpoint"] == "/db/TDNA")
    assert tdna["needs"] == ["tdnt_seed", "tdgr_seed"]
    # Remapped from the example's elements 101-105 onto the base model's beams.
    assert tdna["createPayload"]["ELEM"] == [1, 2, 3]
    assert tdna["createPayload"]["INS_ELEM"] == 1
    assert tdna["createPayload"]["CURVE"] == "SPLINE"
    assert "RADIUS" not in json.dumps(tdna["createPayload"])

    tdpl = next(case for case in extras18 if case["endpoint"] == "/db/TDPL")
    assert tdpl["needs"] == [
        "tdpl_prestress_case", "tdnt_seed", "tdgr_seed", "tdna_seed",
    ]
    item = tdpl["createPayload"]["ITEMS"][0]
    assert item["LCNAME"] == "PS18_SEED"
    assert item["TENDON_NAME"] == "TDNA_SEED"
    assert tdpl["updatePayload"]["ITEMS"][0]["END"] == 1200000


def test_extras19_ptns_seeds_the_manual_prerequisite_chain() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    extras19 = [case for case in fixture["cases"] if case["tier"] == "extras19"]
    assert len(extras19) == 1

    ptns = extras19[0]
    assert ptns["endpoint"] == "/db/PTNS"
    assert ptns["id"] == 5
    assert ptns["products"] == ["gen", "civil"]
    # 2026-09-20, Build 09/15/2026: npm and Python passed on Gen and Civil.
    assert ptns["confirmed"] is True
    assert ptns["needs"] == [
        "ptns_nodes", "ptns_truss", "ptns_load_case",
        "ptns_external_load_case",
    ]

    # Every prerequisite is this tier's own. A seed shared with another tier
    # is POSTed twice whenever both are selected, because the runner runs a
    # selected tier's whole seed list, and nodes 21-22 must stay unattached
    # for ELNK/RIGD/MCON.
    assert fixture["seeds"]["ptns_nodes"]["endpoint"] == "/db/NODE"
    assert set(fixture["seeds"]["ptns_nodes"]["records"]) == {"51", "52"}
    truss = fixture["seeds"]["ptns_truss"]
    assert truss == {
        "endpoint": "/db/ELEM",
        "records": {
            "5": {
                "TYPE": "TRUSS", "MATL": 1, "SECT": 1,
                "NODE": [51, 52], "ANGLE": 0,
            },
        },
    }
    load_case = fixture["seeds"]["ptns_load_case"]
    assert load_case["endpoint"] == "/db/STLD"
    assert load_case["records"]["19"]["NAME"] == "PS19_SEED"
    assert load_case["allowRenumbering"] is True
    assert fixture["seeds"]["ptns_external_load_case"] == {
        "endpoint": "/db/EXLD",
        "records": {"1": {"LCNAME_ITEM": ["PS19_SEED"]}},
    }

    item = ptns["createPayload"]["ITEMS"][0]
    assert item == {
        "ID": 1, "LCNAME": "PS19_SEED", "GROUP_NAME": "", "TENSION": 130,
    }
    assert ptns["updatePayload"]["ITEMS"][0]["TENSION"] == 260
    assert ptns["expected"] == {"created": 130, "updated": 260}


def test_moving_country_cases_build_the_vehicle_they_name_and_prove_the_put() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_endpoint = {case["endpoint"]: case for case in fixture["cases"]}

    # Each sub-load names a vehicle; before 2026-09-19 no case built one, and
    # MVLDch/MVLDid failed on it. India's name is the one ch08's own General
    # Load Python example pairs with its section 10 Class A vehicle.
    for endpoint, code, key, name in (
        ("/db/MVLDch", "CHINA", "VEHICLE_CLASS", "CN_UD_Lane1"),
        ("/db/MVLDid", "INDIA", "VEHICLE_CLASS_1", "IN(IRC6)_ClassA"),
    ):
        case = by_endpoint[endpoint]
        seed = f"moving_case_vehicle_{code}"
        assert case["needs"][-1] == seed
        assert fixture["seeds"][seed]["endpoint"] == "/db/MVHL"
        assert fixture["seeds"][seed]["records"]["1"]["VEHICLE_LOAD_NAME"] == name
        assert {item[key] for item in case["createPayload"]["SUB_LOAD_ITEMS"]} == {name}
        assert case["products"] == ["civil"] and case["confirmed"] is True

    # A country case whose update equalled its create could not fail; the
    # PUT now changes DESC alone, as /db/STLD's confirmed case does.
    for endpoint in ("/db/MVLDch", "/db/MVLDid", "/db/MVLDeu", "/db/MVLDpl"):
        case = by_endpoint[endpoint]
        assert case["expected"] == {"created": "", "updated": "crud updated"}
        diff = {k for k in case["createPayload"]
                if case["createPayload"][k] != case["updatePayload"][k]}
        assert diff == {"DESC"}, (endpoint, diff)


def test_fbld_seeds_are_marked_as_renumbering() -> None:
    # /db/FBLD renumbers to the next free id (live, 2026-08-16). Unmarked,
    # fbld7_seed's id 90 reads as missing to the npm harness, which then
    # blocks /db/FBLA instead of testing it - while Python, which does not
    # verify seed ids, reaches FBLA. The two SDKs tested different things
    # until 2026-09-19.
    # extras1's fbld_seed asks for id 1 in an empty table, which is the next
    # free id, so it needs no flag and a confirmed case proves it; this is
    # about a seed that asks for an id the product will not give it.
    seeds = json.loads(FIXTURE.read_text(encoding="utf-8"))["seeds"]
    assert seeds["fbld7_seed"]["endpoint"] == "/db/FBLD"
    assert list(seeds["fbld7_seed"]["records"]) == ["90"]
    assert seeds["fbld7_seed"]["allowRenumbering"] is True


def test_live_case_fixture_does_not_reseed_base_skew_node() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    skew = next(case for case in fixture["cases"] if case["endpoint"] == "/db/SKEW")

    assert "skew_node" not in fixture["seeds"]
    assert skew["setup"] == []


def test_live_case_fixture_carries_design_element_setup() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    element_cases = [
        next(case for case in fixture["cases"] if case["endpoint"] == endpoint)
        for endpoint in ("/db/LENG", "/db/LTSR", "/db/MBTP")
    ]

    for case in element_cases:
        assert case["id"] == 2
        assert case["setup"] == [
            {"seed": "ltsr_material"},
            {"seed": "ltsr_section"},
            {"seed": "ltsr_nodes"},
            {"seed": "ltsr_beam"},
        ]
    assert fixture["seeds"]["ltsr_beam"] == {
        "endpoint": "/db/ELEM",
        "replaceExisting": True,
        "records": {"2": {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [2, 3]}},
    }
    assert fixture["seeds"]["ltsr_nodes"]["replaceExisting"] is True


def test_live_case_fixture_carries_design_member_setup() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    memb = next(case for case in fixture["cases"] if case["endpoint"] == "/db/MEMB")

    assert memb["setup"] == [
        {"seed": "ltsr_material"},
        {"seed": "ltsr_section"},
        {"seed": "ltsr_nodes"},
        {"seed": "ltsr_beam"},
        {"seed": "member_node"},
        {"seed": "member_beam"},
    ]
    assert fixture["seeds"]["member_beam"] == {
        "endpoint": "/db/ELEM",
        "replaceExisting": True,
        "records": {"3": {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [3, 4]}},
    }
    assert fixture["seeds"]["member_node"]["replaceExisting"] is True


def test_live_case_fixture_carries_wall_mark_plate_setup() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    wmak = next(case for case in fixture["cases"] if case["endpoint"] == "/db/WMAK")

    assert wmak["setup"] == [
        {"seed": "ltsr_material"},
        {"seed": "wmak_thickness"},
        {"seed": "wmak_nodes"},
        {"seed": "wmak_plate"},
    ]
    assert fixture["seeds"]["wmak_plate"] == {
        "endpoint": "/db/ELEM",
        "replaceExisting": True,
        "records": {
            "4": {
                "TYPE": "PLATE", "MATL": 1, "SECT": 1,
                "NODE": [1, 2, 4, 3], "ANGLE": 0, "STYPE": 1,
            },
        },
    }
    assert fixture["seeds"]["wmak_nodes"]["replaceExisting"] is True


def test_live_case_fixture_carries_manual_sdis_sld_shape() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    sdis = next(case for case in cases if case["endpoint"] == "/db/SDIS")
    payload = sdis["createPayload"]

    assert payload["SDIS_DEV_TYPE"] == "SLD"
    assert payload["SB"] == {
        "AS": 0.05,
        "K0": 100000,
        "QD": 2,
        "Pi_VALUE": 0,
        "MU0": 0.05,
    }
    assert sdis["confirmed"] is True


def test_live_case_fixture_carries_manual_sdst_bl2_shape() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    sdst = next(case for case in cases if case["endpoint"] == "/db/SDST")

    assert {
        key: sdst["createPayload"][key]
        for key in ("K0", "P1", "ALPHA1", "KB", "BL2")
    } == {
        "K0": 1000,
        "P1": 100,
        "ALPHA1": 0.2,
        "KB": 2000,
        "BL2": {"BETA": 0},
    }
    assert sdst["confirmed"] is True


def test_live_case_fixture_carries_complete_manual_splc_and_thms_shapes() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    splc = [case for case in cases if case["endpoint"] == "/db/SPLC"]
    thms = next(case for case in cases if case["endpoint"] == "/db/THMS")

    assert all(case["confirmed"] is True for case in splc)
    assert splc[0]["createPayload"]["aUSEMODE"] == [
        {"bUSE": True, "MSFACTOR": 1},
        {"bUSE": True, "MSFACTOR": 1},
        {"bUSE": True, "MSFACTOR": 1},
    ]
    assert thms["confirmed"] is True
    assert thms["createPayload"]["ITEMS"][0] == {
        "ID": 1, "LCNAME": "THIS_SEED", "ANGLE": 0, "FUNCX": "THFC_SEED",
        "SCALEX": 1.0, "ATIMEX": 0, "FUNCY": "THFC_SEED", "SCALEY": 1.0,
        "ATIMEY": 0, "FUNCZ": "THFC_SEED", "SCALEZ": 0.667, "ATIMEZ": 0,
    }


def test_live_case_fixture_marks_reconfirmed_plane_load_type() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    pnld = next(case for case in cases if case["endpoint"] == "/db/PNLD")

    assert pnld["confirmed"] is True
    assert pnld["id"] == 2
    # This used to assert an empty setup, which recorded the old emitter's
    # behaviour rather than the case's: /db/PNLD declares pnld_seed and the
    # Python runner has always built it. The npm harness gets it too now.
    assert pnld["needs"] == ["pnld_seed"]
    assert pnld["setup"] == [{"seed": "pnld_seed"}]
    # Live confirms the product ignores requested key 90 and assigns key 1;
    # npm must verify the preserved NAME rather than treating that as failure.
    assert fixture["seeds"]["pnld_seed"]["allowRenumbering"] is True


def test_live_case_fixture_uses_complete_manual_seismic_damper_examples() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    sdvi = next(case for case in cases if case["endpoint"] == "/db/SDVI")
    sdve = next(case for case in cases if case["endpoint"] == "/db/SDVE")

    assert sdvi["createPayload"]["INPUT_TYPE_EXFN"] == 0
    assert sdvi["confirmed"] is True
    assert set(sdvi["createPayload"]["ITEM"][0]) == {
        "OPT_DOF", "CE", "P1", "C1", "ALPHA1", "K0", "EXFN_PY",
        "EXFN_VY", "EXFN_DE", "EXFN_DC", "OPT_EXFN_CE", "EXFN_CE",
    }
    assert len(sdvi["createPayload"]["ITEM"]) == 6
    assert {
        key: sdve["createPayload"][key]
        for key in (
            "MATERIAL_TYPE", "SHEAR_AREA", "THICKNESS", "MULTIPL", "DIR",
            "FREQ", "STIFF_FACTOR", "DAMP_FACTOR", "REF_T", "LIMIT_DEF",
            "EFF_STIFF", "EQUI_DAMP", "OPT_MOUNT_STIFF", "MOUNT_STIFF",
            "OPT_KINETIC_FRIC", "KINETIC_FRIC",
        )
    } == {
        "MATERIAL_TYPE": "GR100", "SHEAR_AREA": 0.05, "THICKNESS": 0.02,
        "MULTIPL": 1, "DIR": "Dx", "FREQ": 0, "STIFF_FACTOR": 1,
        "DAMP_FACTOR": 1, "REF_T": 20, "LIMIT_DEF": 0.3, "EFF_STIFF": 0,
        "EQUI_DAMP": 0, "OPT_MOUNT_STIFF": True, "MOUNT_STIFF": 1200,
        "OPT_KINETIC_FRIC": False, "KINETIC_FRIC": 0,
    }
    assert sdve["confirmed"] is True


def test_live_case_fixture_marks_reconfirmed_civil_analysis_cases() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    civil_cases = {
        case["endpoint"]: case
        for case in cases
        if case["products"] == ["civil"]
        and case["endpoint"] in {"/db/EIGV", "/db/BCCT"}
    }

    assert set(civil_cases) == {"/db/EIGV", "/db/BCCT"}
    assert all(case["confirmed"] is True for case in civil_cases.values())


def test_live_case_fixture_marks_current_design_round_trips() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    confirmed = {
        case["endpoint"]: case["confirmed"]
        for case in cases
        if case["endpoint"] in {
            "/db/DCON", "/db/DSTL", "/db/LENG", "/db/MEMB",
            "/db/DCTL", "/db/LTSR", "/db/MBTP", "/db/WMAK",
        }
    }

    assert confirmed == {
        "/db/DCON": True,
        "/db/DSTL": False,
        "/db/LENG": True,
        "/db/MEMB": True,
        "/db/DCTL": True,
        "/db/LTSR": True,
        "/db/MBTP": True,
        "/db/WMAK": True,
    }


def test_live_case_fixture_marks_current_heat_source_round_trip() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    hsfc = next(case for case in cases if case["endpoint"] == "/db/HSFC")

    assert hsfc["confirmed"] is True
    assert hsfc["id"] == 92
    assert hsfc["needs"] == ["hsfc_seed"]


def test_live_case_fixture_explicitly_replaces_new_project_baselines() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    material = fixture["seeds"]["ltsr_material"]
    section = fixture["seeds"]["ltsr_section"]
    thickness = fixture["seeds"]["wmak_thickness"]

    assert material["endpoint"] == "/db/MATL"
    assert material["replaceExisting"] is True
    assert material["records"]["1"]["PARAM"][0]["DB"] == "S450"
    assert section["endpoint"] == "/db/SECT"
    assert section["replaceExisting"] is True
    assert thickness["endpoint"] == "/db/THIK"
    assert thickness["replaceExisting"] is True


def test_live_case_fixture_confirms_response_spectrum_load_on_both_products() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    splc = [case for case in cases if case["endpoint"] == "/db/SPLC"]

    assert [(case["products"], case["confirmed"]) for case in splc] == [
        (["civil"], True),
        (["gen"], True),
    ]


def test_live_case_fixture_splits_product_asymmetric_seismic_combination() -> None:
    """Keep Gen's accepted ST shape separate from Civil's manual-shaped RS probe."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seismic = [
        case for case in fixture["cases"]
        if case["endpoint"] == "/db/LCOM-SEISMIC"
    ]

    assert [
        (case["products"], case["confirmed"], case["createPayload"]["vCOMB"])
        for case in seismic
    ] == [
        (["gen"], True, [{"ANAL": "ST", "LCNAME": "DL", "FACTOR": 1.0}]),
        (["civil"], False, [{
            "ANAL": "RS", "LCNAME": "SPLC_LCOM_SEED", "FACTOR": 1.0,
        }]),
    ]
    assert seismic[1]["needs"] == ["lcom_seismic_splc"]
    assert seismic[0]["setup"] == []
    assert seismic[1]["setup"] == [
        {"seed": "lcom_seismic_spfc"},
        {"seed": "lcom_seismic_splc"},
    ]
    assert fixture["seeds"]["lcom_seismic_splc"] == {
        "endpoint": "/db/SPLC",
        "records": {
            "1": {
                "NAME": "SPLC_LCOM_SEED", "DIR": "XY", "SCALE": 1.0,
                "PMFT": 1.0, "aFUNCNAME": ["SPFC_LCOM_SEED"],
            },
        },
    }


def test_no_ledger_entry_contradicts_its_own_level() -> None:
    """A `live_verified` entry's prose and its `level` must say the same thing.

    Both halves are edited by hand, on different lines, and a batch touches
    several entries at once - so an update can land on the neighbouring
    endpoint. That happened: `/db/HPCE` was raised to `write` while its own
    method text still ended "Not resolved as a fixture problem. Left at level:
    read", and `/db/THMS` kept `read` under a method describing a completed
    round trip that persisted `SCALEX` 1.0 to 1.5.

    Neither needs outside evidence to catch. The entry disagrees with itself.
    """

    says_read = re.compile(
        r"(?:left at level: read|remains read-level|stays read-level)", re.IGNORECASE
    )
    says_write = re.compile(
        r"(?:full write round trip confirmed|write-round-trip confirmed)", re.IGNORECASE
    )
    problems: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            verified = node.get("live_verified")
            endpoint = node.get("endpoint")
            if endpoint and isinstance(verified, dict):
                method = verified.get("method", "")
                level = verified.get("level")
                if says_read.search(method) and level == "write":
                    problems.append(f"{endpoint}: method says read-level, level is write")
                if says_write.search(method) and level != "write":
                    problems.append(
                        f"{endpoint}: method describes a write round trip, level is {level!r}"
                    )
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(json.loads((ROOT / "docs" / "coverage.json").read_text(encoding="utf-8")))
    assert not problems, "\n".join(problems)


def test_unknown_endpoint_selection_is_refused_before_any_product_call() -> None:
    """`--endpoints` must reject a name the way `--tier` does.

    The filter is applied inside the tier loop, which runs after `/doc/NEW`
    has already discarded whatever the caller had open. A typo there used to
    leave the run with zero cases: the document was gone and nothing was
    tested. Both refusals must happen before the client is even built.
    """

    for arguments, expected in (
        (["--endpoints", "/db/NOPE"], "No live case for endpoint /db/NOPE"),
        (
            ["--tier", "extras5", "--endpoints", "/db/NODE"],
            "/db/NODE has no case in the selected tier(s)",
        ),
    ):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/live_crud_check.py",
                "--product",
                "gen",
                "--mapi-key",
                "not-a-real-key",
                *arguments,
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 2, result.stdout + result.stderr
        assert expected in result.stderr, result.stderr
        # Nothing may have reached the product.
        assert "mapikey/verify" not in result.stderr


def test_both_harnesses_build_the_same_base_model() -> None:
    """The fixture must carry the model, not just the cases that attach to it.

    Python built the base model by calling typed resources with inline literals
    inside ``_seed_model``, so only Python could replay it. The npm harness
    starts from a genuinely empty ``/doc/NEW``, which is why thirteen cases
    confirmed here reported ``REGRESS`` there against preconditions no one had
    created. A base model only one harness can build is a hole in this file's
    claim to be the language-neutral source both read.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    steps = fixture["baseModel"]

    assert steps, "the fixture must carry the base model every case attaches to"
    for step in steps:
        assert step["endpoint"].startswith("/db/"), step
        assert step["method"] in {"POST", "PUT"}, step
        assert step["records"], f"{step['endpoint']}: a step with no records builds nothing"

    # Order is load-bearing: an element cannot reference a node, a material or a
    # section that a later step creates.
    order = [step["endpoint"] for step in steps]
    for earlier, later in (("/db/NODE", "/db/ELEM"),
                           ("/db/MATL", "/db/ELEM"),
                           ("/db/SECT", "/db/ELEM"),
                           ("/db/STLD", "/db/BODF")):
        assert order.index(earlier) < order.index(later), (
            f"{earlier} must be built before {later}"
        )


def test_the_npm_harness_reads_the_base_model_from_the_fixture() -> None:
    """It may replay the emitted steps and may not carry its own copy.

    A hand-written second copy is how the two harnesses would drift back apart,
    and a payload written into a harness rather than measured is the mistake
    this repository has paid for more than once.
    """
    source = (ROOT / "packages" / "typescript" / "scripts" / "live-crud.mjs").read_text(
        encoding="utf-8"
    )

    assert "fixture.baseModel" in source, "the npm harness must build the emitted base model"
    assert "buildBaseModel(client)" in source, "and must call it before running any case"

    built = source.index("await buildBaseModel(client);")
    first_case = source.index("for (const [caseIndex, liveCase] of cases.entries())")
    assert built < first_case, "the base model must be built before the first case runs"


def test_every_declared_need_resolves_to_a_seed_or_a_stated_reason() -> None:
    """A need that resolves to nothing is worse than one that cannot be met.

    The npm harness used to receive only the seeds an emitter happened to
    export, and dropped the rest with no record, so a case ran with its setup
    silently shortened and failed exactly the way an SDK defect fails. Every
    name must land in one of two places: the seeds the fixture can replay, or
    the seeds it cannot, each with the reason it cannot.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seeds = set(fixture["seeds"])
    unsupported = fixture["unsupportedSeeds"]

    unresolved = {
        (case["endpoint"], name)
        for case in fixture["cases"]
        for name in case["needs"]
        if name not in seeds and name not in unsupported
    }
    assert not unresolved, f"needs resolving to nothing: {sorted(unresolved)}"

    for name, reason in unsupported.items():
        assert reason.strip(), f"{name} is unsupported without saying why"

    for case in fixture["cases"]:
        expected = [name for name in case["needs"] if name in unsupported]
        assert case["blockedSeeds"] == expected, case["endpoint"]


def test_a_seed_is_excluded_only_because_it_cannot_be_replayed() -> None:
    """The boundary is the harness's own vocabulary, not a hand-picked list.

    live-crud.mjs replays a prerequisite as Assign POSTs and per-id DELETEs,
    in order, so every seed the tiers declare today can be expressed. Until
    2026-09-17 a DELETE was outside that vocabulary and three seeds -- and the
    three confirmed cases behind them -- could not reach npm at all.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["unsupportedSeeds"] == {}

    multi_step = {name for name, seed in fixture["seeds"].items() if "steps" in seed}
    assert multi_step, "a seed built from several POSTs must still be exported"

    # What Python's DbResource.delete sends, one id per URL.
    assert fixture["seeds"]["pjcf_unlock"] == {"endpoint": "/db/PJCF", "delete": ["1"]}
    solid = fixture["seeds"]["solid11_seed"]["steps"]
    assert [step["endpoint"] for step in solid] == ["/db/NODE", "/db/ELEM", "/db/ELEM"]
    assert solid[1] == {"endpoint": "/db/ELEM", "delete": ["1"]}
    assert solid[2]["records"]["1"]["TYPE"] == "SOLID"


def test_only_a_listed_seed_may_have_its_read_answered_empty() -> None:
    """A read is exported only where it guards a Python-only duplicate.

    stage11_seed reads /db/STAG so a full Python run does not create stage 1
    twice; npm starts from the base model, where it never exists. Any other
    seed that reads must stay unsupported, with the reason -- answering its
    read with an empty table would export whichever branch that happens to
    pick, which is a guess.
    """
    live = _live_crud_module()
    assert live.FRESH_DOCUMENT_SEEDS == frozenset({"stage11_seed"})

    def reads_then_writes(client):
        if not live.Node.get(client=client):
            live.Node.create({1: {"X": 0, "Y": 0, "Z": 0}}, client=client)

    tier = live.Tier(
        "reader", "a seed that branches on a read",
        lambda: [live.SeedStep("reader_seed", reads_then_writes)], list,
    )
    original = live.TIERS
    live.TIERS = [tier]
    try:
        seeds, unsupported = live._exportable_tier_seeds()
    finally:
        live.TIERS = original

    assert seeds == {}
    assert "GET /db/NODE" in unsupported["reader_seed"]


def test_seeds_are_emitted_in_the_order_a_case_needs_them() -> None:
    """The emitted setup follows ``needs``, so the order is the build order.

    Python runs every tier seed in the tier's own order and never read
    ``needs`` for ordering, so HECB's needs sat stage-first while the stage
    names groups a later seed creates. npm replays exactly the list.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    setups = {
        case["endpoint"]: [step.get("seed") for step in case["setup"]]
        for case in fixture["cases"]
        if case["endpoint"] in {"/db/HECB", "/db/HSPT", "/db/STCT", "/db/MVHL"}
    }
    assert setups["/db/HECB"] == ["solid11_seed", "hecb_seed", "stage11_seed"]
    assert setups["/db/HSPT"] == ["hecb_seed", "stage11_seed"]
    assert setups["/db/STCT"] == ["hecb_seed", "stage11_seed"]
    # /db/MVHL renumbers: the case's id 2 needs the vehicle seed at id 1.
    assert setups["/db/MVHL"] == ["mvcd", "vehicle"]


def test_a_replaced_need_is_neither_prepended_nor_blocked() -> None:
    """DYFG/DYNF need EUROCODE; Python gets it from another case, npm from a seed.

    Their `needs` still name mvcd_ksce_seed, because that is what Python gates
    on. Prepending it to npm's setup would POST /db/MVCD twice and fail on the
    collision before the endpoint under test is touched.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        if case["endpoint"] in {"/db/DYFG", "/db/DYNF"}:
            assert case["needs"] == ["mvcd_ksce_seed"]
            assert case["setup"] == [{"seed": "mvcd_eurocode"}]
            assert case["blockedSeeds"] == []
    assert fixture["seeds"]["mvcd_eurocode"] == {
        "endpoint": "/db/MVCD", "records": {"1": {"CODE": "EUROCODE"}},
    }
    # The value is the switch case's own confirmed update payload.
    switch = next(
        case for case in fixture["cases"]
        if case["endpoint"] == "/db/MVCD" and case["tier"] == "extras14"
    )
    assert switch["confirmed"] is True
    assert switch["updatePayload"] == {"CODE": "EUROCODE"}


def test_an_unordered_comparison_is_declared_not_inferred() -> None:
    """npm cannot see a probe that sorts; the fixture has to say so."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    unordered = sorted(
        case["endpoint"] for case in fixture["cases"] if case["expected"].get("unordered")
    )
    assert unordered == ["/db/BCGA-M1"]
    for case in fixture["cases"]:
        assert case["expected"].get("unordered", True) is True, case["endpoint"]


def test_the_npm_harness_blocks_a_case_it_cannot_seed() -> None:
    """It must refuse such a case, and must not read the refusal as a regression.

    scripts/live_crud_check.py calls a case whose seed step failed BLOCKED and
    exits 3, because that result says nothing about the endpoint under test.
    The npm harness had no such class, so a missing seed record was reported as
    a package regression on a confirmed case.
    """
    source = (ROOT / "packages" / "typescript" / "scripts" / "live-crud.mjs").read_text(
        encoding="utf-8"
    )
    support = (
        ROOT / "packages" / "typescript" / "scripts" / "live-harness-support.mjs"
    ).read_text(encoding="utf-8")

    assert "liveCase.blockedSeeds" in source, "the npm harness must read the blocked list"
    assert "fixture.unsupportedSeeds" in source, "and must report why the seed is missing"
    assert "classifyResult" in source and "exitCodeFor" in source

    # The two decisions Python already makes, in one place npm can test.
    assert 'return "BLOCK"' in support
    assert "result.confirmed && !result.blocked" in support


def test_the_npm_harness_pins_the_fixture_version() -> None:
    """A stale checkout must fail loudly, not build an older model in silence."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = (ROOT / "packages" / "typescript" / "scripts" / "live-crud.mjs").read_text(
        encoding="utf-8"
    )
    pinned = re.search(r"const EXPECTED_FIXTURE_VERSION = (\d+);", source)
    assert pinned, "live-crud.mjs must pin the fixture version it was written for"
    assert int(pinned.group(1)) == fixture["version"]


def test_a_hand_curated_base_seed_wins_a_name_collision() -> None:
    """One name exists in both places and they are not the same record.

    ``lcom_seismic_splc`` is a base-model seed holding the SPLC record, and
    also a tier seed step that creates SPFC *and* SPLC. Merging the exported
    tier seeds over the base ones replaced a record cases reference by name
    with a two-step composite, which duplicated the SPFC create for the one
    case that already spells out both halves. The hand-curated record wins,
    and a second collision must be looked at rather than merged.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seed = fixture["seeds"]["lcom_seismic_splc"]

    assert seed["endpoint"] == "/db/SPLC"
    assert "steps" not in seed, "the base-model record must survive the merge"
    assert set(seed["records"]) == {"1"}

    seismic = [case for case in fixture["cases"] if case["endpoint"] == "/db/LCOM-SEISMIC"]
    for case in seismic:
        seeds = [step["seed"] for step in case["setup"] if "seed" in step]
        assert len(seeds) == len(set(seeds)), f"{case['endpoint']} seeds a record twice"


def test_distinct_floor_load_seed_payloads_have_distinct_names() -> None:
    """The extras7 payload must not replace CO_F's different fixture seed."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert set(fixture["seeds"]["fbld_seed"]["records"]) == {"1"}
    assert set(fixture["seeds"]["fbld7_seed"]["records"]) == {"90"}


def _live_crud_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "live_crud_check_under_test", ROOT / "scripts" / "live_crud_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_case_whose_id_a_seed_already_owns_is_blocked_not_regressed() -> None:
    """A taken id says nothing about the endpoint, so it cannot be a regression.

    Confirmed live on Civil 2026-09-05: extras4's Civil-only lcom_seismic_splc
    seed creates /db/SPLC id 1 and extras5's Civil /db/SPLC case owns the same
    id, so selecting both tiers answered `Key Already Exist` for a shape both
    products accept whenever either tier runs alone. That printed REGRESS and
    exited 1 -- "treat as an SDK defect" -- for a collision inside the fixture.
    Asking for a different id is not the fix: this load-case family renumbers a
    requested key to the next free slot, so a case asking for 2 lands at 1 when
    the other tier was not selected.
    """
    live = _live_crud_module()

    class _Resource:
        ENDPOINT = "/db/FAKE"
        NAME = "Fake"
        METHODS = frozenset({"POST", "PUT", "DELETE"})

        @staticmethod
        def items(client=None):
            return {1: {"NAME": "taken by a seed"}}

        @staticmethod
        def create(records, client=None):
            raise AssertionError("a case must not POST over a record it does not own")

    case = live.Case(
        _Resource, {"NAME": "x"}, {"NAME": "y"},
        lambda payload: payload.get("NAME"), "x", "y",
        item_id=1, confirmed=True,
    )
    row = live._run_case(case, client=None)

    assert row["classification"] == live.BLOCKED
    assert row["ok"] is False
    assert "already exists" in row["steps"]["create"]["error"]


def test_nothing_attaches_an_element_to_the_reserved_node_pair() -> None:
    """Nodes 21-22 carry links, never elements.

    The base model builds that pair unattached so /db/ELNK, /db/RIGD and
    /db/MCON can each own it in turn without colliding with a real element --
    they already collide with each other, and rely on each deleting itself
    before the next runs. extras19's truss seed borrowed the pair on
    2026-09-20 and was rebuilt on its own nodes the same day; this fails
    offline if a fixture reaches for them again.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reserved = {21, 22}

    def element_records(source: dict) -> list[tuple[str, dict]]:
        found = []
        if source.get("endpoint") == "/db/ELEM":
            found += [(key, record) for key, record in (source.get("records") or {}).items()]
        for step in source.get("steps") or []:
            found += element_records(step)
        return found

    offenders = []
    for name, seed in fixture["seeds"].items():
        for key, record in element_records(seed):
            if reserved.intersection(record.get("NODE") or []):
                offenders.append(f"seed {name} element {key}")
    for step in fixture["baseModel"]:
        for key, record in element_records(step):
            if reserved.intersection(record.get("NODE") or []):
                offenders.append(f"base model element {key}")
    for case in fixture["cases"]:
        if case["endpoint"] != "/db/ELEM":
            continue
        for payload_key in ("createPayload", "updatePayload"):
            nodes = (case.get(payload_key) or {}).get("NODE") or []
            if reserved.intersection(nodes):
                offenders.append(f"case {case['endpoint']} {payload_key}")

    assert offenders == [], (
        "nodes 21-22 are reserved for the link and constraint cases: "
        + ", ".join(offenders)
    )


def test_an_unreadable_record_fails_its_case_and_does_not_lose_the_run() -> None:
    """A probe that cannot subscript the record raises MidasAPIError.

    `live_crud_check.apply_probe` exists because a probe reaches into the
    read-back record -- `p["ITEMS"][0]["END"]` -- so a product returning
    another shape raises KeyError, not MidasAPIError. The tier loop catches
    MidasAPIError and records a failed case; a KeyError escapes it and takes
    the report, the end-of-run checkpoint and the restore of an empty scratch
    document with it, leaving the product holding the fixture's model. One
    endpoint answering oddly must cost one case, not the run.
    """
    module = _live_crud_module()

    class _Case:
        @staticmethod
        def probe(record):
            return record["ITEMS"][0]["END"]

    with pytest.raises(module.MidasAPIError) as caught:
        module.apply_probe(_Case(), {"ITEMS": []}, "/db/X", "wrote")
    assert "probe could not read the record" in str(caught.value)
    assert "IndexError" in str(caught.value)

    with pytest.raises(module.MidasAPIError):
        module.apply_probe(_Case(), {}, "/db/X", "wrote")
    with pytest.raises(module.MidasAPIError):
        module.apply_probe(_Case(), None, "/db/X", "updated to")


def test_a_readable_record_passes_the_probe_value_through_unchanged() -> None:
    """The guard must not swallow a value or a genuine MidasAPIError."""
    module = _live_crud_module()

    class _Good:
        @staticmethod
        def probe(record):
            return record["ITEMS"][0]["END"]

    assert module.apply_probe(_Good(), {"ITEMS": [{"END": 3}]}, "/db/X", "wrote") == 3

    class _Raises:
        @staticmethod
        def probe(record):
            raise module.MidasAPIError("the product refused the read")

    with pytest.raises(module.MidasAPIError) as caught:
        module.apply_probe(_Raises(), {}, "/db/X", "wrote")
    assert str(caught.value) == "the product refused the read"
