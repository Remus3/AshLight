# Existing PoE1/PoE2 companion tools

Research date 2026-11-16. Study for features and pitfalls only; no code copied. Release dates and SPDX ids come from the GitHub REST API (repos/OWNER/REPO and /releases/latest) and LICENSE files unless noted. Anything not verified is marked UNVERIFIED.

## GGG policy baseline (read first)

- GGG developer docs policy summary: websites carry least risk; standalone executables are permitted but discouraged and must use a public OAuth client; macros must be invoked manually, one fixed function, one game-affecting action per invocation; apps reading screen, clipboard or logs are limited to one screen/clipboard read per manual key press; apps that interact with the game or its files are strictly prohibited and can mean immediate account termination; endpoints outside the docs must not be reverse-engineered (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- Rate limits are dynamic; apps must obey X-Rate-Limit-* and Retry-After headers; frequent excess or many 4xx responses can get access revoked; User-Agent must be `OAuth {clientId}/{version} (contact: {contact})`; new application registrations are currently not being processed (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- Memory reading is not named in those docs; it falls under "apps that interact with the game" (our inference from the same page) (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- GGG staff on a third-party tools thread: "we do not encourage the creation or use of third-party tools", cannot guarantee a tool stays allowed, advised against anything interacting with the game client for advantage and against more than one action per keystroke or click; staff did not name or approve Awakened PoE Trade (https://www.pathofexile.com/forum/view-thread/3482763) (accessed 2026-11-16).
- Exile-UI's author states GGG has never approved any local third-party tool to their knowledge and that creators can be banned for distributing ToS-violating tools (https://github.com/Lailloken/Exile-UI) (accessed 2026-11-16).
- ToS controversy example: a forum poster claimed a ban attributed to Exiled Exchange 2; other users doubted EE2 alone was the cause and suggested too many trade queries; no GGG staff reply on the page. Unproven (https://www.pathofexile.com/forum/view-thread/3777565/page/2) (accessed 2026-11-16).

## What NOT to do: memory readers (PoeHUD / ExileApi)

- What: PoeHUD-derived tools such as ExileApi read game process memory to draw an overlay (https://github.com/vadash/ExileApi) (accessed 2026-11-16).
- A GGG announcement banning PoeHUD/ExileApi by name: UNVERIFIED (not found in searches 2026-11-16).
- Why avoid: a GGG developer quote (secondhand, 2020 Reddit post) says the rule has been unchanged for about eight years: you may not run programs that interact with the Path of Exile game client (https://lr.in.psf.lt/r/pathofexiledev/comments/ga4wzy/psa_waves_of_players_being_banned_for_use_of) (accessed 2026-11-16). Same prohibition in the developer docs (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- Design rule for us: never read process memory, inject, hook the renderer, or send input that affects the game. Read only Client.txt, user-triggered clipboard, and official APIs.

## Awakened PoE Trade (SnosMe)

- What: PoE1 price-check overlay for gems, rares, uniques, currency (https://github.com/SnosMe/awakened-poe-trade) (accessed 2026-11-16).
- Stack: Electron + Vue/TypeScript; libuiohook for global input (same URL).
- License: MIT (GitHub API, same repo) (accessed 2026-11-16).
- Maintenance: latest release v3.29.108 on 2026-09-09; last push 2026-09-24; 339 open issues.
- Data: clipboard copy of the item; poe.ninja, RePoE, poeprices.info credited in README; official trade queries (same URL).
- Overlay: window attached to the game by window title (see EE2 fork setup note below); exact transparency/click-through mechanism UNVERIFIED.
- Pitfalls from issues:
  - Lag in Fullscreen and Windowed Fullscreen: https://github.com/SnosMe/awakened-poe-trade/issues/1941 (accessed 2026-11-16)
  - Overlay layer and background dim stuck on screen: https://github.com/SnosMe/awakened-poe-trade/issues/1944 (accessed 2026-11-16)
  - Washed-out NVIDIA Shadowplay recordings in borderless and fullscreen: https://github.com/SnosMe/awakened-poe-trade/issues/1936 (accessed 2026-11-16)
  - Wrong overlay offsets on some windowed-fullscreen resolutions: https://github.com/SnosMe/awakened-poe-trade/issues/1281 (accessed 2026-11-16)
  - Installer never starts or Squirrel failure: https://github.com/SnosMe/awakened-poe-trade/issues/1680 and https://github.com/SnosMe/awakened-poe-trade/issues/1553 (accessed 2026-11-16)
  - Rate limiting noticed while parsing item mods: https://github.com/SnosMe/awakened-poe-trade/issues/1779 (accessed 2026-11-16)
  - "Failed to load leagues": https://github.com/SnosMe/awakened-poe-trade/issues/1840 (accessed 2026-11-16)
  - Performance impact on apps other than PoE: https://github.com/SnosMe/awakened-poe-trade/issues/415 (accessed 2026-11-16)
- ToS: not approved by GGG; see baseline thread.

## Exiled Exchange 2 (Kvan7)

- What: PoE2 fork of Awakened PoE Trade; setup note says PoE1 APT settings can migrate and config windowTitle must read "Path of Exile 2" (https://github.com/Kvan7/Exiled-Exchange-2) (accessed 2026-11-16).
- Stack: Electron/TypeScript (GitHub API language TypeScript; main/renderer folders).
- License: MIT (GitHub API).
- Maintenance: v0.16.3 released 2026-09-06; last push 2026-09-17.
- Data: clipboard item text, poe.ninja, poeprices.info, RePoE, trade API (README acknowledgments).
- Pitfalls:
  - Randomly exceeding trade limit: https://github.com/Kvan7/Exiled-Exchange-2/issues/502 (accessed 2026-11-16)
  - Overlay misaligned after update: https://github.com/Kvan7/Exiled-Exchange-2/issues/697 (accessed 2026-11-16)
  - Frame-rate issues with AMD FreeSync: https://github.com/Kvan7/Exiled-Exchange-2/issues/571 (accessed 2026-11-16)
  - Overlay stays on top of game / does not work in background: https://github.com/Kvan7/Exiled-Exchange-2/issues/1047 (accessed 2026-11-16)
  - Lossless Scaling not working after overlay closes: https://github.com/Kvan7/Exiled-Exchange-2/issues/47 (accessed 2026-11-16)
  - Linux/XWayland overlay does not follow game window; GNOME stops accepting clicks: https://github.com/Kvan7/Exiled-Exchange-2/issues/1041 and https://github.com/Kvan7/Exiled-Exchange-2/issues/1069 (accessed 2026-11-16)
  - Fetching PoE1 league names in PoE2 build: https://github.com/Kvan7/Exiled-Exchange-2/issues/769 (accessed 2026-11-16)
  - Fake download sites: README warns only listed sites are official (https://github.com/Kvan7/Exiled-Exchange-2) (accessed 2026-11-16)
- ToS: single unproven ban claim in baseline.

## Sidekick (Sidekick-Poe)

- What: PoE1 and PoE2 price check, dangerous map-mod warnings (https://github.com/Sidekick-Poe/Sidekick) (accessed 2026-11-16).
- Stack: Blazor UI in an Avalonia desktop host (WebView2 on Windows), .NET 10; also web app/Docker; SharpHook, TextCopy.
- License: MIT (GitHub API).
- Maintenance: v2026.11.6 released 2026-11-16 (very active).
- Data: simulated copy keypress to read the item; official trade, poe2scout.com, poe.ninja, poeprices.info, poewiki, poedb (README).
- Overlay: windowed app plus tray; closing window hides to tray (README).
- Pitfalls:
  - Sidekick.dll flagged Trojan:Script/Wacatac.B!ml: https://github.com/Sidekick-Poe/Sidekick/issues/1246 (accessed 2026-11-16)
  - Not centered at DPI other than 100 percent: https://github.com/Sidekick-Poe/Sidekick/issues/261 ; zoom setting in https://github.com/Sidekick-Poe/Sidekick/pull/607 (accessed 2026-11-16)
  - Focus lost / wrong window switched: https://github.com/Sidekick-Poe/Sidekick/issues/612 and https://github.com/Sidekick-Poe/Sidekick/issues/445 (accessed 2026-11-16)
  - Alt-key chat commands toggling fullscreen: https://github.com/Sidekick-Poe/Sidekick/pull/456 (accessed 2026-11-16)
  - KDE Wayland needs a Remote Control permission prompt (README) (accessed 2026-11-16)

## Path of Building and Path of Building PoE2 (PathOfBuildingCommunity)

- What: offline build planner: passive tree, skills, items, DPS/defence calcs, character import, trade search from item planner (https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2) (accessed 2026-11-16).
- Stack: Lua with a Windows runtime; Python helper scripts.
- License: MIT text in LICENSE.md (copyright David Gowor); GitHub API reports NOASSERTION, so extra bundled-component notices may exist: UNVERIFIED (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/LICENSE.md) (accessed 2026-11-16).
- Maintenance: PoE1 v2.67.2 released 2026-08-07; PoE2 v0.23.1 released 2026-07-28; pushed 2026-11-16 and 2026-11-13.
- Not an overlay; relevant as a build-code/data source.

## PoE Overlay (Kyusung4698) and community forks

- What: price check, stash grid, trade companion whisper popups, vendor recipes, hotkeys; Electron+Angular community fork requires windowed fullscreen (https://github.com/wratho/PoE-Overlay-Community-Fork) (accessed 2026-11-16).
- Original: MIT, last push 2022-04-16, moved to Overwolf; stale (https://github.com/Kyusung4698/PoE-Overlay) (accessed 2026-11-16).
- PoE2 support: not mentioned. Overwolf overlay bannability question had no definitive answer seen: https://pathofexile.com/forum/view-thread/3637217 (accessed 2026-11-16).

## PoE Lurker (C1rdec)

- What: PoE1 trade manager; Patreon "Lurker Pro" extras (https://github.com/C1rdec/Poe-Lurker) (accessed 2026-11-16).
- Stack: C#/.NET 8+, MahApps.Metro UI, Winook thread hook.
- License: MIT (GitHub API). Maintenance: v2.2.2 released 2025-11-15; last push 2026-05-18.
- Whisper detection method, overlay details, PoE2 support: UNVERIFIED.

## Exilence Next / Exilence CE

- What: net worth and income-per-hour tracker for characters and stash tabs, group net worth (https://github.com/exilence-ce/exilence-ce) (accessed 2026-11-16).
- Stack: Electron 15 + React 17 + mobx, .NET Core 3.1 backend (README).
- License: README says CC BY-NC 3.0; GitHub API shows no SPDX; LICENSE file URL fetch returned 404, so the file itself is UNVERIFIED.
- Maintenance: Exilence Next v1.2.1 released 2022-09-17 (https://github.com/viktorgullmark/exilence-next) (accessed 2026-11-16); CE v1.3.0 released 2026-07-25.
- Data: poe.ninja prices; stash access method and PoE2 support UNVERIFIED.
- Pitfall: old runtime pins (Node 14-16, Electron 15); manual protocol handler on Linux.

## Craft of Exile (website)

- What: browser crafting odds calculator/emulator, PoE1 and PoE2 (`?game=poe2`, data updated for PoE2 patch 0.5 per page); single developer; not affiliated with GGG (https://www.craftofexile.com/) (accessed 2026-11-16).
- Closed website; license UNVERIFIED. Idea: link out, do not reimplement.

## Mercury Trade (Exslims) and Community Fork (Morph21)

- What: Java overlay: trade whisper notification panel with hotkey response buttons, chat scanner, history restore, stash highlight, do-not-disturb, screen "Capture" timers (https://github.com/Morph21/MercuryTrade-Community-Fork) (accessed 2026-11-16).
- Stack: Java, Maven, Launch4j. License: MIT. Release date from repo page: UNVERIFIED.
- PoE2: setting added per release 1.3.5, with known issues listed (https://newreleases.io/project/github/Morph21/MercuryTrade-Community-Fork/release/1.3.5) (accessed 2026-11-16).
- Pitfall: client must not be in fullscreen; notifications appearing while minimized fixed in 1.3.5.

## SlimTrade (zmilla93)

- What: PoE1 and PoE2 trade overlay: incoming/outgoing popups, stash helper, chat scanner, history restoring trades received while the app was closed, 25+ themes (https://github.com/zmilla93/SlimTrade) (accessed 2026-11-16).
- Stack: Java (inferred from pom.xml/jpackage). License: MIT. Latest release 0.6.8 on 2025-06-24; last push 2026-11-10.
- PoE2 pitfall: an older release note says PoE2 broke incoming/outgoing whisper detection, so outgoing trades needed an extra hotkey (https://newreleases.io/project/github/zmilla93/SlimTrade/release/0.5.0-pre6) (accessed 2026-11-16); current state UNVERIFIED.

## Exile-UI (formerly Lailloken UI)

- What: AutoHotkey overlay toolkit for PoE1 and PoE2: clone-frames, Act-Tracker and Act-Decoder, Map-Tracker, item info, Stash-Ninja/Rune-Ninja (PoE2), chat macros, FilterSpoon, Statlas (PoE2), trade logging, cheat sheets, translations (https://github.com/Lailloken/Exile-UI) (accessed 2026-11-16).
- Stack: AutoHotkey with GDI+ and UWP OCR libraries.
- License: MIT. Maintenance: v1.66.0 released 2026-11-14; last push 2026-11-15; about 1.4k stars.
- Data: Client.txt (level, area changes, NPC dialogue), screen checks and OCR on key press, simulated keys for item copy and chat commands, PoB/poe.ninja/poedb data (README).
- Fullscreen behavior: UNVERIFIED. Author calls it "rough around the edges"; screen checks and key sending sit close to GGG's one-action-per-keypress rules and the author disclaims ban knowledge (README).
- Old repo name Lailloken/Lailloken-UI now redirects (GitHub API "Moved Permanently", accessed 2026-11-16).

## Leveling overlays (PoE1 and PoE2)

- Qutm (Vyary): PoE2 campaign overlay; zone guide updating on zone change, layout widget, inventory scan (beta), price check (beta); Tauri + TypeScript + Vite; transparent overlay; reads only Client.txt; Apache-2.0; Windows primary (https://github.com/Vyary/qutm) (accessed 2026-11-16). Last push 2026-11-17 (GitHub search API).
- exile-leveling (HeartofPhos): web leveling route app, editable route, data from exile-export `.dat.json`; MIT; last push 2026-11-12; no PoE2 mention (https://github.com/HeartofPhos/exile-leveling) (accessed 2026-11-16).
- poe2-leveling (domistae): PoE2 campaign route in HTML, MIT, last push 2026-11-08 (https://github.com/domistae/poe2-leveling) (accessed 2026-11-16; contents not read).
- PoE-Leveling-Guide (JusKillmeQik): AHK overlay, MIT, last push 2024-07-25, stale (https://github.com/JusKillmeQik/PoE-Leveling-Guide) (accessed 2026-11-16).
- XileHUD: overlay with mod/base/unique lookup; GPL-3.0; pushed 2026-07-28 (https://github.com/XileHUD/poe_overlay) (accessed 2026-11-16); internals UNVERIFIED.

## Chaos Recipe Enhancer

- What: PoE1 overlay showing items to pick for chaos/regal/chance/exalted vendor recipes; set tracker overlay; sound on completed sets; offline loot filter edits (https://github.com/ChaosRecipeEnhancer/ChaosRecipeEnhancer) (accessed 2026-11-16).
- Stack: C#/.NET WPF. License: GPL-3.0 (GitHub API). Latest release v3.28.1002 on 2026-03-03.
- Data: stash via OAuth to GGG servers (README). PoE2 support not mentioned. Online loot filter sync unsupported.

## PoE-TradeMacro (old)

- What: AHK 1.x script built on PoE-ItemInfo: alt+d search on poe.trade, advanced search, wiki, item age, league switch (https://github.com/PoE-TradeMacro/POE-TradeMacro) (accessed 2026-11-16).
- License: GPL-3.0. Last release v2.16.0 on 2020-06-19; last push 2021-08-02 (GitHub API).
- Why discontinued: no notice on the README page; reason UNVERIFIED. Context (our inference, not sourced): it targeted the old poe.trade site and used macro-style input.
- Lineage: Sidekick credits it (https://github.com/Sidekick-Poe/Sidekick) (accessed 2026-11-16).

## Wealthy Exile (website)

- What: site with Stash (currency per hour, tab breakdown, snapshots), Services, Strategies, Trade; not affiliated with GGG; data method and PoE2 support not stated (UNVERIFIED) (https://wealthyexile.com/) (accessed 2026-11-16).
- Third-party helper: Chrome extension that watches the log to trigger snapshots, MIT (https://github.com/pfeigl/WealthyExileSnapshotter) (accessed 2026-11-16).

## PoE2-specific trackers and small projects

- Map trackers (waystone/tablet/loot/profit): igodspy/PoE2MT (MIT) and OrkunPolat/poe2-map-tracker (no license), both tiny; internals UNVERIFIED (https://github.com/igodspy/PoE2MT) (accessed 2026-11-16).
- exiled-orb: PoE1/2 desktop overlay with price check, mod tiers, map-run tracker, OAuth; MIT; tiny (https://github.com/yurikoeth/exiled-orb) (accessed 2026-11-16).
- poe2-log-watcher (Go): whisper notifications from the log; no license (https://github.com/quinlayen/poe2-log-watcher) (accessed 2026-11-16).
- PoE2-AutoFlask (Python, MIT): reads health/mana and presses flasks; this kind of automation breaches the manual-invocation rule; do not emulate (https://github.com/adnv3k/PoE2-AutoFlask) (accessed 2026-11-16).
- Repos titled "PoE2 cheat 2026 / bot / ESP" appear in search; treat as scams or malware, never use (search results, accessed 2026-11-16).
- Standalone death counter or zone-time tracker with a real user base: none found (UNVERIFIED); closest are Exile-UI Map-Tracker and Qutm.

## Feature patterns worth adopting

Ranked by value for a glanceable live companion; all feasible from Client.txt, user-triggered clipboard and official APIs:

1. Zone/area timer and run log from Client.txt area-change lines (Exile-UI Map-Tracker and Act-Tracker, Qutm zone guide).
2. Act/leveling hints keyed to current zone (Qutm, exile-leveling, Exile-UI Act-Decoder); needs our own route data since routes are community-authored.
3. Trade whisper notification popups with response buttons and history restore after the app was closed (SlimTrade, Mercury Trade, PoE Lurker).
4. Price check on copied item, one clipboard read per user key press (APT, EE2, Sidekick): the policy-compliant model.
5. Session stats: runs per hour, deaths, level-ups, XP per hour from log lines (Exile-UI, Exilence income tracking).
6. Currency rates panel from poe.ninja / poe2scout with cached, rate-limited fetch (Sidekick, APT).
7. Second-screen web dashboard: GGG docs say websites carry least risk (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
8. Stash net-worth/income via official OAuth (Exilence CE, Chaos Recipe Enhancer): valuable but new OAuth app registration is closed, feasibility UNVERIFIED.
9. Link out to Craft of Exile rather than reimplementing crafting math.
10. Dangerous map-mod warnings (Sidekick) and a do-not-disturb mode (Mercury Trade).

## Pitfalls to avoid

- Memory reading, injection, auto-input: prohibited, termination risk (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).
- Timer, file-change or screen-triggered input is not allowed under the macro rules (same URL); flask bots breach it (https://github.com/adnv3k/PoE2-AutoFlask) (accessed 2026-11-16).
- Overlay lag in fullscreen/borderless: https://github.com/SnosMe/awakened-poe-trade/issues/1941 (accessed 2026-11-16). Keep GPU use minimal; target borderless windowed; document exclusive fullscreen as unsupported.
- Stuck overlay or dim layer: https://github.com/SnosMe/awakened-poe-trade/issues/1944 (accessed 2026-11-16). Add a hide watchdog.
- Screen-capture software interference: https://github.com/SnosMe/awakened-poe-trade/issues/1936 (accessed 2026-11-16).
- AMD FreeSync frame-rate issue with a transparent window: https://github.com/Kvan7/Exiled-Exchange-2/issues/571 (accessed 2026-11-16).
- DPI, offset and resolution errors: https://github.com/Sidekick-Poe/Sidekick/issues/261 , https://github.com/SnosMe/awakened-poe-trade/issues/1281 , https://github.com/Kvan7/Exiled-Exchange-2/issues/697 (accessed 2026-11-16). Track the game window rect continuously (EE2 on Linux read it once: https://github.com/Kvan7/Exiled-Exchange-2/issues/1041) (accessed 2026-11-16).
- Antivirus false positive on unsigned managed binary: https://github.com/Sidekick-Poe/Sidekick/issues/1246 (accessed 2026-11-16). Plan code signing and reproducible builds.
- Installer failures: https://github.com/SnosMe/awakened-poe-trade/issues/1680 (accessed 2026-11-16).
- Trade API rate limits and 4xx bursts: https://github.com/Kvan7/Exiled-Exchange-2/issues/502 and https://github.com/SnosMe/awakened-poe-trade/issues/1779 (accessed 2026-11-16). Honor X-Rate-Limit and Retry-After, serialize queries, never auto-search on hover.
- League-list fetch failures and PoE1/PoE2 league mixups: https://github.com/SnosMe/awakened-poe-trade/issues/1840 and https://github.com/Kvan7/Exiled-Exchange-2/issues/769 (accessed 2026-11-16). Cache with fallback.
- PoE2 whisper log format changes breaking detection: https://newreleases.io/project/github/zmilla93/SlimTrade/release/0.5.0-pre6 (accessed 2026-11-16). Parse defensively, version the parser, test against sample lines per patch.
- Fullscreen-only restriction frustrates users: https://github.com/Morph21/MercuryTrade-Community-Fork and https://github.com/wratho/PoE-Overlay-Community-Fork (accessed 2026-11-16).
- Focus stealing from the game: https://github.com/Sidekick-Poe/Sidekick/issues/612 and https://github.com/Kvan7/Exiled-Exchange-2/issues/1047 (accessed 2026-11-16). Make the overlay click-through by default, interactive only on hotkey.
- Platform dependency (Overwolf) and abandoned upstream: https://github.com/Kyusung4698/PoE-Overlay (accessed 2026-11-16).
- Fake download sites: https://github.com/Kvan7/Exiled-Exchange-2 (accessed 2026-11-16). Publish checksums and one official download page.
- Branding: apps must not appear GGG-official and should show a non-affiliation notice (https://www.pathofexile.com/developer/docs) (accessed 2026-11-16).

## License notes

- MIT (ideas reusable; code reuse would need notice, but we copy none): Awakened PoE Trade, Exiled Exchange 2, Sidekick, Path of Building (MIT text, see caveat), Exile-UI, PoE Lurker, SlimTrade, MercuryTrade fork, PoE Overlay, exile-leveling.
- Apache-2.0: Qutm (compatible with our license).
- GPL-3.0, DO NOT copy code into Apache-2.0: PoE-TradeMacro, Chaos Recipe Enhancer, XileHUD (GitHub API).
- CC BY-NC 3.0 per README, non-commercial and not a software license: Exilence CE; do not copy code or assets. File-level license UNVERIFIED.
- Closed or unstated: Craft of Exile, Wealthy Exile, several tiny repos; no reuse.
- Feature ideas are not copyrightable. Game data (mods, tree, zone and route data) is GGG's and may carry its own terms: UNVERIFIED; check GGG terms before bundling. RePoE and exile-export derive from game files.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-16)
- https://www.pathofexile.com/forum/view-thread/3482763 (accessed 2026-11-16)
- https://www.pathofexile.com/forum/view-thread/3777565/page/2 (accessed 2026-11-16)
- https://pathofexile.com/forum/view-thread/3637217 (accessed 2026-11-16)
- https://lr.in.psf.lt/r/pathofexiledev/comments/ga4wzy/psa_waves_of_players_being_banned_for_use_of (accessed 2026-11-16)
- GitHub REST API repo and release endpoints for the repos named above (accessed 2026-11-16)
- https://github.com/SnosMe/awakened-poe-trade (accessed 2026-11-16)
- https://github.com/Kvan7/Exiled-Exchange-2 (accessed 2026-11-16)
- https://github.com/Sidekick-Poe/Sidekick (accessed 2026-11-16)
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2 (accessed 2026-11-16)
- https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/LICENSE.md (accessed 2026-11-16)
- https://github.com/Lailloken/Exile-UI (accessed 2026-11-16)
- https://github.com/exilence-ce/exilence-ce (accessed 2026-11-16)
- https://github.com/C1rdec/Poe-Lurker (accessed 2026-11-16)
- https://github.com/ChaosRecipeEnhancer/ChaosRecipeEnhancer (accessed 2026-11-16)
- https://github.com/PoE-TradeMacro/POE-TradeMacro (accessed 2026-11-16)
- https://github.com/Vyary/qutm (accessed 2026-11-16)
- https://github.com/HeartofPhos/exile-leveling (accessed 2026-11-16)
- https://github.com/Morph21/MercuryTrade-Community-Fork (accessed 2026-11-16)
- https://github.com/wratho/PoE-Overlay-Community-Fork (accessed 2026-11-16)
- https://github.com/zmilla93/SlimTrade (accessed 2026-11-16)
- https://www.craftofexile.com/ (accessed 2026-11-16)
- https://wealthyexile.com/ (accessed 2026-11-16)
- GitHub issue and release pages cited inline (accessed 2026-11-16)
