import { describe, expect, it, vi } from "vitest";

import { MidasClient, designTables } from "../src";

describe("designTables", () => {
  it("routes design-force table requests to their documented DESIGN/TABLE endpoint", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementation(async () => new Response(JSON.stringify({ message: "ok" }), { status: 200 }));
    const client = new MidasClient({ fetch });

    await designTables.rcKds.getBeamDesignForcesTable({
      parts: ["PartI"],
      exportPath: "C:/reports/beam.json",
      client,
    });
    await designTables.srcAikSrc2k.getSrcColumnDesignForcesTable({ client });

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "https://moa-engineers.midasit.com:443/gen/DESIGN/RC/KDS-41-20-2022/TABLE",
      "https://moa-engineers.midasit.com:443/gen/DESIGN/SRC/AIK-SRC2K/TABLE",
    ]);
    expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
      Argument: {
        TABLE_NAME: "",
        TABLE_TYPE: "BEAMDESIGNFORCES",
        EXPORT_PATH: "C:/reports/beam.json",
        PARTS: ["PartI"],
      },
    });
    expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({
      Argument: { TABLE_NAME: "", TABLE_TYPE: "SRCCOLUMNDESIGNFORCES" },
    });
  });
});
