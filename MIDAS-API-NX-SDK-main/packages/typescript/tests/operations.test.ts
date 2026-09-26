import { describe, expect, it, vi } from "vitest";

import {
  MidasClient,
  MidasRequestError,
  MidasResultError,
  ProductMismatchError,
  designTables,
  doc,
  getTable,
  operationCount,
  operations,
  resourceCount,
  tableCount,
  tables,
  unwrapTable,
} from "../src";

function mockClient(body: object = { message: "ok" }) {
  const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200 }),
  );
  return { client: new MidasClient({ fetch }), fetch };
}

describe("generated API surface", () => {
  it("keeps the reviewed Python surface represented", () => {
    expect(resourceCount).toBe(305);
    expect(operationCount).toBe(70);
    expect(tableCount).toBe(87);
    expect(operations.ope.divideElements.metadata.endpoint).toBe("/ope/DIVIDEELEM");
    expect(typeof tables.result1.getReactionTable).toBe("function");
    expect(typeof designTables.rcKds.getColumnDesignForcesTable).toBe("function");
  });

  it("wraps operation arguments", async () => {
    const { client, fetch } = mockClient();
    await operations.view.setAngle({ HORIZONTAL: 30 }, { client });
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      Argument: { HORIZONTAL: 30 },
    });
  });

  it("sends an empty Argument for no-argument POST operations", async () => {
    const { client, fetch } = mockClient();
    await operations.post.design.getPmInteractionDiagram({ client });
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({ Argument: {} });
  });

  it("blocks Gen-only operations before sending a Civil request", async () => {
    const { fetch } = mockClient();
    const client = new MidasClient({ product: "civil", fetch });

    await expect(operations.ope.getStoryCheckParameter({ client })).rejects.toBeInstanceOf(
      ProductMismatchError,
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects the documented /ope/GSBG mutually exclusive arguments before sending", async () => {
    const { client, fetch } = mockClient();
    await expect(
      operations.ope.generateBridgeGirderDiagram({ BATCH: true, BRDG_GROUP: "BG_MAIN" }, { client }),
    ).rejects.toBeInstanceOf(MidasRequestError);
    await expect(
      operations.ope.generateBridgeGirderDiagram({ BATCH: false, BATCH_LIST: ["OUT"] }, { client }),
    ).rejects.toBeInstanceOf(MidasRequestError);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("document and table safety behavior", () => {
  it("detects /doc/ANAL failures returned with HTTP 200", async () => {
    const { client } = mockClient({ message: "MIDAS CIVIL NX Analysis failed." });
    await expect(doc.analyze(undefined, { client })).rejects.toBeInstanceOf(MidasResultError);
  });

  it("maps camelCase table options to the official request keys", async () => {
    const { client, fetch } = mockClient();
    await getTable("REACTIONG", {
      tableName: "Reaction",
      loadCaseNames: ["DL(ST)"],
      nodeElements: { keys: [1, 2] },
      client,
    });
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      Argument: {
        TABLE_NAME: "Reaction",
        TABLE_TYPE: "REACTIONG",
        NODE_ELEMS: { KEYS: [1, 2] },
        LOAD_CASE_NAMES: ["DL(ST)"],
      },
    });
  });

  it("unwraps unstable /post/TABLE top-level keys by shape", () => {
    expect(unwrapTable({ empty: { HEAD: ["Index"], DATA: [[1]] } })).toEqual({
      HEAD: ["Index"],
      DATA: [[1]],
    });
  });
});
