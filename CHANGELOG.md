# Changelog

Every AshLight version, newest first. Generated from docs/releases/<version>.md by `python tools/release.py notes --changelog`; edit those files, never this one.

## [0.2.0-rc.2] - 2026-11-28
<!-- lead: hand-written, kept when the notes are regenerated -->
AshLight 0.2.0-rc.2 is a test version of 0.2.0. It replaces 0.2.0-rc.1, which was never published. AshLight now installs with one line and updates itself. Kindler suggests a build for you, and a new Progression view shows your trees and gems level by level. AshLight's updater only offers full releases, so to try this test version, install it yourself.
<!-- /lead -->

### Added
- Install with one line. AshLight installs for your Windows user only, with no admin rights. It downloads the Python and Electron it needs from their makers and checks each download against a known hash. An uninstall script removes AshLight and keeps your saved data unless you ask it to remove that too.
- AshLight updates itself. While web data is on, it checks for a new full release once a day, downloads it and verifies it. After a 24 hour wait it installs the update the next time AshLight starts. If the new version won't start, AshLight goes back to the old one. To update now, click 'Update now' in Settings. To approve each update yourself, turn on click-only updates.
- 'Start with Windows', off by default, in the tray menu and in Settings. When on, AshLight starts in the tray and the overlay waits for the game.
- Kindler, a build generator. Pick a style (melee, spells, minions or bows) and click Generate. Path of Building scores AshLight's own build plans and shows the best one. The plan runs from act 1 to early maps. It lists skills and supports, when each gem unlocks, passives in order, the ascendancy, and what to look for on each item slot. With 'Follow Play guidance' on, the plan follows your zone and level.
- Choose the build Play follows: the build you pasted, or a Kindler plan.
- Progression view: your passive and ascendancy trees, your skill gems with their supports, and a 'Next up' list. When you level up, AshLight shows it where the item card was. A pasted build with trees for different level ranges switches to the tree for your level.
- When you level up, a card names the gems from your build that you can now use.
- Item info: click an item or gem name to see its base, its price (while web data is on) and where it can be found. Gems also show their level, costs and stats.
- Mark the item you wear: AshLight then compares each checked item with the item you wear first, and your Path of Building plan second.
- With no build loaded, the item check still says keep or vendor for your level.
- Uncut gems: an item check on an uncut gem names the gems in your build that it can become.
- Augments: with the Path of Building calc on, an item check with a free socket names the augment that helps your build most.
- Every campaign zone has a guide line, and you can write your own note for any zone.
- The session summary counts your sales and adds up their listed prices. The total is an estimate.
- 'This is my character' on the Characters card. AshLight then stays on that character and never switches.
- Change your hotkeys in the app. If another program already uses a key, AshLight picks a free one and tells you.
- The overlay shows short cards when you enter a zone and when an act split closes. Until you have used it, it also shows a one-line hint about the item-check key.
- One-click 'Set up the Path of Building calc' button in the desktop app.
- Checks gets a 'Tried in game' list, a report preview before you copy it, a note when the game data is older than the game, and an 'Installed copy' row.
- Screenshots and a four-page player guide on the GitHub project page.

### Changed
- A new Play screen with a fixed layout that does not scroll, and four tabs: Play, Build and items, Run and Settings. Dark by default, with a Theme choice (Dark, Follow Windows, Light).
- In the desktop app, cards on Build and items and on Run can be folded to their title.
- The item check shows its first answer at once, and the Path of Building numbers follow when ready.
- An empty clipboard at the item-check press now says 'Copy the item first'.
- The overlay text is easier to read, and its background can be set from 80 to 100 percent solid.
- When the game wakes, the companion window comes back on your other screen without taking focus.
- The Path of Building calc stops when idle and starts again on your next press, to free memory.
- Prices: AshLight now asks poe.ninja for prices less often. Full releases send no poe.ninja requests at all for now, so an installed copy shows a trade search link instead of prices.

### Fixed
- A dead log reader, core or overlay now starts again by itself, and Stop stops only what was running.
- A changed poe.ninja format no longer clears your prices: AshLight keeps the last good ones.

