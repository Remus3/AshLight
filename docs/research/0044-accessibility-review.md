# 0044 - Accessibility review

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B8
accessibility. WCAG 2.2 AA for the dashboard, the desktop client window
and, as far as it applies to a click-through non-focusable surface, the
overlay; plus the automated checks and tests that would hold the result.
Status: draft

## Sources (all accessed 2026-11-18)

- S1: W3C WAI, WCAG overview page, https://www.w3.org/WAI/standards-guidelines/wcag/
  - WCAG 2.2 is the current recommendation; its latest update is dated
  12 December 2024 (first 2.2: 5 October 2023); WCAG 3 is an early draft.
- S2: W3C, Understanding SC 2.2.1 Timing Adjustable,
  https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html -
  content that disappears after a set time is a time limit, unless a
  non-timed way to get the same information exists (its toast example).
- S3: Electron docs, webContents,
  https://www.electronjs.org/docs/latest/api/web-contents - the
  `zoom-changed` event (Ctrl + wheel request), zoom modes, visual (pinch)
  zoom disabled by default.
- S4: Electron docs, Menu, https://www.electronjs.org/docs/latest/api/menu
  - a default application menu is created when the app sets none; null
  removes it. The page does not say what happens to the zoom
  accelerators; see F4.
- S5: WCAG 2.2 success criteria numbers and levels as cited below
  (https://www.w3.org/TR/WCAG22/). Not re-read in full this session; the
  numbers and AA / AAA levels come from the recommendation as known before
  this session. UNVERIFIED re-read.
- S6: Chrome "keyboard-focusable scroll containers" (shipped in Chrome 130,
  2024): a scroller with no focusable child becomes focusable by itself.
  From prior knowledge, not re-fetched. UNVERIFIED.
- S7: Machado, Oliveira, Fernandes (2009) colour vision deficiency
  simulation matrices, severity 1.0, applied in linear RGB (used for the
  CVD numbers below; the maths only, no copied text).
- PACK: the ultraplan UI evidence pack `up-evidence` (synthetic states a
  to g, 135 dashboard captures, overlay composites; made 2026-11-17 at
  b8fda80). Cited by path inside the pack.
- PROBE: this note's own follow-up probe (headless Chrome over CDP, state
  f on port 8966, an existing synthetic demo log, below-normal priority,
  stopped after use), kept outside the repo at
  `<sidecar>\Scratch\up-0044\probe-out\probe.json` with 32 screenshots
  (focus walk on Play, forced colours dark and light, prefers-contrast
  more, reflow at 200 / 400 percent, text-spacing override, live-region
  mutation count, the auto tab switch). A second probe for the other four
  tabs' focus walk was written but not run (the earlier attempt of this
  task stopped); the pack's DOM focus order covers those tabs.
- CVD: `<sidecar>\Scratch\up-0044\cvd.json` - CIE76 colour distance of the
  kit status tokens under normal, protan, deutan and tritan simulation (S7).
- Repo, read 2026-11-18: web/index.html, web/app.css, web/tabs.js,
  app/overlay/overlay.css, app/client/window.js, server/al/state.py,
  tests/test_a11y.py, docs/design/0001-design-system.md sections 5 and 11,
  ROADMAP.md rows UX-A11Y, UX-U8, MERGE-SEAMS-FOLLOWUP. Sibling notes:
  0042 (usability), 0048 (performance budgets), 0045 (local surface).

## Summary

- The dashboard is in good shape against WCAG 2.2 AA: every text pair is
  at least 4.5:1 (lowest 5.31 dark, 4.90 light, PACK key measurement 10),
  nothing animates and reduced motion is honoured globally, the page
  reflows at 320 CSS px with no horizontal scroll at 200 and 400 percent,
  a text-spacing override clips nothing, landmarks and 14 headings are in
  order, no focusable element is unnamed, and no state is carried by
  colour alone (glyph plus word everywhere).
- The pack's overlay finding (key measurement 15: 13 px text 3.81 to 4.19
  over bright scenes) is a measurement artefact: the pack blended the text
  with the plate instead of the scene. Pixel sampling of the pack's own
  PNG gives 4.83 (muted) and 4.97 (amber) over white, matching design 0001
  section 5.2. The overlay passes 1.4.3, with a thin 0.3 margin (F1).
