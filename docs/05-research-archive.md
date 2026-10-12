# 05 — StarCraft: Ghost research archive

Annotated index of every source gathered about **StarCraft: Ghost**'s
development and the 2020 leak, plus what was extracted from the user's own copy
of the build.

> **Legal.** The game build and its data are unreleased, copyrighted material.
> Nothing copyrighted is committed to this repo. All fetched pages and
> build-derived text live under `res/`, which is **gitignored**; the tracked
> docs contain only links, metadata and original analysis. Get the leak and any
> third-party assets yourself.

---

## How this was collected

- Fetching uses the workspace `browser` CLI (Playwright/Chromium) via
  [`scripts/ghost-research/fetch.mjs`](../scripts/ghost-research/fetch.mjs).
  It navigates with a real browser, then extracts visible page text in
  64 KB chunks with `extract get-text`.
- Website origins are enumerated from the Internet Archive CDX index for
  `blizzard.com/ghost/*` (539 archived URLs) — captured to
  `res/starcraft-ghost-archive/ghost_cdx.txt`.
- Archives are read through Wayback **raw** snapshots (`…/web/<ts>id_/<url>`),
  which serves the original bytes and avoids the injected `wombat.js` that
  breaks DOM inspection.
- Sites behind Cloudflare (Kotaku, BetaArchive, NeoGAF, GameSpot, Fandom, …)
  are fetched from Wayback instead of live.
- Build-side text is extracted by
  [`scripts/ghost-research/extract-build-text.mjs`](../scripts/ghost-research/extract-build-text.mjs)
  from `extracted/StarCraft Ghost Xbox Finn Hillbilly/`.
- Re-run everything:

  ```sh
  node scripts/ghost-research/fetch.mjs            # ~95 sources -> res/.../text
  node scripts/ghost-research/extract-build-text.mjs
  node scripts/ghost-research/manifest.mjs         # regenerate the table below
  ```

## Artifact layout (all gitignored under `res/starcraft-ghost-archive/`)

| Path | Contents |
|------|----------|
| `text/<name>.txt` | Visible text of each source |
| `text/<name>.meta.json` | Fetch metadata (URL, byte counts, checksum) |
| `build-text/*.nlt`, `*.nsc` | The build's own UI/lore text tables and mission chronicle |
| `build-text/*.strings.txt` | Printable strings from the packed string tables |
| `build-manifest/*.txt` | File listings: levels, cutscenes, video, sounds, UI materials |
| `ghost_cdx.txt` | Internet Archive URL inventory for `blizzard.com/ghost/*` |

---

## 1. Official Blizzard "StarCraft: Ghost" website (the stated vision)

The game's own promotional site is fully archived. Highest-value pages:

- **Press release (2002-09-20, Tokyo Game Show)** — announcement: "tactical-action
  console game", Nova, enhanced physical and psionic abilities, Calldown
  attacks, 3rd-person camera; co-developed with Nihilistic, co-published by
  Capcom in Japan, slated **late 2003**.
  <https://web.archive.org/web/20021004122855/http://www.blizzard.com/ghost/pressrelease.shtml>
- **F.A.Q. (2004)** — feature list: sonic-speed outmaneuver, cloak, lockdown,
  Battlecruiser/Siege Tank strikes, pilotable StarCraft vehicles, Gauss Rifle
  and combat pistol, Mar Sara/Aiur, Terran/Zerg/Protoss units.
  <https://web.archive.org/web/20040701072122/http://blizzard.com/ghost/faq.shtml>
- **F.A.Q. (2005)** — expands the promise: **12–15 h single-player**, **16-player
  multiplayer over Xbox Live and Battle.net**, playable **Zerg multiplayer
  units**, the **"Invasion"** mode, a new **Abaddon** level; platforms narrowed
  to **Xbox and PlayStation 2** (GameCube dropped).
  <https://web.archive.org/web/2005/http://www.blizzard.com/ghost/faq.shtml>
