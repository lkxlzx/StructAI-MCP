import { designTables, operations, post, resources, tables } from "../src";
import { describe, expect, it } from "vitest";

// This file is compiled by `npm run typecheck`. The unreachable block keeps
// public API examples type-checked without making live requests in Vitest.
if (false) {
  operations.post.design.getPmInteractionDiagram();
  operations.post.design.getSteelCodeCheck();

  tables.preProcess.getMaterialTable({ tableName: "Materials" });
  tables.result1.getReactionTable({
    tableType: "REACTIONL",
    loadCaseNames: ["DL(ST)"],
  });
  tables.story.getStoryModeShapeTable({ modes: ["Mode1"] });
  post.getWallDesignForcesTable({ storyNames: ["1F"] });
  designTables.rcKds.getBeamDesignForcesTable({ exportPath: "C:/reports" });

  // These endpoints shared a legacy Python payload name, but their reviewed
  // contracts differ: DYFG requires HEIGHT_COVER while DYNF permits omission.
  resources.db.movingLoads.railwayDynamicFactor.create({ 1: { INPUT_TYPE: 0, HEIGHT_COVER: 1 } });
  resources.db.movingLoads.railwayDynamicFactorByElement.create({ 1: { INPUT_TYPE: 0 } });

  // /db/BODF is now modelled directly from its manual contract.
  resources.db.staticLoads.selfWeight.create({ 1: { LCNAME: "DL", FV: [0, 0, -1] } });

  // @ts-expect-error /db/BODF requires the load-case name
  resources.db.staticLoads.selfWeight.create({ 1: { FV: [0, 0, -1] } });

  // @ts-expect-error /db/BODF's FV factor is exactly three directional values
  resources.db.staticLoads.selfWeight.create({ 1: { LCNAME: "DL", FV: [0, -1] } });

  // @ts-expect-error /db/DYFG requires HEIGHT_COVER in its contract payload
  resources.db.movingLoads.railwayDynamicFactor.create({ 1: { INPUT_TYPE: 0 } });

  // A discriminated payload must still accept the documented values the
  // manual gives no table for. /db/FBLA documents FLOOR_DIST_TYPE 1 to 4 and
  // supplies tables for 1 and 2 only, so 3 and 4 have to remain expressible.
  resources.db.staticLoads.floorLoad.create({
    1: { FLOOR_LOAD_TYPE_NAME: "FL1", FLOOR_DIST_TYPE: 3, NODES: [1, 2, 3, 4] },
  });

  resources.db.staticLoads.floorLoad.create({
    1: { FLOOR_LOAD_TYPE_NAME: "FL1", FLOOR_DIST_TYPE: 1, NODES: [1, 2, 3, 4], LOAD_ANGLE: 30 },
  });

  // ...while a field the manual puts under another branch stays an error.
  resources.db.staticLoads.floorLoad.create({
    1: {
      FLOOR_LOAD_TYPE_NAME: "FL1",
      FLOOR_DIST_TYPE: 3,
      NODES: [1],
      // @ts-expect-error LOAD_ANGLE is documented under FLOOR_DIST_TYPE 1, not 3
      LOAD_ANGLE: 30,
    },
  });

  // Material tables do not accept analysis-result filters.
  // @ts-expect-error loadCaseNames is not supported by this wrapper
  tables.preProcess.getMaterialTable({ loadCaseNames: ["DL(ST)"] });

  // Mode selection belongs to Story Mode Shape, not Reaction.
  // @ts-expect-error modes is not supported by this wrapper
  tables.result1.getReactionTable({ modes: ["Mode1"] });

  // Directional wrappers only accept the three documented axes.
  // @ts-expect-error invalid direction
  tables.preProcess.getMassSummaryTable("Q");

  // Wall design forces use story selection rather than member-end parts.
  // @ts-expect-error parts is not supported by the wall wrapper
  post.getWallDesignForcesTable({ parts: ["PartI"] });

  // The DESIGN/TABLE endpoint does not accept analysis-result load filters.
  // @ts-expect-error loadCaseNames is not supported by this endpoint
  designTables.rcKds.getBeamDesignForcesTable({ loadCaseNames: ["DL(ST)"] });
}

describe("public type surface", () => {
  it("exposes the generated namespaces at runtime", () => {
    expect(typeof tables.preProcess.getMaterialTable).toBe("function");
    expect(typeof operations.post.design.getPmInteractionDiagram).toBe("function");
  });
});
