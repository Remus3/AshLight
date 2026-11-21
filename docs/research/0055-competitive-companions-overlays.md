# 0055 - Competitive review: other games' companions and overlay platforms (patterns)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B16
competitive review: other games and overlay platforms. Design patterns only,
taken from overlay platforms (Overwolf, Xbox Game Bar), action-RPG and MOBA
companions, web loadout managers, combat-meter and aura add-ons, parser
overlays, sim-racing dashboards, OS notification guidance, subtitle
legibility over video and glance rules from watches and cars. PoE tools are
note 0054; features note 0038; utilities and settings note 0039; usability
note 0042. No code, asset or text of any tool is copied.
Status: verified

## Sources (all accessed 2026-11-18, local time)

Overlay platforms
- OW-SS: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/second-screen
  (second-screen windows open by themselves at game start, go to the
  largest monitor the game is not on, follow the game if it moves,
  remember their place; at-a-glance content, no interaction expected in
  play; the page also pitches second screens as ad space, and a banner
  says Overwolf approves only apps that use its monetization from
  2026-11-01).
- OW-OVL: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/in-game-overlays
  (advice, not a hard rule: avoid blocking game UI; avoid semi-transparent
  widgets that reduce clarity; put hotkey reminders in widgets or screens;
  window kinds: lobby, loading, in-game overlay, widget, second screen).
- OW-HK: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/hot-key-and-settings
  (rebind inside the app; a key that conflicts with another app is added
  as unassigned; tell users which keys are assigned and when they change;
  remind users of the key when a window does not open by itself; offer
  passthrough).
- OW-FTUE: https://dev.overwolf.com/ow-native/guides/general-product/first-time-user-experience
  (tutorial as short as possible; the app's value fits one sentence; let
  users do the action rather than read about it; respect the match).
- OW-BP: https://dev.overwolf.com/ow-native/guides/general-product/best-practices
  (app windows need close and minimize controls; a concise message per
  possible error. Re-fetched by the verifier: the page does NOT say to
  hide windows while the game is alt-tabbed, so that claim is removed).
- GB-MODES: https://learn.microsoft.com/en-us/gaming/game-bar/designguide/gamebar-modes
  (Game Bar widgets: plan for at least 2 widgets open; desktop widths 240
  to 600 epx, compact 464 to 900 epx; page dated 2024-09-09).
- GB-UI: https://learn.microsoft.com/en-us/gaming/game-bar/designguide/widgetui
  (one content set, shown at a larger scale in compact mode; every input
  method has explicit states; page dated 2024-09-09).

OS and platform notification and glance guidance
- AP-NOTIF: https://developer.apple.com/design/human-interface-guidelines/notifications.md
  (one notification per thing, never repeated while unanswered; an app in
  the foreground inserts the item into its view instead of notifying; a
  short look appears only briefly, so it is never the only carrier of
  critical information; keep private data out; change log 2023-10-24).
- AP-WATCH: https://developer.apple.com/design/human-interface-guidelines/designing-for-watchos.md
  (glanceable single-screen interactions, many concise interactions of
  under a minute each, anticipate needs from on-device data; change log
  2023-06-05).
- WEAR-TILE: https://developer.android.com/design/ui/wear/guides/surfaces/tiles
  (immediate, predictable, relevant: only the most critical bits, one
  task per tile, content fits the current situation).
- MS-NOTIF: https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/app-notifications-ux-guidance
  (notifications must not be noisy; suppress into Notification Center
  instead of alerting; respect Focus Sessions; clear notices the user has
  already seen elsewhere; page updated 2026-04-21).
- WCAG-221: https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
  (a message that disappears by itself is fine under SC 2.2.1 when the
  same information can be found elsewhere; otherwise it needs turn off /
  adjust / extend).
- NNG-IND: https://www.nngroup.com/articles/indicators-validations-notifications/
  (indicators vs validations vs notifications; passive notices are easy
  to miss, so key information never relies on them alone; never a fading
  toast for an error; 2024-01-17).

Glance rules from driving and displays
- NHTSA: 78 FR 24818, Visual-Manual NHTSA Driver Distraction Guidelines
  for In-Vehicle Electronic Devices, 2013-04-26,
  https://www.govinfo.gov/content/pkg/FR-2013-04-26/pdf/2013-09883.pdf
  (read from the PDF text: mean glance away 2 s or less, 85 percent of
  glances 2 s or less, 12 s total eyes-off-road per task; glances over
  2.0 s correlate with crash risk; displaying automatically scrolling
  text is a per se lock out; 24 test participants suffice for the glance
  protocol, 21 of 24 must pass). Verifier correction: the 30-character
  reading limit (punctuation not counted) was in the 2012 proposal, taken
  from the Japanese JAMA guidelines; this final notice drops the character
  count and locks out kinds of non-driving text (books, web pages, social
  media, ads) instead. The 30 characters are not a final NHTSA rule.
- FHWA: In-Vehicle Display Icons and Other Information Elements, Vol. I,
  FHWA-RD-03-065, 2004-09,
  https://www.fhwa.dot.gov/publications/research/safety/03065/03.cfm
  (text characters at least 16 arcmin (0.27 deg) of visual angle,
  preferred 24 (0.40 deg); icons at least 41 arcmin, preferred 85; the
  discussion puts critical symbols at least 20 arcmin; legibility starts
  to drop below about 18).

