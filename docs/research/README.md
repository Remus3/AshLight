# Research index

One file per topic, numbered `NNNN-<topic>.md`. Every factual claim cites a
source URL with its access date; anything not confirmed is marked
UNVERIFIED. New research appends a new number (deep dives use
`NNNN-deep-dive-<date>.md`); an update to a topic edits its file and adds a
dated line to that file's "Sources". Studying another tool never means copying
its code (license notes: 0006).

- 0001 GGG third-party tool policy - what GGG permits and forbids, verified
  quotes of the developer docs, binding design consequences
  ([0001-ggg-tool-policy.md](0001-ggg-tool-policy.md))
- 0002 Client.txt log format and events - location, prefix, zone / level /
  death / whisper / chat lines, localization, event schema
  ([0002-client-log.md](0002-client-log.md))
- 0003 Item clipboard text - Ctrl+C / Ctrl+Alt+C sections, mod tags, stat-id
  mapping, parser design ([0003-item-clipboard.md](0003-item-clipboard.md))
- 0004 Trade API and rate limits - trade2 endpoints, X-Rate-Limit headers,
  OAuth and User-Agent rules ([0004-trade-api.md](0004-trade-api.md))
- 0005 Data sources - poe.ninja, poe2db, poe2wiki, RePoE exports, licenses
  and caching ([0005-data-sources.md](0005-data-sources.md))
- 0006 Existing companion tools - features, stacks, licenses, pitfalls
  ([0006-existing-tools.md](0006-existing-tools.md))
- 0007 Overlay technology on Windows - layered windows, click-through,
  fullscreen modes, Electron / Tauri / WPF / Qt / native, budgets
  ([0007-overlay-tech.md](0007-overlay-tech.md))
- 0008 Second-screen dashboard technology - SSE vs WebSocket, security,
  glanceable UI ([0008-dashboard-tech.md](0008-dashboard-tech.md))
- 0009 Name review - AshLight collisions, GGG proper-noun check, PoE tool
  naming, fallback shortlist ([0009-name-review.md](0009-name-review.md))
- 0010 Theorycraft scope - PoB2 license / headless / build codes, GGG OAuth
  character import, game data licenses, upgrade search, tools, name fit
  ([0010-theorycraft-scope.md](0010-theorycraft-scope.md))
- 0011 Data license verification - repoe-fork, GGG exports, PoB2, poe2db,
  wiki, poe.ninja, GGG API User-Agent, with URLs and dates
  ([0011-data-license-verification.md](0011-data-license-verification.md))
- 0012 PoE2 graphics options and PC specs - option labels, official
  minimum / recommended specs, what costs the most FPS (GFX-ADVISOR)
  ([0012-poe2-graphics.md](0012-poe2-graphics.md))
- 0013 Web endpoint verification - live poe.ninja overview shape, pobb.in and
  pastebin raw paths, rate and terms checks (DATA-NINJA-VERIFY, TC-URL-VERIFY)
  ([0013-web-endpoint-verify.md](0013-web-endpoint-verify.md))
- 0014 GGG PoE2 tree export shape - real data.json keys vs the treedata.py
  reader; two mismatches (DATA-TREE-SHAPE, DATA-TREE-FIX)
  ([0014-tree-export-shape.md](0014-tree-export-shape.md))
- 0015 PoB2 spec node ids vs GGG tree export skill ids - identical id space
  (PoB2 source plus a 4914-node cross-check); id_match guard (DATA-TREE-IDS)
  ([0015-pob2-tree-node-ids.md](0015-pob2-tree-node-ids.md))
- 0016 trade2 search link form - `?q=<JSON>` built by community tools,
  rarity filter path, undocumented by GGG (PRICE-TRADE-LINK)
  ([0016-trade2-search-link.md](0016-trade2-search-link.md))
- 0017 PoB-PoE2 drift check Nov 2026 - no release after v0.23.1, dev 109
  ahead, HeadlessWrapper and .build export deltas; pin HOLD (TC-DRIFT)
  ([0017-pob2-drift-2026-11.md](0017-pob2-drift-2026-11.md))
- 0018 PoE2 state Nov 2026 - patch 0.5.5f, 1.0 on 2026-12-11, Client.txt
  deltas (none new), policy unchanged, GGG public Currency Exchange and
  .build format with adjudicator rulings
  ([0018-poe2-state-2026-11.md](0018-poe2-state-2026-11.md))
- 0019 poe.ninja PoE2 contract - documented economy routes, unique and
  exchange types, cache / UA / no-SLA terms, excluded builds endpoints
  ([0019-poe-ninja-poe2-contract.md](0019-poe-ninja-poe2-contract.md))
