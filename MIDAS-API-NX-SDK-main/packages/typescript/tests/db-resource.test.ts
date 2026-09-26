import { describe, expect, it, vi } from "vitest";

import {
  DestructiveOperationError,
  MidasClient,
  defineDbResource,
} from "../src";

const metadata = {
  className: "Node",
  endpoint: "/db/NODE",
  name: "Node",
  products: ["gen", "civil"] as const,
  methods: ["GET", "POST", "PUT", "DELETE"] as const,
  manualChapter: "03_DB_Node_Element.md",
};

describe("DbResource", () => {
  it("wraps create items in Assign with string IDs", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(async () =>
      new Response(JSON.stringify({ message: "ok" }), { status: 200 }),
    );
    const client = new MidasClient({ fetch });
    const node = defineDbResource(metadata);

    await node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);

    const init = fetch.mock.calls[0]?.[1];
    expect(JSON.parse(String(init?.body))).toEqual({
      Assign: { "1": { X: 0, Y: 0, Z: 0 } },
    });
  });

  it("uses one per-ID DELETE request", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(async () =>
      new Response(JSON.stringify({ message: "ok" }), { status: 200 }),
    );
    const client = new MidasClient({ fetch });
    const node = defineDbResource(metadata);

    await node.delete([1, 3], client);

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "https://moa-engineers.midasit.com:443/gen/db/NODE/1",
      "https://moa-engineers.midasit.com:443/gen/db/NODE/3",
    ]);
  });

  it("runs destructive per-ID requests sequentially", async () => {
    let releaseFirst!: (response: Response) => void;
    const firstResponse = new Promise<Response>((resolve) => {
      releaseFirst = resolve;
    });
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementationOnce(async () => firstResponse)
      .mockImplementation(async () =>
        new Response(JSON.stringify({ message: "ok" }), { status: 200 }),
      );
    const client = new MidasClient({ fetch });
    const node = defineDbResource(metadata);

    const deletion = node.delete([1, 2], client);
    expect(fetch).toHaveBeenCalledTimes(1);

    releaseFirst(new Response(JSON.stringify({ message: "ok" }), { status: 200 }));
    await deletion;
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("stops before later IDs when a delete fails", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      new Response(JSON.stringify({ message: "failed" }), { status: 500 }),
    );
    const client = new MidasClient({ fetch });
    const node = defineDbResource(metadata);

    await expect(node.delete([1, 2], client)).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("blocks whole-table deletion unless explicitly confirmed", async () => {
    const node = defineDbResource(metadata);
    await expect(node.deleteAll({})).rejects.toBeInstanceOf(DestructiveOperationError);
  });
});