Text over video
- BBC-W3C: BBC review comments to the W3C, 2014-12-04,
  https://lists.w3.org/Archives/Public/public-pfwg-comments/2014OctDec/0003.html
  (outlines and drop shadows are no general substitute for a solid
  background: white text with shadow fails over bright footage such as
  snow; shadows add visual busyness; let the box extend a little past the
  text; a box kept on screen with no text obscures video for nothing, so
  keeping it must be optional, not preferred).
- RTSS-FILL: https://wccftech.com/how-to-set-up-high-quality-performance-overlays-with-rtss/amp/
  (2026-01-01; the RivaTuner Statistics Server on-screen display has an
  "On-Screen Display fill" option that puts a translucent black box behind
  the stats; the guide does not mention shadow or outline settings). The
  frame-rate OSD class reaches the same answer as subtitles: a box, not
  just a shadow.

Companions, add-ons, parsers, dashboards (search-result summaries and
third-party pages; product claims marked UNVERIFIED where used)
- BLITZ: https://www.wombocombo.gg/blog/game-analytics/blitz-gg-overlay-review
  and https://sourceforge.net/app/blitz/ (a MOBA companion. The
  SourceForge listing, re-fetched by the verifier, confirms build
  suggestions during champion select, builds applied automatically, data
  overlaid on the selection screen and post-game summaries; an in-match
  overlay and a premium tier are UNVERIFIED (the listing says "Free")).
- MOBA-OVL: https://mobalytics.gg/lol/glp/app-download (same class;
  page not opened, the guide page returned 403).
- DIM-GH: https://github.com/DestinyItemManager/DIM (web item and
  loadout manager, MIT, licence re-checked) and DIM-LO: https://maxroll.gg/destiny-2/resources/loadout-optimizer-guide-destiny-2
  (the player ticks stat priorities, best loadouts sort to the top).
- WA-LOAD: WeakAuras load conditions as summarised in search results from
  the WeakAuras wiki mirror and player forums (a display loads only while
  every ticked condition holds; conditions are ANDed; "In Combat" is a
  tristate load option). UNVERIFIED: the live wiki Load-Options page is
  empty, so this rests on community text.
- OP-SETUP: https://overlayplugin.github.io/docs/setup (place the overlay,
  then tick Lock overlay); CB-README:
  https://github.com/OverlayPlugin/cactbot/blob/main/README.md (setup
  ticks "Lock Overlay" and "Enable Clickthrough"; untick clickthrough
  only to click lines); OP-REL: https://github.com/ngld/OverlayPlugin/releases
  (v0.17.3 added an option to hide overlays outside combat). A "hide while
  the game is not the active window" option was not found in these
  pages: UNVERIFIED.
- SIM-TAB: https://simxpro.com/blogs/guides/simhub-dashboard-on-a-tablet-cheap-second-screen-setup-that-works
  (a second-screen race dash starts with four items, the gear big and
  central; big gear plus revs beats tiny graphs; stability matters more
  than refresh rate; if the dash takes more than a split second to read,
  simplify).
- SIM-PERIPH: https://shop.germansimracing.de/en/blogs/kaufberatung/dashboard-simracing-nachruesten
  (shift lights are seen in peripheral vision and hold the eye less than
  numbers; search summary, page not opened, UNVERIFIED).

Repo (read 2026-11-18)
- design 0001 sections 2, 3, 5.2, 6, 7, 10 (docs/design/0001-design-system.md);
  decisions 0003, 0014, 0019, 0029, 0038, 0041; research 0038, 0039,
  0042, 0054.
- Code cited inline as path:line.
- Measured locally: Segoe UI cap height 0.7002 em, x-height 0.5000 em
  (OS/2 table of the system font file, scratch script under
  <sidecar>\Scratch\up-0055).

## Summary

- AshLight already follows most of what the large platforms teach:
  overlay = short look, dashboard = long look (AP-NOTIF); a fixed content
  cap; no OS toasts in play (MS-NOTIF); context-driven visibility
  (WA-LOAD, decision 0029); inferred character, league and monitor scale.
  The gaps are small and cheap.
- Biggest gap (R1): on first run the companion window opens centred on
  the primary display (app/client/link.js:88-95), which is where the game
  runs in Windowed Fullscreen. Overwolf puts second-screen windows on the
  largest monitor the game is not on (OW-SS). Infer it: the largest
  display the overlay is not on, no question asked.
- Distance legibility (R2): read at 80 cm on a 24 inch 1080p second
  monitor, the two-column Play tab's labels (13.6 px, 13 px in a short
  window) and sub lines (14.4 px) subtend 11.3 (10.8) and 12.0 arcmin,
  under the 16 arcmin floor drivers' displays use (FHWA). Glance numbers
  (26.7 to 36.6 arcmin) are fine. Hand this to the
  typography note 0041 and plan section 03 as a measured rule.
- Same-thing-twice (R3): a buyer who re-sends the same whisper gets a
  second trade card (server/al/state.py:1556-1560). Apple's rule is one
  notice per thing; refresh the existing card instead.
- Teach the hotkey where it is used (R4): Overwolf asks for hotkey
  reminders in the overlay itself (OW-OVL, OW-HK). Use the empty card
  slot for a self-retiring "Alt+Shift+E: check a copied item" line.
- Formalise two rules as tests (R5, R6): every overlay item that leaves by
  itself has a dashboard twin that stays (WCAG-221, AP-NOTIF short look);
  the card's first line leads with the verdict, no overlay text ever
  scrolls (NHTSA final rule) and no OS toast fires in play (MS-NOTIF).
