# 0054 - Competitive review: PoE and PoE2 companion tools (design patterns)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B16
competitive review: PoE trade and overlay tools. Design patterns only
(layout, glance density, notices, onboarding, settings, updates) from 30
tools and modules in 9 classes. Features are note 0038, utilities and
settings note 0039, other games' companions note 0055 (planned in
docs/plan/README.md, not written yet). No code, asset or text of any
tool is copied; GPL and NC tools are read for ideas only.
Status: verified

## Sources (accessed 2026-11-18; keys marked (17) on 2026-11-17, local time)

Price-check overlays
- EE2-QS (17) https://kvan7.github.io/Exiled-Exchange-2/quick-start ; same
  site: EE2-FAQ (17) /faq ; EE2-DL (17) /download ; EE2-ISS (17) /issues ;
  EE2-OCR (17) /ocr-guide ; EE2-CHAT (17) /chat-commands ; EE2-XP (17)
  /xp-tracker.html ; EE2-SS /stash-search.html
- EE2-GH (17) https://github.com/Kvan7/Exiled-Exchange-2 (1.2k stars, 176
  open issues) ; EE2-TOP .../issues?q=is%3Aissue+sort%3Acomments-desc
- APT-QS (17) https://snosme.github.io/awakened-poe-trade/quick-start ;
  APT-FAQ (17) /faq ; APT-TOP
  https://github.com/SnosMe/awakened-poe-trade/issues?q=is%3Aissue+sort%3Areactions-%2B1-desc
- SK (17) https://github.com/Sidekick-Poe/Sidekick (516 stars) ; SK-REL
  .../releases ; SK-TOP .../issues?q=is%3Aissue+sort%3Acomments-desc
- XT https://github.com/maxensas/xiletrade ; XH
  https://github.com/XileHUD/poe_overlay (both GPL family: ideas only)

Overlay-platform apps
- POV (17) https://www.poeoverlay.com/ ; POV-FAQ (17) /faq ; POV-CL (17)
  /changelog/poe-overlay-ii ; POV-OW
  https://www.overwolf.com/app/kyusung4698-poe_overlay_ii
- P2K https://www.overwolf.com/app/poe2k-poe2k ; MOBA
  https://mobalytics.gg/llms.txt
- OW-DEV https://dev.overwolf.com/ow-electron/reference/Overwolf-electron-APIs/overlay/Overview

Trade-whisper managers
- ST (17) https://github.com/zmilla93/SlimTrade ; ST-REL .../releases
- MT (17) https://github.com/Morph21/MercuryTrade-Community-Fork
- PL (17) https://github.com/C1rdec/Poe-Lurker ; PL-CS
  .../blob/main/assets/CheatSheet.md

Levelling and campaign helpers
- EUI-W (17) https://github.com/Lailloken/Exile-UI/wiki ; same wiki:
  EUI-ACT /Act%E2%80%90Tracker ; EUI-MAP /Map%E2%80%90Tracker ; EUI-SC (17)
  /Screen-checks ; EUI-MI /Map-info-panel ; EUI-SS /Search-strings ;
  EUI-SN /Stash%E2%80%90Ninja ; EUI-REL (17)
  https://github.com/Lailloken/Exile-UI/releases ; EUI-TOP
  .../issues?q=is%3Aissue+sort%3Acomments-desc
- QUTM (17) https://github.com/Vyary/qutm ; EC (17) https://exilecompass.com/
- POL2-DL (17) https://kami-guru.github.io/path-of-levelling-2 ; POL2-QS
  (17) /quick-start
- EXP https://www.pathofexile.com/forum/view-thread/3934202 (2026-05-29)
- PLO https://poe-leveling-overlay.pages.dev/
- SNIP-POL2: search-result summary of an r/PathOfExile2 thread about POL2
  (thread id 1jqz0i8); three mirrors refused the fetch, date not confirmed.
  UNVERIFIED hints only.

Trackers, build views, build sites, filters, crafting
- TX (17) https://github.com/dermow/TraXile ; DILLA
  https://doofdilla.github.io/dillapoe2stat
- POB https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2 (1.9k
  stars, 136 open issues)
- NINJA-B https://poe.ninja/posts/launching-builds ; NINJA-BP
  https://poe.ninja/posts/poe2-build-planner-prototype
- PBB https://pobb.in/ ; EXB https://exiles.build/ ; MAXR
  https://maxroll.gg/poe2/news/poe2planner-character-import-feature
- FB https://www.filterblade.xyz/?game=Poe2 ; P2F https://poe2filter.com/
- COE https://www.craftofexile.com/?game=poe2 ; DBT
  https://poe2db.tw/us/Tools (community list: 26 entries, 9 groups)

Repository (read 2026-11-17 / 18): research 0001, 0006, 0023, 0026, 0038,
0039, 0052; decisions 0003, 0013, 0014, 0017, 0029, 0030, 0031, 0033,
0038, 0041, 0045; design 0001; the code cited as path:line.

## Summary

- The field's norm is an overlay the player can click, an item copy the
  tool triggers itself, trade-site queries and chat commands. Read
  literally, all four are outside the floor (the overlay must be
  click-through; no input; no trade-site call); AshLight has none and
  should not (F2, F3, Rejected).
- What transfers is pattern-level. Eight changes: a setup card that ends
  first run on one tab (R1), a chooser for what the overlay shows plus a
  sample card (R2), lines that say when a part is off (R3), the vendor
  search string shown in town (R4), a waystone card the player can tune
  (R5), update wording on top of note 0052 (R6), a four-page player guide
  (R7), an optional peek key (R8).
