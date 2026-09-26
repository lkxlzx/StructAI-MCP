/**
 * midas-nx KDS 41 12:2022 wind-load example.
 *
 * Risk level: 4 - high risk (see https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels).
 * It also runs an analysis, which can take a while and is not interruptible
 * from here.
 *
 * Creates a plate element and applies a pressure (wind) load to it, per
 * docs/manual/06_DB_Static_Loads.md #10 (/db/PRES) in the MIDAS-API manual
 * repo.
 *
 * WARNING: doc.newProject() discards any unsaved work in whatever document is
 * currently open, even work unrelated to this script.
 *
 * Requires a running MIDAS Gen NX (or Civil NX) with Open API connected - set
 * MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running:
 *
 *     node examples/javascript/kds-wind-load.mjs
 *
 * This is the JavaScript twin of examples/python/kds_wind_load.py, field for
 * field.
 */
import { MidasClient, doc, resources } from "midas-nx";

// Reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from the environment.
const client = new MidasClient({ product: "gen" });

const { unit } = resources.db.project;
const { node, element } = resources.db.nodeElement;
const { thickness } = resources.db.properties.thickness;
const { staticLoadCase, pressureLoad } = resources.db.staticLoads;

await doc.newProject({ client });
await unit.update({ 1: { DIST: "M", FORCE: "KN" } }, client);

// Wind load case (KDS 41 12:2022)
await staticLoadCase.create(
  { 1: { NAME: "WIND_X_KDS", TYPE: "W", DESC: "KDS 풍하중 X방향" } },
  client,
);

// 3x3m plate at Z=5
await node.create(
  {
    1: { X: 0, Y: 0, Z: 5 },
    2: { X: 3, Y: 0, Z: 5 },
    3: { X: 3, Y: 3, Z: 5 },
    4: { X: 0, Y: 3, Z: 5 },
  },
  client,
);

await thickness.create(
  {
    1: {
      NAME: "T1000",
      TYPE: "VALUE",
      bINOUT: false,
      T_IN: 1.0,
      T_OUT: 0,
      O_VALUE: 0,
    },
  },
  client,
);

await element.create(
  { 1: { TYPE: "PLATE", SECT: 1, NODE: [1, 2, 3, 4], STYPE: 1 } },
  client,
);

// Pressure load: 1.5 kN/m^2, global X direction (negative = suction).
// DIRECTION is always sent explicitly - the documented default is refused for
// a PLATE + FACE pressure, and which way a pressure acts is an engineering
// decision an SDK must not pick.
await pressureLoad.create(
  {
    1: {
      ITEMS: [
        {
          ID: 1,
          LCNAME: "WIND_X_KDS",
          CMD: "PRES",
          ELEM_TYPE: "PLATE",
          FACE_EDGE_TYPE: "FACE",
          DIRECTION: "GX",
          EDGE_FACE: 1,
          FORCES: [-1.5, 0, 0, 0, 0],
        },
      ],
    },
  },
  client,
);

await doc.save({ client });
await doc.analyze({ client });

console.log("Wind load applied and analysis run.");
