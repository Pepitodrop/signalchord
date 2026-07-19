import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {resolve} from "node:path";

import {
  compileMerzSpeech,
  transpileMerzSpeech,
} from "../apps/web/src/vendor/merzato-lang/merzSpeech.js";

const root = resolve(import.meta.dirname, "..");
const memePath = resolve(root, "apps/web/public/programs/merz/meme-cabinet.merz");
const graphPath = resolve(root, "apps/web/public/programs/merz/graph-growth-briefing.merz");
const canonicalVelatoPath = resolve(root, "velato/programs/live-graph-minute.vasm");
const publicVelatoPath = resolve(root, "apps/web/public/programs/velato/live-graph-minute.vasm");

const [memeSource, graphSource, canonicalVelato, publicVelato] = await Promise.all([
  readFile(memePath, "utf8"),
  readFile(graphPath, "utf8"),
  readFile(canonicalVelatoPath, "utf8"),
  readFile(publicVelatoPath, "utf8"),
]);

const memeProgram = compileMerzSpeech(memeSource, {filename: "meme-cabinet.merz"});
const graphProgram = compileMerzSpeech(graphSource, {filename: "graph-growth-briefing.merz"});
const memeAssembly = transpileMerzSpeech(memeSource);
const graphAssembly = transpileMerzSpeech(graphSource);

assert.ok(memeProgram.instructions.length > 70, "meme cabinet should remain a substantial executable speech program");
assert.match(memeAssembly, /call helfer/);
assert.match(memeAssembly, /helfer:/);
assert.match(memeAssembly, /ret/);
assert.match(memeAssembly, /jmp ausgabe/);
assert.match(memeSource, /Was ist Bubatz\?/);
assert.match(memeSource, /Regierungsflieger statt Privatflieger\./);

assert.ok(graphProgram.instructions.length > 15, "graph briefing should remain executable");
assert.match(graphAssembly, /call graph_score/);
assert.match(graphAssembly, /graph_score:/);
assert.match(graphAssembly, /store r10/);
assert.match(graphAssembly, /ret/);

assert.equal(publicVelato, canonicalVelato, "public Velato source must match the canonical checked-in policy");
const velatoInstructions = canonicalVelato
  .split(/\r?\n/)
  .map(line => line.replace(/#.*$/, "").trim())
  .filter(Boolean);
assert.equal(velatoInstructions.length, 100, "Live Graph Minute must remain exactly 100 instructions");
assert.equal(velatoInstructions.at(-1), "HALT");

console.log("Creative Merzato and Velato programs validated.");