- Players complain about install, platform, start-up and fetch failures:
  none of the 15 most-commented EE2 issues asks for a feature (F8).
- Two PoE2 tools are dark today for lack of GGG account APIs, and one
  toolkit switched off three screen-read automations after GGG's reworded
  policy (F3). Both back the floor as written.
- AshLight alone gives a build-aware verdict on a press, states a
  no-input posture in plain words, and runs a second-screen page that
  rearranges itself (last section).

## Current state

- Windows: an overlay of 2 HUD lines and a 3-line card (trade or item
  check; app/overlay/index.html:13-27), 280 x 176 DIP base
  (app/shared/layout.js:35), 6 corners, default top-right, scale 0.95-2.0,
  opacity 0.9-1.0 (layout.js:24-31); it never takes a click (CLAUDE.md
  floor; design 0001 section 10). A companion window and a tray with 4
  items (app/client/tray_menu.js:13-19); closing goes to the tray with a
  one-time note (app/client/window.js:225-229). A dashboard of 5 tabs
  (web/index.html:41-52); Play shows itself on news after a 10 s grace
  (web/tabs.js:43).
- Data: Client.txt after one opt-in card that prints the found path
  (index.html:69-82; found through the Steam library list,
  server/al/logfile.py:10-19, 91); the clipboard once per Alt+Shift+E
  press (app/main.js:396-403; default keys main.js:33-34); web data off
  until ticked (index.html:440-448).
- Notices: no sound, toast or modal (design 0001 sections 2, 7.1); at
  most 5 open trade cards, gone after 600 s (server/al/state.py:28, 31);
  the item card stays 20 s (state.py:35); a tab mark and one polite line
  carry news (index.html:53-55).
- Onboarding: the consent card, per-card empty states (index.html:174-177)
  and a footer list of what AshLight does and never does
  (index.html:606-627). The other first steps sit on three more tabs:
  build paste (368-371), web data (440-443), overlay position in a fold
  (543-565).
- Settings: the two keys change only in the settings file
  (index.html:176-177, 515-516); 14 self-checks plus 2 conditional rows
  and a redacted Copy report (server/al/diag.py:226-234;
  index.html:526-540). The waystone rules are 11 fixed entries
  (server/al/theorycraft/waystone.py:44-86); the card names at most 3
  mods (state.py:360, 417-419).
- Updates: VERSION = "0.1.0" (server/al/__init__.py:7), no remote, no
  release; /api/version feeds only the data credit (web/app.js:1103). No
  version line, update check or change list in web/ or app/.

## Findings

### F1. The tools

Per tool: glance, window, data and posture, first run, notices, voices.
"Outside our floor" marks a technique AshLight must never use; it is
recorded as that and nothing else.

A. Price-check overlays

- A1 Exiled Exchange 2 (PoE2, MIT). Glance: the item's stats as ticked
  filters with editable ranges; the tool says it does not decide the
  price (EE2-QS). Window: a transient price window (hold Ctrl to keep it,
  or a second key that stays) and a widget layer on Shift+Space (EE2-QS)
  with the settings behind a cog (EE2-FAQ). Data: clipboard item text,
  trade-site queries, poe.ninja (EE2-GH). Outside our floor: it presses
  keys itself (its FAQ says the clip key is pressed by the tool on every
  price check), sends chat commands, pastes saved text into the game's
  search bar and scrolls stash tabs on Ctrl+wheel (EE2-FAQ, EE2-CHAT,
  EE2-SS, EE2-QS);
  the trade site is not ours to call (decision 0017). An optional widget
  reads the screen once per key press (EE2-OCR). First run: installer;
  Windowed or Windowed Fullscreen only; 9 game languages; an unsigned-app
  warning; one named download place against fakes (EE2-DL). Voices: F8;
  324,973 Windows installer downloads of v0.16.3 (research 0039).
