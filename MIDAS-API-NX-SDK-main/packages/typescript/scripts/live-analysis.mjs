#!/usr/bin/env node
/**
 * Build, save, analyse, read and clean a disposable column through the npm
 * package's public API. This is intentionally separate from live-crud.mjs:
 * result tables require a solved model, not a pre-process CRUD fixture.
 */
import { doc, MidasClient, post, resources } from "../dist/index.js";

const endpointNames = {
  unit: "/db/UNIT", material: "/db/MATL", section: "/db/SECT",
  node: "/db/NODE", element: "/db/ELEM", constraint: "/db/CONS",
  staticLoad: "/db/STLD", selfWeight: "/db/BODF",
};

function usage(message) {
  if (message) console.error(message);
  console.error("Usage: npm run live:analysis -- -- --product gen|civil --save-dir C:/temp [--mapi-key key] [--timeout ms]");
  process.exit(2);
}

function parseArgs(argv) {
  const args = { timeout: 30_000, saveDir: process.env.MIDAS_NX_SAVE_DIR, mapiKey: process.env.MIDAS_MAPI_KEY };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--product" || flag === "--save-dir" || flag === "--mapi-key" || flag === "--timeout") {
      if (!value || value.startsWith("--")) usage(`${flag} needs a value.`);
      args[flag.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
      index += 1;
    } else if (flag === "--help" || flag === "-h") {
      usage();
    } else {
      usage(`Unknown option: ${flag}`);
    }
  }
  if (args.product !== "gen" && args.product !== "civil") usage("--product must be gen or civil.");
  if (!args.saveDir) usage("Set --save-dir (or MIDAS_NX_SAVE_DIR) to a known writable directory on the NX machine.");
  args.timeout = Number(args.timeout);
  if (!Number.isFinite(args.timeout) || args.timeout <= 0) usage("--timeout must be a positive number of milliseconds.");
  return args;
}

function findResource(value, endpoint, visited = new Set()) {
  if (typeof value !== "object" || value === null || visited.has(value)) return undefined;
  visited.add(value);
  if (value.metadata?.endpoint === endpoint && typeof value.create === "function") return value;
  for (const child of Object.values(value)) {
    const found = findResource(child, endpoint, visited);
    if (found) return found;
  }
  return undefined;
}

function resourceFor(name) {
  const resource = findResource(resources.db, endpointNames[name]);
  if (!resource) throw new Error(`The public npm package does not expose ${endpointNames[name]}.`);
  return resource;
}

function checkpointPath(product, saveDir, label) {
  const directory = saveDir.replaceAll("\\", "/").replace(/\/+$/, "");
  if (!/^[A-Za-z]:\/[^\0]*$/.test(directory)) throw new Error(`--save-dir must be an absolute Windows directory, got ${JSON.stringify(saveDir)}.`);
  // Product-native NX extension: Gen NX .mgbx, Civil NX .mcbz (author-confirmed 2026-08-31).
  return `${directory}/midas-nx-${label}-${product}-${Date.now()}.${product === "civil" ? "mcbz" : "mgbx"}`;
}

async function requireEmpty(resourcesToCheck, client) {
  for (const resource of resourcesToCheck) {
    const items = await resource.items(client);
    if (Object.keys(items).length) throw new Error(`${resource.metadata.endpoint} is not empty; refusing to create the analysis fixture.`);
  }
}

async function deleteOne(resource, id, client) {
  await resource.delete([id], client);
  if (Object.hasOwn(await resource.items(client), id)) throw new Error(`${resource.metadata.endpoint}/${id} remained after individual DELETE.`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const client = new MidasClient({ mapiKey: args.mapiKey, product: args.product, timeout: args.timeout });
  const health = await client.verifyConnection();
  if (health.status !== "connected") throw new Error(`Server reachable but not connected: ${JSON.stringify(health)}`);

  const model = Object.fromEntries(Object.keys(endpointNames).map((name) => [name, resourceFor(name)]));
  await requireEmpty([model.material, model.section, model.node, model.element, model.constraint, model.staticLoad, model.selfWeight], client);
  const beforeUnit = await model.unit.items(client);
  const created = [];
  try {
    await doc.saveAs(checkpointPath(args.product, args.saveDir, "before-analysis"), { client });
    await model.unit.update({ 1: { DIST: "M", FORCE: "KN" } }, client);
    await model.material.create({ 1: { TYPE: "CONC", NAME: "C24", PARAM: [{ P_TYPE: 1, STANDARD: "KS01(RC)", DB: "C24" }] } }, client); created.push([model.material, 1]);
    await model.section.create({ 1: { SECTTYPE: "DBUSER", SECT_NAME: "Column", SECT_BEFORE: { USE_SHEAR_DEFORM: true, SHAPE: "SB", DATATYPE: 2, SECT_I: { vSIZE: [0.6, 0.6] } } } }, client); created.push([model.section, 1]);
    await model.node.create({ 1: { X: 0, Y: 0, Z: 0 }, 2: { X: 0, Y: 0, Z: 3.2 } }, client); created.push([model.node, 1], [model.node, 2]);
    await model.element.create({ 1: { TYPE: "BEAM", MATL: 1, SECT: 1, NODE: [1, 2] } }, client); created.push([model.element, 1]);
    await model.constraint.create({ 1: { ITEMS: [{ ID: 1, CONSTRAINT: "1111111" }] } }, client); created.push([model.constraint, 1]);
    await model.staticLoad.create({ 1: { NAME: "DL", TYPE: "D", DESC: "npm analysed fixture" } }, client); created.push([model.staticLoad, 1]);
    await model.selfWeight.create({ 1: { LCNAME: "DL", FV: [0, 0, -1] } }, client); created.push([model.selfWeight, 1]);
    const saved = checkpointPath(args.product, args.saveDir, "analysis-model");
    await doc.saveAs(saved, { client });
    console.log(`SAVED ${saved}`);
    await doc.analyze(undefined, { client, timeout: args.timeout });
    for (const tableType of ["REACTIONG", "DISPLACEMENTG", "BEAMFORCE"]) {
      const raw = await post.getTable(tableType, { client, loadCaseNames: ["DL(ST)"], nodeElements: { keys: [1] } });
      const table = post.unwrapTable(raw);
      if (!Array.isArray(table.HEAD) || !Array.isArray(table.DATA) || table.DATA.length === 0) throw new Error(`${tableType} was not a populated HEAD/DATA table: ${JSON.stringify(raw)}.`);
      console.log(`PASS /post/TABLE ${tableType} rows=${table.DATA.length} keys=${Object.keys(raw).join(",")}`);
    }
  } finally {
    for (const [resource, id] of created.reverse()) await deleteOne(resource, id, client);
    if (Object.keys(beforeUnit).length) await model.unit.update(beforeUnit, client);
  }
}

main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
