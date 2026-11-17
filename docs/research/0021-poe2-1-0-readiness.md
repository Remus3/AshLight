# 0021 - PoE2 1.0 launch readiness (2026-12-11)

All sources accessed 2026-11-17. Extends 0018 section 1 (patch / league
state) and 0017 (PoB drift). Feeds ROADMAP row UTIL-1.0-POST. Official 1.0
patch notes are NOT published yet; every content figure below is from the
ExileCon 2026 reveal (2026-11-07/08) as reported by outlets that cite the
official forum, Steam page and the official X account. Re-check against the
patch notes when they appear (typically days before launch).

## 1. What is announced

- Date and model: 1.0 leaves Early Access and goes free-to-play on
  2026-12-11 (PST), PC, PS5 and Xbox Series X|S; exact launch hour not
  announced
  (https://www.keengamer.com/articles/news/path-of-exile-2-adds-the-shadow-and-conquerors-of-wraeclast-league-at-its-december-11-launch/ ,
  https://www.poe-vault.com/poe2/news/path-of-exile-2-launches-free-to-play-on-december-11 ,
  accessed 2026-11-17).
- Acts: Acts 5 and 6 finish the campaign, "24 new areas and 18 major
  bosses", ending with a return to Oriath; the endgame gets a new story arc
  and "Atlas progression refinements" (keengamer, same URL, accessed
  2026-11-17). Area names and internal area ids: NOT published.
- Classes: Shadow ("a dagger and trap specialist focused on stealth") and
  Duelist ("the game's first sword class"); 10 of 12 planned classes at
  launch, the last two after launch (keengamer, accessed 2026-11-17).
  Ascendancy names: reported as Assassin / Infiltrator (Shadow) and Knight
  (Duelist, a second one later); outlets conflict - UNVERIFIED
  (https://www.iggm.com/news/poe-2-1-0-conquerors-of-wraeclast-league-shadow-duelist-major-updates-explained ,
  search snippet, accessed 2026-11-17).
- League: "Conquerors of Wraeclast", a siege league: recruit mercenaries,
  place troops before each fight, 23 army battles in the campaign, an
  endgame stronghold and sieges of rival factions' castles (keengamer,
  accessed 2026-11-17); factions contest "sections of the Atlas"
  (https://www.poe-vault.com/poe2/news/conquerors-of-wraeclast-explained-path-of-exile-2s-1-0-league-has-you-raise-an-army ,
  search snippet, accessed 2026-11-17).
- Other: 40 new uniques, 70 revamped uniques, "an overhaul of the passive
  skill tree", balance pass, more support gems
  (https://www.cheatcc.com/articles/path-of-exile-2-sets-december-11-for-1-0-adding-acts-5-and-6-and-two-classes/ ,
  search snippet; page itself returned 403; accessed 2026-11-17).
- League end: Forbidden Rites and Runes of Aldur close at the 1.0 launch,
  per GGG's 2026-08-31 FAQ as reported; whether characters migrate to
  Standard is not stated - UNVERIFIED
  (https://www.playnews.gg/en/guides/path-of-exile-2-forbidden-rites-runs-for-98-days-not-a-month-ggg-s-faq-contradicts-our-august-28-reading ,
  https://timesaver.gg/blog/poe2-1-0-wipe-currency-characters-what-happens ,
  search snippets, accessed 2026-11-17).
- In-game death summary: a third-party article saw a "show death summary"
  button in a GGG performance video and guesses it is for 1.0 - speculation
  only, UNVERIFIED
  (https://www.mmoexp.com/News/path-of-exile-2-1-0-patch-notes-new-classes-death-recap-swords-daggers-and-more.html ,
  accessed 2026-11-17).

## 2. Impact on AshLight

- Client.txt: no announcement touches the log. New lines are likely from
  the league (army battle / siege NPC dialogue, stronghold scene names) and
  Acts 5-6 scenes; nothing known about formats. The debug sink (0002
  section 4) catches them without code changes; review it on launch day.
