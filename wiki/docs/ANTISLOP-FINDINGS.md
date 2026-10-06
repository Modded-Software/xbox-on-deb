# Findings: AI slop, vibecoding anti-patterns, and this wiki

Research notes gathered 2026-10-06 before redesigning the StarCraft: Ghost
archive wiki. Part A records what the workspace already mandates. Part B records
vibecoding anti-patterns from the field. Part C records the AI design slop
taxonomy. Part D audits this wiki against that taxonomy. Part E notes what is
specific to this subject. Part F is the design brief the plan will follow.

## Part A: What the workspace already mandates

Searched `../WORKSPACE-CI` for governing guidance. The relevant documents:

| Document | What it owns |
| --- | --- |
| `docs/presentation-guardrails.md` | Core doctrine: enforcement lives in tooling, not prose |
| `docs/requirements/REQ-WIKI.md` | Portal principles: canonical sources, dense catalogues, explicit empty states |
| `docs/specifications/SPEC-WIKI.md` | Next.js reference implementation; catalogue + modal inspection pattern |
| `docs/requirements/REQ-WIKI-RESPONSIVE.md` | Breakpoints 480/768/1024, 320px floor, no horizontal scroll, fluid display type |
| `docs/requirements/REQ-WEB-COMPONENTS.md` | Theme contract: CSS custom-property tokens, three-tier system, light/dark |
| `web-components/src/styles/_variables.css` | The actual token system: palette, 4px spacing grid, type scale, radii |
| `workflows/WORKFLOW-WRITING-WIKIS.md` | Wiki structure, sourcing, citation, maintenance |
| `workflows/WORKFLOW-WRITING-WEBSITE-COPY.md` | Hero/catalogue copy, banned marketing patterns |
| `workflows/WORKFLOW-WRITING-README.md` | Prose style rules shared by all workflows |
| `workflows/WORKFLOW-CREATING-DIAGRAMS.md` | Mermaid rules |

The `../MOTHERFUCKING-SPA` reference adds the typography and restraint contract:

- `docs/requirements/REQ-MFSPA-TYPE.md`: `--measure: 60ch`, line-height 1.5, no
  webfonts, off-black on near-white, system font stack, single-column flow.
- `docs/research/02-evidence-library/mfspa-lineage-brutalism.md`: the
  motherfuckingwebsite lineage, web brutalism, and the bloat canon. Key line:
  "good design is as little design as possible."

Doctrine to carry forward:

1. **Enforcement, not instruction.** Rules live in tests and checks, not in a
   prompt. A design rule that cannot be tested will drift.
2. **Content is the design.** The workspace portal is a dense, source-backed
   catalogue. The equivalents here are tables, timelines, and an archive index.
3. **System fonts are a deliberate workspace choice**, not a default. The
   anti-slop advice to avoid system fonts collides with this contract. The
   resolution is to keep system fonts and buy distinctiveness elsewhere:
   typographic scale extremes, weight contrast, layout, color, and real
   imagery.
4. **Spend boldness in one place.** Keep the frame quiet; make one element the
   memorable thing.
5. **Budgets are design.** A route budget and a no-webfont rule are aesthetic
   constraints, not overhead.

## Part B: Vibecoding anti-patterns (systemic and code)

The code-level failures cohere into one mechanism: a model optimizes each output
for local plausibility and has no persistent architectural memory, so the whole
becomes incoherent even when each part looks fine.

| Anti-pattern | Mechanism | Source |
| --- | --- | --- |
| Duplicate implementations of one concept (five auth flows) | Later sessions re-add instead of replacing | Rogulia, "Vibe-coded codebase patterns" |
| Tests that assert nothing (assert the function ran) | Model tests implementation, not behavior | Rogulia; MasterPrompting |
| Unused / hallucinated dependencies | Model adds plausible packages | CSA research note (19.7% hallucinated deps) |
| Security defaults copied from tutorials | `localStorage` tokens, `CORS *`, string-built SQL | Rogulia; Veracode (45% OWASP failure) |
| Schema and docs drift from code | Migrations/README generated at different times | Rogulia |
| No ownership or architecture | "Everyone is a 10x engineer"; no review gate | Samuel Zhao, "Vibe Coding Anti-Patterns" |
| First output accepted unread | Appearance of competence suppresses review | Vybe; MasterPrompting |
| No error handling, no end-to-end test | Happy path only | Vybe; MasterPrompting |
| Context window overflow across a long session | Decisions drop and contradict | Vybe |

The lesson that applies to a static site: the same reflex that produces five auth
flows produces a card grid on every page and a purple accent because no decision
was recorded. Consistency must be written into a test, not remembered.

## Part C: AI design slop taxonomy