- Rejected: Overwolf as a runtime, foreground-window detection, auto-import
  into the game, sound, flashing urgency, user scripting, parser-style
  memory or packet reads, monetised second screens.

## Current state

- Overlay content cap: 2 HUD lines plus one 3-line card, never two cards
  (docs/design/0001-design-system.md:598-603). Card lines are clipped at
  34 characters each (app/shared/format.js:120-125), so a card can carry
  about 100 characters.
- Card lifetimes: item check and price cards 20 s (server/al/state.py:35,
  39), trade cards 600 s (server/al/state.py:31), at most 5 open trade
  cards, oldest dropped (server/al/state.py:28); the overlay leaves the
  card slot at `expires_at` (app/shared/render_gate.js:27-49).
- Dashboard twins exist: the Item check card on Play keeps every compared
  slot; the trade list keeps requests with a dismiss
  (docs/design/0001-design-system.md:322-345).
- Trade whispers: every incoming trade whisper appends a new card
  (server/al/state.py:1556-1560); a finished trade closes one card, by
  name or the oldest (server/al/state.py:1310-1321, decision 0019); old
  cards expire (server/al/state.py:1301-1308). No merge of repeats.
- OS notifications: one tray balloon, once, when the window first closes
  to the tray, silent (app/client/window.js:225-232). Nothing else.
- Companion placement: saved bounds when still visible, else centred on
  the primary display at the default size (app/client/link.js:71-95,
  app/client/window.js:147-150). The overlay defaults to the primary
  display, top-right (app/shared/layout.js:26).
- Inferred settings already in place: monitor-height scale
  (app/shared/layout.js:47-50, UX-DPI), character from Client.txt
  (decision 0038), league from poe.ninja (decision 0026), overlay hides
  while the log is idle (decision 0029 amendment).
- Overlay legibility: 92 percent plate plus 1 px text shadow, opacity
  floor 0.9 (app/shared/layout.js:31,
  docs/design/0001-design-system.md:216-243, 604-617); the card plates
  hide when their text is empty (app/overlay/overlay.js:27, 30 set
  `hidden`; app/overlay/overlay.css:43), empty status and timer spans
  collapse (app/overlay/overlay.css:65, 69).
- Type sizes on the two-column Play tab (900 x 560 or more): stat label
  13.6 px (web/app.css:114; 13 px when the window is 820 px tall or less,
  web/app.css:567), stat sub line 14.4 px (web/app.css:545), zone timer
  20.8 px (web/app.css:541), glance numbers clamp 32 to 44 px
  (web/app.css:539); body 16 px; overlay secondary and status 13 px
  (app/overlay/overlay.css:67, 89), trade and item cards 14 px, HUD 15 px,
  zone 16 px (app/overlay/overlay.css:52, 59, 84, 107;
  docs/design/0001-design-system.md:52-92).

## Findings

F1. Short look and long look: AshLight has the right split. Apple's watch
notifications come in two stages: a short look that disappears and must
never be the only carrier of critical information, and a long look with
detail (AP-NOTIF). WCAG treats a self-dismissing message as fine only when
the information is available elsewhere (WCAG-221); NN/g says the same of
passive notices (NNG-IND). AshLight's overlay card (20 s or 600 s) is the
short look and the dashboard card is the long look. Nothing enforces the
pairing: a future overlay card kind (0038 R2 proposes zone and act cards)
could ship without a twin. Matters to the player: a card missed in a fight
is still on the second screen.

F2. Second-screen placement is not inferred. Overwolf's rule: open the
second-screen window at game start, on the largest monitor the game is not
on, remember the user's place (OW-SS). AshLight's first run centres the
companion on the primary display (app/client/link.js:88-95). In Windowed
Fullscreen (the only supported mode, CLAUDE.md) the game normally sits on
the primary display, so the companion starts under the game and the player
must find and drag it once. It is remembered afterwards, so the cost is
one-time, but it lands in the first minute, where 0042 and 0054 R1 put the
most weight.

F3. Glance budgets from driving give hard numbers the design lacks. NHTSA:
mean glance away 2 s or less, 85 percent of glances 2 s or less, at most
12 s total per task, no automatically scrolling text (NHTSA). A 30
character per-task reading cap appears in the 2012 proposal and the JAMA
guidelines, but the final notice dropped it, so it is a heuristic, not a
rule. Design 0001 asks for "one fixation, <= 5 words" per HUD line
(docs/design/0001-design-system.md:627-629) while the card allows 3 x 34
characters (app/shared/format.js:121). The verdict is already the first
word of the card head, so a 2 s glance gets the answer; this is not
written down or tested. No overlay text scrolls today (nowrap plus
ellipsis, app/overlay/overlay.css:58).

F4. The dashboard is read at second-screen distance, and its small text is
below the drivers'-display floor. FHWA puts text at 16 arcmin minimum and
critical symbols at 20 (FHWA). With Segoe UI cap height 0.7002 em
(measured) on a 24 inch 1080p panel (0.2768 mm per pixel at 100 percent)
the visual angle is:
- at 80 cm: short-window label 13 px 10.8, label 13.6 px 11.3, sub line
  14.4 px 12.0, body 16 px 13.3, zone timer 20.8 px 17.3, glance numbers
  32 to 44 px 26.7 to 36.6 arcmin;
- at 60 cm: 13 px 14.4, label 15.1, sub line 16.0, body 17.8, timer 23.1
  arcmin.
