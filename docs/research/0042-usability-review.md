# 0042 - Usability review: task walks, heuristic findings, phone view options

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B6
usability. Scope: the top player tasks walked end to end from the code and
the scripts with a step count, a heuristic evaluation with a severity per
issue (status, errors and empty states, wording, dashboard and overlay
consistency, settings discoverability), and the open operator decision on a
phone view laid out without deciding it. Pure glance and zero-click
questions are note 0043; the settings surface itself is note 0039.
Status: verified

## Sources (all accessed 2026-11-18)

- NN10: https://www.nngroup.com/articles/ten-usability-heuristics/ (the
  ten usability heuristics, H1 to H10 below; first published 1994-04-24,
  last reviewed 2024-01-30).
- NNSEV: https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/
  (severity 0 to 4 from frequency, impact and persistence; 1994-11-01).
- MS-LANG: https://support.microsoft.com/en-us/office/switch-between-languages-using-the-language-bar-1c2242c0-fe15-4bc3-99bc-535de6f4f258
  (Alt+Shift switches between keyboard layouts).
- MS-KEYS: https://support.microsoft.com/en-us/windows/keyboard-shortcuts-in-windows-dcc61a57-8ff0-cffe-9796-cb9706c75eec
  (Ctrl+Shift switches the keyboard layout, Windows key+Spacebar the input
  language, when more than one is installed).
- EL-GS: https://www.electronjs.org/docs/latest/api/global-shortcut
  (register returns a boolean; a chord another program holds fails
  silently; a registered chord works without keyboard focus).
- MS-FW: https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules
  (inbound is blocked by default; the first listen call prompts; the
  answer of a user who is not a local admin creates block rules; page
  dated 2025-06-06).
- TS: https://tailscale.com/kb/1312/serve (a tailnet proxy serves a
  localhost port to the owner's devices over HTTPS; one command after
  HTTPS certificates are enabled).
- SD: https://www.spacedesk.net/ (display extension software: a driver on
  the PC, viewers for Android, iOS and browsers, over USB, Wi-Fi or LAN).
- EE2-DL: https://kvan7.github.io/Exiled-Exchange-2/download and EE2-QS:
  https://kvan7.github.io/Exiled-Exchange-2/quick-start (a PoE2 price
  overlay: download, run the installer, launch; the installer build
  updates itself, the portable one does not; hotkeys are changed in its
  settings window; the extra steps on that page are for players moving
  from the PoE1 tool).
- PACK: the ultraplan UI evidence pack `up-evidence` (made 2026-11-17 at
  commit b8fda80; synthetic states a to g, 135 dashboard captures, overlay
  composites). Items are cited by their path inside the pack.
- Repo, read 2026-11-18: the files cited inline; design 0001 sections 7 to
  11; decisions 0003, 0013, 0014, 0016, 0017, 0029, 0038, 0041, 0045;
  research 0038, 0039, 0045, 0049, 0050, 0051, 0052, 0053. The sibling
  notes 0040 (visual design), 0043 (glance and zero-click) and 0044
  (accessibility) were not in the tree when this was drafted; the
  verifier added their recommendation numbers where they overlap (see
  "Verification").

## Summary

- Play itself is where AshLight is strongest: 0 acts in campaign and in
  maps, trade cards arrive and leave by themselves, an item check is 2
  chords (the floor forbids fewer), Quit is 2 clicks.
- The cost is before and around play. From a bare Windows PC to the first
  item verdict is 14 acts in README order (3 of them typed commands, 191 s
  of tests in the middle); 12 on the shortest path that already works; 8
  with an installer and R3. Five one-time setups end in a JSON file or
  PowerShell (contact, hotkeys, calc, a log outside Steam, game data).
- Heuristic evaluation (NN10, severity NNSEV): 23 findings, none a
  catastrophe, 6 major, 13 minor, 4 cosmetic. The majors: a web-data
  switch that promises prices that never come (F1), a verdict that hides
  that the build is stale (F2), 11 sentences that end at a file or script
  the player cannot find (F3), a README that sends players down the
  developer path (F4), no next step after the opt-in (F5), and a dead end
  for a log outside Steam (F6).
- Best first moves, all small: tell the truth at the web-data switch (R1),
  put the build caveat on the verdict (R2), give the build prompt its own
  button from the first minute (R3), a no-dead-end copy pass (R4), a
  player README (R5). Each removes steps or a wrong belief; none touches
  the floor or a settled decision.
- Phone view: five options from "none" to a LAN listener, with what each
  costs the player and the project. No recommendation; the operator
  decides (CLAUDE.md keeps LAN access off).

## Current state

### Method

- Heuristics: NN10. H1 visibility of system status, H2 match with the real
  world, H3 user control and freedom, H4 consistency and standards, H5
  error prevention, H6 recognition rather than recall, H7 flexibility and
  efficiency, H8 aesthetic and minimalist design, H9 help users recognise, diagnose and
  recover from errors, H10 help and documentation.
- Severity: NNSEV. 0 no problem, 1 cosmetic, 2 minor, 3 major, 4
  catastrophe; judged from how often it occurs, how hard it is to get
  past, and whether it keeps coming back.
- Wording is judged against the project's own rules: design 0001 section
  8 (plain words, no internals, errors say what happened and what to do)
  and checklist P1 to P8, N1 to N6.
