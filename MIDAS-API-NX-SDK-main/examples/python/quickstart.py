#!/usr/bin/env python3
"""midas_nx quick start - creates a model. See verify_and_read.py for a
read-only alternative that is safe to run against a real project.

Risk level: 4 - high risk (see docs/safety.md#risk-levels).

Ports the MIDAS-API manual repo's README quick-start example: create a new
document, set units, define a material/section, place two nodes, connect
them with a column element, then save.

WARNING: doc.new_project() discards any unsaved work in whatever document is
currently open in Gen NX/Civil NX, even work unrelated to this script. Only
run this against a blank project, or one you don't mind losing unsaved
changes in.

Requires a running MIDAS Gen NX (or Civil NX) with Open API connected — set
MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running.
"""
from midas_nx import MidasClient, Product, doc
from midas_nx.db.node_element import Element, Node
from midas_nx.db.project import Unit
from midas_nx.db.properties.material import Material
from midas_nx.db.properties.section import Section

client = MidasClient(product=Product.GEN)  # reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from env

# 1) New document
doc.new_project(client=client)

# 2) Units (m, tonf)
Unit.update({1: {"DIST": "M", "FORCE": "TONF"}}, client=client)

# 3) Material (RC)
Material.create(
    {
        1: {
            "TYPE": "CONC",
            "NAME": "C32",
            "PARAM": [{"P_TYPE": 1, "STANDARD": "AS17(RC)", "DB": "C32"}],
        }
    },
    client=client,
)

# 4) Section (rectangular column)
Section.create(
    {
        1: {
            "SECTTYPE": "DBUSER",
            "SECT_NAME": "H300x150",
            "SECT_BEFORE": {
                "SHAPE": "H",
                "OFFSET_PT": "CC",
                "DATATYPE": 1,  # 1=DB, 2=User — sibling of SECT_I, not nested inside it
                "SECT_I": {"DB_NAME": "KS21", "SECT_NAME": "H300x150x6.5/9"},
            },
        }
    },
    client=client,
)

# 5) Two nodes
Node.create(
    {
        1: {"X": 0, "Y": 0, "Z": 0},
        2: {"X": 0, "Y": 0, "Z": 3.2},
    },
    client=client,
)

# 6) Column element (BEAM type)
Element.create(
    {1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2], "ANGLE": 0}},
    client=client,
)

# 7) Save
doc.save(client=client)

print("Model created.")
