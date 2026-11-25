# 0001 - AshLight design system

Status: accepted 2026-11-16 (operator order 2026-11-16). Owner of reviews:
the `design-reviewer` agent (`.claude/agents/design-reviewer.md`). First
audit: `docs/design/0002-first-audit.md`. Sections 3, 4, 5, 6, 7.2, 9, 10
and 11 rewritten 2026-11-22 from the 2026-11-18 target-design amendment
once its TD steps had landed (PLAY-TD-23-RECORDS; decision 0075; plan
`docs/plan/03-target-design.md`).

**NLM** means natural-language messaging: how AshLight phrases events,
statuses and notifications as short natural sentences, and the rules for
making that text from log events (section 9; ruling Q-15, 2026-11-18).

## 1. Scope and sources of truth

- Surfaces: the second-screen dashboard (`web/`), the overlay HUD
  (`app/overlay/`, `app/shared/`), and every user-facing string the core
  produces (the card and event text package `server/al/text/`, e.g.
  `events.py` `summarize`; status words in `server/al/data/status_words.json`).
- Colours, themes and the state vocabulary come from the fleet kit:
  `ops/fleet_kit/tokens.json` / `tokens.css` (kit v32). The kit is never
  edited here. AshLight adds only `--al-*` tokens for needs the kit does not
  cover (the overlay plate, control boundaries) and documents them below.
- Kit UI/UX standard rules this builds on: colour never carries a state
  alone (tokens.json `states._README`); every state has a glyph, a bracket
  row form and a word.
- The ToS floor in `CLAUDE.md` outranks everything here. No design rule may
  need game input, memory reads, or a clipboard / screen watcher.

## 2. Principles

1. **Glance, don't read.** The player looks away from a fight for under a
   second. Every overlay line must be readable in one fixation: number or
   noun first, at most about 5 words, no sentence to parse.
2. **It runs itself.** After the one-time Client.txt opt-in, AshLight needs
   no clicks during play. State changes arrive by themselves; the user acts
   only by choice (hotkey, dismiss, settings).
3. **Quiet by default.** No sound, no motion, no flashing, no modal, no
   focus steal. Something new is shown by its position and a steady edge,
   never by movement.
4. **Right thing, right moment.** What is shown depends on context (map,
   town / hideout, trading, dead, AFK). Detail lives one step away on the
   dashboard, never stacked on the overlay.
5. **Plain words.** Write like a friend at the next desk: present tense,
   sentence case, the player's own vocabulary, no internal names ("core",
   "token", "SSE", "tailer").
6. **Never colour alone.** Every state has a word or glyph; colour only
   reinforces it. Palettes hold WCAG 2.2 AA in light and dark.
7. **Honest.** Say what AshLight knows and what it does not ("level unknown",
   not a guessed number). Never imply AshLight acted in the game.

## 3. Type scale

One family: `system-ui, "Segoe UI", sans-serif` (no web fonts, no CDN).
Numbers use `font-variant-numeric: tabular-nums` so they do not jitter.
Mono stack (`--al-font-mono`): `Consolas, monospace`, Consolas first
because the target is Windows, where it ships with every release.

Dashboard (TD-03): six rem tokens in the token block at the top of
`web/app.css`, each with one fixed rem line box (px at root 16px, scale
step 1):

| Token | Size | Line box | Use |
|---|---|---|---|
| `--al-fs-micro` | 0.8125rem (13px) | 18px | the two footer sentences only |
| `--al-fs-meta` | 0.875rem (14px) | 20px | badges (the tab mark word too), row meta, kept-check rows (review text) |
| `--al-fs-body` | 1rem (16px) | 22px | body, rows, sentences |
| `--al-fs-title` | 1.25rem (20px) | 26px | region and card titles; in-play text (strip labels, sub lines, status words in the bar, strip, notice, build line and item check, the top answers) |
| `--al-fs-glance` | 1.75rem (28px) | 32px | the zone name on the strip, the verdict word of the item check |
| `--al-fs-hero` | 2rem (32px) | 36px | strip numbers (level, deaths, session) |

Rules: no `vw` and no `clamp()` in any font size; nothing under 14px on
the dashboard except the two footer sentences (13px); no weight 600 or
more under 14px, no exception (the tab mark word is a badge at 14px since
F-189, closing review finding TD23-1); in-play text at
the 20px token or larger; uppercase only for labels of 3 words or fewer
(tracking `--al-track-caps`, 0.04em).

Root scale (TD-09): the root font size is 100% x s (`html { font-size:
calc(100% * var(--al-s)) }`), s the largest of 1, 1.25, 1.5, 2 whose
compact cockpit fits, that is a viewport of at least 64em x 43.75em times
s. The size class is full from 75em x 47.5em times s, compact from 64em x
43.75em times s, and flow below the s = 1 compact threshold. The queries
are in em, so the viewer's own default font size moves every threshold;
every track, gap and chrome figure is rem and grows with s.

Distance rule: in-play text is at least 16 arcmin of cap height at the
reference setup (24 inch 1080p, dashboard at 80 cm, overlay at 60 cm);
the title step and up meet it (`tests/test_design_tokens.py`).

Overlay (CSS px at zoom 1.0; the window zoom is the layout `scale`). Two
sizes only, both weight 600, line-height 1.3, tabular numerals, set by two
tokens in `app/overlay/overlay.css` (TD-05, OVL-TD05-LEGIBILITY):

| Token | Size | Roles |
|---|---|---|
| `--al-ovl-fs-hud` | 16px | HUD lines: zone line, zone timer (full text colour, never clipped), level and deaths, the status word, the opt-in zone-guide line |
| `--al-ovl-fs-card` | 14px | card lines: trade card, item check card, price card, zone and act cards, key hint |

The zone-guide line sits on HUD line 2, so it keeps the HUD size (plan 03
named 14px for it; `tests/test_ux_review.py` allows a font size only on
the plate rules). Nothing on the overlay is under 14px. Overlay rule: rendered text never
under 12px **after** zoom, so the smallest overlay size times the minimum
`scale` must be >= 12px; with 14px that means `scale >= 0.86`.

## 4. Spacing and shape

- 4px grid: 4, 8, 12, 16, 24, 32 (tokens `--al-space-0` to `--al-space-4`:
  2, 4, 8, 12, 16px; rem, so they grow with the scale step s).
- Only the tokens (F-189, held by `tests/test_spacing_scale.py`): every
  margin, padding and gap in `web/*.css`, the region padding properties
  included, is 0, auto or `--al-space-0` to `--al-space-4`; a negative
  step is `calc(-1 * var(--al-space-N))`, and the one border allowance is
  `calc(var(--al-space-N) - 1px)` (the pager's 2px dashed end button gives
  back its extra 1px a side, so the box never moves). A literal that was
  off the scale went to the nearest step, a tie to the smaller one.
- Radius: exactly three values, `--al-radius-card` (8px cards and
  regions), `--al-radius-control` (6px controls and overlay plates) and
  `--al-radius-pill` (999px badges); 0 only for a square corner.
- Badge: one `.badge` (it replaced .pill, .verdict, .tab-mark and .tag): a
  word, often after a mono glyph, in a 1px `--al-control-edge` pill edge,
  meta step and line box, weight 600, `--al-space-2` side padding, no
  vertical padding. Its colour comes only from `data-state` (the kit
  states) or `data-verdict` (upgrade, risky) and repeats the word. A place
  changes only the type step or the side padding: the bar status word (20px,
  400, the 32px button), the item check verdict (16px), the tab mark word
  (`--al-space-1` side padding). No renderer makes another badge class.
- List row: one rule, two densities. Roomy (the Checks rows, the graphics
  advisor): a 1px `--fk-border` separator and `--al-space-1` above and
  below. Dense (pager rows, build health rows; the feed and kept-check
  rows in their region sheets): the row's own line box, no separator, no
  padding.