- A step is one player act: a typed command, a click, a key chord, a
  paste, a file edit, an install. Waiting is given in seconds, not counted.
- Evidence: the code and scripts at HEAD and the PACK captures. Nothing
  was run against the live client, the game or the live log.

### Task walks (steps today)

- T1 First install. Needs Python 3.11, Node 20 for the client, pytest for
  the build step, and the source tree (README.md:60-64; no installer and
  no remote yet). README order: 3 installs, fetch the source, open
  PowerShell, then `setup.ps1`, `build.ps1`, `run.ps1` (README.md:66-69)
  = 8 acts. Waits: `npm ci` and the Electron download
  (scripts/setup.ps1:228-245), then the whole test suite, 191 s median
  (research 0049; scripts/build.ps1:165-177). Shortest path that works: 2
  installs, the source, a shell, `setup.ps1`, then the desktop shortcut
  setup wrote (scripts/setup.ps1:186-211) = 6 acts. Benchmark: download,
  installer, launch = 3 (EE2-DL).
- T2 First run. The shortcut starts the client; it starts the core itself
  and shows "Starting AshLight. The dashboard opens here in a moment."
  (app/client/window.js:127-145; app/client/starting.html:14). Then one
  click on "Allow reading Client.txt" (web/index.html:69-82). Zone, level
  and deaths come back from the log by themselves (decision 0008). 1 act.
- T3 Client.txt opt-in. 1 click; the card names the file and how to stop.
  Stop is 1 click on a footer link (web/index.html:635). A log outside
  the Steam libraries: no route in the app (F6); a JSON key and a restart.
- T4 Getting a build in. In Path of Building the player copies a code (3
  clicks there). In AshLight: Build tab, click the box, paste = 3 acts;
  it loads on the paste event (web/app.js:1153-1154) and stays per
  character (decision 0045). With a share link while web data is off:
  paste, refusal, Items tab, tick, Build tab, box, paste = 8 acts
  (web/tc.js:137-140).
- T5 Hotkey discovery and the item / price check. The chords are named in
  the Item check card's empty state and on the Settings tab
  (web/index.html:174-177, 515-516), in the README, nowhere on the
  overlay or the tray. A check is hover, Ctrl+C, Alt+Shift+E: 2 chords;
  the price link and value ride the same press (decision 0016). Changing
  a key: find and edit the JSON file, Quit, relaunch = about 6 acts
  (research 0039 F6).
- T6 Reading Play in the campaign. 0 acts. Zone guide alone overflows its
  column by 21 px at 1280x760 and 166 px at 1024x700; in the worst case
  the build alert and the tip sit 380 px below the fold (PACK README key
  measurements 2, 3, 5), so 1 scroll.
- T7 Reading Play in maps. 0 acts. Typical filled state: 365 words, 120
  elements, 321 px of inner scroll at 1280x760 (PACK run/summary_lines.txt,
  state f).
- T8 A trade whisper arrives. 0 acts to see it: overlay card with who,
  what, price, tab and position (app/shared/format.js:70-98), the
  dashboard list, and Play shows itself (web/app.js:196). It leaves on
  the accept / cancel line or after 10 minutes (decision 0019); Dismiss
  is 1 click. Answering is the player's own act in the game.
- T9 Switching character. After a game restart: 0 acts, the first
  level-up or death names the character and its build swaps in
  (decisions 0038, 0045). Without a game restart AshLight keeps the old
  character (server/al/state.py:1344-1356); the "Show numbers for"
  picker only changes what is shown (web/chars.js:55-93). A character
  with no build: T4 again.
- T10 Turning web data on. Promised: Items and prices tab, tick = 2 acts.
  Real: plus find the JSON file, open it, type a contact, save = 6 acts
  (F1); zone levels need a PowerShell command on top (server/al/acts.py:
  65-66) = 8.
- T11 The optional calc. A shell, `setup.ps1 -TcCalc`, wait for the
  fetch and the LuaJIT build, then open the JSON file, set
  `"tc_calc": true`, save = 6 acts; active within 30 s, no restart
  (server/al/theorycraft/calcwire.py:30, 138-187). Research 0039 F7, R5.
- T12 Updating. No update path and no version on the dashboard: a pull of
  the source, `setup.ps1` again when the lockfile changed, a client
  restart for app/ changes. Nothing says an update exists (research 0052
  F7; 0051; 0053).
- T13 Stopping. Tray icon, right-click, "Quit AshLight" = 2 acts; it
  stops core, supervisor, client and overlay (app/client/window.js:
  212-215; scripts/stop.ps1). The window's X only hides to the tray and
  says so once per run (app/client/window.js:225-232). Without the
  client: a typed `stop.ps1`.
- T14 Uninstalling. No script and no README section. By hand: Quit (2),
  disable autostart if it was enabled (2), delete two shortcuts (2), the
  folder (1) and the sidecar folder (1), whose place only
  `python -m server.al.paths` prints = 8 acts (research 0052 F7, R5).

### What the app says, state by state

- Not opted in. Pill "not reading Client.txt" (web/status.js:52); overlay
  "not reading - see dashboard" (app/shared/render_gate.js:133); tiles
  "-" with "Counts once reading starts"; Checks "Permission: Not given
  yet." and a "fix" mark on the Settings tab (PACK run/a/dash-play-1280x760.png).
