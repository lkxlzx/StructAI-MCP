/**
 * midas-nx read-only sanity check.
 *
 * Risk level: 1 - read-only (see https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels).
 * Verifies the connection and reads the current model's nodes. Does not
 * create, change, or delete anything - safe to run against a real project.
 * See quickstart.mjs for an example that builds a model instead.
 *
 * Requires a running MIDAS Gen NX (or Civil NX) with Open API connected - set
 * MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running:
 *
 *     node examples/javascript/verify-and-read.mjs
 *
 * This is the JavaScript twin of examples/python/verify_and_read.py.
 */
import { MidasClient, resources } from "midas-nx";

// Reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from the environment.
const client = new MidasClient({ product: "gen" });

console.log(await client.verifyConnection());

const nodes = await resources.db.nodeElement.node.items(client);
console.log(`Connected. Found ${Object.keys(nodes).length} node(s) in the current model.`);
