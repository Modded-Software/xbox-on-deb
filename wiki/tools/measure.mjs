#!/usr/bin/env node
import { brotliCompressSync, constants } from 'node:zlib';
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = join(ROOT, 'site');
const ASSETS = join(SITE, 'assets');

const ROUTE_BUDGET = 50 * 1024;
const JS_BUDGET = 8 * 1024;
const CSS_BUDGET = 8 * 1024;

const MARKER_START = '<!-- receipts:start -->';
const MARKER_END = '<!-- receipts:end -->';

function brotliSize(content) {
  return brotliCompressSync(content, {
    params: { [constants.BROTLI_PARAM_QUALITY]: 11 },
  }).length;
}

function walk(dir) {
  const entries = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      entries.push(...walk(path));
    } else {
      entries.push(path);
    }
  }
  return entries;
}

function findDocuments() {
  const docs = [];
  for (const locale of readdirSync(SITE)) {
    const localeDir = join(SITE, locale);
    if (!statSync(localeDir).isDirectory()) {
      continue;
    }
    for (const file of walk(localeDir)) {
      if (file.endsWith('index.html') || file.endsWith('404.html')) {
        docs.push({ locale, file });
      }
    }
  }
  return docs;
}

function routePathOf(locale, file) {
  const rel = posix.join(...file.slice(join(SITE, locale).length + 1).split(/[\\/]/));
  if (rel === 'index.html') {
    return `/${locale}/`;
  }
  if (rel === '404.html') {
    return `/${locale}/404.html`;
  }
  return `/${locale}/${posix.dirname(rel)}/`;
}

function htmlAssetRefs(html) {
  const refs = new Set();
  for (const match of html.matchAll(/(?:href|src)="(\/[^"#]+)"/g)) {
    const url = match[1];
    if (/\.(css|js|mjs|svg|png|ico|webmanifest)$/.test(url)) {
      refs.add(url);
    }
  }
  return refs;
}

function jsImports(source) {
  const refs = new Set();
  for (const match of source.matchAll(/from\s+'([^']+)'/g)) {
    refs.add(match[1]);
  }
  return refs;
}

function resolveJsGraph(entryUrl) {
  const seen = new Set();
  const queue = [entryUrl];
  while (queue.length > 0) {
    const url = queue.pop();
    if (seen.has(url)) {
      continue;
    }
    seen.add(url);
    const filePath = join(SITE, url);
    const source = readFileSync(filePath, 'utf8');
    for (const specifier of jsImports(source)) {
      if (specifier.startsWith('.')) {
        queue.push(posix.normalize(posix.join(posix.dirname(url), specifier)));
      } else if (specifier.startsWith('/')) {
        queue.push(specifier);
      }
    }
  }
  return seen;
}

function stripReceipts(content) {
  const start = content.indexOf(MARKER_START);
  const end = content.indexOf(MARKER_END);
  if (start === -1 || end === -1) {
    return content;
  }
  return content.slice(0, start + MARKER_START.length) + content.slice(end);
}

function measureRoute(doc) {
  const html = Buffer.from(stripReceipts(readFileSync(doc.file, 'utf8')));
  const files = new Map();
  files.set(doc.file, html);
  const jsUrls = [];
  for (const url of htmlAssetRefs(html.toString('utf8'))) {
    if (url.endsWith('.js') || url.endsWith('.mjs')) {
      jsUrls.push(url);
    } else {
      files.set(join(SITE, url), readFileSync(join(SITE, url)));
    }
  }
  let jsRaw = 0;
  let jsCompressed = 0;
  for (const entry of jsUrls) {
    for (const url of resolveJsGraph(entry)) {
      const filePath = join(SITE, url);
      if (files.has(filePath)) {
        continue;
      }
      const content = readFileSync(filePath);
      files.set(filePath, content);
      jsRaw += content.length;
      jsCompressed += brotliSize(content);
    }
  }
  if (jsUrls.length > 0) {
    for (const dataFile of ['locales.json', 'routes.json']) {
      const filePath = join(ASSETS, dataFile);
      if (!files.has(filePath) && existsSync(filePath)) {
        files.set(filePath, readFileSync(filePath));
      }
    }
  }
  let raw = 0;
  let compressed = 0;
  let cssRaw = 0;
  let cssCompressed = 0;
  for (const [filePath, content] of files) {
    raw += content.length;
    compressed += brotliSize(content);
    if (filePath.endsWith('.css')) {
      cssRaw += content.length;
      cssCompressed += brotliSize(content);
    }
  }
  return { raw, compressed, jsRaw, jsCompressed, cssRaw, cssCompressed };
}

function kb(bytes) {
  return (bytes / 1024).toFixed(2);
}