- **Covert Ops** subsection — the "encyclopedia" of the vision:
  - Psi powers: `cloak`, `speed`, `sight`/vision
  - Weapons: `assault`, `gauss`, `shotgun`, `flamethrower`, `lockdown`, `sniper`
  - Vehicles: `grizzly`, `siegetank`, `stinger`, `vulture`
  - Characters: `marine`, `firebat`, `ghost`, `light-infantry`
  - Multiplayer: Deathmatch, Team Deathmatch, CTF, King of the Hill, and the
    StarCraft-flavoured **Capture the Base** (a.k.a. "Mobile Conflict") and
    **Invasion**
  - Story / Nova backstory
- **Insider / Movies** — "making of" material and the 2005 gameplay,
  multiplayer and cinematic trailers (movie downloaders archived).
- **TGS 2003 press release**, **E3 2003 page**, **controller setup**,
  **screenshots**, **press index**.

All mirrored under `text/official-*.txt` (see table below).

## 2. The 2020 leak — coverage and primary teardown

- **Hidden Palace** — dump record: *StarCraft: Ghost (May 8, 2004 prototype)*,
  dumped/released by **Finn Hillbilly**, file release date 2019-12-29, Xbox
  Dev Kit. <https://hiddenpalace.org/StarCraft:_Ghost_(May_8,_2004_prototype)>
- **BetaArchive thread `t=40850`** — the deepest community teardown: command-line
  switches (`/devmode /console /window /tgs /level /nosound`), the NOD engine
  lineage to *Vampire: The Masquerade – Redemption* (`masquerade.ini`), Xbox
  build dates, the `Nova` profile unlock, `ghostsp.nsc` mission re-enabling, the
  Win32 `Star*.exe` TGS demo lineage. <https://www.betaarchive.com/forum/viewtopic.php?t=40850>
- **NeoGAF thread "Nihilistic Software's Starcraft Ghost 2003 build has been
  leaked"** (stranno) — features list, resolution/128 MB notes, weapons/powers
  from the build. <https://www.neogaf.com/threads/nihilistic-softwares-starcraft-ghost-2003-build-has-been-leaked.1526286/>
- **Lost Media Wiki** — leak timeline and download-link history.
- **Archive.org item** `starcraftghostxbox_202002` (uploaded 2020-02-16).
- Coverage: Kotaku, The Verge, IGN, Polygon, Engadget, VG247, DualShockers,
  GameRevolution, GamingBolt, Wccftech, Digital Trends.

## 3. Development history, interviews, postmortems

- **Polygon, "StarCraft: Ghost: What went wrong" (2016)** — nine developers;
  the definitive postmortem (identity crisis, Strike Teams, producer churn,
  E3 2004 meeting, Nihilistic exit). <https://www.polygon.com/2016/7/5/11819438/starcraft-ghost-what-went-wrong/>
- **MCV/DEVELOP (2016)**, **RPS (2016)**, **Screen Rant (2020)** — summaries.
- **Gamasutra/GameDeveloper "Blizzard 'Refocuses' Console Dev, Postpones
  Starcraft Ghost" (2006)** — the indefinite-hold statement.
- **Eurogamer** — GameCube cancellation (2005); Nihilistic exit (2004); "World
  of Warcraft killed StarCraft Ghost" (2011).
- **Kotaku/VG247 (2011)** — Morhaime at D.I.C.E. on WoW resource decisions.
- **GameSpot** — 2002 announcement/preview, 2004 Nihilistic-exit article.
- **IGN** — 2003 gameplay details (moves, weapons), 2004 Nihilistic exit.
- **Blizzplanet** — abilities, FAQ, Julian Kwasneski interview (audio/tech),
  Robert Huebner (Nihilistic) interview via Xbox Evolved.
- **The Next-Gen/Edge archived piece** — Rob Pardo "we still believe in that
  game" (2007).

## 4. Concept art, soundtrack, reference

