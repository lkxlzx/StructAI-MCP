import json

import responses

from midas_nx import view


@responses.activate
def test_get_selection_sends_get_with_no_body(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/view/SELECT",
        json={"SELECT": {"NODE_LIST": [67, 130], "ELEM_LIST": [92, 93]}}, status=200,
    )
    result = view.get_selection(client=gen_client)
    assert result == {"SELECT": {"NODE_LIST": [67, 130], "ELEM_LIST": [92, 93]}}
    sent = responses.calls[0].request
    assert sent.method == "GET"
    assert sent.body is None


@responses.activate
def test_capture_smart_report_mode(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/CAPTURE", json={"CAPTURE": {"message": "Success"}}, status=200)
    argument: view.CaptureArgument = {
        "EXPORT_PATH": "C:\\MIDAS\\CaptureTest\\image.jpg",
        "FIGURE_NAME": "Figure 1",
    }
    view.capture(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "EXPORT_PATH": "C:\\MIDAS\\CaptureTest\\image.jpg",
            "FIGURE_NAME": "Figure 1",
        }
    }


@responses.activate
def test_capture_user_setting_mode(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/CAPTURE", json={"CAPTURE": {"message": "Success"}}, status=200)
    argument: view.CaptureArgument = {
        "SET_MODE": "post",
        "SET_HIDDEN": False,
        "EXPORT_PATH": "C:\\MIDAS\\CaptureTest\\image.jpg",
        "HEIGHT": 1000,
        "WIDTH": 1000,
        "ACTIVE": {
            "ACTIVE_MODE": "Active",
            "N_LIST": [104, 125, 151, 153],
            "E_LIST": [196, 228, 229, 231, 232, 269, 270, 279, 280, 291, 292, 349, 350],
        },
        "ANGLE": {"HORIZONTAL": 45, "VERTICAL": 60},
        "DISPLAY": {
            "NODE": {"NODE": True, "NODE_NUMBER": True},
        },
        "PERSPECTIVE": True,
        "ZOOM_LEVEL": 150,
        "BGCOLOR_TOP": {"R": 255, "G": 125, "B": 125},
        "RESULT_GRAPHIC": {
            "CURRENT_MODE": "beam diagrams",
            "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": "DL"},
            "COMPONENTS": {"PART": "total", "COMP": "Fx"},
            "DISPLAY_OPTIONS": {"FIDELITY": "Exact", "FILL": "line fill", "SCALE": 1.0},
            "TYPE_OF_DISPLAY": {
                "CONTOUR": {"OPT_CHECK": True},
                "DEFORM": {"OPT_CHECK": True},
                "LEGEND": {"OPT_CHECK": True},
                "VALUES": {"OPT_CHECK": True},
            },
            "OUTPUT_SECT_LOCATION": {"OPT_I": True, "OPT_CENTER_MID": True, "OPT_J": True},
        },
    }
    view.capture(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_precapture_sends_fiber_option(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/PRECAPTURE", json={"CAPTURE": {"message": "Success"}}, status=200)
    argument: view.PrecaptureArgument = {
        "EXPORT_PATH": "C:\\MIDAS\\CaptureTest\\Test.jpg",
        "VIEW_TYPE": "FIBR",
        "OPTION": {"ID": 1},
    }
    view.precapture(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_angle_sends_horizontal_and_vertical(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/ANGLE", json={"ANGLE": {"message": "Success"}}, status=200)
    view.set_angle({"HORIZONTAL": 30, "VERTICAL": 15}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"HORIZONTAL": 30, "VERTICAL": 15}}


@responses.activate
def test_set_active_mode_all(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/ACTIVE", json={"ACTIVE": {"message": "Success"}}, status=200)
    view.set_active({"ACTIVE_MODE": "All"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"ACTIVE_MODE": "All"}}


@responses.activate
def test_set_active_mode_active_by_node_element(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/ACTIVE", json={"ACTIVE": {"message": "Success"}}, status=200)
    argument: view.ActiveArgument = {
        "ACTIVE_MODE": "Active",
        "N_LIST": [469, 770, 772, 773],
        "E_LIST": [1631, 1646, 1654],
    }
    view.set_active(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_active_mode_identity(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/ACTIVE", json={"ACTIVE": {"message": "Success"}}, status=200)
    argument: view.ActiveArgument = {
        "ACTIVE_MODE": "Identity",
        "IDENTITY_TYPE": "BoundaryGroup",
        "IDENTITY_LIST": ["Support", "Support2", "Support3"],
    }
    view.set_active(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_display_node_group(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/DISPLAY", json={"DISPLAY": "Display settings updated."}, status=200)
    argument: view.DisplayArgument = {
        "NODE": {
            "NODE": False,
            "NODE_NUMBER": False,
            "STORY_NAME": False,
            "NODE_LOCAL_AXIS": False,
        }
    }
    view.set_display(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_display_load_group(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/DISPLAY", json={"DISPLAY": "Display settings updated."}, status=200)
    argument: view.DisplayArgument = {
        "LOAD": {
            "CASE_SELECTION": {"TYPE": "st", "NAME": "DL"},
            "GROUP_SELECTION": ["Load Group 1", "Load Group 2", "Load Group 3"],
            "LOAD_VALUE": {"FORMAT": "Fixed", "PLACE": 1},
            "NODAL_LOAD": True,
            "BEAM_LOAD": True,
            "PRESSURE_LOAD": True,
            "WIND_LOAD": True,
            "SEISMIC_LOAD": True,
        }
    }
    view.set_display(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_display_view_group_uses_corrected_viewport_gizmo_spelling(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/DISPLAY", json={"DISPLAY": "Display settings updated."}, status=200)
    argument: view.DisplayArgument = {
        "VIEW": {
            "UCS_AXIS": True,
            "VIEWPORT_GIZMO": True,
            "VIEW_POINT": True,
            "DESCRIPTION": "Test",
            "LABEL_ORIENTATION": 15,
        }
    }
    view.set_display(argument, client=gen_client)
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body == {"Argument": argument}
    assert "VIEWPORT_GIZMO" in body["Argument"]["VIEW"]
    assert "VIEWPPORT_GIZMO" not in body["Argument"]["VIEW"]


@responses.activate
def test_set_display_misc_group_includes_grid_model_load_line(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/DISPLAY", json={"DISPLAY": "Display settings updated."}, status=200)
    argument: view.DisplayArgument = {
        "MISC": {
            "NODAL_MASS": True,
            "GRID_MODEL_LOAD_LINE": True,
        }
    }
    view.set_display(argument, client=gen_client)
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["MISC"]["GRID_MODEL_LOAD_LINE"] is True


@responses.activate
def test_set_result_graphic_contour_details(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/RESULTGRAPHIC", json={"RESULTGRAPHIC": "Result graphic display updated."}, status=200)
    argument: view.ResultGraphicArgument = {
        "CURRENT_MODE": "beamdiagrams",
        "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": "DL"},
        "COMPONENTS": {"PART": "total", "COMP": "Fx"},
        "DISPLAY_OPTIONS": {"FIDELITY": "Exact", "FILL": "line", "SCALE": 1.0},
        "TYPE_OF_DISPLAY": {
            "CONTOUR": {
                "OPT_CHECK": True,
                "NUM_OF_COLOR": 6,
                "COLOR_TYPE": "rgb",
                "OPTIONS": {"GRADIENT_FILL": False, "CONTOUR_FILL": False},
            }
        },
        "OUTPUT_SECT_LOCATION": {"OPT_I": True, "OPT_CENTER_MID": True, "OPT_J": True},
    }
    view.set_result_graphic(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}


@responses.activate
def test_set_result_graphic_deform_details_with_contour(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/view/RESULTGRAPHIC", json={"RESULTGRAPHIC": "Result graphic display updated."}, status=200)
    argument: view.ResultGraphicArgument = {
        "CURRENT_MODE": "beamdiagrams",
        "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": "DL"},
        "COMPONENTS": {"PART": "total", "COMP": "Fx"},
        "DISPLAY_OPTIONS": {"FIDELITY": "Exact", "FILL": "line", "SCALE": 1.0},
        "TYPE_OF_DISPLAY": {
            "CONTOUR": {
                "OPT_CHECK": True,
                "NUM_OF_COLOR": 6,
                "COLOR_TYPE": "rgb",
                "OPTIONS": {"GRADIENT_FILL": False, "CONTOUR_FILL": False},
            },
            "DEFORM": {
                "OPT_CHECK": True,
                "SCALE_FACTOR": 2.0,
                "REL_DISP": True,
                "REAL_DISP": True,
                "REAL_DEFORM": True,
            },
        },
        "OUTPUT_SECT_LOCATION": {"OPT_I": True, "OPT_CENTER_MID": True, "OPT_J": True},
    }
    view.set_result_graphic(argument, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": argument}