- Real defects, all fixable in CSS or a few lines of JS: the Play column
  focus ring is clipped to one 3 px edge by its parent (F2); in forced
  colours every tab gets the same underline, so the selected tab is shown
  by weight only (F3); the auto switch to Play leaves focus on a
  de-selected tab (F9); disabled buttons look enabled (F12).
- The one possibly High item is the desktop client: `win.setMenu(null)`
  (app/client/window.js:171) with no zoom handler may leave the companion
  window with no keyboard zoom, a 1.4.4 Resize Text failure there (F4,
  UNVERIFIED until a probe runs in Electron).
- The 20 s overlay card passes 2.2.1 because the dashboard keeps the same
  item check without a timer (S2 toast rule); the dashboard text that says
  "here and on the overlay for 20 seconds" is wrong about "here" (F10).
- Top recommendations: R1 an in-browser a11y pass in the existing CDP
  harness (no new dependency), R2 the column focus fix (MERGE-SEAMS F4),
  R3 forced-colours tab state, R4 the client zoom probe and fix.

## Current state

- Structure: `<html lang="en">` (web/index.html:2); one banner
  (web/index.html:35), main (:66), footer (:602); h1 AshLight (:36); a
  WAI-ARIA tablist with roving tabindex (:41-51) and arrow / Home / End
  keys (web/tabs.js:50-58); tabpanels with tabindex 0 (:67, 230, 321, 436,
  509).
- Live regions: 12 role=status nodes (index.html:55, 56, 60, 81, 154, 173,
  201, 367, 371, 449, 503, 564), all polite; the cap is held by
  tests/test_a11y.py:148 and design 0001 section 11 N6. PROBE live_idle:
  0 mutations while idle.
- Focus: a 3 px ring in the text colour on every focusable kind
  (web/app.css:91, 148, 230, 253-254, 328, 504, 515-516); tabs use an inset
  ring (app.css:494).
- Motion: `prefers-reduced-motion: reduce` kills animation, transition and
  smooth scrolling for every node (app.css:429-431); the overlay forces no
  animation unconditionally (app/overlay/overlay.css:23). PACK key
  measurement 12: 0 animations, 0 transitions in all 135 captures.
- Contrast modes: `prefers-contrast: more` lifts muted text to the text
  colour (app.css:424-426; overlay.css:134-139); the overlay has a
  forced-colours block (overlay.css:151-157, ROADMAP UX-U8); the dashboard
  has none and relies on the system mapping.
- Existing guard: tests/test_a11y.py (227 lines, 13 tests: landmarks,
  heading order, polite only, no ticking value in a live region, pills
  written only on change, the live-region cap, no positive tabindex, every
  control named, aria-label placement, focus ring per focusable kind, text
  colours as measured token pairs). It is static (html.parser and regex);
  nothing checks the rendered page for clipping, forced colours, zoom or
  real focus order.
- Overlay: a separate click-through, non-focusable window (main.js:221-244);
  0 interactive elements, 0 live regions, a screen-reader-only disclaimer
  (PACK key measurement 13).
- Card lifetime: EVAL_CARD_S = 20 and PRICE_CARD_S = 20
  (server/al/state.py:35, 39) bound only the overlay card
  (state.py:750-785); the snapshot keeps `eval` without expiry
  (state.py:1841-1843) and the dashboard renders it (web/app.js:614, 1011).

## Findings

F1 - Overlay contrast passes; the pack's number is wrong (method).
- Evidence: PACK `run/c/overlay.json` contrast.method says "text x page
  opacity over that" (over the plate composite). The page opacity is a
  group opacity (overlay.css:28, `html { opacity: 0.9 }`), so a text pixel
  is 0.9 text + 0.1 scene. PACK `run/c/overlay-window.png`: muted text
  pixels are (153, 161, 170) at alpha 230 (0.90), the plate is alpha 212
  (0.83). Over white that composites to #a3aab2 text on #383b3e plate:
  41 pixels of #a3aab2 (+-2) in PACK `run/c/overlay-1920x1080-white.png`
  against 13 near the pack's predicted #8f979f (anti-aliasing), and 17
  amber pixels at the group-opacity value against 0 at the pack's value.
