# 0055 - Competitive review: other games' companions and overlay platforms (patterns)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B16
competitive review: other games and overlay platforms. Design patterns only,
taken from overlay platforms (Overwolf, Xbox Game Bar), action-RPG and MOBA
companions, web loadout managers, combat-meter and aura add-ons, parser
overlays, sim-racing dashboards, OS notification guidance, subtitle
legibility over video and glance rules from watches and cars. PoE tools are
note 0054; features note 0038; utilities and settings note 0039; usability
note 0042. No code, asset or text of any tool is copied.
Status: draft

## Sources (all accessed 2026-11-18, local time)

Overlay platforms
- OW-SS: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/second-screen
  (second-screen windows open by themselves at game start, go to the
  largest monitor the game is not on, remember their place; at-a-glance
  content, no interaction expected in play).
- OW-OVL: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/in-game-overlays
  (overlays must not cover critical game UI; avoid semi-transparent widgets
  that reduce clarity; put hotkey reminders in widgets; window kinds:
  lobby, loading, in-game, widget, second screen).
- OW-HK: https://dev.overwolf.com/ow-native/guides/product-guidelines/app-screen-behavior/hot-key-and-settings
  (rebind inside the app; a key that conflicts with another app is left
  unassigned and the user is told; remind users of the key when a window
  does not open by itself; offer passthrough).
- OW-FTUE: https://dev.overwolf.com/ow-native/guides/general-product/first-time-user-experience
  (tutorial as short as possible; the app's value fits one sentence; let
  users do the action rather than read about it; respect the match).
- OW-BP: https://dev.overwolf.com/ow-native/guides/general-product/best-practices
  (best-practice index: windows need close / minimize, no app window while
  the game is alt-tabbed; seen as a search result summary only, the page
  body was not opened - details marked UNVERIFIED where used).
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
  2.0 s correlate with crash risk; no automatically scrolling text; no
  more than 30 characters of text (punctuation not counted) read per task;
  24 test participants suffice for the glance protocol).
- FHWA: In-Vehicle Display Icons and Other Information Elements, Vol. I,
  FHWA-RD-03-065, 2004-09,
  https://www.fhwa.dot.gov/publications/research/safety/03065/03.cfm
  (text at least 16 arcmin of visual angle, up to 24; critical symbols at
  least 20 arcmin; legibility drops below about 18).

Text over video
- BBC-W3C: BBC review comments to the W3C, 2014-12-04,
  https://lists.w3.org/Archives/Public/public-pfwg-comments/2014OctDec/0003.html
  (outlines and drop shadows are no general substitute for a solid
  background: white text with shadow fails over bright footage such as
  snow; shadows add visual busyness; pad the box past the text; do not
  keep a box on screen with no text in it).

Companions, add-ons, parsers, dashboards (search-result summaries and
third-party pages; product claims marked UNVERIFIED where used)
- BLITZ: https://www.wombocombo.gg/blog/game-analytics/blitz-gg-overlay-review
  and https://sourceforge.net/app/blitz/ (a MOBA companion: champion
  select suggestions, in-game overlay, post-game review; auto-import of
  runes and builds into the game client; premium tier).
- MOBA-OVL: https://mobalytics.gg/lol/glp/app-download (same class;
  page not opened, the guide page returned 403).
- DIM-GH: https://github.com/DestinyItemManager/DIM (web loadout manager,
  MIT) and DIM-LO: https://maxroll.gg/destiny-2/resources/loadout-optimizer-guide-destiny-2
  (the player ticks stat priorities, best loadouts sort to the top).
- WA-LOAD: WeakAuras load conditions as summarised in search results from
  the WeakAuras wiki mirror and player forums (a display loads only while
  every ticked condition holds, e.g. in combat; conditions are ANDed).
  UNVERIFIED against the live wiki.
- OP-SETUP: https://overlayplugin.github.io/docs/setup (place the overlay,
  then tick Lock overlay); click-through advice in community guides
  conflicts (search summary), UNVERIFIED.
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
  largest monitor the game is not on (OW-SS). Infer it: largest
  non-primary display, no question asked.