- A2 Awakened PoE Trade (PoE1, MIT; parent of A1). Same keys, window
  model and six-page docs (APT-QS, APT-FAQ). Voices: never search
  automatically, add a manual button (#314, closed 2021-02-19); bring
  back a removed price option (#1694, opened 2025-11-07, 14 thumbs-up);
  the tool takes focus from the game on Linux (#1428, opened 2024-08-04)
  (APT-TOP).
- A3 Sidekick (PoE1 and PoE2, MIT). Price check and dangerous map
  modifiers; a desktop window that hides to the tray, an overlay view
  with its own navigation bar, a web mode with no login (SK, SK-REL).
  Outside our floor: the tool copies the item itself (on KDE Wayland it
  asks for the desktop's Remote Control permission to do so, SK);
  trade-site data. Notices: releases of 15 Nov 2026 shrank the API
  status, hid it until the first request and, on Linux, made a failed
  copy say why (SK-REL). Voices: Traditional Chinese (#274, 17 comments,
  closed 2026-03-01); keeps not responding (#904, closed 2026-07-22);
  first launch fails (#444, closed 2025-01-02) (SK-TOP).
- A4 Xiletrade (GPL): price-check helper with a languages file, portable
  archive and web installer (XT); feature list not on the page read.
- A5 XileHUD (GPL-3.0). Modifier data for the copied item, a levelling
  guide, a campaign-reward helper; three view modes down to a
  click-through minimal one; a feature selector that turns modules off;
  tray. Outside our floor: its key triggers the game's copy. Pick the
  game once at first launch; updates download silently and apply at
  exit; unsigned-app warning (XH).

B. Overlay-platform apps

- B1 PoE Overlay II (PoE2; platform store or standalone; ads and a paid
  tier). Price check with a model estimate, campaign guide, stash
  tracker, market browser (POV). Outside our floor: optional ads and a
  Premium tier (monthly, yearly, 60-day league pass) on GGG-derived
  features (POV-FAQ), and a platform whose reference speaks of an overlay
  it injects at game launch (OW-DEV; how the PoE build attaches is
  UNVERIFIED). Its OAuth sign-in (POV-FAQ) is a documented route, closed
  to AshLight while registration is closed (F3; decision 0045 keeps a
  no-request stub for it). Notices: 1.68.0
  (2026-10-03) tells the player when the overlay or auto-launch is
  disabled; 1.69.0 (2026-10-23) helps when the wrong game is detected;
  1.64.0 (2026-09-07) added maps done, maps an hour and average time;
  1.62.0 (2026-09-03) fixed hotkey errors that were not shown (POV-CL).
  Voices: 3.8 of 5 from 81 ratings, 2.26M downloads; reviews of 1-16 Nov
  2026 are short praise; one player with two monitors says checking the
  trade site by hand was workable but the overlay made sorting drops much
  easier (POV-OW), a point for in-game glance, not for a second screen.
- B2 PoE2K (platform store, ads): a floating trade panel, one-click copy
  of a trade message, compact to full search windows, a desktop mode.
  3.5 of 5 from 4 ratings; two of four visible reviews are negative (did
  not work; crashes and ads) (P2K). How it reads chat: UNVERIFIED.
- B3 Mobalytics desktop app (platform-built, Windows): for PoE2 a build
  tracker that detects the stage of a build and suggests next steps; a
  paid tier (MOBA). Overlay details for PoE2: UNVERIFIED.

C. Trade-whisper managers

- C1 SlimTrade (PoE1 and PoE2, MIT). One popup per trade, a stash helper,
  chat scanner, history rebuilt from the client file even when the app
  was closed; themes, fonts, custom sounds (ST). Outside our floor: reply
  buttons and search buttons that paste into the game. 0.6.6 and 0.6.7
  added a preview for stash alignment; 0.6.5 fixed crashes of its
  patch-notes window (ST-REL; June 2025 per research 0006).
- C2 MercuryTrade community fork (PoE1, MIT). A notice panel with
  hotkeyable reply, invite, kick and trade buttons; notices collapse into
  a group past a set limit; an ignore list for sold items; do-not-disturb;
  patch notes at launch; not for fullscreen (MT). Outside our floor: the
  buttons by their function, and a part that mirrors a screen region.
- C3 PoE Lurker (PoE1, MIT, paid extras). Offers as tiles: first click
  invites, second asks for the trade, corners for busy and dismiss; an
  update icon on a HUD element (PL-CS). Outside our floor: each of those
  sends a command; it credits a thread-level hook library (PL; mechanism
  UNVERIFIED). Builds are signed through a free program for open source.

D. Levelling and campaign helpers

- D1 Exile-UI Act-Tracker (MIT). A guide panel on the bottom edge: each
  line a step, hints indented in smaller type; the page turns when the
  player enters the place the last line names; previous / next buttons
  and a fast-forward; an optional timer that pauses when unfocused and
  after 10 s away; switches for league start and optional content
  (EUI-ACT). First run: 6 steps with a script runtime; two keys; settings
  sections with help and wiki links (EUI-W). Outside our floor: screen
  checks, key sending, resizing the game window (EUI-W, EUI-SC). Guide
  data is re-issued per patch and applies only on a guide reset
  (EUI-REL). Voices: "Resizes game client" (#812, opened 2026-07-24, 24
  comments); "Constant scanning causing lag" (#20, closed 2022-02-24);
  pixel-check trouble (#696, closed 2025-11-05) (EUI-TOP).
- D2 Qutm (PoE2, Apache-2.0). Zone guide and layout widget from
  Client.txt only. First run in 3 steps: pick the log, set the key,
  choose the widgets; updates itself (QUTM).
- D3 Path of Levelling 2 (PoE2). Zone notes, gem setups, an XP panel from
  Client.txt, whose path the player pastes. One key makes the overlay
  interactive; windows are dragged and resized; checks at start,
  installs at the next start; unsigned-app warning (POL2-DL, POL2-QS).
  Voices (SNIP-POL2, UNVERIFIED): the top request was to show only while
  the game is the active window; then on-screen controls and log
  auto-detection; windows dragged off-screen were lost.
- D4 ExileXP (PoE2, forum post 2026-05-29). A corner window with this
  zone's tasks, a gem panel per act, per-act vendor search strings with
  one-click copy, a slot per character, a catch-up button; Client.txt
  only; keys to hide and to toggle click-through; hides on Alt+Tab;
  tray; no account, no telemetry; unsigned-app warning (EXP).
- D5 PoE Leveling Overlay (PoE1; PoE2 announced). Auto-advancing guide, a
  picker that scans the Path of Building save folder, a regex helper
  shown in town. First run: the log is found alone with a Browse
  fallback, pick a build, type one local chat line to link the character
  (PLO).
- D6 Exile Compass: quest and act tracking, gem rewards, regex creator,
  speedrun timer with act splits (EC). Data source not stated.

E. Map and session trackers

- E1 Exile-UI Map-Tracker and Map-info (EUI-MAP, EUI-MI). Tracker: a
  bottom-edge panel hidden while mapping, shown while a key is held; the
  timer follows the instance; CSV export; a search field per column; its
  wiki keeps kill counts manual because automating them would break
  GGG's terms. Map-info: mods grouped by who they affect, sorted by a
  4-step rank the player sets by hovering a mod and pressing 1-4, pinned
  build-specific mods, a summary line (count, quantity, rarity, pack).
- E2 TraXile (PoE1, MIT). Client.txt only: a sidebar app with a live
  timer against the player's average, activity log, one global filter,
  tags with sounds, two small overlays; control by chat lines the player
  types and the tool reads back; checks for a new version at start and
  hourly, with an update button in the title bar (TX).
- E3 DillaPoE2Stat (PoE2). Loot per map from account inventory
  snapshots, local pages for stream overlays, desktop toasts. Its page
  says it does not work now because GGG disabled inventory API access;
  setup edits a config file (DILLA).

F to I. Build views, build sites, filter editors, crafting helpers

- F1 Path of Building for PoE2 (MIT): a stat sidebar beside tree, skill
  and item planners, a calculations breakdown tab, share codes; updates
  itself in seconds (POB). Its update dialog was not found: UNVERIFIED.
- G1 poe.ninja builds: lists with the share of characters using each
  class, item and keystone; a click filters, a second control excludes;
  tree heatmap; column chooser; pages with gear, gems and PoB-simulated
  stats (NINJA-B); a `.build` export with a switch per section
  (NINJA-BP). G2 pobb.in: paste a code, get a page (PBB). G3 Maxroll
  planner: imports own characters after an account login (MAXR). G4
  exiles.build: hibernating until GGG reviews OAuth applications (EXB).
- H1 FilterBlade: an Overview / Get-started tab, then "Auto-Adjust for
  build" (it starts from the player's class and character) before the
  detailed customise tabs; a strictness setting that sets how much shows;
  a 3-step export (name, export, finish) by one-time account sync, paid
  automatic sync or download (FB). H2 poe2filter.com:
  presets first, then quick filters with a tutorial; sync, a save
  straight into the game's folder with standing browser access, download
  or copy (P2F).
- I1 Craft of Exile: Calculator, Simulator and Emulator tabs; left click
  requires a mod, right click blocks it; an import button (COE). I2 EE2
  stash search and Exile-UI Search-strings: named presets, plain names in
  place of regex, a key per entry; both paste into the game, outside our
  floor (EE2-SS, EUI-SS). I3 Exile-UI Stash-Ninja: price tags laid over
  fixed-layout stash tabs, aligned by a hand-tuned gap (EUI-SN).

### F2. Window model

13 of the 14 desktop overlays read in detail (A1-A3, A5, B1, B2, C1-C3,
D1-D5) take clicks, always or after a key; D2 does not say. 4 state a
Windowed or Windowed Fullscreen requirement (A1, C2, D1, D3), AshLight's
mode. Depth on a separate page or window exists in 4 (E2, E3, B2 desktop
mode, A3 web mode); none has a guarded second-screen page as its main
surface. AshLight's overlay can never be clicked: safe in a fight, and it
costs one-screen players the detail (note 0038 F2).

### F3. Posture

At least 8 of those 14 send input to the game (A1, A2, A3, A5, C1, C2,
C3, D1). D1 switched off three screen-read features (a continuous scan
while a key is held, an auto-hide, automatic overlay repositioning) in
v1.65.3 / v1.65.4 (12-13 Nov; the year is not printed on the release
page, 2026 per research 0026) after GGG's reworded policy, and now calls
older releases use at your own risk (EUI-REL). Client.txt only: D2, D3, D4, E2, and D5
plus the player's own build files. Account APIs: B1, A5 (one feature),
E3, G3, G4; of these E3 is dark because inventory access is disabled and
G4 is hibernating until OAuth reviews resume (read 2026-11-18), so
decision 0045's no-request stub is the right shape. No surveyed tool
claims memory reading (that class: research 0006), and none but AshLight
pairs a log-only, no-input posture with item checks.

### F4. First run

Shortest: D2 and H1 in 3 steps, D5 in 3 plus an optional one. Longest: D1
with a runtime install and per-feature calibration. Log path: found alone
with a Browse fallback (D5), picked (D2), pasted (D3, complained about),
a config file (E3). AshLight finds it alone and asks consent first, the
strictest of the set, yet spreads its other first steps over 4 tabs. 4
tools tell players to click through the Windows unsigned-app warning (A1,
A5, D3, D4); one is signed (C3).

### F5. Notices

Sound or toast: C1, E2, E3. Stacking: C2 groups past a limit; AshLight
caps at 5 and expires at 600 s. The newest releases move toward quieter
status (A3) and toward telling the player when the tool itself is off
(B1). AshLight folds its checks while green (index.html:526-531) but has
no line for an overlay the player switched off (web/app.js:989-990
covers only the idle hide).

### F6. Settings and language

Every surveyed overlay whose docs were read rebinds keys in a settings
screen. The file edits that remain are flagged by their own docs as a
trouble spot (A1: without a hand-edited window-title key in config.json
it opens only for PoE1, EE2-DL) or sit in a script config (E3). AshLight's keys and 11 of its 14 settings need the file (note
0039). Tuning in place exists in E1 (rank a mod where it is shown) and A1
(edit a range in the price window); AshLight tunes weights on another tab
and waystone rules not at all. A1 handles 9 game languages; AshLight
reads English logs and says so (decision 0040).

### F7. Updates

Installed builds update themselves: A1 (installer yes, portable no, a
flag turns it off), D3 (check at start, install at next start), A5
(applied at exit), D2, E2, F1, B1. Change lists: C2 shows patch notes at
launch and C1 had to fix crashes of its patch-notes window; D1 keeps
announcements in an updater section; B1 lists its game-data version apart
from the app version; A3 cuts releases that carry only refreshed data.
AshLight has no update path yet; note 0052 R6 designs one.

### F8. What players complain about

The 15 most-commented EE2 issues (EE2-TOP): 6 Linux or macOS overlay and
key problems (#673 opened 2025-09-11, 40 comments; #299; #820; #513;
#349; #793), 3 trade or league fetch failures (#13, 45 comments; #910
opened 2026-06-05, 35; #101), 2 install or crash loops (#575 opened
2025-08-31, 35; #779 opened 2025-12-18, 35), 2 side effects of the
triggered copy (#124; #338 opened 2025-01-21, 21), 2 localisation tasks
(#69, #66). Its common-issues page adds a graphics utility that silently
flips the game to Fullscreen and a second instance that starts and does
nothing (EE2-ISS). A3's list has the same shape, plus a package manager
offering another vendor's product of the same name as an upgrade (#1277,
closed 2026-11-16, SK-TOP).

### F9. Small defect found

A failed registration of the show / hide key is only logged
(app/main.js:392-394); the hotkey check reads only the item-check line
(server/al/diag.py:316-334), so Checks stays green while Alt+Shift+A does
nothing. B1 fixed the same class of silent failure in 1.62.0 (POV-CL).

## Recommendations

### Adopted patterns (pattern - where it goes in AshLight - source - access date)

- P1 Three-step first run (find the log, set the key, choose what shows)
  - Play setup card, R1 - https://github.com/Vyary/qutm - 2026-11-17.
- P2 Preset first, detail later (auto-adjust from the class, customise
  after) - setup card row 2 and the weights card, beside note 0038 R1's
  default-weights path -
  https://www.filterblade.xyz/?game=Poe2 - 2026-11-18.
- P3 Per-part show / hide and density modes - Settings "Overlay shows",
  R2 - https://github.com/XileHUD/poe_overlay - 2026-11-18.
- P4 A preview beside the setting - sample card button, R2 -
  https://github.com/zmilla93/SlimTrade/releases - 2026-11-18.
- P5 The tool says when one of its own parts is off - Play line and a
  Checks row, R3 - https://www.poeoverlay.com/changelog/poe-overlay-ii -
  2026-11-17.
- P6 A press that fails says why - item card error lines, R3 -
  https://github.com/Sidekick-Poe/Sidekick/releases - 2026-11-18.
- P7 Search strings shown where they are used, by a plain name, one click
  to copy - Play zone tile in towns, R4 -
  https://www.pathofexile.com/forum/view-thread/3934202 - 2026-11-18.
- P8 Mods grouped and ranked with a reward summary, the rank set where
  the mod is shown - waystone part of the item card, R5 -
  https://github.com/Lailloken/Exile-UI/wiki/Map-info-panel - 2026-11-18.
- P9 Quiet update: check alone, apply at next start, changes listed in
  the settings area, game-data version shown apart - Settings tab, R6 -
  https://kami-guru.github.io/path-of-levelling-2/quick-start -
  2026-11-17.
- P10 A four-page player guide with "is it allowed" among the first three
  answers and one named download place - docs and README, R7 -
  https://kvan7.github.io/Exiled-Exchange-2/faq - 2026-11-17.
- P11 Signed builds through a free signing program for open source - note
  0053 - https://github.com/C1rdec/Poe-Lurker - 2026-11-17.
- P12 One sentence at the log opt-in on what is kept and for how long -
  consent card (index.html:73-77), R1 -
  https://kvan7.github.io/Exiled-Exchange-2/xp-tracker.html - 2026-11-17.
- P13 A build from a save file the player picks, the same bytes as a
  paste - Build tab beside the paste box, later (Open question 2) -
  https://poe-leveling-overlay.pages.dev/ - 2026-11-18.

Validated, already in AshLight (no work): close to tray with a one-time
note (A3; window.js:225-229); progress per character from the log (D4;
decisions 0038, 0045); timers that stop when away (D1; decision 0029);
checks folded while green (A3); history rebuilt from the log after a
restart (C1; decision 0008); map numbers as a small fixed set (B1; note
0038 R6). (The draft also counted a B1 review as backing a second screen
for judging drops; re-read, that review credits the in-game overlay, so
it is struck.)

### R1. Setup card: finish first run on the Play tab

- Action: replace the consent card with one "Set up AshLight" card of 4
  rows with state glyphs: 1 allow reading Client.txt (the existing button
  and words, plus P12), 2 your build (paste here), 3 prices (web data and
  contact), 4 overlay (corner, sample card, the two keys and whether each
  registered). Done rows fold; the card leaves when row 1 is done and the
  rest are done or skipped.
- Impact: H. First run drops from 4 tabs to 1 (F4, P1, P2).
- Effort: M. Risk: Play must fit without page scroll (design 0001
  section 4): the card replaces the consent card, it does not add one.
- ToS check: floor rule "Client.txt tailed only after the user's opt-in,
  with a visible indicator": row 1 is that opt-in, unchanged; rows 2-4
  read nothing new; web data stays OFF until ticked (decision 0013).
- Depends on: notes 0038 R3 / 0039 R2 (contact field), 0039 R3 (keys in
  the snapshot), R2 (sample card), the design reviewer.
- Files likely touched: web/index.html, web/app.js, web/status.js,
  web/app.css, server/al/state.py, app/test/dashboard.test.js.
- Acceptance test: a cold profile shows the 4 rows and nothing else on
  Play; after row 1 the feed is live and rows 2-4 can each be done or
  skipped without leaving Play; the card then goes; at most 12 live
  regions; no page scroll at 1280x760.
- ZERO-CLICK: one required click (the opt-in the floor demands); the
  other rows are optional and clear themselves when their data arrives.

### R2. Overlay parts chooser and a sample card

- Action: a Settings group "Overlay shows" with switches for HUD line 1,
  HUD line 2, trade card and item card (and note 0038 R2's zone and act
  cards), two presets (Full, Cards only), and a "Show a sample card for
  10 s" button beside the position form.
- Impact: M to H. 5 surveyed overlays offer per-part choice (P3); the HUD
  lines mostly repeat the game's own UI (note 0038 F2) and the default
  corner covers the corner map (design 0001 section 10).
- Effort: S to M. Risk: a hidden HUD hides "AshLight offline"; a failure
  word must still show.
- ToS check: floor rule "separate transparent, always-on-top,
  click-through, non-focusable window ... must not cost game FPS": the
  window is unchanged and paints less; the sample is AshLight's own text,
  with no screen read and no input.
- Depends on: a design 0001 section 10 amendment (content cap wording).
- Files likely touched: app/shared/layout.js, server/al/layout.py,
  app/shared/render_gate.js, app/overlay/overlay.js, web/index.html,
  web/app.js, app/test/layout.test.js, tests/test_budgets.py.
- Acceptance test: with Cards only the overlay is empty until a card or a
  failure word; Python and JS normalize() agree on the new keys; the
  sample shows for 10 s and enters no history; budget tests stay green.
- ZERO-CLICK: the default stays Full; a set-once choice saved on change.

### R3. Say when a part is off

- Action: a Checks row for the show / hide key like the item-check one
  (F9), and one Play line while the player has the overlay switched off
  ("Overlay off - Alt+Shift+A shows it"), fed by the client telling the
  core through the local token API the item press already uses.
- Impact: M. Silent failure is the largest complaint class (F8, P5, P6).
- Effort: S. Risk: one more snapshot field.
- ToS check: floor rule "never send input to the game": the client only
  reports its own window state to its own core; no game read is added.
- Depends on: none; fold into note 0039 R3 if that lands first.
- Files likely touched: app/main.js, app/overlay_gate.js,
  server/al/diag.py, server/al/state.py, server/al/http.py, web/app.js,
  web/index.html, app/test/checks.test.js.
- Acceptance test: an overlay log holding "toggle shortcut not available"
  yields a failing row with a fix line; switching the overlay off flips
  the snapshot field and the Play line within one update; no new preload
  action (decision 0041).
- ZERO-CLICK: both lines appear and clear by themselves.

### R4. Town moment: the vendor search string on Play

- Action: while the log places the player in a campaign town or the
  hideout and a build is loaded, the Play zone tile shows the top search
  string by a plain name with a Copy button; the Build tab list stays.
- Impact: M in the campaign. The string is a tab and 2 clicks away today
  (index.html:403-407); 3 levelling tools show it in town (P7).
- Effort: S. Risk: Play height; one row, hidden outside towns.
- ToS check: decisions 0014 and 0030: the clipboard is written only on
  the player's click; floor rule "never send input": the player pastes.
- Depends on: the town flag of the cached area snapshot
  (server/al/zoneguide.py:133-156); shares strings with note 0039 R13.
- Files likely touched: web/app.js, web/search.js, web/zoneguide.js,
  web/index.html, server/al/state.py, app/test/search.test.js.
- Acceptance test: a replayed log entering a town shows the row and
  leaving hides it; no build, no row; Copy writes the exact string, which
  stays within the game's 250-character limit.
- ZERO-CLICK: shows and leaves with the zone; Copy is the one click the
  clipboard rule requires.

### R5. A waystone card the player can tune

- Action: list every risky mod (not 3 "and N more") above the reward
  line, and give each rule a three-way switch on the card (auto, always
  warn, never warn) saved in the settings.
- Impact: M while mapping. The 11 rules are fixed; a player who out-gears
  a mod cannot quiet it and one who fears a mod cannot raise it (P8, F6).
- Effort: S to M. Risk: "never" hides a real danger; the card shows the
  count of silenced rules.
- ToS check: floor rule "clipboard ... once per manual press": the same
  press and text; the switches are local settings.
- Depends on: note 0038 R4 (real waystone samples).
- Files likely touched: server/al/theorycraft/waystone.py,
  server/al/state.py, server/al/settingsio.py, web/tc.js,
  tests/test_waystone.py, app/test/tc_view.test.js.
- Acceptance test: a text with 5 risky mods lists 5; a rule set to never
  drops out and the card says "1 rule silenced"; a rule set to always
  warns at capped resistance; the overlay card keeps 3 lines of 34
  characters.
- ZERO-CLICK: defaults unchanged; tuning is optional and saved on change.

### R6. Update wording on top of note 0052 R6

- Action: three display rules for the update path that note designs: the
  notice is a Settings tab mark and one line, never a window; the change
  list is a fold of the last 3 versions, written for players; Settings
  shows "AshLight <version>" and "game data from <date>" on two lines.
- Impact: M now, H at go-public: a tool tied to a log format that may
  shift on 2026-12-11 must be able to say "update me" (F7, P9).
- Effort: S once 0052 R2 and R6 exist. Risk: none.
- ToS check: decision 0013: no request while web data is off; floor rule
  "truthful User-Agent naming AshLight and its version" for the check.
- Depends on: note 0052 R2 and R6; a public release (operator act).
- Files likely touched: web/index.html, web/checks.js, web/app.js,
  server/al/state.py.
- Acceptance test: a snapshot with an update entry marks the Settings tab
  and prints one line, with no dialog and no focus change; with web data
  off a fake transport records 0 calls.
- ZERO-CLICK: the notice arrives by itself; applying follows 0052 R6.

### R7. A four-page player guide

- Action: Download, Quick start, Common issues and FAQ pages built from
  the footer promise list and the Checks fix lines. The FAQ answers "Is
  it allowed? Can I be banned?" first and honestly: no tool is approved,
  and here is what AshLight does and never does. README and About name
  the one download place.
- Impact: M at go-public (P10; F8 shows where the questions come from).
- Effort: S to M. Risk: wording that sounds like an endorsement.
- ToS check: floor rules on branding: every page carries the
  non-affiliation line, uses no GGG art and never says GGG approves or
  authorises AshLight.
- Depends on: notes 0057 (go-public; planned, not written yet) and 0053
  (where downloads live).
- Files likely touched: docs/ (new player pages), README.md, app/about.js.
- Acceptance test: the four pages pass the ASCII and leak tests, each has
  the disclaimer, and one test finds the same download place in the
  README, the FAQ and About.
- ZERO-CLICK: reading is optional; nothing in play depends on it.

### R8. Peek key for one-screen players (optional)

- Action: an optional third AshLight key that shows the companion window
  at a compact size on the game's monitor and hides it on the next press.
- Impact: L to M. 13 of 14 surveyed overlays work on one screen (F2).
- Effort: S. Risk: focus leaves the game while the window is up (the
  player's own key press), and the game may apply its own background
  frame cap then (UNVERIFIED for PoE2; Open question 3); a third global
  key.
- ToS check: the overlay stays click-through and non-focusable (floor);
  the companion is AshLight's own ordinary window (decision 0041); the
  press reads nothing and sends nothing; hiding acts on AshLight's window
  only and never queries or activates the game window (decision 0029
  amendment).
- Depends on: note 0039 R3 (key handling) and Open question 3.
- Files likely touched: app/main.js, app/client/window.js, app/hotkey.js,
  server/al/hotkeys.py, app/test/client.test.js.
- Acceptance test: node test - one press shows, the next hides, a held
  key does not repeat; the handler makes no clipboard or screen call;
  unset by default.
- ZERO-CLICK: off by default; one press when the player wants detail.

## Cut or merge

- Merge R3 into note 0039 R3 when both run; R4 and note 0039 R13 share
  one string list; R1 hosts the contact field of notes 0038 R3 / 0039 R2;
  R6 is the display half of note 0052 R6.
- Do not grow the trade cards (agrees with note 0038): every trade
  manager rests on reply buttons AshLight may never have (C1-C3).
- Do not add a second filter tool: both editors sync to the account or
  save where AshLight will not write (H1, H2; note 0039 F15).

## Rejected

- A copy key the tool presses (A1, A3, A5); reply, invite, trade-request
  and hideout buttons (A1, C1-C3); pasting a search string into the
  game's box (A1, D1, C1): floor, no input. AshLight copies on a click
  and the player pastes.
- Trade-site listings and model estimates trained on them (A1-A3, B1):
  floor and decision 0017.
- Screen reads that run or react by themselves, screen-region mirrors and
  per-feature screen calibration (D1, C2): floor (one read per press); D1
  itself switched three off; calibration is upkeep every patch.
- Price tags drawn over stash tabs (I3): clutter, hand-tuned offsets
  (upkeep), and the content cap of design 0001 section 10.
- An overlay layer that takes clicks after a key (A1, A5, D3, D5): floor
  wording (click-through, non-focusable); R8 is the answer inside it.
- Hiding the overlay unless the game is the foreground window (D4;
  SNIP-POL2): settled, decision 0029 amendment (Open question 1).
- Platform overlay infrastructure, ads and paid tiers (B1-B3): floor (no
  injection; no revenue from GGG-derived features).
- Account sign-in features: stash tracking, inventory snapshots,
  character import (B1, A5, E3, G3, G4): registration is closed and two
  such tools are dark (F3); decision 0045 already keeps the stub.
- Sounds and desktop toasts (C1, E2, E3): clutter; design 0001 principle
  3. A patch-notes window at launch (C1, C2): clutter; R6 uses a fold.
- Saving a filter into the game's folder or by account sync (H2, H1):
  settled decisions 0031 and 0033.
- Commands typed into local chat and read back from the log (E2, D5):
  clutter (other players see the line) and upkeep.
- An XP multiplier number (A1; D1 calls the PoE2 formula unknown):
  rejected in note 0038 (research 0028 ruling B).
- Data-only releases (A3): upkeep; AshLight fetches at run time under the
  one opt-in (decision 0026). Themes by the dozen (C1): upkeep against
  the measured contrast pins of design 0001.
- Free dragging of every widget (D3: windows lost off-screen): clutter;
  corners only (design 0001 section 10).
- Hook libraries and resizing the game window (C3, D1): floor.
- A web mode with no login on a published port (A3): CLAUDE.md keeps
  127.0.0.1 and the per-start token.

## Open questions

1. Foreground hide. The field treats "show only while the game is in
   front" as basic (D4, SNIP-POL2). Decision 0029's amendment bars the
   window check unless the operator permits it in writing. Needs an
   operator decision; the evidence here does not meet the clause alone.
2. A watched Path of Building save folder (D5's picker) would end the
   "paste a fresh code" nag with no click, but the floor lists what may
   be read and that folder is not on it. Needs an adjudicator ruling; the
   file-pick form (P13) follows decision 0033 and needs none.
3. R8: does Windows hand focus back to the game every time the companion
   hides? Needs a live test with the operator; whether the key is wanted
   at all is an operator taste call.
4. The share of one-screen players is unknown and AshLight keeps no
   telemetry by design; R8 and note 0039 R13 are judgement calls.
5. Left UNVERIFIED: how B1's standalone build and B2 read item and chat
   data; F1's update dialog; the date of SNIP-POL2.

## Three and three

The best tools do, AshLight does not:
1. Update themselves and need no file edit: installed builds of A1, A5,
   D2, D3, E2, F1 and B1 update alone and every key is set in a settings
   screen (F6, F7). AshLight has no release and keeps its keys in a file
   (notes 0052 R6, 0039 R3; R1 and R6 here).
2. Work on one screen: the overlay itself takes clicks for the guide,
   settings and searches (F2). AshLight's never can, by the floor (notes
   0038 R2, 0039 R13; R2 and R8 here).
3. Price a rare in one press with listings or an estimate (A1-A3, B1).
   That rests on a triggered copy and the trade site, both outside the
   floor: the gap stays, and AshLight answers with a verdict and a link.

AshLight does, they do not:
1. A verdict against the player's own build on the press, with Path of
   Building's own DPS and EHP change, and waystone risk read from the
   build's numbers. The price overlays show filters and say they do not
   decide (EE2-QS); the nearest rival is an experimental, calibrated
   module of D1 (EUI-REL, v1.65.1).
2. Send nothing to the game and say so on the page: an explicit log
   opt-in with a visible state, a does / never list
   (index.html:69-82, 606-627), web data off by default. At least 8 of
   14 desktop tools send input (F3).
3. A guarded second-screen page that rearranges itself with no click and
   rebuilds its session memory from the log (death list, act splits, map
   ladder, run history, last session). The closest are E2 (PoE1, typed
   chat commands), E3 (dark) and A3's web mode (no login).

## Verification

Independent verifier, 2026-11-18 (local time).

Checked:
- Code: 33 path:line citations opened (overlay HTML, layout.js, tray
  menu, window.js, tabs.js, logfile.py, main.js, state.py, diag.py,
  waystone.py, zoneguide.py, __init__.py, app.js, 15 ranges of
  web/index.html); all hold. F9 confirmed: app/main.js:392-394 only logs
  "toggle shortcut not available", and server/al/diag.py:316-334 scans
  only for "item check shortcut not available". The 14 + 2 check rows
  (diag.py:228-234) and 11 waystone rules (waystone.py:44-86) counted.
  All 23 files named under "Files likely touched" exist.
- Cross-references: notes 0038 R1-R6, 0039 F1 / F15 / R2 / R3 / R13 and
  0052 R2 / R6 exist and say what this note relies on; 0055 and 0057 are
  planned only (now labelled).
- Web: 24 sources re-fetched 2026-11-18: EE2 issue list (the 15
  most-commented, F8's 6 / 3 / 2 / 2 / 2 split and dates hold), EE2
  quick start, FAQ, download, XP tracker; APT issue list; Sidekick repo,
  releases, issue list; XileHUD; PoE Lurker; Exile-UI releases and
  Map-Tracker wiki; PoE Overlay II changelog, FAQ and store page; qutm;
  Path of Levelling 2 download and quick start; ExileXP forum post;
  SlimTrade releases; MercuryTrade fork; DillaPoE2Stat; exiles.build;
  Path of Building PoE2 repo; FilterBlade; poe2filter.com.
- Floor (C): every R1-R8 ToS check re-read against each floor rule; none
  needs input, a watcher, a trade-site call, memory, injection or
  revenue. R8 gained the background-frame-cap risk. Settled decisions
  (D): no recommendation contradicts one; the foreground hide stays an
  operator question under decision 0029.
- Brief (E): all nine tool classes covered; recommendation fields (F)
  complete for R1-R8.

Corrected:
- Summary: all four field norms are outside the floor, not three.
- EE2 installer downloads 324,913 -> 324,973 (research 0039 figure).
- APT #1694: 14 thumbs-up, not 14 comments.
- EE2 window model cited to the quick start (the FAQ does not say it).
- Sidekick copy mechanism worded as the README states it.
- PoE Overlay II: the paid tier and ads are what sit outside the floor;
  OAuth sign-in is documented but closed to AshLight; 1.62.0 dated.
- The B1 "second monitor" review was misread: it credits the in-game
  overlay; struck from the validated list.
- FilterBlade layout and export described from the page (not "six tabs"
  and a "slider"); P2 reworded to match.
- F6: "main source of trouble" softened to what EE2's page says.
- F3: the three Exile-UI features named; the release page omits the year.
- Rejected: "merchant history" removed (not on the POV FAQ).

Still UNVERIFIED: how PoE Overlay II standalone and PoE2K read item and
chat data; how the PoE Overlay II platform build attaches; Path of
Building's update dialog (its README only promises updates in seconds);
the date and content of SNIP-POL2; Mobalytics' PoE2 overlay; whether
PoE2 caps frames while unfocused (R8). Not re-fetched (sampled out, low
decision weight): XT, MOBA, OW-DEV, P2K, PLO, EC, TX, NINJA-B / BP, PBB,
MAXR, COE, DBT, EUI-ACT / SC / MI / SS / SN / W, EE2-OCR / CHAT / SS /
ISS, ST repo page. The file runs past the 500-line target; left as is.
