import { getDefaultClient } from "./client";
import { MidasResultError } from "./errors";
import type { OperationOptions } from "./operation";
import type { JsonObject } from "./types";

async function post(endpoint: string, argument: JsonObject | string, options: OperationOptions = {}) {
  return (options.client ?? getDefaultClient()).request<JsonObject>(
    "POST",
    endpoint,
    { Argument: argument } as JsonObject,
    options,
  );
}

export const doc = {
  /**
   * Create a new project.
   *
   * @warning This can open MIDAS's own "save changes?" dialog and block the
   * entire API session until a person dismisses it. It has also crashed Gen
   * NX while a large analyzed model was open. Use only when the current model
   * may be discarded and the product process can be restarted.
   */
  newProject: (options?: OperationOptions) => post("/doc/NEW", {}, options),
  /** The path is resolved on the machine running MIDAS NX, not in this process. */
  openProject: (path: string, options?: OperationOptions) => post("/doc/OPEN", path, options),
  closeProject: (options?: OperationOptions) => post("/doc/CLOSE", {}, options),
  save: (options?: OperationOptions) => post("/doc/SAVE", {}, options),
  /**
   * Save on the machine running MIDAS NX. An invalid path can raise a modal
   * product dialog while the API still returns a success-looking message.
   */
  saveAs: (path: string, options?: OperationOptions) => post("/doc/SAVEAS", path, options),
  /**
   * Save the current construction stage on the MIDAS NX host. `stageStep`
   * is the plain stage name; the export currently requires the legacy `.mcb`
   * extension according to live verification.
   */
  stageAs: (
    stageStep: string,
    options: OperationOptions & { exportPath?: string } = {},
  ) => {
    const argument: JsonObject = { STAGE_STEP: stageStep };
    if (options.exportPath !== undefined) argument.EXPORT_PATH = options.exportPath;
    return post("/doc/STAGAS", argument, options);
  },
  importJson: (path: string, options?: OperationOptions) => post("/doc/IMPORT", path, options),
  importMxt: (path: string, options?: OperationOptions) => post("/doc/IMPORTMXT", path, options),
  exportJson: (path: string, options?: OperationOptions) => post("/doc/EXPORT", path, options),
  exportMxt: (path: string, options?: OperationOptions) => post("/doc/EXPORTMXT", path, options),
  /**
   * Run analysis and reject the known HTTP-200 failure message.
   *
   * @warning A timeout is not a rollback. Large solves may continue in MIDAS
   * NX after this promise rejects, so confirm model state before retrying.
   */
  analyze: async (analysisType?: string, options: OperationOptions = {}) => {
    const response = await post(
      "/doc/ANAL",
      analysisType ? { TYPE: analysisType } : {},
      options,
    );
    const message = response.message;
    const client = options.client ?? getDefaultClient();
    if (
      client.raiseOnResultError &&
      typeof message === "string" &&
      message.toLowerCase().includes("failed")
    ) {
      throw new MidasResultError(
        `POST /doc/ANAL -> 200, but the analysis did not succeed: ${message}`,
        { statusCode: 200, method: "POST", endpoint: "/doc/ANAL", responseBody: response },
      );
    }
    return response;
  },
} as const;
