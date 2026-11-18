# 0037 - Data sources: PoB-PoE2, LuaJIT / WinLibs, repoe-fork, GGG tree export

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B1
permitted data sources (PoB-PoE2, repoe-fork, passive tree export). Scope:
the build-time and calc data sources: pinned vs current, drift risk, what
PoE2 1.0 (2026-12-11) breaks, and watcher inputs for note 0058. Extends
research 0011, 0014, 0015, 0017, 0021 and 0030.
Status: draft

Method: read-only GETs of public repository pages and files with a generic
client, plus a blobless no-checkout clone of PoB-PoE2 (9.3 MB) in the
sidecar Scratch for history and file-at-ref reads. Nothing from any upstream
tree was executed. No upstream data is kept in the repo; this note holds
counts and hashes only.

## Sources (all accessed 2026-11-17)

- PB-REF: git ref advertisement of PoB-PoE2 (tags, branch heads),
  https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2.git/info/refs?service=git-upload-pack
- PB-REL: https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases.atom
  (last 10 releases with their notes)
- PB-SRC: the same repository's history and files at v0.23.1 (7d6f530c),
  dev (601768bd) and beta (45bb2301): src/HeadlessWrapper.lua,
  src/_SimpleGraphic.def.lua, src/Launch.lua, src/Data/TradeSiteStats.lua,
  src/GameVersions.lua, LICENSE.md, RELEASE.md, CONTRIBUTING.md,
  .github/workflows/beta.yml and release.yml
- LJ-REF: https://github.com/LuaJIT/LuaJIT.git/info/refs?service=git-upload-pack
- LJ-FEED: https://github.com/LuaJIT/LuaJIT/commits/v2.1.atom
- LJ-ZIP: https://github.com/LuaJIT/LuaJIT/archive/63c8f1a9b479ba5518cf6a170ff7729178bc3cfd.zip
- WL-API: https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/tags/16.2.0posix-23.1.3-14.0.0-ucrt-r3
- WL-REL: https://github.com/brechtsanders/winlibs_mingw/releases.atom
- GH-A1: https://github.blog/open-source/git/update-on-the-future-stability-of-source-code-archives-and-hashes/
  (published 2023-02-21)
- GH-A2: https://github.blog/changelog/2023-01-30-git-archive-checksums-may-change/
- RF-PAGES: https://repoe-fork.github.io/poe2/ (headers of the six fetched
  files, index.json, and the stat file as deployed 2026-11-18 05:43 GMT)
- RF-DATA: https://github.com/repoe-fork/poe2/commits/master.atom
- RF-CODE: https://github.com/repoe-fork/repoe/commits/master.atom
- RF-FIX: https://github.com/repoe-fork/repoe/commit/21f4f6d1008dac46621575ad72445bac66e5364b
- RF-ISSUE: https://github.com/repoe-fork/repoe/issues/79
- RF-README: https://raw.githubusercontent.com/repoe-fork/repoe/master/README.md
- RF-LIC: https://raw.githubusercontent.com/repoe-fork/repoe/master/LICENSE.md
- GT-REF: https://github.com/grindinggear/poe2-skilltree-export.git/info/refs?service=git-upload-pack
- GT-FEED: https://github.com/grindinggear/poe2-skilltree-export/commits/main.atom
- GT-DATA: https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/data.json
  (and README.md beside it; LICENSE and LICENSE.md return 404)
- GGG-DATA: https://www.pathofexile.com/developer/docs/data (text as cached
  by the decision 0044 watch, read 2026-11-18 02:06 UTC)
- NB: https://www.notebookcheck.net/Path-of-Exile-2-finally-reveals-its-gargantuan-full-release-update.1444706.0.html
  (2026-11-07; 1.0 content, a secondary source)
- P05: https://www.rpgsite.net/news/20334-path-exile-2-return-of-the-ancients-release-date-new-content-screenshots
  (0.5.0 launch date 2026-05-29; search summary, several outlets agree)
- Repo files read: config/tc_pins.json, tools/tc_drift.py, tools/tc_pin.py,
  tools/al_loop.py, server/al/theorycraft/snapshot.py, treedata.py,
  bridge.lua, bridge.py, charjson.py, buildlive.py, datacredit.py,
  server/al/tradestats.py, acts.py, diag.py, core.py,
  tests/test_tc_pob_drift_guard.py, tests/tc_live_util.py,
  docs/ops/1.0-launch-runbook.md, decisions 0004, 0009, 0015, 0018, 0020,
  0022, 0025, 0027, 0028, 0034, 0037, 0044.

