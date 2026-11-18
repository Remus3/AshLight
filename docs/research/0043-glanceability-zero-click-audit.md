# 0043 - Glanceability and zero-click audit

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B7
glanceability and zero-click. Scope: every click, paste, press, file
pick, tab switch and scroll the player still makes, how far each can go
inside the ToS floor, the scroll and tab audit from the evidence pack, and
glance budgets a test can assert. It also answers MERGE-SEAMS-FOLLOWUP F1.
Usability heuristics, the settings surface and feature cuts are notes
0042, 0039 and 0038; this note cites them instead of repeating them.
Status: verified

## Sources (all accessed 2026-11-18)

- GGG: https://www.pathofexile.com/developer/docs (re-fetched by the
  verifier) - screen or clipboard reads once per manual key press; macros
  invoked by hand, never by a timer, a file change or a screen read, one
  game action each; executable apps that interact with the game or its
  files are prohibited; new OAuth applications are not being processed
  today. The page says nothing about local files other than the game
  log.
- NHTSA: https://www.transportation.gov/briefing-room/us-dot-releases-guidelines-minimize-vehicle-distractions
  - the 2013 voluntary Phase 1 in-vehicle guideline: single glances away
  of 2 s or less on average, 12 s in total per testable task. The release
  page answered 403 to the verifier; the figures are confirmed only
  through search summaries of the release and its press coverage, not
  the guideline text. Used here only as an analogy for a look at a
  second screen during a fight.
- GLANCE: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-113.html
  - "Designing Glanceable Peripheral Displays" (2006, 3 authors). Its
  abstract (re-fetched) defines glanceability as a quick, low-effort read
  that interrupts the primary task as little as possible, and offers a
  taxonomy of visual variables. It does NOT state that the amount of
  information shown sets the reading speed; the draft's claim to that
  effect is withdrawn (verifier correction).
- OCR: https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine
  (re-fetched) - the Windows OCR engine class: a bitmap in, lines and
  words with positions out; part of the Windows API since Windows 10
  build 10240 (UniversalApiContract v1, windows.dll). The recognizer
  languages are those available on the device (AvailableRecognizerLanguages),
  so whether an English recognizer is present on every install is
  UNVERIFIED.
- PACK: the evidence pack, names relative to its directory (README.txt,
  run/summary_lines.txt, run/<state>/dash-<tab>-<W>x<H>.json and .png).