- Log missing. Pill "waiting for Client.txt" or "Client.txt not found -
  start the game once" (web/status.js:49-50); overlay "waiting for log" /
  "no Client.txt" (render_gate.js:160-161); Checks "Client.txt: Not found
  yet." The Play tab body has 71 words and none about the log
  (PACK run/e/dash-play-1280x760.png).
- Game closed or 20 minutes quiet. Pill "quiet for 20 min - game closed or
  AFK?" (web/status.js:17); zone tag "frozen - log quiet"
  (web/index.html:98); the overlay hides (decision 0029 amendment);
  Settings "Overlay hidden: no game activity for 20 min. It comes back
  with the next log line." (web/index.html:517); a Last session card.
- Web data off. "Web data is off. AshLight asks nothing from the
  internet." (web/prices.js:56); pill "web data is off - no currency
  values" (web/prices.js:136); after a check only the trade link
  sentence (server/al/state.py:551-553); a share link is refused with the
  place of the switch (web/tc.js:137-140).
- Calc off or missing. Item card: "Scored with your stat weights. To see
  DPS and EHP, turn on the optional Path of Building calc in AshLight's
  settings file." (server/al/state.py:269-270); Checks "Calc component:
  Off." or "Missing or changed: a part." (server/al/diag.py:142-155).
- Build missing or stale. A "Your build" card on Play with one of three
  sentences (server/al/state.py:434-448). Nothing on the overlay, nothing
  on the verdict.
- AshLight not reachable. Pill "reconnecting" or "can't reach AshLight -
  restart it" (web/status.js:35-37); overlay "offline"
  (app/overlay/overlay.js:72, 84); client start page "AshLight couldn't
  start. Check that Python 3.11 or newer is installed ..."
  (app/client/starting.html:15).

### Where the controls are

- Settings tab: new-character tips, Restart overlay (client only), Checks,
  and inside one fold the overlay position, settings transfer and the
  graphics advisor (web/index.html:513-598).
- Items and prices tab: the web-data switch and the stat weights
  (web/index.html:440-443, 481-504).
- Run and history tab: the run-history switch and Clear
  (web/index.html:262-266). Play tab: the opt-in card, the character
  picker, the language notice. Footer: Stop reading. Tray: show or hide
  the overlay, Restart overlay, Quit (app/client/tray_menu.js:12-20).
- JSON only: both hotkeys, contact, league, the calc flag, a log path
  (research 0039 "Settings surface": 3 of 14 player settings have a
  control).

### What already works (keep)

Settings save on change and say so; a paste loads the build with no
button; the opt-in card names the file, what is derived and how to stop;
most empty states say what will appear and when; Checks opens by itself
on a failure; a tab the player is working in is held for 10 s before
Play takes over (web/tabs.js:68-73); trade cards expire by themselves;
every script is safe to run again.

## Findings

Format: F, [heuristic; severity], what, evidence, why it matters.

- F1 [H1, H9; 3] The web-data switch lies when no contact is set. The
  status says "Saved. Web data is on. Currency values arrive within a
  minute." and the pill "currency values arrive within a minute"
  (web/prices.js:59-62, 143), but without a contact no request is ever
  made (server/al/ninja.py:227-229, 291-297). The API already says why
  (`blocked`, `contact_set`: ninja.py:313-316; server/al/http.py:568-580);
  the page never reads it. The only hint is a Checks row on another tab
  (server/al/diag.py:118-125). Matters: the player believes prices are
  coming and waits; 2 promised acts become 6.
- F2 [H1, H4; 3] The verdict hides that the build does not fit. The
  overlay card is built from the item check and the price only
  (server/al/state.py:750-797); the stale-build alert exists only as a
  dashboard card, which at 1280x760 sits below the fold in the worst case
  (PACK run/c/dash-play-1280x760.png against its -scrolled-to-end.png).
  State c shows "Upgrade +21 vs Gloves" for a Sorceress scored against a
  Ranger build (PACK run/c/overlay-corner2x-black.png). Matters: wrong
  advice at the moment of decision, with the warning out of view.