## Summary

- Every pin is current today. PoB-PoE2 v0.23.1 is still the newest release,
  the LuaJIT v2.1 head is still the pinned commit, the pinned WinLibs asset
  is the newest POSIX UCRT release and its published digest equals the pin.
  Licences are unchanged.
- The next PoB-PoE2 release breaks the bridge. On dev and on the weekly
  beta branch the headless entry file was reshaped: 3 of the 23 drift guard
  rows fail there, against 0 of 23 at each of 9 sampled tags from v0.5.0 to
  v0.23.1. The fix is one lookup in bridge.lua plus 3 guard rows and can be
  made today.
- TC-DRIFT cannot finish a pin move as built: the release check is skipped
  while HALT exists (now), every trial of a data-carrying release goes
  static-red on a stale file hash, the live gate compares against a GUI
  reading recorded for v0.23.1, and there is no rehearsal against dev.
- repoe-fork is healthy and fast (5 game client versions exported in 21
  days, a fix deployed 30 minutes after its commit) but volatile by its own
  word. Its deploy of 2026-11-18 lifts trade stat id coverage of the default
  weights from 11 of 39 to 39 of 39, which meets the reversal condition of
  the decision 0037 PoB fallback.
- The GGG tree export is unchanged since 2026-09-04. Previews reach its
  main branch about 3.6 days before a patch, so a 1.0 preview tree would be
  fetched while the live game is still 0.5.5.
- The 1.0 runbook covers its 8 checklist items and misses 8 others (R7).
- Twelve ranked recommendations and eight watcher inputs (W1-W8) follow.

## Current state

What the code does today:

- Pins: config/tc_pins.json:4-16 (PoB-PoE2 tag, commit, archive sha256,
  size), :17-24 (`pob2_files`: one data file hash), :25-38 (LuaJIT),
  :39-51 (WinLibs toolchain). Validation and fetch: tools/tc_pin.py:119-200
  and :299-334; host allowlist :55-59; the setup digest covers schema, pob2
  and luajit only (:203-207).
- TC-DRIFT automates: one release read per 24 h (tools/tc_drift.py:57,
  :139-152, :196-217), rate limit handling (:118-136), one detached trial
  per new tag, at most 3 launches (:60-61, :220-227, :300-318), two
  downloads that must agree (:419-431), a candidate pin file (:432-439),
  extraction (:440) and the static guard subset (:65-66, :368-373).
- TC-DRIFT needs a session for: the live trial (`--live`, or a local
  switch, :263-270), `apply` (:459-479), the commit, the HOLD line for
  decision 0004 (:482-491), any bridge.lua or guard edit, the GUI
  reference, and the decision 0028 budget re-measure.
- Snapshot: six sources (server/al/theorycraft/snapshot.py:73-81), 24 h
  minimum age (:57), conditional requests (:178-183), JSON validity as the
  only content check (:188-192), a manifest per file (:198-216), the GGG
  tree gated on a User-Agent contact (:43-55, :167-169).
- Readers: world_areas (server/al/acts.py:171-206, also zoneguide.py and
  underlevel.py), base_items (server/al/theorycraft/basetypes.py:37-62,
  server/al/campaign.py), stat_translations
  (server/al/tradestats.py:73-103), skilltree
  (server/al/theorycraft/treedata.py:175-217). `mods` and `stats` have no
  reader anywhere under server/.
- Attribution: server/al/theorycraft/datacredit.py:14-32 names repoe-fork,
  the trade site origin of the ids, PoB (MIT) and the GGG tree export.

Pinned vs current, measured 2026-11-17:

- PoB-PoE2: pin v0.23.1, commit 7d6f530c (2026-07-28). Newest release:
  the same; `master` head is the pin commit (PB-REF). dev is 109 commits
  ahead (72 in August, 34 in September, 1 each in July, October, November),
  beta 110. LICENSE.md is the same blob at the pin and on dev (MIT). Drift
  risk: high at the next release (F1).
- LuaJIT: pin 63c8f1a9, version 2.1.1794386141 (2026-11-11). The v2.1 head
  is the same commit; the repository has no tags and no releases (LJ-REF).
  The archive re-downloaded today hashes to the pin (LJ-ZIP). Drift risk:
  low; nothing forces a move.
