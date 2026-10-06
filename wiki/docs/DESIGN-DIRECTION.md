# Design direction: Retro StarCraft HUD

Locked 2026-10-06 for the StarCraft: Ghost archive wiki. Companion to
[`ANTISLOP-FINDINGS.md`](ANTISLOP-FINDINGS.md). This document is the brief the
CSS and pages follow. It records the decisions so the design does not drift back
to defaults.

## Concept

The wiki is a **decommissioned Terran tactical terminal**: the in-fiction HUD of
a game that was cancelled, repurposed as a research archive. The frame is a dark
military readout with green and amber phosphor, bracket panels, hairline rules,
and image plates. It is documentary first; the HUD treatment carries the subject
rather than decorating it.

One bold gesture: the hero is a full-bleed **image plate** framed with HUD corner
brackets and overlaid telemetry. Everything around it stays quiet.

## Anti-slop decisions

Recorded so each choice is a decision, not a default. See Part D of the findings
for the audit this answers.

| Default we are avoiding | Decision here |
| --- | --- |
| AI purple `#7a4bd0` / lavender | Phosphor green and amber, sampled from the game's own HUD palette |
| Indigo-to-violet gradients | No gradients. Flat panels and one scanline overlay |
| Rounded-2xl card kit | Angular bracket panels, zero radius, no soft shadows |
| Auto-fit three-card grid | A mission index rail plus data readouts and image plates |
| ALL-CAPS tracked eyebrow above every heading | Uppercase mono only for in-fiction data labels and readout headers |
| Middle-dot meta strings (`A · B · C`) | Slash-separated mono breadcrumbs (`A // B`) |
| Pill status chips with colored border | Bracketed mono status tokens (`[PRESENT]`) |
| Centered article column | Asymmetric terminal frame with a left index rail |
| Text-only collapse of image-rich subject | Real archival image plates, one dominant in the hero |
| Inter / Roboto / Space Grotesk / Geist | System stack retained per workspace contract; distinctiveness from scale, weight, and mono pairing |

Note on uppercase: the anti-slop guidance bans all-caps labels because they are
an unchosen default. Here the brief is a HUD, where uppercase monospace readouts
are the subject. They are confined to data labels and the status bar, and never
used as a decorative eyebrow above ordinary prose headings.

## Palette

Derived from the game's HUD and key art: near-black with a green cast, phosphor
green primary, amber secondary, Terran blue for information, red for cancelled
or absent, Protoss gold for a rare third accent. Six roles, no gradient.

### Dark (default)

| Token | Hex | Role |
| --- | --- | --- |
| `--bg` | `#0b0f0c` | Page background, near-black with a green cast |
| `--panel` | `#141a13` | Panel and table background |
| `--panel-2` | `#1d261b` | Raised panel, hover row |
| `--ink` | `#d7e4d0` | Body text |
| `--muted` | `#8fa08a` | Secondary text, captions |
| `--line` | `#2b3a29` | Hairline rules, panel borders |
| `--phosphor` | `#8dff9f` | Primary accent, active nav, links |
| `--amber` | `#ffb454` | Secondary accent, unwired status |
| `--info` | `#6cb6ff` | Informational links and tags |
| `--danger` | `#ff6b5e` | Absent and cancelled status |
| `--gold` | `#e8c15a` | Rare third accent (Protoss) |

### Light (daylight terminal)

| Token | Hex | Role |
| --- | --- | --- |
| `--bg` | `#eef1e8` | Field-manual paper |
| `--panel` | `#ffffff` | Panel |
| `--panel-2` | `#e2e8db` | Raised panel |
| `--ink` | `#12160f` | Body text |
| `--muted` | `#4b5546` | Secondary text |
| `--line` | `#c3ccbb` | Hairline rules |
| `--phosphor` | `#0b6b2f` | Primary accent (darkened for contrast) |
| `--amber` | `#8a5200` | Secondary accent |
| `--info` | `#10538f` | Information |
| `--danger` | `#a82a1f` | Absent and cancelled |
| `--gold` | `#7a5c00` | Third accent |

