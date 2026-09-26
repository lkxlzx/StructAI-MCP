import { getDefaultClient } from "./client";
import type { OperationOptions } from "./operation";
import type { JsonObject, JsonValue } from "./types";

export interface NodeElementsSelector {
  keys?: number[];
  to?: string;
  structureGroupName?: string;
}

export interface TableUnit {
  force?: string;
  distance?: string;
  heat?: string;
  temperature?: string;
}

export interface TableStyles {
  format?: string;
  decimalPlaces?: number;
}

export interface TableOptions extends OperationOptions {
  tableName?: string;
  exportPath?: string;
  nodeElements?: NodeElementsSelector;
  unit?: TableUnit;
  styles?: TableStyles;
  components?: string[];
  loadCaseNames?: string[];
  /**
   * `OPT_CS`, which has three states - leaving it out is not the same as
   * `false`. Per the manual, `true` switches the view to Construction Stage and
   * returns CS results, `false` switches it to PostCS (the final stage) and
   * returns Post results, and omitting it keeps the current view mode. Leave it
   * undefined to keep the view. Not yet checked against a live product.
   */
  constructionStage?: boolean;
  stageSteps?: string[];
  parts?: string[];
  storyNames?: string[];
  modes?: string[];
  additional?: Record<string, JsonValue | undefined>;
  calculationMethod?: Record<string, JsonValue | undefined>;
}

function compactRecord(values: Record<string, JsonValue | undefined>): JsonObject {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined));
}

function tableArgument(tableType: string, options: TableOptions): JsonObject {
  const argument = compactRecord({
    TABLE_NAME: options.tableName ?? "",
    TABLE_TYPE: tableType,
    EXPORT_PATH: options.exportPath,
    NODE_ELEMS: options.nodeElements
      ? compactRecord({
          KEYS: options.nodeElements.keys,
          TO: options.nodeElements.to,
          STRUCTURE_GROUP_NAME: options.nodeElements.structureGroupName,
        })
      : undefined,
    UNIT: options.unit
      ? compactRecord({
          FORCE: options.unit.force,
          DIST: options.unit.distance,
          HEAT: options.unit.heat,
          TEMP: options.unit.temperature,
        })
      : undefined,
    STYLES: options.styles
      ? compactRecord({ FORMAT: options.styles.format, PLACE: options.styles.decimalPlaces })
      : undefined,
    COMPONENTS: options.components,
    LOAD_CASE_NAMES: options.loadCaseNames,
    OPT_CS: options.constructionStage,
    STAGE_STEP: options.stageSteps,
    PARTS: options.parts,
    STORY_NAMES: options.storyNames,
    MODES: options.modes,
    ADDITIONAL: options.additional as JsonObject | undefined,
    SET_CALCULATION_METHOD: options.calculationMethod as JsonObject | undefined,
  });
  return argument;
}

export async function getTableAt(
  endpoint: string,
  tableType: string,
  options: TableOptions = {},
): Promise<JsonObject> {
  return (options.client ?? getDefaultClient()).request(
    "POST",
    endpoint,
    { Argument: tableArgument(tableType, options) },
    options,
  );
}

/** Query the shared `/post/TABLE` endpoint for one documented table type. */
export function getTable(tableType: string, options: TableOptions = {}): Promise<JsonObject> {
  return getTableAt("/post/TABLE", tableType, options);
}

/**
 * Find the table by its `HEAD`/`DATA` shape instead of its top-level key.
 * Live MIDAS NX sessions have returned the requested name, `Result Table`,
 * and `empty` for equivalent calls, so indexing by `tableName` is unsafe.
 */
export function unwrapTable(response: JsonObject): JsonObject {
  if ("HEAD" in response || "DATA" in response) return response;
  for (const value of Object.values(response)) {
    if (
      typeof value === "object" &&
      value !== null &&
      !Array.isArray(value) &&
      ("HEAD" in value || "DATA" in value)
    ) {
      return value as JsonObject;
    }
  }
  return {};
}

type BaseDesignForcesTableOptions = Pick<
  TableOptions,
  "tableName" | "nodeElements" | "unit" | "styles" | "components"
>;
export type MemberDesignForcesTableOptions = BaseDesignForcesTableOptions &
  Pick<TableOptions, "parts">;
export type WallDesignForcesTableOptions = BaseDesignForcesTableOptions &
  Pick<TableOptions, "storyNames">;

function memberDesignForces(tableType: string) {
  return (options?: MemberDesignForcesTableOptions) => getTable(tableType, options);
}

export function defineTable<TOptions extends TableOptions = TableOptions>(tableType: string) {
  return (options?: TOptions) => getTable(tableType, options);
}

export function defineVariableTable<TOptions extends TableOptions = TableOptions>(
  defaultTableType?: string,
) {
  return (options: TOptions & { tableType?: string } = {} as TOptions) => {
    const tableType = options.tableType ?? defaultTableType;
    if (!tableType) throw new TypeError("tableType is required");
    return getTable(tableType, options);
  };
}

export type TableDirection = "X" | "Y" | "Z";

export function defineDirectionalTable<TOptions extends TableOptions = TableOptions>(prefix: string) {
  return (direction: TableDirection, options?: TOptions) => getTable(`${prefix}${direction}`, options);
}

export const post = {
  getTable,
  unwrapTable,
  getBeamDesignForcesTable: memberDesignForces("BEAMDESIGNFORCES"),
  getColumnDesignForcesTable: memberDesignForces("COLUMNDESIGNFORCES"),
  getBraceDesignForcesTable: memberDesignForces("BRACEDESIGNFORCES"),
  getWallDesignForcesTable: (options?: WallDesignForcesTableOptions) =>
    getTable("WALLDESIGNFORCES", options),
  getSteelMemberDesignForcesTable: memberDesignForces("STEELMEMBERDESIGNFORCES"),
  getSrcBeamDesignForcesTable: memberDesignForces("SRCBEAMDESIGNFORCES"),
  getSrcColumnDesignForcesTable: memberDesignForces("SRCCOLUMNDESIGNFORCES"),
  getColdFormedSteelMemberDesignForcesTable: memberDesignForces(
    "COLDFORMEDSTEELMEMBERDESIGNFORCES",
  ),
} as const;
