#!/usr/bin/env node
/**
 * Live write verification for the npm package's public DB-resource surface.
 *
 * This deliberately lives beside the npm package and imports its built
 * `dist/index.js` entrypoint. It therefore exercises the API a package user
 * installs, rather than raw HTTP or Python implementation details. Case
 * payloads come only from schema/live-cases.json, emitted by Python's
 * scripts/live_crud_check.py; never copy a live payload into this file.
 * DESTRUCTIVE. Before any mutation it saves a timestamped checkpoint in an
 * explicitly configured directory on the NX machine, then calls /doc/NEW and
 * verifies the resulting document is empty. /doc/NEW DISCARDS UNSAVED WORK and
 * has crashed Gen NX on a large real model, so never point this at a session
 * holding a document that matters - get the open document confirmed disposable
 * first. An authenticated MAPI user is not a reliable Windows-profile name, so
 * never derive a server path from it.
 * --no-save-before skips the checkpoint, not the /doc/NEW. It leaves the open
 * document discarded with no backup; pass it only when that was reviewed.
 *
 * Usage:
 *   MIDAS_MAPI_KEY=... MIDAS_NX_SAVE_DIR=E:/NX-Scratch \\
 *     npm run live:crud -- -- --product gen --endpoints /db/NODE,/db/NMAS
 *
 * This script intentionally requires an explicit endpoint selection. A broad
 * accidental run is not a useful substitute for reviewing fixtures in small
 * batches against an empty scratch document.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  caseCleanupMode, classifyResult, containsExpectedValue, exitCodeFor,
  replacedBaseModelRecord, seedSteps, setupCleanupMode, supportedCaseWrites,
  verifyRenumberedSeed,
} from "./live-harness-support.mjs";

// Loaded in main(), after the arguments are checked, so a refused command
// line is refused without a build: tests/live-crud-cli.test.mjs runs before
// `npm run build` in CI and in prepack, where dist/ does not exist yet.
let doc, MidasClient, post, resources;

const fixturePath = fileURLToPath(new URL("../../../schema/live-cases.json", import.meta.url));
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));

// Pinned so a stale checkout fails loudly instead of silently building an
// older model. tests/test_live_cases.py fails if this drifts from
// LIVE_CASES_VERSION in scripts/live_crud_check.py.
const EXPECTED_FIXTURE_VERSION = 6;

function usage(message) {
  if (message) console.error(message);
  console.error("Usage: npm run live:crud -- -- --product gen|civil --endpoints /db/NODE,/db/NMAS [--table-type MASS_SUMMARY_X] [--save-dir E:/NX-Scratch] [--no-save-before] [--mapi-key key] [--timeout ms]");
  console.error("DESTRUCTIVE: this calls /doc/NEW and discards the open document. --no-save-before removes the checkpoint, not the /doc/NEW.");
  process.exit(2);
}

function parseArgs(argv) {
  const args = {
    timeout: 30_000,
    saveBefore: true,
    saveDir: process.env.MIDAS_NX_SAVE_DIR,
    // Keep the documented non-shell-history path working; an explicit
    // --mapi-key remains available for an intentionally one-off session.
    mapiKey: process.env.MIDAS_MAPI_KEY,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--no-save-before") {
      args.saveBefore = false;
    } else if (flag === "--endpoints") {
      if (!value || value.startsWith("--")) usage("--endpoints needs a value.");
      const endpoints = [value];
      while (argv[index + 2] && !argv[index + 2].startsWith("--")) {
        endpoints.push(argv[index + 2]);
        index += 1;
      }
      // npm on PowerShell can split a comma-separated value into separate
      // argv tokens. Accept both that form and the documented comma form.
      args.endpoints = endpoints.join(",");
      index += 1;
    } else if (flag === "--product" || flag === "--table-type" || flag === "--save-dir" || flag === "--mapi-key" || flag === "--timeout") {
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
  if (!args.endpoints) usage("--endpoints is required; select a reviewed small batch.");
  args.timeout = Number(args.timeout);
  if (!Number.isFinite(args.timeout) || args.timeout <= 0) usage("--timeout must be a positive number of milliseconds.");
  if (args.saveBefore && !args.saveDir) {
    usage("Set --save-dir (or MIDAS_NX_SAVE_DIR) to a known writable directory on the NX machine; the signed-in API user is not a safe path source.");
  }
  // Checked here and not only in checkpointPath: that call sits after
  // verifyConnection, so a malformed path used to cost a connection before
  // saying so. Nothing about the shape needs a product to judge it.
  if (args.saveBefore && !isAbsoluteHostDirectory(args.saveDir)) {
    usage(`--save-dir must be an absolute Windows directory on the NX machine, got ${JSON.stringify(args.saveDir)}.`);
  }
  return args;
}

function isAbsoluteHostDirectory(saveDir) {
  return /^[A-Za-z]:\/[^\0]*$/.test(saveDir.replaceAll("\\", "/").replace(/\/+$/, ""));
}

function checkpointPath(product, saveDir) {
  const directory = saveDir.replaceAll("\\", "/").replace(/\/+$/, "");
  if (!isAbsoluteHostDirectory(saveDir)) {
    throw new Error(`--save-dir must be an absolute Windows directory on the NX machine, got ${JSON.stringify(saveDir)}.`);
  }
  // Product-native NX extension: Gen NX .mgbx, Civil NX .mcbz
  // (author-confirmed 2026-08-31; .mgb/.mcb are the pre-NX pair).
  const extension = product === "civil" ? "mcbz" : "mgbx";
  return `${directory}/midas-nx-live-${product}-${Date.now()}.${extension}`;
}

function isResource(value) {
  return typeof value === "object" && value !== null &&
    typeof value.create === "function" && typeof value.items === "function" &&
    typeof value.delete === "function" && typeof value.metadata?.endpoint === "string";
}

function findResource(value, endpoint, visited = new Set()) {
  if (typeof value !== "object" || value === null || visited.has(value)) return undefined;
  visited.add(value);
  if (isResource(value) && value.metadata.endpoint === endpoint) return value;
  for (const child of Object.values(value)) {
    const found = findResource(child, endpoint, visited);
    if (found) return found;
  }
  return undefined;
}

function caseFor(endpoint, product) {
  return fixture.cases.find(
    (candidate) => candidate.endpoint === endpoint
      && (!product || candidate.products.includes(product)),
  );
}

function resourceFor(endpoint) {
  const resource = findResource(resources.db, endpoint);
  if (!resource) throw new Error(`${endpoint}: no public resources.db entry exists in the built npm package.`);
  return resource;
}

/**
 * One prerequisite becomes one or more POST or per-id DELETE steps, replayed
 * in the emitted order.
 */