- 0020 Feature opportunities Nov 2026 - ten features ranked, floor
  yes / no with reasons, filed rows
  ([0020-feature-opportunities-2026-11.md](0020-feature-opportunities-2026-11.md))
- 0021 PoE2 1.0 readiness - announced acts, classes, Conquerors of
  Wraeclast league, league end, impact and the UTIL-1.0-POST checklist
  ([0021-poe2-1-0-readiness.md](0021-poe2-1-0-readiness.md))
- 0022 Loot filters - GGG filter format and folder, NeverSink MIT,
  Account Item Filters API, adjudicator ruling: user-saved snippet only
  (UTIL-FILTER) ([0022-loot-filters.md](0022-loot-filters.md))
- 0023 Player-value gaps Nov 2026 - companion survey, five features ranked
  under the floor, three filed
  ([0023-player-value-gaps-2026-11.md](0023-player-value-gaps-2026-11.md))
- 0024 Policy / API recheck to 2026-11-17 - no floor change in 30 days
  ([0024-policy-api-recheck-2026-11.md](0024-policy-api-recheck-2026-11.md))
- 0025 PoE2 search box (250 chars since 0.5.0, regex, `|`, `!`) and item
  filter syntax; snapshot checks of zone notes and waystone rules
  ([0025-search-box-and-filter-syntax.md](0025-search-box-and-filter-syntax.md))
- 0026 Deep dive 2026-11-17 - policy / APIs / patch notes / tools, no floor
  change; Exile-UI disabled screen-read automation after the 3.30.0 wording
  ([0026-deep-dive-20261117.md](0026-deep-dive-20261117.md))
- 0027 The game's `.build` file: GGG's documented Build object, passive
  ids = GGG tree export `id` (all 6 example ids found), PoB PR #2432 ideas
  only ([0027-build-file-passive-ids.md](0027-build-file-passive-ids.md))
- 0028 Next wave (Nov 2026): build health from PoB PlayerStat, look-for-
  next per slot, under-level warning, run history, price watch, settings
  export; phone / LAN is an operator decision
  ([0028-next-wave-2026-11.md](0028-next-wave-2026-11.md))
- 0029 Policy wording watch - overlay / macro wording diffed against the
  0001 quotes per changelog entry and at 1.0; baseline UNCHANGED 2026-11-17, 1.0
  re-read pending
  ([0029-policy-wording-watch.md](0029-policy-wording-watch.md))
- 0030 Trade stat ids source - no GGG source; repoe-fork stat_translations
  `trade_stats` (already snapshotted) chosen, PoB tables same provenance
  ([0030-trade-stat-ids-source.md](0030-trade-stat-ids-source.md))
- 0031 Third wave (Nov 2026): skill / ailment DPS split from PoB
  FullDPSSkill, defence breakdown + PoB's remaining warnings, waystone
  reward summary, campaign level checks; craft slots and atlas progress
  listed ([0031-wave-3-2026-11.md](0031-wave-3-2026-11.md))
- 0032 Fourth wave (Nov 2026): self-diagnostics card, non-English client
  detector (what Client.txt lines are language dependent), first-hours
  hints for F2P newcomers, map level ladder; atlas progress and locale
  pattern packs listed ([0032-wave-4-2026-11.md](0032-wave-4-2026-11.md))
- 0033 Live character data beyond Client.txt - GGG OAuth public client
  (PKCE, loopback, account:characters: PoE2 equipment / skills /
  passives, no backpack; registration closed); PoB2, poe.ninja, Steam,
  game files ruled out; campaign pathing from world_areas
  ([0033-live-character-data.md](0033-live-character-data.md))
- 0034 Zone guide facts - lasting campaign rewards per zone, main-path
  order, layout tendencies, map completion; facts only, own words
  ([0034-zone-guide-facts.md](0034-zone-guide-facts.md))
- 0035 Data sources: GGG developer platform (OAuth, API Reference, Data
  Exports) - GGG platform as of 2026-11-18: registration closed (second
  closure, reopening guessed early 2027), public-client PKCE with a 10 h
  access token and a 7-day refresh token, the PoE2 endpoints and fields,
  tree export unlicensed. Re-check of research 0033; charjson behind the
  current item shape (R1)
  ([0035-data-sources-ggg-api.md](0035-data-sources-ggg-api.md))
- 0036 poe.ninja as the PoE2 price source: contract, drift, watch design -
  poe.ninja contract as lines (24 URL shapes, 556 GETs a day max), ranked
  drift risks, 12 recommendations and a three-layer shape watch for 0058.
  Verified 2026-11-18
  ([0036-data-sources-poe-ninja.md](0036-data-sources-poe-ninja.md))
