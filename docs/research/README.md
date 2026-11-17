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
- 0026 The game's `.build` file: GGG's documented Build object, passive
  ids = GGG tree export `id` (all 6 example ids found), PoB PR #2432 ideas
  only ([0026-build-file-passive-ids.md](0026-build-file-passive-ids.md))

## Open research (feeds ROADMAP)

- Verify the PoE2 lines marked UNVERIFIED in 0002 against a live log (LIVE-1).
- Whether PoE2 "Fullscreen" is exclusive (0007); test the overlay in each mode.
- poe2db proper-noun check and a direct USPTO / EUIPO search for "Ashlight"
  before publishing (poe2wiki / poewiki done in 0009: 0 hits).
