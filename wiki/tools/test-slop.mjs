import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { SITE, findDocuments } from './lib-docs.mjs';

const CSS = readFileSync(join(SITE, 'assets', 'css', 'main.css'), 'utf8');

test('stylesheet avoids AI slop tells', () => {
  for (const banned of ['#7a4bd0', '#b79cf0', 'box-shadow', 'background-clip', 'backdrop-filter']) {
    assert.ok(!CSS.toLowerCase().includes(banned), `stylesheet contains banned pattern: ${banned}`);
  }
});

test('no decorative rounded cards in the stylesheet', () => {
  const radii = [...CSS.matchAll(/border-radius:\s*([^;]+);/g)].map((m) => m[1].trim());
  for (const radius of radii) {
    assert.ok(/^(0|999px)$/.test(radius), `unexpected border-radius (card-kit tell): ${radius}`);
  }
});

test('pages avoid AI slop copy and chrome', () => {
  for (const doc of findDocuments()) {
    const html = readFileSync(doc.file, 'utf8');
    assert.ok(!/&middot;|&nbsp;&middot;/.test(html), `${doc.file}: middle-dot separator`);
    assert.ok(!/\bGet Started\b|\bLearn more\b|\bElevate your\b|\bSeamless\b/i.test(html), `${doc.file}: generic AI copy`);
    assert.ok(!/href="(https?:)?\/\/fonts\./.test(html), `${doc.file}: webfont reference`);
  }
});