- WinLibs: pin 16.2.0posix-23.1.3-14.0.0-ucrt-r3 (2026-10-18), the newest
  POSIX UCRT release (WL-REL). The API lists the pinned .zip with the same
  size (276414382) and sha256 digest as config/tc_pins.json:46-47; .zip
  assets ship for all four variants (WL-API); the repository's ref listing
  holds 259 tags, so old releases stay available. Drift risk: low.
- repoe-fork: not pinned (latest at fetch). The cache on the dev host (the
  operator's machine) holds the export deployed 2026-11-14 04:18 GMT (game
  client 0.5.5.9); a newer one was deployed 2026-11-18 05:43 GMT, after
  the "Version 0.5.5.10" commit. Drift risk: high for shape, routine for
  content.
- GGG tree export: not pinned (main branch). Head bd87e651, titled 0.5.5,
  2026-09-04; data.json is 5140821 bytes, the size research 0014 and 0015
  recorded. The dev host cache has no tree file (F14). Drift risk: high at
  1.0.

## Findings

- F1. The next PoB-PoE2 release breaks bridge.lua. What: on dev (commit
  9a2c480d, 2026-08-26) src/HeadlessWrapper.lua shrank from 5723 to 2494
  bytes; the launch object moved from a file-local variable to a global
  named `__mainObject__`, and about 50 API stubs, `SetMainObject` among
  them, moved to a new 553-line file src/_SimpleGraphic.def.lua (PB-SRC).
  Evidence: the guard patterns (tests/test_tc_pob_drift_guard.py:40-83) run
  against file contents at each ref give 0 of 23 failing at v0.5.0, v0.8.0,
  v0.12.2, v0.15.0, v0.16.0, v0.20.0, v0.22.0, v0.23.0 and v0.23.1, and 3 of
  23 failing on dev and on beta (rows :41-49). bridge.lua finds the object
  through a global `mainObject` or an upvalue of that name
  (server/al/theorycraft/bridge.lua:258-271); neither exists on dev, so
  `load_build` would end in "PoB did not load the build" (:315; read from
  the code, not run). Why it matters: the pin cannot move until bridge.lua
  learns the new name, and until then the calc stays on v0.23.1, whose
  game data predates 1.0. The guard works; the gap is that nothing makes
  anyone act before launch week.
- F2. The release check is off while HALT exists. The docs watch runs
  before the HALT return (tools/al_loop.py:1547-1551); the drift call sits
  inside the tick body (:1471), which a HALTed tick never reaches. HALT
  dates from 2026-11-17 17:43 local and stays for the ultraplan
  (docs/plan/README.md:69-72); the last drift check ran at 10:03 that day.
  Why it matters: the one signal that starts the pin work is blind through
  the 1.0 window unless HALT is lifted first.
- F3. Every trial of a data-carrying release goes static-red for a
  mechanical reason. `candidate()` moves only the `pob2` block
  (tools/tc_drift.py:323-332); the static subset includes the hash check of
  src/Data/TradeSiteStats.lua against `pob2_files`
  (tests/test_tc_pob_drift_guard.py:150-166). That file changed in 2
  commits since the pin and in 13 commits between 2026-06-03 and
  2026-07-11, so 7 of the 8 releases from v0.18.0 to v0.23.1 would have
  failed it. The file still parses (1857 rows on dev, 1846 at the pin; the
  pin hash was reproduced from git). Why it matters: the unattended
  verdict cannot be green, so it carries no signal, and a session cannot
  fix the candidate by hand because `trial` regenerates it (:432-438).
- F4. The live gate is tied to one PoB version. The GUI reference in the
  sidecar (`Cache\tc_bridge\gui_expected.json`, tests/tc_live_util.py:20-36)
  says `"pob": "v0.23.1"` and holds 17 values read from a screenshot of
  that GUI. Live tests compare the candidate's numbers with them at 0.1
  percent (tests/test_tc_bridge.py:300-302,
  tests/test_tc_pob_drift_guard.py:137-138). A release that rebalances
  anything the reference build uses turns the live trial red and `apply`
  refuses (tools/tc_drift.py:463-465). A new GUI reading means a visible
  PoB window on the dev host. dev also raises PoB's JIT trace limit from
  4000 to 20000 (src/Launch.lua), so the decision 0028 budgets need a
  re-measure.
