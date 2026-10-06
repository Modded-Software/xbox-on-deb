# 06 — Gap analysis: stated vision vs. the leaked build

Compares what **Blizzard and Nihilistic said StarCraft: Ghost would be**
(2002–2006) against what is actually in the **May 8, 2004 Xbox build**
(dumped by "Finn Hillbilly", released 2019-12-29) and the older **Win32 TGS
demo** shipped alongside it.

Sources: [`05-research-archive.md`](05-research-archive.md),
[`02-inventory.md`](02-inventory.md), and the build's own text tables under
`res/starcraft-ghost-archive/build-text/` (gitignored).

> One-line summary: the leak is a **Nihilistic-era vertical slice at the moment
> Blizzard decided to pull the studio** — the core stealth-combat loop, psi
> cloak and several calldowns are real, but most of the marketed feature set
> (full campaign, Protoss arc, multiplayer, vehicle play, most psi powers) is
> absent from playable content and survives only as assets, string tables and
> commented-out mission definitions.

---

## Scope of the two sides

| | Stated vision | Leaked build |
|---|---|---|
| Source | 2002 press release; 2004 & 2005 official FAQ; Covert Ops site; E3/BlizzCon press | `Ghost.xbe` (release), `GhostR.xbe`, `GhostU.xbe`; `Star*.exe` Win32 TGS demo |
| Date | 2002 announcement → 2006 hold | Xbox headers **2004-05-08**; Win32 PEs **2002** |
| Developer | Blizzard + Nihilistic, then Swingin' Ape | Nihilistic (pre-handoff) |
| Platforms | PS2, Xbox, GameCube (→ PS2/Xbox) | Xbox (+ Win32 demo) |

---

## Feature-by-feature gaps

Legend: **Present** = playable in an enabled mission; **Unwired** = assets/text
exist but no enabled mission uses it; **Absent** = not found.

| Feature (as marketed) | Build status | Evidence |
|---|---|---|
| Play as Nova | Present | Nova in roster/menu strings (`game.nls.strings.txt` `140_Nova.nlt`) |
| Cloak / invisibility | Present | `ghostsp.nsc` `POWERS cloak` on every active mission; `060_Cloak.nlt` |
| Vision / thermal ("Sight") | Present | `2_2_OUTERHULL` `POWERS cloak sight`; `061_Sight.nlt` |
| Psi **Speed** (sonic speed) | Unwired | `062_Speed.nlt` + `POWERS speed` only on commented missions (`ghostsp.nsc:449`) |
| Psi **Shield** / **Storm** | Absent | named only in the `.nsc` header grammar (`ghostsp.nsc:20`) |
| Lockdown (immobilise vehicles/cameras) | Partially wired | objectives "Lockdown Camera" (`2_2_OBJ01/10`); active calldowns list omits `lockdown` |
| Calldowns: Identify, Comsat, Irradiate, Arclite, Yamato | Present | `ghostsp.nsc` active `CALLDOWNS identify comsat irradiate arclite yamato`; sound events `expCall*.xsb` |
| Calldowns: **Nuke**, **EMP**, Lockdown | Unwired | enabled only in commented missions (`1_3_INFESTATION`, `3_1_SIEGE_*`); assets `nuke_*.bik`, `emp_*.bik` present |
| Gauss Rifle / combat pistol | Present (pistol+rifle) | 040/030 tutorials; weapons `WeaponGauss.xsb`, `weaponPistol.xsb` |
| Perdition Flamethrower / Torrent Shotgun | Unwired | `weapFlmthrwr.xsb`, flamethrower cutscene `422a_GetFlamethrower`; not on active mission weapon set |
| Sniper (C-20A) | Present | 005/032 tutorials; used to trigger calldowns (`046_CalldownNuke.nlt`) |
| Canister grenades (frag/EMP/irradiate/…) | Partially | `050–059_*.nlt`; inventory `canister` on active missions; several marked `CUT` in `ghostsp.nsc:31-42` |
| Pilot vehicles (Vulture, Siege Tank, Grizzly, Stinger, Goliath) | Unwired (Vulture present) | `027_VultureVehicle`, `028_GoliathVehicle`, `029_SiegeTankVehicle`; Vulture used in `1_3_REFINERYB`; Grizzly/Stinger only in multiplayer lore/assets |
| Acrobatics: climb, wires, tightropes, mantle | Present | `001_Moving`, `002_Jumping`, `003_Climbing`, `013_Wires`; `official-faq-2004` promised them |
| Terran / Zerg / Protoss rendered units | Terran+Zerg present; **Protoss unwired** | full unit bios `100–247_*.nlt`, `protoss.xwb`, `ptss*.xsb`; Protoss missions all commented (`3_x`, `5_1_ARIES`, `4_4_c_darkArchon`) |
| Story-driven campaign + twists | Partial | 423 cutscene scripts, 91 Bink videos, attract mode; playable story stops after Fujita/Hangar |
| **12–15 h** single-player | Not met | 6 playable mission segments (~a few hours), from a planned ~45-segment / 7-act slate |
| **16-player multiplayer**, classes, CTF/CTB/Invasion | **Absent** | no MP in build; `GhostU` shows an "Online Services" menu string but no functioning netsys; Swingin' Ape built MP *after* this build |
| GameCube release | Cancelled (2005) | not build-related; see `eurogamer-cube-cancel` |
| PC/Mac release | Never planned | official FAQ: console only |

---

## Campaign gap (planned vs. shipped)