- F3 [H2, H9, H10; 3] Eleven sentences end at a place the player cannot
  find (verifier count; the draft said nine). "AshLight's settings file"
  with no location (web/index.html:176-177, 515-516;
  server/al/state.py:269-270), `config\local.json` (server/al/diag.py:40;
  state.py:559-562), a PowerShell script (diag.py:39, 43, 44;
  server/al/acts.py:65-66, 71-74), or both at once (diag.py:45-46). One
  of the eleven (state.py:559-562) looks unreachable today (see "Cut or
  merge"), so ten are live. "Settings file" is also the name of a
  second, different file, the export (web/index.html:573;
  web/settingsio.js:26-27). Design 0001 section 8 rule 4 and checklist
  P2 bar internals in a main line; their list names core, token, SSE,
  tailer and HTTP codes, and this note reads a repo path or a script
  name as the same class. Research 0039 F1, F2 count the settings; this
  finding is the wording that sends the player there.
- F4 [H10, H2; 3] The README sends players down the developer path. Its
  quick start lists three commands, the second being the whole test suite
  (README.md:66-69; 191 s, research 0049) with pytest as a prerequisite
  (README.md:62-63); nothing reads the stamp it writes except build.ps1
  itself (server/al/paths.py:141; scripts/build.ps1:139-146). It never
  mentions the shortcut. It calls Node "only needed for the optional
  overlay" (README.md:63-64), yet without it there is no client, tray,
  Quit or shortcut (scripts/setup.ps1:135-144, 191-194) and no item
  check: the hotkey and its one clipboard read live in the client
  (app/main.js:395-403; app/eval_hotkey.js:27-47). No Update, Uninstall
  or Troubleshooting section (research 0052 F7).
- F5 [H6; 3] After the opt-in nothing says what to do next. State a2 is
  84 words with no call to action (PACK run/a2/dash-play-1280x760.png).
  The build prompt needs a character name first
  (server/al/theorycraft/buildlive.py:54-57), which a fresh game start has
  not given yet. The Build tab's empty text asks for "a Path of Building
  code or character JSON" (web/tc.js:68-69): it does not say where a code
  comes from or that a pobb.in or pastebin link works
  (server/al/theorycraft/shareurl.py:32), and no player can produce
  "character JSON" today (research 0033). Design 0001 section 7.1 calls
  the opt-in the only required click; the build paste is a second
  required act per character.
- F6 [H9, H5; 3 for that group] A log outside Steam is a dead end.
  Discovery walks Steam libraries only (server/al/logfile.py:135-153); the
  consent API takes a path but the page never sends one
  (server/al/http.py:673-677; web/app.js:1092). The texts say "start the
  game once" and "AshLight finds it by itself" (web/app.js:1040;
  web/status.js:50; server/al/diag.py:36-37), which is false there and
  false for a configured path (server/al/core.py:733). A configured path
  that does not exist falls back to the Steam log without a word
  (logfile.py:138-153; PACK README "INCIDENT"). Fix owned by 0039 R6.
- F7 [H1; 2] The overlay's own state is invisible. Shown or hidden by the
  player lives in memory, starts as shown and changes by hotkey or tray
  only (app/overlay_gate.js:22, 48; app/main.js:282-286). The dashboard
  explains only the idle case (web/index.html:517) and Checks says "The
  overlay is running." while it is hidden (server/al/diag.py:174-180,
  231). A show-hide chord that failed to register is logged only
  (app/main.js:392-394; EL-GS: it fails silently); only the item-check
  chord has a Checks row (diag.py:183-190, 315-334).
- F8 [H5; 2, and 3 for players with two layouts; UNVERIFIED in play] Both
  default chords contain Alt+Shift (app/main.js:33-34), the Windows chord
  that switches keyboard layouts (MS-LANG; MS-KEYS names the two other
  chords). A registered chord is taken from every program (EL-GS).
  Whether the layout also flips on each press was not tested (no input
  may be sent in this session); Open question 2.
- F9 [H6; 2] The hotkeys must be remembered. The one text on Play that
  names the item-check chord is the empty state, gone after the first
  check (web/index.html:174-177; web/app.js:622). The tray menu names no
  chord (app/client/tray_menu.js:12-20), the overlay never does, and the
  page prints the defaults even when the keys were changed (0039 F6).
- F10 [H4; 2] One state, up to five wordings. Log missing: "waiting for
  Client.txt", "waiting for log", "Not found yet". Idle: "quiet for 20
  min - game closed or AFK?", "frozen - log quiet", "log quiet 20m", "The
  game may be closed", "Overlay hidden: no game activity for 20 min"
  (web/status.js:17, 49; render_gate.js:19, 161; web/index.html:98, 517;
  server/al/diag.py:71, 94-96). Short forms for the overlay are right
  (design 0001 section 9 rule 5); five roots for one fact are not.
- F11 [H4, H6; 2] The Settings tab holds 4 of the 10 controls a player
  can use; the switches for web data and run history live on content
  tabs, Stop reading in the footer, show or hide the overlay in the tray
  only. Moving the overlay is tab plus fold. Outside the fold, the
  only filled (not "secondary") buttons are "Restart overlay", shown in
  the client only, and "Show new-character tips again"
  (web/index.html:521, 524); the tips button, the least important action,
  is the one every player sees.
- F12 [H9; 2] Errors stop one step short of the recovery. "The run log in
  AshLight's Logs folder" names no place and guesses one cause
  (app/client/starting.html:15; research 0050). "can't reach AshLight -
  restart it" does not say how (web/status.js:37). "No currency values
  are saved yet" does not name the switch (web/prices.js:296-298). With
  the log missing the fix sits on another tab (state e above).
- F13 [H3, H5; 2] "Clear run history" deletes up to 20 runs, the map
  ladder and the zone visits on one click with no undo
  (web/history.js:149-154; server/al/core.py:444-467), next to the Keep
  switch (web/index.html:262-266). Design N2 rules out a confirm dialog;
  an undo is still possible.
- F14 [H3; 2] The player cannot tell AshLight which character they are on
  after a switch without a game restart (state.py:1344-1356); numbers and
  item checks then belong to the wrong character. Owned by 0039 R7.
- F15 [H5; 2] A share link pasted while web data is off is refused after
  the fact, 8 acts instead of 3 (web/tc.js:137-140; web/app.js:491-515).
- F16 [H2, H8; 2] On the overlay "Trade link ready" replaces the item
  name on every check that has no poe.ninja value, which is every check
  while web data is off (state.py:551, 791-794; PACK
  run/c/overlay-corner2x-black.png). The overlay cannot be clicked, so
  the line names something the player cannot use there.