- Hit targets on the dashboard: at least 24x24 CSS px (WCAG 2.2 SC 2.5.8);
  aim for 32px tall buttons (28px in region I, 24px in region B and the
  feed head).
- The layout must work at 320px width (dashboard on a phone or a narrow
  second screen) with no horizontal scroll.
- Tabs (TD-19, PLAY-TD-19B-FOUR-TABS; decision 0075): four tabs in the
  header (ARIA tablist, `web/tabs.js`): Play, Build and items, Run,
  Settings. A remembered `items` tab opens Build and items (then `build`
  is remembered). The picked tab is remembered per viewer (localStorage,
  try/catch). ZERO-CLICK: a new item card, trade request or build alert
  shows Play by itself unless the 10 s grace below holds the shown tab;
  then Play carries the mark word "new". Settings carries "fix" while a
  self-check needs one. Nothing animates; the selected tab is bold (600)
  with a bar and aria-selected (never colour alone; in forced colours the
  bar is Highlight). Arrow keys, Home and End move between tabs (one Tab
  stop for the row).
- Play cockpit (TD-09, PLAY-TD-09B-SKELETON): a fixed grid of 7 regions
  in one DOM order, placed by grid placement only, so Tab order = screen
  order: strip G across the top; context C, feed T and notice N on the
  left; build line B, item check I and kept checks U on the right. The
  tracks are the same in every play state (px at s = 1):

  | Region | Full | Compact |
  |---|---|---|
  | G strip | 100 | 100 |
  | C context | 228 | 212 |
  | T feed | 204 | 204 |
  | N notice | 96 | 52 |
  | B build line | 68 | 68 |
  | I item check | 360 | 348 |
  | U kept checks | 100 | 52 |

  Each column sums to 544 (full) or 484 (compact); the grid is 652 or 592
  plus 108 of chrome (bar 52, main padding 12 + 12, footer 32) = 760 or
  700. One row track, the one under C and I, is flexible, so a taller
  window gives its spare height to C and I alone. A track becomes fixed
  once every region over it has started (`data-fit="yes"`,
  `web/regions.js`); before that it is a minimum, so the page stays
  usable while it loads. Regions are not scroll containers and have no
  tab stop. Below the s = 1 compact threshold (64em x 43.75em) the class
  is flow: one column in the same DOM order with one page scroll.
- Region padding (rem, scaling with s): 12px left and right in every
  region. Top and bottom, as shipped (each region's own sheet loads after
  `web/app.css` and overrides its `--region-pad`), each a spacing token
  since F-189: G 2px (`strip.css`), C 8px (`context.css`, so a full guide
  fits its track), T 4px, N 8px, B 4px (`buildline.css`), I 12px, U 4px,
  or 2px in the compact class (`--pad-u`, so its label and one row, 2 + 4
  + 20 + 20 = 46px, fit the 52px track). G, C, T, B and U pad less than
  the plan's 4 / 12 / 8 / 8 / 8 px so a fractional region top never eats
  the 2px slack minimum (fit check G4). 8px between regions, 12px between the two
  columns.
- Play content (TD-10 to TD-16): the build alert is a state of region B;
  the new-character tip, the language note, the setup line and the
  part-is-broken notes share region N, one at a time; trades are one
  line each in the feed and all 5 open requests show (the core keeps 5).
- Other tabs (TD-19 to TD-21): Build and items and Run are fixed 3 x 2
  card grids (compact class and up). Their lists page at 10 one-line rows
  (8 in the compact class), with a "Full text" page of 3 entries of up to
  3 wrapped lines of 47 characters (2 entries of up to 4 lines of 37 in
  the compact class), `web/pager.js`; pagers move only on a press.
  Settings is a rail with one visible section of at most 448px of rows
  (14 rows of 32px), paged beyond that (`web/rail.js`).
- Header line (TD-09, TD-22): the bar holds the mark and name, the
  character name and one status word, with the tab row under them (one
  row once wide enough). The "New on Play: <what>." polite region stays
  but is visually hidden (no box, no height in the 52px bar); the "new"
  mark on the Play tab is its visible twin.
- Reading indicator and footer (TD-21): the bar status word (`#reading`)
  is the reading indicator on every tab and a button that shows Settings
  > Reading and web data with focus on "Stop reading Client.txt". The
  full credits live in Settings > About and data, and a one-line credit
  stays on each card that shows the credited data (Run > Acts, Build and
  items > Prices, the price row of the item check). The footer keeps the
  GGG disclaimer and trademark lines. The footer's version line shows the
  build cut to 7 hex (footerText); Settings > About and data shows the
  full 12.
- Focus ring (TD-22, PLAY-TD-22A-A11Y-CSS): one 3px accent ring for every
  focusable kind, drawn inside the element (outline-offset -3px), so a
  parent that clips its overflow never cuts it; only the one filled
  accent button and a ticked checkbox take it outside (2px).
- Auto-switch grace (TD-22, PLAY-TD-22B-TAB-FOCUS): a click, key press or
  scroll inside the shown tab or the tab row holds that tab for 10 s; a
  new item card, trade or build alert in that time marks Play "new" and the header line says once "New on Play: <what>.". Once the
  grace runs out Play is shown by itself, so never while the user is
  pressing keys in the tab row; if focus then sits on the tab row it
  moves to the Play tab and the header line says once "Showing Play.
  <What>."; a focus inside a panel is never moved. When the game has
  focus Play is always shown.
- Flow and narrow widths (TD-09, TD-22): in the flow class the Zone cell
  takes a full strip row and Level, Deaths and Session share the next;
  the tab row wraps under the brand; feed rows wrap and a trade row's
  right-hand segment moves under its lead line; the footer sentences
  wrap; nothing takes the ellipsis. Under 520px wide main and card
  padding drop to 12px. Status lines in a hidden tab speak once that tab is shown,
  after the player's own click there (paste, copy, a setting, a save).
- Text spacing and zoom (plan 03 section 3.9): `web/textspacing.js` sets
  `data-text-spacing="user"` on the root while a text-spacing override,
  a user style sheet or a minimum font size changes the line box; then
  rows wrap, tracks are minimums, the page is the only scroll container
  and nothing is clipped.

Measured fit (`docs/design/play-fit-figures.md`, PLAY-TD-01B-FIT-HARNESS,
headless Chrome, s = 1, default text settings): the two-column Play that
the cockpit replaced ran past its box in every filled state (state c,
item card up: 406px at 1280x760, 124px at 1920x950, 598px at 1024x700;
the footer wrapped to 65px under 1500px wide, so its chrome was 131px at
1280x760), with 393 words, 133 visible elements and 10 text styles in
state c. Every row cap of section 9 rule 6 was measured with real words
at exactly the cap, alone and with the WCAG 1.4.12 override, against the
narrowest inner width of its region: all fit, with 27px (item sentence)
to 75px (context title) to spare; real text runs about 0.47em a
character, under the 0.5em budget. The cockpit tracks are held by the
fit harness (`tests/test_play_fit.py`, checks G1 and G2) in every play
state and size class.

