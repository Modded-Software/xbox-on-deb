#!/usr/bin/env node
// Capture human-readable text + asset manifests from the user's own extracted
// build into res/starcraft-ghost-archive/ (gitignored). No game binaries copied
// beyond small plaintext tables already present as text.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const SRC = resolve(REPO, "extracted", "StarCraft Ghost Xbox Finn Hillbilly");
const OUT = resolve(REPO, "res", "starcraft-ghost-archive");
const TEXT = join(OUT, "build-text");
const MANIFEST = join(OUT, "build-manifest");
mkdirSync(TEXT, { recursive: true });
mkdirSync(MANIFEST, { recursive: true });

if (!existsSync(SRC)) {
  console.error(`extracted build not found: ${SRC}`);
  process.exit(1);
}

// 1. Plaintext UI tables + mission chronicles
const misc = join(SRC, "Misc");
let copied = 0;
for (const f of readdirSync(misc)) {
  if (f.endsWith(".nlt") || f.endsWith(".nsc") || f === "defaultText.nlt") {
    copyFileSync(join(misc, f), join(TEXT, f));
    copied++;
  }
}
console.log(`copied ${copied} text tables`);

// 2. Printable-string extraction from packed string/game files
function strings(buf, min = 4) {
  const out = [];
  // ASCII
  let cur = "";
  for (const b of buf) {
    if (b >= 0x20 && b <= 0x7e) cur += String.fromCharCode(b);
    else {
      if (cur.length >= min) out.push(cur);
      cur = "";
    }
  }
  if (cur.length >= min) out.push(cur);
  // UTF-16LE (printable low byte, 0x00 high byte)
  cur = "";
  for (let i = 0; i + 1 < buf.length; i += 2) {
    const lo = buf[i];
    const hi = buf[i + 1];
    if (hi === 0 && lo >= 0x20 && lo <= 0x7e) cur += String.fromCharCode(lo);
    else {
      if (cur.length >= min) out.push(cur);
      cur = "";
    }
  }
  if (cur.length >= min) out.push(cur);
  return [...new Set(out)];
}

for (const f of ["game.nls", "game.nlu", "game.nlx", "game.nfx", "JAP_game.nls", "KOR_game.nls"]) {
  const p = join(misc, f);
  if (!existsSync(p)) continue;
  const buf = readFileSync(p);
  const lines = strings(buf, 4);
  writeFileSync(join(TEXT, `${f}.strings.txt`), lines.join("\n"));
  console.log(`${f}: ${lines.length} strings`);
}

// 3. Asset manifests
function manifest(name, relDir, filter) {
  const d = join(SRC, relDir);
  if (!existsSync(d)) return;
  const all = readdirSync(d, { withFileTypes: true });
  const entries = all
    .filter((e) => (filter ? filter(e.name) : true))
    .map((e) => (e.isDirectory() ? `${e.name}/` : `${e.name}\t${readFileSync(join(d, e.name)).length}`));
  writeFileSync(join(MANIFEST, `${name}.txt`), entries.join("\n") + "\n");
  console.log(`${name}: ${entries.length} entries`);
}
manifest("levels", "Levels", (n) => !n.endsWith(".tga"));
manifest("cutscenes", "Cutscenes", (n) => n.endsWith(".nce") || n.endsWith(".ncs"));
manifest("video", "Video", (n) => n.endsWith(".bik") || n.endsWith(".vid"));
manifest("sounds", "Sounds");
manifest("ui-materials", "UI/Materials");