- F17 [H8; 2] Density works against finding things: the Items tab is 419
  words and 52 controls even when empty, because the stat weights fold
  is open by default (web/index.html:483; PACK run/summary_lines.txt,
  state a2); worst-case Play is 397 words; the idle Play column
  overflows 541 px. Detail and targets: notes 0040, 0043.
- F18 [H1; 2] No version and no update notice anywhere in the app; the
  version route is fetched only for the data credit
  (web/app.js:1102-1110). Notes 0051, 0053.
- F19 [H1; 2, browser path only] After a core restart a plain browser tab
  says "reconnecting" for good; its feed ended on the new token. Research
  0050 holds the evidence and the fix.
- F20 [H2; 1] Six wording defects. (a) Checks word "not known yet" beside
  "25 min ago. The game may be closed." (diag.py:94-96; web/checks.js:27).
  (b) "at the top of this page" for a button on another tab (diag.py:38;
  PACK run/a/dash-settings-1280x760.png). (c) "install it again" for a
  part never installed (diag.py:43). (d) "Unnamed item" on a result that
  is not an item, on both surfaces, with the same sentence twice under
  two badges (state.py:501, 510-515; PACK run/e/dash-play-1280x760.png).
  (e) "a contact for the trade site" (state.py:559-562): the app never
  calls the trade site (decision 0017). (f) "quiet for 20 min" is a
  constant; after three hours it still says 20 (web/status.js:17).
- F21 [H1; 1] With the log missing the session clock runs and deaths read
  "0" with "0 level-ups" as if counted (web/app.js:101-102; PACK
  run/e/dash-play-1280x760.png). Design 0001 principle 7 asks for "-".
- F22 [H8; 1] The same under-level fact appears twice on Play, in the
  zone tile and in the Level tile (PACK run/f/dash-play-1280x760.png).
- F23 [H4; 1] A "fix" mark on first run, before the player did anything:
  the unanswered opt-in counts as a failed check (diag.py:74-77;
  web/checks.js:93-94) and repeats the consent card. A pending choice is
  not a fault.

## Recommendations

Ranked, best first. A removed step outranks an explained one.

R1. Tell the truth at the web-data switch.
- Action: the Items tab reads `blocked` and `contact_set` (already in
  GET /api/web-data and /api/rates) and shows "On, but prices need a
  contact first" with the field of 0039 R2 / 0038 R3 right under the
  tick; never "arrive within a minute" while blocked.
- Impact: H. Ends a false promise; with the field T10 drops from 6 acts
  to 3. Effort: S for the words, M with the field (0039 R2).
- Risk: the contact is personal; never echo it (decision 0015).
- ToS check: "truthful User-Agent" and "never a POESESSID" untouched; no
  new request, the one web-data opt-in stays (decision 0013). Settled
  check: decision 0015 reads the contact only from the gitignored
  config/local.json, so the field must write it there and nowhere else,
  and it stays out of the settings export allow-list (decision 0036).
- Depends on: 0039 R2 for the field. Files: web/prices.js, web/app.js,
  web/index.html, app/test/prices.test.js.
- Acceptance test: a rates doc with web_data true and blocked "contact
  not set" renders the new pill and status; no test string promises a
  minute while blocked.
- ZERO-CLICK: nothing added; one typed value per install.