function setupRecords(prerequisite, targetEndpoint) {
  if (typeof prerequisite.seed === "string") {
    // A seed built from several calls is emitted as a "steps" list; a
    // one-call seed keeps the flat shape the base model also uses.
    try {
      return seedSteps(fixture.seeds?.[prerequisite.seed], prerequisite.seed);
    } catch (error) {
      throw new Error(`${targetEndpoint}: ${errorText(error)}`);
    }
  }
  if (typeof prerequisite.endpoint !== "string" || !Number.isInteger(prerequisite.id)) {
    throw new Error(`${targetEndpoint}: fixture setup must name a seed or an endpoint/id source case.`);
  }
  const source = caseFor(prerequisite.endpoint);
  if (!source) throw new Error(`${targetEndpoint}: fixture setup ${prerequisite.endpoint} has no source case.`);
  return [{
    endpoint: prerequisite.endpoint,
    records: { [prerequisite.id]: source.createPayload },
    replaceExisting: false,
  }];
}

function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}

function requireStored(items, id, endpoint, step) {
  const stored = items[id];
  if (!stored) throw new Error(`${endpoint}: id ${id} missing after ${step}.`);
  return stored;
}

function newlyCreatedIds(before, after) {
  return Object.keys(after)
    .map(Number)
    .filter((id) => !Object.hasOwn(before, id));
}