- 0037 Data sources: PoB-PoE2, LuaJIT / WinLibs, repoe-fork, GGG tree
  export - upstream calc and data sources: what is pinned vs current,
  drift risk, and what 1.0 breaks. Next PoB release breaks the bridge;
  TC-DRIFT gaps; watcher inputs W1-W8
  ([0037-data-sources-pob-repoe-tree.md](0037-data-sources-pob-repoe-tree.md))
- 0038 Features review: player value, gaps, cut or merge - covers 35
  player-facing features with value, surface, use per hour, upkeep and
  live proof. Ranks 9 gaps inside the ToS floor (worn-gear baseline,
  overlay zone and act cards, contact field, live capture, one guide file
  for 1.0) and lists what to merge, cut, freeze, promote and demote
  ([0038-features-review.md](0038-features-review.md))
- 0039 Utilities review: what earns its place, what to cut, merge, hide or
  automate - scores 15 utilities and all 18 config keys: keep 5, fix 4,
  merge 3, retire 2 on a trigger, rebuild 1 (autostart). Ranks 13 fixes
  led by in-app contact, league and hotkey controls and snapshot delivery
  ([0039-utilities-review.md](0039-utilities-review.md))
- 0040 Visual design review (dashboard, client window, overlay) - visual
  design against DS 0001: token inventory, luminance maths, 8 ranked
  token/component changes (dark default, Play glance band, stale colour,
  quiet controls). Overlay contrast holds (4.88:1 sampled); PACK
  measurement 15 is a compositing-model error
  ([0040-visual-design-review.md](0040-visual-design-review.md))
- 0041 Typography review (dashboard and overlay) - fonts, sizes, weights,
  numerals and truncation, with measured overlay contrast. Proposes a
  plate-only fade recipe (>= 7:1), 2 overlay sizes, a 6-step dashboard
  token scale, tabular numbers and a larger autoScale
  ([0041-typography-review.md](0041-typography-review.md))
- 0042 Usability review: task walks, heuristic findings, phone view
  options - walks 14 player tasks with step counts and runs an NN/g
  heuristic evaluation: 23 findings, 6 major. Gives 12 ranked fixes
  (truthful web-data switch, build caveat on the verdict, a paste-build
  prompt, a no-dead-end copy pass, a player README) and sets out
  phone-view options P0 to P4 for the operator
  ([0042-usability-review.md](0042-usability-review.md))
- 0043 Glanceability and zero-click audit - interaction inventory (25
  acts) with the furthest floor-safe reduction for each, the scroll and
  tab audit from the evidence pack, and testable glance budgets. Play fits
  with a layout-only change; build load drops to 1 press (R4) or 0 (R3,
  needs a ruling); an item check drops from 5 keys to 3
  ([0043-glanceability-zero-click-audit.md](0043-glanceability-zero-click-audit.md))
- 0044 Accessibility review - WCAG 2.2 AA review of dashboard, desktop
  client and overlay: overlay contrast passes (pack method error), defects
  in Play column focus ring, forced-colours tab state, client keyboard
  zoom, auto-switch focus; 12 ranked fixes led by a CDP a11y test
  ([0044-accessibility-review.md](0044-accessibility-review.md))
- 0045 Security of the local surface - threat model and code audit of the
  127.0.0.1 core (token, Host/Origin, CSP, routes, files, inputs, bridge,
  fetch, hot reload, tasks); 13 findings, 11 ranked fixes, phone-view
  options A/B/C for the operator
  ([0045-security-local-surface.md](0045-security-local-surface.md))
- 0046 Electron hardening and supply chain - Electron shell meets 13 of 20
  checklist items, pin 45.3.3 current (line ends 2027-04-27), npm 13
  packages 0 advisories. Ranked fixes: ELECTRON-WATCH upgrade policy, npm
  lockdown, Node floor 22.12, exe hash pin, shell guards, calc pins
  verified at use, go-public provenance
  ([0046-security-electron-supply-chain.md](0046-security-electron-supply-chain.md))
- 0047 File structure and module boundaries review - maps server/al (72
  modules, 0 cycles), churn and the 9 collision seams. Designs the ledger
  single-writer rule, the ROADMAP parser fix and prune, the state.py text
  split into server/al/text/, the web/ fmt.js and panel registry, and a
  tests naming guard
  ([0047-file-structure-review.md](0047-file-structure-review.md))
- 0048 Performance budgets review (speed, RAM, FPS) - budgets in decisions
  0002, 0024 R7 and 0028 against what the tests actually assert, plus
  measured core, dashboard, overlay and calc costs. Proposes 19 budgets,
  12 ranked fixes, and an OVL-FPS / OVL-BUDGET check that needs only one
  normally played map
  ([0048-performance-budgets-review.md](0048-performance-budgets-review.md))