G5 totals ruling (2026-11-24, PLAY-FIT-G5-TOTALS; figures in
`docs/design/play-fit-figures.md`). The fit harness holds the G5 word
and element totals of Play in every state since this package (the last
pending marker is gone). They were met by real cuts: each region paints
into its slot with no wrapper of its own, rows hold their parts with no
wrapper (feed rows, strip cells, compare rows, the setup and notice
rows), the item card's price is one row and its links and actions share
one row, the U label is its visible heading, and the empty texts are
shorter, each keeping one short clause of what will appear (item card 3
rows, feed "Nothing yet. Trades and events show here.", notice "none -
tips show here", U "Check items to rank them."). The empty item card
now says only that the check stays here: the overlay card's time is no
longer repeated there (the F-151 wording, reversed here), it is the
Settings > Overlay card time choice. The Play region headings as
shipped: "At a glance" (G), "Right now" (C), "Trades N" or "Recent" (T,
visible), "Notices" (N), "Your build" (B), "Item check" (I) and "Best
checks" (U, visible); the others are for screen readers only.
- Decision: elements at most 100 plus 6 per open trade row, counting
  screen-reader-only ones (amended the same day to 94 visible elements
  plus 6 per open trade row by the G5 screen-reader count ruling below;
  a trade row is the row, buyer, item, price, right segment and Dismiss);
  a trade row has no "Trade" tag (the head "Trades N", the verb, the
  price and Dismiss say it); event rows keep their Death, Level and Zone
  tags (the one quick type cue). Words: at most 250, 110 on first run,
  and 150 in a plain campaign zone (state b; it measured 153 until
  PLAY-FIT-B-WORDS cut the campaign-death notice tip from 16 words to
  13, which also names the card by its title, Deaths).
- Alternatives: a flat 100 met by cutting content (compare rows, strip
  labels); a flat 125; a counter that skips visually hidden elements
  (the 6 screen-reader headings and the trade status; a harness change,
  left to its own row); dropping the event tags too.
- Why: the base stays the design's 100 (the heaviest state with no
  trade measures 83, one-trade states 98 of 106); trade-heavy states
  grow with the player's own open requests, as G6 already allows one
  Dismiss per trade.
- Reverses if: a trade row grows past 6 elements; the counter skips
  visually hidden elements (then recompute the allowance; met and
  superseded by the G5 screen-reader count ruling below); players miss
  the Trade tag in play; a state with no trade measures over 100 after
  this package. State b stays at 150: server text that pushes it past
  150 is cut, and the number does not move.

G5 screen-reader count ruling (2026-11-24, PLAY-FIT-SR-COUNT, adjudicator
call; figures in `docs/design/play-fit-figures.md`). It amends the
element half of the G5 totals ruling above and meets its first
Reverses-if (the allowance is recomputed).
- Decision: G5 counts visible elements only. An element is visually
  hidden, and not counted, when it or an ancestor computes clip
  rect(0px, 0px, 0px, 0px) or clip-path inset(50%) (`.sr-only`, the
  region headings, the empty strip cell words, the feed's status line
  while it is not shown). The harness reports them apart as "hidden". The
  allowance is at most 94 visible elements plus 6 per open trade row.
  Words still count screen-reader text. G6 still counts every control,
  a visually hidden one included.
- Alternatives: keep counting hidden elements (the number mixes visual
  clutter with DOM size, and the screen-reader headings spend the
  visual budget); skip them and keep the base at 100 (it loosens the
  budget by about 6 with no design reason); skip them and tighten to
  about 90 (state c, two trades, reads 104 of 106 today and would fail
  with no extra clutter); drop screen-reader text from the word count
  too (words are reading load, and screen-reader users bear it too).
- Why: G5 limits what the eye has to take in, and screen-reader-only
  elements are not seen. The old 100 held 6 to 8 of them in every
  state (the 6 hidden region headings in all), so 94 keeps today's
  effective limit and nothing loosens quietly. Trade rows hold no
  hidden element, so the 6 per row stands. Measured at 1280x760: the
  heaviest state with no trade reads 76 of 94 (e), one trade 92 of 100
  (f, g), two trades 104 of 106 (c), five trades 110 of 124.
- Reverses if: an element the clip test skips proves visible in play;
  a hiding method in use escapes the clip test (then widen the test,
  not the number); a real state passes 94 plus 6 per trade with no
  extra clutter; the harness goes back to counting hidden elements
  (then restore 100); or the operator rules screen-reader text out of
  the word count.

## 5. Colour

### 5.1 Palette

Kit tokens (from `ops/fleet_kit/tokens.json`, kit v32):

| Token | Light | Dark |
|---|---|---|
| surface | #ffffff | #0f1216 |
| surface-2 | #f3f4f6 | #181c22 |
| text | #1a1d21 | #e4e8ec |
| text-muted | #555d66 | #99a1aa |
| border | #d3d8de | #323840 |
| accent | #1559a8 | #5a9ef0 |
| status-ok | #1d7a3a | #46b85c |
| status-warn | #946200 | #d19a2a |
| status-bad | #c4262f | #f0605a |
| status-unknown | #68707a | #959da6 |
| status-halted | #7a4fcf | #a87cf2 |
| status-running | #1765c4 | #5ea4f5 |
| status-idle | #5b636c | #8a929b |

AshLight additions:

| Token | Value | Why |
|---|---|---|
| `--al-plate` (overlay) | rgba(15, 18, 22, var(--al-plate-a, 0.86)) | HUD plate; the plate alone carries the alpha (default 0.86, floor 0.80); text stays opaque (5.2) |
| `--al-ovl-text-2` (overlay) | #c3c9d0 | overlay secondary text (where, more, the card's third line); kit `text-muted` is 3.91:1 at the alpha floor, so it is not overlay text |
| `--al-ovl-warn` (overlay) | #f0bd55 | overlay warn word (the status slot); kit `status-warn` stays an edge colour on the overlay |
| `--al-control-edge` | #7a828c light, #737c88 dark | control boundary: inputs, selects, textareas, secondary buttons, checkboxes; kit `border` is 1.3-1.6:1, too faint for SC 1.4.11, and `text-muted` is louder than the content; `--fk-text` under `prefers-contrast: more` |
| `--al-text-body` | #30353c light, #c5ccd3 dark | sentences and rows inside cards; `--fk-text` stays on values, names, headings and verdict words |

Overlay colours mirror the kit dark theme (`surface`, `text`, `border`,
`status-warn`, `status-ok`) plus the two overlay-only text tokens above.
Green, red and the warn amber are never overlay text: they are card edges,
and the word carries the meaning. The overlay is always dark: it sits on a
game scene, not on a page, so it does not follow `prefers-color-scheme`.

### 5.2 Measured contrast

Computed with the WCAG 2.2 relative-luminance formula (sRGB linearised,
`(L1 + 0.05) / (L2 + 0.05)`), not estimated. `overlay.plate-worst` is
`--al-plate` at its default alpha (0.86) composited over #ffffff, and
`overlay.plate-floor` the same at the 0.80 alpha floor: the brightest
possible game scene is the worst case for light text on a translucent dark
plate. Overlay text is opaque, so the text colour is used as it is. Each
row is
`foreground background minimum measured`; `tests/test_design_contrast.py`
recomputes every row from the token files and fails if a ratio drops under
its minimum or no longer matches the number written here.

```al-contrast
# text (SC 1.4.3, 4.5:1)
light.text light.surface 4.5 16.91
light.text light.surface-2 4.5 15.37
light.text-muted light.surface 4.5 6.68
light.text-muted light.surface-2 4.5 6.07
light.accent light.surface-2 4.5 6.31
light.surface light.accent 4.5 6.94
light.status-ok light.surface-2 4.5 4.90
light.status-warn light.surface-2 4.5 4.76
light.status-bad light.surface-2 4.5 5.21
light.status-unknown light.surface-2 4.5 4.56
light.status-halted light.surface-2 4.5 4.96
light.status-running light.surface-2 4.5 5.16
light.status-idle light.surface-2 4.5 5.54
dark.text dark.surface 4.5 15.25
dark.text dark.surface-2 4.5 13.89
dark.text-muted dark.surface 4.5 7.18
dark.text-muted dark.surface-2 4.5 6.54
dark.accent dark.surface-2 4.5 6.18
dark.surface dark.accent 4.5 6.78
dark.status-ok dark.surface-2 4.5 6.74
dark.status-warn dark.surface-2 4.5 6.81
dark.status-bad dark.surface-2 4.5 5.31
dark.status-unknown dark.surface-2 4.5 6.23
dark.status-halted dark.surface-2 4.5 5.56
dark.status-running dark.surface-2 4.5 6.60
dark.status-idle dark.surface-2 4.5 5.43
# non-text marks and focus ring (SC 1.4.11, 3:1); control edges: al-token-contrast below
light.text-muted light.surface 3.0 6.68
light.text light.surface-2 3.0 15.37
dark.text-muted dark.surface 3.0 7.18
dark.text dark.surface-2 3.0 13.89
# overlay text over the worst-case (white) scene: default plate 0.86 (7:1)
overlay.text overlay.plate-worst 7.0 10.28
overlay.al-ovl-text-2 overlay.plate-worst 7.0 7.59
overlay.al-ovl-warn overlay.plate-worst 7.0 7.30
# overlay text at the 0.80 alpha floor: primary 7:1, secondary and warn 5.5:1
overlay.text overlay.plate-floor 7.0 8.30
overlay.al-ovl-text-2 overlay.plate-floor 5.5 6.13
overlay.al-ovl-warn overlay.plate-floor 5.5 5.90
# overlay card edges at the alpha floor (SC 1.4.11, 3:1)
overlay.status-ok overlay.plate-floor 3.0 4.03
overlay.status-warn overlay.plate-floor 3.0 4.07
overlay.al-edge overlay.plate-floor 3.0 3.91
```