To reach 16 arcmin at 80 cm the font must be at least 19.2 px; 20 arcmin
needs 24 px; the FHWA preferred 24 arcmin needs 28.8 px. The glance
numbers pass; the labels that name them (LEVEL, DEATHS) and the Play sub
lines do not. (Verifier re-computed every figure: cap height x 0.2768 mm
per px, angle = atan(height / distance).) The 80 cm distance and the panel
are assumptions (the operator's real setup is unknown): a sim-racing dash
solves the same problem by showing fewer, bigger things (SIM-TAB). The
overlay is read at desk distance on the game monitor; its 13 px status
words (`N lv under`, `Cold res 32%`) are 14.4 arcmin at 60 cm, under 16,
and they carry a warning, so they are the overlay's critical text.

F5. Repeated whispers make repeated cards. Apple: never send several
notifications for the same thing, even when the user has not answered
(AP-NOTIF); Windows: notifications must not be noisy (MS-NOTIF). In PoE2
trade a buyer often re-sends the same whisper when the seller does not
answer at once. Each one appends a card (server/al/state.py:1556-1560):
two re-sends of one request fill 3 of the 5 slots, the overlay reads "+2
more", and a sixth whisper pushes out an older real buyer
(server/al/state.py:28).

F6. Hotkey teaching happens away from the moment of use. Overwolf asks for
hotkey reminders inside widgets and overlays, and for a reminder whenever a
window does not open by itself (OW-OVL, OW-HK). AshLight shows its chords
on the dashboard (0042 R6) but the overlay, where the player is when they
need Alt+Shift+E, never names it. The empty card slot (design 0001
section 10) is free most of the time.

F7. Context-loaded visibility is the shared pattern of aura add-ons,
parser overlays. WeakAuras displays load only while their conditions hold
(WA-LOAD, UNVERIFIED wording); OverlayPlugin can hide overlays outside
combat (OP-REL). AshLight does the same through Client.txt context
(design 0001 section 7.2, decision 0029 hide on idle). A further variant,
hiding while the game is not the active window, was not found in the
pages read (UNVERIFIED) and would need a foreground-window query, which
decision 0029 settles against (see Rejected).

F7b. Click-through is the settled default of the parser class: place the
overlay, then lock it and turn on click-through, untick it only to click
a line (OP-SETUP, CB-README). AshLight goes one step further: the overlay
is always click-through and is placed from the dashboard (design 0001
section 10, placement), so there is no unlocked state that could catch a
game click. Adopted already; no change.

F8. Notification policy is already right and should be written as a rule.
Apple: an app in the foreground inserts new items into its view instead
of notifying; Windows: suppress into Notification Center, respect Focus
Sessions (AP-NOTIF, MS-NOTIF). AshLight sends one silent tray balloon in
its life (app/client/window.js:225-232) and otherwise puts news into the
dashboard and the card slot. No written rule stops a later feature from
adding a Windows toast for a price move or an upgrade.

F9. Text over bright scenes: AshLight's plate matches the subtitle
guidance. BBC: a shadow or outline is no substitute for a solid box over
bright footage; let the box run past the text; an empty box obscures the
picture for nothing; shadows add busyness (BBC-W3C). The frame-rate OSD
class offers the same answer, a translucent fill box (RTSS-FILL).
AshLight uses a 92 percent plate with 5 to 10 px padding
(app/overlay/overlay.css:47, 78, 101) and hides empty card plates
(app/overlay/overlay.js:27, 30). The 1 px text shadow is redundant on a 92 percent plate; it is not
harmful at 1 px and design 0001 cites a games source for it, so no change
is worth a package (see Cut or merge).

F10. Density by phase. MOBA companions put the dense content before the
match (picks, build) and a review after it (BLITZ listing, verified);
the thin in-match overlay is UNVERIFIED for Blitz. The PoE2 analogue is hideout / town
(dense: vendor string, build, upgrades), map (thin: 2 HUD lines) and the
return after a map or death (summary). Note 0038 R6 "Play follows the
context" already proposes the Play tab switching by context; this review
adds the post-map moment as its third state (R7) rather than a new
package.

F11. Onboarding in one sentence, by doing. Overwolf: the app's value must
fit one sentence; tutorials as short as possible; let users perform the
action (OW-FTUE). Note 0054 R1 (setup card on Play) and R2 (sample card)
cover the structure; this review adds the sentence test and the "do it
once" step (R4 is the doing step for the item check).

F12. Settings inferred, not asked: the platforms infer the context from
data the app already has (AP-WATCH "anticipate needs from on-device
data"; BLITZ fits suggestions to the champion being picked, per its
listing). AshLight infers
character, league, monitor scale and (0039 R6) the log path. The open
inference gaps are the companion's monitor (F2) and the hotkey conflict
heal (0039 R3). Distance cannot be inferred (F4), so it stays a size
control with a good default.

F13. Urgency encoding: peripheral detection favours a coloured block or
edge over text (SIM-PERIPH, UNVERIFIED), which design 0001 already uses
(steady warn edge plus a word, section 6). The two platforms say avoid
low-clarity translucency (OW-OVL); AshLight's opacity floor 0.9 holds that.
No change.

F14. Privacy on the overlay: Apple keeps private data out of short looks
because others may see the screen (AP-NOTIF). AshLight's trade card shows
the buyer's character name; a player who streams with a display capture
shows it too. Low impact, no evidence of demand: Open question 2.

F15 (added by the verifier). Toast timing: none of the sources read gives
a fixed on-screen duration. WCAG's own example is a 5 s toast that is
acceptable only because the inbox holds the same news (WCAG-221); NN/g
reports a user who missed a 5 s error toast and waited minutes (NNG-IND).
The lesson is the pairing, not a number: AshLight's 20 s item card and
600 s trade card (server/al/state.py:31, 35, 39) are long by toast
standards and both have a dashboard twin, which R5 locks in. No change to
the durations.

## Recommendations

R1. Put the companion window on the second monitor by itself on first run.
- Action: when there is no usable saved window state and 2 or more
  displays exist, centre the companion at its default size on the
  largest work area that is not the overlay's display (the overlay
  layout's `display`, default primary, app/shared/layout.js:26; the
  player puts the overlay where the game is, so it stands in for the
  game's monitor without any window query); ties: the first in
  Electron's order; one display keeps today's centred placement.
- Impact: M. Every two-monitor player saves a find-and-drag in the first
  minute; AshLight's main surface is the second screen.
- Effort: S.
- Risk: L. A player whose game runs on a non-primary display and who has
  not moved the overlay there yet may get the companion on the game
  display; the saved place wins from the second start on.
- ToS check: game process and input rules untouched; uses Electron's
  display list only, no window or process enumeration of the game
  (decision 0029 stays intact).
- Depends on: none.
- Files likely touched: app/client/link.js:71-96 (windowBounds takes the
  display list and the overlay display's index), app/client/window.js:147-150,
  app/test (a link.js unit test).
- Acceptance test: unit test with work areas [primary 1920x1080, second
  2560x1440], overlay on primary and no saved state returns bounds inside
  the second area; overlay on the second returns the primary; one area
  returns today's centred bounds; saved visible bounds still win.
- ZERO-CLICK: fully automatic on first start; no question.

R2. A measured distance rule for the type scale (input to 0041 and plan 03).
- Action: write in design 0001 section 3 that Play-tab text a player
  reads in play (tile labels, sub lines, status words) subtends at least
  16 arcmin and critical text 20 arcmin at the reference setup (24 inch
  1080p, 80 cm for the dashboard; 60 cm for the overlay), which gives
  Play labels and sub lines >= 19.2 px (1.2rem), and overlay status words
  at the HUD-number size 15 px (16.7 arcmin at 60 cm and scale 1.0; 15.8
  at the 0.95 scale floor, accepted as rounding); set-once tabs keep
  today's sizes.
- Impact: H for the player who glances at the second screen mid-map; the
  numbers already pass, the words that name them do not (F4).
- Effort: S for the rule and a test; M if the Play layout must reflow.
- Risk: M. Bigger labels cost space on a 900 px column; 0041 must check
  the two-column layout at 900 x 560 (design 0001 section 3).
- ToS check: display only; no floor rule touched.
- Depends on: 0041 typography review and plan section 03 decide the
  final tokens; R2 supplies the measured floor.
- Files likely touched: docs/design/0001-design-system.md section 3,
  web/app.css:114, 545, 567 (Play tile label and sub line sizes),
  app/overlay/overlay.css:67 (.status), tests/test_ux_review.py (a size
  floor check).
- Acceptance test: a test reads the Play-tab label and sub-line font sizes
  and the overlay .status size from the CSS and asserts the arcmin values
  at the reference setup are >= 16 (formula and constants in the test).
- ZERO-CLICK: no interaction; the existing UI scale control stays for
  players at other distances.

R3. One card per trade request: refresh, do not repeat.
- Action: when an incoming trade whisper has the same sender and the same
  item text as an open card, update that card's `at` (it restarts its
  600 s) and price fields instead of appending; the overlay and the trade
  list keep its position; recent whispers still log every line.
- Impact: M. Fewer phantom "+N more", no real buyer pushed out of the
  5-card deque by one impatient one (F5).
- Effort: S.
- Risk: L. Two genuine requests for two identical items from one buyer
  merge into one card; the whisper log still shows both lines.
- ToS check: Client.txt reading only (decision 0003); no input, nothing
  sent to the game.
- Depends on: none. Decision 0019 (a finished trade closes one card) is
  unchanged.
- Files likely touched: server/al/state.py:1556-1560 and a helper next to
  _trade_row (1323), tests (the trade card test file).
- Acceptance test: feed three identical trade whispers from one sender
  and one from another; trade_requests has 2 rows, the first with the
  newest `at`; a "Trade accepted." line still closes one card.
- ZERO-CLICK: automatic.

R4. Teach the item-check key in the empty card slot, then retire the hint.
- Action: while the card slot is empty and the player has never pressed
  the item-check hotkey on this install, the overlay shows one muted line
  `Alt+Shift+E: check a copied item` (the real chord, from the hotkey
  status); it leaves for good after the first press or after 3 game
  sessions, whichever comes first.
- Impact: M. The overlay is where the key is needed, and the platform
  guidance asks for the reminder exactly there (OW-OVL, OW-HK).
- Effort: S.
- Risk: L. One more string in the card slot; it never competes with a
  trade or item card (they take the slot).
- ToS check: no input to the game; the hint only names a key the player
  presses themselves; no clipboard read is caused by the hint (the read
  stays one per press, decision 0003).
- Depends on: the bound chord (default `Alt+Shift+E`, app/main.js:34,
  canonical form from app/hotkey.js); 0039 R3 makes it rebindable and the
  hint reads whatever is bound.
- Files likely touched: app/overlay/overlay.js, app/shared/render_gate.js
  (slot priority), a small "seen" marker under ops/runtime, server or
  client state for the first press.
- Acceptance test: render-gate test: empty slot plus never-pressed shows
  the hint; any card hides it; after a recorded press it never returns;
  the hint text uses the bound chord string.
- ZERO-CLICK: appears and retires by itself; the press it teaches is the
  manual press the floor requires (decision 0003).

R5. Rule and test: every self-leaving overlay item has a dashboard twin.
- Action: add to design 0001 section 10 "a card that leaves the overlay by
  itself stays findable on the dashboard until the player clears it or it
  is superseded" and a test that walks every overlay card kind (trade,
  eval, price, waystone, and any later kind) and asserts the dashboard
  render shows it after `expires_at`.