- Recomputed (opacity 0.9, plate 0.92, scene black / grey / warm #f2e6c8 /
  white): text 12.50 / 11.35 / 9.77 / 9.37; muted 6.02 / 5.66 / 5.01 /
  4.83; amber status 6.26 / 5.85 / 5.17 / 4.97; ok green 6.19 / 5.77 /
  5.07 / 4.89; bad red 4.92 / 4.60 / 4.07 / 3.91 (red is never overlay
  text, design 0001 section 5.2). Design 0001 states 4.80 for muted at
  0.9; the 0.03 gap is 8-bit rounding.
- Why it matters: SC 1.4.3 passes; no plate or opacity change is needed
  for conformance. A plan built on key measurement 15 would spend work on
  a non-defect. The margin is thin (0.33 for muted over white), and the
  1 px text-shadow (overlay.css:53) does not count toward contrast.

F2 - Play column focus ring clipped; one redundant tab stop.
- Evidence: PROBE tabs.play: `#panel-play > div.play-main` keeps 3 px of
  ring only on the right edge, 0 px left / top / bottom; `.play-side`
  keeps only the left edge; both clipped by `#panel-play`, which has
  `overflow: hidden` (app.css:551-552) while the ring is drawn outside
  (`outline-offset: 2px`, app.css:515-516). Play has 11 tab stops, 3 of
  them containers (panel, two columns: index.html:67, 68, 170). The
  panel stop adds nothing on Play because both columns are stops.
- SC: 2.4.7 Focus Visible (AA) is weakened, not strictly failed (one edge
  shows); 2.4.11 Focus Not Obscured (AA) is about author content covering
  focus and is met. Severity Medium: a keyboard user sees a 3 px line at
  the column seam and cannot tell which column has focus.
- This is MERGE-SEAMS-FOLLOWUP F4 (ROADMAP.md:2037-2046), confirmed.

F3 - Forced colours: the selected tab shows by font weight only.
- Evidence: PROBE forced.dark and forced.light: selected and unselected
  tabs both report a CanvasText bottom border (white on black, black on
  white); weight 700 against 400 is the only cue. Screenshot
  `probe-out/forced-dark-play.png`: five identical underlines. The
  transparent unselected border (app.css:486) is forced to a system colour
  and the accent border on the selected tab (app.css:492) becomes the same
  colour.
- SC: 1.4.11 Non-text Contrast asks that a state indicator be
  perceivable; a weight change alone on 16 px text is a weak cue for low
  vision users, who are the forced-colours audience. 4.1.2 is met
  (aria-selected). Severity Medium (forced-colours only).
- Everything else under forced colours holds: pills, verdicts and checks
  keep their words; the focus ring becomes the system Highlight (PROBE
  dark_focus: rgb(26, 235, 255), 3 px, unclipped on the zone guide
  summary); links stay distinct.

F4 - Desktop client: keyboard zoom probably missing.
- Evidence: app/client/window.js:159 `autoHideMenuBar: true` and :171
  `win.setMenu(null)`; no `zoom-changed` or `before-input-event` handler in
  window.js (grep). Electron creates a default menu only when the app sets
  none (S4); the zoom shortcuts Chrome users expect (Ctrl + plus / minus /
  0) are bound by that menu's zoom roles in Electron, so removing the menu
  likely removes them. S3 documents `zoom-changed` for the Ctrl + wheel
  request; whether the default zoom mode applies it without a handler is
  not stated for a BrowserWindow. UNVERIFIED in the real window: the pack
  and PROBE ran in headless Chrome (PACK README GAPS).
- SC: 1.4.4 Resize Text (AA) needs 200 percent text without assistive
  technology; Windows display scaling counts as AT-free only partly
  (it rescales everything, the window minimum size stays). Severity High
  if confirmed: the companion window is the main surface since decision
  0041.