- Distance legibility (R2): read at 80 cm on a 24 inch 1080p second
  monitor, the Play tab's labels (13.6 px) and body text (16 px) subtend
  11.3 and 13.3 arcmin, under the 16 arcmin floor drivers' displays use
  (FHWA). Glance numbers (26.7 to 36.6 arcmin) are fine. Hand this to the
  typography note 0041 and plan section 03 as a measured rule.
- Same-thing-twice (R3): a buyer who re-sends the same whisper gets a
  second trade card (server/al/state.py:1556-1560). Apple's rule is one
  notice per thing; refresh the existing card instead.
- Teach the hotkey where it is used (R4): Overwolf asks for hotkey
  reminders in the overlay itself (OW-OVL, OW-HK). Use the empty card
  slot for a self-retiring "Alt+Shift+E: check a copied item" line.
- Formalise two rules as tests (R5, R6): every overlay item that leaves by
  itself has a dashboard twin that stays (WCAG-221, AP-NOTIF short look);
  the card's first line carries the verdict inside 30 characters and no
  overlay text ever scrolls (NHTSA).
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
  docs/design/0001-design-system.md:216-243, 604-617); plates hide when
  their text is empty (app/overlay/overlay.css:65-69).
- Type sizes: dashboard caption 13 px, label 13.6 px, body 16 px, zone
  timer 20.8 px on the two-column Play tab, glance numbers clamp 32 to
  44 px; overlay secondary 13 px, zone 16 px, HUD numbers 15 px
  (docs/design/0001-design-system.md:52-92).

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
12 s total per task, no automatically scrolling text, at most 30
characters read per task (NHTSA). Design 0001 asks for "one fixation, <= 5
words" per HUD line (docs/design/0001-design-system.md:627-629) but the
card allows 3 x 34 characters (app/shared/format.js:121). The verdict is
already the first line, so the card meets the spirit; the number is not
written down or tested. No overlay text scrolls today (nowrap plus
ellipsis, app/overlay/overlay.css:58).

F4. The dashboard is read at second-screen distance, and its small text is
below the drivers'-display floor. FHWA puts text at 16 arcmin minimum and
critical symbols at 20 (FHWA). With Segoe UI cap height 0.7002 em
(measured) on a 24 inch 1080p panel (0.2768 mm per pixel at 100 percent)
the visual angle is:
- at 80 cm: caption 13 px 10.8, label 13.6 px 11.3, body 16 px 13.3, zone
  timer 20.8 px 17.3, glance numbers 32 to 44 px 26.7 to 36.6 arcmin;
- at 60 cm: caption 14.4, label 15.1, body 17.8, timer 23.1 arcmin.
To reach 16 arcmin at 80 cm the font must be at least 19.2 px; 20 arcmin
needs 24 px. The glance numbers pass; the labels that name them (LEVEL,
DEATHS) and the Play sub lines do not. The 80 cm distance and the panel
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
parser overlays and platforms. WeakAuras displays load only while their
conditions hold (WA-LOAD, UNVERIFIED wording); parser overlays offer an
auto-hide when the game is not the active window (OP-SETUP search
summary); Overwolf shows no app window while the game is alt-tabbed (OW-BP,
UNVERIFIED). AshLight does the first part through Client.txt context
(design 0001 section 7.2, decision 0029 hide on idle). The second part
(hide while alt-tabbed) needs a foreground-window query, which decision
0029 settles against (see Rejected).

F8. Notification policy is already right and should be written as a rule.
Apple: an app in the foreground inserts new items into its view instead
of notifying; Windows: suppress into Notification Center, respect Focus
Sessions (AP-NOTIF, MS-NOTIF). AshLight sends one silent tray balloon in
its life (app/client/window.js:225-232) and otherwise puts news into the
dashboard and the card slot. No written rule stops a later feature from
adding a Windows toast for a price move or an upgrade.