- Impact: M. Locks in F1 before 0038 R2 adds zone and act cards.
- Effort: S.
- Risk: L.
- ToS check: display only.
- Depends on: none; 0038 R2 must pass this test when it lands.
- Files likely touched: docs/design/0001-design-system.md section 10,
  tests (a new test next to tests/test_ux_review.py).
- Acceptance test: the new test fails if a card kind is added to
  render_gate without a dashboard twin selector.
- ZERO-CLICK: not player-facing.

R6. Write the glance budget and the notification policy into design 0001.
- Action: section 10 gains "the card's first line starts with the
  verdict word or the buyer, inside the existing 34-character clip; lines
  2 and 3 are optional detail; no text scrolls or marquees"; section 7.1
  gains "AshLight sends no Windows
  toast, sound or taskbar flash during play; news goes to the card slot
  and the dashboard; the one tray balloon on first close is the only OS
  notice". Add a test that the overlay CSS has no animation, marquee or
  scroll and that main and client code call no Notification or
  flashFrame API outside window.js's balloon.
- Impact: M. Keeps later features (price moves, upgrades) from adding
  OS toasts (F8) and keeps the answer in the first word a 2 s glance
  reaches (F3). No new 30-character clip: the 30-character cap is not a
  final NHTSA rule (Sources, NHTSA), and today's 34 is close enough.
