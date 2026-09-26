#!/usr/bin/env python3
"""midas_nx simple-beam load-combination example.

Ports the MIDAS-API manual repo's examples/python/simple_beam_load_combination.py
tutorial (https://support.midasuser.com/hc/en-us/articles/30230181806361) to
this SDK's DbResource classes. A 10m simply-supported beam (pinned/roller) is
split into 20 elements, given self-weight (DL) + a uniform beam load (SIDL),
then combined into a single load combination. A step up from quickstart.py's
single-column minimal example: node/element generation via a loop, boundary
conditions, and a multi-case load combination.

Requires a running MIDAS Civil NX (or Gen NX) with Open API connected — set
MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running.
"""
from midas_nx import MidasClient, Product, doc
from midas_nx.db.boundary import Constraint
from midas_nx.db.load_combinations import LoadCombinationGeneral
from midas_nx.db.node_element import Element, Node
from midas_nx.db.project import Unit
from midas_nx.db.properties.material import Material
from midas_nx.db.properties.section import Section
from midas_nx.db.static_loads import BeamLoad, SelfWeight, StaticLoadCase

client = MidasClient(product=Product.CIVIL)  # reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from env

# ── inputs ────────────────────────────────────────────────────────────────
length, height, width = 10.0, 1.0, 0.8  # beam length / section height / width (m)
beam_load = -30.0  # additional uniform load (kN/m, SIDL)
material_id, section_id = 1, 1
num_divisions = 20  # split the beam into 20 elements

# 1) New document
doc.new_project(client=client)

# 2) Units (m, kN)
Unit.update({1: {"DIST": "M", "FORCE": "KN"}}, client=client)

# 3) Material (RC C32)
Material.create(
    {1: {"TYPE": "CONC", "NAME": "C32", "PARAM": [{"P_TYPE": 1, "STANDARD": "AS17(RC)", "DB": "C32"}]}},
    client=client,
)

# 4) Section (rectangular, value input)
Section.create(
    {
        1: {
            "SECTTYPE": "DBUSER",
            "SECT_NAME": "Rectangular",
            "SECT_BEFORE": {
                "USE_SHEAR_DEFORM": True, "SHAPE": "SB", "DATATYPE": 2,
                "SECT_I": {"vSIZE": [height, width]},
            },
        }
    },
    client=client,
)

# 5) Nodes (0 to length, split into num_divisions)
interval = length / num_divisions
Node.create(
    {i + 1: {"X": round(i * interval, 6), "Y": 0.0, "Z": 0.0} for i in range(num_divisions + 1)},
    client=client,
)

# 6) Elements (connect adjacent nodes as BEAM)
Element.create(
    {
        i + 1: {"TYPE": "BEAM", "MATL": material_id, "SECT": section_id, "NODE": [i + 1, i + 2]}
        for i in range(num_divisions)
    },
    client=client,
)

# 7) Boundary conditions (pin at the start, roller at the end)
last_node_id = num_divisions + 1
Constraint.create(
    {
        1: {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111000"}]},
        last_node_id: {"ITEMS": [{"ID": 1, "CONSTRAINT": "0111000"}]},
    },
    client=client,
)

# 8) Load cases (DL for self-weight, SIDL for the additional load)
StaticLoadCase.create(
    {
        1: {"NAME": "DL", "TYPE": "USER", "DESC": "Dead Load"},
        2: {"NAME": "SIDL", "TYPE": "USER", "DESC": "Super Imposed Dead Load"},
    },
    client=client,
)

# 9) Self-weight (DL load case, -Z direction, factor 1)
SelfWeight.create({1: {"LCNAME": "DL", "FV": [0, 0, -1]}}, client=client)

# 10) Uniform beam load (SIDL, applied to every element)
BeamLoad.create(
    {
        i + 1: {
            "ITEMS": [{
                "ID": 1, "LCNAME": "SIDL", "CMD": "BEAM", "TYPE": "UNILOAD",
                "DIRECTION": "GZ", "D": [0, 1], "P": [beam_load, beam_load],
            }]
        }
        for i in range(num_divisions)
    },
    client=client,
)

# 11) Load combination (DL*1.2 + SIDL*1.5)
LoadCombinationGeneral.create(
    {
        1: {
            "NAME": "Comb1", "ACTIVE": "ACTIVE", "iTYPE": 0,
            "vCOMB": [
                {"ANAL": "ST", "LCNAME": "DL", "FACTOR": 1.2},
                {"ANAL": "ST", "LCNAME": "SIDL", "FACTOR": 1.5},
            ],
        }
    },
    client=client,
)

# 12) Save
doc.save(client=client)

print("Simple beam and load combination created.")
