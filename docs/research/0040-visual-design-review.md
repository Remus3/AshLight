# 0040 - Visual design review (dashboard, client window, overlay)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B4
visual design. Scope: layout grid, spacing, density, hierarchy, colour
tokens, elevation, borders, brand use, component consistency, state design
and dark-room comfort of `web/`, `app/client`, `app/overlay`, `app/shared`
and `app/brand`, measured against docs/design/0001-design-system.md.
Typography is note 0041 and accessibility is note 0044: cross-references
only. No product code was changed.
Status: draft

## Sources (all accessed 2026-11-18)

Web:
- ELTH Electron nativeTheme API (themeSource values, what it changes):
  https://www.electronjs.org/docs/latest/api/native-theme
- NNG Nielsen Norman Group, dark mode against light mode (article dated
  2020-02-02): https://www.nngroup.com/articles/dark-mode/
- WEBDEV web.dev, prefers-color-scheme (dark theme practice, manual
  switch): https://web.dev/articles/prefers-color-scheme
- NTC W3C, Understanding WCAG 2.2 SC 1.4.11 Non-text Contrast:
  https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- MSCOL Microsoft Learn, Color in Windows (page metadata 2026-10-13):
  https://learn.microsoft.com/en-us/windows/apps/design/style/color
- Not used: the Material dark theme page returned no text to a plain
  fetch (script-rendered), so nothing here rests on it.

Repo and pack:
- DS docs/design/0001-design-system.md (sections cited as DS n).
- CSS web/app.css, app/overlay/overlay.css, app/client/starting.css;
  kit tokens ops/fleet_kit/tokens.css (never edited here, FLEET item 11).
- PACK the ultraplan evidence pack, cited by name relative to the pack
  directory (README.txt, run/<state>/..., run-light/<state>/...).
- M1 own count: a regex inventory of the three CSS files (token uses,
  spacing values, radii, border widths, colour literals).
- M2 own count: pixel statistics of 24 PACK dashboard captures (mean
  relative luminance, share of pixels above 0.18, share of saturated
  pixels per hue, most common tones).
- M3 own count: the brightest glyph pixels against the plate colour in the
  PACK overlay composites, 4 backdrops, states c and c2.
