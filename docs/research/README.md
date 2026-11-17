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

## Open research (feeds ROADMAP)

- Verify the PoE2 lines marked UNVERIFIED in 0002 against a live log (LIVE-1).
- Live trade2 rate-limit values (0004) from a real response's headers.
- Whether PoE2 "Fullscreen" is exclusive (0007); test the overlay in each mode.
- poe2db proper-noun check and a direct USPTO / EUIPO search for "Ashlight"
  before publishing (poe2wiki / poewiki done in 0009: 0 hits).
