import { describe, expect, it } from "vitest";

import type {
  HttpMethod,
  ItemMap,
  JsonObject,
  JsonValue,
  MidasClientOptions,
  RequestOptions,
} from "../src";

const request: RequestOptions = { timeout: 1_000 };
const client: MidasClientOptions = { product: "civil", timeout: 1_000 };
const method: HttpMethod = "DELETE";
const items: ItemMap<{ X: number }> = { 1: { X: 0 }, "2": { X: 1 } };
const body: JsonObject = { Assign: { "1": { X: 0 } }, values: [1, "two", null] };
const value: JsonValue = body;

describe("public JSON and request types", () => {
  it("keeps representative public type fixtures valid", () => {
    expect({ request, client, method, items, value }).toMatchObject({
      request: { timeout: 1_000 },
      client: { product: "civil" },
      method: "DELETE",
      items: { 1: { X: 0 }, 2: { X: 1 } },
    });
  });
});
