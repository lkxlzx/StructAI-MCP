import { describe, expect, it, vi } from "vitest";

import { MidasClient, MidasResultError, doc } from "../src";

function mockClient(body: object, raiseOnResultError = true) {
  const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200 }),
  );
  return { client: new MidasClient({ fetch, raiseOnResultError }), fetch };
}

function requestBody(fetch: ReturnType<typeof vi.fn>) {
  return JSON.parse(String(fetch.mock.calls[0]?.[1]?.body));
}

describe("doc operations", () => {
  it("wraps a project path in Argument and sends it to the document endpoint", async () => {
    const { client, fetch } = mockClient({ message: "command complete" });

    await doc.openProject("C:/models/bridge.mcb", { client });

    expect(fetch.mock.calls[0]?.[0]).toBe("https://moa-engineers.midasit.com:443/gen/doc/OPEN");
    expect(requestBody(fetch)).toEqual({ Argument: "C:/models/bridge.mcb" });
  });

  it("sends an empty Argument for a new project request", async () => {
    const { client, fetch } = mockClient({ message: "command complete" });

    await doc.newProject({ client });

    expect(requestBody(fetch)).toEqual({ Argument: {} });
  });

  it("includes only the documented stage export fields when requested", async () => {
    const { client, fetch } = mockClient({ message: "command complete" });

    await doc.stageAs("Stage 1", { exportPath: "C:/models/stage.mcb", client });

    expect(fetch.mock.calls[0]?.[0]).toBe("https://moa-engineers.midasit.com:443/gen/doc/STAGAS");
    expect(requestBody(fetch)).toEqual({
      Argument: { STAGE_STEP: "Stage 1", EXPORT_PATH: "C:/models/stage.mcb" },
    });
  });

  it("rejects the known HTTP-200 analysis failure message", async () => {
    const { client } = mockClient({ message: "MIDAS GEN NX Analysis failed." });

    await expect(doc.analyze(undefined, { client })).rejects.toMatchObject({
      name: MidasResultError.name,
      statusCode: 200,
      method: "POST",
      endpoint: "/doc/ANAL",
    });
  });

  it("returns an analysis failure message when result-error raising is disabled", async () => {
    const response = { message: "MIDAS GEN NX Analysis failed." };
    const { client } = mockClient(response, false);

    await expect(doc.analyze("STATIC", { client })).resolves.toEqual(response);
  });
});
