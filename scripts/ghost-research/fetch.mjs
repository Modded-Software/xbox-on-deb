#!/usr/bin/env node
// Fetch StarCraft: Ghost research sources into res/starcraft-ghost-archive/.
// Uses the workspace `browser` CLI (Playwright) so JS-heavy and Cloudflare
// pages render. Wayback snapshots use the raw `id_` form to avoid wombat.js.
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "..", "..", "res", "starcraft-ghost-archive", "text");
mkdirSync(OUT, { recursive: true });

const W = "https://web.archive.org/web/";
const wb = (ts, path) => `${W}${ts}id_/http://www.blizzard.com/ghost/${path}`;
const wbx = (ts, url) => `${W}${ts}id_/${url}`;

const SOURCES = [
  // --- Official Blizzard "StarCraft: Ghost" site (Wayback, raw snapshots) ---
  ["official-home", wb("2005", ""), "official"],
  ["official-faq-2002", wb("20020925110405", "faq.shtml"), "official"],
  ["official-faq-2004", wb("20040701072122", "faq.shtml"), "official"],
  ["official-faq-2005", wb("2005", "faq.shtml"), "official"],
  ["official-pressrelease-2002", wb("20021004122855", "pressrelease.shtml"), "official"],
  ["official-pressrelease-tgs2003", wb("20030929010102", "pressrelease-tgs2003.shtml"), "official"],
  ["official-e3-2003-pressrelease", wb("20030526074110", "e3/2003/pressrelease.shtml"), "official"],
  ["official-e3-2003", wb("20030605144621", "e3/2003/index.shtml"), "official"],
  ["official-press-index", wb("20030418035143", "press.shtml"), "official"],
  ["official-controllersetup", wb("20030928010330", "controllersetup.shtml"), "official"],
  ["official-screenshots", wb("2005", "screenshots.shtml"), "official"],
  ["official-covertops", wb("20050521025517", "covertops/"), "official"],
  ["official-psi-index", wb("20050520234445", "covertops/psi/"), "official"],
  ["official-psi-cloak", wb("20060210053636", "covertops/psi/cloak.shtml?vehicleName=cloak"), "official"],
  ["official-psi-speed", wb("20060210053646", "covertops/psi/speed.shtml?vehicleName=speed"), "official"],
  ["official-psi-vision", wb("20051128023308", "covertops/psi/vision.shtml?vehicleName=vision"), "official"],
  ["official-weapons-index", wb("20050521001940", "covertops/weapons/"), "official"],
  ["official-weapons-gauss", wb("20060317165206", "covertops/weapons/gauss.shtml?vehicleName=gauss"), "official"],
  ["official-weapons-assault", wb("20051128034911", "covertops/weapons/assault.shtml?vehicleName=assault"), "official"],
  ["official-weapons-shotgun", wb("20060317165214", "covertops/weapons/shotgun.shtml?vehicleName=shotgun"), "official"],
  ["official-weapons-flamethrower", wb("20050527222136", "covertops/weapons/flamethrower.shtml?vehicleName=flamethrower"), "official"],
  ["official-weapons-lockdown", wb("20051129033158", "covertops/weapons/lockdown.shtml?vehicleName=lockdown"), "official"],
  ["official-weapons-sniper", wb("20060317165236", "covertops/weapons/sniper.shtml?vehicleName=sniper"), "official"],
  ["official-vehicles-index", wb("20050521000746", "covertops/vehicles/"), "official"],
  ["official-vehicles-grizzly", wb("20050524164530", "covertops/vehicles/grizzly.shtml?vehicleName=grizzly"), "official"],
  ["official-vehicles-siegetank", wb("20050524164542", "covertops/vehicles/siegetank.shtml?vehicleName=siegetank"), "official"],
  ["official-vehicles-stinger", wb("20050524164551", "covertops/vehicles/stinger.shtml?vehicleName=stinger"), "official"],
  ["official-vehicles-vulture", wb("20050524164609", "covertops/vehicles/vulture.shtml?vehicleName=vulture"), "official"],
  ["official-characters-index", wb("20050525012709", "covertops/characters/index.shtml"), "official"],
  ["official-characters-marine", wb("20050525034243", "covertops/characters/Marine.shtml"), "official"],
  ["official-characters-firebat", wb("20050525034259", "covertops/characters/firebat.shtml"), "official"],
  ["official-characters-ghost", wb("20050525034221", "covertops/characters/Ghost.shtml"), "official"],
  ["official-characters-light-infantry", wb("20050525034321", "covertops/characters/light-infantry.shtml"), "official"],
  ["official-story", wb("20050520235343", "covertops/story/"), "official"],
  ["official-nova-story", wb("20051225022418", "covertops/story/nova-story.shtml"), "official"],
  ["official-insider-interview", wb("20021221095730", "insider/interview.shtml"), "official"],
  ["official-insider-calldowns", wb("20031001235217", "insider/calldowns.shtml"), "official"],
  ["official-insider-cinematics", wb("20030312014848", "insider/cinematics.shtml"), "official"],
  ["official-movies", wb("20050525195947", "movies/index.shtml"), "official"],

  // --- 2020 leak coverage ---
  ["kotaku-2020-leak", wbx("2020", "https://kotaku.com/it-seems-an-playable-xbox-build-of-starcraft-ghost-has-1841731450"), "leak"],
  ["verge-2020-leak", "https://www.theverge.com/2020/2/17/21141203/starcraft-ghost-playable-build-leaked-xbox-blizzard", "leak"],
  ["ign-2020-leak", "https://www.ign.com/articles/starcraft-ghost-gameplay-leak-xbox-blizzard-footage-playable-build", "leak"],
  ["engadget-2020-leak", "https://www.engadget.com/2020-02-16-starcraft-ghost-playable-leak.html", "leak"],
  ["polygon-2020-leak", "https://www.polygon.com/2020/2/16/21140101/starcraft-ghost-leak-build-video-devkit-xbox/", "leak"],
  ["vg247-2020-leak", "https://www.vg247.com/starcraft-ghost-leaked-build-new-gameplay", "leak"],
  ["dualshockers-2020-leak", "https://www.dualshockers.com/starcraft-ghost-leaked-gameplay-footage-screenshots-cancelled/", "leak"],
  ["gamingbolt-2020-leak", "https://gamingbolt.com/starcraft-ghost-footage-shows-leaked-playable-build", "leak"],
  ["wccftech-2020-leak", "https://wccftech.com/starcraft-ghost-the-cancelled-third-person-action-game-has-leaked-online/", "leak"],
  ["digitaltrends-2020-leak", "https://www.digitaltrends.com/gaming/starcraft-ghost-playable-build-leaks/", "leak"],
  ["gamerevolution-2020-leak", "https://www.gamerevolution.com/news/633684-leaked-starcraft-ghost-build", "leak"],
  ["betaarchive-40850", wbx("2020", "https://www.betaarchive.com/forum/viewtopic.php?t=40850"), "leak"],
  ["neogaf-1526286", wbx("2020", "https://www.neogaf.com/threads/nihilistic-softwares-starcraft-ghost-2003-build-has-been-leaked.1526286/"), "leak"],
  ["hiddenpalace-may2004", "https://hiddenpalace.org/StarCraft:_Ghost_(May_8,_2004_prototype)", "leak"],
  ["lostmediawiki", wbx("2020", "https://lostmediawiki.com/StarCraft:_Ghost_(partially_found_build_of_cancelled_sci-fi_stealth-action_game;_2006)"), "leak"],
  ["archive-org-item", "https://archive.org/details/starcraftghostxbox_202002", "leak"],

  // --- Development history / interviews / analysis ---
  ["polygon-2016-what-went-wrong", "https://www.polygon.com/2016/7/5/11819438/starcraft-ghost-what-went-wrong/", "history"],
  ["mcv-2016-identity-crisis", "https://mcvuk.com/development-news/nihilistic-swingin-ape-and-blizzard-recall-identity-crisis-that-doomed-starcraft-ghost/", "history"],
  ["rps-cancelled", "https://www.rockpapershotgun.com/why-was-starcraft-ghost-cancelled", "history"],
  ["screenrant-cancelled", "https://screenrant.com/why-starcraft-ghost-cancelled-blizzard-shooter-game/", "history"],
  ["gamedeveloper-postpone", "https://www.gamedeveloper.com/game-platforms/blizzard-refocuses-console-dev-postpones-i-starcraft-ghost-i-", "history"],
  ["gamesindustry-indefinitely-postponed", "https://www.gamesindustry.biz/starcraft-ghost-is-indefinitely-postponed", "history"],
  ["gamespot-uncloaked-2002", "https://www.gamespot.com/articles/starcraft-ghost-uncloaked/1100-2880889/", "history"],
  ["gamespot-preview-2002", wbx("2003", "https://www.gamespot.com/articles/starcraft-ghost-preview/1100-2882341/"), "history"],
  ["gamespot-nihilistic-exit-2004", wbx("2004", "https://www.gamespot.com/articles/starcraft-ghost-delayed-nihilistic-no-longer-on-the-project/1100-6101105/"), "history"],
  ["ign-2003-details", "https://www.ign.com/articles/2003/03/30/starcraft-ghost-details-2", "history"],
  ["ign-nihilistic-exits-2004", "https://www.ign.com/articles/2004/06/22/nihilistic-exits-starcraft-ghost", "history"],
  ["gamesindustry-nihilistic-out", "https://www.gamesindustry.biz/nihilistic-no-longer-working-on-starcraft-ghost", "history"],
  ["eurogamer-wow-killed", "https://www.eurogamer.net/world-of-warcraft-killed-starcraft-ghost", "history"],
  ["eurogamer-cube-cancel", "https://www.eurogamer.net/news031105blizzardghostcube", "history"],
  ["eurogamer-nihilistic", "https://www.eurogamer.net/news230604nihilistic", "history"],
  ["vg247-morhaime", "https://www.vg247.com/morhaime-starcraft-ghost-canned-due-to-wow-insta-success", "history"],
  ["kotaku-morhaime-2011", wbx("2011", "https://kotaku.com/the-head-of-blizzard-explains-the-death-of-starcraft-gh-30833489"), "history"],
  ["vg247-demo-reel", "https://www.vg247.com/nihilistic-software-demo-reel-shows-a-glimpse-of-starcraft-ghost", "history"],
  ["gamesindustry-qa-2005", "https://www.gamesindustry.biz/starcraft-ghost-questions-answers", "history"],
  ["n-europe-e3-2004", wbx("2004", "https://n-europe.com/news/e3-2004-starcraft-press-release/"), "history"],
  ["vooks-delayed-2004", "https://www.vooks.net/starcraft-ghost-delayed/", "history"],
  ["blizzplanet-faq", "https://www.blizzplanet.com/blog/comments/starcraft_ghost_faq", "history"],
  ["blizzplanet-abilities", "https://www.blizzplanet.com/blog/comments/starcraft_ghost___abilities", "history"],
  ["blizzplanet-kwasneski-interview", "https://www.blizzplanet.com/blog/comments/starcraft-ghost-interview-julian-kwasneski", "history"],
  ["blizzplanet-huebner-xboxevolved", "https://www.blizzplanet.com/blog/comments/nihilistic_starcraft_ghost_woes_xbox_evolved", "history"],
  ["rpgclassics-scghost", "http://archive.rpgclassics.com/subsites/starcraft/scghost.shtml", "history"],

  // --- Concept art / soundtrack / reference ---
  ["wikipedia-scghost", "https://en.wikipedia.org/wiki/StarCraft:_Ghost", "reference"],
  ["wikipedia-nihilistic", "https://en.wikipedia.org/wiki/Nihilistic_Software", "reference"],
  ["fandom-nihilistic", "https://starcraft.fandom.com/wiki/Nihilistic_Software", "reference"],
  ["fandom-scghost", wbx("2020", "https://starcraft.fandom.com/wiki/StarCraft:_Ghost"), "reference"],
  ["engadget-concept-art-2009", "https://www.engadget.com/2009-03-17-starcraft-ghost-concept-art-surfaces-game-hasnt.html", "reference"],
  ["siliconera-concept-art", "https://www.siliconera.com/starcraft-ghost-concept-art-reveals-stealth-specter-and-protoss-shadow-husk/", "reference"],
  ["gameinformer-archives", "https://gameinformer.com/b/features/archive/2013/12/19/from-the-game-informer-archives-starcraft-ghost.aspx", "reference"],
  ["iamag-concept-art", "https://www.iamag.co/concept-art-collection-for-blizzard-cancelled-game-starcraft-ghost/", "reference"],
  ["n4g-concepts", "https://n4g.com/news/975073/long-lost-starcraft-ghost-concepts", "reference"],
  ["artstation-ericbrowning", "https://www.artstation.com/eric2378/albums/13774800", "reference"],
  ["vgmdb-ost", wbx("2023", "https://vgmdb.net/album/125594"), "reference"],
  ["reddit-story-pieced", wbx("2020", "https://old.reddit.com/r/starcraft/comments/f5vr5y/the_story_of_starcraft_ghost_what_can_be_pieced/"), "reference"],
  ["reddit-soundtrack", wbx("2023", "https://old.reddit.com/r/starcraft/comments/107v4af/uncovered_the_starcraft_ghost_soundtrack_by_kevin/"), "reference"],
  ["reddit-blizzcon-brochure", wbx("2017", "https://old.reddit.com/r/starcraft/comments/5odz3w/brochure_from_blizzards_cancelled_starcraft_ghost/"), "reference"],
];