### Security
- The desktop app's windows are locked down. They can only reach AshLight's own local server and can't open other pages. A few named sites open only in your browser.
- The app checks that it is talking to its own AshLight before it sends anything.
- AshLight's private files are readable only by you.
- The Path of Building calc runs locked down: it can't start programs or write files.
- The desktop app now runs on Electron 45.4.1.

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## [0.2.0-rc.1] - 2026-11-28
<!-- lead: hand-written, kept when the notes are regenerated -->
AshLight 0.2.0-rc.1 is a test version of 0.2.0. AshLight now installs with one line and updates itself. Kindler suggests a build for you, and a new Progression view shows your trees and gems level by level. AshLight's updater only offers full releases, so to try this test version, install it yourself.
<!-- /lead -->

### Added
- Install with one line. AshLight installs for your Windows user only, with no admin rights. It downloads the Python and Electron it needs from their makers and checks each download against a known hash. An uninstall script removes AshLight and keeps your saved data unless you ask it to remove that too.
- AshLight updates itself. While web data is on, it checks for a new full release once a day, downloads it and verifies it. After a 24 hour wait it installs the update the next time AshLight starts. If the new version won't start, AshLight goes back to the old one. To update now, click 'Update now' in Settings. To approve each update yourself, turn on click-only updates.
- 'Start with Windows', off by default, in the tray menu and in Settings. When on, AshLight starts in the tray and the overlay waits for the game.
- Kindler, a build generator. Pick a style (melee, spells, minions or bows) and click Generate. Path of Building scores AshLight's own build plans and shows the best one. The plan runs from act 1 to early maps. It lists skills and supports, when each gem unlocks, passives in order, the ascendancy, and what to look for on each item slot. With 'Follow Play guidance' on, the plan follows your zone and level.
- Choose the build Play follows: the build you pasted, or a Kindler plan.
- Progression view: your passive and ascendancy trees, your skill gems with their supports, and a 'Next up' list. When you level up, AshLight shows it where the item card was. A pasted build with trees for different level ranges switches to the tree for your level.
- When you level up, a card names the gems from your build that you can now use.
- Item info: click an item or gem name to see its base, its price (while web data is on) and where it can be found. Gems also show their level, costs and stats.
- Mark the item you wear: AshLight then compares each checked item with the item you wear first, and your Path of Building plan second.
- With no build loaded, the item check still says keep or vendor for your level.
- Uncut gems: an item check on an uncut gem names the gems in your build that it can become.
- Augments: with the Path of Building calc on, an item check with a free socket names the augment that helps your build most.
- Every campaign zone has a guide line, and you can write your own note for any zone.
- The session summary counts your sales and adds up their listed prices. The total is an estimate.
- 'This is my character' on the Characters card. AshLight then stays on that character and never switches.
- Change your hotkeys in the app. If another program already uses a key, AshLight picks a free one and tells you.
- The overlay shows short cards when you enter a zone and when an act split closes. Until you have used it, it also shows a one-line hint about the item-check key.
- One-click 'Set up the Path of Building calc' button in the desktop app.
- Checks gets a 'Tried in game' list, a report preview before you copy it, a note when the game data is older than the game, and an 'Installed copy' row.
- Screenshots and a four-page player guide on the GitHub project page.

### Changed
- A new Play screen with a fixed layout that does not scroll, and four tabs: Play, Build and items, Run and Settings. Dark by default, with a Theme choice (Dark, Follow Windows, Light).
- In the desktop app, cards on Build and items and on Run can be folded to their title.
- The item check shows its first answer at once, and the Path of Building numbers follow when ready.
- An empty clipboard at the item-check press now says 'Copy the item first'.
- The overlay text is easier to read, and its background can be set from 80 to 100 percent solid.
- When the game wakes, the companion window comes back on your other screen without taking focus.
- The Path of Building calc stops when idle and starts again on your next press, to free memory.
- Prices: AshLight now asks poe.ninja for prices less often. Full releases send no poe.ninja requests at all for now, so an installed copy shows a trade search link instead of prices.

### Fixed
- A dead log reader, core or overlay now starts again by itself, and Stop stops only what was running.
- A changed poe.ninja format no longer clears your prices: AshLight keeps the last good ones.

### Security
- The desktop app's windows are locked down. They can only reach AshLight's own local server and can't open other pages. A few named sites open only in your browser.
- The app checks that it is talking to its own AshLight before it sends anything.
- AshLight's private files are readable only by you.
- The Path of Building calc runs locked down: it can't start programs or write files.
- The desktop app now runs on Electron 45.4.1.

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## [0.1.0] - 2026-11-19
<!-- lead: hand-written, kept when the notes are regenerated -->
AshLight 0.1.0 is the first public version: a live second-screen dashboard and a click-through overlay for Path of Exile 2 that read only the game's Client.txt log, with act and map timers, trade cards, and an item check on a hotkey press that weighs an item against your Path of Building build. Everything runs on your own computer, and web data stays off until you turn it on.
<!-- /lead -->