AshLight's own dashboard colours are measured the same way in the block
below; `tests/test_design_tokens.py` reads each `al-*` value from the token
block at the top of `web/app.css` (light from `:root`, dark from the kit's
dark selectors) and each kit value from tokens.json.

```al-token-contrast
# control boundary (SC 1.4.11, 3:1): on the page and on a card
light.al-control-edge light.surface 3.0 3.89
light.al-control-edge light.surface-2 3.0 3.53
dark.al-control-edge dark.surface 3.0 4.44
dark.al-control-edge dark.surface-2 3.0 4.05
# body text (SC 1.4.3, 4.5:1): on the page and on a card
light.al-text-body light.surface 4.5 12.35
light.al-text-body light.surface-2 4.5 11.22
dark.al-text-body dark.surface 4.5 11.58
dark.al-text-body dark.surface-2 4.5 10.55
```

Not allowed as a boundary or text colour: kit `border` (light 1.43:1 on
surface, 1.30:1 on surface-2; dark 1.59:1 / 1.45:1). It is a decorative
divider only; anything a user must find (an input, a button edge) uses the
control-boundary colour.

Overlay legibility (TD-05, note 0041 recipe): text is opaque and the plate
alone carries the alpha, so a bright scene darkens only behind the plate.
Every alpha composite is rounded to 8 bits a channel as the framebuffer
stores it. Floors: text >= 7:1 at the default plate and secondary and warn
text >= 5.5:1 at the 0.80 floor over white (primary stays >= 7:1 there);
card edges >= 3:1. `tests/test_design_contrast.py` also checks every
overlay text and edge colour over a warm bright scene (#f2e6c8), where each
ratio is higher (text 10.76, secondary 7.94, warn 7.65 at 0.86). The kit
`border` edge (#323840) is decorative only. The overlay has no page
opacity (OVL-TD05-PLATE): the layout's `opacity` value, the "Background"
slider of Settings, sets only the plate alpha `--al-plate-a`
(`layout.js` opacityCss, LIMITS.opacity 0.80 to 1.0); a schema 1 page
opacity of 0.9 to 1.0 migrates to a plate alpha of 0.86 to 1.0.
High-contrast mode (`prefers-contrast: more`) lifts
secondary text to the text colour on both surfaces and makes the overlay
plate opaque; the overlay card's neutral edge keeps its `--al-edge` colour
(U3).

### 5.3 Colour-blind safety

About 8 percent of men and 0.5 percent of women have a colour vision
deficiency, mostly red-green (sources 6, 7). The kit's ok green and bad
red have almost the same luminance (light 4.90 vs 5.21 on surface-2), so a
red-green deficient player cannot tell them apart by colour. Rules:

- Every state shows its kit glyph or word (`[>] reading`, `[x] failed`).
- Event kinds carry a text tag (`TRADE`, `DEATH`, `FROM`) and, where marked
  by colour, also a shape cue (left rule, border). On Play a trade row's
  words are its tag: "<buyer> wants <item> - <price>" and its Dismiss
  (G5 totals ruling, section 4); Run > Recent and the overlay keep the
  word "Trade".
- Never pair red and green as the only difference between two adjacent
  things. Where a categorical palette is needed (charts), use the kit
  `chart` palette with direct labels, or Okabe-Ito hues (source 5).
- Test new colour pairs in a deuteranopia / protanopia simulator before
  merging (Chrome DevTools: Rendering > Emulate vision deficiencies).

### 5.4 Light and dark

The dashboard is dark by default (TD-04, PLAY-TD-04B-THEME-CHOICE;
decision 0075): `web/index.html` ships `<html data-theme="dark">` and the
desktop client starts with the native theme source dark, so nothing needs
a click. One optional setting, Theme in Settings > Appearance and tools
(`web/theme.js`, GET / POST /api/theme, carried by the settings backup),
picks Dark (default), Follow Windows or Light; Follow Windows removes the
attribute, so `prefers-color-scheme` decides through the kit tokens.css,
and the client's native theme follows the same choice. Every colour
reference is a `var(--fk-*)` or `var(--al-*)`; no literal hex in
component CSS. The overlay is always dark and never reads the choice
(5.1).

## 6. State-colour semantics

The reading and connection states have one table:
`server/al/data/status_words.json` (F-131, PLAY-F-131-STATUS-TABLE). Each
state row gives its kit state and glyph (tokens.json `states`), its rank,
the dashboard bar word, the overlay status-slot word (at most 15
characters beside the level text, or at most 27 alone), the Checks row
and detail, and the player's one next step. Every surface takes its words
from it: the bar (`web/status.js`), the overlay status slot
(`app/shared/render_gate.js`), the Checks rows (`server/al/diag.py`
through `server/al/statuswords.py`) and the strip's next step; the two
page copies are held equal by `tests/test_status_words.py` and
`app/test/statuswords.test.js`. A state word is added or changed in that
file, never here. The states, by kit state:

- running `[>]`: reading Client.txt.
- done `[+]`: the dashboard feed is live.
- pending `[ ]`: status unknown, connecting, reconnecting (overlay
  "connecting" / "offline").
- idle `[-]`: not reading Client.txt (no numbers on the overlay).
- blocked `[#]`: waiting for Client.txt, the log quiet for 20 min
  (decision 0029; the overlay hides then, and Settings > Overlay says
  "Overlay hidden: no game activity for 20 min. It comes
  back with the next log line."), Client.txt not found, can't read
  Client.txt, the Client.txt path in the settings missing (all rank 4);
  the reader stalled (rank 5, Checks row "Not reading Client.txt.", no
  bar or overlay word of its own).
- failed `[x]`: can't reach AshLight, or the page was opened without its
  link.

Tokens: running status-running, done status-ok, pending and idle
status-idle, blocked status-warn, failed status-bad; the word and glyph
always carry the state.

The bar shows the worse (higher rank) of the reading and the feed state,
a tie going to the reading state. Normal states are neutral: the reading
word and normal rows carry no colour while all is well.

Event semantics (Play feed, Run > Recent and the overlay card):

- trade request: `accent` edge + the word "Trade" (TD-13); on Play the
  row's own words "<buyer> wants <item> - <price>" and its Dismiss stand
  for that word (G5 totals ruling, section 4). Accent has one
  meaning, "you can act here": links, the selected tab, the focus ring,
  the one filled button and the edge of a trade request that waits for a
  reply.
- warn (`status-warn`) keeps one meaning: act when you can (old build,
  risky waystone, under-level, blocked). It is not "error".
- whisper that is not a trade request, trade accepted / cancelled lines,
  party joins and leaves: Run > Recent only, muted tag (`FROM` / `TO`,
  `TRADE`), no edge. The Play feed holds the open trades plus the newest
  death, level-up and zone entry.
- death: `status-bad` tag (`Death` on Play, `DEATH` in Run > Recent);
  never a full red row (a death is news, not an alarm).
- level up, zone: muted tag only (`Level`, `Zone` on Play).
- a new row says "new" at the start of its right-hand segment for 60 s
  ("new, 2m"); the row's own sentence is not changed.
- build state words (TD-15, region B): "Build fits" `[+]`, "Old build"
  `[?]` and "Wrong class" `[?]`, both with `status-warn`, "No build"
  `[ ]`; the kit word `stale` is not used for "Old build".
- stale data: while the log is idle or AshLight cannot be reached, strip
  values, timers and feed rows use `text-muted` and the zone sub line says
  "frozen <time>".

Red (`status-bad`) is reserved for failures and deaths. Do not use red for
"attention" or for prices.

## 7. Natural use and context

### 7.1 Natural use (zero-click play)

- The only required click in the product is the first-run Client.txt
  opt-in (ToS floor: visible, explicit, revocable). After that, play needs
  no interaction.
- Everything updates by itself: SSE pushes state; timers tick locally; the
  overlay moves when the layout file changes.
- The dashboard session and zone clocks are essential real-time content
  (WCAG 2.2.2 exemption), so they have no pause control. They stop while
  the feed is down (web/app.js tick).
- Hotkey-first: any action a player needs mid-game is a global hotkey
  (today: Alt+Shift+A shows / hides the overlay; Alt+Shift+E checks the
  item the player copied with Ctrl+C in game). Clipboard or screen reads
  happen only on a hotkey press, once per press (CLAUDE.md ToS floor).
- No modals: no `alert`, `confirm`, `prompt`, dialog or toast that blocks
  input or steals focus. The overlay window is non-focusable and
  click-through. One exception, a start-up refusal only (HOME-REFUSAL-COPY,
  REL-HOME-REFUSAL-UI): when the client refuses to start because its
  install folder lies in a Steam library or the game's own folder, it
  shows one blocking OS error box (Electron `dialog.showErrorBox`, title
  `AshLight`) with the refusal sentence and nothing else, once, before any
  window exists, so a Start Menu launch is not silent. The sentence
  (`server/al/paths.py` home_refusal, the same words in
  `app/client/home.js`): `This folder can't hold AshLight: the install
  home may not lie in a '<folder>' folder (a Steam library or the game's
  own folder); install AshLight in its own folder.` No other error, and
  nothing during play, may use an OS error box.
- Notification policy (F-095): AshLight never pulls the eye off the game.
  During play there is no Windows toast or notification, no sound or beep
  and no taskbar or window flash; news is a change of text in place on the
  overlay and the dashboard (section 9 rule 9). The one OS note is the
  tray balloon that says once per run that AshLight is still in the tray,
  shown only when the player closes the window with X, and silent
  (decision 0041). `tests/test_glance_rules.py` scans app/, web/, server/
  and scripts/ for notification, flash and sound APIs and fails on any
  other hit.
- Things that resolve themselves leave by themselves: a stale item (for
  example a trade request the player never answered) should expire after
  a stated time rather than wait for a click. Dismiss stays available.
- Settings save on change (no Save button), and say so in a polite live
  region ("Saved. The overlay moves within a second.").

### 7.2 Context (the right information at the right moment)

| Context (from Client.txt) | Overlay shows | Dashboard emphasis |
|---|---|---|
| In a map / zone | zone, time in zone, level, deaths | strip G: zone, level, deaths, session |
| Entering a guided campaign zone (OVL-ZONE-CARD) | zone card in the card slot for 12 s, only into a free slot (setting "Zone guide on the overlay": On entry, the default, or Always; not under Never) | the zone guide in context region C |
| Closing an act split (OVL-ACT-CARD) | act card for 12 s (`<act> done`, the split time, the gap to the best saved run while run history is on); it drops that entry's zone card | Acts card (Run tab) |
| In town or hideout | zone with "(HO)" tag; trade card if any | context region C in town mode, the feed |
| Trade request arrives | the newest open trade card (who, what, price, where; "+N more" for the rest) | a one-line trade row in feed T with its own Dismiss (plus "Dismiss all" from 2 open requests); all 5 open requests show |
| Died | deaths count changes; no flash, no pop-up; while the opt-in guide line holds line 2, the level and deaths text come back for 20 s | the death row in feed T; the Deaths card (Run tab: newest first, local time, zone and level) |
| AFK / DND | status word on the HUD line | flag under Session |
| Under-levelled for the zone (UTIL-UNDERLEVEL) | status word `N lv under` (gap at or above the setting, default 3) | the Level cell's sub line uses the overlay's words, "N lv under" |
| Not reading / offline | one status word from `server/al/data/status_words.json` ("offline") | the bar status word with the fix |
| Item check hotkey pressed | the press card (verdict, item, top stat) for the card time (20 s by default; setting "Keep a card for" 20 / 60 / 200 s) | item check region I on Play (verdict, compared slots, price row) and the full Item check card on Build and items; the stat weights it adds up are in the Item check scoring card (Build and items); a new card shows Play by itself |
| In a map (UTIL-MAPS, UTIL-MAPRUN-OVL) | row-1 timer is the time in this map (kept across hideout trips) instead of this zone instance; no new line or word; map deaths stay on the dashboard | context region C in map mode; Maps card (Run tab): open map time (counts only while in the map, `(paused)` outside), last 5 maps, average |
| In a campaign act (HUD-ACT) | no change | Acts card (Run tab): splits, zone levels for the current act; in endgame the splits stay, the zone table empties |
| Waystone check (UTIL-WAYSTONE-REWARD) | reward line (`+38% rarity, +12% pack`) replaces the item name in that card | `Rewards: ...` sentence under the risk sentence of the item check |
| Campaign hint (UTIL-CAMPAIGN-CHECKS) | status word, last in the slot order (`Cold res 32%`, `Better flask`, `Boots: no speed`, `Boss: cold`) | Up to 3 hint rows in context region C (`web/context.js`): the boss row as `Boss: <element> damage. Your <element> res: N%.`, the gear rows as their sentence, each sentence in the row's title; a guide block carries its own (PLAY-CAMPAIGN-HINTS-C) |
| Price check from the same press (web data on) | price line replaces the item name in that card; price-only card when no build is loaded (decision 0016) | the price row of region I and the Prices card (Build and items), listings with "about N <primary>" |
| Empty clipboard on the press (OVL-COPY-FIRST) | status card "Copy the item first" | the same words in region I |
| Item check from the same press | none on the overlay | Upgrade search under the item check (TC-UPGRADE) |
| No card due, item key never pressed (OVL-KEY-HINT) | key hint line `<key>: check an item` in the empty slot, for the first 3 game sessions | the item-check help text |

Progressive disclosure (source 9; TD-17): the overlay holds the 2-line
HUD plus one card slot. Its holder is, first match: the press card (item
check, price or merged), the Settings sample card (10 s, only on its
button), the newest open trade card, a zone or act card (12 s, only into
a free slot; it never waits and never returns), the key hint line,
nothing (`server/al/overlayview.py` CARD_HOLDERS; the trade card is built
on the overlay page). Everything else (history, stash coordinates in
full, settings) lives on the dashboard. Never add a third HUD line to fit
a feature; add a dashboard card instead.

HUD line 2 (OVL-LINE2-RULE, OVL-LINE2-GUIDE): level, deaths and one status
word by default. The status slot order, first match, is: the connection
or Client.txt word, "N trades" while another card covers an open trade,
the under-level word, AFK / DND, the zone-guide line, the campaign hint
word, then level and deaths alone. The setting "Zone guide on the overlay" is On entry (default;
the zone card only), Always or Never. Only under Always (an opt-in), in a
guided campaign zone outside town and hideout, the zone-guide line (the
guide entry's `short` field, at most 34 characters, shown as authored or
not at all) replaces the level and deaths text while no connection, log
state, trade count, under-level or AFK / DND word is due, and not while a
zone or act card holds the slot (its line 1 already says the short). A
death or a level-up puts the level and deaths text back for 20 s
(`overlayview.py` CALM_S). Width: the level text, the deaths text and the
status word together are at most 26 characters, counted as `Lv 74  3
deaths` plus the word (`app/shared/format.js` line2Length; the plate is
258px inside and the line keeps a 236px text budget, plan 03 section
5.1); over that the deaths text drops, and the level text too if still
over; a status word over 20 characters stands alone (at most 27).

Dashboard density (UX-DASH-DENSITY, glance review 0004 U26; TD-21): Play
holds only play content and never collapses. Set-once settings live on
the Settings rail, one section shown at a time: Checks, Reading and web
data, Overlay, Keys, Appearance and tools (the graphics advisor is its
one fold), About and data. A tool made from one card's content (the
.build file from the Build card, the loot filter add-on from the Search
strings card) is a page of that card instead, so it stays beside what it
is made from and hides with it. A destructive action
(Clear ...) is a secondary button, never the filled primary style.

## 8. Voice and tone (prose and readability)

Rules (sources 10, 11, 12):

1. Plain English, about a 9-year-old reading age. Short words, short
   sentences (dashboard prose <= 20 words a sentence).
2. Sentence case everywhere except uppercase kind tags.
3. Present tense, active voice, subject first: "Quietfox wants Plain Belt".
4. Use the player's words (zone, hideout, level, trade, whisper). Never
   expose internals: "core", "token", "SSE", "tailer", "HTTP 500" in the
   main line. A repo path or a script name is an internal too
   (RUN-NO-DEAD-ENDS, research 0042 R4): a sentence that sends the player
   somewhere names the control and its exact place ("Settings, Checks",
   "Settings, Reading and web data", the Start Menu shortcut), never a
   script, and the words "settings file", "scripts" and ".ps1" stay out
   of player text (tests/test_copy_dead_ends.py). The settings export is
   the "settings backup".
5. Errors say what happened, then what to do. Never blame the user. No
   exclamation marks, no ALL CAPS shouting, no "Oops".
6. Numbers as digits; units with a space ("12 deaths", "3m").
7. Front-load the key word so a truncated line still makes sense.
8. ASCII only (FLEET item 8): "..." not an ellipsis character, "-" not a
   dash, straight quotes.
9. Empty states explain what will appear and when. In the word-budgeted
   Play regions the explanation is one short clause after the empty word
   ("Nothing yet. Trades and events show here.", "none - tips show
   here"; G5 totals ruling, section 4).

Good / bad examples:

| Bad | Good | Why |
|---|---|---|
| token rejected or core stopped | can't reach AshLight - reopen it from the Start Menu | no internals; gives the fix and where |
| Layout unavailable (core stopped?) | Can't load the overlay settings. Is AshLight running? | plain words, a question the user can answer |
| No events yet. | Nothing yet. Zones, level-ups, deaths and whispers show up here as you play. | says what and when |
| --:-- (blank line under it) | Starts when you allow reading Client.txt | an empty timer says when it starts (UX-U9) |
| Session 0:00 before the first update | Session --:-- until the feed is live; then it counts from the game's log opening, like the resumed deaths | a timer never reads shorter than the zone or act timer next to it (UX-NEW-CARDS) |
| Client.txt waiting | waiting for Client.txt | subject-verb order |
| core not running (overlay) | AshLight offline | the user knows "AshLight", not "core" |
| AFK on / AFK off | You're AFK / You're back | natural sentence |
| Error! Could not save!!! | Not saved. Try again. | no shouting, gives the step |
| Trade from Quietfox: Plain Belt for 5 exalted | Quietfox wants Plain Belt - 5 exalted | who, what, price; verb first after the name |

## 9. Natural-language messaging (NLM)

How AshLight turns a log event into words. All event text is produced in
one place, the card and event text package `server/al/text/` (`events.py`:
`summarize`, `trade_card_text`; `itemcheck.py`: `eval_card_text` /
`stat_delta_text`; one module per card) and the overlay formats in
`app/shared/format.js`; no other site invents event wording.

Generation rules:

1. **Deterministic templates, no language model.** Text is built from
   fixed templates and the event's own fields; the same event always gives
   the same words. Nothing is sent off the machine to phrase text.
2. **One event, one sentence**, subject first: `<who> <verb> <what>`.
   The templates live in one copy sheet per text module of
   `server/al/text/` (TEST-COPY-SHEETS); a new or changed template is
   edited in its sheet, never here. The rules of this section bind every
   sheet. The sheets:
   - events: [`docs/design/copy/events.md`](copy/events.md)
   - itemcheck: [`docs/design/copy/itemcheck.md`](copy/itemcheck.md)
   - buildlive: [`docs/design/copy/buildlive.md`](copy/buildlive.md)
   - price: [`docs/design/copy/price.md`](copy/price.md)
   - waystone: [`docs/design/copy/waystone.md`](copy/waystone.md)
   - overlaycard: [`docs/design/copy/overlaycard.md`](copy/overlaycard.md)
   - explain: [`docs/design/copy/explain.md`](copy/explain.md)
   - playernotes: [`docs/design/copy/playernotes.md`](copy/playernotes.md)
   - iteminfo: [`docs/design/copy/iteminfo.md`](copy/iteminfo.md)
   - kindler: [`docs/design/copy/kindler.md`](copy/kindler.md)
3. **Player text is quoted, never rewritten.** Whisper bodies and names
   are shown verbatim (textContent only, never innerHTML), clipped with
   "..." at the line limit.
4. **Missing fields read honestly**: "level unknown", "character unknown",
   "no price set" - never "None", "undefined", "?" or an empty gap.
5. **Overlay register is telegraphic**: drop verbs and articles when a
   line must fit (`Lv 12 | 3 deaths`, `Trade: Quietfox`). The dashboard
   register is the full sentence.
6. **Line limits**: the overlay strip's zone line 28 chars (the " (HO)"
   tag included; it is a strip row, not a card); every card line (trade,
   item check, price, waystone, zone and act moment) 26 chars, the core's
   CARD_LINE (CARD-LINE-LIMIT-FLIP; 34 before, which rendered past the
   236 px text budget at 14 px - the limit drops, never the font size);
   the zone-guide line on HUD line 2 is the guide entry's `short`, at
   most 34 chars, shown as authored or not at all; the key hint is
   `<key>: check an item`, or `Check: <key>` past 26 chars, and no hint
   for a key over 19 chars. On the Play tab every row is one line,
   composed by the core under a character cap that fits the narrowest
   column even with the WCAG 1.4.12 spacing (`server/al/playview.py`,
   `server/al/playcards.py`): context title 38, context and notice rows
   52, event sentence 38, build row 36, item sentence 2 x 36, kept row 42,
   strip sub line 34 (measured in section 4). Only a name can take the
   ellipsis, with the full text in `title` and on the "Full text" page of
   its card on Run or Build and items (list rows there are one line too).
   Under a text-spacing override rows wrap and the page scrolls.
   Dashboard sentences outside Play wrap, never truncate.
   Card copy (CARD-LINE-LIMIT-COPY): every fixed card line is worded to
   fit 26 characters (CARD_LINE, the format.js maxLen defaults, cardparts
   HEAD_MAX; the key hint's HINT_FIT is CARD_LINE). A line built from
   values drops its least needed part instead of clipping: the keep /
   vendor head drops ", Lv <n>", the item check head rounds, then drops
   the number and keeps the slot name (CL-2; only a slot too long beside
   the verdict drops), the price line names the league only when it fits
   and turns "About <amount>" into "~<amount>".
7. **Plurals are correct**: `1 death`, `2 deaths`, `1 level-up`.
8. **Time words are relative on the overlay** (`3m`, `1h05m`) and local
   clock time on the dashboard (`14:05`).
9. **Notifications are passive.** A new event changes text in place; it
   does not pop up, chime or take focus. At most one overlay card is new at
   a time.
10. Every new template gets a unit test of its exact output.
11. Waystone rewards (decision 0039): see
    [`docs/design/copy/waystone.md`](copy/waystone.md). Campaign hints:
    `This zone's boss deals mostly <element> damage. Your build has N% <element> resistance (the cap is
    75%).` (or `(at the cap)`, or `... resistance is unknown.`), `A(n)
    <base> can drop at your level; your build has a(n) <base>.`, `Your
    build's boots have no movement speed. Boots with it help in the
    campaign.`; words `<Element> res N%`, `Boss: <element>`, `Better
    flask`, `Boots: no speed` (15 chars).
12. Log-state sentences and words (RUN-TAIL-HEAL-CORE,
    RUN-UNREADABLE-WORD; review SRW-1, SRW-2). A log-state sentence is a
    status word, so these stay here, not in a copy sheet. Reader reset
    sentences in the event list, by where the reader goes on:
    `Client.txt is back - reading on from where it stopped`, `Client.txt
    was replaced - reading on from where it stopped`, `Client.txt was
    replaced - reading new lines only`, `Client.txt got shorter - reading
    on from where it stopped`, `Client.txt got shorter - reading new
    lines only`. Reader lines: `AshLight restarted its log reader` (no
    trailing period, like every event line), `Client.txt can't be read
    right now - trying again`, `Client.txt can be read again`. The
    unreadable state is one row of `server/al/data/status_words.json`
    (kit `blocked`): dashboard bar `can't read Client.txt`, overlay status
    slot `can't read log` (15 characters at most beside the numbers), and
    the Reading row of the Checks tool `Client.txt is there but can't be
    read. AshLight keeps trying.` with the fix `Close any program that has
    Client.txt open, or check that you can open the file yourself.` It
    shows only after the opt-in and is named before the quiet-log state.
13. Item check card words (TC-CARD-PARTS; review TCP-8). Mark words: the
    word that pairs the verdict mark is one of `Upgrade`, `Sidegrade`,
    `Downgrade`, `Not checked`, `Risky`, `No risky mods`; a card part that
    needs a new word adds it here first. Tones: the mark's tone, the
    overlay card's verdict edge, is one of `cardparts.TONES`: `upgrade`,
    `sidegrade`, `downgrade`, `risky`, `note`, `""` (no edge); a part's
    new tone is honoured only together with a new word, never colour
    alone. Part keys: a part's `words()` changes only `cardparts.WORD_KEYS`:
    `notes`, `word`, `tone`, `head`, `answers`, `calc`; every other key
    is put back. `tests/test_tc_cardparts.py` keeps these three lists
    equal to the module.

## 10. Overlay rules

- Window: separate, transparent, always-on-top, click-through,
  non-focusable (CLAUDE.md). It exists only while the desktop client runs
  and hides while the game looks closed (decision 0041; decision 0029
  amendment 2026-11-17). Base size 280 x 176 DIP at scale 1.0
  (`app/shared/layout.js` BASE); HUD plates max-width 258px on the
  content box, so a plate measures 258 px inside and 280 px outside
  (padding 10 + 10, border 1 + 1; measured by OVL-CONTRAST-PIXELS,
  HUD-PLATE-WIDTH-DOC); HUD line 2 keeps the 236 px text budget of plan
  03 section 5.1, which `tests/test_overlay_pixels.py` holds.
- Content cap (TD-17, OVL-CARD-SLOT): 2 HUD lines + one 3-line card.
  Nothing else; never two cards at once. The one card slot has these
  holders, first match (section 7.2; `server/al/overlayview.py`
  CARD_HOLDERS): the press card (item check, price, or the merged card of
  one press; decision 0016: the price-only card when no build is
  loaded; "Copy the item first" for an empty clipboard), the Settings
  sample card (10 s, on its button only), the newest open trade card
  ("+N more" for the rest), a zone or act card (12 s, only into a free
  slot, never queued), the key hint line. When a holder leaves, the next
  one due comes back by itself. The card's near edge is anchored 62px
  from the window's anchored edge in every state (the 2-line HUD, 55.6px,
  plus 6), so nothing moves when line 2 changes.
- Card time (TD-18, OVL-TD18-CARD-TIME): the press card shows for 20 s by
  default; the setting "Keep a card for" (Settings > Overlay) picks 20,
  60 or 200 s (layout `card_s`; the default is never stored). The zone
  and act cards keep 12 s and the sample card 10 s; the trade card stays
  while its request is open; the key hint has no expiry while it is due.
- Plate (TD-05, OVL-TD05-PLATE): `--al-plate` (86 percent by default,
  `--al-plate-a` 0.80 to 1.0, set by the "Background" slider) with a 1px
  kit-border edge and the halo `0 0 2px #000, 0 0 2px #000, 0 1px 2px
  #000`, no stroke (`--al-halo`; source 4: outlines and shadows separate
  text from busy scenes). Text is opaque. In high-contrast mode
  (`prefers-contrast: more`) the plate is opaque and secondary text takes
  the text colour (audit 0004 U3). In Windows forced colours the plate is
  opaque Canvas, text and edges take the system theme (the trade, upgrade
  and risky-waystone edges use Highlight; elsewhere the risky waystone
  edge is status-warn, audit 0004 U24), the page root opts out so the
  window stays transparent, and contrast is the theme's own, not measured
  here; the Background slider has no effect there (audit 0004 U8).
- Opacity (TD-05): overlay text pairs >= 7:1 at the default plate and
  >= 5.5:1 at the alpha floor over a white scene, card edges >= 3:1
  (5.2). Decorative transparency comes from the plate, never from fading
  the text; the overlay has no page opacity.
- Size: two sizes, 16px HUD and 14px card; >= 12px after zoom (section 3).
- No flashing, ever (WCAG 2.3.1; the overlay is in peripheral vision during
  combat). No animation, no transition, no blinking caret, no colour
  cycling. A change is a single repaint.
- Repaint budget: only when a visible string changes; the zone timer
  repaints at most once a minute (`render_gate.js`, `test_budgets.py`).
  The row-1 timer is the time in the open map while the player stands in
  that map (an idle log freezes it there), otherwise the time in this zone
  instance (`render_gate.js timerSeconds`; UTIL-MAPRUN-OVL): same text,
  same once-a-minute repaint, no marker. A card's leaving and a quiet
  guide line coming back share the page's one timer.
- Glance time target: each line readable in one fixation (< 1 s): <= 5
  words, number or name first, no wrapping (`nowrap` + ellipsis).
- Glance rule (F-095, TD-17): a card's first line starts with its answer,
  inside the 26-character clip: the verdict word on an item check card
  (one of the section 9 rule 13 mark words: Upgrade, Sidegrade, Downgrade,
  Not checked, Risky, No risky mods), the price word on
  a price card (`Price:`), the buyer on a trade card (`Trade: <buyer>`),
  or one of the fixed status words of a card that has no verdict (No
  build loaded, Not an item, Can't compare this, Build loaded, Build not
  loaded, Can't check this item, Waystone unidentified, Copy the item
  first). A merged card starts with its item check head. A zone or act
  card and the key hint start with their subject (the zone's short, `<act>
  done`, the key).
- Every card that leaves the overlay by itself has a dashboard twin that
  stays: the item check card and the price card (and the merged card) stay
  in the item check (region I on Play; `#eval-result`, `#price-result` on
  Build and items), the trade card in feed T (`#play-t`) while it is open
  and in Run > Recent (`#events`) after it closes, the zone card in the
  zone guide and the act card in the Acts card. `tests/test_glance_rules.py`
  walks every card kind the core can publish and fails when a kind has no
  twin; a card holder declares its twin (or a reason it needs none, as
  the sample card and the key hint do) where it is defined.
- Placement: corners only, user-chosen; default top-right. In PoE2 that
  corner holds the game's corner map (with the quest tracker below it),
  so the 2-line HUD covers its top edge and a card covers more for its
  card time; every other region costs more in a fight (top-left: buffs
  and party frames; top-center: the boss life bar; bottom: globes,
  flasks, skill bar, XP bar). The player moves it in one change on the
  dashboard (UX-DPI ruling 2026-11-17; reverses if play shows the corner
  map is routinely needed and covered, or the HUD grows past 2 lines).
  The TD-17 holders, the 20 / 60 / 200 s card time and the opt-in guide
  line keep the HUD at 2 lines, so the ruling is not reversed (audit 0004
  U11 amendment 2026-11-22).
- Size follows the monitor (TD-06, OVL-TD06-AUTOSCALE): the window is in
  DIPs, so Windows scaling applies by itself, and on a monitor taller
  than 1200 DIPs `layout.js autoScale` grows the HUD by DIP height / 1200
  (1440 DIPs give 1.2; at most 2x, in 0.05 steps) so text is never
  physically smaller than at 1200 DIPs. User size times that factor is
  capped at 2.5, and the window never exceeds the work area; the decision
  0002 overlay budgets were re-run with the change.
- Display mode: Windowed Fullscreen only (CLAUDE.md).
- About text carries the GGG disclaimer (screen-reader visible).

## 11. Audit checklist

Every UI or copy change is reviewed against this list (by the
`design-reviewer` agent, or by hand). IDs are stable; add new ones at the
end of a group.

Colour and contrast
- C1: every text pair is in the 5.2 block or measured in the review, and is
  >= 4.5:1 (>= 3:1 only for 18.66px bold / 24px regular and up).
- C2: control boundaries and focus rings >= 3:1 against their background.
- C3: no literal hex / rgb in component CSS; only `var(--fk-*)` /
  `var(--al-*)` (token blocks excepted).
- C4: no state or event kind carried by colour alone (glyph, word or shape
  present).
- C5: red reserved for failures and deaths; no red-vs-green-only pairs.
- C6: light and dark both checked (dashboard); overlay checked over a white
  scene.
- C7: dashboard text sizes come only from the six type tokens (section 3);
  overlay sizes only from the two overlay tokens (16px and 14px).

Prose and messaging
- P1: plain words, sentence case, present tense, subject first.
- P2: no internals (core, token, SSE, tailer, HTTP codes, repo paths,
  script names) in a main line; a pointer names the control and its place.
- P3: errors say what happened and what to do; no blame, no "!".
- P4: event text comes only from `summarize` / `format.js` templates, each
  with an exact-output test.
- P5: missing values read honestly ("unknown", "no price set").
- P6: player text verbatim via textContent; clipped with ASCII "...".
- P7: plurals and units correct; ASCII only.
- P8: empty states say what will appear.

Natural use and context
- N1: no new required click during play; settings save on change.
- N2: no alert / confirm / prompt / modal / toast / focus steal.
- N3: any mid-game action is a hotkey; clipboard / screen read only on a
  hotkey press.
- N4: information appears in the right context (7.2); overlay additions
  displace nothing and stay within the content cap.
- N5: stale items expire by themselves with a stated time, or the review
  records why not.
- N6: status changes announced politely (`role="status"` / `aria-live
  ="polite"`), never assertively, each in at most 12 words. Live regions:
  at most 3 in the Play panel plus the bar's reading word (the item check
  verdict of region I, the feed's trade status, the notice) and at most 6 in the page
  (`tests/test_a11y.py`), one kept free for an urgent state. Per-press
  budget (F-151, research 0044 R6): one item-check press speaks at most
  three times, all polite: the item check (the verdict of region I on
  Play, or the Item check card on Build and items), the price, and at
  most one header line ("New on Play: <what>." or "Showing Play.
  <What>."); a staged update of the same press is not announced again.
  Silent by design, reached by their headings: the strip G, context
  region C and the zone guide, the build line B (it changes only when the
  character or build changes and is not urgent), the kept checks U, the
  last-session card (`#summarybox`) and the Settings status lines (plain
  text the control points at; a failed save also goes to the header's
  polite line).
- N7: in the full and compact classes at default text settings, no Play
  region scrolls, moves or changes size between states (section 4).
- N8: every item that leaves by itself has a twin that stays (section 10).

Overlay
- O1: no animation, transition, keyframes, blink or flash.
- O2: repaint only on a visible change; budgets test green.
- O3: smallest rendered text >= 12px at the minimum scale.
- O4: each line within the section 9 rule 6 limits, nowrap + ellipsis, readable in one glance.
- O5: retired by O8 (TD-05, OVL-TD05-PLATE; it was "effective opacity
  keeps overlay text >= 4.5:1 over white").
- O6: window stays click-through and non-focusable; no input is sent.
- O7: a press or trade card starts with its answer (verdict word, price
  word or buyer); a status card starts with its status words; a zone or
  act card or the key hint starts with its subject.
- O8: overlay text pairs >= 7:1 at the default plate and >= 5.5:1 at the
  alpha floor over white; card edges >= 3:1 (5.2).

Structure and access (dashboard)
- S1: headings in order; landmarks (header, main, footer) present.
- S2: every control has a visible label or aria-label; hit target >= 24px.
- S3: works at 320px width with no horizontal scroll.
- S4: keyboard reachable with a visible focus ring.
- S5: GGG disclaimer present in the dashboard footer and overlay About.
- S6: the focus ring is drawn inside the element and is never clipped
  (section 4).

## 12. Sources

All accessed 2026-11-16.

1. W3C, Understanding WCAG 2.2 SC 1.4.3 Contrast (Minimum):
   https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
2. W3C, Understanding WCAG 2.2 SC 1.4.11 Non-text Contrast:
   https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast
3. W3C, Understanding WCAG 2.2 SC 2.3.1 Three Flashes or Below Threshold:
   https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
4. Game Accessibility Guidelines, "Provide high contrast between text / UI
   and background":
   https://gameaccessibilityguidelines.com/provide-high-contrast-between-text-ui-and-background
5. Okabe and Ito, Color Universal Design palette (reference values):
   https://siegal.bio.nyu.edu/color-palette/ ; colour-alone caveat:
   https://ctan.ceremade.dauphine.fr/macros/latex/contrib/colorblind/colorblind_doc.pdf
6. Henry Ford Health, "Why men are more likely to be colorblind" (1 in 12
   men, 1 in 200 women):
   https://www.henryford.com/blog/2024/10/why-men-are-more-likely-to-be-colorblind
7. News-Medical, "Color Blindness Prevalence":
   https://www.news-medical.net/health/Color-Blindness-Prevalence.aspx
8. Microsoft, Xbox Accessibility Guideline 102: Contrast (contrast during
   active gameplay; measure against the lowest-contrast part of a busy
   background): https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102
   and XAG 101 Text display:
   https://learn.microsoft.com/da-dk/gaming/accessibility/xbox-accessibility-guidelines/101
9. Nielsen Norman Group, Progressive Disclosure:
   https://www.nngroup.com/videos/progressive-disclosure/
10. GOV.UK, Writing for GOV.UK (plain English, reading age 9):
    https://www.gov.uk/guidance/content-design/writing-for-gov-uk
11. GOV.UK publishing guidance, Clear language:
    https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/
12. Microsoft, Error message guidelines (what happened, why, how to fix; no
    blame): https://learn.microsoft.com/en-us/windows/win32/debug/error-message-guidelines
13. W3C, Understanding WCAG 2.2 SC 2.5.8 Target Size (Minimum):
    https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