function requireExpectedValue(value, expected, endpoint, step, unordered) {
  if (expected === null || expected === undefined) return;
  if (!containsExpectedValue(value, expected, { unordered })) {
  throw new Error(`${endpoint}: expected live value ${JSON.stringify(expected)} after ${step}.`);
  }
}

function assertPayloadDefaults(resource, stored, endpoint, step) {
  for (const [key, expected] of Object.entries(resource.metadata.payloadDefaults ?? {})) {
    if (!Object.is(stored[key], expected)) {
      throw new Error(`${endpoint}: payloadDefaults.${key} was not read back as ${JSON.stringify(expected)} after ${step}.`);
    }
  }
}

async function deleteAndVerify(resource, id, client, endpoint) {
  await resource.delete([id], client);
  if (Object.hasOwn(await resource.items(client), id)) {
    throw new Error(`${endpoint}: id ${id} remains after individual DELETE.`);
  }
}

async function requireEmptyScratchDocument(client) {
  const node = resourceFor("/db/NODE");
  const element = resourceFor("/db/ELEM");
  const [nodes, elements] = await Promise.all([node.items(client), element.items(client)]);
  if (Object.keys(nodes).length || Object.keys(elements).length) {
    throw new Error("/doc/NEW did not leave an empty NODE/ELEM scratch document; refusing live mutations.");
  }
}

/**
 * Build the model every case attaches to, from the shared fixture.
 *
 * This harness used to start each case against a genuinely empty /doc/NEW,
 * so thirteen cases that pass under Python failed here on missing
 * node/element/material/section preconditions and printed REGRESS for a
 * model that was never built. The steps come from schema/live-cases.json's
 * baseModel, which Python emits from the same list its own _seed_model
 * executes - never hand-write one here.
 */
async function buildBaseModel(client) {
  const steps = fixture.baseModel;
  if (!Array.isArray(steps) || !steps.length) {
    throw new Error("The shared fixture has no baseModel; re-emit it with python scripts/live_crud_check.py --emit-cases.");
  }
  for (const step of steps) {
    const resource = resourceFor(step.endpoint);
    const ids = Object.keys(step.records).map(Number);
    if (step.method === "PUT") {
      await resource.update(step.records, client);
    } else {
      await resource.create(step.records, client);
    }
    const stored = await resource.items(client);
    for (const id of ids) {
      requireStored(stored, id, step.endpoint, `base model ${step.method}`);
    }
  }
  console.log(`BUILT base model (${steps.length} steps)`);
}