- Effort: S.
- Risk: L.
- ToS check: no floor rule touched.
- Depends on: none.
- Files likely touched: docs/design/0001-design-system.md sections 7.1
  and 10, tests (app/test for the card head, tests/ for the grep).
- Acceptance test: a test feeds every card kind the core builds
  (server/al/state.py:777, 782 and the waystone heads at 400-420) and
  asserts the head starts with the answer (a verdict phrase such as "No
  risky mods found" or a fixed prefix such as "Price:"), never with the
  bare item name, and that the answer part fits cardText's 34-character
  clip (app/shared/format.js:120-125); a grep test over app/ finds no
  `new Notification`, `flashFrame` or CSS `animation` / `marquee` outside
  the allowed balloon (app/client/window.js:225-232).
- ZERO-CLICK: not player-facing.

R7. The post-map moment as the third Play context (merge into 0038 R6).
- Action: when the player returns to hideout or town from a map (the
  Maps card already knows the open map), the Play tab's hero area shows a
  one-line map summary (time, deaths, upgrades checked) for the stay in
  hideout, then yields to the town view; no overlay change.
- Impact: M. Matches the pre / in / post density of the large companions
  (F10) with data AshLight already has.
- Effort: S once 0038 R6 exists.
- Risk: L.
- ToS check: Client.txt only (decision 0003).
- Depends on: 0038 R6 (Play follows the context); UTIL-MAPS data.
- Files likely touched: web/app.js (Play hero), server/al/state.py
  snapshot field if the summary is computed in the core.
- Acceptance test: fixture log with map entry, death, return to hideout:
  the snapshot's play context reads "after map" with the summary values.
- ZERO-CLICK: automatic from the log.

R8. Bring the companion back when the game wakes, only on another display.
- Action: when the log goes from idle (decision 0029) to a fresh line and
  the companion is closed to the tray or minimised, show it with
  showInactive (no focus) only if its saved bounds lie wholly on a display
  other than the overlay's display; a tray item turns this off.
- Impact: M. Matches OW-SS (second-screen window opens at game start)
  with the signal AshLight already has.
- Effort: S.
- Risk: M. A window shown without focus can still sit above other
  windows on that display; it never touches the game display by rule.
  Ship after R1 so the saved place is usually the second monitor.
- ToS check: no input, no focus steal, no process or window query of the
  game; the trigger is Client.txt freshness only (decision 0029).
- Depends on: R1. Settled check: decision 0041 (X closes the window to
  the tray) and decision 0029 (idle from log staleness) both stand; R8
  only adds a show on the existing fresh-line edge.
- Files likely touched: app/client/window.js, app/main.js (game_idle edge
  from the snapshot), app/client/tray_menu.js.
- Acceptance test: unit test of the decision function: idle-to-fresh plus
  hidden plus bounds on display 2 while the overlay is on display 1
  returns "showInactive"; same display returns "stay"; the off switch
  returns "stay".
- ZERO-CLICK: automatic; one tray toggle for players who do not want it.

## Cut or merge

- R7 merges into 0038 R6 as its third state; it is not its own package.
- R4 merges with 0054 R2 (sample card) and 0042 R6 (chords in view) into
  one "teach the overlay" package if plan 07 prefers fewer packages.
- R5 and R6 are both design-rule plus test packages; one agent, one
  package.
- No change to the overlay text shadow (F9): it is redundant on a 92
  percent plate but costs nothing and is cited by design 0001; not worth a
  package.
- Game Bar widget sizes (GB-MODES 240 to 600 epx) confirm AshLight's 280
  DIP base width (app/shared/layout.js:35); no change.

## Adopted patterns

Register added 2026-11-21 by plan package DATA-RESEARCH-GAPS (gap 0055 of
docs/plan/02-findings.md). One line per pattern AshLight adopts or keeps:
pattern - where it goes in AshLight - source - access date. Source keys
are those of Sources above; every source there was accessed 2026-11-18.
Where a pattern has a plan package, the package id names it (plan of
record docs/plan/packages.json); no row here claims the package landed.

Adopted (new work)
- A1 A second-screen window opens by itself on the largest display the
  game (here: the overlay) is not on and remembers its place - companion
  first-run placement, R1 (plan package OVL-LINKS-DOWNLOADS; decision 0041
  amendment 2026-11-19) - OW-SS - 2026-11-18.
- A2 Text a player reads at a glance subtends at least 16 arcmin, critical
  text 20 - design 0001 section 3 type floor and the Play tokens, R2
  (plan package PLAY-TD-03-TOKENS) - FHWA - 2026-11-18.
- A3 One notice per thing, never repeated while unanswered - one trade
  card per sender and item, refreshed in place, R3 (plan package
  DATA-PRICE-CARD-TEXT) - AP-NOTIF - 2026-11-18.
- A4 Remind the player of the hotkey where the window is, then stop - a
  muted item-check key hint in the empty card slot that retires itself,
  R4 (plan package OVL-KEY-HINT) - OW-OVL, OW-HK - 2026-11-18.
- A5 A message that leaves by itself is fine only when the same
  information stays findable elsewhere - every self-leaving overlay card
  has a dashboard twin, a design rule plus a test, R5 (plan package
  OVL-GLANCE-RULES) - WCAG-221, AP-NOTIF, NNG-IND - 2026-11-18.
- A6 Glances of 2 s or less and no automatically scrolling text - the card
  head leads with the answer, no scroll or marquee, design 0001 section
  10, R6 (plan package OVL-GLANCE-RULES) - NHTSA - 2026-11-18.
- A7 No noisy OS notices while the user is busy; the foreground app puts
  the item in its own view - no Windows toast, sound or taskbar flash in
  play, design 0001 section 7.1, R6 (plan package OVL-GLANCE-RULES) -
  MS-NOTIF, AP-NOTIF - 2026-11-18.
- A8 Dense content before and after the match, little during it - the
  post-map moment as the third Play context, R7 (merged into note 0038 R6;
  plan package PLAY-TD-11-CONTEXT) - BLITZ - 2026-11-18.
- A9 The second-screen window comes back at game start, without focus and
  never on the game display - companion shown inactive when the log
  wakes, tray switch, R8 (plan package OVL-WAKE-COMPANION; decision 0041
  amendment 2026-11-19) - OW-SS - 2026-11-18.

Kept (already in AshLight, confirmed by this review; no work)
- K1 Short look and long look: a brief card in play, the full record on
  the dashboard - overlay card slot plus the Play tab (F1) - AP-WATCH,
  AP-NOTIF - 2026-11-18.
- K2 Click-through as the default, placed first and then locked - the
  overlay is always click-through and is placed from the dashboard
  (design 0001 section 10, F7b) -
  OP-SETUP, CB-README - 2026-11-18.
- K3 A solid plate behind text over bright video, not a shadow alone -
  the overlay's 92 percent plate (F9) - BBC-W3C, RTSS-FILL - 2026-11-18.
- K4 Context-loaded visibility: a display shows only while its condition
  holds - the Client.txt context of design 0001 section 7.2 and the
  decision 0029 hide on idle (F7) -
  OP-REL, WA-LOAD (UNVERIFIED) - 2026-11-18.
- K5 Settings inferred from data the app already has, not asked -
  character, league and the monitor-height overlay scale (F12) -
  AP-WATCH, BLITZ - 2026-11-18.

## Rejected

- Run on an overlay platform (Overwolf or similar) for in-game windows:
  platform in-game windows are drawn into the game's frames by an
  injected overlay (general knowledge, not re-fetched here), which the
  floor forbids (no DLL injection, no DirectX / DXGI hooks); and the
  platform model is ad-funded second screens: OW-SS pitches second
  screens as ad space and, from 2026-11-01, Overwolf approves only apps
  that use its monetization, which would be revenue on GGG-derived
  features (floor: no ads on GGG-derived features). Also against
  decision 0002.
- Hide the overlay while the game is alt-tabbed (a pattern some overlay
  tools are said to offer; not found in OW-BP or OP-SETUP on re-fetch,
  UNVERIFIED): needs a foreground-window or process query. Decision 0029
  settles on Client.txt staleness, reverses only if GGG or the operator
  permits a process-presence check; neither has happened. The overlay is
  click-through, so the cost of staying visible on the desktop is low.
- Exclusive or interactive overlay mode (OW-OVL): takes keyboard and
  mouse from the game and needs focus; against the non-focusable,
  click-through overlay rule (CLAUDE.md) and design 0001 principle 3.
- Auto-import of builds or settings into the game (BLITZ imports runes
  into the client): writing into game files or sending input is outside
  the floor; decisions 0031 and 0034 keep filters and `.build` files as
  player downloads.
- Parser-style combat meters (damage per second from the game): add-on
  meters run on a game's own add-on API, which PoE2 does not offer, and
  standalone parsers of the ACT class read network traffic or memory
  (general knowledge), which is outside the floor (no packet sniffing,
  no memory reads, no injection). Client.txt carries no combat numbers.
- User-scripted triggers in the WeakAuras style (custom Lua or JS
  conditions): runs code the player pastes inside AshLight, widens the
  local attack surface (notes 0045, 0046) and adds settings to a
  zero-click product; the fixed context table (design 0001 section 7.2)
  covers the need.
- Shift-light style urgency (flashing or animated colour): against WCAG
  2.3.1 and design 0001 section 10 (no flashing, no animation).
- Sound cues for trades or deaths (AP-NOTIF allows a short sound): design
  0001 principle 3 is "no sound"; this is a design principle, not a
  settled decision, so the operator could reopen it, but nothing in this
  review is evidence for it.
- A screen or clipboard watcher to show cards without a press (the
  "anticipate needs" pattern of AP-WATCH applied to items): the floor
  allows one read per manual press only (decision 0003).
- Notification Center or Windows toast history as the long look
  (MS-NOTIF): the dashboard is the long look; a toast in play breaks
  R6 and design 0001 section 7.1.

## Open questions

1. The reference setup for R2 (24 inch 1080p, 80 cm dashboard, 60 cm
   overlay) is an assumption. The operator's real monitor size,
   resolution and distance would replace it; this is a measurement, not a
   decision, and belongs in the batched operator ask (plan 09) as an
   optional item. Without it R2 ships with the stated default.
2. Streamer privacy (F14): should the trade card offer a name-hiding
   switch? No evidence of demand; leave unless a player asks. Not an
   adjudicator item.
3. R8 shows a window without the player asking. It stays inside the floor
   and the no-focus rule, but it is a behaviour change some players may
   dislike; plan 07 should ship it default ON with the tray toggle unless
   the operator rules otherwise (adjudicator if contested).

## Verification

Independent verifier, 2026-11-18 (local clock). All re-fetches on that date.

Checked
- Code: 24 path:line citations opened (app/client/link.js,
  app/client/window.js, app/shared/format.js, app/shared/layout.js,
  app/shared/render_gate.js, app/overlay/overlay.css, app/overlay/overlay.js,
  app/main.js, web/app.css, server/al/state.py, design 0001 sections 3
  and 10). Card lifetimes, trade cap, whisper append, close-one-card,
  companion centring, tray balloon, layout floors and base width all hold.
- Web: 18 sources re-fetched (OW-SS, OW-OVL, OW-HK, OW-BP, OW-FTUE,
  GB-MODES, AP-NOTIF, WEAR-TILE, MS-NOTIF, WCAG-221, NNG-IND, NHTSA PDF
  text, FHWA, BBC-W3C, SIM-TAB, DIM-GH, BLITZ SourceForge, OP-SETUP) plus
  3 new (CB-README, OP-REL, RTSS-FILL). Every arcmin figure re-computed.
- ToS floor: R1 to R8 read against every floor rule; none reads memory,
  injects, hooks graphics, sends input, watches the clipboard or screen,
  calls a trade or undocumented endpoint, or earns revenue. R4's hint
  names a key the player presses; R8 uses Client.txt freshness only.
- Settled decisions: 0003, 0019, 0029, 0031, 0034, 0041 checked against
  R1 to R8 and the Rejected list; no reversal proposed.

Corrected
- NHTSA: the 30-character reading cap is from the 2012 proposal (via
  JAMA) and is not in the final 2013 guidelines; F3, R6 and the Summary
  reworded, R6's new 30-character clip dropped.
- Play type sizes: sub lines are 14.4 px on the two-column Play tab
  (web/app.css:545), not 16 px body; labels drop to 13 px in a short
  window (web/app.css:567). F4, Summary and Current state fixed.
- OW-BP does not say to hide windows while the game is alt-tabbed; F7
  and Rejected fixed. OW-HK does not say the user is told about a
  conflict; OW-OVL's points are advice, not "must".
- BBC-W3C on empty boxes: the BBC argues an empty box should be optional
  because it obscures video, not a ban; reworded.
- Empty-plate citation moved from overlay.css:65-69 (status and timer
  spans) to overlay.js:27, 30 (card plates set `hidden`).
- R1 now excludes the overlay's display instead of the primary, a closer
  stand-in for "the monitor the game is on" with no window query.
- Blitz claims narrowed to what its SourceForge listing states.
- Added F7b (click-through as the parser-class default), F15 (toast
  timing) and the RTSS fill box under F9.

UNVERIFIED (left labelled)
- WeakAuras AND-ed load conditions (community text only; the wiki page
  is empty); a "hide while not the active window" option in overlay
  tools; Blitz in-match overlay and premium tier; sim-racing peripheral
  shift lights (SIM-PERIPH); that platform in-game overlays inject into
  the game (general knowledge; the rejection also stands on the
  monetization rule and decision 0002).
- The R2 reference setup (24 inch 1080p, 80 cm and 60 cm) is an
  assumption (Open question 1).

Brief coverage
- Covered: overlay platforms, OS notification and widget guidance, MOBA
  companion density, web loadout manager, aura add-ons, parser overlays,
  sim-racing dashboards, an OSD tool over bright video, watch and
  automotive glance rules.
- Partly covered: action-RPG companions beyond PoE (the pre / in / post
  pattern is taken from the MOBA class; PoE tools are note 0054).
  Aviation HUD research is not covered: the FHWA and NHTSA numbers give
  the measurable rules AshLight needs, and nothing in R1 to R8 depends on
  aviation work.
- Length: about 650 lines, over the 250 to 500 target; kept because the
  corrections had to stay next to the claims they fix.