function run(args) {
  return execFileSync("browser", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

function jget(obj) {
  if (!obj || typeof obj !== "object") return {};
  const d = obj.data && typeof obj.data === "object" ? obj.data : obj;
  return { envelope: obj, result: d };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CHALLENGE = [
  "Performing security verification",
  "Validating browser",
  "Just a moment",
  "Enable JavaScript and cookies",
  "Verification successful. Waiting",
];

async function waitReady() {
  for (let i = 0; i < 15; i++) {
    await sleep(2000);
    let t = "";
    try {
      const raw = run(["extract", "get-text", "--selector", "body", "--length", "400"]);
      t = jget(JSON.parse(raw)).result.text ?? "";
    } catch {
      t = "";
    }
    if (!CHALLENGE.some((c) => t.includes(c))) return;
  }
}

async function fetchText(name, url) {
  run(["navigate", "goto", "--url", url, "--timeout", "60000"]);
  await waitReady();
  let offset = 0;
  let checksum;
  let out = "";
  let meta = {};
  for (let i = 0; i < 40; i++) {
    const args = [
      "extract",
      "get-text",
      "--selector",
      "body",
      "--ellipsize-text-after",
      "100000",
      "--chunk",
      "--offset",
      String(offset),
      "--length",
      "60000",
    ];
    if (checksum) args.push("--checksum", checksum);
    const raw = run(args);
    const obj = JSON.parse(raw);
    const r = jget(obj).result;
    if (obj.success === false) throw new Error(obj.error || "get-text failed");
    out += r.text ?? "";
    meta = {
      url,
      truncated: r.truncated ?? false,
      total_bytes_estimate: r.total_bytes_estimate ?? null,
      snapshot_checksum: r.snapshot_checksum ?? null,
      chunks: i + 1,
    };
    if (r.next_offset === null || r.next_offset === undefined) break;
    offset = r.next_offset;
    checksum = r.snapshot_checksum;
  }
  return { text: out, meta };
}

let ok = 0;
let failed = 0;
try {
  run(["session", "launch"]);
} catch (err) {
  const msg = String(err.stderr ?? err.message ?? "");
  if (msg.includes("profile conflict")) {
    console.log("reusing active browser session");
  } else {
    throw err;
  }
}
for (const [name, url, kind] of SOURCES) {
  const textPath = resolve(OUT, `${name}.txt`);
  if (process.env.FORCE !== "1" && existsSync(textPath) && readFileSync(textPath, "utf8").length > 40) {
    console.log(`skip ${name}`);
    ok++;
    continue;
  }
  try {
    const { text, meta } = await fetchText(name, url);
    writeFileSync(textPath, text);
    writeFileSync(resolve(OUT, `${name}.meta.json`), JSON.stringify({ name, kind, ...meta }, null, 2));
    const flag = meta.truncated ? "TRUNC" : "ok";
    console.log(`${flag} ${name} (${text.length} chars)`);
    ok++;
  } catch (err) {
    failed++;
    console.log(`FAIL ${name}: ${err.message.split("\n")[0]}`);
  }
}
run(["session", "terminate"]);
console.log(`\n== ${ok} ok, ${failed} failed ==`);
