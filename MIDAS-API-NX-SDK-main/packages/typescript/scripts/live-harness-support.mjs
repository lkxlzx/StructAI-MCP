/**
 * Pure helpers shared by the live harness and its unit tests.
 *
 * They live outside live-crud.mjs because that module runs `main()` on
 * import, so nothing there can be unit tested. What is here is exactly the
 * logic that decides how a live result is *read* -- which is worth a test of
 * its own, because getting it wrong turns a fixture problem into a reported
 * SDK regression.
 */

/** Verify only records created by this seed; existing names are not evidence. */
export function verifyRenumberedSeed(source, after, createdIds) {
  if (createdIds.length !== Object.keys(source.records).length) {
    throw new Error(`${source.endpoint}: setup POST did not store every seed record.`);
  }
  const remaining = new Set(createdIds);
  for (const payload of Object.values(source.records)) {
    const name = payload.NAME ?? payload.COMMON?.NAME;
    const id = [...remaining].find((key) =>
      (after[key].NAME ?? after[key].COMMON?.NAME) === name);
    if (typeof name !== "string" || id === undefined) {
      throw new Error(`${source.endpoint}: setup POST did not preserve the seed name.`);
    }
    remaining.delete(id);
  }
}

function sameStructuredValue(value, expected, unordered) {
  if (Object.is(value, expected)) return true;
  if (typeof value !== "object" || value === null
    || typeof expected !== "object" || expected === null) return false;

  if (Array.isArray(expected)) {
    if (!Array.isArray(value) || value.length !== expected.length) return false;
    if (!unordered) {
      return value.every((child, index) => sameStructuredValue(child, expected[index], false));
    }
    // A multiset match: each expected element claims a distinct live one.
    const remaining = [...value];
    return expected.every((child) => {
      const index = remaining.findIndex((candidate) =>
        sameStructuredValue(candidate, child, true));
      if (index < 0) return false;
      remaining.splice(index, 1);
      return true;
    });
  }
  if (!Array.isArray(value)) {
    const valueKeys = Object.keys(value);
    const expectedKeys = Object.keys(expected);
    return valueKeys.length === expectedKeys.length
      && expectedKeys.every((key) => Object.hasOwn(value, key)
        && sameStructuredValue(value[key], expected[key], unordered));
  }
  return false;
}

/**
 * True when a fixture value occurs anywhere in a live response tree.
 *
 * `unordered` comes from the fixture's `expected.unordered`, set where the
 * server returns a list in its own order (Python's probe sorts it there).
 * It relaxes list order only; lengths and elements must still match.
 */
export function containsExpectedValue(value, expected, { unordered = false } = {}) {
  if (sameStructuredValue(value, expected, unordered)) return true;
  if (typeof value !== "object" || value === null) return false;
  return Object.values(value).some(
    (child) => containsExpectedValue(child, expected, { unordered }),
  );
}

/**
 * Normalise one emitted seed into the steps setup replays, in order.
 *
 * A step either POSTs `records` or deletes the listed ids one URL at a time
 * (`delete`), which is what Python's `DbResource.delete` sends. Anything else
 * is a fixture this harness does not understand, and guessing would run a
 * case half-seeded.
 */
export function seedSteps(seed, name) {
  const steps = seed && Array.isArray(seed.steps) ? seed.steps : [seed];
  return steps.map((step) => {
    if (!step || typeof step.endpoint !== "string") {
      throw new Error(`fixture seed ${name} is invalid.`);
    }
    if (Array.isArray(step.delete)) {
      const ids = step.delete.map(Number);
      if (!ids.length || ids.some((id) => !Number.isInteger(id)) || "records" in step) {
        throw new Error(`fixture seed ${name} has an invalid delete step.`);
      }
      return { endpoint: step.endpoint, deleteIds: ids };
    }
    if (typeof step.records !== "object" || step.records === null) {
      throw new Error(`fixture seed ${name} is invalid.`);
    }
    return {
      endpoint: step.endpoint,
      records: step.records,
      // Only an emitted fixture can opt into replacing a record supplied by
      // /doc/NEW. Ordinary setup collisions remain a hard safety failure.
      replaceExisting: step.replaceExisting === true,
      allowRenumbering: step.allowRenumbering === true,
    };
  });
}

/** Select only write methods supported by both the emitted case and resource. */
export function supportedCaseWrites(caseMethods, resourceMethods) {
  return {
    supportsPost: caseMethods.includes("POST") && resourceMethods.includes("POST"),
    supportsPut: caseMethods.includes("PUT") && resourceMethods.includes("PUT"),
  };
}

/** Select the only cleanup path that leaves the live scratch document empty. */
export function caseCleanupMode(caseMethods, resourceMethods, { finalCase, resetDocument }) {
  const supportsDelete = caseMethods.includes("DELETE") && resourceMethods.includes("DELETE");
  if (supportsDelete) return "per-id";
  if (finalCase && resetDocument) return "document-reset";
  return "unsafe";
}

/** Select cleanup for a setup resource without weakening scratch-model safety. */
export function setupCleanupMode(resourceMethods, { finalCase, resetDocument }) {
  if (resourceMethods.includes("DELETE")) return "per-id";
  if (finalCase && resetDocument) return "document-reset";
  return "unsafe";
}

/**
 * Classify one case result the way scripts/live_crud_check.py classifies its
 * own rows, and for the same reason.
 *
 * A case whose *setup* failed says nothing about the endpoint under test, so
 * Python calls it BLOCKED and exits 3 -- "triage the fixture first". This
 * harness had no such class: any failure of a confirmed case read as REGRESS,
 * which is how a missing seed record was reported as a package regression.
 */
export function classifyResult(result) {
  if (result.ok) return "PASS";
  if (result.blocked) return "BLOCK";
  return result.confirmed ? "REGRESS" : "FAIL";
}

/**
 * Exit code for a whole run, mirroring live_crud_check.py: a regression is 1,
 * anything else unresolved is 3, and a blocked case never reaches 1 however
 * confirmed the case is.
 */
export function exitCodeFor(results) {
  const failed = results.filter((result) => !result.ok);
  if (!failed.length) return 0;
  return failed.some((result) => result.confirmed && !result.blocked) ? 1 : 3;
}

/**
 * The base-model record a `replaceExisting` setup step overwrote, or null.
 *
 * Such a step deletes a record the shared base model owns - material 1,
 * section 1, nodes 1-4, element 2-3, thickness 1 - and creates its own under
 * that id. The harness detects what a step created by diffing against a
 * snapshot taken *before* the delete, so a replaced id never looks new and
 * cleanup used to leave it in place: the fixture's steel S450 stayed at
 * material 1, and every later case in the same invocation ran against a base
 * model nobody had rebuilt. Cleanup asks here what to put back.
 *
 * A PUT step is not restorable this way - it changed a record the document
 * supplies rather than one the fixture created - so it is reported as
 * unrestorable rather than replayed as a create.
 */
export function replacedBaseModelRecord(baseModel, endpoint, id) {
  for (const step of baseModel ?? []) {
    if (step.endpoint !== endpoint) continue;
    const record = step.records?.[id];
    if (!record) continue;
    if (step.method === "PUT") return null;
    return record;
  }
  return null;
}
