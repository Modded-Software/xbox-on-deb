#!/usr/bin/env node
// Emit a markdown index of fetched research artifacts from the .meta.json files.
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const TEXT = resolve(REPO, "res", "starcraft-ghost-archive", "text");
const W = "https://web.archive.org/web/";

const order = { official: 0, leak: 1, history: 2, reference: 3 };
const rows = [];
for (const f of readdirSync(TEXT)) {
  if (!f.endsWith(".meta.json")) continue;
  const name = f.replace(/\.meta\.json$/, "");
  const meta = JSON.parse(readFileSync(join(TEXT, f), "utf8"));
  const txt = join(TEXT, `${name}.txt`);
  const chars = statSync(txt).size;
  let live = meta.url;
  let snap = "";
  if (live.startsWith(W)) {
    snap = live;
    live = live.slice(W.length).replace(/^[^/]*id_\//, "");
  }
  rows.push({ name, kind: meta.kind ?? "", live, snap, chars });
}
rows.sort((a, b) => (order[a.kind] ?? 9) - (order[b.kind] ?? 9) || a.name.localeCompare(b.name));

const out = [];
out.push("| artifact | kind | live URL | chars |");
out.push("|---|---|---|---|");
for (const r of rows) {
  const link = r.snap ? `[snapshot](${r.snap})` : "";
  out.push(`| \`text/${r.name}.txt\` | ${r.kind} | ${r.live} ${link} | ${r.chars} |`);
}
const table = out.join("\n");

const doc = process.argv[2];
if (doc) {
  const BEGIN = "<!-- BEGIN GENERATED MANIFEST -->";
  const END = "<!-- END GENERATED MANIFEST -->";
  let md = readFileSync(doc, "utf8");
  const block = `${BEGIN}\n\n${table}\n\n${END}`;
  if (md.includes(BEGIN) && md.includes(END)) {
    md = md.replace(new RegExp(`${BEGIN}[\\s\\S]*${END}`), block);
  } else {
    md = md.trimEnd() + "\n\n" + block + "\n";
  }
  writeFileSync(doc, md);
  process.stdout.write(`updated ${doc} (${rows.length} rows)\n`);
} else {
  process.stdout.write(table + "\n");
}