R2. Put the build caveat on the verdict.
- Action: while a build alert is set, the overlay card's third line is a
  short alert head (34 characters: "Build is for a Ranger", "Build is
  from level 62", "No build for <name>") and the dashboard prints the
  alert sentence directly under the verdict sentence.
- Impact: H. The warning travels with the advice (F2). Effort: S.
- Risk: the third line loses the top stat while the alert lasts.
- ToS check: text from Client.txt and the pasted build only; overlay
  stays within 2 lines plus one 3-line card.
- Depends on: plan section 03 and the design reviewer for the line
  choice (Open question 3). Files: server/al/state.py, web/app.js,
  web/tc.js, tests/test_eval_text.py, tests/test_build_live.py.
- Acceptance test: exact-output tests for the three heads; a snapshot
  with an alert and a fresh item check carries the head in `card.line3`.
- ZERO-CLICK: appears and clears by itself with the alert.

R3. A build prompt with its own button, from the first minute.
- Action: show the "Your build" card as soon as the opt-in is given and
  no build is loaded, without waiting for a character name; give it and
  the three alert sentences one button, "Paste a build", that shows the
  Build tab and puts focus in the paste box; the Build empty text says
  where a code comes from (Path of Building: Import/Export, Generate,
  Copy) and that a pobb.in or pastebin link works; drop "character JSON".
- Impact: H. Every new player and every new character; T4 drops to 2
  acts and the hunt for the tab goes. Effort: S.
- Risk: a button in a card that is not a live region; keep its words.
- ToS check: the build stays user-pasted text (decision 0004); the paste
  is the player's own act; no clipboard read.
- Depends on: none. Related: note 0043 R4 (the item hotkey loads a
  copied build) would remove the tab and the paste box altogether; it
  needs a ruling on whether hotkey-read build text counts as the
  "user-pasted build text" of decision 0004. R3 stays useful either
  way: the prompt is what tells a new player a build is needed.
  Files: server/al/theorycraft/buildlive.py,
  server/al/state.py, web/buildlive.js, web/tabs.js, web/tc.js.
- Acceptance test: a consented snapshot with no build and no character
  carries the prompt; a node test clicks the button and finds Build
  shown and `#build-paste` focused.
- ZERO-CLICK: the prompt shows and leaves by itself; the paste is the
  one act the floor-safe sources leave (TC-IMPORT waits on registration).

R4. No dead ends: a copy pass over the eleven sentences and four errors.
- Action: every sentence in F3 and F12 either gets its control (0039 R2,
  R3, R5, R6) or, until then, names the exact place ("config\local.json
  in the AshLight folder") and never a script for a player task; the
  export file is called "settings backup"; fix F20 (a) to (f).
- Impact: H. Removes the wrong turn from five setups. Effort: S to M.
- Risk: a file path in a main line bends design rule P2 for a while;
  the controls remove it.
- ToS check: wording only; no new read or request.
- Depends on: 0039 R2, R3, R5, R6 for the final form. Files:
  server/al/diag.py, server/al/state.py, server/al/acts.py,
  web/index.html, web/settingsio.js, web/status.js, web/prices.js,
  app/client/starting.html, docs/design/0001-design-system.md.
- Acceptance test: a test greps player-facing strings for "settings
  file", "scripts" and ".ps1" and allows none outside a developer note.
- ZERO-CLICK: fewer wrong acts; nothing added.

R5. A README for players.
- Action: quick start = prerequisites, `setup.ps1`, then the AshLight
  shortcut; build.ps1 moves to CONTRIBUTING.md; say that Node brings the
  client, the tray, the hotkeys and the item check; add Stop, Update,
  Uninstall and Troubleshooting sections with today's real steps.
- Impact: M to H until an installer exists (T1 8 to 6 acts, 191 s less).
  Effort: S. Risk: none; 0052 R4 to R6 replace it later.
- ToS check: documentation only; the disclaimer line stays.
- Depends on: none. Files: README.md, CONTRIBUTING.md.
- Acceptance test: the quick start names one command; a doc test finds
  the words Update, Uninstall and the shortcut.
- ZERO-CLICK: two typed commands fewer.

R6. Show the overlay's state and keep the chords in view.
- Action: the client writes shown / hidden-by-you and both registration
  results to a runtime file (as it does for displays); the core
  publishes them; the Settings line and the Overlay check say "hidden by
  you - Alt+Shift+A shows it"; add a check row for the show-hide chord;
  the tray item and the Item check title carry the effective chord.
- Impact: M. An accidental hide stops being a mystery (F7, F9).
  Effort: S to M. Risk: one more runtime file to keep honest.
- ToS check: AshLight's own window state only; no window, process or
  game check (decision 0029); no input.
- Depends on: 0039 R3 (effective keys), 0039 R12 (remember the choice).
  Files: app/main.js, app/overlay_gate.js, app/client/tray_menu.js,
  server/al/diag.py, server/al/state.py, web/index.html, web/app.js.
- Acceptance test: node test, a toggle rewrites the file; pytest, the
  file's "hidden" turns the check detail; the tray label holds the chord.
- ZERO-CLICK: status only.

R7. One status vocabulary.
- Action: one table (state, dashboard words, overlay word of 15
  characters, Checks detail, next step) in one module, used by the pill,
  the overlay, Checks and the zone tile's sub line; "fix" is kept for
  faults, a pending choice is a note (F23); while the log is missing the
  tiles read "-" and the zone sub line carries the next step (F21, F12).
- Impact: M. Five wordings become one pair per state (F10). Effort: M.
- Risk: exact-output tests on both sides must move together.
- ToS check: wording only; idle still comes from Client.txt staleness.
- Depends on: plan section 03. Files: server/al/state.py,
  server/al/diag.py, web/status.js, web/checks.js,
  app/shared/render_gate.js, docs/design/0001-design-system.md.
- Acceptance test: one table-driven test feeds each state to all four
  surfaces and compares with the table.
- ZERO-CLICK: status only.

R8. Recover a refused share link in one click.
- Action: on the web-data-off refusal the status line offers "Turn on
  web data and load this link", which saves the opt-in and repeats the
  load.
- Impact: M (8 acts to 4). Effort: S.
- Risk: a privacy switch behind a button; the label must name it.
- ToS check: the click is the explicit opt-in of decision 0013; the
  fetch stays one request to an allow-listed host with the truthful
  User-Agent; nothing happens without the click.
- Depends on: none. Files: web/app.js, web/tc.js, app/test/tc_view.test.js.
- Acceptance test: node test, the refusal renders the button; a click
  posts the opt-in, then the same code once.
- ZERO-CLICK: one click replaces four acts.

R9. Undo for Clear run history.
- Action: the click hides the data and shows "Cleared. Undo" in place
  for 10 s; the files are rewritten only after that.
- Impact: L to M (rare, but the loss is permanent). Effort: S.
- Risk: a core exit inside the 10 s must leave the data intact.
- ToS check: local files of decision 0036 only; no modal (design N2).
- Depends on: none. Files: web/history.js, server/al/core.py,
  server/al/http.py, tests/test_run_history.py.
- Acceptance test: clear then undo inside 10 s leaves the file
  byte-identical; clear and wait empties it.
- ZERO-CLICK: nothing in play.

R10. Make the Settings tab the index, and tidy two defaults.
- Action: a short list on top of Settings names every switch with a
  jump that shows its tab and focuses the control (web data, run
  history, stat weights, stop reading, show or hide overlay); the tips
  button becomes secondary and moves into the fold; the stat weights
  fold starts closed.
- Impact: M to L. One place answers "where is the switch" (F11); the
  Items tab drops from 52 controls to about 8 at first sight (F17).
  Effort: S. Risk: jump targets must stay in sync with the tabs.
- ToS check: layout only.
- Depends on: plan section 03 (the tab set may change). Files:
  web/index.html, web/tabs.js, web/app.css, app/test/tabs.test.js.
- Acceptance test: each jump shows the right tab and focuses its
  control; a capture of the empty Items tab counts under 12 tab stops.
- ZERO-CLICK: one click instead of a search.

R11. On the overlay, a name beats "Trade link ready".
- Action: line 2 of the item card shows the price only when there is a
  poe.ninja value; otherwise the item name stays.
- Impact: M to L, every check while web data is off. Effort: S.
- Risk: decision 0017 item 2 gives the overlay "a short notice" for the
  link; R11 drops that notice when no value exists, so it needs a
  recorded amendment of 0017 item 2 (decision, alternatives, why). The
  settled part of 0017 (no trade2 call, a URL the player opens) is
  untouched, and 0016's merged-card rule stays.
- ToS check: cached poe.ninja value only; the trade link stays a
  dashboard link the player opens.
- Depends on: the design reviewer. Files: server/al/state.py,
  tests/test_price_text.py, docs/design/0001-design-system.md.
- Acceptance test: a link card without a value keeps `line2` = name.
- ZERO-CLICK: unchanged.

R12. Check the default chords against the Windows layout switch.
- Action: one operator press per chord with two keyboard layouts
  installed; if the layout flips, pick defaults without the Alt+Shift
  pair and let 0039 R3 fall back by itself when a chord is taken.
- Impact: M for players with two layouts. Effort: S after the check.
- Risk: every other pair has its own clash (MS-KEYS); test before
  changing decision 0014 F1's default.
- ToS check: an AshLight hotkey only; nothing is sent to the game.
- Depends on: the batched operator ask (plan section 09); 0039 R3.
  Files: app/main.js, server/al/hotkeys.py, app/test/hotkey_cases.json.
- Acceptance test: the operator's result is recorded; the case table
  names the layout chords.
- ZERO-CLICK: no layout flips while playing.

## Phone view: options and costs (operator decision, not made here)

Today: the server binds 127.0.0.1 only (server/al/http.py:94), the Host
list holds two local names (http.py:96-97), the footer promises "This
page can't be opened from another device" (web/index.html:617), and the
access token is 48 characters per start (http.py:75-76). The dashboard
already lays out at 320 px (design 0001 section 4). What a phone adds
over the overlay: the full trade list, the item card's sentences and the
zone guide, without leaving the game window; the gain is largest on one
monitor. Research 0045 holds the security side of designs A to C.

- P0 None. Player steps 0, project cost 0. One-monitor players keep the
  overlay and switch windows for the rest.
- P1 A narrow companion window on the same PC. Works today, touches no
  rule. Cost: check the layout under 1024 px (PACK has no such capture).
- P2 The phone as an extra display (0045 design A). Once: a driver on the
  PC and a viewer app on the phone (SD). Per session: start the viewer;
  the window place is remembered. AshLight change: none. Costs: a
  third-party display driver on the gaming PC (frame cost UNVERIFIED); a
  tap on the phone is a mouse click on the PC and can take focus from
  the game; text is small unless the window is narrow.
- P3 A private tunnel to the loopback port (0045 design B). Once: an
  account, an app on PC and phone, HTTPS on, one serve command (TS). Per
  session: a bookmark, if a lasting read-only key exists. AshLight
  change: read-only key, a phone page with no POST, one more Host name,
  an "on" mark, new footer words. Costs: a third party in the trust
  base; whether "LAN access stays off" allows it is the operator's
  reading.
- P4 An opt-in, read-only LAN listener (0045 design C). Once: a tick and
  the Windows firewall prompt, which needs an admin account (MS-FW). Per
  session: a bookmark or a scanned code. AshLight change: the most; a
  pairing code is needed because 48 characters cannot be typed and the
  standard library has no QR encoder. Costs: it reverses the bind rule;
  plain HTTP lets anyone on that Wi-Fi read zone, level and whispers; it
  must refuse public networks.

P3 and P4 share a read-only glance page and should wait for 0045 R1, R3,
R10, R11. Cost rises from P0 to P4; the decision is Open question 1.

## Cut or merge

- Cut from the README quick start: build.ps1 and the three run.ps1
  variants (R5).
- Cut "character JSON" from the Build empty sentence; the paste path
  stays (R3).
- Cut, after a coverage check: the price-card words for searching,
  waiting, listed, "Web data is off" and "Contact not set"
  (server/al/state.py:554-562, 674-699; web/prices.js:202-209).
  price.py now publishes only a link or an error (server/al/price.py:
  44-66), so they look unreachable; design 0001 section 9 still lists
  them.
- Merge the "not an item" sentence shown twice into one (F20 d).
- Merge the two under-level lines on Play into one (F22; 0043 picks).
- Merge five idle wordings and three log-missing wordings into one pair
  each (R7).
- Merge the tips button into the Settings fold (R10).

## Rejected

- One press for an item check, with AshLight sending Ctrl+C: synthesized
  input, floor. Two chords is the minimum.
- Checking an item as soon as it is copied: a clipboard watcher, floor.
- Invite or reply buttons that type into the game chat: input, floor
  (research 0038 lists it the same way).
- Reading Path of Building's own build folder to skip the paste: not on
  the floor's read list, and decision 0004 gives AshLight only
  user-pasted build text; none of its reverse conditions is met. Note
  0043 R3 recommends this read behind its own opt-in and a new
  decision; the two notes conflict and the plan needs one ruling
  (Open question 7).
- Finding the game window or process to say "game closed" for certain or
  to show the hotkeys in place: decision 0029.
- Reading the game's key bindings or config to avoid chord clashes: a
  game file, outside the Client.txt allowance.
- Turning web data on by itself when a link is pasted: decision 0013;
  R8 keeps the click.
- A first-run wizard, a confirm dialog, a toast or a sound: design 0001
  N2 and principle 3; R3 and R9 do the same work in place.
- A LAN bind by default or a cloud relay for the phone: the bind rule
  and the local-only promise (research 0045).

## Open questions

1. OPERATOR DECISION: phone view P0 to P4 (with research 0045 question 1).
2. OPERATOR ACT, one minute, for the batched ask: with two keyboard
   layouts installed, does Alt+Shift+E or Alt+Shift+A also switch the
   layout? UNVERIFIED (F8). If yes, an adjudicator picks new defaults.
3. Design reviewer, plan section 03: which overlay line carries the build
   caveat (R2), and does a name replace "Trade link ready" (R11)?
4. Plan section 03: should Settings own the switches or index them (R10)?
5. UNVERIFIED: the frame cost of display-extension software (P2).
6. Unknown: how many players use a browser tab instead of the client.
   It sets the severity of F19; AshLight has no telemetry and wants none.
7. Plan ruling (adjudicator or operator): this note rejects reading Path
   of Building's builds folder (the floor's read list and decision 0004
   name only user-pasted build text); note 0043 R3 recommends it behind
   an opt-in. Also whether a build read by the item hotkey (0043 R4)
   counts as user-pasted text under decision 0004.

## Verification

Independent verifier, 2026-11-18, against HEAD and the evidence pack.

Checked:
- Code citations: about 85 cited path:line ranges opened, covering every
  finding and every recommendation's evidence (F1 to F23, T1 to T14,
  the state-by-state list, the phone-view facts). All but the items
  below said what the note says.