- F5. Release notes do not show API drift. None of the last 10 release
  notes mentions headless use, XML, the Lua runtime or a breaking change
  (PB-REL). Only file contents do, and reading them is cheap: 9 source
  files answer all 23 guard rows. `trial` accepts release tags only
  (tools/tc_drift.py:73, :157-158), so dev and beta cannot be rehearsed.
  beta is force-pushed every Friday 00:00 UTC by a scheduled workflow.
- F6. Cadence is bursty and each trial is heavy. 34 releases in 557 days;
  three gaps over 90 days (128, 91, 136) and a current gap of 112 days.
  After 0.5.0 (2026-05-29, P05) the first release came 1 day later and 11
  releases landed within 59 days (PB-REF tag dates). A trial downloads
  780 MB and leaves about 0.8 GB (390 MB archive, 435 MB tree) per tag in
  `Cache\pob2\`; nothing prunes old candidates. A pin move also makes each
  calc user fetch 390 MB again, because the checkout path is derived from
  the pin (server/al/theorycraft/bridge.py:69-80, :93-94).
- F7. Archive byte stability is a notice promise, not a guarantee. GitHub
  does not guarantee checksums of generated source archives and points to
  release assets for that (GH-A2); its 2023 commitment kept zip and tar
  stable for at least one year (to 2024-02-21) and promises six months of
  notice before a format change (GH-A1). The PoB and LuaJIT pins use
  generated archives; WinLibs is a release asset. A generator change would
  move every commit archive at once, so the 1.2 MB LuaJIT archive is a
  faithful canary for the 390 MB one. The archive host answers conditional
  requests with 304 on a stable ETag; what that ETag is derived from is
  UNVERIFIED.
- F8. The API quota is shared and avoidable. Anonymous api.github.com
  calls are capped at 60 per hour per address (WL-API headers); TC-DRIFT
  uses that API (tools/tc_drift.py:53-54). The git ref advertisement
  answers the same questions without a quota: 688 bytes for the tree
  repository, 30 KB for LuaJIT, 451 KB for PoB-PoE2.
- F9. LuaJIT version skew, and a toolchain that is used once. The pinned
  PoB archive ships its own 64-bit LuaJIT DLL whose version string reads
  2.1.1784580905; AshLight runs PoB under 2.1.1794386141, about 113 days
  newer. The calc footprint on disk is about 2 GB, of which the toolchain
  is about 1.2 GB (947 MB tree, 276 MB archive), needed only to build one
  exe.
- F10. repoe-fork: fast, automated, volatile. The data repository commits
  "Version" and "Export" per game client version: 0.5.5.5, .7, .8, .9 and
  .10 between 2026-10-28 and 2026-11-18 (RF-DATA). The exporter code
  changed on 6 of the last 7 days (RF-CODE). Its README warns that file
  formats can change at any time, which research 0011 had left unverified
  (RF-README). Licence
  as in research 0011: MIT code, data stated to be GGG-owned (RF-LIC).
  Pages sends ETag, Last-Modified and a 600 s cache lifetime; the ETag
  encodes deploy time and size, so each redeploy forces a full download.
- F11. The decision 0037 fallback now meets its own reversal condition.
  Upstream commit 21f4f6d1 (2026-11-18 05:13 UTC) adds a second lookup
  with the bracket markup reduced to its shown text (RF-FIX, RF-ISSUE);
  the deploy followed 30 minutes later. Measured with
  server/al/tradestats.py `build_index` and `coverage` on both files:
  entries with `trade_stats` 292 -> 1851 of 10759; explicit index 238 ->
  1543; default weights mapped by repoe-fork alone 11 of 39 -> 39 of 39.
  Against the pinned PoB file: 1540 shared keys, 0 conflicts, 306 keys
  only in PoB, 3 only in repoe-fork. The amendment's condition "repoe-fork
  gains full coverage" holds for the 39 default weights, the yardstick it
  used. Why it matters: hosts without the calc component get all default
  filters after a refresh, and the fallback is what causes F3.
- F12. Two of six files are fetched for nothing. mods.json and stats.json
  are 27.9 MB of the 48.2 MB set (58 percent), and no module reads them
  (server/al/theorycraft/snapshot.py:74, :76).
- F13. The snapshot has no shape check and no refresh trigger. Any valid
  JSON replaces the cached file (snapshot.py:188-200); the hot-reload
  guard checks size, validity and top-level type only
  (server/al/hotreload.py:91-102), so a file with renamed fields loads as
  an empty table. The Checks row says "Present" until the file is 60 days
  old (server/al/diag.py:34, :158-171). Only scripts/build.ps1 refreshes.
  F11 shows the cost: a 6-fold content change sits upstream until the next
  build.
- F14. GGG tree export: stable shape, risky branch. 7 commits since
  2026-05-26; tags exist only for 0.4.0, 0.5.0, 0.5.1 and 0.5.2, the head
  0.5.5 is untagged (GT-REF, GT-FEED). The current file parses fully with
  treedata.py: 5152 nodes, 240 without a string id, 669 ascendancy nodes,
  12 classes, 23 named ascendancies, as in research 0014. "0.5.0 Preview"
  was pushed 2026-05-26 04:48 UTC, 3.6 days before the 0.5.0 launch. The
  snapshot follows `main` (snapshot.py:66-67) and keeps one file, so a 1.0
  preview would replace the live tree around 2026-12-07. GGG lists this
  repository as its one official data export for PoE2 (GGG-DATA). On the
  dev host the tree is not cached at all: web data is on but no contact is
  set, so the Build view has no node names and a `.build` export has no
  passives.
- F15. The ascendancy table is behind GGG's own data. The export names
  Abyssal Lich, Spirit Walker and Martial Artist;
  server/al/theorycraft/charjson.py:39-50 has none of them. 23 named plus
  the 3 announced for 1.0 equals the announced total of 26 (NB), so these
  are live names. `class_fits` (server/al/theorycraft/buildlive.py:34-43)
  then reports a wrong-class alert when such a character plays a build
  saved without an ascendancy.
- F16. On the dev host the calc is installed but off: the stamp says
  ready, yet config/local.json carries no `tc_calc`, so
  `tc_calc_enabled` is false (server/al/core.py:553-555). The pin is
  exercised by tests, not by play.
- F17. Small defects. Decision 0004 has two "Pin log" headings
  (docs/decisions/0004-scope-theorycraft.md:108, :129). The cached
  world_areas file has 24 areas with act 6: the 23 interlude areas and one
  placeholder; what 1.0 does with them is UNVERIFIED.
- F18. What 1.0 breaks, in order, and what the runbook covers. Around
  2026-12-07: a preview tree on `main` (F14). 2026-12-11: the game.
  Within about a day of each client version: a repoe-fork export (F10),
  now with Acts 5-6 areas, about 200 new base types and a reworked passive
  tree (NB). Then the first PoB release, 1 day after 0.5.0 last time (0 to
  4 days after earlier patches; those patch dates were not re-checked
  today), followed by a burst (F6); it carries the reshaped headless entry
  (F1) and new trade data (F3). The runbook and UTIL-1.0-POST cover the
  patch notes, the log survey, area-id prefixes, the world_areas refresh,
  zone notes, ascendancy names, the tree refresh with id_match, the
  poe.ninja league and the pin bump (docs/ops/1.0-launch-runbook.md:37-174,
  ROADMAP.md:530-551). They do not cover the eight items listed in R7.

## Recommendations

Ranked, best first. ROADMAP row names are proposals.

- R1 (TC-BRIDGE-NEXT). Action: make `pob_main()` also accept the global
  `__mainObject__`, and let the 3 failing guard rows accept either shape.
  Impact: H; without it the pin cannot move to any 1.0-era release.
  Effort: S. Risk: low; the old paths stay. ToS check: no floor rule
  touched; AshLight's own Lua run under the pinned subprocess, inputs stay
  pasted build text and hotkey-read item text (decision 0004). Depends on:
  nothing. Files likely touched: server/al/theorycraft/bridge.lua,
  tests/test_tc_pob_drift_guard.py. Acceptance test: the 23 patterns pass
  on the installed pin and on the files at the beta head (a scratch read,
  as in this note, or R3 b); the live tests stay green on the pin; the
  fake-bridge tests stay green. ZERO-CLICK: nothing for the player; the
  calc keeps working across the pin move.
- R2 (TC-DRIFT-HALT). Action: run the drift check and its static trial in
  front of the HALT return, next to the docs watch. Impact: H for the 1.0
  window. Effort: S. Risk: low; it writes no tracked file and starts no
  lane, but a new tag starts a 780 MB background download, so run that
  child at below-normal priority. ToS check: public web data clause; one
  anonymous read of a public repository API with the truthful User-Agent,
  no cookie. Depends on: a dated amendment to decision 0025 (same
  reasoning as decision 0044 item 6). Files likely touched:
  tools/al_loop.py, tools/tc_drift.py, tests/test_al_loop.py,
  docs/decisions/0025-tc-drift.md. Acceptance test: a HALTed tick with a
  due check updates ops/runtime/tc_drift.json. ZERO-CLICK: the tick does
  it.
- R3 (TC-DRIFT-TRIAL-FIX). Action: make a trial able to end green: (a)
  re-hash `pob2_files` from the extracted candidate after setup, unless R4
  removes the block; (b) add `trial --ref <branch or commit>` for dev and
  beta, static by default, never accepted by `apply`; (c) key the GUI
  reference by tag: compare numbers only for the same tag, otherwise
  report per-key deltas against the previous pin and require a recorded
  reference or a session's written acceptance; (d) prune candidates other
  than the pin and the newest. Impact: H. Effort: M. Risk: medium; (c)
  changes what live-green means and needs an adjudicated amendment to
  decisions 0025 and 0028. ToS check: none touched; build-time dev tooling
  on public repository files; candidate Lua still runs only on the manual
  trigger. Depends on: R1 for a green rehearsal; R4 decides (a). Files
  likely touched: tools/tc_drift.py, tests/test_tc_drift.py,
  tests/tc_live_util.py, tests/test_tc_bridge.py. Acceptance test: fakes
  prove (a) to (d); a rehearsal against beta reports static-green after
  R1. ZERO-CLICK: static tier unattended; the live tier stays manual by
  decision 0025.
- R4 (MATH-TRADESTAT-RETIRE). Action: have an adjudicator retire the PoB
  TradeSiteStats fallback, since its reversal condition is met (F11).
  Impact: M; removes a hash pin, the cause of F3, and a second relay of
  trade-site data. Effort: S. Risk: 306 PoB-only keys lose filters for
  user-edited weights; repoe-fork could regress, which the R8 coverage
  count would show. ToS check: narrows the surface; still no trade
  endpoint call (decision 0017). Depends on: a snapshot refresh to the
  2026-11-18 export or newer. Files likely touched: config/tc_pins.json,
  server/al/tradestats.py, server/al/theorycraft/datacredit.py,
  tests/test_tc_pob_drift_guard.py, tests/test_math_tradestat_pob.py,
  docs/decisions/0037-trade-stat-ids-source.md. Acceptance test: with the
  refreshed cache and no calc component, coverage of the default weights
  is 39 of 39. ZERO-CLICK: the link gains its filters with no action.
- R5 (WATCH-UPSTREAM). Action: build the watchers below as one stdlib
  tool on the dev loop host, called before the HALT return, with a state
  file under ops/runtime and one tick line per change. Impact: M. Effort:
  M. Risk: low; about 5 reads a day. ToS check: public web data clause;
  public repository pages and files only, truthful User-Agent, no cookie,
  no token; dev tooling, never in the player's core (as decisions 0025 and
  0044). Depends on: note 0058 for the shared watcher shape. Files likely
  touched: a new tools/upstream_watch.py, tools/al_loop.py, tests.
  Acceptance test: fake fetches drive every "on change" branch; a rate
  limit reply moves the next check out. ZERO-CLICK: unattended.
  - W1 PoB release. Watch the newest release tag and the `master` head;
    use the ref advertisement when the API is rate limited. Daily; twice
    daily 2026-12-10 to 2026-12-24. On change: the decision 0025 flow,
    then a HOLD line or a pin commit.
  - W2 PoB next release. Watch the `beta` head; read the 9 guarded files
    at that commit and run the static patterns. Weekly, after Friday 00:00
    UTC. On red: file or refresh TC-BRIDGE-NEXT with the failing rows.
  - W3 Archive canary. Re-download and hash the pinned LuaJIT archive (1.2
    MB); record the three archive ETags as a hint only. Weekly. On
    mismatch: decision 0018 "Reverses if" (git checkout verified by tree
    hash); file a row; setup keeps refusing.
  - W4 WinLibs asset. One API read of the pinned release: size and digest
    equal the pin, the .zip still exists. Weekly. On change: decision 0027
    item 4, the row goes BLOCKED, never a silent re-pin.
  - W5 LuaJIT head. Compare the v2.1 head with the pin. Monthly. On
    change: nothing alone; note it in the next HOLD line.
  - W6 repoe-fork. Watch the newest "Version" or "Export" title of the
    data repository and Last-Modified per file; after a fetch run the R8
    probes and the coverage count. Daily. On a probe failure: keep the
    last good file and file a row citing decision 0009, 0020 or 0037.
  - W7 GGG tree export. Watch the `main` head and its newest commit title.
    Daily; twice daily from 2026-12-05. On a "Preview" title: note it for
    UTIL-1.0-POST step 7 and do not treat it as live; on a release title:
    refresh and run id_match on the saved builds.
  - W8 GGG Data Exports page. Already hashed daily under decision 0044;
    add a topic tag so a new export or a licence line files a row and
    re-opens decision 0009 item 3.
- R6 (DATA-TREE-HOLD). Action: keep the previous tree file when a new one
  arrives and resolve each build against the cached tree with the highest
  id_match share. Impact: M; removes the preview hazard and helps players
  who keep a 0.5 build after 1.0. Effort: M. Risk: low; two 5 MB files.
  ToS check: GGG's own Data Exports source, fetch-only, nothing bundled
  (decision 0009 item 3). Depends on: nothing; wanted before 2026-12-07.
  Files likely touched: server/al/theorycraft/snapshot.py, treedata.py,
  store.py, buildfile.py, tests/test_tc_tree.py, tests/test_tc_tree_ids.py.
  Acceptance test: with a foreign-version tree as the newest file, a build
  still gets names and `.build` ids from the older file. ZERO-CLICK: the
  choice is made per build with no setting.
- R7 (DOC-1.0-RUNBOOK-2). Action: add to the runbook and UTIL-1.0-POST:
  (1) R1 before the first pin move; (2) re-read `pob2_files` or apply R4;
  (3) a new GUI reference and the decision 0028 budgets per pin move; (4)
  a real-export fixture from the 1.0-era PoB, whose builds save in a
  stable element and attribute order (decision 0021); (5) Acts 5-6 entries
  and interlude removal in server/al/data/zone_guide.json (decision 0043);
  (6) boss hints for Acts 5-6 in server/al/campaign.py (decision 0039);
  (7) a base_items check, as about 200 base types are announced (NB); (8)
  the preview-tree rule of R6. Impact: M. Effort: S. Risk: none. ToS
  check: documentation only; step (5) repeats the own-words rule. Depends
  on: R1, R4, R6 for wording. Files likely touched:
  docs/ops/1.0-launch-runbook.md, ROADMAP.md. Acceptance test: each of the
  8 items has a section with files, commands and a read-back. ZERO-CLICK:
  keeps launch day mechanical.
- R8 (TC-SNAP-PROBE). Action: probe each fetched file before it replaces
  the cached one (top-level type, a minimum entry count, the fields its
  reader uses, and for stat_translations the default-weight coverage);
  keep the old file on failure; show one Checks row per source. Impact: M.
  Effort: M. Risk: a probe that is too strict blocks a good file; keep to
  fields the readers need. ToS check: none touched; local validation of
  public files already allowed by decision 0009. Depends on: nothing.
  Files likely touched: server/al/theorycraft/snapshot.py,
  server/al/diag.py, server/al/core.py, tests/test_tc_snap.py,
  tests/test_diag_self.py. Acceptance test: a wrong-shape body leaves the
  cache untouched and the row names the source. ZERO-CLICK: at each build.
- R9 (UTIL-ASC-FROM-TREE). Action: read the class to ascendancy map from
  the cached tree export first, keep the built-in table as the fallback,
  and add the 3 missing names now. Impact: M; ends the false alert of F15
  and makes runbook step 6 automatic. Effort: S. Risk: low. ToS check:
  names from GGG's published export read from the local cache; nothing
  new bundled. Depends on: a cached tree (Q1). Files likely touched:
  server/al/theorycraft/treedata.py, charjson.py, buildlive.py,
  tests/test_build_live.py, tests/test_util_10_ready.py. Acceptance test:
  with a synthetic tree naming a new ascendancy, `class_fits` knows its
  class with no code change. ZERO-CLICK: follows the tree file.
- R10 (DIAG-DATA-AGE). Action: when the log names a campaign or map area
  id that the cached world_areas file lacks, show a Checks row "Game data
  is older than your game" with the build step as the fix. Impact: M; a
  stale snapshot shows on day one, not after 60 days. Effort: S. Risk:
  a false row for an id the export never lists; limit it to campaign and
  map ids. ToS check: reads only the opt-in Client.txt and the local
  cache; no fetch. Depends on: nothing. Files likely touched:
  server/al/acts.py, server/al/core.py, server/al/diag.py,
  tests/test_diag_self.py. Acceptance test: a replayed log with an unknown
  campaign id raises the row; a hideout id does not. ZERO-CLICK: shown by
  itself; the refresh is one build step (Q2).
- R11 (TC-SNAP-TRIM). Action: drop `mods` and `stats` from the snapshot
  until a reader exists. Impact: L-M; 27.9 MB less per refresh per user.
  Effort: S. Risk: none; decision 0009 item 2 permits the files, it does
  not require them. ToS check: fewer requests to a community host.
  Depends on: nothing. Files likely touched:
  server/al/theorycraft/snapshot.py, tests/test_tc_snap.py. Acceptance
  test: a fresh snapshot holds four files and the manifest lists four.
  ZERO-CLICK: unchanged.
- R12 (TC-PIN-POLICY). Action: write the pin policy into decision 0018:
  at most one PoB pin move per game patch cycle unless a release changes
  a reference output; LuaJIT moves only with a PoB move; the toolchain
  tree and archive are removed after a verified build; the update flow of
  note 0052 re-runs the calc setup when the pin digest changed. Impact: L;
  saves about 1.2 GB per calc user and repeated 390 MB fetches. Effort: S.
  Risk: a later rebuild fetches 276 MB again. ToS check: none touched.
  Depends on: R3. Files likely touched: docs/decisions/0018-tc-pin.md,
  tools/tc_pin.py, tests/test_tc_pin.py. Acceptance test: after a ready
  setup the toolchain folder is gone and a re-run is still a no-op.
  ZERO-CLICK: setup cleans up by itself.

## Cut or merge

- Cut: the `mods` and `stats` snapshot files (R11).
- Cut: the PoB TradeSiteStats fallback and its `pob2_files` pin (R4).
- Cut: the toolchain tree after the one build it serves (R12).
- Merge: the PoB release check, the docs watch and W2 to W8 into one
  upstream watcher with one state file and one tick section (R5).
- Merge: the duplicate "Pin log" sections of decision 0004 (F17).

## Rejected

- A core run-time fetch of repoe-fork or tree files. Against decision 0009
  item 2; its reversal conditions are not met by evidence.
- A bundled tree, zone or ascendancy snapshot for an offline first run.
  Against decision 0009 item 1.
- Reading the game's own data files to export data ourselves and skip the
  upstream lag. Outside the floor: AshLight reads only Client.txt, the
  clipboard or screen per press, and public web data.
- Checking or filling trade stat ids from the trade site. Outside the
  floor (trade endpoints are never called) and decision 0017.
- Committing the pin from the detached trial, or running candidate Lua
  unattended by default. Against decision 0025 and its amendment; neither
  reversal condition is met.
- Pinning PoB's dev or beta branch for players. Decision 0018 pins a
  release; unreleased code would reach players.
- A stored GitHub token for a higher quota. Not needed (F8), and a stored
  secret for a read-only check is a cost without a gain.
- poe2db or wiki text for Acts 5-6 on launch day. Against decision 0009
  item 4.

## Open questions

- Q1 (adjudicator, or an operator act). The tree fetch needs a contact
  (decision 0015 item 2), yet the file is served by GitHub, not by GGG's
  API, and its README only points at the OAuth docs. Either the gate is
  narrowed to GGG-hosted requests, or the operator sets `contact` on the
  dev host. Until then R6 and R9 have no tree to work with there.
- Q2 (adjudicator). Who refreshes the snapshot after a game patch?
  Decision 0009 item 2 names scripts/build.ps1 only. The options are the
  launcher, the dev loop, or the build step alone plus R10.
- Q3 (adjudicator). The pinned PoB archive carries a 64-bit LuaJIT DLL
  (616448 bytes). Driving it through ctypes from a helper process would
  remove the LuaJIT pin, the toolchain pin and the C build. Does a binary
  inside a hash-pinned archive satisfy the "hashed binary" conditions of
  decisions 0018 and 0027? Not executed for this note.
- Q4 (operator). Is the calc meant to stay off on the dev host (F16)?
- UNVERIFIED: the 1.0 area-id prefixes and whether interlude ids leave the
  campaign; the date of the 1.0 patch notes; the tag form of the first
  1.0-era PoB release; whether `loadBuildFromXML` and the output keys hold
  in it (R3 rehearsal answers this); what the archive ETag is derived
  from; the PoB 390 MB archive was not re-downloaded today (its pin was
  recorded from two downloads on 2026-11-17, decision 0018).
