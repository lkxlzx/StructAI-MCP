import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.properties.damping import GroupDamping
from midas_nx.db.properties.hinge import (
    InelasticHingeControl,
    InelasticHingeProperty,
    InelasticHingePropertyHyperSBeam,
    InelasticHingePropertyHyperSGeneralLink,
    InelasticHingePropertyHyperSPss,
    InelasticHingePropertyHyperSTruss,
)
from midas_nx.db.properties.material import (
    ChangeProperty,
    InelasticFiberMaterialLink,
    InelasticFiberMaterialLinkHyperS,
    InelasticMaterialProperty,
    Material,
    MaterialHyperS,
    MaterialModifyConcrete,
    PlasticMaterial,
    PlasticMaterialHyperS,
    TimeDependentMaterialCreepShrinkage,
    TimeDependentMaterialFunction,
    TimeDependentMaterialLink,
    TimeDependentMaterialStrength,
)
from midas_nx.db.properties.section import (
    EffectiveWidthScaleFactor,
    ElementStiffnessScaleFactor,
    FiberDivision,
    PlateStiffnessScaleFactor,
    Section,
    SectionReinforcement,
    SectionStiffness,
    SectionStressPoints,
    TaperedGroup,
    VirtualBeam,
    VirtualSection,
)
from midas_nx.db.properties.thickness import Thickness


@responses.activate
def test_material_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MATL", json={}, status=200)

    Material.create(
        {
            1: {
                "TYPE": "CONC",
                "NAME": "C32",
                "PARAM": [{"P_TYPE": 1, "STANDARD": "AS17(RC)", "DB": "C32"}],
            }
        },
        client=gen_client,
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {
            "1": {
                "TYPE": "CONC",
                "NAME": "C32",
                "PARAM": [{"P_TYPE": 1, "STANDARD": "AS17(RC)", "DB": "C32"}],
            }
        }
    }


