import { describe, expect, it, vi } from "vitest";

import { MidasClient, defineDbResource, resources } from "../src";

/**
 * Contract-driven payload normalization.
 *
 * `/db/NMAS` is why this exists. Omitting `rmX`/`rmY`/`rmZ` hung the call and
 * killed the NX session across 15+ reproductions on both Gen NX and Civil NX,
 * while sending them as `0.0` - their own documented default - did not. Python
 * gained that workaround on 2026-07-29; this package shipped on 2026-08-26
 * without it, because the workaround was behaviour inside a method and the
 * generator only carried metadata and docstrings across. The rule now comes
 * from `contracts/endpoints/db-nmas.yaml` and reaches both SDKs the same way.
 */

const ok = () =>
  vi
    .fn<typeof globalThis.fetch>()
    .mockImplementation(async () => new Response(JSON.stringify({ message: "ok" }), { status: 200 }));

function sentBody(fetch: ReturnType<typeof ok>, call = 0): Record<string, unknown> {
  return JSON.parse(String(fetch.mock.calls[call]?.[1]?.body));
}

describe("nodalMass payload normalization", () => {
  it("fills rmX/rmY/rmZ on create when the caller omits them", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });

    await resources.db.staticLoads.nodalMass.create({ 1: { mX: 1, mY: 1, mZ: 1 } }, client);

    expect(sentBody(fetch)).toEqual({
      Assign: { "1": { mX: 1, mY: 1, mZ: 1, rmX: 0, rmY: 0, rmZ: 0 } },
    });
  });

  it("fills rmX/rmY/rmZ on update too", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });

    await resources.db.staticLoads.nodalMass.update({ 7: { mX: 2 } }, client);

    expect(sentBody(fetch)).toEqual({
      Assign: { "7": { mX: 2, rmX: 0, rmY: 0, rmZ: 0 } },
    });
  });

  it("never overwrites a rotational mass the caller supplied", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });

    await resources.db.staticLoads.nodalMass.create({ 1: { mX: 1, rmZ: 500 } }, client);

    const assign = (sentBody(fetch).Assign as Record<string, Record<string, number>>)["1"];
    expect(assign).toEqual({ mX: 1, rmX: 0, rmY: 0, rmZ: 500 });
  });

  it("normalizes every record in one call, not only the first", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });

    await resources.db.staticLoads.nodalMass.create({ 1: { mX: 1 }, 2: { mX: 2 } }, client);

    const assign = sentBody(fetch).Assign as Record<string, Record<string, number>>;
    for (const record of Object.values(assign)) {
      expect(record).toMatchObject({ rmX: 0, rmY: 0, rmZ: 0 });
    }
  });

  it("declares the defaults in its published metadata", () => {
    expect(resources.db.staticLoads.nodalMass.metadata.payloadDefaults).toEqual({
      rmX: 0,
      rmY: 0,
      rmZ: 0,
    });
  });

  it("leaves payloads untouched for resources with no contract rule", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });

    await resources.db.nodeElement.node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);

    expect(sentBody(fetch)).toEqual({ Assign: { "1": { X: 0, Y: 0, Z: 0 } } });
    expect(resources.db.nodeElement.node.metadata.payloadDefaults).toBeUndefined();
  });

  it("applies defaults without mutating the caller's object", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });
    const items = { 1: { mX: 1 } };

    await resources.db.staticLoads.nodalMass.create(items, client);

    expect(items).toEqual({ 1: { mX: 1 } });
  });

  it("does nothing when a resource declares no defaults", async () => {
    const fetch = ok();
    const client = new MidasClient({ fetch });
    const resource = defineDbResource({
      className: "Scratch",
      endpoint: "/db/SCRATCH",
      name: "Scratch",
      products: ["gen", "civil"] as const,
      methods: ["POST"] as const,
      manualChapter: "99_Synthetic.md",
    });

    await resource.create({ 1: { A: 1 } }, client);

    expect(sentBody(fetch)).toEqual({ Assign: { "1": { A: 1 } } });
  });
});
