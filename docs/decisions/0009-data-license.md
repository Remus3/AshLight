# 0009 - DATA-LICENSE: game-data sources, what is bundled vs fetched

Date: 2026-11-16. Trigger: ROADMAP row DATA-LICENSE (decision 0004 item 7:
snapshots only after this ruling). Inputs: research 0005 ("Game data
exports", "poe2db.tw", "PoE2 Wiki") and research 0010 section 1, all
accessed 2026-11-16.

## Verification status (read this first)

This session could NOT fetch any license page: the web fetch tool was
refused by permission for every URL tried on 2026-11-16
(https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md,
https://repoe-fork.github.io/poe2/,
https://github.com/grindinggear/poe2-skilltree-export,
https://github.com/grindinggear/skilltree-export,
https://poe2db.tw/General_disclaimer,
https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights). The ruling
therefore uses only what research 0005 / 0010 already recorded, and rules
conservatively. Follow-up row DATA-LICENSE-VERIFY re-checks each source.

Known facts (research 0005, accessed 2026-11-16):
- repoe-fork (https://github.com/repoe-fork/repoe): repo license UNVERIFIED
  (a LICENSE.md is linked but its text was not read; decision 0004 assumed
  MIT for the code). Its credits state Grinding Gear Games owns the contents
  of the data files. Hosted PoE2 JSON at https://repoe-fork.github.io/poe2
  (stats, mods, base_items, gems, stat_translations, item_classes); the page
  states no license; the README warns the formats may change at any time.
- GGG passive tree export for PoE2: whether a GGG-published
  `poe2-skilltree-export` repository exists, its URL and its terms are
  UNVERIFIED (only the PoE1 `skilltree-export` is known to the project).
- poe2db: "Wikis Content is available under CC BY-NC-SA 3.0 unless
  otherwise noted"; GGG holds the game copyright
  (https://poe2db.tw/General_disclaimer). No API or scraping permission.
- PoE2 wiki: CC BY-NC-SA 3.0 Unported (search summary; the page itself is
  behind bot protection). Automated access is actively blocked.
- AshLight is Apache-2.0 (LICENSE, NOTICE): not share-alike compatible
  with CC BY-NC-SA.

## Decision

1. Bundle nothing. No file, excerpt or derived table from repoe-fork, any
   GGG export, poe2db or the wiki is committed to this repo or shipped in
   any AshLight package. The tracked tree holds only source URLs, our own
   code and, at most, SHA-256 pins.
2. Build-time fetch into the user's own sidecar cache is permitted for:
   the repoe-fork PoE2 JSON files `mods`, `base_items`, `stats`,
   `stat_translations` (https://repoe-fork.github.io/poe2/). Conditions:
   - fetched on the user's machine by `scripts/build.ps1` (opt-out), into
     `<AL sidecar>\Cache\gamedata\` resolved by `server/al/paths.py`;
   - never at runtime by the core, never committed, never uploaded,
     never redistributed from the cache;
   - a manifest per file (URL, fetch date, SHA-256, size, ETag);
   - a truthful User-Agent naming AshLight and its version; conditional
     requests (ETag / Last-Modified) and at most one network check per
     file per 24 h, so a re-run is a no-op;
   - https only, redirects only within the allowlisted hosts;
   - the attribution text below shown wherever the data is used.
3. GGG passive tree export: allowed in principle under the same conditions
   (it is GGG's own publication for tool makers), but DISABLED in the
   snapshot source list until DATA-TREE-SRC confirms the PoE2 repository,
   its data-file URL and its terms. No guessed URL is fetched.
4. poe2db and the PoE2 wiki: link out only. Not fetched at build time, not
   fetched at runtime, no text or table copied (CC BY-NC-SA 3.0 is
   non-commercial and share-alike, our Apache-2.0 tree cannot absorb it,
   and both sites have no sanctioned API and block bots).
5. Attribution text (exposed as
   `server.al.theorycraft.snapshot.ATTRIBUTION`; the UI line is ROADMAP
   row TC-SNAP-UI):

   "Game data (c) Grinding Gear Games. Item, mod and stat data from the
   RePoE fork community export (repoe-fork), downloaded to this computer
   at build time. This product isn't affiliated with or endorsed by
   Grinding Gear Games in any way."

## Alternatives

- Bundle a snapshot in the repo (simplest, offline first run): rejected;
  repoe-fork license unverified and the data is GGG-owned; bundling is
  redistribution.
- Block all snapshots until a web-enabled session verifies every license:
  rejected; a local fetch of public files by the user's own build, never
  redistributed, is the same act as the user's browser opening them, and
  what PoB and other community tools already rely on. Kept the verify row.
- Snapshot poe2db / wiki data at build time: rejected (NC-SA terms, no
  permission, bot protection).
- Runtime fetch on demand: rejected by decision 0004 item 7 (build-time
  snapshots only).

## Why

The ToS floor allows public web data; GGG's policy concern is game-file
access and commercial use of its IP, neither of which a local, credited,
non-redistributed copy of a public community export touches. Keeping the
tracked tree free of data keeps the public repo clean whatever the
repoe-fork license turns out to be.

## Reverses if

- DATA-LICENSE-VERIFY finds the repoe-fork LICENSE forbids this use, or
  GGG objects to tools consuming extracted data: remove the source from
  the snapshot list and delete the cache on the next build.
- A license that permits redistribution is confirmed for a source (e.g. a
  GGG tree export with explicit terms): bundling that source may be
  re-ruled.
- poe2db or the wiki publish an API with terms that permit app use.