function receiptsBlock(rows, maxJs, maxCss) {
  const lines = [];
  lines.push('<table>');
  lines.push('<thead><tr><th>Route</th><th data-n>Raw</th><th data-n>Brotli</th></tr></thead>');
  lines.push('<tbody>');
  for (const row of rows) {
    lines.push(`<tr><td><code>${row.route}</code></td><td data-n>${kb(row.raw)} KB</td><td data-n>${kb(row.compressed)} KB</td></tr>`);
  }
  lines.push('</tbody>');
  lines.push('</table>');
  lines.push(`<p>JavaScript: ${kb(maxJs.compressed)} KB Brotli, ${kb(maxJs.raw)} KB raw (budget 8 KB). CSS: ${kb(maxCss.compressed)} KB Brotli, ${kb(maxCss.raw)} KB raw (budget 8 KB). Route budget 50 KB Brotli. Measured from the files in this commit.</p>`);
  return lines.join('\n');
}

function writeRoutesJson(docs) {
  const routes = {};
  for (const doc of docs) {
    if (doc.file.endsWith('index.html')) {
      (routes[doc.locale] ??= []).push(routePathOf(doc.locale, doc.file));
    }
  }
  for (const list of Object.values(routes)) {
    list.sort();
  }
  const target = join(ASSETS, 'routes.json');
  const content = `${JSON.stringify({ routes }, null, 2)}\n`;
  writeFileSync(target, content);
  return target;
}

function updateColophon(locale, block, checkOnly) {
  const colophon = join(SITE, locale, 'colophon', 'index.html');
  const source = readFileSync(colophon, 'utf8');
  const start = source.indexOf(MARKER_START);
  const end = source.indexOf(MARKER_END);
  if (start === -1 || end === -1) {
    throw new Error(`receipts markers missing in ${colophon}`);
  }
  const current = source.slice(start + MARKER_START.length, end).trim();
  if (current === block) {
    return false;
  }
  if (checkOnly) {
    throw new Error(`receipts in ${colophon} are stale; run node tools/measure.mjs`);
  }
  const updated = `${source.slice(0, start + MARKER_START.length)}\n${block}\n${source.slice(end)}`;
  writeFileSync(colophon, updated);
  return true;
}

function measureAll(docs) {
  const rows = [];
  const failures = [];
  let maxJs = { raw: 0, compressed: 0 };
  let maxCss = { raw: 0, compressed: 0 };
  for (const doc of docs) {
    const route = routePathOf(doc.locale, doc.file);
    const measured = measureRoute(doc);
    rows.push({ route, ...measured });
    if (measured.jsCompressed > maxJs.compressed) {
      maxJs = { raw: measured.jsRaw, compressed: measured.jsCompressed };
    }
    if (measured.cssCompressed > maxCss.compressed) {
      maxCss = { raw: measured.cssRaw, compressed: measured.cssCompressed };
    }
    if (measured.compressed >= ROUTE_BUDGET) {
      failures.push(`${route} weighs ${kb(measured.compressed)} KB Brotli, budget ${kb(ROUTE_BUDGET)} KB`);
    }
    if (measured.jsCompressed >= JS_BUDGET) {
      failures.push(`${route} ships ${kb(measured.jsCompressed)} KB of Brotli JavaScript, budget ${kb(JS_BUDGET)} KB`);
    }
    if (measured.cssCompressed >= CSS_BUDGET) {
      failures.push(`${route} ships ${kb(measured.cssCompressed)} KB of Brotli CSS, budget ${kb(CSS_BUDGET)} KB`);
    }
  }
  rows.sort((a, b) => a.route.localeCompare(b.route));
  return { rows, failures, block: receiptsBlock(rows, maxJs, maxCss) };
}

function main() {
  const checkOnly = process.argv.includes('--check');
  const docs = findDocuments();
  if (docs.length === 0) {
    throw new Error('no documents found under site/');
  }
  if (!checkOnly) {
    writeRoutesJson(docs);
    console.log('routes.json regenerated');
  }
  const locales = [...new Set(docs.map((doc) => doc.locale))];
  let result = null;
  for (let iteration = 0; iteration < 5; iteration += 1) {
    result = measureAll(docs);
    let changed = false;
    for (const locale of locales) {
      changed = updateColophon(locale, result.block, checkOnly) || changed;
    }
    if (!changed) {
      break;
    }
    console.log(`receipts updated (pass ${iteration + 1})`);
  }
  console.log(result.block);
  if (result.failures.length > 0) {
    for (const failure of result.failures) {
      console.error(`BUDGET EXCEEDED: ${failure}`);
    }
    process.exit(1);
  }
}

main();