Sources: Anthropic's `frontend-design` skill and frontend-aesthetics cookbook;
`avoid-ai-design`; the AI Slop Detector and AI Slop Score tools; 925Studios;
Sailop's pattern catalogue; Developers Digest; refero `anti-ai-slop.md`.

The unified diagnosis: slop is the **absence of a decision**, not ugliness.
Models return the statistical median of training data, and the median web design
since 2019 is the Tailwind/shadcn default palette. Anthropic calls this
"distributional convergence."

### C1. Typography

- Inter, Roboto, Arial, Open Sans, and the raw system stack as unchosen defaults.
- The local maxima that replace them: Space Grotesk, Geist (the "new Inter").
- A single accent word italicized, bolded, or recolored in a headline.
- All-caps tracked-out labels and eyebrows above headings.
- Unnecessary labels above content.
- One-size type scale with no extremes ("use extremes: 100/200 vs 800/900, size
  jumps of 3x+").

### C2. Color

- Indigo-to-violet / purple-to-blue gradient, the single loudest tell.
- Gradient `background-clip: text` headlines.
- "Vibecode purple" / lavender-purple accents.
- Timid, evenly distributed palettes with no dominant color and sharp accent.
- Untouched shadcn zinc/slate; default Tailwind `blue-600`.
- Permanent dark mode with barely-passing body contrast, large colored glows.

### C3. Layout

- Full-viewport centered hero: eyebrow, H1, lede, CTA stacked on one axis.
- Badge above the H1 ("Now in beta").
- The three-equal-column icon-tile feature grid.
- Numbered 1-2-3 step sequences, stat banner rows.
- Four-column footer, three-tier pricing rings.
- Zero asymmetry, uniform `gap-4`/`p-6` with no spatial hierarchy.

### C4. Components and chrome

- The "SaaS-card kit": identical rounded cards, one `border-radius` regardless
  of hierarchy, the same soft grey shadow under every surface, gradient washes.
- `backdrop-blur` glassmorphism by reflex.
- The colored left-border card or blockquote (described as "almost as reliable a
  sign of AI-generated design as em-dashes are for AI-generated text").
- Icon-in-a-rounded-square; emoji as icons or feature bullets.
- Meta strings joined with middle dots (`A · B · C`).
- `WORD — fragment` labels with a spaced em dash.
- A monospace face used for small data labels; `→` appended to links.

### C5. Imagery

- **Text-only collapse.** The subject is image-led, but the agent cannot generate
  images, so it replaces photography, screenshots, and art with text and CSS
  blobs. This is the #9 tell in refero's list.
- Generic gradient placeholders, abstract blob backgrounds, weak CSS fakes for
  real imagery.
- AI-generated stock imagery; human hands, faces, and text are the highest-risk
  AI tells.
- "If the first viewport works fine without the hero image, the image is too
  weak."

### C6. Copy

- "Elevate / Seamless / Powerful", generic CTAs ("Get Started", "Learn more").
- Filler microcopy and invented metrics.

## Part D: Audit of this wiki

Honest pass over the wiki I just built, against Part C.

| Tell | Where | Verdict |
| --- | --- | --- |
| Purple accent | `site/assets/css/main.css` `--accent: #7a4bd0`, dark `--accent: #b79cf0` | Literally "vibecode purple." The loudest single tell. |
| Uniform rounded cards | `.cards li { border-radius: .5rem }`, `.facts`, `pre`, blockquote | The SaaS-card kit. |
| Auto-fit card grid | `.cards { grid-template-columns: repeat(auto-fit, minmax(15rem,1fr)) }` | The three-card reflex, generalized. |
| ALL-CAPS tracked label | `.facts h2 { text-transform: uppercase; letter-spacing: .06em }` | Tracked-out eyebrow label. |
| Middle-dot meta string | footer `Sources &middot; Colophon` on every page | The `A · B · C` tell. |
| Pill status chips with colored border | `.tag { border: 1px solid currentColor; border-radius: .25em }` | Colored-border chip reflex. |
| Centered single column, no asymmetry | `main { max-width: 68ch; margin: 0 auto }` | Generic article shell. |
| Zero images | every page | Text-only collapse of an image-rich subject. This is the worst one. |
| Purple lightning-bolt favicon | `site/assets/img/favicon.svg` | Purple default carried into the icon. |
| Permanent dark scheme | `color-scheme: light dark` + dark overrides | Acceptable, but must be checked for contrast. |

Not present, for credit: no gradient, no glassmorphism, no emoji, no gradient
text, no webfonts, no glow, no fake metrics, no marketing CTAs, no em dashes.

So the wiki is not maximally sloppy. It is forgettable: the frame is a generic
document shell, the accent is the default AI purple, and there is no content
imagery to carry a subject that is entirely made of imagery.

## Part E: What is specific to this subject

This is the opportunity that separates a de-slopped wiki from a merely recolored
one.

1. **The subject is image-led and the imagery is archived.** The official
   `blizzard.com/ghost` site is fully preserved on the Wayback Machine:
   screenshots, wallpapers, artwork, unit renders, trailer stills. Hidden Palace
   and the leak coverage hold build screenshots and the Xbox dev-kit photos.
   Concept art exists on ArtStation, IAMAG, Engadget, and Siliconera. Real
   assets exist; none should be generated.
2. **The subject has its own visual identity.** StarCraft: Ghost was a dark
   military sci-fi game: near-black space, HUD greens and ambers, Terran blue,
   Zerg organic greens, Protoss gold, and a Ghost/Nova key art in cold violet
   and steel. A palette sampled from the artifact is a decision made for this
   brief, which is exactly what the anti-slop guidance asks for.
3. **The subject is an archive of a cancellation.** The natural design metaphor
   is a **declassified dossier or mission archive**: hairline rules, file
   numbers, redaction bars, stamped status marks, an index rail, teletype
   monospace for identifiers, image plates with captions and credits. This is
   the broadsheet/archive direction Anthropic lists as a legitimate non-default,
   and it fits tables, timelines, and source lists better than cards.
4. **Copyright constrains the images, not the design.** Images stay gitignored
   under `res/`, local only, credited, never committed. The wiki references
   local paths and degrades to intentional captioned plates when a clone has no
   images.
5. **The subject's real imagery can carry the hero.** A Nova key-art plate or a
   build screenshot in the first viewport replaces the generic text hero.

## Part F: Design brief (proposed)

- **Concept.** A declassified mission archive for a game that was never
  released. Frame quiet and documentary; one bold gesture in the hero and in the
  typographic treatment of the case-file identifier.
- **Palette.** Derived from the artifact, 4 to 6 values: a near-black graphite
  base, a bone/field-manual paper for light mode, one cold signal accent (the
  Ghost violet-steel, used sparingly), a HUD amber/green for status, and a
  Terran red for "absent/cancelled." No gradients.
- **Type.** System stack retained (workspace contract). Distinctiveness from
  scale extremes and weight contrast, a fixed-width face for identifiers and
  table data, and a deliberate type scale with 3x jumps. No ALL-CAPS eyebrows.
- **Layout.** Asymmetric archive frame: an index rail or a left-aligned file
  header, hairline rules, zero or minimal radius, image plates, and a
  caption/credit system. Tables and timelines are first-class, not cards.
- **Media.** A curated set of real images, one dominant above-the-fold plate on
  the home page, contextual plates on article pages, and a gallery on the media
  page. Every image gets dimensions, alt text, a caption, and a source credit.
- **Boldness.** One memorable element: the hero image plate with an overlaid
  case-file header and the mission-archive index. Everything else stays plain.
- **Constraints preserved.** WCAG 2.2 AA, reduced motion, 320px to 1280px,
  route/JS/CSS budgets, no webfont, no third-party requests, documents-first,
  real archival imagery only.

## Sources

- Anthropic, "Improving frontend design through Skills", 2025-11-12, <https://claude.com/blog/improving-frontend-design-through-skills>.
- Anthropic, `frontend-design` skill, <https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md>.
- Anthropic, "Prompting for frontend aesthetics" cookbook, <https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics>.
- `avoid-ai-design`, <https://github.com/funboy322/avoid-ai-design>.
- refero, `anti-ai-slop.md`, <https://github.com/referodesign/refero_skill/blob/master/skills/refero-design/references/anti-ai-slop.md>.
- 925Studios, "AI Slop Fonts and Gradients", 2026-06-14, <https://www.925studios.co/blog/ai-slop-design-tells>.
- Sailop, "AI Slop Encyclopedia", 2026-03-20, <https://sailop.com/blog/ai-slop-encyclopedia>.
- Developers Digest, "AI Design Slop: 16 Patterns", <https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it>.
- Rogulia, "Vibe-coded codebase patterns", 2026-05-28, <https://iurii.rogulia.fi/blog/vibe-coded-codebase-patterns>.
- Zhao, "Vibe Coding Anti-Patterns", 2026-06-30, <https://samuelzhaoy.github.io/vibe-coding-anti-patterns/>.
- Cloud Security Alliance, "Vibe Coding Security Debt", 2026-04-06, <https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-codegen-vulnerability-debt-20260406-csa/>.
- Frontend Horizon, "AI Image Generation for Marketing Sites", 2026-03-22, <https://www.frontendhorizon.com/blog/ai-image-generation-for-marketing-sites-what-works-what-trips-the-slop-detector>.