- M4 own run: a hidden, unfocusable Electron window of the client's default
  size read 1264 x 821 px of content for the 1280 x 860 window on this
  machine (scale factor 1); then the PACK script for states c, d, f on
  Play at 1264 x 821 (port 8962, hidden, below-normal priority, the
  pack's own synthetic log, stopped after). Not part of the PACK.
- Sibling notes: 0038 (features), 0039 (utilities), 0042 (usability).

## Summary

1. The base is sound and stays: one colour source, zero colour literals in
   web/app.css and in every dashboard and overlay script, 13 text /
   background pairs with the lowest at 5.31:1, no shadow, no motion, and a
   dark page whose mean relative luminance is 0.016 to 0.037 (M2).
2. The largest comfort defect is that nothing makes the surface dark. The
   dashboard and the client follow the Windows app mode; in light mode the
   same Play tab has a mean luminance of 0.90, 25 to 56 times the dark one.
3. Play does not read as one surface. It has 5 container looks, the
   answer the player just asked for (the verdict) is 16 px in a pill while
   a zone name is 28 px, the zone tile takes 48 percent of the left
   column with prose, and the trade card starts at the fold.
4. Colour is spent on the normal state: 2 pills are coloured all the time,
   6 buttons are filled accent blocks (1 deserves it), and amber carries
   10 meanings through 15 references.
5. Stale looks live. In the idle state the level, deaths and timers keep
   the full text colour; only a pill and a 13.6 px tag change.
6. Form controls shout: every input edge is the 7.18:1 muted text colour,
   so the Items tab is a grid of about 40 bright boxes.
7. The system drifts: 72 percent of spacing values sit on the documented
   grid, 24 and 32 px are never used, 5 radii for 3 documented, 5 badge
   looks, 10 kinds of list row with 7 paddings.
8. The client window has a third palette (7 literals) and its compact
   layout rule misses the default window by 1 px.
9. The overlay holds. Sampled pixels give 4.88:1 for the 13 px muted line
   over white, so PACK measurement 15 (3.81) is a model error, not a
   defect; no overlay token changes.
10. Eight ranked recommendations follow; the first four are worth doing
    before any feature work on Play.

## Current state

### Colour tokens in the dashboard (web/app.css; values light / dark)

Uses are `var()` references counted by M1.

- `--fk-surface` #ffffff / #0f1216, 8 uses: page (app.css:10), text on the
  filled button (84), input fills (141, 208, 222, 264), whisper row inset
  (181), tab hover (493).
- `--fk-surface-2` #f3f4f6 / #181c22, 2 uses: header bar (32), card (66).
- `--fk-text` #1a1d21 / #e4e8ec, 18 uses: body (11), every focus ring
  (91, 148, 230, 254, 328, 504, 516), tab text (483), fold summaries
  (443, 473).
- `--fk-text-muted` #555d66 / #99a1aa, 25 uses: secondary text, and the
  control boundary of DS 5.1 (142, 209, 223, 265, 279, 327, 498).
- `--fk-border` #d3d8de / #323840, 19 uses: card, tile and pill outlines,
  every row divider.
- `--fk-accent` #1559a8 / #5a9ef0, 12 uses: filled button (85-86), links
  (95, 252), consent outline (77), whisper edge and tag (181-182), Last
  session and tip edges (191, 452), range and checkbox tint (227, 326),
  selected tab bar (492).
- `--fk-status-warn` #946200 / #d19a2a, 15 uses, 10 meanings: blocked pill
  (50), trade request in three places (183-184, 187, 200), risky verdict
  (284), build health (374), graphics warning (390), under-level (434),
  slower split (436), blocked check (471), language note (474), build
  alert (511).
- `--fk-status-ok` #1d7a3a / #46b85c, 5 uses: live pill (48), upgrade
  verdict (282), passed check (469).
- `--fk-status-bad` #c4262f / #f0605a, 4 uses: failed pill (51), consent
  error (79), death tag (185).
- `--fk-status-running` #1765c4 / #5ea4f5, 2 uses (47); 1.07:1 from the
  accent, so the two blues are one colour to the eye.
- `--fk-status-idle` #5b636c / #8a929b, 1 use (49).
- In the kit, unused here: `--fk-status-unknown`, `--fk-status-halted`,
  `--fk-chart-1` to `-9`.
- No `--al-*` token exists in web/app.css. The `--al-fs-*` names in DS 3
  are marked proposed and are not in the CSS (note 0041).

### Colour tokens in the overlay (app/overlay/overlay.css:6-21)

`--fk-text` #e4e8ec (5 uses), `--fk-text-muted` #99a1aa (3), `--fk-border`
#323840 (3), `--fk-status-warn` #d19a2a (3), `--fk-status-ok` #46b85c (1),
`--al-plate` rgba(15, 18, 22, 0.92) (3), `--al-shadow` #000 (3),
`--al-edge` #99a1aa (1). Declared and used by no rule: `--fk-surface`
(overlay.css:7) and `--fk-status-bad` (overlay.css:11). System colours
`Canvas` and `Highlight` appear only under forced colours (151-157). The
opacity is page CSS on `html` (overlay.css:28, app/shared/layout.js:139-141),
never a window opacity.

### Colour outside tokens

- app/client/starting.css:3-5: six literals, none a kit value: `--bg`
  #f6f6f4 / #16181d, `--fg` #1d1f23 / #e8e8e6, `--muted` #4f5560 / #a9adb5.
- app/client/window.js:158: window `backgroundColor` "#16181d", 1.06:1
  from the dashboard surface #0f1216 it is replaced by.
- app/main.js:221: "#00000000", the transparent overlay window (needed).
- web/favicon.svg and assets/brand: the brand tile (#181c22, hairline
  #323840, flame #eb6834, core #fcd27a, ash #99a1aa), recorded in
  docs/design/0005-brand-mark.md. Allowed.
- None in web/*.js, web/index.html, app/overlay/*.js, app/shared/*.js; no
  inline style anywhere. DS 11 item C3 holds for dashboard and overlay and
  fails only in the client start page.

### Layout, spacing, shape (M1)

- Shell at 900 x 560 and up (app.css:525-561): header 50 px, footer 39 px,
  the rest is `main`; at 1280 x 760 that leaves 655 px (PACK
  run/c/dash-play-1280x760.png, json: columns 618 x 654 px).
- Play is two equal columns (app.css:551); `main` caps at 1600 px
  (app.css:530), so at 1920 x 950 a column is about 774 px and a prose
  line runs to about 105 characters (PACK run/c/dash-play-1920x950.png).
- Spacing: 195 px values in web/app.css; 140 (72 percent) are on the DS 4
  grid (0, 4, 8, 12, 16). Off the grid: 6 px 19 times, 2 px 17, 10 px 11,
  20 px 5, 14 px once. The grid's 24 and 32 are used 0 times.
- Three density tiers by media query: card padding 16 / 12 / 12, gaps
  16 / 12 / 8, tile padding 12-16 / 8-12 / 4-10 (app.css:63-68, 106-111,
  536-546, 565-570), plus two narrow tiers (413, 446).
- Radius: 8 px (card, tile), 6 px (controls, fieldset), 999 px (pill,
  verdict, tab mark), 4 px twice (`.tag` app.css:156, `.search-text` 368),
  6 6 0 0 (tab). DS 4 names 8, 6 and 999 only.
- Border widths: 1 px 26 times, 3 px 8 (focus rings, tab bar), 4 px 7
  (left edges). The overlay edge is 3 px (overlay.css:80, 103).
- Elevation: no box-shadow in any file. Depth is two fills 1.10:1 apart
  plus a 1 px line at 1.59:1 (on surface) or 1.45:1 (on surface-2).
- Overlay: 2 of 11 spacing values on the grid (5, 6, 10 px dominate); a
  deliberate compact scale for a 280 x 176 window, not a defect.

### Components

- Containers, 6 looks: `.card` fill plus outline (app.css:63-68); `.stat`
  outline and no fill (106-111); card with a 4 px left edge (191, 452,
  474, 511); `.trades` with a full amber outline (187); consent with an
  accent outline (77); fieldset (336).
- Badges, 5 looks: `.pill` (36-51), `.verdict` (276-284), `.tab-mark`
  (495-502), `.tag` (151-159), the uppercase `.kind` word (171-178).
- List rows, 10 kinds, 7 paddings: event 6px 8px (165), trade 8px and 4px 8px in
  the shell (198, 546), stat lines 4px 0 (295), price 4px 0 (313), gear
  6px 0 (347), search 8px 0 (361), health 4px 0 (373), graphics 6px 0
  (394), checks 6px 0 (464), table cells 6px 8px 6px 0 (237).
- Buttons: the bare `button` is the filled accent style (82-90);
  `.secondary` (206-211), `.link` (92-99), `.tab` (482-494). In
  web/index.html 6 buttons are bare (lines 79, 89, 521, 524, 534, 572)
  and 6 are secondary; 2 more are made in script (web/app.js:172,
  web/search.js:86).
- Tables: one `.acts-table` style for all 6 tables (236-250). Consistent.
- Toasts: none, by rule (DS 11 item N2). 12 status regions.

### States as drawn

- First run (PACK run/a/dash-play-1280x760.png): consent card with an
  accent outline; the tiles show "-" and "--:--" at glance size in the
  full text colour.
- Empty item check (same capture): two muted paragraphs, each starting
  "Nothing checked yet."
- Loading: words only ("Searching prices...", a pending pill). No
  skeleton, which fits the no-motion rule.
- Idle, "game may be closed" (PACK run/d/dash-play-1280x760.png): amber
  pill "quiet for 20 min - game closed or AFK?" and a tag "frozen - log
  quiet" (web/index.html:98, web/app.js:1022). Values unchanged.
- Error (PACK run/e/dash-play-1280x760.png, run/e/dash-settings-1280x760.png):
  amber pill, the word "fix" on the Settings tab, a neutral "Not checked"
  verdict, a Checks row with glyph, word and a bold fix line.
- Feed down: a red pill (web/status.js:37) and stopped timers
  (web/app.js:89). Not in the PACK; UNVERIFIED by eye.

### Luminance and colour share (M2, 1280 x 760 unless said)

- Dark, mean relative luminance: first run 0.027, after consent 0.016,
  zone guide 0.027, worst-case Play 0.035, idle 0.025, Checks error 0.019,
  Run 0.034, Build 0.026, Items 0.034, Settings 0.025.
- Light (PACK run-light): Play 0.898, Run 0.880, Items 0.882.
- Pixels brighter than 0.18 (text and edges): 1.8 to 5.1 percent in dark.
- Saturated pixels in dark: blue 0.65 to 2.15 percent, amber 0.41 to 1.21,
  red 0.07 to 0.39, green 0.04 to 0.14. Blue is the largest hue in every
  capture; the one filled button is 0.9 to 1.0 percent of the screen.
- Text pairs (PACK json, 45 captures at 1280 x 760): 13 distinct, none
  under 5.31:1; body text is 15.25:1 on the page and 13.89:1 on a card.

## Findings

- F1 Nothing forces dark. web/app.css:6 and the kit sheet follow
  `prefers-color-scheme`; no file sets `data-theme` and the client never
  sets `nativeTheme.themeSource` (no match in web/, app/main.js or app/client). The PACK ran
  the full matrix in dark only, which hides this. In light mode the
  second screen is a 0.90 panel beside a dark game (M2), the case MSCOL
  calls painful in a dark room. UNVERIFIED: that light is the Windows
  out-of-box app mode; if so this is what a new player gets. Why it
  matters: it is the one visual defect that can make the player close the
  dashboard at night.
- F2 Play has no dominant element and its first screen is prose. Read off
  PACK run/c/dash-play-1280x760.png: the zone tile is 316 of 655 px (48
  percent), 8 of its 11 lines are 16 px guide text; the three tiles take
  129 px, mostly empty under their numbers; the trade card, the only thing
  that needs the player within minutes, shows 1.5 rows; the build alert
  is below the fold. In the client's default window the left column still
  overflows 356 px (worst case), 207 px (typical) and 521 px (idle) (M4).
  The verdict "Upgrade" is 16 px bold in a pill (app.css:276-281) under a
  16 px card title, while "Clearfell" is 28 px: the answer to the
  player's own key press is the same size as its explanation.
- F3 Two brightness steps for everything. Guide prose, item sentences,
  names and glance numbers share #e4e8ec; the only other step is muted,
  used 25 times. Hierarchy rests on size alone, so 397 words (PACK
  measurement 6) compete at one brightness. Note 0042 F17 hands its
  density targets to this note; see R2.
- F4 The normal state is coloured. "reading Client.txt" is always blue
  and "live" always green (app.css:47-48); with the selected tab bar and
  links, blue is on screen in every state. DS 2 principle 3 asks for
  quiet by default and MSCOL for accent used sparingly. Colour should
  mean "something changed".
- F5 Five ordinary buttons are filled accent blocks: "Hide this notice",
  "Restart overlay", "Show new-character tips again", "Copy report",
  "Download settings" (web/index.html:89, 521, 524, 534, 572). The fill
  #5a9ef0 is 56 times the luminance of the page and the brightest large
  shape on the Settings tab (PACK run/e/dash-settings-1280x760.png). Only
  the consent button (index.html:79) earns it.
- F6 Amber is diluted and doubled. DS 6 says warn means "needs you soon".
  It also marks a slower split and a graphics list, and a trade request
  gets it twice at once: the whole card outline (app.css:187) and every
  row edge (200).
- F7 Idle and stale look live. In PACK run/d/dash-play-1280x760.png the
  level, deaths, session and the frozen timer are full white; the idle
  word is a 13.6 px tag. A glance from the game cannot tell frozen from
  running. The first-run dashes have the same problem in reverse: the
  largest marks on the screen are placeholders.
- F8 Control edges are louder than content. Every input, select, secondary
  button and the checkbox use #99a1aa at 7.18:1 (DS 5.1) where NTC asks
  for 3:1 and sets no upper limit. The Items tab has about 40 number
  inputs: #99a1aa is 0.9 percent of that capture against 0.2 to 0.4
  elsewhere (M2; PACK run/f/dash-items-1280x760.png). The unchecked
  checkbox there draws as a grey filled square, which reads as disabled.
- F9 The system drifts from DS 4: 72 percent on the grid, 24 and 32
  unused, a 4 px radius twice, 5 badge looks, 7 row paddings, 3 px
  against 4 px for the same edge cue on overlay and dashboard. No test
  holds spacing or radius, so each new card adds a variant.
- F10 Event rows shift and float. A whisper or trade row gets a 4 px edge
  and a darker fill (app.css:181), which moves its time 4 px right of the
  rows around it, and the 13 px tag is top-aligned beside 16 px text
  because the row has no baseline alignment (app.css:162-168; PACK
  run/f/dash-run-1280x760.png, Recent card).
- F11 The client has its own palette. Start page and window background use
  #16181d, #e8e8e6, #a9adb5 (starting.css:3-5, window.js:158), not the
  kit values, so the window steps from one dark to another when the
  dashboard loads; in light mode it goes dark window, light start page,
  light dashboard.
- F12 The compact rule misses its target. app.css:563-565 tightens tiles
  for "the ~1280x800 desktop client" at `max-height: 820px`; the default
  window (app/client/link.js:15) has 821 px of content here (M4), so the
  rule never applies in the window it was written for. UNVERIFIED on
  other Windows versions, whose frame sizes differ.
- F13 Wide windows stretch prose. With the 1600 px cap, lines reach about
  105 characters at 1920 px; the tiles grow into empty boxes (PACK
  run/c/dash-play-1920x950.png).
- F14 The brand is absent from the surface. The header is the word
  "AshLight" at 16 px (web/index.html:36); the mark exists only as the
  favicon and tray icon. Low cost, low harm, noted for completeness.
- F15 The overlay is within its own rules. M3 over white: text 9.46:1,
  amber status word 4.98:1, 13 px muted line 4.88:1 (glyph #a3aab2 on
  plate #373a3d); over the warm backdrop 9.86 / 5.18 / 5.06; over black
  12.51 / 6.22 / 6.03. These match DS 5.2 (9.34 / 4.96 / 4.80 with
  8-bit rounding). PACK README measurement 15 reports 3.81 and 4.04
  because it composited the text over the plate; the page fades as one
  group over the scene, so text gains light from a bright scene. The
  margin over 4.5:1 is thin (0.38) and rests on the 0.9 floor, which
  app/shared/layout.js:31 enforces. Notes 0041 and 0044 should not plan
  work on that reading. Three identical plate blocks (overlay.css:45-56,
  76-88, 99-111) are the only clean-up.

## Recommendations

### Token and component changes at a glance

AshLight cannot edit `--fk-*` (FLEET item 11), so every change is an
`--al-*` token declared once in web/app.css, with light and dark values.

- `data-theme` on `<html>`: old absent (follows the system); new "dark" by
  default. All 13 dark pairs stay as measured (lowest 5.31:1). Where: the
  whole dashboard and the client window. (R1)
- `--al-text-body`: new. Dark #c5ccd3, 10.55:1 on a card and 11.58:1 on
  the page; light #30353c, 11.22:1 and 12.35:1. Old: `--fk-text`
  (13.89:1 / 15.25:1 dark). Where: paragraphs and list text inside
  cards; `--fk-text` stays on glance values, names, headings, verdict
  words. (R2)
- `--al-text-stale`: new, equals `--fk-text-muted`, 7.18:1 on the page in
  dark, 6.68:1 light. Old: `--fk-text` on glance values in every state.
  Where: `.stat .value`, the zone timer and placeholders while idle,
  offline or empty. (R3)
- `--al-control-edge`: new. Dark #6b7480, 3.61:1 on a card and 3.97:1 on
  the page; light #7b838d, 3.49:1 and 3.84:1. Old: `--fk-text-muted`
  (6.54:1 / 7.18:1 dark). Where: app.css:142, 209, 223, 265, 327; back to
  `--fk-text` under `prefers-contrast: more`. (R5)
- Normal-state pill: old colour and outline `--fk-status-running` /
  `--fk-status-ok` (6.60:1 / 6.74:1); new text `--fk-text-muted` (6.54:1
  on the header) with a `--fk-border` outline. Where: app.css:47-48. (R4)
- Bare `button`: old filled accent (text 6.78:1 on the fill); new the
  quiet style now called `.secondary`; the fill moves to `.primary`,
  used once. Where: app.css:82-90, 206-211. (R4)
- `--al-space-0` to `-4` = 2, 4, 8, 12, 16 px and `--al-radius-card` 8,
  `--al-radius-control` 6, `--al-radius-pill` 999. Old: 11 raw values and
  5 radii. Where: all of web/app.css. (R7)
- Client start page and window: old #16181d / #e8e8e6 / #a9adb5; new
  #0f1216 / #e4e8ec / #99a1aa (15.25:1 and 7.18:1). (R6)

### R1. Dark unless the player chooses otherwise

- Action: ship `<html data-theme="dark">` in web/index.html, set
  `nativeTheme.themeSource = "dark"` in the client before the first
  window, and add one Settings choice "Theme: Dark / Follow Windows /
  Light" that swaps both (the kit sheet already honours `data-theme`;
  ELTH: themeSource drives `prefers-color-scheme`).
- Impact: H. Removes a 25 to 56 times brightness jump for every player
  whose Windows app mode is light. NNG reports that light polarity reads
  faster, in a night glance test too, and that users should be able to
  switch: hence a choice, and hence R2 keeps glance sizes large.
- Effort: S for the default, M with the setting.
- Risk: a player who wants light must find the setting; the start page
  cannot read it before the core is up (R6 makes that page dark).
- ToS check: display only on AshLight's own windows. Touches no read,
  input or network rule; the footer disclaimer rule is untouched.
- Depends on: nothing. R6 shares the client files.
- Files likely touched: web/index.html, web/app.js or web/settingsio.js,
  app/main.js, app/client/window.js, the settings allow-list in server/al,
  DS 5.4, tests.
- Acceptance test: with `prefers-color-scheme: light` emulated the page
  background computes to rgb(15, 18, 22) and a capture has mean relative
  luminance under 0.05; with the setting on Light it computes to white;
  a node test proves themeSource is set before window creation.
- ZERO-CLICK: dark with no action; the choice is one optional click.

### R2. Make Play one surface: glance band, then what needs you, then prose

- Action: (a) one glance band at the top of the left column holding zone
  name, zone timer, level, deaths and session in a single row of cells,
  at most 120 px tall at the client default size; (b) trades and the
  build alert directly under it; (c) the zone guide as an ordinary card
  after them, in `--al-text-body`, the only part allowed to fold or
  scroll; (d) the item card leads with the verdict at the zone-timer
  size and carries a 4 px left edge in the verdict colour (ok, warn or
  `--al-edge`), the same cue the overlay card uses (overlay.css:103-115);
  (e) prose blocks cap at 70 characters and `main` at 1360 px.
- Impact: H. Targets for note 0042 F17 and plan section 03: at 1264 x 821
  the left column fits with no scroll in the typical state (today 207 px
  over) and the trade rows and build alert are fully in view in the
  worst case (today 356 px over, alert hidden).
- Effort: M.
- Risk: the band is tight for long zone names (wrap to 2 lines, timer
  stays); card order is also the subject of 0038 R6, so decide once.
- ToS check: layout of data AshLight already has; no new read, nothing
  sent to the game.
- Depends on: 0041 for the sizes, 0038 R6 and 0043 for order by context.
- Files likely touched: web/index.html, web/app.css, web/tabs.js,
  web/zoneguide.js, tests/test_a11y.py, DS 3 and DS 4.
- Acceptance test: a capture test at 1264 x 821 with the PACK state c and
  f fixtures asserts band height, zero left-column overflow in f, and
  that `#trades` and `#build-alert` end above the column's bottom in c;
  the verdict's computed size equals the zone timer's.
- ZERO-CLICK: nothing to press; the order is fixed in the page.

### R3. Stale and empty values look stale

- Action: set `data-fresh="no"` on `body` while `tailer.idle` is true or
  the feed is down, and `data-empty` on a tile with no value; under
  either, glance values and timers use `--al-text-stale`. Words stay
  ("frozen - log quiet", the pill), so colour never works alone.
- Impact: H for a glance: a frozen number no longer passes for a live
  one, and first-run dashes stop being the brightest marks.
- Effort: S.
- Risk: low; 7.18:1 at 28 px and up stays readable.
- ToS check: the idle state comes only from Client.txt staleness
  (decision 0029); no process check, no new read.
- Depends on: nothing.
- Files likely touched: web/app.js, web/status.js, web/app.css, tests.
- Acceptance test: in PACK state d the computed colour of `#zone` and the
  three tile values is rgb(153, 161, 170); in state c it is
  rgb(228, 232, 236); in state a the dashes are muted.
- ZERO-CLICK: follows the feed by itself.

### R4. Colour only for exceptions

- Action: (a) the running and done pills become neutral (glyph and word
  stay); blocked and failed keep their colour; (b) flip the button
  default: bare `button` is quiet, `.primary` is filled, used for the
  consent button only; (c) one amber cue per item: drop the trades card
  outline (app.css:187), keep the row edges; the slower split
  (app.css:436) goes to normal text with its word; (d) footer lines and
  the fold summary take `--fk-text-muted` (7.18:1 at 13 px).
- Impact: M to H. In the normal state the header has no colour, so an
  amber or red pill is the only coloured thing when it appears.
- Effort: S.
- Risk: a neutral "live" pill is less of a reassurance; the glyph `[+]`
  and the word remain.
- ToS check: the floor rule on the visible reading indicator: the pill
  stays, with glyph and words, in the same place. The disclaimer rule:
  the sentence stays shown in the footer at AA contrast; only its
  brightness changes. If the operator reads "show" more strictly, keep
  the disclaimer at `--fk-text` and mute the other two lines.
- Depends on: 0042 R7 (one status vocabulary) for the pill words.
- Files likely touched: web/app.css, web/index.html (5 class changes),
  tests/test_ux_review.py, DS 6.
- Acceptance test: in PACK state f the computed colour of `#reading` and
  `#link` is the muted token; exactly one element matches
  `button.primary`; a pixel count of a Settings capture finds no filled
  accent block wider than 100 px.
- ZERO-CLICK: nothing to press.

### R5. Quiet control edges and an honest checkbox

- Action: introduce `--al-control-edge` (values above) for input, select,
  textarea, secondary button and checkbox boundaries; draw the unchecked
  checkbox as an empty box with that edge and the checked one filled
  with the accent; keep the 3 px `--fk-text` focus ring.
- Impact: M. The Items tab stops being a grid of bright boxes while every
  control keeps 3:1 against both neighbours (NTC).
- Effort: S.
- Risk: 3.61:1 is close to the 3:1 floor; the contrast test must own the
  number so a later edit cannot slip under it.
- ToS check: none of the floor rules is touched (styling only).
- Depends on: 0044 for target size (the 20 px checkbox is its item).
- Files likely touched: web/app.css, DS 5.1 and the DS 5.2 block,
  tests/test_design_contrast.py.
- Acceptance test: four new rows in the DS 5.2 block (edge on page and on
  card, light and dark, minimum 3.0) pass in tests/test_design_contrast.py;
  no rule outside the token block uses `--fk-text-muted` as a border.
- ZERO-CLICK: nothing to press.

### R6. One palette for the client window, and a compact rule that applies

- Action: start page always dark with the kit values (drop its light
  branch), window background "#0f1216", and replace the 820 px threshold
  by one that covers the default window with room (899 px), or fold the
  compact tier into the shell.
- Impact: M. No tone step while the client starts; the compact tiles
  apply in the default window: state c is 1034 px of content with the
  tier (PACK, 1280 x 760) and 1063 px without it (M4), so about 29 px.
- Effort: S.
- Risk: a taller window between 821 and 899 px gets tighter tiles.
- ToS check: none of the floor rules is touched. The start page keeps the
  GGG disclaimer (app/client/starting.html).
- Depends on: R1 (same files), R2 (it may remove the tier).
- Files likely touched: app/client/starting.css, app/client/window.js,
  web/app.css, app/test.
- Acceptance test: a node test reads starting.css and window.js and finds
  only the three kit dark values; a capture at 1264 x 821 shows the tile
  padding of the compact tier.
- ZERO-CLICK: nothing to press.

### R7. One scale, one badge, one row, held by a lint

- Action: declare the spacing and radius tokens above and use only them;
  remove the 4 px radius; replace `.pill`, `.verdict`, `.tab-mark` and
  `.tag` by one `.badge` with a compact size; one list row rule with two
  densities (8 px and 4 px); baseline-align event rows and reserve the
  4 px edge column on every row; use one edge width (4 px dashboard, 3 px
  overlay, written down in DS 4); give the three overlay plates one
  shared class. Add a test that fails on a spacing or radius value
  outside the set.
- Impact: M. Little visible change by itself; it stops the drift that
  produced 5 badge looks and 7 row paddings; without the lint each new
  card adds another.
- Effort: M.
- Risk: many small visual diffs in one change; do it after R2 so it is
  not done twice.
- ToS check: none of the floor rules is touched. Overlay rule: no new
  repaint, no animation; the plate CSS is the same after the merge.
- Depends on: R2, R4, R5.
- Files likely touched: web/app.css, web/*.js that create badges,
  app/overlay/overlay.css, app/overlay/index.html, DS 4, a new test.
- Acceptance test: the new test passes; M1 re-run reports 100 percent of
  spacing values in the set and 3 radii; PACK overlay window captures
  are pixel-identical before and after.
- ZERO-CLICK: nothing to press.

### R8. The mark beside the name

- Action: show the existing small mark at 20 px left of "AshLight" in the
  header, as an image from the dashboard's own files.
- Impact: L. Ties the window, tray and taskbar icon to the page.
- Effort: S.
- Risk: none; the dashboard CSP already allows its own images
  (server/al/http.py:39).
- ToS check: the branding rule: the mark is AshLight's own flame and ash
  drawing (docs/design/0005-brand-mark.md), no GGG art, logo or name.
- Depends on: nothing.
- Files likely touched: web/index.html, web/app.css,
  tests/test_brand_assets.py.
- Acceptance test: the header holds one image with empty alt text and a
  20 px box; the CSP test stays green.
- ZERO-CLICK: nothing to press.

## Cut or merge

- Remove the trades card outline, the 4 px radius, the `.tag` look and
  the start page's light palette (R4, R7, R6).
- Merge the three overlay plate blocks into one class (R7).
- Merge the short-window tier into the shell tier if R2 lands (R6).
- `--fk-surface` and `--fk-status-bad` in overlay.css are used by no
  rule. Remove them only together with the matching DS 5.2 row, which
  tests/test_design_contrast.py reads; otherwise leave them.
- Keep `--al-edge` although it equals the muted grey: it exists so that
  high-contrast mode does not whiten the card edge (overlay.css:18-20).
- The two header pills could become one; the wording side is 0042 R7.
- The empty item card repeats "Nothing checked yet." twice; one sentence
  is enough. Wording is 0042's; the visual gain is one paragraph less.

## Rejected

- Game-styled chrome (rarity colours, item frames, fonts or textures that
  imitate the game). Floor: no GGG art, logos or trademarks in branding,
  and never present AshLight as official.
- A blurred or frosted overlay plate, or a plate that adapts to the scene
  behind it. Both need the game's pixels continuously. Floor: the screen
  is read only once per manual hotkey press, never by a watcher or timer.
- Dimming the dashboard or switching theme when the game is in front or
  running. It needs a process or window check, against decision 0029.
- A pulse, flash or slide for a new trade or verdict. DS 2 principle 3
  and DS 10 forbid motion; the overlay must not cost FPS.
- A second overlay card or a third HUD line to carry more. Decision 0014
  (one card slot) and DS 7.2 stand; no reversal condition is met.
- Red for a downgrade verdict or a falling price. DS 6 reserves red for
  failures and deaths.
- The brand orange as the interface accent. It sits beside warn amber and
  would blur "needs you soon".
- Editing kit token values in this tree. FLEET item 11; a wish for a kit
  3:1 edge token goes to the kit owner as a note.
- Icon or web fonts from a CDN. Stack rule: no CDN at runtime.

## Open questions

- Should the browser path be dark by default too, or only the desktop
  client? Recommended: both, by the static attribute. Adjudicator.
- Does the operator accept a muted disclaimer line (R4 d)? The floor says
  "show"; a strict reading keeps it at full text colour. Operator or
  adjudicator.
- Is 10.55:1 body text comfortable on the operator's second monitor in a
  dark room? Not measurable here (no photometer, headless captures);
  settle by eye once, then freeze the value in the contrast test.
- Does the default client window give 821 px of content on Windows 11?
  UNVERIFIED; R6 picks a threshold that does not depend on it.
- All captures are headless Chrome, not the Electron window, and light
  mode has 3 captures. A light-mode pass of every tab is needed only if
  the Light choice of R1 is kept.
