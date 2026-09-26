import { describe, expect, it } from "vitest";

import {
  MidasAPIError,
  MidasAuthError,
  MidasNotFoundError,
  MidasRequestError,
  MidasServerError,
  errorForStatus,
} from "../src";

describe("MidasAPIError", () => {
  it("retains request context and its original cause", () => {
    const cause = new Error("socket closed");
    const responseBody = { error: { message: "invalid model" } };
    const error = new MidasAPIError("POST failed", {
      statusCode: 502,
      method: "POST",
      endpoint: "/doc/ANAL",
      responseBody,
      cause,
    });

    expect(error).toMatchObject({
      name: "MidasAPIError",
      message: "POST failed",
      statusCode: 502,
      method: "POST",
      endpoint: "/doc/ANAL",
      responseBody,
      cause,
    });
  });
});

describe("errorForStatus", () => {
  it.each([
    [401, MidasAuthError],
    [403, MidasAuthError],
    [404, MidasNotFoundError],
    [500, MidasServerError],
    [503, MidasServerError],
    [400, MidasRequestError],
    [429, MidasRequestError],
  ] as const)("maps HTTP %i to %p", (status, ErrorClass) => {
    expect(errorForStatus(status)).toBe(ErrorClass);
  });

  it("returns constructible classes that retain the mapped error name", () => {
    const ErrorClass = errorForStatus(404);
    const error = new ErrorClass("missing", { endpoint: "/db/NODE" });

    expect(error).toBeInstanceOf(MidasNotFoundError);
    expect(error.name).toBe("MidasNotFoundError");
    expect(error.endpoint).toBe("/db/NODE");
  });
});
