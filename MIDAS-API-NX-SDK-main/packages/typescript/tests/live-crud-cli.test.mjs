import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HARNESS = fileURLToPath(new URL("../scripts/live-crud.mjs", import.meta.url));

/**
 * Run the harness with the given argv and return what it wrote and its code.
 *
 * It is spawned rather than imported because it calls `main()` at module
 * scope and exports nothing. Every case here is refused during argument
 * parsing, so no call reaches a product.
 */
function run(args) {
  try {
    const stdout = execFileSync(process.execPath, [HARNESS, ...args], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      // No relay: every case here is meant to be refused during argument
      // parsing, and pointing the client at a closed local port means a case
      // that slips past parsing fails on a refused connection instead of
      // reaching a real product.
      env: {
        ...process.env,
        MIDAS_NX_SAVE_DIR: "",
        MIDAS_BASE_URL: "http://127.0.0.1:1",
        MIDAS_MAPI_KEY: "not-a-key",
      },
    });
    return { code: 0, stdout, stderr: "" };
  } catch (error) {
    return {
      code: error.status ?? 1,
      stdout: error.stdout ?? "",
      stderr: error.stderr ?? "",
    };
  }
}

describe("live-crud.mjs argument safety", () => {
  it("refuses to start without a save directory", () => {
    // Every checkpoint lands on the machine running NX, not the one running
    // the script. A path that does not exist there raises a modal dialog
    // *there* while the HTTP call still answers like a success, blocking the
    // whole session until a human dismisses it. Deriving one from
    // verify_connection()'s `user` was tried and disproved on 2026-08-31:
    // that field is the MAPI account's email, not the host's Windows profile.
    const result = run(["--product", "gen", "--endpoints", "/db/NODE"]);
    expect(result.code).not.toBe(0);
    expect(result.stderr).toContain("--save-dir");
  });

  it("stops asking for one once the caller waives the checkpoint", () => {
    // --no-save-before removes the safety net, not the /doc/NEW. Waiving the
    // checkpoint is the only thing that makes --save-dir unnecessary, so this
    // must get past argument parsing -- and then fail on the closed port,
    // never on the missing directory.
    const result = run([
      "--product", "gen", "--endpoints", "/db/NODE", "--no-save-before",
    ]);
    expect(result.code).not.toBe(0);
    expect(`${result.stdout}${result.stderr}`).not.toContain("--save-dir");
  });

  it("rejects a save directory that is not an absolute path on the NX host", () => {
    const result = run([
      "--product", "gen", "--endpoints", "/db/NODE", "--save-dir", "scratch",
    ]);
    expect(result.code).not.toBe(0);
    expect(`${result.stdout}${result.stderr}`).toContain("absolute");
  });
});
