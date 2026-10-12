# StarCraft: Ghost archive wiki

A static reference wiki about the cancelled StarCraft: Ghost and the May 8 2004
Xbox build that leaked in 2020. It documents the development history, the leaked
artifact, and the gap between the announced feature set and what the build
contains.

The wiki is a documents-first static site. Every route is a complete HTML
document that renders and reads with JavaScript off. A few kilobytes of vanilla
JavaScript upgrade same-origin navigation with the Navigation API and View
Transitions. There is no framework, no build step, no webfont, and no
third-party request.

## Layout

```
site/
  assets/
    css/main.css        hand-written stylesheet (Retro StarCraft HUD)
    js/                 main.js, router.js, transitions.js
    img/favicon.svg
    media/              optimized images (gitignored; see Images)
    routes.json         generated route registry
  en/
    index.html          home
    <route>/index.html  one document per route
    404.html
  robots.txt
  sitemap.xml
docs/
  ANTISLOP-FINDINGS.md  research on AI slop and the audit of this wiki
  DESIGN-DIRECTION.md   the committed art direction
  IMAGE-CREDITS.md      generated image provenance
tools/
  lib-docs.mjs          document discovery
  lib-server.mjs        static file server
  serve.mjs             start the local server
  serve.sh              run the server from the wiki root
  test-documents.mjs    document contract, image, and link checks
  test-slop.mjs         anti-slop stylesheet and copy lint
  measure.mjs           page-weight measurement and receipts
  run-tests.sh          checks plus test run
  measure.sh            rewrite the receipts block
```

## Images

The imagery is real archived material from the official StarCraft: Ghost
website, fetched through the Wayback Machine. Nothing is generated, and no
copyrighted file is committed.

- `scripts/ghost-research/image-sources.json` (tracked) is the curated source
  list with role, caption, alt, and credit.
- `scripts/ghost-research/images.py` downloads originals into `res/` and writes
  WebP and JPEG derivatives into `wiki/site/assets/media/`, both gitignored.
- `wiki/docs/IMAGE-CREDITS.md` (tracked) records every image's source and archive
  URL.

Rebuild the image set (needs Pillow, installed in `.venv-wiki`):

```sh
python3 -m venv .venv-wiki && .venv-wiki/bin/pip install Pillow
.venv-wiki/bin/python scripts/ghost-research/images.py
```

Without the media directory, pages render captioned placeholder plates instead of
broken images. See [`docs/DESIGN-DIRECTION.md`](docs/DESIGN-DIRECTION.md) for the
palette and layout contract.

## Serve locally

The wiki ships a small static server, the same in-process Node server the tests
use. From this directory:

```sh
bash tools/serve.sh              # http://127.0.0.1:18082/en/
PORT=18173 bash tools/serve.sh   # pick another port
```

Any static file server also works, for example
`python3 -m http.server 8080 --directory site`.

## Test

```sh
bash tools/run-tests.sh
```

That measures every route against the page-weight budgets, verifies the colophon
receipts are current, checks image integrity, runs the anti-slop lint, and
asserts the document contract on every page: one heading, landmarks, a labelled
primary nav, an announcer, image alt and dimensions, no third-party asset
origins, and internal links that resolve.

Rewrite the receipts block after editing pages:

```sh
bash tools/measure.sh
```

## Sources and legal

Facts are drawn from public sources, listed on the wiki's sources page with live
and archived links. The build-derived facts come from the extracted data
documented in `../docs/05-research-archive.md` and
`../docs/06-vision-vs-build-gap-analysis.md`.

This wiki does not host the leaked build or any copyrighted assets. StarCraft
and StarCraft: Ghost are trademarks of Blizzard Entertainment.