- Evidence pack: every number in the Summary and the findings re-read
  from up-evidence run/summary_lines.txt and its README (84, 161, 197,
  365, 397 and 419 words; 52 controls; 21, 166, 321, 380 and 541 px;
  135 captures; the state c overlay composite shows "Upgrade +21 vs
  Gloves / Trade link ready" for a Sorceress against a Ranger build).
- The Summary's act counts re-derived from the walks: 8 + 1 + 3 + 2 =
  14 (README), 6 + 1 + 3 + 2 = 12 (shortest), 3 + 1 + 2 + 2 = 8
  (installer and R3).
- Web sources: all 10 re-fetched on 2026-11-18 and their content
  re-read (NN10, NNSEV, MS-LANG, MS-KEYS, EL-GS, MS-FW, TS, SD, EE2-DL,
  EE2-QS); each supports the claim it is cited for.
- ToS floor: all 12 recommendations and the five phone options tested
  against each floor rule; none needs the floor bent. R8 keeps the
  web-data opt-in an explicit click; R12 is the operator pressing an
  AshLight hotkey, nothing synthesized.
- Settled decisions: checked R1 against 0015, R11 against 0016 and
  0017, R12 against 0014, R6 and R7 against 0029, R9 against 0036,
  R8 against 0013.

Corrected:
- F3 count: eleven sentences, not nine (ten live); Summary and R4
  follow. Rule 4 nuance added (its list does not name paths).
- F11: "Restart overlay" is also a filled button; the claim that the
  tips button was the only one was wrong.
- R11: it amends decision 0017 item 2 (the overlay's short notice), not
  only 0016's wording; it now says an amendment must be recorded.
- R1: added the decision 0015 / 0036 constraint on where the contact
  field writes.
- Method: H8 is "aesthetic and minimalist design" (NN10).
- Sources: EE2-DL extra steps are for PoE1 migrants; the portable build
  does not self-update.

Cross-references added now that the sibling notes exist:
- 0043 R3 (PoB builds folder) conflicts with this note's Rejected list:
  Open question 7.
- 0043 R4 (item hotkey loads a copied build) complements R3.
- 0043 R1 and 0040 R2 (Play fits its column) own T6, T7 and F17's
  overflow; 0043 R6 (four tabs, closed folds) overlaps R10.
- 0044 R8 (item-check empty text) touches the same sentence as F9 and
  R4; one copy change should serve both.
- 0040 R3 (stale and empty values look stale) overlaps F21 and R7.

UNVERIFIED (unchanged):
- F8 / R12: whether Alt+Shift+E or Alt+Shift+A flips the keyboard
  layout in play (no input may be sent; Open question 2). MS-KEYS does
  not list Left Alt+Shift; MS-LANG does.
- P2: the frame cost of display-extension software (Open question 5).
- F21's "0" deaths reading rests on the pack capture of state e, not on
  a code path traced end to end.