- Concept art: Engadget (2009), Siliconera (2011), Game Informer archive,
  IAMAG collection, N4G, Eric Browning's ArtStation album.
- Soundtrack: Kevin Manthei's Nihilistic-era OST (self-released CD-R, 2022);
  VGMDB entry + Reddit discovery thread.
- Lore/reference: Wikipedia, StarCraft Fandom, the Reddit "story pieced
  together" writeup, the BlizzCon 2005 brochure scan thread.
- Composer/crew interviews and the BlizzCon 2005 multiplayer reveal.

## 5. Build-derived evidence (from the user's own archive)

`extracted/StarCraft Ghost Xbox Finn Hillbilly/` — May 8, 2004 Nihilistic
build (see [`02-inventory.md`](02-inventory.md)). Extracted to `res/.../build-text`:

- `ghostsp.nsc` / `ghostsp2.nsc` — the single-player **chronicle**: full mission
  graph, per-mission powers/calldowns/ammo/inventory, with most entries
  commented out.
- 171 `.nlt` text tables — tutorials, unit bios, weapon/vehicle/power
  descriptions, calldown lore (e.g. `060_Cloak.nlt`, `046_CalldownNuke.nlt`).
- `game.nls` / `.nlu` / `.nlx` / `.nfx` string dumps — mission names, objective
  strings, briefing/dialogue, including debug placeholders.
- Asset manifests: 423 cutscene scripts, 91 Bink videos, 160 sound banks,
  26 level files.

---

## Full artifact manifest

*(live URL + Wayback snapshot where a site blocked direct access; `chars` is the
extracted visible-text size)*

<!-- BEGIN GENERATED MANIFEST -->