- The dashboard itself zooms well when the browser zooms (F5), so the fix
  is only to give the window the zoom keys back.

F5 - Reflow, text spacing and zoom pass in the page.
- Evidence: PROBE reflow at 200 percent of 1280x760 (640x380 CSS px), 200
  percent of 1920x950 and 400 percent of 1280x1024 and 1280x760 (320 CSS
  px wide): page_overflow_x 0 and no clipped or horizontally scrolling box
  on all five tabs; Play is 2311 px tall at 640 px and 3110 px at 320 px.
  Text-spacing override (line 1.5, paragraph 2, letter 0.12, word 0.16
  em) at 1280x760 and 320x256: no offender, nothing clipped. The app
  shell gives way to normal page flow under 900x560 (app.css:525), which
  is what makes 400 percent work.
- SC: 1.4.10 Reflow and 1.4.12 Text Spacing pass. ROADMAP UX row
  (ROADMAP.md:1035-1038) already guards the 320 px wrap of a long name.

F6 - Motion: nothing to fix.
- Evidence: PACK key measurement 12; app.css:429-431; overlay.css:23. The
  reduced-motion PNGs match the normal ones (PACK `run/*/dash-*-rm.png`).
- SC: 2.2.2 (nothing moves or auto-updates in a moving way; values change
  in place), 2.3.1 (no flash) and AAA 2.3.3 pass.

F7 - Dashboard contrast passes; light green is the thinnest pair.
- Evidence: PACK key measurement 10 (7-9 pairs per view, none under 4.5:1;
  lowest 5.31 dark Run tab, 4.90 light green "[+]"). Non-text: the
  checkbox boundary is a 1 px muted outline (app.css:326-327; muted on
  surface 6.54 dark, 6.07 light, CVD file); the focus ring is the text
  colour (13.9:1 dark, 15.4:1 light on surface-2), 3 px. Tab underline
  accent on surface-2: 6.18 dark, 6.31 light.
- SC: 1.4.3, 1.4.11 pass. Light theme was captured only for states c and
  f (PACK `run-light/`); PROBE contrast checks on the other light views
  did not run (second probe), so light coverage is partial.

F8 - Colour-blind safety: rule C4 holds; the palette itself would not.
- Evidence: every state carries a glyph and a word (web/checks.js:22-27,
  web/prices.js:134, 201, 204, web/status.js:35); glyphs are aria-hidden
  (index.html:57, 61, 206, 452; checks.js:105); event kinds carry text
  tags; the overlay verdict edge repeats the head word (format.js:108).
  The run history "slower" colour (history.js:119) sits on the word
  "slower". No charts exist in web/.
- CVD distances (CIE76, normal / protan / deutan / tritan; under about 10
  two small marks read as one colour): dark ok vs bad 107 / 30 / 5.1 /
  115 (deutan: nearly identical); light ok vs bad 102 / 17 / 18 / 111;
  dark ok vs warn 67 / 20 / 29 / 75; dark accent vs running 2.4 in every
  view (one hue on purpose). Under protan simulation dark bad-red text on
  surface-2 drops from 5.31 to 4.07:1 perceived.
- SC: 1.4.1 Use of Colour passes because of the words. Why it matters:
  the deutan ok / bad near match means any future colour-only cue (a
  coloured dot, a chart series, an edge without a word) fails at once for
  about 6 percent of male players; design 0001 section 5.3 already says
  so, but no test checks new CSS for it.

F9 - Auto switch to Play leaves focus on a de-selected tab.
- Evidence: PROBE switch_before / switch_after: focus on `#tab-build`
  (selected, tabindex 0); an item check arrives; Play is shown and
  `#tab-build` keeps focus with aria-selected false and tabindex -1. The
  rule treats focus in the tab row as "not working in the panel"
  (web/tabs.js:68-73, focusTab returns null for the row). With focus in
  the Build paste box the switch is held and the header says "New on
  Play: item check." (PROBE switch_busy) - correct.
