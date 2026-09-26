import { describe, expect, it, vi } from "vitest";

import {
  MidasAuthError,
  MidasClient,
  MidasResultError,
  MidasServerError,
  ProductMismatchError,
} from "../src";

function response(body: unknown, init: ResponseInit = {}): Response {
  return new Response(body === undefined ? undefined : JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("MidasClient", () => {
  it("builds the product URL and sends the MAPI key", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response({ NODE: {} }));
    const client = new MidasClient({ mapiKey: "secret", product: "civil", fetch });

    await client.request("GET", "/db/NODE");

    expect(fetch).toHaveBeenCalledWith(
      "https://moa-engineers.midasit.com:443/civil/db/NODE",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "MAPI-Key": "secret" }),
      }),
    );
  });

  it("raises for a 2xx error body", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      response({ error: { message: "Please perform analysis." } }),
    );
    const client = new MidasClient({ fetch });

    await expect(client.request("POST", "/post/TABLE", {})).rejects.toBeInstanceOf(
      MidasResultError,
    );
  });

  it("can return a 2xx error body when explicitly configured", async () => {
    const body = { error: { message: "Please perform analysis." } };
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response(body));
    const client = new MidasClient({ fetch, raiseOnResultError: false });

    await expect(client.request("POST", "/post/TABLE", {})).resolves.toEqual(body);
  });

  it("maps authentication failures", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      response({ message: "invalid key" }, { status: 401 }),
    );
    const client = new MidasClient({ fetch });

    await expect(client.request("GET", "/db/NODE")).rejects.toBeInstanceOf(MidasAuthError);
  });

  it("keeps non-JSON responses inside the SDK error hierarchy", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      new Response("<html>proxy</html>", { status: 200 }),
    );
    const client = new MidasClient({ fetch });

    await expect(client.request("GET", "/db/NODE")).rejects.toBeInstanceOf(MidasServerError);
  });

  it("enforces product compatibility", () => {
    const client = new MidasClient({ product: "gen", fetch: vi.fn() });
    expect(() => client.checkProduct(["civil"], "Civil-only resource")).toThrow(
      ProductMismatchError,
    );
  });
});