Contrast: body text meets 4.5:1 on its background in both schemes. Accent text on
panels meets 4.5:1 or is paired with an icon or label so color is not the only
signal. Status is always carried by the bracketed text, not color alone.

## Typography

System fonts only, per `REQ-MFSPA-TYPE` and the workspace no-webfont rule.

- **Body and display:** `system-ui, sans-serif`. One family, as the frontend
  skill recommends when a second face is not clearly distinct.
- **Data, identifiers, labels:** `ui-monospace, "SFMono-Regular", Menlo,
  Consolas, monospace`.
- **Scale with extremes:** display sizes use `clamp()` with roughly 3x jumps from
  body to hero, and weight contrast of 400 vs 700. No 1.5x increments.
- **Measure:** body capped near `64ch`. The terminal frame is wider than the
  prose column; prose blocks stay capped inside it.
- No all-caps eyebrows on prose headings. Mono uppercase is reserved for data
  labels such as `PLATE 03`, `STATUS`, `FILE ID`.

## Layout

Asymmetric terminal frame.

```
+------------------------------------------------------------------+
| STATUS BAR  SCG // ARCHIVE   BUILD 2004-05-08   [SOURCE LINKS]   |
+------------------------------------------------------------------+
| INDEX RAIL |  MISSION HEADER (file id, title, status)            |
| 01 HOME    |                                                  |
| 02 TIMELINE|  +--------------------------------------------+  |
| 03 HIST    |  |  HERO IMAGE PLATE  [ reticle corners ]     |  |
| 04 LEAK    |  |  overlaid telemetry line                   |  |
| 05 CAMPAIGN|  +--------------------------------------------+  |
| ...        |                                                  |
|            |  PROSE (capped measure)                          |
|            |  READOUT TABLES                                  |
|            |  IMAGE PLATES with PLATE nn captions             |
+------------------------------------------------------------------+
```

- **Status bar:** thin top strip, mono, carries the archive id and key build
  fact. Not sticky by default; it is chrome, not a nav bar.
- **Index rail:** primary navigation as a numbered mission index. On narrow
  viewports it becomes a horizontal scroller above the content (no off-canvas
  drawer, no JS dependency).
- **Panels:** angular, zero radius, 1px `--line` border with small corner
  brackets drawn in CSS. No box-shadow.
- **Tables:** readouts. Mono uppercase headers, hairline row rules, no zebra
  beyond a subtle `--panel-2` hover.
- **Figures:** image plate with corner brackets, a mono `PLATE nn` label, a
  caption, and a source credit.

## Media

The subject is image-led and the imagery is archived. Real assets only, never
generated.

- **Hero:** one dominant key-art or build-screenshot plate above the fold.
- **Articles:** contextual plates where the subject warrants (a mission, a
  weapon, a location, a studio). Not one stock image per page.
- **Media page:** a gallery of screenshots, wallpapers, and concept art.
- **Treatment:** each plate has intrinsic width and height, `loading="lazy"`
  except the hero, a caption, alt text, and a credit linking the source.
- **Absent images:** when the local (gitignored) image set is not present, the
  plate renders as an intentional bordered placeholder with the caption and
  credit. No fake imagery, no CSS blobs.
- **Copyright:** images are local only, under `res/` and
  `wiki/site/assets/img/`, both gitignored. The tracked
  `wiki/docs/IMAGE-CREDITS.md` maps each to its source and archive URL.

## Motion

Minimal and purposeful. A short HUD flicker or scanline is optional and must be
CSS-only, must not loop indefinitely, and must be disabled under
`prefers-reduced-motion`. The route transition reuses the existing
Navigation API upgrade. No scroll animations, no hover lifts.

## Boldness budget

One bold element: the hero image plate with reticle framing and telemetry. The
index rail, tables, and prose stay plain and disciplined. Before shipping, remove
one accessory: any HUD effect that does not serve the archive is cut.

## Constraints carried over

WCAG 2.2 AA, reduced motion, 320px to 1280px with no horizontal scroll,
per-route/JS/CSS budgets enforced by `tools/measure.mjs`, documents-first,
no webfont, no third-party requests, no tracking.