- SC: 2.4.3 Focus Order (A) is strained (the focused tab is no longer the
  roving stop; the next Tab lands in the Play panel, a screen reader hears
  "Build tab, not selected"); 3.2.1 is not involved (not triggered by
  focus). Severity Low: it needs a check to arrive within 10 s of a key
  press in the row (GRACE_MS, tabs.js:43) or later with no other input.

F10 - Time limits: the overlay card passes 2.2.1; dashboard copy misleads.
- Evidence: overlay card 20 s (state.py:35, 750-785), trade requests clear
  after 10 minutes (shown on Play: "Requests clear after 10 minutes"),
  toasts none (N2). The dashboard keeps the item check without expiry
  (state.py:1841-1843). S2: a timed message with a non-timed alternative
  is not a 2.2.1 time limit. Trade requests also stay in the Run tab event
  list. The empty-state copy at index.html:174-176 says the verdict shows
  "here and on the overlay for 20 seconds"; "here" is wrong.
- SC: 2.2.1 passes via the dashboard; the copy is a 3.3.2-adjacent
  clarity issue, not a failure. Severity Low.

F11 - Target size passes; two checkboxes are 20 px.
- Evidence: PACK key measurement after 15: `#history-keep` and
  `#webdata-on` are 20x20 (app.css:326); every other target is at least
  24 px (PROBE targets on Play: 12 targets, 0 small). The label around
  each is a 32 px tall target that toggles the same box (app.css:325).
- SC: 2.5.8 Target Size (Minimum, AA) passes via the equivalent-control /
  spacing exceptions; design 0001 S2 asks 24 px for the hit target itself.
  Severity Low.

F12 - Disabled buttons look exactly like enabled ones.
- Evidence: PROBE disabled_dark / disabled_light: a disabled primary and
  secondary button keep colour, background, border, opacity 1 and cursor
  pointer. No `:disabled` rule in web/app.css (grep). Buttons that disable
  in use: `#buildfile-save` (web/app.js:440) and `#checks-copy`
  (web/checks.js:130).
- SC: not a failure (inactive controls are exempt from 1.4.3 / 1.4.11, and
  4.1.2 exposes `disabled`), but a sighted player clicks a dead button
  with no feedback. Severity Low.

F13 - Live regions: at the cap, and one press can speak three times.
- Evidence: 12 of 12 (Current state); one item check updates
  `#eval-result` and `#price-result` (both polite, atomic, index.html:173,
  201) and, off Play, `#tab-news` (index.html:55). `#link` (index.html:60)
  is role=status only for a connection word that rarely matters to a
  listener. MERGE-SEAMS F2 already asks to free that slot.
- SC: 4.1.3 Status Messages passes (polite, no focus move). Why it
  matters: a new urgent status cannot get a region without removing one;
  two to three consecutive polite announcements per press are the upper
  bound and acceptable.

F14 - Keyboard reach: complete but long on Items.
- Evidence: PACK key measurement 8: tab stops Play 12, Items 49, Build
  20, Settings 16, Run 6 (DOM order). The Run / Items / Build columns
  scroll (app.css:556) without tabindex; a column with a focusable child
  scrolls by keyboard from that child, and one without becomes focusable
  by itself in Chrome 130 and later (S6, UNVERIFIED for Electron 45).
  No keyboard trap found (PROBE walk returns to the first stop). Global
  hotkeys always hold Ctrl or Alt (app/hotkey.js:2-6), so 2.1.4 Character
  Key Shortcuts does not apply.
- SC: 2.1.1, 2.1.2, 2.4.1 (landmarks and headings bypass blocks) pass.
  Severity Low: 49 Tab presses to the end of Items.

F15 - Screen-reader walk-through is feasible; not yet done with a real
reader.
- Evidence: PROBE ax (Play): 725 nodes; banner, main, contentinfo, 4 named
  regions; 14 headings in order (h1 AshLight, h2 per card, h3 inside the
  item check); 5 tabs; 0 unnamed focusables; the deaths dash has
  screen-reader text (index.html:125). The overlay is not reachable by
  keyboard by design; every overlay item is mirrored on Play (zone, level,
  deaths, trade card, item card), which is its accessible equivalent.
- Gap: no NVDA / Narrator pass exists; the AX tree is a proxy.