@responses.activate
def test_matd_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        MaterialModifyConcrete.create({1: {"TYPE": "CONC"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_matd_get_and_put_are_allowed(gen_client):
    responses.add(responses.GET, "https://x.test:443/gen/db/MATD", json={"MATD": {}}, status=200)
    responses.add(responses.PUT, "https://x.test:443/gen/db/MATD", json={}, status=200)

    MaterialModifyConcrete.get(client=gen_client)
    MaterialModifyConcrete.update(
        {1: {"TYPE": "CONC", "NAME": "C16/20", "REBAR_CODENAME": "EN04(RC)"}},
        client=gen_client,
    )

    assert len(responses.calls) == 2


@responses.activate
def test_matd_delete_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        MaterialModifyConcrete.delete([1], client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_section_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SECT", json={}, status=200)

    Section.create(
        {
            1: {
                "SECTTYPE": "DBUSER",
                "SECT_NAME": "H300x150",
                "SECT_BEFORE": {
                    "SHAPE": "H",
                    "OFFSET_PT": "CC",
                    "DATATYPE": 1,
                    "SECT_I": {"DB_NAME": "KS21", "SECT_NAME": "H300x150x6.5/9"},
                },
            }
        },
        client=gen_client,
    )

    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["SECTTYPE"] == "DBUSER"
    # DATATYPE is a sibling of SECT_I inside SECT_BEFORE, not nested inside it
    # (docs/manual/04_DB_Properties.md #12-A) — regression check for that mix-up.
    assert body["SECT_BEFORE"]["DATATYPE"] == 1
    assert "DATATYPE" not in body["SECT_BEFORE"]["SECT_I"]


@responses.activate
def test_thickness_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THIK", json={}, status=200)

    Thickness.create(
        {1: {"NAME": "T200", "TYPE": "VALUE", "bINOUT": False, "T_IN": 0.20, "T_OUT": 0, "O_VALUE": 0}},
        client=gen_client,
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"NAME": "T200", "TYPE": "VALUE", "bINOUT": False, "T_IN": 0.20, "T_OUT": 0, "O_VALUE": 0}}
    }


@responses.activate
def test_inelastic_fiber_material_link_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IMFM", json={}, status=200)
    InelasticFiberMaterialLink.create(
        {1: {"CONC_NAME": "Concrete_KP", "CONFINED_CONC_NAME": "Confined_KP", "REBAR_NAME": "Rebar_Menegotto"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CONC_NAME"] == "Concrete_KP"


@responses.activate
def test_time_dependent_material_function_create_creep_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDMF", json={}, status=200)
    TimeDependentMaterialFunction.create(
        {
            1: {
                "NAME": "CreepFunc_1",
                "FTYPE": "CREEP",
                "CTYPE": "CC",
                "SCALE": 1.0,
                "vDAY": [{"DAY": 28, "VALUE": 0.5}, {"DAY": 90, "VALUE": 1.0}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FTYPE"] == "CREEP"


@responses.activate
def test_time_dependent_material_creep_shrinkage_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDMT", json={}, status=200)
    TimeDependentMaterialCreepShrinkage.create(
        {1: {"NAME": "KDS2016", "CODE": "KDS2016", "STR": 24000, "HU": 70, "MSIZE": 0.2, "AGE": 28}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CODE"] == "KDS2016"


@responses.activate
def test_time_dependent_material_strength_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDME", json={}, status=200)
    TimeDependentMaterialStrength.create(
        {1: {"NAME": "TDME_KDS2016", "TYPE": "CODE", "CODENAME": "KDS2016", "STRENGTH": 24000}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["TYPE"] == "CODE"


@responses.activate
def test_change_property_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EDMP", json={}, status=200)
    ChangeProperty.create({10: {"TYPE": "NSM", "H_VS": 0.10}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"10": {"TYPE": "NSM", "H_VS": 0.10}}}


@responses.activate
def test_time_dependent_material_link_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TMAT", json={}, status=200)
    TimeDependentMaterialLink.create({2: {"TDMT_NAME": "KDS2016", "TDME_NAME": "KDS2016"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"2": {"TDMT_NAME": "KDS2016", "TDME_NAME": "KDS2016"}}}


@responses.activate
def test_plastic_material_create_von_mises_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EPMT", json={}, status=200)
    PlasticMaterial.create(
        {1: {"NAME": "Steel_VonMises", "MODEL_TYPE": "VM", "VMISES": {"INIT_YIELD_STRESS": 235000}}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MODEL_TYPE"] == "VM"


@responses.activate
def test_plastic_material_create_drucker_masonry_concdmg_variants(gen_client):
    """docs/manual/04_DB_Properties.md #10 -- DRUCKER/MASONRY/CONCDMG were
    entirely missing from PlasticMaterialPayload until the 2026-08-25
    manual re-check; one payload per MODEL_TYPE, mirroring the existing
    Von-Mises coverage above."""
    responses.add(responses.POST, "https://x.test:443/gen/db/EPMT", json={}, status=200)
    PlasticMaterial.create(
        {
            1: {
                "NAME": "Soil_DruckerPrager",
                "MODEL_TYPE": "DP",
                "DRUCKER": {"INIT_COHESION": 50, "INIT_FRIC_ANGLE": 30, "OPT_HARDENING": 0, "HARDENING_COEF": 100},
            }
        },
        client=gen_client,
    )
    assert json.loads(responses.calls[0].request.body)["Assign"]["1"]["MODEL_TYPE"] == "DP"

    responses.add(responses.POST, "https://x.test:443/gen/db/EPMT", json={}, status=200)
    PlasticMaterial.create(
        {
            2: {
                "NAME": "Brick_Masonry",
                "MODEL_TYPE": "MA",
                "MASONRY": {
                    "BM": {
                        "YOUNG_S_MODULUS": 20000000,
                        "POSSIONS_S_RATIO": 0.2,
                        "TENSION_STRENGTH": 1000,
                        "SOFTENING_PARAMETER": 0.5,
                    },
                    "BED_JOINT": {
                        "YOUNG_S_MODULUS": 10000000,
                        "POSSIONS_S_RATIO": 0.2,
                        "TENSION_STRENGTH": 500,
                        "HARDENING_PARAM": 0.5,
                    },
                    "HEAD_JOINT": {
                        "YOUNG_S_MODULUS": 10000000,
                        "POSSIONS_S_RATIO": 0.2,
                        "TENSION_STRENGTH": 500,
                        "HARDENING_PARAM": 0.5,
                    },
                    "GEOM": {
                        "BRICK_LENGTH": 0.24,
                        "BRICK_HEIGHT": 0.07,
                        "THICKNESS_BED": 0.01,
                        "THICKNESS_HEAD": 0.01,
                        "COORD_TYPE": 0,
                    },
                },
            }
        },
        client=gen_client,
    )
    assert json.loads(responses.calls[1].request.body)["Assign"]["2"]["MODEL_TYPE"] == "MA"

    responses.add(responses.POST, "https://x.test:443/gen/db/EPMT", json={}, status=200)
    PlasticMaterial.create(
        {
            3: {
                "NAME": "Conc_Damage",
                "MODEL_TYPE": "DM",
                "CONCDMG": {
                    "DILIATION_ANGLE": 36,
                    "ECCEN": 0.1,
                    "FBO_FCO": 1.16,
                    "K": 0.667,
                    "VISCOSITY_PARAM": 0,
                    "COMP_ITEMS": [{"INELASTIC_STRAIN": 0, "YIELD_STRESS": 30000, "DAMAGE": 0}],
                    "TENSILE_ITEMS": [{"INELASTIC_STRAIN": 0, "YIELD_STRESS": 3000, "DAMAGE": 0}],
                },
            }
        },
        client=gen_client,
    )
    assert json.loads(responses.calls[2].request.body)["Assign"]["3"]["MODEL_TYPE"] == "DM"


@responses.activate
def test_inelastic_material_property_create_kent_park_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FIMP", json={}, status=200)
    InelasticMaterialProperty.create(
        {
            3: {
                "NAME": "Conc_Kent&Park",
                "MATL_TYPE": "CONC",
                "HYS_MODEL": "KPM",
                "CONC": {
                    "KENPAR": {
                        "FC": 30000,
                        "PARTIAL_FACT": 1.0,
                        "K": 1.0,
                        "EC0": 0.002,
                        "EC1_METHOD": 1,
                        "EC1": 0.0035,
                        "Z": 100,
                        "ECU": 0.003,
                        "STRENGTH_AFTER": 0,
                    }
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    kenpar = json.loads(sent.body)["Assign"]["3"]["CONC"]["KENPAR"]
    assert json.loads(sent.body)["Assign"]["3"]["HYS_MODEL"] == "KPM"
    assert kenpar["EC1_METHOD"] == 1
    assert kenpar["Z"] == 100
    assert kenpar["STRENGTH_AFTER"] == 0


@responses.activate
def test_tapered_group_create_poly_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TSGR", json={}, status=200)
    TaperedGroup.create(
        {
            2: {
                "NAME": "PolyGroup",
                "ELEMLIST": [4, 5, 6],
                "ZVAR": "POLY",
                "YVAR": "POLY",
                "ZEXP": 2.0,
                "ZFROM": "i",
                "ZDIST": 0,
                "YEXP": 1.5,
                "YFROM": "j",
                "YDIST": 0.1,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["2"]
    assert body["ZVAR"] == "POLY"
    assert body["YEXP"] == 1.5
    assert body["YFROM"] == "j"


@responses.activate
def test_section_stiffness_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SECF", json={}, status=200)
    SectionStiffness.create(
        {
            9001: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "GROUP_NAME": "Creep716",
                        "AREA_SF": 2.61,
                        "W_SF": 1.0,
                        "IPART": 3,
                        "bDiffIJ": True,
                        "J1": 2.61,
                        "J8": 1.0,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["9001"]["ITEMS"][0]
    assert item["AREA_SF"] == 2.61
    assert item["bDiffIJ"] is True
    assert item["J1"] == 2.61


@responses.activate
def test_section_reinforcement_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/RPSC", json={}, status=200)
    SectionReinforcement.create(
        {
            401: {
                "OPT_MBAR_J": False,
                "OPT_SBAR_J": False,
                "OPT_CRACKED": False,
                "SBAR_ITEMS": [
                    {"OPT_DR": False, "OPT_SBW": False, "OPT_TR": False, "OPT_SR": False, "OPT_LBAR_FLG": False},
                    {"OPT_DR": False, "OPT_SBW": False, "OPT_TR": False, "OPT_SR": False, "OPT_LBAR_FLG": False},
                ],
                "MBAR_ITEMS": [
                    {"IJ": "I", "NAME": "D25", "REF_Y": 0, "Y": 0, "REF_Z": 1, "Z": 0.05, "NUM": 4, "SPACING": 0.15}
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["401"]
    assert body["OPT_CRACKED"] is False
    assert body["MBAR_ITEMS"][0]["NAME"] == "D25"


@responses.activate
def test_section_stress_points_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/STRPSSM", json={}, status=200)
    SectionStressPoints.create(
        {
            9003: {
                "OPT_SAME_J": True,
                "POINT_SIZE_1": 2,
                "POINT_SIZE_2": 2,
                "POINT1": [{"PY": 0.00583, "PZ": 0.00476}],
                "POINT2": [{"PY": 0.00583, "PZ": 0.00476}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["9003"]["POINT_SIZE_1"] == 2


@responses.activate
def test_plate_stiffness_scale_factor_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PSSF", json={}, status=200)
    PlateStiffnessScaleFactor.create(
        {12: {"ITEMS": [{"ID": 1, "GROUP_NAME": "Service", "AXIAL_X": 0.6}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["12"]["ITEMS"][0]["AXIAL_X"] == 0.6


@responses.activate
def test_virtual_beam_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/VBEM", json={}, status=200)
    VirtualBeam.create({1: {"VSEC1": 1, "VSEC2": 2}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"VSEC1": 1, "VSEC2": 2}}}


@responses.activate
def test_virtual_section_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/VSEC", json={}, status=200)
    VirtualSection.create(
        {
            1: {
                "NAME": "Girder_I_Section",
                "CENT_CALC_TYPE": 0,
                "CEN_PT_X": 0,
                "CEN_PT_Y": 18.0,
                "CEN_PT_Z": 0.934,
                "NORMAL_X": 1,
                "NORMAL_Y": 0,
                "NORMAL_Z": 0,
                "NODE_LIST": [20, 29, 26, 23],
                "ELEM_LIST": [10, 11, 12],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NAME"] == "Girder_I_Section"


@responses.activate
def test_effective_width_scale_factor_create_keyed_by_element_id(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/EWSF", json={}, status=200)
    EffectiveWidthScaleFactor.create(
        {10: {"ITEMS": [{"ID": 1, "LYSCALE": 0.5, "ZTSCALE": 0.6, "ZBSCALE": 0.7, "bJ": False}]}},
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["10"]["ITEMS"][0]["LYSCALE"] == 0.5


@responses.activate
def test_element_stiffness_scale_factor_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ESSF", json={}, status=200)
    ElementStiffnessScaleFactor.create(
        {1: {"ITEMS": [{"ID": 1, "AREA_SF": 0.5, "ASY_SF": 0.6}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["AREA_SF"] == 0.5


@responses.activate
def test_fiber_division_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FIBR", json={}, status=200)
    FiberDivision.create(
        {
            1: {
                "NAME": "Column_Fiber",
                "SECT_KEY": 11001,
                "ASSIGN_TYPE": 0,
                "FIMP_NAME": ["Steel", "Cover Concrete", "Core", "Core", "Core", "Core"],
                "FIBR_BASE": [
                    {
                        "FIBR_BASE_KEY": 752,
                        "REBAR_NAME": "",
                        "AREA": 0.00688072,
                        "CENTER_Y": -1.05047e-16,
                        "CENTER_Z": 1.06179,
                        "FIBER_MATL_ID": 1,
                        "AREA_CONSIDER_REBAR": 0,
                        "OPT_IS_REBAR": False,
                        "POINT_Y": [0.0527429, 0.0527429, -0.0527429, -0.0527429, 0],
                        "POINT_Z": [1.08596, 1.029, 1.029, 1.08596, 1.1025],
                    }
                ],
                "OPT_MONITORED_FIBER": True,
                "MONITORED_FIBER": [0, 0, 0, 0, 0, 0],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["SECT_KEY"] == 11001
    # FIBR_BASE_KEY is an Integer fiber id, not a bool -- confirmed live 2026-08-27
    # via GET /info/db/FIBR (see FiberDivisionBaseItem's docstring).
    assert body["FIBR_BASE"][0]["FIBR_BASE_KEY"] == 752
    assert isinstance(body["FIBR_BASE"][0]["FIBR_BASE_KEY"], int)
    assert body["OPT_MONITORED_FIBER"] is True


@responses.activate
def test_inelastic_hinge_control_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IEHC", json={}, status=200)
    InelasticHingeControl.create(
        {
            1: {
                "BEAM_LOC": 1,
                "OPT_ConsiderRebarArea1D": False,
                "FAreaSizeCore": 1,
                "BeamDivNumNy": 15,
                "BeamDivNumNz": 20,
                "FAreaSizeCover": 1,
                "BeamDivNumNyCover": 20,
                "BeamDivNumNzCover": 15,
                "WallConsOut": False,
                "WAreaSize": "AUTO",
                "WallDivNumZ": 8,
                "WallDivNumY": 1,
                "WAreaSizeCover": 1,
                "WallDivNumZCover": 8,
                "WallDivNumYCover": 1,
                "OPT_ConsiderRebarAreaWall": False,
                "dR": 0.4,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["BeamDivNumNy"] == 15
    assert body["BeamDivNumNzCover"] == 15
    assert body["WAreaSize"] == "AUTO"


@responses.activate
def test_inelastic_hinge_property_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IEHG", json={}, status=200)
    InelasticHingeProperty.create(
        {2101: {"PROP_NAME": "Fiber_Auto", "FIBER_NAME": "B2102_Column12"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"2101": {"PROP_NAME": "Fiber_Auto", "FIBER_NAME": "B2102_Column12"}}}


@responses.activate
def test_group_damping_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/GRDP", json={}, status=200)
    GroupDamping.create(
        {
            1: {
                "bExistStrain": True,
                "OPT_CALC_WHEN_USED": True,
                "STRAIN_GROUP_ITEMS": [{"GROUP_TYPE": "MATERIAL", "GROUP_NAME": "1", "DAMPING_RATIO": 0.05}],
                "STRAIN_GROUP_PRIORITY": 0,
                "STRAIN_VALUE_PRIORITY": 0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["STRAIN_GROUP_ITEMS"][0]["DAMPING_RATIO"] == 0.05


@responses.activate
def test_group_damping_create_rayleigh_variant(gen_client):
    """docs/manual/04_DB_Properties.md #30 — Element Mass & Stiffness
    Proportional (Rayleigh damping) branch, missing from this repo's
    GroupDampingPayload until the 2026-08-27 manual re-check."""
    responses.add(responses.POST, "https://x.test:443/gen/db/GRDP", json={}, status=200)
    GroupDamping.create(
        {
            1: {
                "bExistElement": True,
                "OPT_MASS_PROP_DEFAULT": True,
                "OPT_STIFF_PROP_DEFAULT": True,
                "DIRECT_CALC_MODE_DEFAULT": 1,
                "MASS_COEF_DEFAULT": 0.04188790133333333,
                "STIFF_COEF_DEFAULT": 0.0848826377636192,
                "FREQ_PERIOD_MODE_DEFAULT": 0,
                "FREQ_MODE_1_DEFAULT": 0.1,
                "FREQ_MODE_2_DEFAULT": 0.2,
                "PERIOD_MODE_1_DEFAULT": 0,
                "PERIOD_MODE_2_DEFAULT": 0,
                "DAMPING_MODE_1_DEFAULT": 0.06,
                "DAMPING_MODE_2_DEFAULT": 0.07,
                "GROUP_DAMPING_ITEMS": [
                    {
                        "GROUP_TYPE": "MATERIAL",
                        "GROUP_NAME": "1",
                        "STIFF_COEF": 0.005787452574792216,
                        "OPT_STIFF_PROP": True,
                        "MASS_COEF": 0.06854383854545451,
                        "OPT_MASS_PROP": True,
                        "DIRECT_CALC_MODE": 1,
                        "FREQ_PERIOD_MODE": 0,
                        "FREQ_MODE_1": 0.5,
                        "FREQ_MODE_2": 0.6,
                        "PERIOD_MODE_1": 0,
                        "PERIOD_MODE_2": 0,
                        "DAMPING_RATIO_MODE": 0,
                        "DAMPING_RATIO_MODE_1": 0.02,
                        "DAMPING_RATIO_MODE_2": 0.02,
                    }
                ],
                "ELEM_GROUP_PRIORITY": 0,
                "ELEM_VALUE_PRIORITY": 0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["bExistElement"] is True
    assert body["GROUP_DAMPING_ITEMS"][0]["STIFF_COEF"] == 0.005787452574792216


@responses.activate
def test_material_hyper_s_create_sends_info_derived_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MATL-M1", json={}, status=200)
    matl = {
        "MATL_NAME": "C24",
        "MATL_TYPE": "CONC",
        "DAMP_RAT": 0,
        "PARAM": [{"P_TYPE": 0, "STANDARD": "KS01(RC)", "DB": "C24"}],
    }
    MaterialHyperS.create({1: matl}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": matl}}


@responses.activate
def test_inelastic_fiber_material_link_hyper_s_create_sends_nested_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/IMFM-M1", json={}, status=200)
    InelasticFiberMaterialLinkHyperS.create(
        {1: {"CONCRETE": {"UN_CONC_NAME": "Concrete_KP"}, "STEEL": {"STEEL_NAME": "Steel_Menegotto"}}},
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CONCRETE"]["UN_CONC_NAME"] == "Concrete_KP"


@responses.activate
def test_plastic_material_hyper_s_create_von_mises_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/EPMT-M1", json={}, status=200)
    PlasticMaterialHyperS.create(
        {1: {"NAME": "Steel_VonMises", "MODEL_TYPE": 1, "VMISES": {"INIT_YIELD_STRESS": 235000}}},
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MODEL_TYPE"] == 1


@responses.activate
def test_inelastic_hinge_property_hyper_s_beam_create_keyed_by_element_id(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/IEHG-BEAM-M1", json={}, status=200)
    InelasticHingePropertyHyperSBeam.create({2101: {"INEL_PROP_NAME": "Fiber_Auto"}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"2101": {"INEL_PROP_NAME": "Fiber_Auto"}}}


@responses.activate
def test_inelastic_hinge_property_hyper_s_truss_gl_pss_create_keyed_by_element_id(civil_client):
    for cls, endpoint in (
        (InelasticHingePropertyHyperSTruss, "IEHG-TRUSS-M1"),
        (InelasticHingePropertyHyperSGeneralLink, "IEHG-GL-M1"),
        (InelasticHingePropertyHyperSPss, "IEHG-PSS-M1"),
    ):
        responses.add(responses.POST, f"https://x.test:443/civil/db/{endpoint}", json={}, status=200)
        cls.create({1: {"INEL_PROP_NAME": "Fiber_Auto"}}, client=civil_client)
        sent = responses.calls[-1].request
        assert json.loads(sent.body) == {"Assign": {"1": {"INEL_PROP_NAME": "Fiber_Auto"}}}