F9. Text over bright scenes: AshLight's plate matches the subtitle
guidance. BBC: a shadow or outline is no substitute for a solid box over
bright footage; pad the box; do not leave an empty box on screen; shadows
add busyness (BBC-W3C). AshLight uses a 92 percent plate with 6 to 10 px
padding and hides empty plates (app/overlay/overlay.css:47, 65-69, 78,
101). The 1 px text shadow is redundant on a 92 percent plate; it is not
harmful at 1 px and design 0001 cites a games source for it, so no change
is worth a package (see Cut or merge).

F10. Density by phase. MOBA companions put the dense content before the
match (picks, build), a thin overlay during it and a review after it
(BLITZ, UNVERIFIED feature list). The PoE2 analogue is hideout / town
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
data"; BLITZ detects the champion from the client). AshLight infers
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

## Recommendations

R1. Put the companion window on the second monitor by itself on first run.
- Action: when there is no usable saved window state and 2 or more
  displays exist, centre the companion at its default size on the
  largest work area that is not the primary display (ties: the first in
  Electron's order); one display keeps today's centred placement.
- Impact: M. Every two-monitor player saves a find-and-drag in the first
  minute; AshLight's main surface is the second screen.
- Effort: S.
- Risk: L. A player whose game runs on a non-primary display gets the
  companion on the primary one only if that one is largest; the saved
  place wins from the second start on.
- ToS check: game process and input rules untouched; uses Electron's
  display list only, no window or process enumeration of the game
  (decision 0029 stays intact).
- Depends on: none.
- Files likely touched: app/client/link.js (windowBounds takes the display
  list with a primary flag), app/client/window.js:147-150, app/test
  (a link.js unit test).
- Acceptance test: unit test with work areas [primary 1920x1080, second
  2560x1440] and no saved state returns bounds inside the second area;
  with one area returns today's centred bounds; saved visible bounds still
  win.
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
  web/app.css (Play tile label and sub line sizes), app/overlay/overlay.css
  (.status), tests/test_ux_review.py (a size floor check).
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
- Depends on: the bound chord is already reported by the client (0039 R3
  makes it rebindable; the hint reads whatever is bound).
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
- Action: section 10 gains "the card's first line carries the verdict or
  the buyer within 30 characters; lines 2 and 3 are optional detail; no
  text scrolls or marquees"; section 7.1 gains "AshLight sends no Windows
  toast, sound or taskbar flash during play; news goes to the card slot
  and the dashboard; the one tray balloon on first close is the only OS
  notice". Add a test that the overlay CSS has no animation, marquee or
  scroll and that main and client code call no Notification or
  flashFrame API outside window.js's balloon.
- Impact: M. Keeps later features (price moves, upgrades) from adding
  OS toasts (F8) and keeps the card inside the NHTSA 30-character read
  (F3).
- Effort: S.
- Risk: L.
- ToS check: no floor rule touched.
- Depends on: none.
- Files likely touched: docs/design/0001-design-system.md sections 7.1
  and 10, app/shared/format.js (line-1 30-character clip for the head
  only), tests.
- Acceptance test: tests assert cardText head length <= 30 with the
  verdict first; a grep test over app/ finds no `new Notification`,
  `flashFrame` or CSS `animation`/`marquee` outside the allowed balloon.
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
- Depends on: R1.
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

## Rejected

- Run on an overlay platform (Overwolf or similar) for in-game windows:
  platform overlays draw into the game's frames through a graphics hook,
  which the floor forbids (no DirectX / DXGI hooks), and the platform
  model is ad-funded second screens (OW-SS mentions ad placement), which
  would be revenue on GGG-derived features. Also against decision 0002.
- Hide the overlay while the game is alt-tabbed (OW-BP, OP-SETUP
  auto-hide): needs a foreground-window or process query. Decision 0029
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
- Parser-style combat meters (damage per second from the game): such
  parsers read network traffic or memory; outside the floor (no packet
  sniffing, no memory reads). Client.txt carries no combat numbers.
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