F16 - Electron-only states not measured.
- Evidence: PACK README GAPS: the companion window, its starting page
  (app/client/starting.html, role=status lines :14-15), tray menu and the
  Windows high-contrast themes in the real window were not captured. The
  window paints `#16181d` before load (window.js:158), a dark flash in the
  light or high-contrast theme (cosmetic, no SC).

## Recommendations

R1 - Add an in-browser a11y pass to the existing CDP harness.
- Action: extend app/test/cdp (the headless Chrome harness behind
  tests/test_dash_console.py) with an a11y job over one fixture state:
  AX tree (no unnamed focusable, heading levels never skip, landmark set),
  a real Tab walk on all five tabs with ring-visibility per stop (no ring
  edge under its width unless the element itself is clipped), forced
  colours emulation (selected tab has a border unlike the others),
  320 CSS px reflow and the text-spacing override (no horizontal scroll,
  no clipped text box), reduced-motion parity, and a contrast sweep of
  computed pairs with a planted failing pair as a self-test.
- Impact: H - the static test_a11y.py cannot see clipping, forced colours
  or real focus order; F2, F3 and F9 would have been caught.
- Effort: M. Risk: low; headless Chrome is already a test dependency of
  test_dash_console.py; the job must skip cleanly where Chrome is absent,
  as that test does.
- ToS check: drives AshLight's own page in a windowless Chrome with
  synthetic Tab keys to that page only; nothing reaches the game, no
  clipboard or screen read (floor rules "never send input to the game",
  "clipboard / screen only per hotkey press" untouched).
- Depends on: nothing. Files likely touched: app/test/cdp/a11y.mjs (new),
  tests/test_a11y_render.py (new), tests/test_dash_console.py (shared
  fixture start).
- Acceptance test: the new pytest runs in about 10 s, fails on a planted
  clipped ring, a planted unnamed button and a planted 3:1 pair, and is
  green on main after R2 and R3.
- ZERO-CLICK: a test; no player step.

R2 - Fix the Play column focus (MERGE-SEAMS-FOLLOWUP F4).
- Action: drop tabindex from `#panel-play` (index.html:67), keep the two
  columns as labelled groups with tabindex 0, and draw their ring inside
  (`outline-offset: -3px` for .play-main, .play-side and .panel-grid >
  .col at app.css:515-516), matching the tab ring (app.css:494).
- Impact: M - a visible, unambiguous ring on both columns; one fewer stop.
- Effort: S. Risk: low; tests/test_a11y.py:202 (ring per focusable kind)
  stays green.
- ToS check: layout only; touches no floor rule.
- Depends on: none (R1 guards it). Files likely touched: web/index.html,
  web/app.css, tests/test_a11y.py.
- Acceptance test: R1's walk shows 3 px of ring on all four edges of each
  column at 1280x760 and 1024x700; Play has 10 stops in state c.
- ZERO-CLICK: no player step.

R3 - Give the selected tab a forced-colours cue.
- Action: add `@media (forced-colors: active)` to web/app.css with
  `button.tab { border-bottom-color: Canvas; }` and
  `button.tab[aria-selected="true"] { border-bottom-color: Highlight; }`.
- Impact: M - the current tab is visible in every Windows contrast theme.
- Effort: S. Risk: low; system colour keywords only (design 0001 C3
  allows them where tokens cannot apply, as overlay.css:151-157 does).
- ToS check: CSS only; touches no floor rule.
- Depends on: none. Files likely touched: web/app.css,
  tests/test_ux_review.py or R1's job.
- Acceptance test: under forced-colors emulation the selected tab's
  bottom border colour differs from every other tab's (R1), dark and light.
- ZERO-CLICK: follows the OS setting; no click.

R4 - Probe and restore zoom in the desktop client.
- Action: in the Electron test path, open the client window hidden, send
  Ctrl+= to its own webContents and read `getZoomFactor()`; if it stays
  1.0, add a hidden application menu with the zoomIn / zoomOut / resetZoom
  roles (or a `before-input-event` handler for Ctrl + plus / minus / 0)
  and a `zoom-changed` handler for Ctrl + wheel, persisting the factor in
  the window state the client already keeps (readState,
  app/client/window.js:84).
