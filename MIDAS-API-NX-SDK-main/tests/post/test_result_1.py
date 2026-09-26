import json

import responses

from midas_nx.post import result_1


@responses.activate
def test_get_reaction_table_sends_full_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_reaction_table(
        table_name="Reaction(Global)",
        unit={"FORCE": "kN", "DIST": "m"},
        styles={"FORMAT": "Fixed", "PLACE": 12},
        components=["Node", "Load", "FX", "FY", "FZ", "MX", "MY", "MZ", "Mb"],
        node_elems={"KEYS": [1]},
        load_case_names=["DL(ST)"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "Reaction(Global)",
            "TABLE_TYPE": "REACTIONG",
            "UNIT": {"FORCE": "kN", "DIST": "m"},
            "STYLES": {"FORMAT": "Fixed", "PLACE": 12},
            "COMPONENTS": ["Node", "Load", "FX", "FY", "FZ", "MX", "MY", "MZ", "Mb"],
            "NODE_ELEMS": {"KEYS": [1]},
            "LOAD_CASE_NAMES": ["DL(ST)"],
        }
    }


@responses.activate
def test_get_reaction_table_accepts_local_surface_spring_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_reaction_table(result_1.TABLE_TYPE_REACTION_LOCAL_SURFACE_SPRING, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "REACTIONLSURFACESPRING"


@responses.activate
def test_get_displacement_table_defaults_to_global(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_displacement_table(table_name="Displacement", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "DISPLACEMENTG"


@responses.activate
def test_get_displacement_table_accepts_local_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_displacement_table(result_1.TABLE_TYPE_DISPLACEMENT_LOCAL, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "DISPLACEMENTL"


@responses.activate
def test_get_truss_force_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_truss_force_table("TrussForce", load_case_names=["DL(ST)"], client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"TABLE_NAME": "TrussForce", "TABLE_TYPE": "TRUSSFORCE", "LOAD_CASE_NAMES": ["DL(ST)"]}
    }


@responses.activate
def test_get_truss_stress_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_truss_stress_table("TrussStress", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TRUSSSTRESS"


@responses.activate
def test_get_cable_force_table_sends_construction_stage_fields(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_cable_force_table(
        "CableForce",
        load_case_names=["SelfWeight(CS)"],
        opt_cs=True,
        stage_step=["nl_001"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "CABLEFORCE"
    assert body["OPT_CS"] is True
    assert body["STAGE_STEP"] == ["nl_001"]


@responses.activate
def test_get_cable_config_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_cable_config_table("CableConfig", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "CABLECONFIG"


@responses.activate
def test_get_cable_efficiency_table_uses_documented_misspelling(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_cable_efficiency_table("CableEfficiency", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "CABLEEFFIENCY"


@responses.activate
def test_get_beam_force_table_defaults_to_beamforce(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_force_table(table_name="BeamForce", node_elems={"TO": "1 to 10"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMFORCE"


@responses.activate
def test_get_beam_force_table_accepts_by_max_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_force_table(result_1.TABLE_TYPE_BEAM_FORCE_BY_MAX, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMFORCEVBM"


@responses.activate
def test_get_beam_force_static_prestress_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_force_static_prestress_table("BeamForcePS", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMFORCESTP"


@responses.activate
def test_get_beam_stress_table_defaults_to_beamstress(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_stress_table(table_name="BeamStress", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMSTRESS"


@responses.activate
def test_get_beam_stress_table_accepts_7dof_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_stress_table(result_1.TABLE_TYPE_BEAM_STRESS_7DOF, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMSTRESS7DOF"


@responses.activate
def test_get_beam_stress_detail_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_stress_detail_table("BeamStressEq", node_elems={"KEYS": [32]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMSTRESSDETAIL"


@responses.activate
def test_get_beam_stress_psc_table_defaults_to_psc(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_stress_psc_table(table_name="BeamStressPSC", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMSTRESSPSC"


@responses.activate
def test_get_beam_stress_psc_table_accepts_7dof_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_beam_stress_psc_table(result_1.TABLE_TYPE_BEAM_STRESS_7DOF_PSC, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BEAMSTRESS7DOFPSC"


@responses.activate
def test_get_concurrent_joint_force_table_sends_full_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_concurrent_joint_force_table(
        table_name="Concurrent Joint Forces",
        node_elems={"KEYS": [9, 10]},
        unit={"FORCE": "KN", "DIST": "M"},
        components=["Fx", "Fy", "Fz"],
        load_case_names=["case_01(MV:max)"],
        opt_cs=True,
        stage_step=["CS1:001(first)"],
        additional={"SET_REACTION_PARAMS": {"NODE_KEY": 10, "COMPONENT": "111111"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "Concurrent Joint Forces",
            "TABLE_TYPE": "CONCURRENT_JOINT_FORCE",
            "NODE_ELEMS": {"KEYS": [9, 10]},
            "UNIT": {"FORCE": "KN", "DIST": "M"},
            "COMPONENTS": ["Fx", "Fy", "Fz"],
            "LOAD_CASE_NAMES": ["case_01(MV:max)"],
            "OPT_CS": True,
            "STAGE_STEP": ["CS1:001(first)"],
            "ADDITIONAL": {"SET_REACTION_PARAMS": {"NODE_KEY": 10, "COMPONENT": "111111"}},
        }
    }


@responses.activate
def test_get_plate_force_local_table_sends_full_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_force_local_table(
        "PlateForceLocal",
        unit={"FORCE": "kN", "DIST": "m"},
        node_elems={"KEYS": [592]},
        load_case_names=["DL(ST)"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "PlateForceLocal",
            "TABLE_TYPE": "PLATEFORCEL",
            "UNIT": {"FORCE": "kN", "DIST": "m"},
            "NODE_ELEMS": {"KEYS": [592]},
            "LOAD_CASE_NAMES": ["DL(ST)"],
        }
    }


@responses.activate
def test_get_plate_force_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_force_global_table("PlateForceGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATEFORCEG"


@responses.activate
def test_get_plate_force_unit_length_table_defaults_to_local(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_force_unit_length_table(table_name="PlateForceUnitLength", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATEFORCEUL"


@responses.activate
def test_get_plate_force_unit_length_table_accepts_wood_armer_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_force_unit_length_table(result_1.TABLE_TYPE_PLATE_FORCE_UNIT_LENGTH_WOOD_ARMER, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATEFORCEWA"


@responses.activate
def test_get_plate_stress_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_stress_local_table("PlateStressLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATESTRESSL"


@responses.activate
def test_get_plate_stress_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_stress_global_table("PlateStressGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATESTRESSG"


@responses.activate
def test_get_plate_strain_local_table_defaults_to_plastic(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_strain_local_table(table_name="PlateStrainLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATESTRAINPL"


@responses.activate
def test_get_plate_strain_local_table_accepts_total_variant_with_stage_step(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_strain_local_table(
        result_1.TABLE_TYPE_PLATE_STRAIN_LOCAL_TOTAL,
        opt_cs=True,
        stage_step=["nl_001"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "PLATESTRAINTL"
    assert body["OPT_CS"] is True
    assert body["STAGE_STEP"] == ["nl_001"]


@responses.activate
def test_get_plate_strain_global_table_defaults_to_plastic(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_strain_global_table(table_name="PlateStrainGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATESTRAINPG"


@responses.activate
def test_get_plate_strain_global_table_accepts_total_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plate_strain_global_table(result_1.TABLE_TYPE_PLATE_STRAIN_GLOBAL_TOTAL, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLATESTRAINTG"


@responses.activate
def test_get_plane_stress_force_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_stress_force_local_table("PlaneStressForceLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRESSFL"


@responses.activate
def test_get_plane_stress_force_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_stress_force_global_table("PlaneStressForceGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRESSFG"


@responses.activate
def test_get_plane_stress_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_stress_local_table("PlaneStressLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRESSSL"


@responses.activate
def test_get_plane_stress_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_stress_global_table("PlaneStressGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRESSSG"


@responses.activate
def test_get_plane_strain_force_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_strain_force_local_table("PlaneStrainForceLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRAINFL"


@responses.activate
def test_get_plane_strain_force_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_strain_force_global_table("PlaneStrainForceGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRAINFG"


@responses.activate
def test_get_plane_strain_stress_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_strain_stress_local_table("PlaneStrainStressLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRAINSL"


@responses.activate
def test_get_plane_strain_stress_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_plane_strain_stress_global_table("PlaneStrainStressGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PLANESTRAINSG"


@responses.activate
def test_get_axisymmetric_force_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_axisymmetric_force_local_table("AxiForceLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "AXISYMMETRICFL"


@responses.activate
def test_get_axisymmetric_force_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_axisymmetric_force_global_table("AxiForceGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "AXISYMMETRICFG"


@responses.activate
def test_get_axisymmetric_stress_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_axisymmetric_stress_local_table("AxiStressLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "AXISYMMETRICSL"


@responses.activate
def test_get_axisymmetric_stress_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_axisymmetric_stress_global_table("AxiStressGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "AXISYMMETRICSG"


@responses.activate
def test_get_solid_force_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_force_local_table("SolidForceLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLIDFL"


@responses.activate
def test_get_solid_force_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_force_global_table("SolidForceGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLIDFG"


@responses.activate
def test_get_solid_stress_local_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_stress_local_table("SolidStressLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLIDSL"


@responses.activate
def test_get_solid_stress_global_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_stress_global_table("SolidStressGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLIDSG"


@responses.activate
def test_get_solid_strain_local_table_defaults_to_plastic(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_strain_local_table(table_name="SolidStrainLocal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLID_LOCA_PLAST_STRAIN"


@responses.activate
def test_get_solid_strain_local_table_accepts_total_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_strain_local_table(result_1.TABLE_TYPE_SOLID_STRAIN_LOCAL_TOTAL, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLID_LOCA_TOTAL_STRAIN"


@responses.activate
def test_get_solid_strain_global_table_defaults_to_plastic(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_strain_global_table(table_name="SolidStrainGlobal", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLID_GLOB_PLAST_STRAIN"


@responses.activate
def test_get_solid_strain_global_table_accepts_total_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_solid_strain_global_table(result_1.TABLE_TYPE_SOLID_STRAIN_GLOBAL_TOTAL, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SOLID_GLOB_TOTAL_STRAIN"


@responses.activate
def test_get_elastic_link_table_defaults_to_elasticlink(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_elastic_link_table(table_name="ElasticLink", load_case_names=["SWofGirders(ST)"], client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "ELASTICLINK"


@responses.activate
def test_get_elastic_link_table_accepts_by_max_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_elastic_link_table(result_1.TABLE_TYPE_ELASTIC_LINK_BY_MAX, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "ELASTICLINKVBM"


@responses.activate
def test_get_general_link_table_defaults_to_force(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_general_link_table(table_name="GeneralLink", load_case_names=["SWofGirders(ST)"], client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "GENERAL_LINK_FORCE"


@responses.activate
def test_get_general_link_table_accepts_deform_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_general_link_table(result_1.TABLE_TYPE_GENERAL_LINK_DEFORM, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "GENERAL_LINK_DEFORM"


@responses.activate
def test_get_vibration_mode_shape_table_defaults_to_eigenvalue(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_vibration_mode_shape_table(table_name="VibrationMode", node_elems={"KEYS": [1]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "VibrationMode",
            "TABLE_TYPE": "EIGENVALUEMODE",
            "NODE_ELEMS": {"KEYS": [1]},
        }
    }


@responses.activate
def test_get_vibration_mode_shape_table_accepts_participation_vector_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_vibration_mode_shape_table(result_1.TABLE_TYPE_PARTICIPATION_VECTOR_MODE, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "PARTICIPATIONVECTORMODE"


@responses.activate
def test_get_buckling_mode_shape_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_buckling_mode_shape_table("BucklingMode", node_elems={"KEYS": [1]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BUCKLINGMODE"


@responses.activate
def test_get_tendon_coordinates_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_coordinates_table("TendonCoordinates", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"TABLE_NAME": "TendonCoordinates", "TABLE_TYPE": "TNDN_COORDINATES"}
    }


@responses.activate
def test_get_tendon_elongation_table_sends_stage_step_fields(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_elongation_table("TendonElongation", opt_cs=True, stage_step=["CS16:001(first)"], client=gen_client)
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "TNDN_ELONGATION"
    assert body["OPT_CS"] is True
    assert body["STAGE_STEP"] == ["CS16:001(first)"]


@responses.activate
def test_get_tendon_arrangement_table_sends_table_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_arrangement_table("TendonArrangement", node_elems={"KEYS": [50]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_ARRANGEMENT"


@responses.activate
def test_get_tendon_loss_table_defaults_to_force(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_loss_table(table_name="TendonLoss", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_LOSS_FORCE"


@responses.activate
def test_get_tendon_loss_table_accepts_stress_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_loss_table(result_1.TABLE_TYPE_TENDON_LOSS_STRESS, node_elems={"KEYS": [33]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_LOSS_STRESS"


@responses.activate
def test_get_tendon_weight_table_defaults_to_group(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_weight_table(table_name="TendonWeight", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_WEIGHT_GROUP"


@responses.activate
def test_get_tendon_weight_table_accepts_profile_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_weight_table(result_1.TABLE_TYPE_TENDON_WEIGHT_PROFILE, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_WEIGHT_PROFILE"


@responses.activate
def test_get_tendon_stress_limit_check_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_stress_limit_check_table("TendonStressLimitCheck", unit={"FORCE": "kN", "DIST": "m"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "TendonStressLimitCheck",
            "TABLE_TYPE": "TNDN_STRS_LIMIT_CHECK",
            "UNIT": {"FORCE": "kN", "DIST": "m"},
        }
    }


@responses.activate
def test_get_tendon_approx_loss_table_defaults_to_force(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_approx_loss_table(table_name="TendonApproxLoss", node_elems={"KEYS": [1]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_APPROX_LOSS_FORCE"


@responses.activate
def test_get_tendon_approx_loss_table_accepts_stress_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_tendon_approx_loss_table(result_1.TABLE_TYPE_TENDON_APPROX_LOSS_STRESS, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "TNDN_APPROX_LOSS_STRESS"


@responses.activate
def test_get_composite_section_beam_table_sends_construction_stage_fields(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_composite_section_beam_table(
        table_name="CompSectForce",
        node_elems={"KEYS": [1]},
        load_case_names=["DL(CS)"],
        opt_cs=True,
        stage_step=["CS1:001(first)"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "COMPSECTBEAMFORCE"
    assert body["OPT_CS"] is True
    assert body["STAGE_STEP"] == ["CS1:001(first)"]


@responses.activate
def test_get_composite_section_beam_table_accepts_stress_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_composite_section_beam_table(result_1.TABLE_TYPE_COMPOSITE_SECTION_BEAM_STRESS, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "COMPSECTBEAMSTRESS"


@responses.activate
def test_get_composite_section_self_constraint_beam_table_defaults_to_force(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_composite_section_self_constraint_beam_table(
        table_name="SelfConstForce",
        node_elems={"KEYS": [1]},
        load_case_names=["TG(+)(CS)"],
        opt_cs=True,
        stage_step=["CS1:001(first)"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SELF_CONST_BEAM_FORCE"


@responses.activate
def test_get_composite_section_self_constraint_beam_table_accepts_stress_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_composite_section_self_constraint_beam_table(
        result_1.TABLE_TYPE_SELF_CONSTRAINT_BEAM_STRESS, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SELF_CONST_BEAM_STRESS"


@responses.activate
def test_get_wall_force_table_sends_full_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    result_1.get_wall_force_table(
        table_name="WallForce",
        unit={"FORCE": "kN", "DIST": "m"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        node_elems={"KEYS": [1, 2, 3]},
        load_case_names=["gLCB6(CB)"],
        story_names=["2F"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "WallForce",
            "TABLE_TYPE": "WALL_FORCE_MOMENT",
            "UNIT": {"FORCE": "kN", "DIST": "m"},
            "STYLES": {"FORMAT": "Fixed", "PLACE": 3},
            "NODE_ELEMS": {"KEYS": [1, 2, 3]},
            "LOAD_CASE_NAMES": ["gLCB6(CB)"],
            "STORY_NAMES": ["2F"],
        }
    }
