#!/usr/bin/env python3
"""midas_nx KDS 41 12:2022 wind-load example.

Creates a plate element and applies a pressure (wind) load to it, per
docs/manual/06_DB_Static_Loads.md #10 (/db/PRES) in the MIDAS-API manual
repo. Requires a running MIDAS Gen NX/Civil NX with Open API connected.
"""
from midas_nx import MidasClient, Product, doc
from midas_nx.db.node_element import Element, Node
from midas_nx.db.project import Unit
from midas_nx.db.properties.thickness import Thickness
from midas_nx.db.static_loads import PressureLoad, StaticLoadCase

client = MidasClient(product=Product.GEN)

doc.new_project(client=client)
Unit.update({1: {"DIST": "M", "FORCE": "KN"}}, client=client)

# Wind load case (KDS 41 12:2022)
StaticLoadCase.create(
    {1: {"NAME": "WIND_X_KDS", "TYPE": "W", "DESC": "KDS 풍하중 X방향"}},
    client=client,
)

# 3x3m plate at Z=5
Node.create(
    {
        1: {"X": 0, "Y": 0, "Z": 5},
        2: {"X": 3, "Y": 0, "Z": 5},
        3: {"X": 3, "Y": 3, "Z": 5},
        4: {"X": 0, "Y": 3, "Z": 5},
    },
    client=client,
)

Thickness.create(
    {1: {"NAME": "T1000", "TYPE": "VALUE", "bINOUT": False, "T_IN": 1.0, "T_OUT": 0, "O_VALUE": 0}},
    client=client,
)

Element.create(
    {1: {"TYPE": "PLATE", "SECT": 1, "NODE": [1, 2, 3, 4], "STYPE": 1}},
    client=client,
)

# Pressure load: 1.5 kN/m^2, global X direction (negative = suction)
PressureLoad.create(
    {
        1: {
            "ITEMS": [
                {
                    "ID": 1,
                    "LCNAME": "WIND_X_KDS",
                    "CMD": "PRES",
                    "ELEM_TYPE": "PLATE",
                    "FACE_EDGE_TYPE": "FACE",
                    "DIRECTION": "GX",
                    "EDGE_FACE": 1,
                    "FORCES": [-1.5, 0, 0, 0, 0],
                }
            ]
        }
    },
    client=client,
)

doc.save(client=client)
doc.analyze(client=client)

print("Wind load applied and analysis run.")
