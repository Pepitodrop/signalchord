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
const labScriptPath = resolve(root, "apps/web/public/lab.js");
const prepareStaticPath = resolve(root, "apps/web/scripts/prepare-static.mjs");
const webPackagePath = resolve(root, "apps/web/package.json");
const nginxPath = resolve(root, "infrastructure/docker/web-nginx.conf");

const [
  memeSource,
  graphSource,
  canonicalVelato,
  publicVelato,
  labScript,
  prepareStatic,
  webPackageSource,
  nginx,
] = await Promise.all([
  readFile(memePath, "utf8"),
  readFile(graphPath, "utf8"),
  readFile(canonicalVelatoPath, "utf8"),
  readFile(publicVelatoPath, "utf8"),
  readFile(labScriptPath, "utf8"),
  readFile(prepareStaticPath, "utf8"),
  readFile(webPackagePath, "utf8"),
  readFile(nginxPath, "utf8"),
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

// Parse the browser script in CI and enforce the secure build-time loading path.
new Function(labScript);
assert.match(labScript, /webkitAudioContext/);
assert.match(labScript, /speechSynthesis/);
assert.match(labScript, /createDynamicsCompressor/);
assert.match(prepareStatic, /<script src=\"\/lab\.js\" defer><\/script>/);
assert.match(prepareStatic, /Prepared Lab document still contains inline JavaScript/);
assert.match(JSON.parse(webPackageSource).scripts.build, /prepare-static\.mjs dist\/lab\.html/);
assert.doesNotMatch(nginx, /sub_filter/);
assert.doesNotMatch(nginx, /script-src[^;]*unsafe-inline/);

console.log("Creative Merzato, Velato, speech and CSP-safe Live Lab paths validated.");
