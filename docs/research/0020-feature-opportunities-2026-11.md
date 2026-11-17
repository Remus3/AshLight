# 0020 - Feature opportunities, ranked (Nov 2026)

Date 2026-11-17. Built from 0017 (PoB drift), 0018 (patch / log / policy),
0019 (poe.ninja) and the ToS floor in CLAUDE.md. Ranked by player value
per unit of work, highest first. "Floor" = feasible under the ToS floor
and decisions 0003, 0013-0017. Top rows are filed in ROADMAP.md.

1. Map run tracker (UTIL-MAPRUN). Floor: YES - Client.txt only, already
   opted in; no new read. From `Generating level <N> area "<id>"` plus
   hideout / town `[SCENE]` names: maps run, time per map, maps per hour,
   area level, deaths per map, session totals on the dashboard; one line
   in the overlay status slot. Value: the most-asked endgame stat; zero
   clicks. Risk: endgame area-id prefix UNVERIFIED (verify on the first
   live map, LIVE-1 style fixture) (0018 section 2).
2. Unique prices on the hotkey (PRICE-UNIQUE). Floor: YES - poe.ninja
   documented economy route, same press and opt-in (0015, 0017). Value
   card + listing count + 7-day trend; match on name + baseType (0019).
3. Stackable prices on the hotkey (PRICE-STACKABLES). Floor: YES - more
   exchange overview types (Omens, Essences, Runes, SoulCores, Catalysts,
   ...), one request per type per hour with ETag (0019).
4. PoE2 1.0 readiness (UTIL-1.0-READY). Floor: YES - data and parser
   only. 1.0 on 2026-12-11 adds Acts 5-6, Duelist / Shadow, a new league
   (0018): act prefixes, class names, league rollover, refreshed repoe-fork
   snapshot, debug-sink review of new system lines in the first 1.0 log.
   Value: nothing breaks on launch day, when free-to-play brings new users.
5. In-game Build Planner export (TC-BUILDFILE). Floor: YES, ONLY as a
   user-saved file (adjudicator ruling, 0018 section 3): the dashboard
   offers "Save .build" for the loaded PoB build; the player places it in
   their BuildPlanner folder; AshLight never writes there. GGG documents
   the format for tools ("created manually or by tools"). Value: the
   game's own build guide shows the player's PoB plan in-game. Risk: the
   format is "Version 1 (Experimental)"; passive ids are strings like
   `strength89`, so the mapping from PoB / GGG export numeric ids is
   UNVERIFIED (research task inside the row).
6. Price movers panel (UTIL-MOVERS). Floor: YES - reuses the cached
   overviews, no extra request rate. Value: modest (what to sell now).
7. Boss reached markers. Floor: YES (log only) but LOW confidence: only
   NPC dialogue lines exist, no kill line (0018). Not filed; revisit after
   a live boss log (LIVE-1).
8. Exchange ratio history from GGG's public Currency Exchange API (TC-CURX).
   Floor: NO for now - adjudicator ruling: needs an AshLight public OAuth
   client (registration closed). Filed BLOCKED on TC-OAUTH-REG.
9. Meta builds / popular items from poe.ninja builds. Floor: NO -
   poe.ninja excludes builds / character endpoints from third-party use
   (0019). Not filed.
10. Loot / currency drop tracker. Floor: NO - Client.txt logs no drops
    (0018), and continuous screen capture is forbidden (decision 0003);
    the only permitted path is a per-press read. Not filed.

Also for the math lane: TC-DRIFT HOLD (no PoB-PoE2 release after v0.23.1;
dev 109 commits ahead with 0.5.5 data and a HeadlessWrapper cache change,
0017).

## Sources

- docs/research/0017-pob2-drift-2026-11.md (2026-11-17)
- docs/research/0018-poe2-state-2026-11.md (2026-11-17)
- docs/research/0019-poe-ninja-poe2-contract.md (2026-11-17)
- https://www.pathofexile.com/developer/docs/game (accessed 2026-11-17)
- https://poe.ninja/docs/api (accessed 2026-11-17)