- Impact: H if F4 is confirmed - 1.4.4 for the main surface.
- Effort: S to M. Risk: low; the menu stays hidden (autoHideMenuBar), no
  reload or devtools accelerator is added (keep `devTools` gated,
  window.js:168).
- ToS check: the key event goes to AshLight's own hidden test window, never
  to the game; the overlay keeps its own fixed zoom (main.js:191).
- Depends on: none. Files likely touched: app/client/window.js,
  app/test/client.test.js.
- Acceptance test: an Electron test shows zoom 1.1 after one Ctrl+= and
  2.0 reachable; the factor survives a window restart.
- ZERO-CLICK: zoom is the player's own key; nothing new to set up.

R5 - Keep focus on the selected tab when Play is shown automatically.
- Action: in web/tabs.js treat focus in the tab row as working in the
  current tab (focusTab returns state.current when the active element is
  a tab), so a switch never strands focus; alternatively, when a switch
  happens with focus on a tab, move focus to the Play tab (one element in
  the row, the roving stop).
- Impact: L - keyboard and screen-reader users keep a consistent stop.
- Effort: S. Risk: low; app/test/tabs.test.js covers shouldSwitch.
- ToS check: dashboard logic only.
- Depends on: none. Files likely touched: web/tabs.js,
  app/test/tabs.test.js.
- Acceptance test: a node test with focus on `tab-build` and a notify
  call: either no switch plus the header news, or Play selected with focus
  on `tab-play`; never focus on a tabindex -1 tab.
- ZERO-CLICK: no player step.

R6 - Free a live-region slot and document the speech budget.
- Action: make `#link` a plain pill (MERGE-SEAMS F2), lower the cap test
  to 11 with one slot reserved for urgent states, and write the per-press
  announcement budget (eval, price, at most one header line) into design
  0001 N6.
- Impact: M - room for a future urgent status without removing one.
- Effort: S. Risk: low; tests/test_a11y.py:148.
- ToS check: copy and markup only.
- Depends on: none. Files likely touched: web/index.html,
  tests/test_a11y.py, docs/design/0001-design-system.md.
- Acceptance test: 11 role=status nodes; test_a11y green; PROBE-style
  idle run shows 0 mutations.
- ZERO-CLICK: announcements stay automatic and polite.

R7 - A visible disabled state.
- Action: add `button:disabled { opacity: 0.6; cursor: not-allowed; }` (or
  a muted border and text) and make each disabling site say why next to
  the button (the build file and checks copy rows already have status
  lines).
- Impact: L. Effort: S. Risk: low; keep the disabled text at least 3:1 as
  a courtesy even though exempt.
- ToS check: CSS only.
- Depends on: none. Files likely touched: web/app.css.
- Acceptance test: computed style of a disabled button differs from the
  enabled one (R1 or a static CSS test).
- ZERO-CLICK: no player step.

R8 - Correct the item-check empty text.
- Action: say the dashboard card stays and the overlay card leaves after
  20 seconds (index.html:174-176), and record the 2.2.1 reasoning (the
  dashboard is the untimed alternative) as an N5 note in design 0001.
- Impact: L. Effort: S. Risk: none.
- ToS check: copy only; it keeps naming the per-press clipboard read.
- Depends on: none. Files likely touched: web/index.html,
  docs/design/0001-design-system.md, the exact-copy test that holds it.
- Acceptance test: the copy test asserts the new sentence.
- ZERO-CLICK: no player step.

R9 - 24 px checkboxes.
- Action: set `.check input` to 24x24 (app.css:326).
- Impact: L - meets design 0001 S2 without the exception. Effort: S.
- ToS check: CSS only. Files likely touched: web/app.css.
- Acceptance test: PACK-style target scan reports 0 targets under 24 px.
- ZERO-CLICK: no player step.

R10 - Lock rule C4 with a test.
- Action: a static test that every CSS rule setting a status colour
  (`--fk-status-*`) targets an element whose markup or JS also writes a
  word or glyph (pill, verdict, kind tag, check word), with an explicit
  allow-list for edges that repeat a heading word.