- 0049 Test suite speed - profile of the 2319-test suite (237 s, 5 files
  hold 60 percent: real git, live calc, floor scan, sleeps), gate log
  analysis, and a wave policy of named-file subsets plus one whole suite
  per merge batch. Verified 2026-11-18
  ([0049-test-suite-speed.md](0049-test-suite-speed.md))
- 0050 Reliability review - 32 failure modes (8 heal, 13 silent, 10
  manual) with code citations, R0-R12 fixes and 28 CI chaos tests. Top: no
  log discovery in test/demo cores (F32), tailer self-heal, client error
  guards, durable writes
  ([0050-reliability-review.md](0050-reliability-review.md))
- 0051 Observability review - logs, Checks, /api/health, dev ledgers
  reviewed; a dead tailer shows healthy, version identifies nothing.
  Ranked plan: masked parse ledger, build stamp, crash records, counters,
  explainer, public report
  ([0051-observability-review.md](0051-observability-review.md))
- 0052 Deployment reference pattern (install, build, release, update,
  uninstall) - the reference app's zip-plus-manifest per-user deployment
  pattern (install, update, rollback, uninstall, release gates), mapped
  onto AshLight's rules, with a gap list for the five scripts and 7 ranked
  recommendations
  ([0052-deployment-reference-pattern.md](0052-deployment-reference-pattern.md))
- 0053 Packaging and release options - how a stranger installs, updates
  and removes AshLight: portable zip with hash-pinned embeddable CPython
  and Electron, no installer framework, unsigned at first. Tag-triggered
  CI release with generated changelog and checksums, in-app update notice
  under web_data, one-click verified update with rollback
  ([0053-packaging-release-options.md](0053-packaging-release-options.md))
- 0054 Competitive review: PoE and PoE2 companion tools (design
  patterns) - design patterns from 30 PoE and PoE2 companion tools in 9 classes:
  what they show, window model, policy posture, first run, notices, player
  complaints. Gives 8 recommendations (setup card, overlay parts chooser,
  off-state lines, town search string, tunable waystone card, update
  wording, player guide, peek key)
  ([0054-competitive-poe-tools.md](0054-competitive-poe-tools.md))
- 0055 Competitive review: other games' companions and overlay platforms
  (patterns) - patterns from overlay platforms, OS notification and watch
  guidance, MOBA companions, parser overlays, sim-racing dashboards,
  subtitle and OSD legibility, and driving glance rules. 8
  recommendations: second-monitor placement, a distance type rule, merging
  repeat trade cards, an in-overlay hotkey hint and glance rules as tests
  ([0055-competitive-companions-overlays.md](0055-competitive-companions-overlays.md))
- 0056 Third-party repo review (ideas only) - ideas from a set of public
  third-party repos that stays anonymous: all of its live data paths fall
  outside the floor. 12 floor-safe recommendations, led by weights stored
  as deltas, a no-build campaign keep check and a hot reload stale-pin
  fix. No code reuse
  ([0056-third-party-repo-review.md](0056-third-party-repo-review.md))
- 0057 Go-public readiness - go-public audit: identity and leak sweeps
  clean over all 404 commits, so full history can be published. Seven
  blockers (guarded pre-push, docs, Windows CI plus the identity guard,
  fresh-clone run, main-only push, NOTICE, security fixes before the
  visibility flip) and the gh repo setup steps
  ([0057-go-public-readiness.md](0057-go-public-readiness.md))
- 0058 No-reminder automation and upstream watchers - contracts of the
  unattended loop (row syntax, BLOCKED, Depends on, done flip, runs cap,
  HALT), 14 watchers with homes and row templates, the 1.0 launch gate,
  screenshot/changelog/docs freshness, and the loop/wave contract.
  Verified 2026-11-18
  ([0058-automation-watchers.md](0058-automation-watchers.md))
- 0060 Operator requests 2026-11-19 - item info popover sources and fields
  (drop rates, NPC prices and disenchant yields have no permitted source;
  poe2db / wiki are CC BY-NC-SA, link only), the Kindler build generator
  within PoB interop, header text, version line and card collapse;
  follow-ups on licence and Kindler detail. Feeds decisions 0081 to 0083
  and docs/plan/10
  ([0060-operator-requests-2026-11-19.md](0060-operator-requests-2026-11-19.md))

## Open research (feeds ROADMAP)

- Verify the PoE2 lines marked UNVERIFIED in 0002 against a live log (LIVE-1).
- Whether PoE2 "Fullscreen" is exclusive (0007); test the overlay in each mode.
- poe2db proper-noun check and a direct USPTO / EUIPO search for "Ashlight"
  before publishing (poe2wiki / poewiki done in 0009: 0 hits).
- 0059 Deep dive 2026-11-19 - offline run (web data off), no floor change, no
  new rows ([0059-deep-dive-20261119.md](0059-deep-dive-20261119.md))
