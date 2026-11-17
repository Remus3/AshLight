# 0009 - DATA-LICENSE: game-data sources, what is bundled vs fetched

Date: 2026-11-16. Trigger: ROADMAP row DATA-LICENSE (decision 0004 item 7:
snapshots only after this ruling). Inputs: research 0005 ("Game data
exports", "poe2db.tw", "PoE2 Wiki") and research 0010 section 1, all
accessed 2026-11-16.

## Verification status at the original ruling (2026-11-16)

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

## Verification results (DATA-LICENSE-VERIFY, 2026-11-17)

Web access worked this session. Evidence and quotes: research 0011. Every
URL below was accessed 2026-11-17. Status: V verified, C corrected,
U unverifiable (could not be read at the source).

1. V. repoe-fork code license is MIT, (c) 2016 brather1ng. Source:
   https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md.
   It adds a notice that generated files in `data` are owned by Grinding
   Gear Games and "shall not be used or published without being in
   accordance with their terms of use". (Resolves the "MIT assumed" line;
   the data notice is new and supports decision items 1 and 2.)
2. V. repoe-fork credits: GGG owns the data files ("The contents of all
   `data` files obviously belong to them"). Source:
   https://github.com/repoe-fork/repoe.
3. V. https://repoe-fork.github.io/poe2/ states no license and links to the
   repoe-fork GitHub project.
4. C. The hosted PoE2 files do not match the fetch list. `mods.json` and
   `base_items.json` exist (HTTP 200). `stats.json` and
   `stat_translations.json` return 404. The real files are
   `stats_by_file.json` (14.4 MB) and the directory `stat_translations/`
   (for example `stat_translations/stat_descriptions.json`, 10.1 MB). The
   snapshot source list in `server/al/theorycraft/snapshot.py` points at
   the two 404 URLs: ROADMAP row DATA-SRC-URLS.
5. U. The repoe-fork README warning that formats may change at any time:
   not seen in the fetched README text; keep treating formats as unstable.
6. C. A GGG PoE2 tree export exists:
   https://github.com/grindinggear/poe2-skilltree-export (public, `main`,
   files `assets/`, `README.md`, `data.json`; raw `data.json` returns 200).
   It has NO LICENSE file and its README says only "Exported data for Path
   of Exile 2's Passive Skill Tree". The PoE1 repo
   (https://github.com/grindinggear/skilltree-export) also shows no license
   file. See "What changes" below (item 3 amended).
7. V (code) / U (data). Path of Building PoE2 is MIT (c) David Gowor with
   third-party licenses listed:
   https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/LICENSE.md
   (https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2). The
   `src/Data` files' own terms could not be read; the MIT grant covers
   PoB's code, not GGG-owned data. Nothing from PoB data is bundled.
8. V. GGG developer terms (https://www.pathofexile.com/developer/docs):
   only resources in the API Reference or Data Exports are supported, other
   internal APIs or in-game resources are denied; "we cannot allow our
   Intellectual Property to be used to generate commercial revenue"; the
   "isn't affiliated" line must be visible; tools that interact with the
   game or its files mean account termination. U: the Terms of Use
   sections it cites (7b, 7c, 7i) were not shown, and the page gives no
   explicit rule on redistributing extracted data. Hence "bundle nothing"
   stands.
9. V. poe2db: "Wikis Content is available under CC BY-NC-SA 3.0 unless
   otherwise noted", (c) 2014-2026 PoE2DB, GGG holds the game copyright,
   some articles adapted from Project PoE Wiki. Source:
   https://poe2db.tw/General_disclaimer. C: the page has no scraping,
   crawling or API terms at all (absence, not a prohibition), and our fetch
   was not bot-blocked there. Link-out only still stands (NC-SA, no
   sanctioned API).
10. V (secondary). PoE2 wiki text and graphics are CC BY-NC-SA 3.0
    Unported where lawfully licensable; game assets are GGG copyright, use
    permitted on the wiki only. Source: search summary of
    https://www.poe2wiki.net/wiki/Path_of_Exile_2_Wiki:Copyrights . The
    page itself (and /General_disclaimer, /COPYING) returned an Anubis
    "Access Denied" bot wall to our fetch: V that automated access is
    blocked; U the license text was not read first-hand.
11. V. poe.ninja API terms: https://poe.ninja/docs/api. Descriptive
    User-Agent identifying the app AND a contact; modest concurrency and
    volume; use ETag / conditional requests, do not bypass caching; no
    polling faster than a few minutes; do not use the API to replicate the
    site; desktop apps "should proxy these requests through their own
    backend"; only the economy endpoints are documented, builds / profiles
    endpoints are "not available for third-party use"; no SLA, breaking
    changes without notice; misbehaving clients are blocked. poe.ninja
    footer: "not affiliated with or endorsed by Grinding Gear Games".
    Effect on DATA-NINJA: UA must carry a contact; economy endpoints only.
12. C. User-Agent for GGG's API: the developer docs require
    `User-Agent: OAuth {clientId}/{version} (contact: {contact}) ...` from
    "any application that interacts with our API". Our "AshLight plus
    version" rule is not enough where the OAuth API is used: it needs the
    client id form and a contact. The pathofexile.com/api/trade2 endpoints
    are not described on the docs page (U); GGG staff forum posts (search
    summary only) say a unique identifiable User-Agent is needed or you get
    blocked, and that rate limits are per IP or account. Research 0004
    stays the working note for trade2; no contact value is stored in the
    tracked tree (per-host `config/local.json`).
13. V. Apache-2.0 vs CC BY-NC-SA share-alike incompatibility: a legal
    reading, not a fetchable claim; unchanged.

Counts (13 numbered lines, 17 claim parts; lines 7, 8, 9, 10, 12 split): verified
8 (1, 2, 3, 7 code, 8, 9 license, 10 blocked-bot, 11), corrected 4 (4, 6,
9 scraping-terms note, 12), unverifiable 5 (5, 7 data, 8 ToS sections, 10
license text first-hand, 12 trade2 docs). Line 13 is reasoning, not
counted. Nothing found forbids the fetch-only ruling.

### What changes for fetch / bundle

- Bundling: unchanged, still nothing (the MIT grant covers code only; data
  is GGG-owned and its "terms of use" are not spelled out anywhere
  readable).
- Fetch list corrected: `stats` -> `stats_by_file.json`;
  `stat_translations` -> `stat_translations/stat_descriptions.json`
  (combined file; others optional). ROADMAP DATA-SRC-URLS.
- Item 3 amended: the GGG PoE2 tree export exists, so the "disabled until
  confirmed" gate is lifted for DATA-TREE-SRC: it may be fetched under the
  item 2 conditions at
  https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/data.json
  (host raw.githubusercontent.com to ALLOWED_HOSTS). No license file exists,
  so it stays fetch-only, never bundled. Decided without an adjudicator: no
  fork in the road, it applies the existing conservative rule.
- poe.ninja and GGG API clients must send the User-Agent form with a
  contact (ROADMAP DATA-NINJA note); poe.ninja's "proxy through your own
  backend" advice is met by the local core being the only caller (one
  caller per machine, one request per hour).

## Decision

1. Bundle nothing. No file, excerpt or derived table from repoe-fork, any
   GGG export, poe2db or the wiki is committed to this repo or shipped in
   any AshLight package. The tracked tree holds only source URLs, our own
   code and, at most, SHA-256 pins.
2. Build-time fetch into the user's own sidecar cache is permitted for:
   the repoe-fork PoE2 JSON files `mods`, `base_items`, `stats`,
   `stat_translations` (https://repoe-fork.github.io/poe2/). Conditions:
   - fetched on the user's machine by `scripts/build.ps1` only while the
     web_data opt-in is on or the build is forced (AUDIT-SNAPSHOT-OPTIN
     amendment below), into
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

## Amendment 2026-11-17 (AUDIT-SNAPSHOT-OPTIN, audit finding T1)

Ruled by the adjudicator agent (CLAUDE.md FLEET item 1).
- Decision: the build-time game-data snapshot follows the single
  `web_data` opt-in of decision 0013 (default off). `scripts/build.ps1`
  runs it only when config/local.json holds `"web_data": true` (strict
  bool, as the core reads it) or the build is forced with `-Snapshot` /
  env `AL_SNAPSHOT=1` (passed on as `snapshot --opt-in`); `-NoSnapshot` /
  `AL_NO_SNAPSHOT=1` still skip and win. `snapshot.main` checks the same
  setting itself, so a direct run also makes no request while it is off.
  Once web data is on, every build refreshes the snapshot by itself
  (the 24 h gate keeps a re-run a no-op).
- Alternatives: (b) keep the opt-out and write a build-time exception into
  0013 - rejected: users read "nothing hits the network while off"
  literally and a fresh build would still contact two hosts; (c) a second
  `snapshot` setting - rejected: two consent switches contradict 0013's
  one opt-in.
- Why: one consent switch, the promise kept literally, zero-click after
  the opt-in; the app already treats the snapshot as optional (zone levels,
  tree names and the data credit read a missing cache as absent).
- Reverses if: a core feature turns out to need snapshot data and cannot
  degrade, the operator rules that a build-time fetch is not "web data",
  or first-run use shows users missing the data and not finding the switch.
- Tests: tests/test_audit_snapshot_optin.py.