### Added
- Guarded pre-push, go-public decision, CLAUDE.md hygiene (GP-02)
- A live lane / loop tick writing ops/loop/control/loop_items/*.json mid-suite tripped fleet_test_guard with a false error at a random teardown (TEST-FLAKE)
- Real-browser check of the cards added after audit 0003 (Act times, item check, price / upgrade link, build view) at 320 / 768 / 1440 px, dark, light and forced colours (glance review 0004 U7) (UX-U7)
- Act splits survive a core restart: LIVE-RESUME (decision 0008) also returns the current run's area-generation ids with their line timestamps, so the splits rebuild from Client.txt instead of starting empty and partial (HUD-ACT-RESUME)
- Batch 2 (area-audit) (AREA-AUDIT)
- Walk the first-run path cold (no consent, no config, web data off, no Path of Building calc) on the dashboard and the overlay (UX-FIRSTRUN)
- Rebuild the map runs and death recap at core start from the current game run in Client.txt, as HUD-ACT-RESUME does for act splits (decision 0023 pattern, no persisted state) (UTIL-MAPS-RESUME)
- A magic item's true base type: the name line "Hale Iron Ring of the Bear" keeps its affix words as the base, so the trade / upgrade links searched a type that does not exist (MATH-MAGIC-BASE)
- Pass 2 finding P2-C1 (medium, claim re-opened): TC-BRIDGE was flipped done but its ACCEPT ("outputs on a fixture build match PoB GUI within 0.1 percent") never ran - tests/test_tc_bridge.py live tests skip (no luajit.exe: no compiler on this machine; no gui_expected.json) (AUDIT-TC-BRIDGE-LIVE)
- Stdlib seeded property / fuzz tests (bounded time) for the Client.txt line parser, the item-text parser, the PoB2 share-code codec, the build / character JSON / poe.ninja parsers and the price / snapshot builders: random bytes in mixed encodings, truncations, mutations, extreme numbers, wrong-typed card fields (TEST-FUZZ)
- Run the real Electron overlay on this machine's physical display(s) against a test core fed by tools/synth_client.py; real desktop screenshots (OS screen capture of the desktop, never the game) to verify transparency, click-through and non-focusable window flags, corner position, scaling at the monitor's real DPI, and the About disclaimer; close it by the PID started (UX-REAL-OVERLAY)
- Pass 2 findings P2-M1 (medium), P2-M2, P2-M3 (low); server/al/runs.py was mid-change in UTIL-MAPS-RESUME, so not fixed in pass 2 (AUDIT-MAP-SEED)
- Prove the theorycraft path on real data: test core (port 8961-8979, temp config "tc_calc": true), the real reference build via POST /api/build-code, PoE2 copy-format items via POST /api/eval; card deltas from PoB, sane, in budget, graceful when the calc is killed (MATH-E2E-LIVE)
- A game start while the core runs must void the previous run's zone (TEST-LIVE-RESTART)
- Glance pass over today's newest surfaces: the Last session card (silent, no live region: it must be noticed by its place), the idle "log quiet" state (dashboard pill, zone tag, overlay word), price movers, the item card "Price and points" and "Rolls" lines, and the Path of Building calc off / failed notices, at 320 / 768 / 1440 px in dark, light and forced colours (UX-NEWEST)
- Waystone mod check on the item-check press: parse waystone clipboard text (tier, area level, mods) and flag mods dangerous for the loaded build (reduced recovery, no regen, extra element vs the build's weakest resistance, monster crit, ...) from AshLight-authored rules on mod text; one card line "Risky for this build: ..." (research 0023 item 1) (UTIL-WAYSTONE)
- Tests/test_http_robust.py:: test_slow_sse_reader_is_dropped_and_does_not_stall_others failed once in a full gated suite (TEST-FLAKE-SSE)
- Give the overlay RAM headroom under the 250 MB budget (248 MB measured, 3 processes) (UX-OVL-RAM)
- One synthetic scenario through every feature over the real HTTP / SSE surface of a core on a free port 8961-8979: consent, log opened, acts 1-4 with level-ups / deaths / splits, maps with a same-seed portal re-entry, trades accepted / cancelled, item checks (gear, waystone, unique), price book from a local mock poe.ninja, build code, 20 min quiet (time-injected), idle + saved summary, core restart + resume (TEST-FULLSTACK)
- A state change with no log event (the idle state and the session summary card from the core loop tick, a trade card expiring) reached SSE clients only on the next heartbeat (http.SSE_HEARTBEAT_S 15 s) (TEST-FULLSTACK-SSE-IDLE)
- Equipped vs checked item on the card: which equipped item the swap replaces and PoB's DPS / EHP delta of it; for rings and a one-hand weapon of a dual wielder the better slot is the headline and the other slot keeps its own PoB line (MATH-COMPARE)
- Glance pass over the util batch 5 / 6 surfaces: waystone verdict on the item card and overlay, Search strings card (Copy feedback without live-region spam, keyboard reachable, long strings wrap at 320 px), Zone tip in Act times, the ashlight.filter download (what it does; AshLight writes nothing into game folders) (UX-B5-CARDS)
- A weapon the main skill cannot use (PoB's own disableReason, read through the bridge) reads "Your main skill can't use this weapon type" as a downgrade, not -100 % and not the "don't add up" fallback (MATH-WEAPON-TYPE)
- AREA-AUDIT pass 4 lows P4-4..P4-6 (docs/audit/2026-11-17-audit.md "Pass 4"): core.tick_sources reads local.json every 0.5 s loop tick (use an mtime check); delta._swap_sane's "base has no weapon_unusable" test can never be false (base outputs never ask main_skill; fix the code or the 0032 amendment wording); the UX-OVL-RAM 2-process / 215 MB budget is only in the opt-in live smoke (AUDIT-P4-LOW)
- Decision 0033 (area-util) (UTIL-FILTER-MERGE)
- Export the loaded PoB build as a GGG Build Planner `*.build` JSON (Version 1, research 0018 section 3) offered as a dashboard "Save .build" download on the player's click; NEVER written into the game's BuildPlanner folder (adjudicator ruling 2026-11-17) (TC-BUILDFILE)
- Map run tracker from Client.txt only: a new instance from `Generating level <N> area "<id>" with seed <N>` with an endgame area id starts a map, hideout / town `[SCENE]` pauses it, a new seed ends it; dashboard shows maps run, time per map, maps per hour, area level, deaths per map, session totals; overlay status slot one line (UTIL-MAPRUN)
- One overlay status line for the open map (name, time in map), split from UTIL-MAPRUN (adjudicator 2026-11-17) (UTIL-MAPRUN-OVL)
- Build health card from the loaded build's PoB-exported PlayerStat values only: each element resist below the 75 cap (chaos shown as a number), ReqStr / ReqDex / ReqInt above Str / Dex / Int (PoB's own warning condition), SpiritUnreserved below 0, weakest element by PoB's *MaximumHitTaken; Life / ES / armour / evasion / block shown as plain values (research 0028 sections 1-2) (MATH-BUILD-HEALTH)
- Under-level warning: area level from the `Generating level N area` line minus the player level from level-up lines; at or above a setting (default 3 levels under) show "N levels under this zone" in the act card and the overlay status word (research 0028 section 3) (UTIL-UNDERLEVEL)
- Glance pass over Build health, Look for next, Run history, Price watch, Settings import / export, the .build save, the filter-merge picker, the under-level line and overlay word, and map time on HUD line 1 (UX-B9-CARDS)
- AREA-AUDIT pass 5 lows P5-2..P5-7 (docs/audit/2026-11-17-audit.md "Pass 5"): settings import may switch tc_calc on (treat like web_data); imported hotkeys accept a bare key (require a modifier); Core._config cache misses a same-size rewrite on a coarse-timestamp filesystem; a filter with the start marker but no end marker stacks a second section; Run history says "No finished acts saved yet" while the current run's splits are saved; decision 0035 is an unrecorded gap (AUDIT-P5-LOW)
- Single-column dashboard below about 520 px for a narrow side window next to the game (research 0028 section 5 item 2, ruling F: desktop layout only, the bind stays 127.0.0.1): the first screen is live play info (session tiles, trades, acts, maps, deaths, item check, recent), the tool cards (build, build health, search, prices, price watch, run history, tools) go into one folded group at the end; DOM order = Tab order (nodes move, no CSS `order`); live regions unchanged (cap 12); wider windows keep today's order (UX-NARROW)
- Find a permitted source for trade stat ids (mod filters for TC-UPGRADE links): GGG API Reference / Data Exports check first (decision 0017), then attributed build-time snapshots with a license check per decision 0009; never the trade2 /data/stats endpoint from the app (TC-UPGRADE-STATS)
- Only 11 of 39 default weights find a trade stat id in the cached stat_descriptions.json: find why and map every default weight that has an explicit trade stat in the file, exact template match only, never a guessed id (decision 0037 item 3) (MATH-TRADESTAT-COVER)
- Multi-character view (research 0028 section 3 item 3, after UTIL-RUN-HISTORY): run history, pace, act splits and deaths keyed by the character name the player's own Client.txt reports; switching character never mixes runs; the dashboard shows the current character by default with a small selector (no aria-live, cap 12) (UTIL-MULTICHAR)
- Fill the trade stat ids repoe-fork lacks from the hash-pinned PoB-PoE2 checkout's TradeSiteStats.lua when the optional calc component is installed (no new download or host), exact template match, bounded text parse, never run as Lua (MATH-TRADESTAT-POB)
- AREA-AUDIT pass 6 lows P6-3, P6-4 (docs/audit/2026-11-17-audit.md "Pass 6"): web/chars.js `seen` is a plain object, so a character named "constructor" / "toString" / "__proto__" is left out of the selector (use Object.create(null) or a Map); the runbook says `tools/tc_drift.py status` shows the new tag, but before the first check it prints `{}` (document it or print the pinned tag) (AUDIT-P6-LOW)
- Waystone reward summary on the same item-check press: sum the reward mods on waystone text (item quantity, item rarity, pack size, rare / magic monsters, waystone drop chance; unidentified noted) into one line next to the UTIL-WAYSTONE risk line ("Rewards: +38% quantity, +25% rare monsters"); overlay keeps its 2-line rule (research 0031 sections 1, 4.3) (UTIL-WAYSTONE-REWARD)
- Skill and ailment DPS split: parse the build XML's `<FullDPSSkill stat value skillPart source>` elements (PoB writes one per contributing skill in every saved build) into one row per skill (name, count, DPS, share of the summed total) and, when non-zero, PoB's BleedDPS / IgniteDPS / PoisonDPS / ImpaleDPS / TotalDotDPS; card labelled "from PoB" (research 0031 sections 2, 4.1) (MATH-SKILL-SPLIT)
- AREA-AUDIT pass 7 lows P7-4 to P7-8 (docs/audit/2026-11-17-audit.md "Pass 7"): P7-4 core._outputs_ready reads state.build_info outside the state lock and writes it back, so a build loaded in that window can be overwritten by the old build's info (bump calc_rev inside SessionState under its lock); P7-5 the health card says "once the optional calc is on" while the calc IS on and its first background answer is pending (calc_on is "table ready", not "switch on"; pass the switch state separately); P7-6 campaign.FlaskCache's re-read on change never runs, the core calls get() once at start (call it on the tick, or drop the claim); P7-7 campaign.build_facts reads any "movement speed" text as speed, so boots with only "reduced Movement Speed" count as fast (match "increased"); P7-8 jsonfile.read_json has no default size cap (layout config, displays.json, summaries, ninja caches read uncapped; add a generous default such as 32 MB) (AUDIT-P7-LOW)
- Release readiness: a fresh `git clone` of main into the AL sidecar Scratch dir, with AL_SIDECAR_ROOT on a throwaway sidecar and a free port 8961-8979, runs the README first-time path exactly as written (setup.ps1, build.ps1 with web_data off, the suites, run.ps1 -NoBrowser, /api/health, stop.ps1) (TEST-CLEAN-CLONE)
- About 25 merges touched web/ today: sweep every card and state (no consent, no build, build loaded, gear / waystone / weapon item checks, trades, maps, deaths, idle with the last session card) at 360 / 520 / 768 / 1440 px, dark / light / forced colours, folds closed and open: overlaps, clipped text, broken folds, focus order, duplicate or contradictory messages, console errors and CSP violations (from CDP), stale copy (UX-REGRESSION-SWEEP)
- First-hours hints for a new character: one-time, auto-expiring hints keyed to Client.txt events (first level-up from level 1, first campaign death: "campaign deaths cost no experience", first town / hideout, first map: "deaths in maps cost experience", first item-check moment: the hotkey how-to), AshLight-authored restated facts, shown in the event feed and the overlay status word (research 0032 sections 1, 5.3) (NEWBIE-HINTS)
- Self-diagnostics "Checks" card: Client.txt found / consented / reading / last line age, character seen, log language (LANG-GUARD), web data on and contact set, price book age and last fetch error, calc component installed and pinned, build-time data snapshots present and age, overlay and supervisor alive (procs.py), hotkey registered, version / build stamp (DIAG-SELF)
- The dashboard was one column of ~19 cards and scrolled at 1080p (UI-GLANCE)
- A launchable desktop client instead of the dashboard in a browser tab (operator ask 2026-11-17; decision 0041): the Electron app with --client runs a framed, resizable "AshLight" companion window with the standard title bar (X closes it to the tray; size / position remembered in ops/runtime), a tray (Minimize-Restore / Show in-game overlay / Restart overlay / Quit; left-click restores), a "Restart overlay" dashboard button inside the client (id restart-overlay) and the overlay, in one process; the overlay exists only while the client runs (operator order 2026-11-17; run.ps1 starts the client, never a bare overlay) (DESKTOP-CLIENT)
- Make the app hot-reloadable: data files (tracked data/, cached snapshots) re-read on change with the last good copy kept on a bad edit and a one-line health note; web/ edits reload the open dashboard (SSE "reload"); overlay page edits reload the overlay page; server/ .py edits restart the core through the supervisor after a preflight, never looping on broken code (HOT-RELOAD)
- Live zone guide and quest tracker: on every zone change the dashboard shows the zone's goal, bonus content with a permanent reward, a layout tendency, the next zone, waypoint / nearest waypoint (world_areas snapshot), a clear-or-push lean from level vs zone level, and per character the act's main-path steps done plus bonus zones skipped in earlier acts (ZONE-GUIDE)
- A distinctive app icon (shortcut, window, tray), dashboard favicon and README hero, drawn from own SVG sources (design note docs/design/0005-brand-mark.md) (BRAND-ICON)
- Daily read of GGG's developer docs (index, authorization, reference, changelog, data, game) for changes, above all whether new OAuth application registration reopened (operator order 2026-11-17, decision 0044) (GGG-DOCS-WATCH)
- Item upgrade notices tied to the character being played (operator order 2026-11-17, decision 0045): one build per character (keyed by the decision 0038 name; legacy last-code.txt moves to the first character), swapped by the core loop tick; stale-build alert `build_alert` (missing / class / 5+ levels behind) in the #build-alert slot (web/buildlive.js); every checked item kept per character in memory (10) and re-scored on each build or weight change, `upgrades` lists the ones that beat the gear now (slot replaced, delta, fit); build files hot-reload on mtime; build sources behind theorycraft/providers.py (paste now, ggg_api stub: not set up, no request) (BUILD-LIVE)
- A pointed, test or demo core never looks for the live Client.txt (SEC-NO-DISCOVERY)
- Serve /web/ from a fixed name map (closes the UNC path leak) + Refuse cross-site requests on every route; trim unused allowances (SEC-STATIC-MAP)
- Strict build XML intake: refuse an inflated payload holding a NUL byte (SEC-XML-NUL)
- Hardened write path in jsonfile (temp name, fsync, retry, .bak, Saver) (RUN-DURABLE-JSONFILE)
- Loopback calls never use a proxy (SEC-NO-PROXY)
- Split Tick review and work-list methods out of al_loop.py (no behaviour change) (LOOP-SPLIT-TICK)
- Carve the loop tests that later packages rewrite into four owner files (LOOP-TESTS-CARVE)
- Slot tables: pure priority and eviction functions for Play and the overlay (PLAY-TD-02-SLOTS)
- ROW-FILES tool: tools/roadmap.py with rows, lint, new and done (AUTO-03)
- FS-LEDGERS: union merge for one-line ledgers and a ledger shape test (LOOP-LEDGERS)
- Loop preflight command: gates once on unchanged main, hand-off count (LOOP-PREFLIGHT-CMD)
- Item card parts registry (server side seam) (TC-CARD-PARTS)
- Demo mode core: an isolated instance on a fixture folder (SEC-DEMO-CORE)
- LOOP-PREFLIGHT core: session line, dry run past HALT, tick step seam (AUTO-01)
- DIVE-FLOOR: dives lose free web tools and read GGG only at the two docs pages (AUTO-04)
- The loop merge closes a row with a done file, not a ROADMAP.md edit (LOOP-ROWFILES-MERGE)
- Hand-off bullets are loop work only with a LOOP: prefix (LOOP-HANDOFF-PREFIX)
- ROADMAP-PRUNE: tools/roadmap_fold.py with prune and fold, first prune run (AUTO-02)
- One test file that pins the local HTTP surface (SEC-SURFACE-PIN)
- Store modules save with one .bak and clear it with the data (RUN-DURABLE-STORE-FILES)
- Tailer never dies and never replays a backlog (logfile.py) (RUN-TAIL-HEAL-READER)
- Region hook: one registry, pre-linked region files (PLAY-TD-09A-REGION-HOOK)
- Ceiling on handler threads (SEC-CEIL-HTTP)
- Demo mode entry: python -m server.al --demo <fixture dir> (SEC-DEMO-ENTRY)
- Pin the pytest plugin set; register markers; keep the end of the gate output (TEST-PLUGIN-PIN)
- A failed item is parked visibly; a foreign gate failure ends the fix rounds (LOOP-FAILED-PARK)
- The loop work list reads rows through the loader: DEPENDS and exact-id briefs (LOOP-ROWFILES-WORK)
- /done folds row files and prunes done rows; the fold round trip is tested (LOOP-DONE-FOLD)
- Guard test for test naming and test-to-test imports (TEST-LAYOUT-GUARD)
- Dashboard renders card notes, word and tone from the core + Recover a refused share link in two clicks (TC-CARD-PARTS-WEB)
- League identity for launch day: id and name, conditional league GET (DATA-LEAGUE-IDENTITY)
- Play state recipes and the long-string fixture (PLAY-TD-01A-PLAY-STATES)
- The item key loads a copied build (TC-PRESS-BUILD)
- In_hideout from the area id of the generation line, not an English scene-name substring (OVL-HIDEOUT-AREA)
- Fresh-clone proof of the suite (GP-04)
- Replace the local-only wording in loop tools and ritual files (PUB-LOCAL-ONLY-TEXT)
- Wave folder hold and the shared merge lock (LOOP-WAVE-HOLD)
- Private runtime files: explicit ACL on the runtime dir and local config (SEC-ACL-APPLY)
- CI workflows and their lint test (GP-05)
- Price card words: cache age, league after a change, contact copy + One card per trade request: a repeated whisper refreshes its card (DATA-PRICE-CARD-TEXT)
- One status vocabulary table for the bar, the overlay, Checks and the strip (PLAY-F-131-STATUS-TABLE)
- Fit harness, red first (G1, G2, G4-G7, G9) (PLAY-TD-01B-FIT-HARNESS)
- Worn-gear store and baseline (TC-WORN-STORE)
- Main-process parts seam: app/parts/ files loaded by app/parts.js; hotkey registration moves into the first part (OVL-MAIN-PARTS)
- Type, spacing, scale and control-edge tokens (PLAY-TD-03-TOKENS)
- Evaluate() in all-or-nothing stages (TC-PRESS-STAGED-EVAL)
- Core hello handshake: GET /api/hello and the supervisor check (SEC-HELLO-CORE)
- One filter control, stamped (TC-FILTER-ONE-CONTROL)
- WAVE-INTERPLAY: BLOCKED reason echo and the dispatch re-check from HEAD (AUTO-06)
- Plug-in folder: ticks, Checks rows and token-gated routes without shared-file edits (RUN-SEAMS)
- Setup.ps1 makes the sidecar private; the logon launcher starts PowerShell by its System32 path (SEC-ACL-SETUP)
- Port lease for tests that bind a port (leases 8962-8969) (TEST-PORT-LEASE)
- Play view: capped strings for strip, feed, notices and build line (PLAY-TD-07A-PLAY-VIEW)
- Play skeleton: 7 fixed regions on the cockpit grid (PLAY-TD-09B-SKELETON)
- Keep-or-vendor verdict with no build loaded (TC-CAMPAIGN-KEEP)
- Parse ledger module: hit counts and masked shapes (logshapes.py) (RUN-LEDGER-CORE)
- Hotkeys in the client: re-register on a config change, fall back from a taken key, write ops/runtime/hotkeys.json (OVL-KEYS-CLIENT)
- Pager: list pages and the Full text page (PLAY-TD-19A-PAGER)
- Glance budget and notification policy in design 0001, held by tests (OVL-GLANCE-RULES)
- Dark by default in the desktop client (PLAY-TD-04A-DARK-CLIENT)
- Checks note when AshLight's folders let someone else write (SEC-ACL-CHECK)
- Move the five CRLF / hand-rolled writers onto the jsonfile helper (RUN-DURABLE-CRLF)
- Play view: context modes, item card and kept checks (PLAY-TD-07B-PLAY-CARDS)
- Bar: the mark, the character slot and one status word + MERGE-SEAMS F5 and F7: restart note clears, tool-row class (PLAY-TD-09C-BAR)
- Feed T: five one-line rows, trades first (PLAY-TD-13-FEED)
- Build line B with the Paste a build button (PLAY-TD-15-BUILDLINE)
- Notice N: one notice at a time (PLAY-TD-14-NOTICE)
- Verdict store, token API and read-back script for the 'Tried in game' checks (RUN-VERDICTS-CORE)
- Overlay settings schema: parts switches, quiet town, zone-guide choice in layout.py and layout.js (OVL-OVERLAY-KEYS)
- Tools/state_equiv.py and the design gate prefix server/al/text/ (TEST-STATE-EQUIV)
- The source install works for a stranger (DEP-02)
- OBS-SSE-EVENTS: stop sending chat-bearing frames by default (SEC-SSE-TAP)
- App/test/_web.js: one helper that knows where dashboard sources live (node side) (TEST-WEB-SRCPATHS-NODE)
- Tests/srcpaths.py: one helper that knows where dashboard sources live (Python side) (TEST-WEB-SRCPATHS-PY)
- Core saves retried from the tick with back-off; one Checks row while unsaved (RUN-DURABLE-STORES)
- Mark timing, calc and worker-group tests (TEST-MARKS)
- Context C: guide, town, map and none modes (PLAY-TD-11-CONTEXT)
- Kept checks U: the 3 best checked items (PLAY-TD-16B-KEPT-CHECKS)
- Strip G, the bar words and the stale look (PLAY-TD-10-STRIP)
- Item card I: verdict first, reserved rows (PLAY-TD-16A-ITEMCARD)
- Overlay page honours the parts switches: a part that is off drops out, an empty HUD plate is absent (OVL-PARTS-PAGE)
- Zone guide short field: loader, cap and view key (PLAY-TD-08A-GUIDE-SHORT-FIELD)
- Installed-mode paths (Python side) (DEP-05)
- Build caveat on the verdict; alerts name the item-key press (TC-VERDICT-CAVEAT)
- Rotate the sub-agent ledger, flag a stale docs watch, tidy (DEV-LEDGERS)
- Web/fmt.js: pad, duration and clock defined once (TEST-WEB-FMT)
- Core restarts a dead log reader and the Reading row tells the truth (RUN-TAIL-HEAL-CORE)
- Tools/test_select.py: the test files for a diff (TEST-SELECT)
- Three diagnosed parallel suite runs: why the loop's xdist runs went red (TEST-XDIST-DIAG)
- Context C: setup, error and idle modes (PLAY-TD-12-CONTEXT-SETUP)
- Community files (GP-06)
- One version, enforced, and the release tool dispatcher (DEP-03)
- Spike: AshLight under the private runtimes (DEP-01)
- Commit subject check in the commit-msg hook (REL-SUBJECT-CHECK)
- Webfetch: bounded gzip inflate, HTTPException mapping, Retry-After helper (DATA-WEBFETCH-GZIP)
- HTTP route tables per verb (TEST-HTTP-ROUTES)

### Fixed
- Drop aria-live from session summary, clear ROADMAP conflict markers
- Resolve logs a warning for an out-of-block port before falling back to 8960
- Pre-push guard hardened after review
- Design review S2/S3 fixes - waypoint row folded, build-alert slot labelled and styled, dead zone margins; file MERGE-SEAMS-FOLLOWUP (MERGE-SEAMS)
- Create the private repository, first push, CI green (GP-09)

### Security
- Electron pin: config/electron_pin.json and tools/electron_pin.py (hash-pinned fetch, verify, unpack) (OVL-ELECTRON-PIN)

Also: 258 internal changes.

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