async function runCase(liveCase, client, cleanupContext) {
  const resource = resourceFor(liveCase.endpoint);
  const cleanupMode = caseCleanupMode(
    liveCase.methods, resource.metadata.methods, cleanupContext,
  );
  if (cleanupMode === "unsafe") {
    throw new Error(
      `${liveCase.endpoint}: a no-DELETE case must run last and be followed by a document reset.`,
    );
  }
  const setup = [];
  const targetCreatedIds = new Set();
  let result;
  // A failure before the endpoint under test is touched says nothing about
  // that endpoint, so it is reported blocked rather than as a regression --
  // the same split scripts/live_crud_check.py makes for a failed seed step.
  let phase = "setup";
  try {
    for (const prerequisite of liveCase.setup) {
      for (const source of setupRecords(prerequisite, liveCase.endpoint)) {
        const sourceResource = resourceFor(source.endpoint);
        if (source.deleteIds) {
          // A seed that clears a record the fresh document supplies. Nothing
          // to clean up afterwards: the document reset restores it.
          if (!sourceResource.metadata.methods.includes("DELETE")) {
            throw new Error(`${liveCase.endpoint}: setup ${source.endpoint} has no DELETE to replay.`);
          }
          for (const id of source.deleteIds) {
            await deleteAndVerify(sourceResource, id, client, source.endpoint);
          }
          continue;
        }
        const sourceCleanupMode = setupCleanupMode(
          sourceResource.metadata.methods, cleanupContext,
        );
        if (sourceCleanupMode === "unsafe") {
          throw new Error(`${liveCase.endpoint}: setup ${source.endpoint} cannot be individually cleaned up.`);
        }
        const before = await sourceResource.items(client);
        const requestedIds = Object.keys(source.records).map(Number);
        const collisions = requestedIds.filter((id) => Object.hasOwn(before, id));
        if (collisions.length && !source.replaceExisting) {
          for (const id of collisions) {
            throw new Error(`${liveCase.endpoint}: setup ${source.endpoint}/${id} already exists; refusing to overwrite a scratch record.`);
          }
        }
        for (const id of collisions) {
          await deleteAndVerify(sourceResource, id, client, source.endpoint);
        }
        await sourceResource.create(source.records, client);
        const after = await sourceResource.items(client);
        const createdIds = newlyCreatedIds(before, after);
        setup.push({
          resource: sourceResource, ids: createdIds, endpoint: source.endpoint,
          cleanupMode: sourceCleanupMode,
          // A collision this step was allowed to overwrite. It is absent from
          // createdIds because the id existed in `before`, so cleanup has to
          // be told about it explicitly.
          replacedIds: collisions,
        });
        if (source.allowRenumbering) {
          verifyRenumberedSeed(source, after, createdIds);
        } else {
          for (const id of requestedIds) requireStored(after, id, source.endpoint, "setup POST");
        }
      }
    }

    phase = "case";
    const before = await resource.items(client);
    const { supportsPost, supportsPut } = supportedCaseWrites(
      liveCase.methods, resource.metadata.methods,
    );
    if (!supportsPost && !supportsPut) {
      throw new Error(`${liveCase.endpoint}: fixture has neither a POST nor PUT write operation.`);
    }
    if (supportsPost && Object.hasOwn(before, liveCase.id)) {
      throw new Error(`${liveCase.endpoint}/${liveCase.id} already exists; refusing to overwrite a scratch record.`);
    }
    if (supportsPost) {
      await resource.create({ [liveCase.id]: liveCase.createPayload }, client);
      const afterCreate = await resource.items(client);
      for (const id of newlyCreatedIds(before, afterCreate)) targetCreatedIds.add(id);
      const created = requireStored(afterCreate, liveCase.id, liveCase.endpoint, "POST");
      requireExpectedValue(
        created, liveCase.expected.created, liveCase.endpoint, "POST",
        liveCase.expected.unordered === true,
      );
      assertPayloadDefaults(resource, created, liveCase.endpoint, "POST");
    }

    if (supportsPut) {
      const beforeUpdate = await resource.items(client);
      await resource.update({ [liveCase.id]: liveCase.updatePayload }, client);
      const afterUpdate = await resource.items(client);
      for (const id of newlyCreatedIds(beforeUpdate, afterUpdate)) targetCreatedIds.add(id);
      const updated = requireStored(afterUpdate, liveCase.id, liveCase.endpoint, "PUT");
      requireExpectedValue(
        updated, liveCase.expected.updated, liveCase.endpoint, "PUT",
        liveCase.expected.unordered === true,
      );
      assertPayloadDefaults(resource, updated, liveCase.endpoint, "PUT");
    }

    if (cleanupMode === "per-id") {
      await deleteAndVerify(resource, liveCase.id, client, liveCase.endpoint);
      targetCreatedIds.delete(liveCase.id);
    }
    result = { endpoint: liveCase.endpoint, ok: true, confirmed: liveCase.confirmed };
  } catch (error) {
    result = {
      endpoint: liveCase.endpoint, ok: false, confirmed: liveCase.confirmed,
      blocked: phase === "setup", error: errorText(error),
    };
  } finally {
    const cleanupErrors = [];
    for (const id of cleanupMode === "per-id" ? targetCreatedIds : []) {
      try {
        await deleteAndVerify(resource, id, client, liveCase.endpoint);
      } catch (error) {
        cleanupErrors.push(`${liveCase.endpoint}/${id}: ${errorText(error)}`);
      }
    }
    for (const prerequisite of setup.reverse()) {
      if (prerequisite.cleanupMode === "document-reset") continue;
      for (const id of prerequisite.ids) {
        try {
          await deleteAndVerify(prerequisite.resource, id, client, prerequisite.endpoint);
        } catch (error) {
          cleanupErrors.push(`${prerequisite.endpoint}/${id}: ${errorText(error)}`);
        }
      }
      for (const id of prerequisite.replacedIds ?? []) {
        const original = replacedBaseModelRecord(
          fixture.baseModel, prerequisite.endpoint, id,
        );
        try {
          await deleteAndVerify(prerequisite.resource, id, client, prerequisite.endpoint);
          if (original) {
            await prerequisite.resource.create({ [id]: original }, client);
            requireStored(
              await prerequisite.resource.items(client), id,
              prerequisite.endpoint, "base model restore",
            );
          }
        } catch (error) {
          // Left unrestored, the next case in this invocation runs against a
          // base model that is no longer the one the fixture describes, and
          // reports a defect the SDK does not have. Fail loudly instead.
          cleanupErrors.push(
            `${prerequisite.endpoint}/${id} (base model restore): ${errorText(error)}`,
          );
        }
      }
    }
    if (cleanupErrors.length) {
      result = {
        ...result,
        ok: false,
        error: [result.error, `Cleanup failed: ${cleanupErrors.join("; ")}`].filter(Boolean).join("; "),
      };
    }
  }
  return result;
}