- Act ids: acts.py already reads `G5_` / `G6_` as Act 5 / 6 (UTIL-1.0-READY,
  done). The real 1.0 prefixes are UNVERIFIED until a live log; the
  return-to-Oriath area may use another prefix.
- Classes: charjson.BASE_CLASSES has Duelist / Shadow; ASCENDANCY_CLASS
  lacks the 1.0 ascendancies (names unverified, add from patch notes or
  the GGG tree export).
- Passive tree overhaul: the build-time GGG tree export snapshot
  (github.com/grindinggear/poe2-skilltree-export) and the id_match guard
  (DATA-TREE-IDS, 0015) must be re-run; old PoB codes may reference removed
  nodes (MATH-POB-DRIFT-GUARD fails loudly, decision 0028).
- poe.ninja: "The first entry is the current temporary challenge league"
  (https://poe.ninja/docs/api , accessed 2026-11-17). ninja.py re-reads the
  league every 6 h and within the hour after a 404 / empty overview
  (UTIL-1.0-READY), so the new league is picked up on day 1; the first
  hours will have few listings (thin-market rules apply).
- PoB-PoE2: latest release still v0.23.1 (2026-07-28), no 0.5.5 or 1.0
  release (https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases ,
  accessed 2026-11-17). A 1.0 PoB release will likely land days after
  launch; TC-PIN stays on HOLD until then (0017), and the calc component
  degrades to "PoB not current" meanwhile.
- Free-to-play: many new players; levelling helpers (HUD-ACT, pace) and the
  first-run path gain value.

## 3. UTIL-1.0-POST checklist (copied into the ROADMAP row)

1. Read the 1.0 patch notes when published: act / area names, ascendancy
   names, chat or log changes, filter syntax changes.
2. Launch day: read the debug sink of the first 1.0 Client.txt; add a
   fixture for every new system line shape (league battles, stronghold,
   Acts 5-6 scenes, death summary if any).
3. Confirm the Act 5 / 6 area-id prefixes and the return-to-Oriath id
   live; fix acts.act_of if not `G5_` / `G6_`.
4. Refresh the repoe-fork world_areas snapshot (build step, decision 0009)
   so Acts 5-6 get zone levels.
5. Add the 1.0 ascendancies to charjson.ASCENDANCY_CLASS.
6. Refresh the GGG passive tree export snapshot and re-run the id_match
   guard (tree overhaul).
7. Confirm poe.ninja lists the new league first and the price card label
   switches within 1 h.
8. When PoB-PoE2 ships a 1.0 release: run TC-DRIFT, bump config/tc_pins.json
   (decision 0018).

## Sources

- https://www.keengamer.com/articles/news/path-of-exile-2-adds-the-shadow-and-conquerors-of-wraeclast-league-at-its-december-11-launch/ (accessed 2026-11-17)
- https://www.poe-vault.com/poe2/news/path-of-exile-2-launches-free-to-play-on-december-11 (search snippet, accessed 2026-11-17)
- https://www.poe-vault.com/poe2/news/conquerors-of-wraeclast-explained-path-of-exile-2s-1-0-league-has-you-raise-an-army (search snippet, accessed 2026-11-17)
- https://www.iggm.com/news/poe-2-1-0-conquerors-of-wraeclast-league-shadow-duelist-major-updates-explained (search snippet, accessed 2026-11-17)
- https://www.cheatcc.com/articles/path-of-exile-2-sets-december-11-for-1-0-adding-acts-5-and-6-and-two-classes/ (search snippet, accessed 2026-11-17)
- https://www.playnews.gg/en/guides/path-of-exile-2-forbidden-rites-runs-for-98-days-not-a-month-ggg-s-faq-contradicts-our-august-28-reading (search snippet, accessed 2026-11-17)
- https://timesaver.gg/blog/poe2-1-0-wipe-currency-characters-what-happens (search snippet, accessed 2026-11-17)
- https://www.mmoexp.com/News/path-of-exile-2-1-0-patch-notes-new-classes-death-recap-swords-daggers-and-more.html (accessed 2026-11-17)
- https://poe.ninja/docs/api (accessed 2026-11-17)
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases (accessed 2026-11-17)
