/**
 * midas-nx simple-beam load-combination example.
 *
 * Risk level: 4 - high risk (see https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels).
 *
 * Ports the MIDAS-API manual repo's simple_beam_load_combination tutorial
 * (https://support.midasuser.com/hc/en-us/articles/30230181806361). A 10m
 * simply-supported beam (pinned/roller) is split into 20 elements, given
 * self-weight (DL) + a uniform beam load (SIDL), then combined into a single
 * load combination. A step up from quickstart.mjs's single-column example:
 * node/element generation in a loop, boundary conditions, and a multi-case
 * load combination.
 *
 * WARNING: doc.newProject() discards any unsaved work in whatever document is
 * currently open, even work unrelated to this script.
 *
 * Requires a running MIDAS Civil NX (or Gen NX) with Open API connected - set
 * MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running:
 *
 *     node examples/javascript/simple-beam-load-combination.mjs
 *
 * This is the JavaScript twin of
 * examples/python/simple_beam_load_combination.py, field for field.
 */
import { MidasClient, doc, resources } from "midas-nx";

// Reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from the environment.
const client = new MidasClient({ product: "civil" });

const { unit } = resources.db.project;
const { material } = resources.db.properties.material;
const { section } = resources.db.properties.section;
const { node, element } = resources.db.nodeElement;
const { constraint } = resources.db.boundary;
const { staticLoadCase, selfWeight, beamLoad } = resources.db.staticLoads;
const { loadCombinationGeneral } = resources.db.loadCombinations;

// -- inputs ---------------------------------------------------------------
const length = 10.0; // beam length (m)
const height = 1.0; // section height (m)
const width = 0.8; // section width (m)
const beamLoadValue = -30.0; // additional uniform load (kN/m, SIDL)
const materialId = 1;
const sectionId = 1;
const numDivisions = 20; // split the beam into 20 elements

// 1) New document
await doc.newProject({ client });

// 2) Units (m, kN)
await unit.update({ 1: { DIST: "M", FORCE: "KN" } }, client);

// 3) Material (RC C32)
await material.create(
  {
    1: {
      TYPE: "CONC",
      NAME: "C32",
      PARAM: [{ P_TYPE: 1, STANDARD: "AS17(RC)", DB: "C32" }],
    },
  },
  client,
);

// 4) Section (rectangular, value input)
await section.create(
  {
    1: {
      SECTTYPE: "DBUSER",
      SECT_NAME: "Rectangular",
      SECT_BEFORE: {
        USE_SHEAR_DEFORM: true,
        SHAPE: "SB",
        DATATYPE: 2,
        SECT_I: { vSIZE: [height, width] },
      },
    },
  },
  client,
);

// 5) Nodes (0 to length, split into numDivisions)
const interval = length / numDivisions;
const round6 = (value) => Number(value.toFixed(6));
await node.create(
  Object.fromEntries(
    Array.from({ length: numDivisions + 1 }, (_, i) => [
      i + 1,
      { X: round6(i * interval), Y: 0.0, Z: 0.0 },
    ]),
  ),
  client,
);

// 6) Elements (connect adjacent nodes as BEAM)
await element.create(
  Object.fromEntries(
    Array.from({ length: numDivisions }, (_, i) => [
      i + 1,
      { TYPE: "BEAM", MATL: materialId, SECT: sectionId, NODE: [i + 1, i + 2] },
    ]),
  ),
  client,
);

// 7) Boundary conditions (pin at the start, roller at the end)
const lastNodeId = numDivisions + 1;
await constraint.create(
  {
    1: { ITEMS: [{ ID: 1, CONSTRAINT: "1111000" }] },
    [lastNodeId]: { ITEMS: [{ ID: 1, CONSTRAINT: "0111000" }] },
  },
  client,
);

// 8) Load cases (DL for self-weight, SIDL for the additional load)
await staticLoadCase.create(
  {
    1: { NAME: "DL", TYPE: "USER", DESC: "Dead Load" },
    2: { NAME: "SIDL", TYPE: "USER", DESC: "Super Imposed Dead Load" },
  },
  client,
);

// 9) Self-weight (DL load case, -Z direction, factor 1)
await selfWeight.create({ 1: { LCNAME: "DL", FV: [0, 0, -1] } }, client);

// 10) Uniform beam load (SIDL, applied to every element)
await beamLoad.create(
  Object.fromEntries(
    Array.from({ length: numDivisions }, (_, i) => [
      i + 1,
      {
        ITEMS: [
          {
            ID: 1,
            LCNAME: "SIDL",
            CMD: "BEAM",
            TYPE: "UNILOAD",
            DIRECTION: "GZ",
            D: [0, 1],
            P: [beamLoadValue, beamLoadValue],
          },
        ],
      },
    ]),
  ),
  client,
);

// 11) Load combination (DL*1.2 + SIDL*1.5)
await loadCombinationGeneral.create(
  {
    1: {
      NAME: "Comb1",
      ACTIVE: "ACTIVE",
      iTYPE: 0,
      vCOMB: [
        { ANAL: "ST", LCNAME: "DL", FACTOR: 1.2 },
        { ANAL: "ST", LCNAME: "SIDL", FACTOR: 1.5 },
      ],
    },
  },
  client,
);

// 12) Save
await doc.save({ client });

console.log("Simple beam and load combination created.");