- Impact: M - the deutan ok / bad near match (F8) makes any colour-only
  cue an instant failure; the test makes it impossible to merge one.
- Effort: S. Risk: false positives handled by the allow-list.
- ToS check: test only. Files likely touched: tests/test_a11y.py.
- Acceptance test: planting `.foo { color: var(--fk-status-ok) }` on a
  wordless node fails the test.
- ZERO-CLICK: a test.

R11 - Widen the overlay contrast margin (optional).
- Action: raise the overlay plate to 0.96 (overlay.css:16) or the overlay
  muted token to about #b0b8c0, and fix the pack method note so later
  reviews composite text over the scene (F1).
- Impact: L - muted over white goes from 4.83 to 5.49 (plate 0.96) or
  6.08 (lighter muted); helps the 13 px secondary lines on bright scenes
  in practice, conformance is already met.
- Effort: S. Risk: a darker plate hides a little more of the game corner;
  check the overlay budgets test.
- ToS check: overlay stays a separate click-through, non-focusable window;
  opacity and colour only.
- Depends on: a ruling in plan section 03 (target design) on the plate
  value. Files likely touched: app/overlay/overlay.css,
  docs/design/0001-design-system.md 5.2, tests/test_ux_review.py.
- Acceptance test: the overlay colour test reports muted >= 5.0 over white
  at opacity 0.9.
- ZERO-CLICK: no player step.

R12 - One real screen-reader pass, scripted where possible.
- Action: after R1 to R6 land, an agent runs Narrator (built into Windows)
  or NVDA over the dashboard in a browser on a fixture core and records
  what is heard for: page load, an item check, a trade request, a tab
  switch, the Settings form. The AX-tree snapshot from R1 becomes the
  regression guard; the manual pass is repeated only when the tab set
  changes.
- Impact: M. Effort: M. Risk: it needs a visible window and audio on the
  operator's machine, so it must run when the operator is not playing.
- ToS check: reads AshLight's own page with an OS reader; nothing touches
  the game.
- Depends on: R1-R6. Files likely touched: none (findings go to a research
  note).
- Acceptance test: a dated transcript of what was heard per step, no
  unnamed or doubled announcements.
- ZERO-CLICK: a dev task; no player step.

## Cut or merge

- Merge R2 and R6 into MERGE-SEAMS-FOLLOWUP (its F4 and F2) rather than new
  rows; that row already owns them.
- Merge R7 and R9 into one CSS package with R3 (one small change to
  web/app.css plus its tests).
- Deferred: axe-core as a dev-only checker. It would add an npm
  devDependency and a licence check (MPL-2.0 as known before this session,
  UNVERIFIED), which needs a decision under CLAUDE.md "Third-party code".
  R1 uses only Chrome's own protocol and covers the rules this UI needs;
  revisit only if R1 misses a class of defect in two reviews.

## Rejected

- A screen reader reading the overlay window or an accessible overlay
  focus mode: the overlay must stay non-focusable and click-through
  (CLAUDE.md ToS floor, overlay rule); the dashboard is its equivalent.
- Announcing the item verdict by speech synthesis or a sound on the
  hotkey press: not an accessibility need the dashboard leaves open, and
  design 0001 N2 rules out alerts; no floor issue, rejected on scope.
- Reading the game's own colour-blind or UI-scale settings to match them:
  that would mean reading game files or settings outside Client.txt
  (floor: read only what GGG permits).
- A timer that re-shows the overlay card for longer than 20 s by default
  to satisfy 2.2.1: not needed (S2 alternative rule, F10) and it would
  take the one card slot from the next press (decision 0014).

## Open questions

- F4 needs one Electron probe (R4 first step) to move from UNVERIFIED to
  confirmed or closed; no operator decision needed.
- R11 plate value is a target-design call for plan section 03 (visual
  weight of the HUD against contrast margin); an adjudicator can take it
  if section 03 does not.
- Light-theme coverage outside states c and f and every fold open in the
  other tabs remain unmeasured; R1's job closes this without a new pack.