| artifact | kind | live URL | chars |
|---|---|---|---|
| `text/official-characters-firebat.txt` | official | http://www.blizzard.com/ghost/covertops/characters/firebat.shtml [snapshot](https://web.archive.org/web/20050525034259id_/http://www.blizzard.com/ghost/covertops/characters/firebat.shtml) | 71 |
| `text/official-characters-ghost.txt` | official | http://www.blizzard.com/ghost/covertops/characters/Ghost.shtml [snapshot](https://web.archive.org/web/20050525034221id_/http://www.blizzard.com/ghost/covertops/characters/Ghost.shtml) | 121 |
| `text/official-characters-index.txt` | official | http://www.blizzard.com/ghost/covertops/characters/index.shtml [snapshot](https://web.archive.org/web/20050525012709id_/http://www.blizzard.com/ghost/covertops/characters/index.shtml) | 262 |
| `text/official-characters-light-infantry.txt` | official | http://www.blizzard.com/ghost/covertops/characters/light-infantry.shtml [snapshot](https://web.archive.org/web/20050525034321id_/http://www.blizzard.com/ghost/covertops/characters/light-infantry.shtml) | 151 |
| `text/official-characters-marine.txt` | official | http://www.blizzard.com/ghost/covertops/characters/Marine.shtml [snapshot](https://web.archive.org/web/20050525034243id_/http://www.blizzard.com/ghost/covertops/characters/Marine.shtml) | 72 |
| `text/official-controllersetup.txt` | official | http://www.blizzard.com/ghost/controllersetup.shtml [snapshot](https://web.archive.org/web/20030928010330id_/http://www.blizzard.com/ghost/controllersetup.shtml) | 219 |
| `text/official-covertops.txt` | official | http://www.blizzard.com/ghost/covertops/ [snapshot](https://web.archive.org/web/20050521025517id_/http://www.blizzard.com/ghost/covertops/) | 2453 |
| `text/official-e3-2003.txt` | official | http://www.blizzard.com/ghost/e3/2003/index.shtml [snapshot](https://web.archive.org/web/20030605144621id_/http://www.blizzard.com/ghost/e3/2003/index.shtml) | 338 |
| `text/official-e3-2003-pressrelease.txt` | official | http://www.blizzard.com/ghost/e3/2003/pressrelease.shtml [snapshot](https://web.archive.org/web/20030526074110id_/http://www.blizzard.com/ghost/e3/2003/pressrelease.shtml) | 508 |
| `text/official-faq-2002.txt` | official | http://www.blizzard.com/ghost/faq.shtml [snapshot](https://web.archive.org/web/20020925110405id_/http://www.blizzard.com/ghost/faq.shtml) | 2428 |
| `text/official-faq-2004.txt` | official | http://www.blizzard.com/ghost/faq.shtml [snapshot](https://web.archive.org/web/20040701072122id_/http://www.blizzard.com/ghost/faq.shtml) | 2176 |
| `text/official-faq-2005.txt` | official | http://www.blizzard.com/ghost/faq.shtml [snapshot](https://web.archive.org/web/2005id_/http://www.blizzard.com/ghost/faq.shtml) | 2189 |
| `text/official-home.txt` | official | http://www.blizzard.com/ghost/ [snapshot](https://web.archive.org/web/2005id_/http://www.blizzard.com/ghost/) | 383 |
| `text/official-insider-calldowns.txt` | official | http://www.blizzard.com/ghost/insider/calldowns.shtml [snapshot](https://web.archive.org/web/20031001235217id_/http://www.blizzard.com/ghost/insider/calldowns.shtml) | 851 |
| `text/official-insider-cinematics.txt` | official | http://www.blizzard.com/ghost/insider/cinematics.shtml [snapshot](https://web.archive.org/web/20030312014848id_/http://www.blizzard.com/ghost/insider/cinematics.shtml) | 3903 |
| `text/official-insider-interview.txt` | official | http://www.blizzard.com/ghost/insider/interview.shtml [snapshot](https://web.archive.org/web/20021221095730id_/http://www.blizzard.com/ghost/insider/interview.shtml) | 797 |
| `text/official-movies.txt` | official | http://www.blizzard.com/ghost/movies/index.shtml [snapshot](https://web.archive.org/web/20050525195947id_/http://www.blizzard.com/ghost/movies/index.shtml) | 471 |
| `text/official-nova-story.txt` | official | http://www.blizzard.com/ghost/covertops/story/nova-story.shtml [snapshot](https://web.archive.org/web/20051225022418id_/http://www.blizzard.com/ghost/covertops/story/nova-story.shtml) | 2215 |
| `text/official-press-index.txt` | official | http://www.blizzard.com/ghost/press.shtml [snapshot](https://web.archive.org/web/20030418035143id_/http://www.blizzard.com/ghost/press.shtml) | 536 |
| `text/official-pressrelease-2002.txt` | official | http://www.blizzard.com/ghost/pressrelease.shtml [snapshot](https://web.archive.org/web/20021004122855id_/http://www.blizzard.com/ghost/pressrelease.shtml) | 2023 |
| `text/official-pressrelease-tgs2003.txt` | official | http://www.blizzard.com/ghost/pressrelease-tgs2003.shtml [snapshot](https://web.archive.org/web/20030929010102id_/http://www.blizzard.com/ghost/pressrelease-tgs2003.shtml) | 1011 |
| `text/official-psi-cloak.txt` | official | http://www.blizzard.com/ghost/covertops/psi/cloak.shtml?vehicleName=cloak [snapshot](https://web.archive.org/web/20060210053636id_/http://www.blizzard.com/ghost/covertops/psi/cloak.shtml?vehicleName=cloak) | 847 |
| `text/official-psi-index.txt` | official | http://www.blizzard.com/ghost/covertops/psi/ [snapshot](https://web.archive.org/web/20050520234445id_/http://www.blizzard.com/ghost/covertops/psi/) | 277 |
| `text/official-psi-speed.txt` | official | http://www.blizzard.com/ghost/covertops/psi/speed.shtml?vehicleName=speed [snapshot](https://web.archive.org/web/20060210053646id_/http://www.blizzard.com/ghost/covertops/psi/speed.shtml?vehicleName=speed) | 515 |
| `text/official-psi-vision.txt` | official | http://www.blizzard.com/ghost/covertops/psi/vision.shtml?vehicleName=vision [snapshot](https://web.archive.org/web/20051128023308id_/http://www.blizzard.com/ghost/covertops/psi/vision.shtml?vehicleName=vision) | 714 |
| `text/official-screenshots.txt` | official | http://www.blizzard.com/ghost/screenshots.shtml [snapshot](https://web.archive.org/web/2005id_/http://www.blizzard.com/ghost/screenshots.shtml) | 205 |
| `text/official-story.txt` | official | http://www.blizzard.com/ghost/covertops/story/ [snapshot](https://web.archive.org/web/20050520235343id_/http://www.blizzard.com/ghost/covertops/story/) | 2129 |
| `text/official-vehicles-grizzly.txt` | official | http://www.blizzard.com/ghost/covertops/vehicles/grizzly.shtml?vehicleName=grizzly [snapshot](https://web.archive.org/web/20050524164530id_/http://www.blizzard.com/ghost/covertops/vehicles/grizzly.shtml?vehicleName=grizzly) | 800 |
| `text/official-vehicles-index.txt` | official | http://www.blizzard.com/ghost/covertops/vehicles/ [snapshot](https://web.archive.org/web/20050521000746id_/http://www.blizzard.com/ghost/covertops/vehicles/) | 262 |
| `text/official-vehicles-siegetank.txt` | official | http://www.blizzard.com/ghost/covertops/vehicles/siegetank.shtml?vehicleName=siegetank [snapshot](https://web.archive.org/web/20050524164542id_/http://www.blizzard.com/ghost/covertops/vehicles/siegetank.shtml?vehicleName=siegetank) | 490 |
| `text/official-vehicles-stinger.txt` | official | http://www.blizzard.com/ghost/covertops/vehicles/stinger.shtml?vehicleName=stinger [snapshot](https://web.archive.org/web/20050524164551id_/http://www.blizzard.com/ghost/covertops/vehicles/stinger.shtml?vehicleName=stinger) | 532 |
| `text/official-vehicles-vulture.txt` | official | http://www.blizzard.com/ghost/covertops/vehicles/vulture.shtml?vehicleName=vulture [snapshot](https://web.archive.org/web/20050524164609id_/http://www.blizzard.com/ghost/covertops/vehicles/vulture.shtml?vehicleName=vulture) | 518 |
| `text/official-weapons-assault.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/assault.shtml?vehicleName=assault [snapshot](https://web.archive.org/web/20051128034911id_/http://www.blizzard.com/ghost/covertops/weapons/assault.shtml?vehicleName=assault) | 374 |
| `text/official-weapons-flamethrower.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/flamethrower.shtml?vehicleName=flamethrower [snapshot](https://web.archive.org/web/20050527222136id_/http://www.blizzard.com/ghost/covertops/weapons/flamethrower.shtml?vehicleName=flamethrower) | 458 |
| `text/official-weapons-gauss.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/gauss.shtml?vehicleName=gauss [snapshot](https://web.archive.org/web/20060317165206id_/http://www.blizzard.com/ghost/covertops/weapons/gauss.shtml?vehicleName=gauss) | 208 |
| `text/official-weapons-index.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/ [snapshot](https://web.archive.org/web/20050521001940id_/http://www.blizzard.com/ghost/covertops/weapons/) | 262 |
| `text/official-weapons-lockdown.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/lockdown.shtml?vehicleName=lockdown [snapshot](https://web.archive.org/web/20051129033158id_/http://www.blizzard.com/ghost/covertops/weapons/lockdown.shtml?vehicleName=lockdown) | 375 |
| `text/official-weapons-shotgun.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/shotgun.shtml?vehicleName=shotgun [snapshot](https://web.archive.org/web/20060317165214id_/http://www.blizzard.com/ghost/covertops/weapons/shotgun.shtml?vehicleName=shotgun) | 354 |
| `text/official-weapons-sniper.txt` | official | http://www.blizzard.com/ghost/covertops/weapons/sniper.shtml?vehicleName=sniper [snapshot](https://web.archive.org/web/20060317165236id_/http://www.blizzard.com/ghost/covertops/weapons/sniper.shtml?vehicleName=sniper) | 288 |
| `text/archive-org-item.txt` | leak | https://archive.org/details/starcraftghostxbox_202002  | 4535 |
| `text/betaarchive-40850.txt` | leak | https://www.betaarchive.com/forum/viewtopic.php?t=40850 [snapshot](https://web.archive.org/web/2020id_/https://www.betaarchive.com/forum/viewtopic.php?t=40850) | 10619 |
| `text/digitaltrends-2020-leak.txt` | leak | https://www.digitaltrends.com/gaming/starcraft-ghost-playable-build-leaks/  | 11756 |
| `text/dualshockers-2020-leak.txt` | leak | https://www.dualshockers.com/starcraft-ghost-leaked-gameplay-footage-screenshots-cancelled/  | 3194 |
| `text/engadget-2020-leak.txt` | leak | https://www.engadget.com/2020-02-16-starcraft-ghost-playable-leak.html  | 2188 |
| `text/gamerevolution-2020-leak.txt` | leak | https://www.gamerevolution.com/news/633684-leaked-starcraft-ghost-build  | 3705 |
| `text/gamingbolt-2020-leak.txt` | leak | https://gamingbolt.com/starcraft-ghost-footage-shows-leaked-playable-build  | 148412 |
| `text/hiddenpalace-may2004.txt` | leak | https://hiddenpalace.org/StarCraft:_Ghost_(May_8,_2004_prototype)  | 1991 |
| `text/ign-2020-leak.txt` | leak | https://www.ign.com/articles/starcraft-ghost-gameplay-leak-xbox-blizzard-footage-playable-build  | 6156 |
| `text/kotaku-2020-leak.txt` | leak | https://kotaku.com/it-seems-an-playable-xbox-build-of-starcraft-ghost-has-1841731450 [snapshot](https://web.archive.org/web/2020id_/https://kotaku.com/it-seems-an-playable-xbox-build-of-starcraft-ghost-has-1841731450) | 2032 |
| `text/lostmediawiki.txt` | leak | https://lostmediawiki.com/StarCraft:_Ghost_(partially_found_build_of_cancelled_sci-fi_stealth-action_game;_2006) [snapshot](https://web.archive.org/web/2020id_/https://lostmediawiki.com/StarCraft:_Ghost_(partially_found_build_of_cancelled_sci-fi_stealth-action_game;_2006)) | 2208 |
| `text/neogaf-1526286.txt` | leak | https://www.neogaf.com/threads/nihilistic-softwares-starcraft-ghost-2003-build-has-been-leaked.1526286/ [snapshot](https://web.archive.org/web/2020id_/https://www.neogaf.com/threads/nihilistic-softwares-starcraft-ghost-2003-build-has-been-leaked.1526286/) | 10509 |
| `text/polygon-2020-leak.txt` | leak | https://www.polygon.com/2020/2/16/21140101/starcraft-ghost-leak-build-video-devkit-xbox/  | 6270 |
| `text/verge-2020-leak.txt` | leak | https://www.theverge.com/2020/2/17/21141203/starcraft-ghost-playable-build-leaked-xbox-blizzard  | 19242 |
| `text/vg247-2020-leak.txt` | leak | https://www.vg247.com/starcraft-ghost-leaked-build-new-gameplay  | 5510 |
| `text/wccftech-2020-leak.txt` | leak | https://wccftech.com/starcraft-ghost-the-cancelled-third-person-action-game-has-leaked-online/  | 192218 |
| `text/blizzplanet-abilities.txt` | history | https://www.blizzplanet.com/blog/comments/starcraft_ghost___abilities  | 4637 |
| `text/blizzplanet-faq.txt` | history | https://www.blizzplanet.com/blog/comments/starcraft_ghost_faq  | 6042 |
| `text/blizzplanet-huebner-xboxevolved.txt` | history | https://www.blizzplanet.com/blog/comments/nihilistic_starcraft_ghost_woes_xbox_evolved  | 2354 |
| `text/blizzplanet-kwasneski-interview.txt` | history | https://www.blizzplanet.com/blog/comments/starcraft-ghost-interview-julian-kwasneski  | 16554 |
| `text/eurogamer-cube-cancel.txt` | history | https://www.eurogamer.net/news031105blizzardghostcube  | 8504 |
| `text/eurogamer-nihilistic.txt` | history | https://www.eurogamer.net/news230604nihilistic  | 5031 |
| `text/eurogamer-wow-killed.txt` | history | https://www.eurogamer.net/world-of-warcraft-killed-starcraft-ghost  | 8084 |
| `text/gamedeveloper-postpone.txt` | history | https://www.gamedeveloper.com/game-platforms/blizzard-refocuses-console-dev-postpones-i-starcraft-ghost-i-  | 8738 |
| `text/gamesindustry-indefinitely-postponed.txt` | history | https://www.gamesindustry.biz/starcraft-ghost-is-indefinitely-postponed  | 5639 |
| `text/gamesindustry-nihilistic-out.txt` | history | https://www.gamesindustry.biz/nihilistic-no-longer-working-on-starcraft-ghost  | 5655 |
| `text/gamesindustry-qa-2005.txt` | history | https://www.gamesindustry.biz/starcraft-ghost-questions-answers  | 5949 |
| `text/gamespot-nihilistic-exit-2004.txt` | history | https://www.gamespot.com/articles/starcraft-ghost-delayed-nihilistic-no-longer-on-the-project/1100-6101105/ [snapshot](https://web.archive.org/web/2004id_/https://www.gamespot.com/articles/starcraft-ghost-delayed-nihilistic-no-longer-on-the-project/1100-6101105/) | 4032 |
| `text/gamespot-preview-2002.txt` | history | https://www.gamespot.com/articles/starcraft-ghost-preview/1100-2882341/ [snapshot](https://web.archive.org/web/2003id_/https://www.gamespot.com/articles/starcraft-ghost-preview/1100-2882341/) | 10070 |
| `text/gamespot-uncloaked-2002.txt` | history | https://www.gamespot.com/articles/starcraft-ghost-uncloaked/1100-2880889/  | 18624 |
| `text/ign-2003-details.txt` | history | https://www.ign.com/articles/2003/03/30/starcraft-ghost-details-2  | 13910 |
| `text/ign-nihilistic-exits-2004.txt` | history | https://www.ign.com/articles/2004/06/22/nihilistic-exits-starcraft-ghost  | 4243 |
| `text/kotaku-morhaime-2011.txt` | history | https://kotaku.com/the-head-of-blizzard-explains-the-death-of-starcraft-gh-30833489 [snapshot](https://web.archive.org/web/2011id_/https://kotaku.com/the-head-of-blizzard-explains-the-death-of-starcraft-gh-30833489) | 2904 |
| `text/mcv-2016-identity-crisis.txt` | history | https://mcvuk.com/development-news/nihilistic-swingin-ape-and-blizzard-recall-identity-crisis-that-doomed-starcraft-ghost/  | 3581 |
| `text/n-europe-e3-2004.txt` | history | https://n-europe.com/news/e3-2004-starcraft-press-release/ [snapshot](https://web.archive.org/web/2004id_/https://n-europe.com/news/e3-2004-starcraft-press-release/) | 461 |
| `text/polygon-2016-what-went-wrong.txt` | history | https://www.polygon.com/2016/7/5/11819438/starcraft-ghost-what-went-wrong/  | 11707 |
| `text/rpgclassics-scghost.txt` | history | http://archive.rpgclassics.com/subsites/starcraft/scghost.shtml  | 2911 |
| `text/rps-cancelled.txt` | history | https://www.rockpapershotgun.com/why-was-starcraft-ghost-cancelled  | 3977 |
| `text/screenrant-cancelled.txt` | history | https://screenrant.com/why-starcraft-ghost-cancelled-blizzard-shooter-game/  | 3493 |
| `text/vg247-demo-reel.txt` | history | https://www.vg247.com/nihilistic-software-demo-reel-shows-a-glimpse-of-starcraft-ghost  | 8253 |
| `text/vg247-morhaime.txt` | history | https://www.vg247.com/morhaime-starcraft-ghost-canned-due-to-wow-insta-success  | 8241 |
| `text/vooks-delayed-2004.txt` | history | https://www.vooks.net/starcraft-ghost-delayed/  | 151798 |
| `text/artstation-ericbrowning.txt` | reference | https://www.artstation.com/eric2378/albums/13774800  | 2194 |
| `text/engadget-concept-art-2009.txt` | reference | https://www.engadget.com/2009-03-17-starcraft-ghost-concept-art-surfaces-game-hasnt.html  | 2280 |
| `text/fandom-nihilistic.txt` | reference | https://starcraft.fandom.com/wiki/Nihilistic_Software  | 23600 |
| `text/fandom-scghost.txt` | reference | https://starcraft.fandom.com/wiki/StarCraft:_Ghost [snapshot](https://web.archive.org/web/2020id_/https://starcraft.fandom.com/wiki/StarCraft:_Ghost) | 31644 |
| `text/gameinformer-archives.txt` | reference | https://gameinformer.com/b/features/archive/2013/12/19/from-the-game-informer-archives-starcraft-ghost.aspx  | 6657 |
| `text/iamag-concept-art.txt` | reference | https://www.iamag.co/concept-art-collection-for-blizzard-cancelled-game-starcraft-ghost/  | 16417 |
| `text/n4g-concepts.txt` | reference | https://n4g.com/news/975073/long-lost-starcraft-ghost-concepts  | 4096 |
| `text/reddit-blizzcon-brochure.txt` | reference | https://old.reddit.com/r/starcraft/comments/5odz3w/brochure_from_blizzards_cancelled_starcraft_ghost/ [snapshot](https://web.archive.org/web/2017id_/https://old.reddit.com/r/starcraft/comments/5odz3w/brochure_from_blizzards_cancelled_starcraft_ghost/) | 13727 |
| `text/reddit-soundtrack.txt` | reference | https://old.reddit.com/r/starcraft/comments/107v4af/uncovered_the_starcraft_ghost_soundtrack_by_kevin/ [snapshot](https://web.archive.org/web/2023id_/https://old.reddit.com/r/starcraft/comments/107v4af/uncovered_the_starcraft_ghost_soundtrack_by_kevin/) | 16392 |
| `text/reddit-story-pieced.txt` | reference | https://old.reddit.com/r/starcraft/comments/f5vr5y/the_story_of_starcraft_ghost_what_can_be_pieced/ [snapshot](https://web.archive.org/web/2020id_/https://old.reddit.com/r/starcraft/comments/f5vr5y/the_story_of_starcraft_ghost_what_can_be_pieced/) | 16625 |
| `text/siliconera-concept-art.txt` | reference | https://www.siliconera.com/starcraft-ghost-concept-art-reveals-stealth-specter-and-protoss-shadow-husk/  | 2903 |
| `text/vgmdb-ost.txt` | reference | https://vgmdb.net/album/125594 [snapshot](https://web.archive.org/web/2023id_/https://vgmdb.net/album/125594) | 2546 |
| `text/wikipedia-nihilistic.txt` | reference | https://en.wikipedia.org/wiki/Nihilistic_Software  | 4897 |
| `text/wikipedia-scghost.txt` | reference | https://en.wikipedia.org/wiki/StarCraft:_Ghost  | 10708 |

<!-- END GENERATED MANIFEST -->
