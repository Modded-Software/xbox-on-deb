import { readdirSync, statSync } from 'node:fs';
import { join, dirname, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const SITE = join(ROOT, 'site');

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

export function findDocuments() {
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

export function routePathOf(locale, file) {
  const rel = posix.join(...file.slice(join(SITE, locale).length + 1).split(/[\\/]/));
  if (rel === 'index.html') {
    return `/${locale}/`;
  }
  if (rel === '404.html') {
    return `/${locale}/404.html`;
  }
  return `/${locale}/${posix.dirname(rel)}/`;
}
