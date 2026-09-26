#!/usr/bin/env python3
"""midas_nx read-only sanity check.

Risk level: 1 - read-only (see docs/safety.md#risk-levels). Verifies the
connection and reads the current model's nodes. Does not create, change, or
delete anything - safe to run against a real project. See quickstart.py for
an example that builds a model instead.

Requires a running MIDAS Gen NX (or Civil NX) with Open API connected — set
MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running.
"""
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

client = MidasClient(product=Product.GEN)  # reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from env

print(client.verify_connection())

nodes = Node.items(client=client)
print(f"Connected. Found {len(nodes)} node(s) in the current model.")