- PROBE: a re-measure made for this note with the pack's own script
  (port 8965, states c, d, f, hidden headless Chrome, synthetic log,
  stopped afterwards; no process left on the port). It adds per-block
  heights and a CSS-only layout prototype injected into the probe page,
  no product file changed. Files: `<sidecar>\Scratch\up-0043\`
  probe-c.json, probe-d.json, proto.js, measure.js.
- POB: the hash-pinned PoB-PoE2 v0.23.1 checkout in the sidecar Cache
  (config/tc_pins.json): src/Modules/Main.lua:87-91 and :849-853 (user
  folder "Path of Building (PoE2)" under the host's user path, builds in
  its "Builds" sub-folder, a custom place in Settings.xml `buildPath`,
  :577-578); Main.lua:82-84 (dev or standalone mode keeps user data next
  to the program instead); src/Classes/PoEAPI.lua:93 (PoB imports a
  character through its own OAuth client, `client_id=pob`). The user
  path comes from the runtime's GetUserPath, which is not in the PoB
  source; that it is the Documents folder is UNVERIFIED. Builds are saved
  as `<name>.xml` (src/Modules/Build.lua:1480).
- Repo: web/index.html, web/app.js, web/tabs.js, web/app.css,
  web/zoneguide.js, app/main.js, app/eval_hotkey.js, server/al/http.py,
  server/al/core.py, server/al/hotkeys.py,
  server/al/theorycraft/{providers,store,buildlive,paste,shareurl}.py,
  scripts/*.ps1, docs/design/0001-design-system.md, decisions 0003, 0013,
  0017, 0041, 0045, research 0033, 0035, 0038, 0039, 0042, 0054.

## Summary

- Play does not fit. It scrolls in 6 of 9 pack states at 1280x760 and 5
  of 9 at 1920x950: worst case 380 px left and 321 px right at 1280x760,
  124 / 117 px at 1920x950; the idle state (d) overflows its left
  column by 541 px at 1280x760 and 311 px at 1920x950.
- One cause carries most of it: the zone tile spans the row and holds the
  guide, so the tile block takes 457 of 654 px while three tiles of 129 px
  hold 2 to 13 words each.
- A CSS-only prototype (58 rules, 2 DOM moves, nothing new shown) brings
  the worst case to 472 px left and 367 px right: 0 px overflow at both
  sizes with 182 px to spare at 1280x760, and 397 words down to 256. The
  idle state fits with 79 px to spare. That is R1.
- Items: today hover, Ctrl+C, Alt+Shift+E: 2 chords, 5 key presses. With
  the clipboard, 2 chords is the floor minimum; a roll under one held
  modifier makes it 3 key presses (R5). One press per item is possible
  only by a screen read on the press, which the floor allows and which
  needs OCR (R7, spike only).
- The build: today 6 acts per build change across two programs. Best
  floor-safe fix: follow the folder Path of Building already saves into
  (R3, zero acts in AshLight after one opt-in). Next: let the existing
  hotkey press load a copied code (R4, 1 chord, no tab). The GGG character
  API stays blocked: registration is closed [GGG].
- Tabs: 5 today; 4 is enough (R6). Only Play is needed during play.
- Budgets for tests: no scroll in Play at the two sizes in 6 states,
  260 words, each top answer in the first view within 6 words (R2).

## Current state

Shell: five tabs (web/index.html:42-51); at 900x560 and up the page never
scrolls and each column scrolls alone (web/app.css:549-554). A new item
card, trade or build alert shows Play by itself unless the player is
working in the shown tab (web/tabs.js:68-73, 10 s grace at :43). The
overlay has no interactive element (PACK README measurement 13).

Interaction inventory. "Often" = how often in normal use. Bound = the
floor rule or decision that keeps the act.

In play:
- I1 Item check. web/index.html:174-177, app/main.js:34 and :401,
  app/eval_hotkey.js:27-47 (one clipboard read per press, main.js:397),
  POST /api/eval (server/al/http.py:326). The player hovers the item,
  presses the game's own Ctrl+C, then Alt+Shift+E. Often: per item.
  Bound: decision 0003, floor (no input to the game, one read per press).
- I2 Show or hide the overlay: Alt+Shift+A (app/main.js:33, :392). By
  choice; the overlay also hides by itself while the game is idle.
- I3 Dismiss a trade row or all rows (web/app.js:172-177,
  web/index.html:150). Optional: rows leave after 10 minutes (:147) or on
  the accept / cancel line (decision 0019).
- I4 Open the trade or upgrade search link (web/app.js:688, :934). Per
  priced item, by choice. Bound: decision 0017 (the app never calls the
  trade site; the player opens the link).
- I5 Copy a search string, then paste it into the game's search box
  (web/search.js:109, web/health.js:189). Per search. Bound: clipboard
  write only on a click (decision 0014); the paste is the player's.
- I6 Switch tab (web/index.html:42-51). Needed in play only to look
  something up; Play comes back by itself.
- I7 Scroll a Play column (web/app.css:554). Forced today in 6 of 9
  states at 1280x760 (Findings F1). No rule requires it.
- I8 Open the zone guide "more" fold (web/zoneguide.js:93-97). Per zone
  at most; holds the optional rows.
- I9 Pick a character (web/index.html:117, web/chars.js:121). Only with
  2 or more characters and only to look at another one's numbers.
- I10 Hide the language notice (web/index.html:89). Optional; it clears
  by itself.

Setup and occasional:
- I11 Install and first start: typed commands (scripts/setup.ps1:29-32,
  scripts/run.ps1:39-46), then the Start Menu or Desktop shortcut
  (setup.ps1:164). Once. Note 0042 counts 14 acts to the first verdict.
- I12 Allow reading Client.txt (web/index.html:79; POST /api/consent,
  http.py:318). Once. Bound: floor (opt-in with a visible indicator).
- I13 Load a build: in Path of Building, open Import/Export and copy the
  code (2 to 3 acts); in AshLight click Build (index.html:46), click the
  paste box (:369) and press Ctrl+V; the paste event sends it
  (web/app.js:1153-1154, :499; http.py:324). 6 acts, once per character
  (decision 0045 keeps one build per character and swaps by itself,
  theorycraft/store.py:223) and again after every build change. A share
  link works the same way with web data on (theorycraft/shareurl.py).
- I14 Use web data: one checkbox (index.html:441); the contact is typed
  into a settings file by hand (note 0039, note 0042 F1). Once.
- I15 Change a hotkey: edit the settings file by hand (index.html:176,
  :515-516). Rare. Note 0039 R3 puts it in the app.
- I16 Overlay position form (index.html:549-561). Once.
- I17 Stat weights form (index.html:488-501). Rare.
- I18 Run history switch and Clear (index.html:263-265), Clear watched
  items (:471). Rare.
- I19 Loot filter: download (index.html:419) or pick a file to merge
  (:427), then move the file by hand. Rare. Bound: decisions 0031, 0033.
- I20 Save the .build file (index.html:360), then move it by hand. Rare.
  Bound: decision 0034.
- I21 Settings export, import file pick (index.html:572-574). Rare.
- I22 Graphics fold (index.html:581), Copy report (:534), tips again
  (:524), Restart overlay (:521), Copy code (:350). Rare, by choice.
- I23 Tray: Minimize or Restore, overlay on / off, Restart overlay, Quit
  (app/client/tray_menu.js:13-19). Quit is the one needed act.
- I24 Stop reading Client.txt (index.html:635). Rare. Bound: floor
  (revocable opt-in).
- I25 Optional calc: scripts/setup.ps1 -TcCalc (:31); logon start:
  scripts/autostart.ps1 -Enable (:26). Once each; note 0039 R4, R5.

Counts: 10 kinds of act in play, of which 1 is forced by the floor per
item (I1), 1 is forced by the layout (I7) and 8 are by choice; 15 setup
or occasional kinds, of which 2 are floor-bound (I12, I24).

Furthest reduction per act inside the floor (added by the verifier; the
brief asks for one per act). "Floor" names the CLAUDE.md rule that bounds
it.
- I1: 2 chords to 3 key presses (R5); 1 press only by a screen read (R7).
  Floor: one clipboard / screen read per manual AshLight press; no input
  to the game, so the game's copy stays the player's own key.
- I2: already automatic while idle (decision 0029 amendment); the key
  stays for choice. Floor: none.
- I3: already automatic (10 min, decision 0019); the button stays as an
  option. Floor: none.
- I4: stays one click; R1 keeps it one line in the first view. Floor: the
  app never calls the trade site, the player opens the URL (decision
  0017).
- I5: stays click plus the player's own paste; the town string can move
  to Play (note 0054 R4) to save the tab switch. Floor: no input to the
  game; clipboard write only on a click (decision 0014).
- I6: Play already returns by itself (web/tabs.js:68-73); 5 tabs to 4
  (R6). Floor: none.
- I7: removed (R1). Floor: none.
- I8: stays an optional fold; the objective line shows without it.
- I9: already automatic from the log (decision 0038); the picker only
  views another character. Floor: none.
- I10: already clears by itself; button optional.
- I11: once; note 0042 owns the first-run count. Floor: none.
- I12: stays one click. Floor: Client.txt only after opt-in with a
  visible indicator.
- I13: 6 acts to 0 in AshLight (R3, after one opt-in) or to 1 chord (R4).
  Floor: R4 is the same single read per press; R3 needs a ruling (Open
  question 1).
- I14: the checkbox stays (decision 0013, default OFF); the hand-typed
  contact moves into the app (note 0039 R2). Floor: public web data
  only, truthful User-Agent.
- I15: hand edit to an in-app setting (note 0039 R3). Floor: hotkey rule
  of server/al/hotkeys.py (no game or Windows combination).
- I16, I17, I18, I21, I22: rare, by choice; R6 closes the folds so they
  cost no scroll. Floor: none.
- I19, I20: stay a download plus a manual move. Floor and decisions
  0031, 0033, 0034: AshLight never writes into a game folder.
- I23: Quit stays; logon start is opt-in (decision 0011).
- I24: stays. Floor: revocable opt-in.
- I25: once each (note 0039 R4, R5); the calc stays opt-in (decision
  0018).

## Findings

F1. Play scrolls in most filled states (PACK run/<state>/dash-play-*.json,
left column / right column overflow in px):
- 1280x760 (column height 654): a 0 / 0, a2 0 / 0, b 21 / 0, c 380 / 321,
  c2 281 / 0, d 541 / 0, e 0 / 0, f 231 / 321, g 231 / 376.
- 1920x950 (column height 836): b 0 / 0, c 124 / 117, c2 47 / 0,
  d 311 / 0, f 64 / 117, g 64 / 171; a, a2, e fit.
The page itself never scrolls (0 of 135 captures). The operator's rule is
no scrolling; the tab that must fit is the one that does not.

F2. One block causes most of it. In state c at 1280x760 [PROBE] the tile
block is 457 px of the 654 px column: the zone tile spans the row
(web/app.css:129) and holds the guide (index.html:102-108), 315 px for 67
words; under it three tiles of 129 px hold 13, 6 and 2 words. Then trades
252 px (43 words), build alert 201 px (51 words), tip 101 px (21 words).
In the first view: zone, tiles and 1.5 trade rows; the build alert and the
tip are fully below the fold.

F3. Game idle is the worst left column (541 px, state d): the session
summary card (251 px) lands above trades, alert and tip, so 108 of 204
words are in the first view. The player returning to the desk sees the
summary and half a trade card.

F4. The item card is one 975 px card in a 654 px column (state c): price
(192 px) and price-and-points (81 px) are below the fold; the verdict,
compare table and upgrade link are above it. With web data on (state g)
the card grows to 1030 px.

F5. A layout-only prototype fits everything [PROBE proto.js]. It shows no
new data and moves or trims what exists:
- tiles: one strip of four (zone, level, deaths, session), 457 -> 79 px;
- guide: its own card under the strip, title and duplicate tip line
  dropped, 215 -> 140 px;
- trades: one line per request, 3 rows then a count, the 10-minute
  sentence dropped, Dismiss all in the heading row, 252 -> 118 px;
- build alert: heading inline, 2 one-line upgrade rows, 201 -> 67 px;
- tip: one line, no heading, 101 -> 36 px;
- session summary: two columns, 251 -> 122 px;
- item card: sentence clamped, first compared slot only with 5 stat rows,
  upgrade and price as one link line each, 3 listings, when-line and
  calc line dropped, 975 -> 367 px.
Result, states c and d: left 1034 -> 472 px and 1195 -> 575 px, right
975 -> 367 px; 0 px overflow at 1280x760 and 1920x950 for both (state d
overflows 7 px at 1024x700). Words 397 -> 256 (c) and 271 -> 231 (d).
Spare height at 1280x760: 182 px (c), 79 px (d).

F6. The guide height in the pack is the real maximum: the demo zone
(Clearfell) is the longest of the 93 guide entries, 46 words against a
median of 12 and a 90th percentile of 26 (server/al/data/zone_guide.json,
counted for this note). Not covered by the pack and to be absorbed by the
spare height: timers past 0:02, the calc line with PoB deltas, a full
price book, the language notice (PACK README, Gaps).

F7. Design 0001 states figures the pack disproves: "1920x950 Play left
column fits exactly, 1280x760 is within 26px with two open trades"
(docs/design/0001-design-system.md:117-121). With the guide, a build
alert and 2 trades it is 124 px and 380 px over. That is the measurement
MERGE-SEAMS-FOLLOWUP F1 asks for; the row can close on these numbers.

F8. An item check costs hover + 2 chords = 5 key presses (Ctrl, C, Alt,
Shift, E), per item. Nothing in the floor requires the second chord to
sit on other modifiers than the first. Alt+Shift is also the Windows
layout switch (note 0042 R12).

F9. The build costs 6 acts per change, in two programs, and one of them
is a tab switch away from Play (I13). Nothing follows the folder Path of
Building saves into, although the store already reloads a build file by
itself when its mtime moves (theorycraft/store.py:260) and PoB can import
the live character by itself [POB]. With the player's own character as
the build, the stale alert returns every 5 levels
(theorycraft/buildlive.py:22), so the 6 acts repeat through a campaign.

F10. The press that already exists reads a copied build code and throws
it away: `Core.eval_press` sends every clipboard text to the item check
(server/al/core.py:259-273) and non-item text ends as a "Not an item"
card (PACK run/e). The same read could load the build with no tab, click
or paste.

F11. Other tabs scroll, by choice of reading [PACK, state f, px over at
1280x760 / 1920x950]: Run and history 261 and 879 / 20 and 567; Build
271, 133 (code box) and 350 / 67, 114 and 148; Items and prices 664 to
668 / 427 to 431 in every state, because the stat weights fold starts
open (index.html:483; 1322 px column); Settings 0 with its folds closed,
561 to 565 / 379 to 383 when Checks opens by itself (states a, e).

F12. Interactive load is small on Play and large elsewhere [PACK README
measurement 8]: Play 15 visible controls and 12 tab stops in the worst
case, of which 6 sit in the two columns [PROBE]; Items 52 and 49.

## Scroll audit: what must move, shrink or leave

Play, to reach 0 px at 1280x760 and 1920x950 (R1). Figures: F5.
- Move: the guide out of the zone tile into a card under a one-row tile
  strip; Dismiss all into the Trade requests heading row.
- Shrink: tiles to one 79 px strip (label "Deaths"); trades, alert, tip
  and the idle summary to the compact forms of F5; the item card to
  verdict, sentence, one compare block, one link line each.
- Leave Play: the pace line (to Run and history); the under-level line
  under the Level tile while a guide is shown (the guide carries the gap;
  this settles note 0042 F22); the item card's when-line, calc line,
  second and third compared slots, rows past 5, price sentences and
  price-and-points notes (to a "Details" fold at the end of the card,
  closed by default; opening it is the player's choice and may scroll);
  trade rows past 3 (a count; the full list stays in Recent).
- Stays as is: consent card, language notice, status pills, footer.

Other tabs (not needed in play; fix by caps and closed folds, R6):
- Run and history: cap Recent and Death recap at 8 rows each with a fold
  for the rest (879 px comes from these two lists).
- Build: the code box and the gear list go into folds; Build health and
  Search strings keep their column.
- Items and prices: the stat weights fold starts closed (note 0042 R10);
  that alone removes the 668 / 431 px.
- Settings: fits; Checks opening by itself on a failure is correct.

## Tab audit

- Play: zone, guide, level, deaths, session, trades, build alert, tip,
  item card. Needed in play: always. Keep.
- Run and history: act times, zone levels, run history, maps and ladders,
  death recap, recent events. Needed in play: between maps or acts, a few
  times an hour at most. Keep.
- Build: build view, code out, .build file, build health, look for next,
  search strings, loot filter. Needed in play: after a build change, and
  for a search string in town (note 0054 R4 puts that string on Play).
- Items and prices: web-data switch, currency values, movers, price
  watch, stat weights. Needed in play: currency values now and then; the
  switch and the weights are settings.
- Settings: hotkey hint, tools, Checks, overlay position, settings
  transfer, graphics. Needed in play: never, unless Checks says "fix".

Merge to 4 tabs (R6): Play; Run and history; Build and items (build,
health, search strings, stat weights closed, currency values and movers
with price watch folded in per note 0039 R10); Settings (the web-data
switch with its contact field per note 0039 R2, tools, Checks). A
three-tab set (Play, Review, Setup) would put two unrelated things in one
panel and bring scroll back; not recommended.

## The two named pains

Build, ranked by acts saved (all inside the floor unless listed under
Rejected; R3 subject to the Open question 1 ruling). Build order differs:
R4 first (effort S, certainly inside the floor), R3 after the ruling.
1. Follow the Path of Building builds folder (R3). After one opt-in the
   player only saves in PoB; AshLight acts 0. PoB can refresh the live
   character through its own account import, so "import, save" in PoB
   replaces find-a-link, copy, switch, paste.
2. Load a copied code on the existing hotkey press (R4). 1 chord, no tab
   switch, no click; works from any window.
3. Remember per character (exists, decision 0045). Keep. One build per
   character, swapped from the log with no act.
4. GGG character API (stub exists, providers.py:59-85). Would give worn
   gear, skills and passives with no PoB at all, one browser approval per
   7 days at best (note 0035). Blocked: registration closed [GGG]; the
   docs watch (decision 0044) flags a reopening by itself.
5. Share link paste (exists, web data on). Same acts as a code paste.
6. Worn-gear baseline from presses (note 0038 R1). Complements 1 to 4.
Public profile sources: none is usable (Rejected).

Items, today, from the code: hover the item; press Ctrl+C (the game
copies the item text); press Alt+Shift+E (AshLight reads the clipboard
once, app/eval_hotkey.js:36, and posts it); the verdict shows on the
overlay card for 20 s (server/al/state.py:35) and on Play. Per item:
1 pointer move, 2 chords, 5 key presses, 0 clicks.
Minimum the floor allows:
- With the clipboard: 2 chords. The copy must be the player's own key
  press (no input to the game) and the read needs its own AshLight press
  (no watcher). A roll under one held modifier cuts it to 3 key presses
  (R5).
- With the screen: 1 chord. The floor permits one screen read per manual
  press; it needs OCR of the tooltip (R7, spike).
- Fewer checks instead of faster checks: a search string that lights up
  candidates in the stash or vendor (I5; note 0054 R4), value tiers in the
  loot filter (decision 0032), the upgrade list re-scored by itself on a
  build change (decision 0045). These cost 0 presses per item.

## Glance budgets (testable)

Model: one look is at most 2 s [NHTSA, analogy]; a glance read should
interrupt the main task as little as possible [GLANCE]; that fewer words
read faster is assumed here, not sourced (UNVERIFIED); a reader takes
about 4 words a second (rule of thumb, UNVERIFIED as a measured rate). So an answer must be in the first view
and reachable within 6 words of its card's first word: 0.3 s to land
plus 6 / 4 s is under 2 s. The test asserts the proxy, not the time.

- B1 No scroll: `.play-main` and `.play-side` have scrollHeight equal to
  clientHeight at 1280x760 and 1920x950 in the pack states b, c, c2, d,
  f, g (Details fold closed); the page overflow stays 0.
- B2 Spare height: at least 40 px free in each Play column in state c at
  1280x760 (the prototype has 182 px), so real strings fit.
- B3 Words on Play: at most 260 in the worst case (today 397, prototype
  256); at most 200 in the zone-guide state b (today 197).
- B4 Elements on Play: at most 100 visible in the worst case (today 133;
  the prototype was not counted, so confirm on the first run and lower).
- B5 Controls on Play: at most 8 inside the two columns, all in the first
  view (today 6, of which 4 in the first view at 1280x760).
- B6 Top answers in the first view, each within 6 words of its card's
  start and at 16 px or larger: where am I and for how long (zone tile);
  what to do here (guide objective line); is this item an upgrade
  (verdict word); what is it worth (price line); who trades what, where
  (first trade row); my level and whether I am under-levelled; deaths;
  session time; is AshLight reading (pill); is my build stale (alert
  heading).
- B7 Glance values: zone name, level, deaths, session and verdict word at
  20 px or larger; no Play text under 13 px (design 0001 section 3).
- B8 Tabs: at most 4; a new card, trade or alert shows Play with no act
  (exists, app/test/tabs.test.js).
- B9 Item check: at most 3 key presses per item with the default keys
  (after R5); build load: 0 acts in AshLight with the folder source on
  (after R3).

## Recommendations

R1. Make Play fit: the measured layout.
- Action: implement F5 and the Play list of the scroll audit in
  web/index.html and web/app.css, with a closed "Details" fold in the
  item card for what leaves the first view.
- Impact: H. Removes every forced scroll on the one tab used in play;
  alert and tip become visible in the worst case; 141 fewer words.
- Effort: M. Risk: longer real strings; covered by B2 and ellipsis on
  the one-line rows (full text in the title and in Details).
- ToS check: layout and copy only; reads and sends nothing new. The
  affiliation line in the footer stays (floor: statement shown).
- Depends on: nothing. Settles MERGE-SEAMS-FOLLOWUP F1 and note 0042 F22.
- Files likely touched: web/index.html, web/app.css, web/app.js,
  web/trades.js, web/buildlive.js, web/summary.js, web/zoneguide.js,
  docs/design/0001-design-system.md (section 4 figures), app/test/*.
- Acceptance test: B1, B2, B3 green in headless Chrome on states b, c,
  c2, d, f, g; design-reviewer pass.
- ZERO-CLICK: nothing to do; the layout fills by itself. Details is an
  optional click.

R2. Put the glance budgets under test.
- Action: one CDP test (pattern of app/test/cdp/dash_console.mjs) that
  builds the six states from the pack's recipe and asserts B1 to B7; a
  node test for B8.
- Impact: H. Without it the next card added to Play brings scroll back
  (it happened between UI-GLANCE and the merge, F7).
- Effort: M. Risk: a test core with a missing log path tails the live log
  (PACK README, Incident); the fixture must create the log file first and
  pin discovery, as the pack script does. Never part of a whole-suite run
  that touches port 8960.
- ToS check: test only; synthetic log, no game, no live Client.txt.
- Depends on: R1 for green; a supported demo mode (note 0058 R8 a) makes
  it simpler.
- Files likely touched: app/test/cdp/play_glance.mjs,
  tests/test_dash_console.py or a sibling, tools/design_gate.py.
- Acceptance test: red on today's layout (c: 380 px), green after R1.
- ZERO-CLICK: runs in the gates; no player act.

R3. Follow the Path of Building builds folder.
- Action: a third build source "pob_folder": after one opt-in on the
  Build tab that shows the folder path, each loop tick stats the folder
  and loads the newest saved build that fits the character played
  (remembered file per character first, else exactly one file whose
  class fits per buildlive.class_fits, else ask once in the build
  alert).
- Impact: H. Build acts in AshLight drop from 3 per change to 0; with
  PoB's own character import the build tracks the live character.
- Effort: M. Risk: wrong file picked (bounded by the class and level
  checks and the alert naming the file); a custom PoB folder (read
  `buildPath` from PoB's Settings.xml, or let the player pick once); a
  portable or dev PoB keeps its user data next to the program
  (Main.lua:82-84), so the default path is wrong there and the one-time
  pick is the fallback.
- ToS check: reads the player's own planner files, written by PoB, not
  by the game: no game file, no process, no clipboard, no screen, no
  network, no input. GGG's read rules cover the screen, the clipboard and
  the game's logs, and bar macros triggered by a file change [GGG]; a
  file change here starts no macro and no game action. Read literally,
  the CLAUDE.md floor's "READ ONLY what GGG permits" list names only
  Client.txt, the clipboard / screen per press and public web data, and
  a PoB file is none of them; the precedents that AshLight already reads
  non-game local files are decision 0033 (filter bytes the player picks)
  and the decision 0037 amendment (one file of the pinned PoB checkout).
  The file holds the same build text the player pastes today. Verifier
  call: keep R3 as a recommendation but do not build it before a
  recorded ruling (Open question 1); if the ruling says the floor list
  is exhaustive, R3 moves to Rejected and R4 carries the build pain.
- Settled decisions: decision 0004 (and the CLAUDE.md stack clause)
  says the optional calc gets "only user-pasted build text and
  hotkey-read item text"; a build read from a file widens that input and
  needs a recorded amendment, not a reversal (none of 0004's "Reverses
  if" conditions is met). Decision 0045 makes sources pluggable and says
  turning a provider on is its own decision.
- Depends on: decision 0045 (store, providers); a new decision plus the
  0004 amendment.
- Files likely touched: server/al/theorycraft/providers.py, store.py,
  model.py (XML entry), server/al/core.py (tick_build), server/al/http.py,
  web/tc.js, web/buildlive.js, tests/.
- Acceptance test: with the source on, writing a fixture XML into a temp
  builds folder changes `build` in the snapshot within one tick; a file
  of another class is not picked; off by default; no read before opt-in.
- ZERO-CLICK: after the one opt-in, saving in PoB is the only act.

R4. Let the item hotkey load a copied build.
- Action: in `Core.eval_press`, classify the text first
  (theorycraft/paste.detect): a PoB code or character JSON loads the
  build, a share link loads only with web data on, anything else is the
  item check as today. The overlay card says "Build loaded: <name>".
  The "no build" and "stale build" alerts on Play name this press (the
  key read from the config) in one line, with note 0042 R3.
- Impact: H. I13 drops from 6 acts to copy in PoB plus 1 chord; no tab
  switch, no click, and it works for players who never save in PoB.
- Effort: S. Risk: a build replaced by accident (the card names the
  build; the old file is kept as one undo).
- ToS check: the same single clipboard read on the same manual AshLight
  hotkey press (decision 0003); nothing new is read, nothing is sent to
  the game; the share-link fetch stays under the web-data opt-in
  (decision 0013) and its host allow-list. The "Build loaded" card uses
  the one overlay card slot like an item card (decision 0014 F2).
- Settled decisions: the text reaching the calc is a hotkey-read build,
  not "user-pasted build text" in the words of decision 0004; the same
  player-copied text reaches the same parser, so record a one-line
  amendment to 0004 with R4 (no "Reverses if" condition needed, nothing
  is reversed).
- Depends on: the 0004 amendment line.
- Files likely touched: server/al/core.py, server/al/state.py (card
  words), app/overlay/overlay.js, web/index.html (hint text), tests/.
- Acceptance test: POST /api/eval with a fixture code changes `build`
  and returns a "Build loaded" card; item text still gives a verdict;
  text that paste.detect calls "code" but that fails to decode falls
  back to the item check; a link with web data off gives the existing
  refusal words.
- ZERO-CLICK: 1 press, required by the floor (one read per manual press).

R5. A roll for the item check.
- Action: make the default item key a second tap under the modifier the
  player already holds for the game's copy, and offer it in the in-app
  hotkey setting of note 0039 R3. The key itself must pass
  server/al/hotkeys.py and be free in the game's default binds
  (UNVERIFIED which neighbour of C is free; check in the game's options
  before choosing).
- Impact: M. 5 key presses to 3 per item, one hand, no modifier change;
  also leaves Alt+Shift (note 0042 R12).
- Effort: S. Risk: a clash with a game bind hides that bind while
  AshLight runs (a global shortcut takes the key from every program);
  the Checks row for the hotkey already reports a failed registration.
  A Ctrl+letter default is also taken from the browser and every other
  program while AshLight runs (server/al/hotkeys.py:4-5 says so for all
  AshLight keys), so pick a letter no common program binds, or keep
  Alt+Shift+E as a listed alternative.
- Settled decisions: decision 0014 F1 names Alt+Shift+E as the default;
  changing the default keeps its contract (own hotkey, one read per
  press, config `eval_hotkey`), so it is an amendment to the default,
  not a reversal.
- ToS check: still the player's own Ctrl+C, then one manual press of an
  AshLight hotkey with one clipboard read; no input sent, no watcher.
- Depends on: note 0039 R3 for the in-app setting.
- Files likely touched: app/main.js, app/hotkey.js, server/al/hotkeys.py,
  app/test/hotkey_cases.json, web/index.html (two hint texts).
- Acceptance test: hotkey case table accepts the new default and still
  refuses every GAME_KEYS entry; B9.
- ZERO-CLICK: 2 presses under one hold; the floor forbids fewer with the
  clipboard.

R6. Four tabs and closed folds.
- Action: merge Items and prices into "Build and items" and Settings as
  in the tab audit; start the stat weights fold closed; cap Recent and
  Death recap at 8 rows with a fold.
- Impact: M. One tab fewer to search; the 668 px Items scroll and the
  879 px Run scroll go.
- Effort: M. Risk: the picked-tab memory names a tab that is gone (map
  it to its new home once).
- ToS check: layout only; the web-data switch keeps its default OFF and
  its wording (decision 0013).
- Depends on: note 0039 R2, R10 and note 0042 R10 (same cards).
- Files likely touched: web/index.html, web/tabs.js, web/app.css,
  docs/design/0001-design-system.md, app/test/tabs.test.js.
- Acceptance test: B8; with folds closed no column scrolls in state f at
  1920x950.
- ZERO-CLICK: Play still shows by itself; nothing new to press.

R7. Spike: one press per item by a screen read.
- Action: time-boxed test of one capture of the tooltip area on the
  AshLight press, read by an OCR engine run as an optional external
  tool, compared against the clipboard text of the same 30 items.
- Impact: M if it reads mods exactly, none otherwise. Effort: L. Risk:
  misread numbers give wrong verdicts; a new optional dependency
  (decision 0002 keeps the core stdlib-only, so it must follow the
  decision 0018 pattern or use the OS engine [OCR], whose languages
  depend on what the device has installed).
- ToS check: one screen read per manual AshLight key press is what the
  floor and [GGG] allow; no continuous capture, no timer, nothing sent
  to the game. The capture is made by AshLight's own window process, not
  by a hook in the game's graphics.
- Depends on: a decision; R5 first (cheaper, certain).
- Files likely touched: app/main.js, a new optional tool, tests.
- Acceptance test: 30 of 30 items parse to the same stats as their
  clipboard text, or the spike is closed as rejected.
- ZERO-CLICK: 1 press, the floor minimum for any item read.

## Cut or merge

- Merge: Items and prices into Build and items plus Settings (R6).
- Merge: the under-level line into the guide while a guide shows (R1).
- Cut from Play's first view: pace line, when-line, calc line, trade
  expiry sentence, tip heading, "Upgrade search" / "Price" / "Price and
  points" headings and sentences (R1; all kept in Details or Run).
- Cut: the dead `/api/clipboard-read` stub (server/al/http.py:311-317;
  501 since the hotkey reads in the client, decision 0014 F1 chose the
  client read over it). One route less to explain. Its one consumer,
  tests/test_http_security.py:152-154, goes with it.

## Rejected

- AshLight sending Ctrl+C on its own press: synthesized input (floor).
- Checking an item, or loading a build, as soon as it is copied: a
  clipboard watcher (floor).
- A pass-through key listener that treats the player's Ctrl+C as the
  AshLight press: it needs a system-wide keyboard hook that sees every
  key, decision 0003 keeps the copy and the AshLight press apart, and
  hotkeys.py bars Ctrl+C as an AshLight key. Not inside the floor as
  written; reverses only if decision 0003 does.
- A "load build from clipboard" button on the dashboard: a clipboard
  read on a click, not on a manual press of an AshLight hotkey (floor;
  R4 gives the same result inside it).
- Public profile sources: poe.ninja character and build endpoints are
  internal and not for third parties, the website character-window
  endpoints are undocumented and need POESESSID (research 0033 section
  3; floor: documented endpoints only, never POESESSID).
- Reusing PoB's OAuth client id or its saved tokens: misrepresents the
  client (research 0033) and reads another program's credentials.
- Reading the game's planner folder or filter folder for a build: game
  folders outside the Client.txt-only read rule (research 0033 section
  4), and they hold a plan, not the character.
- Repeated or timed screen reads for inventory or stash: continuous
  capture (floor).
- A three-tab set: see the tab audit.

## Open questions

1. R3 needs a recorded decision that a player-chosen PoB builds folder
   is a permitted local read (not a game file; opt-in; path shown), and
   whether the CLAUDE.md floor's "READ ONLY" list is exhaustive for
   non-game local files; plus the decision 0004 input-clause amendment
   (R3 and R4). Adjudicator can take it; the evidence is in the R3 ToS
   check. The verifier could not spawn one (no agent tool in its run),
   so it is filed, not ruled.
2. R5: which key next to C is free in the game's default binds. One look
   at the game's input options settles it (operator, or the live capture
   session of note 0038 R4).
3. R7: whether an OCR spike is worth a wave before 1.0. Recommended: no;
   after R5 the saving is 1 key press per item.
4. B4 (100 elements) and B2 (40 px) are set from one prototype run with
   short synthetic strings; confirm on the first real run of R2.

## Verification

Independent verifier, 2026-11-18. No product file, core or browser was
started; the live core and Client.txt were not touched.

Checked:
- Code citations: about 75 path:line claims opened (web/index.html 34 lines,
  web/app.js 7, web/app.css 2, web/tabs.js 2, web/search.js, web/health.js,
  web/zoneguide.js, web/chars.js, app/main.js 5, app/eval_hotkey.js,
  app/client/tray_menu.js, server/al/http.py 5, core.py, state.py,
  hotkeys.py, theorycraft store.py 2, buildlive.py, providers.py,
  paste.py, scripts setup / run / autostart, design 0001:117-121). All
  hold; the setup.ps1 and run.ps1 cites point at the parameter blocks of
  the typed commands, which is what the inventory means. 15 named
  "files likely touched" exist.
- Numbers: every Play overflow figure in the Summary and F1 re-read from
  the pack's per-state JSON (18 column values at two sizes, 6 of 9 and 5
  of 9 scrolling states, 0 page overflow in 135 dashboard captures, 397
  words and 133 elements in state c); F2, F3, F5 block heights, word
  counts, spare height (182 px, 79 px) and the 7 px at 1024x700 re-read
  from the author's probe files (`<sidecar>\Scratch\up-0043\`); F6 guide
  statistics recounted from server/al/data/zone_guide.json (93 entries,
  Clearfell 46 words, median 12, 90th percentile 26, counting every text
  field); F11 other-tab overflows and F12 control counts re-read from the
  pack.
- Web: 4 sources re-fetched (GGG docs, Berkeley abstract, Microsoft OCR
  page; NHTSA answered 403, checked through search summaries); PoB
  source lines re-read in the pinned checkout.
- ToS floor: R1 to R7 tested against every floor rule; Rejected list
  re-checked (all 9 stay rejected).
- Settled decisions: R3, R4 against decision 0004; R5 against 0014 F1;
  the clipboard-read cut against 0014 F1; R1, R6 against 0019, 0029,
  0013.
- Completeness: brief points 1 to 5 covered; the per-act reduction
  (brief point 2) was missing for most acts and was added.

Corrected:
- GLANCE: the abstract does not say the amount of information sets the
  reading speed; claim withdrawn from Sources and the budget model.
- OCR: the class is part of the Windows API since build 10240 (now
  sourced); only the per-device recognizer language stays UNVERIFIED.
- PoB: user path comes from the runtime's GetUserPath (Documents
  UNVERIFIED); portable or dev PoB keeps user data next to the program
  (Main.lua:82-84), added as an R3 risk; citation widened to :87-91.
- Summary: the idle figures were written as a left / right pair; they
  are the left column at two sizes.
- R3: the literal floor reading and the decision 0004 input clause
  added; R3 is held behind a ruling, R4 is built first.
- R4: decision 0004 amendment line, card slot (0014 F2) and a decode
  fallback test added.
- R5: system-wide key capture risk for a Ctrl+letter default and the
  0014 F1 default noted.
- Cut list: the stub's test consumer named.
- Added: "Furthest reduction per act" for I1 to I25.

Still UNVERIFIED: the 4 words a second rate; that fewer words read
faster; NHTSA figures (search summaries only); an OCR recognizer
language on every install; PoB's user path being Documents; which
Ctrl neighbour of C is free in the game's default binds (Open question
2); the prototype element count (B4) and real-string heights (B2), since
the probe ran states c and d only with synthetic strings, calc off and a
thin price book.