The build's own string table preserves the **entire intended mission list**, most
of it unbuilt or disabled. Missions actually enabled in `ghostsp.nsc`:

1. **Scattered Forces** (`1_2_ZERG`, Miners Bunker)
2. **Zergling Rush** (`1_2_ZERGA`)
3. **Canyon Advance** (`1_2_ZERGB`)
4. **The Fujita Pinnacle** (`2_2_OUTERHULL`, Threat Base Upper)
5. **Pinnacle Hangar** (`2_2_OUTERHULLA`)
6. **Sabotage** (`1_3_REFINERYB`, Hive Station Outer) — the first level; does not
   load on a 64 MB retail Xbox
7. *The Borgo Refinery* (`1_3_REFINERY`) — present but commented out
   (`ghostsp.nsc:95`), re-enablable

Against the ~45 IDs in `game.nls.strings.txt:651-698`, the unbuilt/commented
slate includes the whole Protoss arc (**In the Path of Titans**, **Sacred
Ground**, **Khaydarin Core**, **Arbiter Tribunal**, **Artemis Boss**), the Zerg
arc (**The Shadow Hunters**, **The Way of the Warrior**, **Terrazine Mining
A/B/C**, **The Path of Shadow**), endgame bosses (**Aries Boss**, **Hauler
Boss**, **Vulcan Boss**), and a StarCraft-1 homage act (**Desperate Alliance**,
**Revolution**, **Backwater Station**, **The Trump Card**, **The Jacobs
Installation**, **The Invasion of Aiur**, **The New Gettysberg**).

### Debug / placeholder evidence of unfinished content

`game.nls.strings.txt` contains unabashed placeholders, proving the slate was
still being shaped:

- `4_2_OBJ05..10`: "Find the MacGuffin part #1", "Find the Flux Capacitor",
  "Find the Heisenberg Compensator", "Find the Minovsky Particles", "Find the
  Maltese Falcon".
- `2_2_OBJ50/55/60`: "[TEMP] Disable Heisenberg Compensators / Flux
  Capacitor / Deactivate laser wall".
- `1_2_1_BRIEFINGTEXT`: "And here comes a Zergling Rush!!! (Yeah, I know you
  can't see it. But it's coming. Someday.)".
- Infested-marine dialogue written as a joke: "...kill me, I'm infested blah
  blah blah...".

---

## "Content-rich, wiring-poor": assets present, gameplay absent

A recurring pattern is that **audio/video/text for cut features ship in the
build** even though no enabled mission exposes them:

- Calldown movie assets: `nuke_*`, `emp_*`, `irradiate_*`, `yamato_*`,
  `arclite_*`, `comsat_*`, `identify_fire` (`build-manifest/video.txt`).
- Sound events for every calldown/canister: `expCallNuke.xsb`, `expCallEMP.xsb`,
  `expCanSmoke.xsb`, `projCanLockdown.xsb`, … (`build-manifest/sounds.txt`).
- Complete Protoss and Zerg rosters: `ptss*.xsb`, `zerg*.xsb`, unit bios to
  `247_VoidSeeker.nlt`.
- Tutorial tables for features with no enabled mission: `007_TargetLock`,
  `010_SilentDisable`, `011_Minimap`, `033_PsiBlade`, `031_ShockGlove`,
  `059_LockdownCanister`.
- An `Attract_Mode.vid`, Blizzard/Nihilistic logos, `TGS_*` cutscenes and a
  `TGS_*` sound set — the **Tokyo Game Show demo lineage** (also present as the
  Win32 `Star*.exe` 2002 builds).

So the build is closer to a **broad but shallow vertical slice** than a
content-complete campaign: the systems and assets span the whole vision, but the
mission graph exposes only a fraction.

---

## Timeline gap

| Date | Event | Build relevance |
|---|---|---|
| 2002-09-20 | Announced at TGS; late-2003 target | Win32 `Star*.exe` (2002) = the TGS demo |
| 2003 | Slipped; E3/TGS media; multiplayer added to design | — |
| 2004-05-08 | — | **This build.** |
| 2004-06 | Nihilistic exits; game handed to Swingin' Ape | build predates MP work |
| 2005 | BlizzCon 2005 MP reveal; GameCube cancelled | MP absent here |
| 2006-03 | Indefinite hold | — |
| 2014 | Officially cancelled | — |

The build sits exactly at the **handoff seam**: after Nihilistic's stealth-heavy
single-player foundation, before Swingin' Ape's multiplayer-and-reboot era.

---

## Reading the gap

- The **single-player stealth-action core is the real survivor**: Nova, cloak,
  sight, sniper, calldowns, acrobatic traversal and a Zerg/Terran level set all
  function — matching Huebner's "a really good stealth level, a Zerg level …"
  recollection (Polygon 2016).
- The **advertised breadth was largely aspirational at this date**: multiplayer,
  16 players, Invasion/Capture-the-Base, playable Zerg classes, the Protoss arc,
  most psi powers, broad vehicle play, and the 12–15 h campaign.
- Much of that breadth exists as **data, not gameplay** — a useful distinction
  for anyone modding or re-enabling content (e.g. un-commenting missions in
  `ghostsp.nsc`) and for judging what Swingin' Ape inherited.
- The later Swingin' Ape build (BlizzCon 2005) is **not** in this leak; the
  multiplayer and next-gen-era features described from 2005 onward cannot be
  assessed from this artifact.

See [`07-decomp-workflow.md`](../recomp/docs/07-decomp-workflow.md) and the
`recomp/` tree for the ongoing static-analysis effort this archive supports.