/**
 * Exercise the public /post/TABLE adapter with real data.  The records come
 * from the shared fixture, including the Nodal Mass omitted-default case;
 * do not add a second hand-written payload here.
 */
async function runPopulatedTable(tableType, client) {
  const nodeCase = caseFor("/db/NODE", client.product);
  const massCase = caseFor("/db/NMAS", client.product);
  if (!nodeCase || !massCase) throw new Error("The shared fixture must contain /db/NODE and /db/NMAS cases.");

  const node = resourceFor(nodeCase.endpoint);
  const mass = resourceFor(massCase.endpoint);
  const id = 900_301;
  let nodeCreated = false;
  let massCreated = false;
  let result;
  try {
    await node.create({ [id]: nodeCase.createPayload }, client);
    nodeCreated = true;
    requireStored(await node.items(client), id, nodeCase.endpoint, "table seed POST");

    await mass.create({ [id]: massCase.createPayload }, client);
    massCreated = true;
    const storedMass = requireStored(await mass.items(client), id, massCase.endpoint, "table seed POST");
    assertPayloadDefaults(mass, storedMass, massCase.endpoint, "table seed POST");

    const raw = await post.getTable(tableType, {
      client,
      nodeElements: { keys: [id] },
    });
    const table = post.unwrapTable(raw);
    if (!Array.isArray(table.HEAD) || !Array.isArray(table.DATA) || table.DATA.length === 0) {
      throw new Error(`/post/TABLE ${tableType}: expected populated HEAD/DATA table, received ${JSON.stringify(raw)}.`);
    }
    result = {
      endpoint: `/post/TABLE ${tableType}`,
      ok: true,
      // This is the documented table whose populated shape was observed on
      // both products on 2026-08-31. Other caller-selected table types still
      // need fixture/ledger triage before a failure can be called regression.
      confirmed: tableType === "MASS_SUMMARY_X",
      keys: Object.keys(raw),
      rows: table.DATA.length,
    };
  } catch (error) {
    result = {
      endpoint: `/post/TABLE ${tableType}`,
      ok: false,
      confirmed: tableType === "MASS_SUMMARY_X",
      error: errorText(error),
    };
  } finally {
    const cleanupErrors = [];
    if (massCreated) {
      try {
        await deleteAndVerify(mass, id, client, massCase.endpoint);
      } catch (error) {
        cleanupErrors.push(`${massCase.endpoint}: ${errorText(error)}`);
      }
    }
    if (nodeCreated) {
      try {
        await deleteAndVerify(node, id, client, nodeCase.endpoint);
      } catch (error) {
        cleanupErrors.push(`${nodeCase.endpoint}: ${errorText(error)}`);
      }
    }
    if (cleanupErrors.length) {
      result = {
        ...result,
        ok: false,
        error: [result.error, `Cleanup failed: ${cleanupErrors.join("; ")}`].filter(Boolean).join("; "),
      };
    }
  }
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  ({ doc, MidasClient, post, resources } = await import("../dist/index.js"));
  const selected = args.endpoints
    .split(/[\s,]+/)
    // npm 12 on Windows can retain cmd.exe's caret quoting around a path.
    // Caret is not valid in a MIDAS endpoint, so normalizing it is unambiguous.
    .map((endpoint) => endpoint.replaceAll("^", ""))
    .filter(Boolean);
  if (fixture.version !== EXPECTED_FIXTURE_VERSION) {
    throw new Error(
      `schema/live-cases.json is version ${fixture.version}, this harness expects `
      + `${EXPECTED_FIXTURE_VERSION}. Re-emit it with `
      + "python scripts/live_crud_check.py --emit-cases, or update this checkout.",
    );
  }
  const client = new MidasClient({ mapiKey: args.mapiKey, product: args.product, timeout: args.timeout });
  const cases = selected.map(
    (endpoint) => caseFor(endpoint, args.product)
      ?? usage(`${endpoint}: no ${args.product} case in ${fixturePath}.`),
  );
  const health = await client.verifyConnection();
  if (health.status !== "connected") throw new Error(`Server reachable but not connected: ${JSON.stringify(health)}`);
  if (args.saveBefore) {
    const path = checkpointPath(args.product, args.saveDir);
    await doc.saveAs(path, { client });
    console.log(`SAVED ${path}`);
  }
  await doc.newProject({ client });
  await requireEmptyScratchDocument(client);
  console.log("CREATED empty scratch document");
  await buildBaseModel(client);

  const results = [];
  for (const [caseIndex, liveCase] of cases.entries()) {
    if (!liveCase.products.includes(args.product)) {
      console.log(`SKIP ${liveCase.endpoint} does not support ${args.product}.`);
      continue;
    }
    // Some Python seed steps read state back or delete a record, which this
    // harness cannot replay from an emitted POST. The fixture names those and
    // says why, so report the case blocked rather than running it with the
    // setup silently shortened and reading the result as an SDK defect.
    const blockedSeeds = liveCase.blockedSeeds ?? [];
    if (blockedSeeds.length) {
      const why = blockedSeeds
        .map((name) => `${name} (${fixture.unsupportedSeeds?.[name] ?? "reason not emitted"})`)
        .join("; ");
      const result = {
        endpoint: liveCase.endpoint, ok: false, confirmed: liveCase.confirmed,
        blocked: true, error: `the shared fixture cannot express seed ${why}`,
      };
      results.push(result);
      console.log(`${classifyResult(result)} ${result.endpoint} ${result.error}`);
      continue;
    }
    const result = await runCase(liveCase, client, {
      finalCase: caseIndex === cases.length - 1 && !args.tableType,
      resetDocument: args.saveBefore,
    });
    results.push(result);
    console.log(`${classifyResult(result)} ${result.endpoint}${result.error ? ` ${result.error}` : ""}`);
  }
  if (args.tableType) {
    const result = await runPopulatedTable(args.tableType, client);
    results.push(result);
    console.log(`${classifyResult(result)} ${result.endpoint}${result.ok ? ` keys=${result.keys.join(",")} rows=${result.rows}` : ` ${result.error}`}`);
  }
  const exitCode = exitCodeFor(results);

  // Cases leave a throwaway model dirty even when every record was deleted.
  // Save that model to a different timestamped checkpoint before /doc/NEW so
  // the next live run cannot be blocked by NX's modal save-changes prompt.
  if (args.saveBefore) {
    const finalPath = checkpointPath(args.product, args.saveDir);
    await doc.saveAs(finalPath, { client });
    console.log(`SAVED throwaway model ${finalPath}`);
    await doc.newProject({ client });
    await requireEmptyScratchDocument(client);
    console.log("RESTORED empty scratch document");
  }
  return exitCode;
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(errorText(error));
  process.exitCode = 2;
});
