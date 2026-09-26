import {
  getTableAt,
  type MemberDesignForcesTableOptions,
  type TableOptions,
} from "./post";

export type DesignEndpointTableOptions = MemberDesignForcesTableOptions &
  Pick<TableOptions, "exportPath" | "client">;

function defineDesignTable(endpoint: string, tableType: string) {
  return (options?: DesignEndpointTableOptions) => getTableAt(endpoint, tableType, options);
}

export const designTables = {
  rcKds: {
    getColumnDesignForcesTable: defineDesignTable(
      "/DESIGN/RC/KDS-41-20-2022/TABLE",
      "COLUMNDESIGNFORCES",
    ),
    getBraceDesignForcesTable: defineDesignTable(
      "/DESIGN/RC/KDS-41-20-2022/TABLE",
      "BRACEDESIGNFORCES",
    ),
    getBeamDesignForcesTable: defineDesignTable(
      "/DESIGN/RC/KDS-41-20-2022/TABLE",
      "BEAMDESIGNFORCES",
    ),
  },
  srcAikSrc2k: {
    getSrcBeamDesignForcesTable: defineDesignTable(
      "/DESIGN/SRC/AIK-SRC2K/TABLE",
      "SRCBEAMDESIGNFORCES",
    ),
    getSrcColumnDesignForcesTable: defineDesignTable(
      "/DESIGN/SRC/AIK-SRC2K/TABLE",
      "SRCCOLUMNDESIGNFORCES",
    ),
  },
} as const;
