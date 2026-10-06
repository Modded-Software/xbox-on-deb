import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { SITE, findDocuments, routePathOf } from './lib-docs.mjs';

const MEDIA = join(SITE, 'assets', 'media');
const MANIFEST = join(MEDIA, 'manifest.json');
const hasManifest = existsSync(MANIFEST);
const docs = findDocuments();

function checkOneDocument(doc) {
  const html = readFileSync(doc.file, 'utf8');
  const route = routePathOf(doc.locale, doc.file);

  const h1s = html.match(/<h1\b[^>]*>/g) ?? [];
  assert.equal(h1s.length, 1, `${route}: exactly one h1`);
  assert.match(h1s[0], /tabindex="-1"/, `${route}: h1 carries tabindex="-1"`);

  assert.match(html, /<a href="#main" class="skip-link">/, `${route}: skip link present`);
  assert.match(html, /<main id="main">/, `${route}: main landmark`);
  assert.match(html, /<footer>/, `${route}: footer landmark`);
  assert.match(html, /<nav[^>]*aria-label="Primary"/, `${route}: labelled primary nav`);
  const currents = html.match(/aria-current="page"/g) ?? [];
  assert.ok(currents.length <= 1, `${route}: at most one aria-current`);

  assert.match(html, /<div id="announcer" role="status"><\/div>/, `${route}: announcer`);
  assert.match(html, /<title>[^<]{4,}<\/title>/, `${route}: non-empty title`);
  assert.match(html, /<meta name="description" content="[^"]{20,}">/, `${route}: meta description`);
  assert.match(html, new RegExp(`<html lang="${doc.locale}">`), `${route}: html lang matches locale dir`);

  assert.match(html, /<script type="module" src="\/assets\/js\/main\.js"><\/script>/, `${route}: module upgrade script`);
  assert.match(html, /<link rel="stylesheet" href="\/assets\/css\/main\.css">/, `${route}: stylesheet`);

  assert.doesNotMatch(html, /src="https?:\/\//, `${route}: no third-party asset origins`);
  assert.doesNotMatch(html, /\son[a-z]+="/i, `${route}: no inline event handlers`);
  assert.doesNotMatch(html, /&middot;/, `${route}: no middle-dot meta separators`);

  for (const match of html.matchAll(/<img\b[^>]*>/g)) {
    const tag = match[0];
    assert.match(tag, /alt="[^"]+"/, `${route}: image needs non-empty alt: ${tag}`);
    assert.match(tag, /width="\d+"/, `${route}: image needs width: ${tag}`);
    assert.match(tag, /height="\d+"/, `${route}: image needs height: ${tag}`);
    assert.ok(
      /loading="lazy"/.test(tag) || /fetchpriority="high"/.test(tag),
      `${route}: image needs loading=lazy or fetchpriority=high: ${tag}`,
    );
    const src = tag.match(/src="(\/assets\/media\/[^"]+)"/);
    if (src && hasManifest) {
      const target = join(SITE, src[1]);
      assert.ok(existsSync(target), `${route}: image asset missing: ${src[1]}`);
    }
  }

  for (const match of html.matchAll(/href="(\/[^"#]*)"/g)) {
    const target = join(SITE, match[1]);
    const resolved = match[1].endsWith('/') ? join(target, 'index.html') : target;
    assert.ok(existsSync(resolved) && statSync(resolved).isFile(), `${route}: internal link target missing: ${match[1]}`);
  }
}

for (const doc of docs) {
  test(`document contract: ${routePathOf(doc.locale, doc.file)}`, () => {
    checkOneDocument(doc);
  });
}

test('image manifest integrity', { skip: !hasManifest }, () => {
  const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8'));
  assert.ok(manifest.images.length >= 40, 'expected a curated set of images');
  for (const image of manifest.images) {
    assert.ok(existsSync(join(MEDIA, `${image.id}.webp`)), `missing webp: ${image.id}`);
    assert.ok(existsSync(join(MEDIA, `${image.id}.jpg`)), `missing jpg: ${image.id}`);
    assert.ok(image.width > 0 && image.height > 0, `bad dimensions: ${image.id}`);
    assert.ok(image.alt && image.caption && image.credit, `missing credit fields: ${image.id}`);
    assert.match(image.url, /^https?:\/\/(www\.)?blizzard\.com\//, `unexpected source: ${image.id}`);
  }
});
