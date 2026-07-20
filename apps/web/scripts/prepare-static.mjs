import {readFile, writeFile} from "node:fs/promises";
import {resolve} from "node:path";

const input = process.argv[2];
if (!input) throw new Error("Usage: node scripts/prepare-static.mjs <lab.html>");

const path = resolve(process.cwd(), input);
const html = await readFile(path, "utf8");
const inlineScriptPattern = /<script(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script>/gi;
const matches = [...html.matchAll(inlineScriptPattern)];
const externalTag = '<script src="/lab.js" defer></script>';

let prepared = html;
if (matches.length === 1) {
  prepared = html.replace(inlineScriptPattern, externalTag);
} else if (matches.length === 0 && html.includes(externalTag)) {
  prepared = html;
} else {
  throw new Error(`Expected exactly one inline Lab script, found ${matches.length}.`);
}

if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(prepared)) {
  throw new Error("Prepared Lab document still contains inline JavaScript.");
}
if (!prepared.includes(externalTag)) {
  throw new Error("Prepared Lab document does not load /lab.js.");
}

await writeFile(path, prepared, "utf8");
console.log(`Prepared CSP-safe static Lab document: ${path}`);
