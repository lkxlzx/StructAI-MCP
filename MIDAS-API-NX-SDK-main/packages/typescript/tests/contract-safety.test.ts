import { describe, expect, it, vi } from "vitest";

import {
  DestructiveOperationError,
  MidasClient,
  MidasServerError,
  MidasRequestError,
  operations,
  defineDbResource,
  resources,
  unwrapTable,
} from "../src";

const metadata = {
  className: "ContractSafetyProbe",
  endpoint: "/db/CONTRACT-SAFETY-PROBE",
  name: "Contract safety probe",
  products: ["gen", "civil"] as const,
  methods: ["POST", "GET", "PUT", "DELETE"] as const,
  manualChapter: "not-a-manual-source.ts",
};

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

type UnwrapResponseCase = "table_name" | "result_table" | "empty_with_table" | "no_table";

function unwrapResponseCases(): UnwrapResponseCase[] {
  const processLike = globalThis as typeof globalThis & {
    process?: { env?: Record<string, string | undefined> };
  };
  const raw = processLike.process?.env?.MIDAS_UNWRAP_TABLE_RESPONSE_CASES;
  if (!raw) return ["table_name", "result_table", "empty_with_table", "no_table"];
  return JSON.parse(raw) as UnwrapResponseCase[];
}

function unwrapFixture(caseName: UnwrapResponseCase) {
  const table = { HEAD: ["Node", "FX"], DATA: [["1", "-10"]] };
  switch (caseName) {
    case "table_name":
      return { response: { "Requested table": table }, expected: table };
    case "result_table":
      return { response: { "Result Table": table }, expected: table };
    case "empty_with_table":
      return { response: { empty: table }, expected: table };
    case "no_table":
      return { response: { message: "" }, expected: {} };
  }
}

