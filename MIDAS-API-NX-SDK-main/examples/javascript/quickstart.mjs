/**
 * midas-nx quick start - creates a model. See verify-and-read.mjs for a
 * read-only alternative that is safe to run against a real project.
 *
 * Risk level: 4 - high risk (see https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels).
 *
 * Ports the MIDAS-API manual repo's README quick-start example: create a new
 * document, set units, define a material/section, place two nodes, connect
 * them with a column element, then save.
 *
 * WARNING: doc.newProject() discards any unsaved work in whatever document is
 * currently open in Gen NX/Civil NX, even work unrelated to this script. Only
 * run this against a blank project, or one you don't mind losing unsaved
 * changes in.
 *
 * Requires a running MIDAS Gen NX (or Civil NX) with Open API connected - set
 * MIDAS_MAPI_KEY (and optionally MIDAS_BASE_URL) before running:
 *
 *     node examples/javascript/quickstart.mjs
 *
 * This is the JavaScript twin of examples/python/quickstart.py, field for
 * field.
 */
import { MidasClient, doc, resources } from "midas-nx";

// Reads MIDAS_MAPI_KEY / MIDAS_BASE_URL from the environment.
const client = new MidasClient({ product: "gen" });

const { unit } = resources.db.project;
const { material } = resources.db.properties.material;
const { section } = resources.db.properties.section;
const { node, element } = resources.db.nodeElement;

// 1) New document
await doc.newProject({ client });

// 2) Units (m, tonf)
await unit.update({ 1: { DIST: "M", FORCE: "TONF" } }, client);

// 3) Material (RC)
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

// 4) Section (rectangular column)
await section.create(
  {
    1: {
      SECTTYPE: "DBUSER",
      SECT_NAME: "H300x150",
      SECT_BEFORE: {
        SHAPE: "H",
        OFFSET_PT: "CC",
        DATATYPE: 1, // 1=DB, 2=User - sibling of SECT_I, not nested inside it
        SECT_I: { DB_NAME: "KS21", SECT_NAME: "H300x150x6.5/9" },
      },
    },
  },
  client,
);

// 5) Two nodes
await node.create(
  {
    1: { X: 0, Y: 0, Z: 0 },
    2: { X: 0, Y: 0, Z: 3.2 },
  },
  client,
);

// 6) Column element (BEAM type)
await element.create(
  { 1: { TYPE: "BEAM", MATL: 1, SECT: 1, NODE: [1, 2], ANGLE: 0 } },
  client,
);

// 7) Save
await doc.save({ client });

console.log("Model created.");
