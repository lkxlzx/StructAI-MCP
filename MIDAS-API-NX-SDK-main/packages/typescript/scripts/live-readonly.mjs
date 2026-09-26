#!/usr/bin/env node
/**
 * Live read-only sweep of the npm package's public resource surface.
 *
 * The safe counterpart to live-crud.mjs, and the npm counterpart to Python's
 * scripts/live_readonly_sweep.py. It issues GET only, so it can run against a
 * document someone is working in - it calls no /doc/NEW, sends no body, and
 * touches nothing the product would ask about. That is what makes it the one
 * to reach for first when a patch lands or a session needs checking.
 *
 * Like live-crud.mjs it imports the built `dist/` entrypoint rather than the
 * TypeScript sources, so what it proves is what an installed package does. A
 * route this sweep answers on is a route the npm surface addresses correctly:
 * the endpoint string, the product gate and the response unwrapping all come
 * from the generated metadata, and a wrong one shows up as a 404 here.
 *
 * What a clean run does and does not prove. It proves every declared route
 * exists, answers, and parses - which is exactly what catches a renamed
 * endpoint or a product declared for the wrong one. It proves nothing about
 * request *shapes*: every field-name, enum and default defect this repo has
 * found was invisible to a GET, because the server never saw a payload. Use
 * live-crud.mjs for that, on a document that can be discarded.
 *
 * One caveat that is not about data safety: a GET can still raise a modal
 * dialog on the NX machine if the open document lives somewhere the account
 * cannot write, because some read-shaped commands write an auxiliary file
 * beside it. Keep working documents off Program Files-style paths.
 *
 * Usage:
 *   MIDAS_MAPI_KEY=... npm run live:readonly -- -- --product gen
 *   npm run live:readonly -- -- --product civil --resource /db/SECT --out report.json
 *
 * In Git Bash, prefix with MSYS_NO_PATHCONV=1 or `--resource /db/SECT` is
 * rewritten into a Windows path before Node ever sees it - the same trap
 * CLAUDE.md documents for scripts/gen_endpoint.py.
 */
import { writeFileSync } from "node:fs";

import { MidasClient, resources } from "../dist/index.js";

function usage(message) {
  if (message) console.error(message);
  console.error(
    "Usage: npm run live:readonly -- -- --product gen|civil [--resource /db/SECT] [--out report.json] [--mapi-key key] [--timeout ms]",
  );
  console.error("GET only: safe against an open document. Use live-crud.mjs to verify write shapes.");
  process.exit(2);
}

function parseArgs(argv) {
  const args = { timeout: 60_000, mapiKey: process.env.MIDAS_MAPI_KEY };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--product" || flag === "--resource" || flag === "--out" || flag === "--mapi-key" || flag === "--timeout") {
      if (!value || value.startsWith("--")) usage(`${flag} needs a value.`);
      // `--mapi-key` reaches the options object as `mapiKey`, matching
      // live-crud.mjs so the two harnesses take the same flags.
      args[flag.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
      index += 1;
    } else if (flag === "--help" || flag === "-h") {
      usage();
    } else {
      usage(`Unknown option: ${flag}`);
    }
  }
  if (args.product !== "gen" && args.product !== "civil") usage("--product must be gen or civil.");
  args.timeout = Number(args.timeout);
  if (!Number.isFinite(args.timeout) || args.timeout <= 0) usage("--timeout must be a positive number of milliseconds.");
  return args;
}

/** Every resource in the generated tree, with the path a caller would type. */
function collect(node, path, found) {
  for (const [key, value] of Object.entries(node)) {
    if (typeof value !== "object" || value === null) continue;
    if (typeof value.get === "function" && typeof value.metadata?.endpoint === "string") {
      found.push({ path: [...path, key].join("."), resource: value });
    } else {
      collect(value, [...path, key], found);
    }
  }
  return found;
}

/**
 * An empty table and a populated one are both successes; only the caller can
 * say which they expected. A brand-new document still answers with data for
 * units, structure type and the colour tables, so "empty" is not a problem
 * and "has data" is not proof the sweep touched anything.
 */
function classify(body) {
  if (body && typeof body === "object" && Object.keys(body).length === 1 && body.message === "") {
    return "empty";
  }
  return "data";
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const client = new MidasClient({
    mapiKey: args.mapiKey,
    product: args.product,
    timeout: args.timeout,
  });

  // Every exit after the first request sets `process.exitCode` and returns
  // rather than calling process.exit(). Node on Windows aborts with a libuv
  // assertion when the process is torn down while a fetch handle is still
  // closing, which turns a clean sweep into exit 127.
  let health;
  try {
    health = await client.verifyConnection();
  } catch (error) {
    console.error(`Could not reach the MIDAS NX Open API server: ${error.message}`);
    process.exitCode = 2;
    return;
  }
  if (health?.status !== "connected") {
    console.error(`Server reachable but not connected: ${JSON.stringify(health)}`);
    process.exitCode = 2;
    return;
  }
  console.log(`${args.product}: connected\n`);

  const all = collect(resources, [], []);
  const selected = all.filter(({ resource }) => {
    if (!resource.metadata.products.includes(args.product)) return false;
    if (!resource.metadata.methods.includes("GET")) return false;
    return !args.resource || resource.metadata.endpoint.includes(args.resource);
  });
  if (!selected.length) {
    console.error(`No GET-capable ${args.product} resource matches ${args.resource ?? "(all)"}.`);
    console.error("In Git Bash, prefix the command with MSYS_NO_PATHCONV=1 or --resource /db/SECT is rewritten into a Windows path.");
    process.exitCode = 2;
    return;
  }
  console.log(`${selected.length} of ${all.length} declared resources serve GET on ${args.product}\n`);

  const rows = [];
  const failures = [];
  for (const { path, resource } of selected) {
    const endpoint = resource.metadata.endpoint;
    try {
      const body = await resource.get(client);
      rows.push({ path, endpoint, outcome: classify(body) });
    } catch (error) {
      const name = error?.constructor?.name ?? "Error";
      const message = String(error?.message ?? error).split("(Hint")[0].trim();
      rows.push({ path, endpoint, outcome: "error", name, message });
      failures.push({ endpoint, name, message });
    }
  }

  const answered = rows.filter((row) => row.outcome !== "error");
  const empty = answered.filter((row) => row.outcome === "empty").length;
  console.log(`answered: ${answered.length}  (${empty} empty, ${answered.length - empty} carrying data)`);
  console.log(`failed:   ${failures.length}`);
  for (const failure of failures) {
    console.log(`   ${failure.endpoint.padEnd(24)} ${failure.name}: ${failure.message.slice(0, 110)}`);
  }

  if (args.out) {
    writeFileSync(args.out, `${JSON.stringify({ product: args.product, rows }, null, 1)}\n`, "utf8");
    console.log(`\nReport written to ${args.out}`);
  }
  // A route that does not answer is the finding this sweep exists for.
  process.exitCode = failures.length ? 1 : 0;
}

await main();