describe("contract safety probes", () => {
  it("normalize_defaults: sends required explicit defaults through the npm resource", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response({ message: "ok" }));
    const client = new MidasClient({ fetch });

    await resources.db.staticLoads.nodalMass.create({ 1: { mX: 1 } }, client);

    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      Assign: { "1": { mX: 1, rmX: 0, rmY: 0, rmZ: 0 } },
    });
  });

  it("reject_request: rejects /ope/GSBG batch-exclusive fields before sending", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = new MidasClient({ fetch });

    await expect(
      operations.ope.generateBridgeGirderDiagram({ BATCH: true, BRDG_GROUP: "CONTRACT-PROBE" }, { client }),
    ).rejects.toBeInstanceOf(MidasRequestError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reject_request: refuses an empty object in a field the contract names", async () => {
    // /db/MVHL's VEH_DEFAULT. The server takes `{}`, answers with no error and
    // stores nothing, so the caller's next GET is what tells them - which is
    // exactly the class of defect a contract rule exists to keep out of one
    // language. The field list is generated from contracts/endpoints/.
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = new MidasClient({ fetch });
    const resource = defineDbResource({ ...metadata, rejectEmptyFields: ["VEH_DEFAULT"] });

    await expect(
      resource.create({ 1: { MVLD_CODE: 2, VEH_DEFAULT: {} } }, client),
    ).rejects.toBeInstanceOf(MidasRequestError);
    await expect(
      resource.update({ 1: { MVLD_CODE: 2, VEH_DEFAULT: {} } }, client),
    ).rejects.toBeInstanceOf(MidasRequestError);
    expect(fetch).not.toHaveBeenCalled();

    // Omitting the field is a different request and stays allowed.
    const allowed = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementation(async () => response({ message: "ok" }));
    await resource.create({ 1: { MVLD_CODE: 2 } }, new MidasClient({ fetch: allowed }));
    expect(allowed).toHaveBeenCalledOnce();
  });

  it("reject_request: the generated /db/MVHL resource carries the contract's field", () => {
    expect(resources.db.movingLoads.vehicles.metadata.rejectEmptyFields).toEqual([
      "VEH_DEFAULT",
    ]);
  });

  it("reject_request: refuses a record that omits a field the contract requires explicitly", async () => {
    // /db/PRES's DIRECTION, nested one array deep. The manual marks it
    // Optional with the default "NORMAL", and on a PLATE with FACE_EDGE_TYPE
    // "FACE" the server refuses both the omission and that value. There is no
    // default an SDK could fill in - which way the pressure acts is the
    // engineer's decision - so the request is stopped and the caller asked.
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = new MidasClient({ fetch });
    const resource = defineDbResource({
      ...metadata,
      requiredExplicitFields: ["ITEMS[].DIRECTION"],
    });
    const item = { LCNAME: "LC", ELEM_TYPE: "PLATE", FACE_EDGE_TYPE: "FACE", EDGE_FACE: 1 };

    await expect(resource.create({ 4: { ITEMS: [item] } }, client)).rejects.toBeInstanceOf(
      MidasRequestError,
    );
    await expect(resource.update({ 4: { ITEMS: [item] } }, client)).rejects.toBeInstanceOf(
      MidasRequestError,
    );
    // The second entry is the one missing it; the message has to say which.
    await expect(
      resource.create({ 4: { ITEMS: [{ ...item, DIRECTION: "LZ" }, item] } }, client),
    ).rejects.toThrow(/ITEMS\[1\]/);
    expect(fetch).not.toHaveBeenCalled();

    // Sending the documented value explicitly stays the caller's to make: it
    // is valid for the other ELEM_TYPE/FACE_EDGE_TYPE pairs the manual lists.
    const allowed = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementation(async () => response({ message: "ok" }));
    await resource.create(
      { 4: { ITEMS: [{ ...item, DIRECTION: "NORMAL" }] } },
      new MidasClient({ fetch: allowed }),
    );
    expect(allowed).toHaveBeenCalledOnce();
  });

  it("reject_request: an absent or wrongly typed container is not a missing field", async () => {
    // A record with no ITEMS at all never reaches the field, so there is
    // nothing for this rule to say about it. Refusing it here would invent a
    // requirement the contract does not state - ITEMS' own requiredness is a
    // separate row - and would break the DELETE-shaped bodies that carry none.
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementation(async () => response({ message: "ok" }));
    const client = new MidasClient({ fetch });
    const resource = defineDbResource({
      ...metadata,
      requiredExplicitFields: ["ITEMS[].DIRECTION"],
    });

    await resource.create({ 4: {} }, client);
    await resource.create({ 4: { ITEMS: [] } }, client);
    await resource.create({ 4: { ITEMS: "not an array" } }, client);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("reject_request: the generated /db/PRES resource carries the contract's path", () => {
    expect(resources.db.staticLoads.pressureLoad.metadata.requiredExplicitFields).toEqual([
      "ITEMS[].DIRECTION",
    ]);
  });

  it("per_id_request: sends one DELETE URL per id and stops after the first failure", async () => {
    const resource = defineDbResource(metadata);
    const successfulFetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementation(async () => response({ message: "ok" }));
    const successfulClient = new MidasClient({ fetch: successfulFetch });

    await resource.delete([7, 9], successfulClient);

    expect(successfulFetch.mock.calls.map(([url]) => url)).toEqual([
      "https://moa-engineers.midasit.com:443/gen/db/CONTRACT-SAFETY-PROBE/7",
      "https://moa-engineers.midasit.com:443/gen/db/CONTRACT-SAFETY-PROBE/9",
    ]);

    const failingFetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response({ message: "failed" }, 500))
      .mockResolvedValue(response({ message: "ok" }));
    const failingClient = new MidasClient({ fetch: failingFetch });

    await expect(resource.delete([7, 9], failingClient)).rejects.toBeInstanceOf(MidasServerError);
    expect(failingFetch).toHaveBeenCalledTimes(1);
    expect(failingFetch.mock.calls[0]?.[0]).toBe(
      "https://moa-engineers.midasit.com:443/gen/db/CONTRACT-SAFETY-PROBE/7",
    );
  });

  it("require_confirmation: rejects a whole-table DELETE before sending it", async () => {
    const resource = defineDbResource(metadata);
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = new MidasClient({ fetch });

    await expect(resource.deleteAll({ client })).rejects.toBeInstanceOf(DestructiveOperationError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("unwrap_table_by_shape: decodes every response case declared by the contract", () => {
    const cases = unwrapResponseCases();
    expect(cases).toEqual(
      expect.arrayContaining(["table_name", "result_table", "empty_with_table", "no_table"]),
    );

    for (const caseName of cases) {
      const { response, expected } = unwrapFixture(caseName);
      expect(unwrapTable(response)).toEqual(expected);
    }
  });
});
