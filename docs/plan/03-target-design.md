# 03 - Target design

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).

Status: final

Scope: the target look and behaviour of the dashboard (Play tab, tab set) and the overlay, the
type scale, the colour tokens, and the ordered steps (TD-nn) that get there. It is the judged
result of a three-design panel, corrected against the rulings and findings of
docs/plan/findings.json, then corrected again after the design review recorded in the last
section. The Game ToS floor (CLAUDE.md) is untouched and read strictly.

Reading the numbers: px figures are at scale step 1 (root 16 px) unless marked. [M] = measured
(evidence pack, notes 0040 / 0041 / 0043). [C] = computed for this section (WCAG 2.2 contrast
formula, layout arithmetic, text widths from the Segoe UI font metrics; scripts kept in
`<sidecar>\Scratch\up-plan\td_check.py` and `td_width.py`). [D] = design budget from the fixed
line boxes of section 6 and the character budgets of section 3.4; TD-01 must confirm every [D]
figure with real long strings before it is quoted as measured.

## 1. Decision

Base: design A, the fixed cockpit. Three designs were written independently
(`<sidecar>\Scratch\up-plan\design-A.md`, `design-B.md`, `design-C.md`) and scored by three judges.

| Judge (lens) | A fixed cockpit | B phase-adaptive | C overlay-first | Winner |
|---|---|---|---|---|
| J1 the player in play | 84 | 77 | 62 | A |
| J2 accessibility and legibility | 75 | 70 | 78 | C |
| J3 feasibility and safety | 79 | 72 | 55 | A |
| Total | 238 | 219 | 195 | A |

The workflow summary showed 250 for C: judge J3's entry for C came in two parts and its 55 was
added twice. The corrected total is 195, so A ranks first by total and by two of three judges.

Why A: its tracks are fixed and do not depend on content, so "no scroll" and "same place" hold by
construction and are cheap to test; one rem arithmetic proves both reference sizes; the larger
window buys larger text, not more words; the build state is always visible; the overlay window
stays 280 x 176, so the decision 0002 budgets are not reopened.

Flaws the judges found in A, and the fix used here:
- A claimed the guide's `line` field is at most 34 characters. It is composed up to 120
  (`server/al/zoneguide.py` MAX_LINE). Fixed by graft G-01 (an authored `short` field).
- A added a third HUD row. That is not adopted (findings 0040-X5; decision 0014; design 0001
  section 10; the top-right placement ruling reverses "if the HUD grows past 2 lines"). Fixed by
  graft G-02: the HUD stays at 2 lines.
- A dropped to a scrolling page under 1200 x 760. Fixed by graft G-08 (a compact step).
- A's width rule (1280 s) excluded the client's own 1264 px default. Fixed in section 3.1: the
  threshold is the cockpit minimum, 75 em.
Not taken as base: C (its CHECK slot sums exceed its own budgets, 3 HUD lines plus a queue line,
a 30 percent larger window not measured against decision 0002); B (band heights contradict its
own row metrics, a phase change swaps a whole column, compare rows vanish while being read).

Grafts (id, origin, idea):
- G-01 (C): a zone-guide `short` field, authored, at most 34 characters, AshLight's own words;
  empty when unsure; a missing `short` shows nothing, never a clipped sentence. Own step (TD-08).
- G-02 (B): 2 HUD lines at most; line 2 is picked by one priority order (section 5.2).
- G-03 (B, changed by the design review): the guide line on HUD line 2 is an opt-in. Setting
  On entry (default, for everyone) / Always / Never; the display count is not used, so nothing
  changes when a monitor is plugged in.
- G-04 (C): one-line 32 px trade rows. Taken further: the feed has 5 rows, so all 5 server
  trade slots (`state.py` TRADE_REQUESTS = 5) show on Play and no trade goes to "+N more".
- G-05 (B, with C's condition): `autoScale` reference 1200 DIP (F-162), and the decision 0002
  overlay budgets re-run in the same step (TD-06).
- G-06 (B): a Theme setting, Dark (default) / Follow Windows / Light (F-086). A's "forced dark,
  no choice" is dropped.
- G-07 (C): a staged item press, first card stage under 0.5 s (F-059, note 0048 R3).
- G-08 (C): a compact step between 1024 x 700 and the full cockpit instead of the scrolling
  fallback, with a written eviction order (section 3.8). Per judge J3 it is a table, not
  CSS-only. After the design review the compact class exists at every scale step (3.1).
- G-09 (B): slot priority and eviction are pure functions with an exhaustive table test
  (TD-02), next to A's browser captures (TD-01).
- G-10 (B): every height is labelled [M], [C] or [D]; TD-01 confirms the [D] figures.
- G-11 (A, kept and tightened per J2): rem scale steps chosen by width AND height; the root is
  a percentage (100% x s) and the queries are in em, so the user's default font size applies;
  fixed line boxes per type step; the 1 px borders are counted in every vertical sum.
- G-12 (A): an inset 3 px focus ring (outline-offset -3 px) that no region can clip.
- G-13 (B): on the automatic return to Play, focus moves to the Play tab only when it sat on the
  tab row and the 10 s grace ran out with no key press or click, and the move is announced
  (section 9); a card, trade or notice never moves focus (note 0044 F9, F-096).
- G-14 (B): overlay card time 20 s (default) / 60 s / 200 s, beside the untimed Play twin.
- G-15 (A): a browser accessibility test (focus ring box, forced-colours tab, target sizes,
  live-region count) plus a text-spacing run (F-121).
- G-16 (C): under zoom or a text-spacing override the page scrolls; nothing is clipped and no
  nested scroll box appears (section 3.9).
- G-17 (C): the control edge is #737c88 (4.05:1 on a card) instead of A's #6b7480 (3.61:1).
- G-18 (C): every "fix" line names an in-app control, never a file or a shell command.
- G-19 (C): any overlay content change records its effect on decision 0014 and on the placement
  ruling in the decision record (TD-23).

Corrections from docs/plan/findings.json, which outrank the panel:
- Four tabs, not the panel's three: F-067 fixes Play, Build and items, Run, Settings; the
  three-tab set is not adopted (0043-X9). It is offered only as option O-4.
- No third HUD line and no second card (0040-X5); zone and act moment cards use the one card
  slot (F-119).
- In-play strip text (tile labels, sub lines, status words) uses the 20 px step (F-053).
- Dark by default with a choice (F-086); the setup card has 4 rows (F-069); "I wear this"
  (F-070) and the keep-or-vendor verdict with no build (F-060) are part of the item card.
- The item key stays Alt+Shift+E until the operator's two checks (Q-09, F-054): option O-3.
- Reading Path of Building's builds folder (Q-01) and a browser file pick for builds (Q-02,
  F-058) are outside the current floor text: options O-1 and O-2, not designed in.

## 2. Principles

1. Same place, always: 7 Play regions with fixed rectangles. A region changes its words, never
   its position or size, in every state.
2. Fit by construction: tracks are fixed and every string is capped where it is composed (rows,
   characters). No state can add height; clipping is a guard, never the mechanism.
3. One answer per region, in its first 6 words, at the 20 px step or larger.
4. Variable content competes in fixed slots by a written priority; the loser goes to a twin that
   stays (Run or Build and items), never to a scroll.
5. Play needs no control: every control on it is optional. Switches live in Settings.
6. Dark, still, quiet: dark unless chosen, 0 animations, 0 sounds. Urgency is region, glyph and
   word; colour marks exceptions only.
7. The overlay is a 2-line HUD plus one card; everything else is the dashboard's job.
8. The floor is the design limit: one manual press per read, nothing sent to the game.

## 3. Play tab

### 3.1 Size classes and the scale rule

Root font size = 100% x s (the viewer's default font size, 16 px unless changed, times the scale
step s). The step and the class are chosen by media queries in em on width AND height, so a
larger default font moves the thresholds with it.

Rule: s is the largest of 1, 1.25, 1.5, 2 whose compact cockpit fits the viewport (at least
64em x 43.75em, times s). The class is full when the viewport is also at least 75em x 47.5em
times s, else compact. Under 64em x 43.75em the class is flow (s = 1).

| s | Root | compact from (at a 16 px default) | full from (at a 16 px default) |
|---|---|---|---|
| 1 | 16 px | 64em x 43.75em (1024 x 700) | 75em x 47.5em (1200 x 760) |
| 1.25 | 20 px | 80em x 54.6875em (1280 x 875) | 93.75em x 59.375em (1500 x 950) |
| 1.5 | 24 px | 96em x 65.625em (1536 x 1050) | 112.5em x 71.25em (1800 x 1140) |
| 2 | 32 px | 128em x 87.5em (2048 x 1400) | 150em x 95em (2400 x 1520) |

- 1280x760: full, s = 1. 1264x821 (the client's default content size [M]): full, s = 1, 61 px
  of extra height. 1024x700: compact, s = 1.
- 1920x950: full, s = 1.25, root 20 px. 950 / 20 = 47.5 rem: the vertical budget in rem is
  identical to 1280x760, so one arithmetic proves both.
- A maximised browser on a 1080p display has a viewport of about 1920 x 875 to 955, depending
  on its toolbars. From 875 px it is compact at s = 1.25 and from 950 px full at s = 1.25: the
  text sizes are the same on both sides of 950 px and only the three evictions of 3.8 change.
  The root no longer drops from 20 px to 16 px when a bookmarks bar appears.
- 1920x1080 (full screen): compact, s = 1.5 (1536 x 1050), 30 px extra. 2560x1440 (full
  screen): compact, s = 2, 40 px extra; a maximised browser there (about 2560 x 1300): full,
  s = 1.5, 160 px extra.
- Browser windows under 700 px tall are in the flow class and Play scrolls there. That hits a
  maximised browser on a 1366x768 laptop (viewport about 1366 x 650). The desktop client's own
  window is not affected (1264 x 821 by default; on that laptop full screen, 1366 x 768, is
  compact). 1366 x 650 is a tested, accepted flow state (G1), not a play state.
- Extra height goes only to regions C and I (their tracks are `minmax(track, 1fr)`); line caps
  do not change, so nothing moves relative to its region top. Extra width goes to the columns
  (7fr / 5fr); `main` is capped at 100 rem.
- What 1920x950 buys is reading distance, not words: in-play text 25 px, verdict 35 px,
  numbers 40 px (section 6).
- The 820 px short-window query of today is deleted (F-086 asked for a threshold that covers the
  default window; the scale rule is that threshold).

### 3.2 Frame arithmetic

Chrome at s = 1: bar 52 + main padding 12 + 12 + footer 32 = 108 px [D] (today 106 [M]).

    full, 1280x760, s = 1   left column                right column
    strip G     100         G spans both columns
    gap           8
    body        544         C 228 + 8 + T 204          B 68 + 8 + I 360
                            + 8 + N 96 = 544           + 8 + U 100 = 544
    grid        652         100 + 8 + 544 = 652        100 + 8 + 544 = 652
    + chrome    108         652 + 108 = 760            overflow 0 px

    full, 1920x950, s = 1.25 (every track, gap and chrome figure x 1.25)
    chrome      135         bar 65 + 15 + 15 + footer 40
    strip G     125
    gap          10
    body        680         C 285 + 10 + T 255         B 85 + 10 + I 450
                            + 10 + N 120 = 680         + 10 + U 125 = 680
    grid        815         125 + 10 + 680 = 815       815 + 135 = 950, overflow 0 px

    compact, 1024x700, s = 1
    strip G     100
    gap           8
    body        484         C 212 + 8 + T 204          B 68 + 8 + I 348
                            + 8 + N 52 = 484           + 8 + U 52 = 484
    grid        592         100 + 8 + 484 = 592        592 + 108 = 700, overflow 0 px

    compact, 1920x875, s = 1.25 (the compact figures x 1.25)
    strip G     125
    gap          10
    body        605         C 265 + 10 + T 255         B 85 + 10 + I 435
                            + 10 + N 65 = 605          + 10 + U 65 = 605
    grid        740         125 + 10 + 605 = 740       740 + 135 = 875, overflow 0 px

Rounding at s = 1.25: tracks, gaps and chrome are multiples of 4 px at s = 1, so they stay
whole. Line boxes do not all stay whole (18, 22 and 26 px become 22.5, 27.5 and 32.5 px); the
browser lays them out in sub-pixel units and paints to the device pixel. G4 therefore measures
slack after rounding and asks for at least 3 px at s = 1.25 (3.7 gives the figures).

Today [M]: state c puts 1034 px of content into a 654 px column at 1280x760 (380 px over on the
left, 321 px on the right); 124 / 117 px over at 1920x950; idle is 541 / 311 px over.

Widths [C]: at s = 1 main padding 16 + 16, content 1248 px, column gap 12, columns 7fr / 5fr =
721 / 515 px. Strip cells: Zone 708 (flex) | Level 176 | Deaths 152 | Session 176, 3 gaps of 12.
At 1200 px wide: columns 674 / 482, zone cell 628. At 1920 (s = 1.25): padding 20 + 20, content
1880, gap 15, columns 1088 / 777, cells 1205 | 220 | 190 | 220. Compact at 1024: columns
572 / 408, zone cell 452.

### 3.3 Diagram (1280x760)

    +------------------------------------------------------------------------------------------+
    | BAR 52   AshLight  [Play] [Build and items] [Run] [Settings]   Emberdemo  [>] reading    |
    +------------------------------------------------------------------------------------------+
    | G 100  Zone                               | Level           | Deaths      | Session      |
    |        Clearfell                  12:41   | 4               | 1           | 0:42         |
    |        Act 1 - area level 4               | 2 lv under      | 1 this zone | 2 level-ups  |
    +----------------------------------------------------+-------------------------------------+
    | C 228  CONTEXT (one of 7 modes)                    | B 68  BUILD LINE                    |
    |        title + 7 rows + 1 facts row                |       state word, name / fix line   |
    |                                                    +-------------------------------------+
    |                                                    | I 360  ITEM CHECK                   |
    +----------------------------------------------------+   VERDICT 28 px + item name         |
    | T 204  FEED: head + 5 one-line rows                |   sentence (2 rows)                 |
    |        open trades first (all 5), then the latest  |   compare block (label + 5 rows)    |
    |        death / level-up / zone                     |   price row                         |
    |                                                    |   Trade search | Upgrade search     |
    +----------------------------------------------------+   Details | I wear this             |
    | N 96   NOTICE: one notice (head + 2 rows,          +-------------------------------------+
    |        1 action), "+2 more"                        | U 100  KEPT CHECKS: label + 3 rows  |
    +----------------------------------------------------+-------------------------------------+
    | FOOT 32  This product isn't affiliated with or endorsed by Grinding Gear Games in any way.|
    +------------------------------------------------------------------------------------------+

### 3.4 Regions: content, line arithmetic, caps (s = 1)

Line boxes are fixed rem heights (section 6): meta 20, body 22, title 26, glance 32, hero 36.
Region heights therefore do not depend on font metrics or on string length. In the compact and
full classes at default text settings every row is one line with `nowrap` and an ellipsis as
the last guard; composed rows stay under the character budgets at the end of this section, so
only a name (zone, item, buyer, build) can take the ellipsis, and its full text is in `title`
and in the row's twin. Under a text-spacing override and in the flow class rows wrap instead
(3.9). Each sum counts the region's 1 px border twice.

G strip, track 100 [D]: border 2 + padding 4 + 4 + label row 26 + value row 36 + sub row 26
= 98; slack 2.
- Zone: label "Zone" (20 px, muted); value = zone name 28 px / 700, one line, plus the zone or
  map timer at 20 px / 600 right-aligned in the same row (never clipped); sub (20 px) = act,
  area level, tags (hideout, "frozen 14:02", AFK, DND).
- Level: number 32 px / 700; sub = "2 lv under" with its glyph while under-levelled (the same
  words as the overlay status word, design 0001 section 7.2), else the class. Deaths: number;
  sub "1 this zone". Session: timer; sub "2 level-ups" or "4 maps, 5/h".
- The character name sits in the bar (16 px), not in a tile: at 20 px it does not fit a tile
  (note 0043, fit case b). Pace line and character picker: Run tab. Cap 20 words.

C context, track 228 [D]: border 2 + padding 12 + 12 + title 26 + 7 body rows 154 + facts row
20 = 226; slack 2. Exactly one mode, first match wins:
1. setup - no consent yet (F-069): title "Set up AshLight" 26; row "Allow reading Client.txt"
   22 + the log path 20 + button row 36 (the only filled accent button in the app); 3 more rows
   with state glyphs (your build, prices, overlay) 66; one promise line 20. 190 of 202.
2. error - reading is not possible (Client.txt missing or unreadable, AshLight not answering):
   what is wrong (2 rows), what AshLight is doing or what to do (3 rows), button "Open Checks".
   172 of 202.
3. idle - `game_idle` (decision 0029): "Last session", 6 label: value rows, an ended-at facts
   row. 178 of 202.
4. map - in a map, or in the hideout after a map this game run (F-068): map name, level; this
   map's time and deaths; maps this session, per hour, average; last waystone verdict; in the
   hideout one line for the map just closed and, with a build, the search string row. 156 of 202.
5. town - a campaign town, or the hideout before any map: the vendor search string by a plain
   name with Copy (control row 32, F-124; only with a build), then up to 4 guide rows. 166 of 202.
6. guide - a campaign zone with a guide entry (one guide file, F-122): the objective is the
   title row (20 px / 600); then up to 7 rows: bonus, boss and resist hint, flask / boots hint,
   layout (2), next zone and waypoint, "your note" (F-186, 1 row); facts row (level advice).
   200 of 202.
7. none - "No zone yet" (2 rows), or the zone name alone in an unknown area.
- Caps: 52 words; the title at most 38 characters and each body row at most 52 characters,
  composed (word-wrapped) at the source (character budgets below); a guide entry that needs
  more than 7 rows of 52 characters fails a data test.

T feed, track 204 [D]: border 2 + padding 6 + 6 + head 26 + 5 rows x 32 = 200; slack 4.
- 5 fixed one-line row slots (32 px each; text line box 26).
- Trade row: a 4 px accent edge, the tag "Trade" (14 px / 600), then "<buyer> wants <item> -
  <price>" at 20 px (buyer 600); right-aligned at 16 px: stash tab, position, age, then the
  row's own "Dismiss" button (14 px text, 24 px tall, about 60 px wide). The item name takes
  the ellipsis. A repeated whisper refreshes its row (F-120).
- Event row (16 px): tag (Death, Level, Zone) + the sentence (at most 38 characters) + local
  time.
- For 60 s after arrival the right-aligned segment starts with the word "new" ("new, 2m";
  "new, 14:02"). The row text itself keeps its "<who> <verb> <what>" template.
- Head: "Trades 5" or "Recent", plus "Dismiss all" (24 px tall) while 2 or more trades are
  open.
- Shown on Play: open trade requests, the latest death, the latest level-up, the latest zone
  change. Not shown on Play, kept in Run > Recent: whispers that are not trade requests,
  trade accepted / cancelled lines, party joins and leaves, older events. AFK and DND are tags
  on the Zone sub line, not rows.
- Cap 50 words.

N notice, track 96 [D]: border 2 + padding 8 + 8 + head row 32 + 2 body rows 44 = 94; slack 2.
- One notice. Head: glyph + state word at 20 px / 600 (line box 26 in the 32 px head row),
  then the short title (16 px / 600, at most 20 characters), at most 1 action button (32 px,
  label at most 12 characters) right-aligned in the head row. The state word with its glyph is
  at most 12 characters. Body rows at most 52 characters. "+2 more" is a text count;
  every queued notice also lives in Settings (Checks) or on its own card. Cap 22 words.

B build line, track 68 [D]: border 2 + padding 8 + 8 + row 26 + row 22 = 66; slack 2.
- Row 1: state glyph + word at 20 px / 600 ("[+] Build fits", "[?] Old build", "[?] Wrong
  class", "[ ] No build") + build name and level (16 px). "Old build" is AshLight's word; the
  kit state word `stale` (red, a failure) is not used for it. Row 2 (16 px, muted, at most 36
  characters): source and age, DPS / EHP when the calc is on; or the fix in one line, naming
  the press of F-042.
- The build alert is a STATE of this region, not a card in a queue: it can never push
  anything. One optional button "Paste a build" (24 px, row 1) only while no build is loaded
  (F-041); it shows Build and items and focuses the paste box. Cap 16 words.

I item check, track 360 [D]: border 2 + padding 12 + 12 + head 32 + 4 + sentence 44 + 8 +
compare (label 20 + 5 rows 110) + 8 + price row 26 + links row 28 + 8 + action row 28 = 342;
slack 18.
- Head: verdict word at 28 px / 700 with its glyph ("[+] Upgrade", "[-] Sidegrade",
  "[-] Downgrade", "[?] Risky", "[-] Not an item"), then the item name at 20 px, ellipsis.
- Sentence: 2 rows (at most 64 characters, wrapped at 36), starts with the reason; carries the
  build caveat while B is not "fits"
  (F-043); names the missing input instead of guessing; with no build it is the keep-or-vendor
  verdict (F-060) or the comparison with the worn item (F-070).
- Compare: ONE slot (the better one; the label says "vs <worn item> (+1 other slot)"), 5 rows.
  A waystone puts its reward totals in rows 1-2.
- Price row (20 px value, 14 px source and age), or the reason there is none ("web data is
  off").
- Links: at most 2 (trade search, upgrade search), 28 px; they open the player's browser.
- Actions: "Details" (shows Build and items > Last item: every slot, calc line, rolls, price
  and points, the time of the check) and "I wear this" (F-070). 28 px.
- Staged (F-059): the weights verdict fills first (under 0.5 s), then the Path of Building
  rows, then the per-mod rows. The rows are reserved, so nothing moves while it fills.
- The card stays until the next check (the twin of the overlay's timed card). Empty: 3 rows
  that teach the press with the real bound keys (F-026). Cap 60 words.

U kept checks, track 100 [D]: border 2 + padding 8 + 8 + label 20 + 3 rows x 20 = 98; slack 2.
- The 3 best items checked this session against the CURRENT build (decision 0045 re-score;
  memory only, Q-26 b), best first: glyph + word, gain, item, slot, time (14 px, at most 42
  characters; the item name takes the ellipsis). A build or weight change re-orders it by
  itself. Empty: one muted line. Cap 24 words. U is a review list (lean-in text): its status
  words stay at 14 px; the same verdict was shown at 28 px in I when the item was checked.

Bar, 52: mark and name; the 4 tabs (16 px); the character name and class (16 px, muted); one
status word, "[>] reading" (20 px; glyph and word from the state table of design 0001
section 6, where reading Client.txt is the kit state running; the worse of the reading state
and the feed state, from the one status table of F-131; neutral colour while ok, F-159). The
status word is the visible reading indicator of the ToS floor: it is on every tab in every
state, and it is a button (32 px tall) that shows Settings > Reading and web data with focus
on "Stop reading Client.txt", so the opt-in is revoked in 2 clicks from anywhere. The
"New on Play: <what>." line of design 0001 section 4 stays a polite live region but is
visually hidden (no box, 0 px of the 52 px bar); its visible twin is the count on the Play tab.
Footer, 32: the disclaimer sentence (13 px, text colour) and the trademark sentence (13 px,
muted) on one row. The two footer folds move to Settings > About and data, open: what AshLight
does and never does, and the full game data credits (decision 0009). A one-line credit stays
on every card that shows the credited data: the facts row of Run > Acts (zone levels from the
game data snapshot), the facts row of Build and items > Prices and the source text of Play
I's price row (poe.ninja).

Character budgets [D] (TD-07 composes under them; TD-01 measures them with real strings). A
composed row must fit its region at the narrowest cockpit column (compact at 1024 px: left
572 px, right 408 px, minus border and padding) even under the WCAG 1.4.12 override
(letter-spacing 0.12em, word-spacing 0.16em with one space per 6 characters). Budget per
character: 0.5em at weight 400 and 0.54em at weight 600, plus 0.147em for the override. Font
metrics check [C]: 52 characters of body text at 16 px measure 349 px and 477 px with the
override; 60 characters measure 553 px with it and 72 characters 668 px, so the draft's 72
did not fit the 546 px compact column or the 648 px column of a 1200 px window.

| Row | Size / weight | Narrowest inner width | Budget per char | Cap | Cap x budget |
|---|---|---|---|---|---|
| C title | 20 / 600 | 546 | 13.73 | 38 | 522 |
| C body row, N body row | 16 / 400 | 546 (N 554) | 10.35 | 52 | 538 |
| T event sentence (beside the tag and "new, 14:02") | 16 / 400 | 397 | 10.35 | 38 | 393 |
| B row 2 | 16 / 400 | 390 | 10.35 | 36 | 372 |
| I sentence, per row (2 rows, 64 in all) | 16 / 400 | 382 | 10.35 | 36 | 372 |
| U row | 14 / 400 | 398 | 9.05 | 42 | 380 |
| N head: word 12 (20 / 600) + title 20 (16 / 600) + button 12 | mixed | 554 | 13.73 / 10.99 | 12 + 20 + 12 | 165 + 220 + 140 + 16 of gaps = 541 |

Names are data and are not capped here: the zone name, item names, buyer and build names take
the ellipsis at default text settings and wrap under an override.

### 3.5 Slot priority and eviction

All of it lives in one module of pure functions, `web/slots.js`, with no DOM access (TD-02):
- `contextMode(state)`: the 7 modes of C in the order above.
- `feedRows(trades, events)`: 5 slots. Open trades first, newest on top (all 5 server slots);
  the free slots take the latest death, the latest level-up and the latest zone change, in
  that order, at most 3. A trade is never evicted by an event. Whatever leaves stays in
  Run > Recent.
- `noticePick(queue)`: (1) a part is broken but reading works (key not registered, web data
  failing or waiting for a contact, calc failed, overlay switched off); (2) a build question
  that needs an answer (two matching builds); (3) the game-language notice; (4) "Setup: N steps
  left" with one button to Settings (F-069); (5) data notes (game data snapshot, update staged,
  GGG docs flag); (6) new-character tip (10 min); (7) key reminder "<key>: check an item",
  retired after 3 successful presses; (8) empty: the label "Notices" and "none", muted.
- `buildLine(state)`, `keptChecks(items, build)`: the B states; the top 3 by current score.
- `trackSet(sizeClass)`: the track tables of 3.2 and 3.8.
- `hudLine2(state)` and `cardHolder(state)`: the overlay rules of section 5 (shared tables).
Nothing on Play is evicted by content pressure in the full class: every region always has its
whole track. Eviction exists only in the compact class (3.8).

### 3.6 Every state (the tracks are the same in all of them)

    state                  G       C       T               N            B            I          U
    first run              dashes  setup   empty           empty        No build     teach      empty
    opted in, no line yet  dashes  none    empty           setup steps  No build     teach      empty
    campaign zone          live    guide   events          tip or key   any          last       any
    campaign town          live    town    events          as queued    any          last       any
    mapping                live    map     trades, events  as queued    Build fits   last       top 3
    trade burst, 5         live    as zone 5 trades        as queued    any          any        any
    item card up           live    as zone as queued       as queued    any          verdict    re-ranked
    build alert up         live    as zone as queued       as queued    Old / Wrong  caveat     any
    game idle              frozen  idle    muted rows      as queued    any          last       any
    error: no log          dashes  error   empty           broken part  any          last       any
    error: AshLight lost   frozen  error   muted           muted        muted        muted      muted
    press error            live    as zone as queued       as queued    any          Not an item any

Before consent the six other regions show their heading and one muted line each, with no
control (F-069 wants nothing but the setup card to act on).

### 3.7 Worst-case arithmetic

The worst case is every region showing its tallest mode at once (campaign zone with the longest
guide entry, 5 open trades, a notice with an action, a wrong-class build, a full item card,
3 kept checks). Tallest content per region against its track [D]:

| Region | Tallest mode | Content | Track | Slack | Slack at s = 1.25 |
|---|---|---|---|---|---|
| G | live | 98 | 100 | 2 | 3 (122 of 125) |
| C | guide (setup 216, idle 204, error 198, town 192, map 182) | 226 | 228 | 2 | 3 (282 of 285) |
| T | 5 rows | 200 | 204 | 4 | 5.5 (249.5 of 255) |
| N | notice with action | 94 | 96 | 2 | 3 (117 of 120) |
| B | any state | 66 | 68 | 2 | 3 (82 of 85) |
| I | full card | 342 | 360 | 18 | 23 (427 of 450) |
| U | 3 rows | 98 | 100 | 2 | 3 (122 of 125) |

At s = 1.25 the content is 2 px of border plus the rem part x 1.25 (G: 2 + 96 x 1.25 = 122).

- 1280x760: left 100 + 8 + 228 + 8 + 204 + 8 + 96 = 652; right 100 + 8 + 68 + 8 + 360 + 8 + 100
  = 652; + 108 chrome = 760. Overflow 0 px in every state, because no state changes a track.
- 1920x950: every rem figure x 1.25: 815 + 135 = 950. Overflow 0 px. Inside a region the rem
  content grows x 1.25 while the 2 px of border do not, so the slack grows (never shrinks).
- 1264x821 (client default): 61 px extra, shared by C and I. 1024x700 and 1920x875: section
  3.8.
- Word total, worst case: 20 + 52 + 50 + 22 + 16 + 60 + 24 = 244 in the grid (today 397 [M]).

### 3.8 Compact class (64em x 43.75em times s, up to the full cockpit of that step)

Same 7 regions, same DOM order, three evictions in this order (px at s = 1):
1. N keeps its head row only (track 52: border 2 + padding 8 + 8 + head 32 = 50; slack 2);
   notice kinds 6 and 7 (tip, key reminder) are not shown.
2. C keeps 6 body rows (track 212: border 2 + padding 12 + 12 + title 26 + 6 rows 132 + facts
   20 = 204; slack 8); setup drops its promise line.
3. U keeps the best kept check only, and its padding drops from 8 + 8 to 4 + 4 (track 52:
   border 2 + padding 4 + 4 + label 20 + 1 row 20 = 50; slack 2). With the full-class padding
   the content would be 58 px, 6 px over the track: the draft's sum left the second 8 px out.
Never evicted: the strip, the 5 feed rows, the build line, the verdict, sentence, compare rows
and price of I (track 348 for 342 of content; slack 6).

| Region | Content | Track | Slack | Slack at s = 1.25 |
|---|---|---|---|---|
| G | 98 | 100 | 2 | 3 (122 of 125) |
| C | 204 | 212 | 8 | 10.5 (254.5 of 265) |
| T | 200 | 204 | 4 | 5.5 (249.5 of 255) |
| N | 50 | 52 | 2 | 3 (62 of 65) |
| B | 66 | 68 | 2 | 3 (82 of 85) |
| I | 342 | 348 | 6 | 8 (427 of 435) |
| U | 50 | 52 | 2 | 3 (62 of 65) |

Sum at 1024x700: left 100 + 8 + 212 + 8 + 204 + 8 + 52 = 592; right 100 + 8 + 68 + 8 + 348 +
8 + 52 = 592; + 108 = 700. Overflow 0 px. Sum at 1920x875 (s = 1.25): left 125 + 10 + 265 +
10 + 255 + 10 + 65 = 740; right 125 + 10 + 85 + 10 + 435 + 10 + 65 = 740; + 135 = 875.
Overflow 0 px. The right column has no spare track in this class (68 + 8 + 348 + 8 + 52 =
484), so region I's slack is 6 px here, not the 18 px of the full class; G4 says so.

### 3.9 Outside the cockpit: zoom, text spacing, small windows

- One DOM order everywhere: bar, G, C, T, N, B, I, U, footer. The cockpit places the regions
  with grid placement only (left column C, T, N; right column B, I, U), so screen order, focus
  order and DOM order are the same in every class; no CSS `order` and no reordering.
- Flow class (under 64em x 43.75em; also 200 percent zoom and a 320 px wide window): one
  column in that same DOM order (the item card is sixth), with one page scroll; rows wrap, so
  nothing takes the ellipsis. This is the WCAG reflow path, not a play state.
- Flow at narrow widths (no horizontal scroll down to 320 px): under 40em wide the Zone cell
  takes a full row of the strip and Level, Deaths and Session share the next row as 3 equal
  cells; the tab row wraps under the brand (design 0001 section 4, kept) with the character
  name and the status word on the brand row; a trade row's right-aligned segment moves under
  its lead line and "Dismiss" stays at the end of the first line; the two footer sentences
  stack.
- Text-spacing overrides (WCAG 1.4.12) and user style sheets: region tracks are minimums
  (`minmax(track, auto)`), no Play element clips on either axis, and the page is the only
  scroll container. Composed rows fit one line even under the override (the character budgets
  of 3.4). For names and for any other user style, a probe switches the rows to wrapping: a
  hidden one-row reference element is watched by a ResizeObserver (an event, not a timer), and
  when its box differs from the token values the page gets `data-text-spacing="user"`, under
  which rows are `white-space: normal`, the tracks grow and the page scrolls. Nothing is cut
  and no nested scroll box appears. In the tested states at default text settings no track
  grows.
- The no-scroll guarantee is therefore stated for default text settings in the compact and
  full classes (1024 x 700 and up at a 16 px default).

## 4. Tab set: 4 tabs

Play, Build and items, Run, Settings (today 5: Play, Run and history, Build, Items and prices,
Settings). This is the ruled set (F-067; the conflict of notes 0043 / 0042 / 0038 is closed
there). The panel's three-tab set (Play, Review, Setup) is not adopted (0043-X9) and is listed
only as option O-4. Rule a player can remember: Play = now, nothing to press; Build and items =
what I wear and what to look for; Run = what happened; Settings = every switch.

No tab scrolls. Build and items and Run are fixed grids of 6 cards (3 x 2). At s = 1 a card is
408 x 322 px [C]: border 2 + padding 24 + title 26 + 10 rows x 22 + pager row 28 = 300, slack
22. A list longer than 10 rows pages ("1-10 of 23", Prev / Next, 28 px); a card's rarer tools
are further pages of the same card. F-067's row caps and closed folds become pages: no fold can
grow a card. Compact class: the same 3 x 2 grid with 8 rows a page (card 322 x 292 px: 2 + 24
+ 26 + 176 + 28 = 256, slack 36).

One row rule on these two tabs: a list row is one line (22 px) with the ellipsis as the guard,
exactly as on Play; a row never wraps on a list page. The full text is on the card's "Full
text" page, switched by one button in the pager row ("Full text" / "List"): 3 entries a page,
each up to 3 wrapped lines of 22 px (3 x 66 = 198 of the 220 px row block; slack 22). Compact:
2 entries a page, each up to 4 lines (2 x 88 = 176 of 176). No composed string is over 120
characters (a data test; the guide `line` cap). 120 characters need 3 lines at 47 characters
(382 px inner width at the 8 px budget of 3.4) and 4 lines at 37 characters (296 px, compact)
[D]. The Full text page is the keyboard-reachable twin of every row that can take the
ellipsis.

Settings is a rail (220 px, 6 sections, one visible) and a detail pane (1016 x 652 at s = 1;
760 x 592 compact). Pane arithmetic [D], compact (the tighter case): 592 - border 2 - padding
24 = 566 px inside. Fixed parts: index row 32 + section heading 26 + gap 8 + status line 20 =
86. A setting row is 32 px (label 16 px, control at least 24 px); a text line is 22 px, a sub
line 20 px. Rule: a section holds at most 448 px of rows and text (14 rows of 32); 448 + 86 =
534 of 566, 32 px spare. A section that needs more pages like a card (pager 28 px, inside the
spare) and never scrolls.

| Section | Rows of 32 px | Text and sub lines | Content | + 86 fixed | Of 566 |
|---|---|---|---|---|---|
| 1 Checks | 12 check rows a page + Copy report 1 | pager 28 | 444 | 530 | spare 36 |
| 2 Reading and web data | 6 (stop reading, log path, web data, contact, league, price book) | 2 sub lines 40 | 232 | 318 | spare 248 |
| 3 Overlay | 10 (on / off, preset, parts in 2 rows, corner, size, Background, zone guide, card time, sample card) | 0 | 320 | 406 | spare 160 |
| 4 Keys | 3 (item key, overlay key, change key) | 2 text lines 44 | 140 | 226 | spare 340 |
| 5 Appearance and tools | 6 (Theme, autostart, export, import, restart overlay, More) | 0 | 192 | 278 | spare 288 |
| 6 About and data | 2 (run history keep / clear, version) | 14 text lines 308 (does and never does 8, credits 4, trademark 1, disclaimer 1) | 372 | 458 | spare 108 |

At 1280x760 the pane is 652 px (626 inside), 60 px more spare in every row. TD-21 confirms the
row counts against the real controls; a section that comes out over 448 px pages.

Build and items (6 cards):
- Build: name, class, level, source and age, key stats (6), Copy code. Pages: paste box and
  share link; per-character list (decision 0045); "More": the `.build` download.
- Health and next: build health (top 3), "Look for next" rows each with its trade-search link
  (F-123). Pages: gear, gems, notes.
- Search strings: the strings with Copy. Page: loot filter download and merge.
- Last item: the full check behind Play's card (every slot, calc line, rolls, price and
  points, time); the worn set (F-070).
- Prices: "Your checked items" on top (F-056), currency values (top 6), movers (3); the
  blocked wording of F-018.
- Item scoring: the changed weights only; "Edit weights" pages of 10; reset.

Run (6 cards):
- Acts: act, time in act, run total, your best. Pages: zone levels; the pace line.
- Maps: this session's maps. Pages: saved sessions; the summary line.
- Recent: events newest first, chips All / Deaths / Trades; it is the twin of Play's feed.
- Deaths: death recap, most deaths.
- Last session: the summary (also Play C while idle). Pages: run history (20 runs).
- Characters: the picker (looking at another character is a review act), per-character bests.

Settings (rail; an index row on top jumps to and focuses switches that live elsewhere: build
source, item scoring, search strings and filter, characters):
1. Checks - shows by itself when a check fails; Copy report.
2. Reading and web data - stop reading (the bar status word lands here, section 3.4), the log
   path, the one web-data switch with contact and league, price book state.
3. Overlay - parts chooser with presets (F-118), corner, size, Background, zone guide (On
   entry / Always / Never), card time, sample card.
4. Keys - the real bound keys, change key (F-026).
5. Appearance and tools - Theme, autostart, settings transfer, restart overlay; "More": the
   graphics advisor.
6. About and data - what AshLight does and never does, the full game data credits (the
   one-line credits stay on the cards that show the data, section 3.4), the trademark line,
   run history keep / clear, version.

Where today's tabs go:
- Play -> Play (section 3). Pace line, character picker, extra compared slots, price and
  points notes, the time and calc lines of the item card -> Run or Build and items.
- Run and history -> Run. The keep / clear switch -> Settings 6.
- Build -> Build and items (Build, Health and next, Search strings). The town search string ->
  Play C.
- Items and prices -> Build and items (Prices, Item scoring, Last item); the web-data switch
  -> Settings 2.
- Settings -> Settings 1 to 6.

Cut: the dead `/api/clipboard-read` stub (F-188); the separate price watch card (F-056); the
separate "Zone tip" (F-122); the "Requests clear after 10 minutes" sentence; the tip heading;
the item card's sub-headings. Kept after the design review: the per-row Dismiss on Play (a
player must be able to clear one wrong request without losing the others; design 0001 section
7.2 "trade list with dismiss"). Hidden under "More" pages: the `.build` download, the graphics advisor, settings transfer. Frozen (no
growth): trade cards, tips.
Tab memory: a stored `items` maps once to `build`; the other three names stay. News for Play
still shows Play by itself (10 s grace, exists). Play carries a count while another tab is
shown; Settings carries "fix" while a check needs one.

## 5. Overlay

Window: unchanged. Separate, transparent, always-on-top, click-through, non-focusable; 280 x 176
DIP at scale 1.0 (`app/shared/layout.js` BASE); plates at most 258 px wide; corners only,
default top-right; hidden while the game is idle (decision 0029). Content cap unchanged in
count: 2 HUD lines + one 3-line card. The placement ruling's reversal clause ("the HUD grows
past 2 lines") is not triggered.

### 5.1 Default content

- Line 1 (16 px): zone or map name (28 characters, ellipsis) and the zone or map timer (never
  clipped, minute steps).
- Line 2 (16 px): "Lv 74  3 deaths" plus at most one status word at the same size; the "|"
  glyph becomes a 10 px gap (F-094).
- Line 2 width budget: the plate is at most 258 px wide, 236 px inside (border 2, padding 10
  + 10, `app/overlay/overlay.css`). Rule in `hudLine2`: the level text and the status word
  together are at most 26 characters; over that the deaths text drops ("Lv 74" + gap +
  "Boots: no speed"); a status word over 20 characters stands alone (at most 27). Font metrics
  [C] at 16 px / 600: "Lv 74  3 deaths" 108.5 px and "Boots: no speed" 116.1 px, so the pair
  with the gap is 234.6 px (1.4 px spare) and "Lv 100  999 deaths" with the same word is
  259 px, over the plate: the draft did not check this. With the rule the worst strings are
  "Lv 100" + gap + "Boots: no speed" = 170.6 px and "not reading - see dashboard" alone =
  205.4 px. Budget [D]: 7.84 px a character (0.49em, the widest measured sample), 26 x 7.84 +
  10 = 213.8 px of 236. TD-17 measures the rendered widths (G10).
- With the parts chooser (F-118) a part that is off drops out; a line with nothing left is
  absent; with no line the HUD plate is absent. Preset "Cards only" shows no HUD.

### 5.2 Line 2 priority (one order, first match)

1. Connection or log state word: "AshLight offline", "no Client.txt", "waiting for log", "not
   reading - see dashboard" (before any data the word stands alone).
2. "2 trades" while another card covers an open trade card.
3. Under-level word "3 lv under".
4. "AFK" / "DND".
5. The zone-guide line (5.4), alone on the line, when it is due.
6. A campaign hint word ("Boss: cold").
7. "Lv 74  3 deaths" alone.
Ranks 1-4 and 6 are the status word after the level text; rank 5 replaces the level text for
as long as it is due and yields at once to ranks 1-4. The guide line is due only when the
setting of 5.4 is Always (an opt-in), the zone is a guided campaign zone with a `short`, and
there was no death and no level-up in the last 20 s: a death or a level-up puts "Lv 74  3
deaths" back for 20 s, so the "Died" moment of design 0001 section 7.2 still shows on the
overlay. With the default setting rank 5 never fires and line 2 always carries level and
deaths.

### 5.3 Card slot (one card, 3 lines of 14 px, 34 characters each)

Holder, first match:
1. The press card: an answer card (item verdict, price, waystone) or a status card ("Build
   loaded: <name>", "Not an item", "Copy the item first"): from the press for the card time
   (20 s default; setting 20 / 60 / 200 s); the newest press wins; first stage under 0.5 s
   (F-059).
2. The newest open trade request, until it closes (accept / cancel line, dismiss, 10 min),
   with "+N" in its first line. It returns by itself when a press card leaves.
3. A moment card (F-119), 12 s, only into a free slot, never waiting, never interrupting: the
   zone card on the first entry of a guided campaign zone per game run, or the act card when
   an act split closes.
4. The key hint line "<key>: check an item" (F-166): until the first press or 3 game
   sessions. 15 characters plus the key name, so a key name of up to 19 characters fits the
   34-character line ("Ctrl+Alt+Shift+F12: check an item" is 33 characters, 214 px [C]).
5. Nothing: the card plate is absent. The sample card shows only on its Settings button (10 s).
Card grammar, by card kind (the O7 / G11 rule):
- answer card or trade card: line 1 starts with its answer: the verdict word and size, the
  price word, or the buyer; line 2 = what (item name; the price only when a poe.ninja value
  exists, F-163); line 3 = why or worth (top stat, DPS / EHP, where; the build caveat head
  while a build alert is set, F-043).
- status card: line 1 starts with its status words, from one allow-list: "Build loaded", "Not
  an item", "Copy the item first".
- moment card and key hint: line 1 starts with its subject: the guide `short` (zone card),
  "Act <n>" (act card), the key name (key hint).
The edge only repeats the word: ok green for an upgrade, accent for a trade, warn for risky, neutral otherwise.
Never two cards. The card's near edge is anchored 62 px from the window's anchored edge (the
2-line HUD height 55.6 + 6), whatever line 2 shows, so a card never jumps.

### 5.4 Zone-guide line (S5-FOLLOWUP a)

- Text: the guide entry's new `short` field: authored, AshLight's own words, at most 34
  characters, for every guide entry (93 today [M]); empty when unsure. The overlay never reads
  the 120-character `line` (that stays the dashboard form). No `short`, no text.
- Two forms from the same field. The zone card (5.3 rank 3): line 1 = `short`, line 2 = bonus
  or "Next: <zone>", line 3 = level advice or boss element. The guide line: `short` on HUD
  line 2 (5.2 rank 5), 14 px, secondary colour.
- Setting "Zone guide on the overlay" (Settings > Overlay): On entry = the zone card only
  (the default, for everyone); Always = the zone card, then the guide line for the rest of the
  stay (an opt-in, because it takes the place of the level and deaths text; 5.2); Never =
  neither. The default does not depend on the display count, so plugging in a monitor changes
  nothing; the choice is stored like every other overlay setting.
- Absent in maps, towns, the hideout and unguided zones. Twin: Play C (guide mode), no timer.

### 5.5 Heights [C]

HUD, 2 lines of 16 px: border 2 + padding 12 + 20.8 + 20.8 = 55.6 px (53.0 with the 14 px guide
line; 34.8 with 1 line). Card: border 2 + padding 10 + 3 x 18.2 = 66.6 px. Tallest content: 62
+ 66.6 = 128.6 px of 176 (47.4 px spare; today 125.6 [M]).

Widths [C] (Segoe UI Semibold font metrics; inside width 236 px): a 34-character card line at
14 px / 600 measures 200 to 230 px (lower case 199.9; capitals and digits 229.6), so the
34-character limit holds at the new size; a 28-character zone name at 16 px / 600 measures
about 200 px and the "12:41" timer 34.7 px, so with the 10 px gap a name over about 26
characters takes the ellipsis (the timer never does, as today); line 2 is in 5.1. TD-05 and
TD-17 repeat these as rendered measurements; if a 34-character fixture line does not fit, the
character limit drops, never the font size.

### 5.6 Legibility over bright scenes (note 0041 recipe, F-094)

- Text is always opaque. The slider (relabelled "Background") sets the plate alpha only:
  default 0.86, floor 0.80, max 1.0 (saved 0.9-1.0 values map onto 0.86-1.0). No `html
  { opacity }`.
- Plate rgba(15, 18, 22, a), 1 px #323840 edge, radius 6 px. Halo: `text-shadow: 0 0 2px #000,
  0 0 2px #000, 0 1px 2px #000`. No stroke.
- Two sizes only: 16 px (HUD lines, status word) and 14 px (card lines, guide line, key hint);
  weight 600; line-height 1.3; tabular numerals. Nothing under 14 px.
- Contrast on the composited plate, 8-bit [C]:

| Colour | a 0.86 white | a 0.86 warm #f2e6c8 | a 0.86 grey | a 0.86 black | a 0.80 white |
|---|---|---|---|---|---|
| primary text #e4e8ec | 10.28 | 10.76 | 13.09 | 15.58 | 8.30 |
| secondary text #c3c9d0 | 7.59 | 7.94 | 9.66 | 11.50 | 6.13 |
| warn text #f0bd55 | 7.30 | 7.65 | 9.30 | 11.07 | 5.90 |
| edge ok #46b85c (non-text) | 4.98 | 5.22 | 6.35 | 7.55 | 4.03 |
| edge warn #d19a2a (non-text) | 5.04 | 5.28 | 6.42 | 7.64 | 4.07 |
| edge accent #5a9ef0 (non-text) | 4.57 | 4.79 | 5.82 | 6.93 | 3.69 |
| edge bad #f0605a (non-text) | 3.93 | 4.12 | 5.01 | 5.96 | 3.18 |

- Floors: text at least 7:1 at the default plate and 5.5:1 at the alpha floor over white;
  edges at least 3:1. Green, red and accent are never overlay text colours; the word carries
  the meaning.
- `autoScale` reference 1200 DIP instead of 1440 (F-162): 1080 -> 1.0, 1440 -> 1.2, 2160 ->
  1.8, cap 2.0; the decision 0002 overlay budgets are re-run in the same step.
- `prefers-contrast: more`: opaque plate, secondary = primary. Forced colours: as today.
- Nothing reads the screen to adapt the plate (that would be a screen watcher).

### 5.7 Never on the overlay

A button, link, input or anything that takes a click or focus; a third HUD line; a second
card; a line over its character limit; wrapping, scrolling, moving or blinking text; a list,
table, price book or compare rows; build stats; guide prose beyond the `short` line; the
session summary; setup steps or the consent prompt; Checks detail (one status word only);
sound, an OS toast, a taskbar flash; green, red or accent text; anything while the game is
idle; anything from a read other than Client.txt, the per-press clipboard text and cached
public web data; any GGG art or logo.

## 6. Typography

Family: `system-ui, "Segoe UI", sans-serif`. No bundled font. No monospace on Play (tabular
numerals do the job); `Consolas, monospace` only for code boxes and paths. Tokens are rem at
root 16 px x s; no `vw` in any font size; sizes change only at the scale steps.

| Token | rem | px s=1 | px s=1.25 | Weight | Line box | Numerals | Role |
|---|---|---|---|---|---|---|---|
| `--al-fs-micro` | 0.8125 | 13 | 16.25 | 400 | 18 | - | the two footer sentences only |
| `--al-fs-meta` | 0.875 | 14 | 17.5 | 400 / 600 | 20 | tabular | facts rows, ages, sources, caps labels inside regions (600, +0.04em), kept-check rows, table heads |
| `--al-fs-body` | 1 | 16 | 20 | 400 / 600 | 22 | tabular | sentences, rows, tabs, buttons, inputs |
| `--al-fs-title` | 1.25 | 20 | 25 | 400 / 600 | 26 | tabular | in-play text: strip labels and sub lines (400), status words, zone timer, context title, item name, trade lead, price, build state (600) |
| `--al-fs-glance` | 1.75 | 28 | 35 | 700 | 32 | - | zone name, verdict word |
| `--al-fs-hero` | 2 | 32 | 40 | 700 | 36 | tabular | level, deaths, session |

- This is the F-053 token set (13, 14, 16, 20, 28, 32 / 40). F-053's two hero values are one
  token at the two reference sizes: 32 px at 1280x760 and 40 px at 1920x950. F-053's size test
  is read in rem: computed font size / root font size is one of the six values.
- Line boxes are fixed rem heights (the px column x s), not unitless multipliers, so a row's
  height does not depend on the font's metrics.
- Minimums: dashboard 14 px (13 px only in the footer); no weight 600 or 700 under 14 px;
  overlay 14 CSS px; every top answer (section 11, G9) at the title step or larger.
- Status words (F-053) are at the title step in the bar, G, N, B and I (I's verdict at the
  glance step). U's kept-check rows are lean-in review text at the meta step; each of them was
  shown at 28 px in I when it was checked.
- Distance rule (F-053, Q-14: reference setup 24 inch 1080p, dashboard at 80 cm, overlay at
  60 cm): in-play text at least 16 arcmin of cap height. [C] at 80 cm: 20 px = 16.6, 25 px =
  20.8, 28 px = 23.3, 32 px = 26.6 arcmin; 14 px = 11.7 and 16 px = 13.3 (lean-in text only).
  Overlay at 60 cm: 16 px = 17.8, 14 px = 15.5.
- Overlay tokens: `--al-ovl-fs-hud` 16 px and `--al-ovl-fs-card` 14 px, both 600 / 1.3 /
  tabular. Today's 15 px and 13 px roles go.
- Text styles (size + weight pairs): Play at most 9 (13/400, 14/400, 14/600, 16/400, 16/600,
  20/400, 20/600, 28/700, 32/700; F-053 allows 10); other tabs at most 8; overlay 2. Today: up
  to 16 on Play [M].
- `font-variant-numeric: tabular-nums` on `body` and on the overlay plates (F-161).

## 7. Colour

Dark by default: `<html data-theme="dark">`, `color-scheme: dark`, and
`nativeTheme.themeSource = "dark"` before the first window; the client start page and window
background use the same values (F-086). Ruling on forcing dark: not forced. One Settings choice
"Theme: Dark / Follow Windows / Light" stays; the overlay is always dark. Under the Windows
default app mode Play's mean luminance is about 25 times higher today [M]. Kit `--fk-*` tokens
are the source and are never edited; `--al-*` tokens are AshLight's own, declared once in
`web/app.css`. Contrast is on page / on card [C].

| Token | Dark | Light | Role | Dark contrast | Light contrast |
|---|---|---|---|---|---|
| `--fk-surface` | #0f1216 | #ffffff | page | - | - |
| `--fk-surface-2` | #181c22 | #f3f4f6 | region plate, bar | 1.10 vs page | 1.10 vs page |
| `--fk-border` | #323840 | #d3d8de | region edge, dividers; decorative only | 1.59 / 1.45 | 1.43 / 1.30 |
| `--al-control-edge` | #737c88 | #7a828c | input, select, checkbox, button edges (non-text, 3:1) | 4.44 / 4.05 | 3.89 / 3.53 |
| `--fk-text` | #e4e8ec | #1a1d21 | values, titles, verdict word, disclaimer | 15.25 / 13.89 | 16.91 / 15.37 |
| `--al-text-body` | #c5ccd3 | #30353c | sentences, rows | 11.58 / 10.55 | 12.35 / 11.22 |
| `--fk-text-muted` | #99a1aa | #555d66 | labels, sub lines, stale or empty values | 7.18 / 6.54 | 6.68 / 6.07 |
| `--fk-accent` | #5a9ef0 | #1559a8 | links, focus ring, selected tab, trade edge, the 1 filled button (its text is the surface colour: 6.78 dark, 6.94 light) | 6.78 / 6.18 | 6.94 / 6.31 |
| `--fk-status-ok` | #46b85c | #1d7a3a | upgrade, check passed, build fits | 7.40 / 6.74 | 5.39 / 4.90 |
| `--fk-status-warn` | #d19a2a | #946200 | needs you: old build, risky, under-level, blocked | 7.48 / 6.81 | 5.24 / 4.76 |
| `--fk-status-bad` | #f0605a | #c4262f | failed, lost, death | 5.83 / 5.31 | 5.73 / 5.21 |
| `--fk-status-idle` | #8a929b | #5b636c | idle, neutral verdict, pending | 5.96 / 5.43 | 6.09 / 5.54 |
| `--al-plate` | rgba(15, 18, 22, 0.86) | same | overlay plate (alpha 0.80 to 1.0) | section 5.6 | - |
| `--al-ovl-text-2` | #c3c9d0 | same | overlay secondary text | 7.59 worst | - |
| `--al-ovl-warn` | #f0bd55 | same | overlay warn word | 7.30 worst | - |

- Floors: every text pair at least 4.5:1 (lowest: light warn on a card 4.76; dark bad on a card
  5.31); non-text (control edges, focus ring, glyph strokes) at least 3:1 (lowest 3.53).
- One meaning per colour: ok = good or working; warn = act when you can; bad = failed, lost or
  a death; accent = "you can act here": something interactive (a link, the selected tab, the
  focus ring, the one filled button) or a request that waits for the player's reply (the
  trade edge). That is one meaning with five uses. Trade rows move from amber to accent, so
  amber no longer sits beside the green / red pair. A whisper that is not a trade request
  loses its accent edge: it is not shown on Play and keeps only its muted FROM / TO tag in
  Run > Recent.
- Never colour alone: every state is a glyph and a word from the kit vocabulary (`[+]`, `[ ]`,
  `[?]`, `[#]`, `[x]`, `[-]`, `[>]`; no AshLight-made glyph); one table maps states to words
  (F-131). Verdicts are words (Upgrade, Sidegrade, Downgrade, Risky). An edge only repeats it.
- Colour marks exceptions: the normal "reading" word, normal buttons and normal rows are
  neutral (F-159); red is never used for attention, prices or a downgrade.
- Stale data is visible (F-087; a look, not a state word): `body[data-fresh="no"]` (idle, AshLight lost) draws strip values,
  timers and feed rows in `--fk-text-muted` and adds "frozen <time>" to the zone sub line.

## 8. Motion and attention

- Nothing moves on either surface: 0 CSS animations, 0 transitions, 0 scrolling or blinking
  text, no sound, no OS toast, no taskbar flash in play (F-095; kept as a test).
  `prefers-reduced-motion` therefore changes nothing.
- Urgency is encoded, in this order, by: (1) the region (trades always in T, build trouble
  always in B, broken parts in N, the asked-for answer always in I and in the overlay card);
  (2) glyph + word; (3) a 4 px left edge in the status colour (3 px on the overlay); (4) for
  60 s after arrival the word "new" at the start of the row's right-aligned segment ("new,
  2m"; a text change, not motion; the row's own sentence is not touched).
- Three levels: ambient (strip, HUD lines; neutral), notice (N, moment cards, warn words; one
  amber cue per item), asked-for or reply-needed (I, T, press and trade cards).
- Tab marks: a count on the Play tab when news arrives while another tab is shown; Play then
  shows by itself after the 10 s grace.
- Content swaps happen in place on the state push; a region repaints only when its text
  changes. Dashboard timers tick once a second (tabular numerals, fixed width); the overlay
  timer repaints at most once a minute.

Timing:

| Item | Shown for | Twin that stays |
|---|---|---|
| overlay press card | 20 s (setting 20 / 60 / 200 s) | Play I until the next check; Build and items > Last item |
| overlay zone or act card | 12 s | Play C (guide); Run > Acts |
| overlay trade card | until closed or 10 min | Play T; Run > Recent |
| overlay key hint | until the first press or 3 game sessions | Play I empty state; Settings > Keys |
| overlay sample card | 10 s, only on its button | none needed (the player asked) |
| Play notice kinds 6-7 (tip, key reminder) | 10 min / 3 presses | Settings > Keys; the guide |
| the word "new" | 60 s | the row itself |
| everything else | until its cause ends | - |

WCAG 2.2.1 holds three ways: no interaction is ever timed; the press card time can be raised
to 10 times the default; every item that leaves by itself has a twin that stays. A test lists
the twins and fails when a card kind has none (F-095, note 0055 R5).

## 9. Accessibility commitments (WCAG 2.2 AA)

- 1.4.3 / 1.4.11: the floors of section 7 in dark and light, asserted by the token test and a
  browser colour-pair test; overlay text at least 7:1 over white at the default plate and
  5.5:1 at the floor (F-144 measures rendered pixels).
- 1.4.1: no state by colour alone (glyph + word). 1.3.1: one heading per region, landmarks
  (header, main, footer) kept, headings in order.
- 1.4.4 / 1.4.10: 200 percent zoom and a 320 px width use the flow class (em-based queries),
  with no horizontal scroll: the narrow-width rules of 3.9 (strip, tab row, trade row,
  footer); the client restores Ctrl + plus / minus / 0 (note 0044 F4).
- 1.4.12: section 3.9. A test injects the four text-spacing overrides on the long-string
  fixture at 1024x700 and 1280x760 and asserts, for every element under the Play panel, no
  clipping on the block axis (scrollHeight <= clientHeight) and none on the inline axis
  (scrollWidth <= clientWidth), and that only the page scrolls. Composed rows are under the
  character budgets of 3.4; names wrap through the text-spacing probe. At default settings a
  name that takes the ellipsis has its full text in `title` and in a keyboard-reachable twin
  (the Full text page of its card, section 4).
- 1.3.2 / 2.1.1 / 2.4.3: every control by keyboard; one DOM order in every class: bar, G, C,
  T, N, B, I, U, footer (DOM order = reading order = focus order; grid placement only, 3.9).
  Regions do not scroll, so they need no tab stop; `#panel-play` loses its `tabindex` (F-096).
  One tab stop for the tab row (arrow keys, Home, End). When a trade row is dismissed from the
  keyboard, focus goes to the next row's "Dismiss", else to the T heading (`tabindex="-1"`).
- 2.4.7 / 2.4.11: a 3 px accent ring drawn inside the element (`outline-offset: -3px`), never
  clipped by a parent (note 0044 F2); an outside ring only on the one filled accent button.
- 2.5.8: every target at least 24 x 24 px; buttons 32 px where the row allows (28 px in I,
  24 px in B and the T head); the two 20 px checkboxes grow to 24 (F-164).
- 2.2.1 / 2.2.2 / 2.3.1: section 8; nothing flashes, nothing advances by itself (pagers move
  only on a press).
- 3.2.1 / focus: a card, trade, notice or mode change never moves focus. The automatic return
  to Play happens only after the 10 s grace of design 0001 section 4 (no click, key press or
  scroll in the shown tab or the tab row for 10 s), so a user who is arrowing across the tabs
  is never pulled away. When it happens, focus moves to the Play tab only if focus sat on the
  tab row; a focus inside a panel is never moved (then Play only carries its count). The move
  is announced once in the polite header line: "Showing Play. New trade." (G-13).
- 3.3.1 / 3.3.3: every fix line names an in-app control, never a file or a shell command.
- 4.1.3: at most 4 live regions on Play (verdict, trade status, notice, reading word) and 6 in
  the page (today 12 in the DOM, 6-7 visible [M]); all polite; the strip and the guide are not
  live. Each announcement at most 12 words.
- Forced colours: the selected tab has its own border, not weight alone (note 0044 F3); the
  trade and verdict edges use system colours; words stay. Disabled buttons look disabled and
  say why.
- Overlay: 0 focusable elements, 0 live regions; the dashboard is its accessible equivalent
  (0044-X1 stays rejected). The disclaimer stays in the overlay About as text.

## 10. Zero-click flows (inside the rulings)

Build arrival - the player never hunts for a link:
1. Already there: one build per character, swapped from Client.txt when the character changes
   (decision 0045, exists). 0 acts for every session after the first load.
2. No build is not a wall: with none, the item check answers from the worn item (F-070), the
   keep-or-vendor rules (F-060) and the default weights; B reads "[ ] No build" and names the
   one press. No dead end, no prompt in the way.
3. Old by itself: 5 or more levels behind (or a class mismatch) turns B to "[?] Old build" /
   "[?] Wrong class" and puts the caveat on every verdict (F-043). No card, no click.
4. One press, anywhere (F-042, ruled in by Q-02): in Path of Building, Export > Copy, then
   press the AshLight item key. The same single clipboard read of that manual press is
   classified: a PoB code or character JSON loads the build (overlay card "Build loaded:
   <name>"), a share link loads only with web data on, anything else is the item check. 1
   chord, no tab, no paste box. Lands with the dated amendment of decision 0004 item 4.
5. Paste box and share link stay on Build and items for players who prefer them; B's "Paste a
   build" button goes there (F-041).
Not designed in (options, section 13): following the Path of Building builds folder (O-1), a
build file picked in the browser (O-2), the GGG character API (registration is closed; the
`ggg_api` provider stays a no-request stub until the docs watch of decision 0044 flags a
reopening). No design element depends on any of them.

Item flow - the minimum the floor allows, and fewer checks instead of faster ones:
- Per item: hover, the game's own copy key (the player's press), then the AshLight item key
  (exactly one clipboard read per press; an empty read shows "Copy the item first", F-054).
  Today that is 2 chords, 5 key presses with Alt+Shift+E. 2 chords is the floor's minimum:
  the copy must be the player's press and the read needs its own AshLight press.
- 3 key presses (hold Ctrl, tap C, tap the neighbour key) is option O-3: it waits for the
  operator's two one-minute checks (Q-09). The default stays Alt+Shift+E until then.
- The answer needs no look-away: verdict word first on the overlay card within 0.5 s (F-059),
  and at 28 px in I, which stays.
- 0 presses where possible: the vendor search string on Play C in town (one optional Copy
  click a visit lights up candidates, F-124), value tiers in the loot filter (decision 0032),
  "Look for next" with a per-slot trade-search link the player opens (F-123), and U re-ranking
  the kept checks by itself on a build or weight change (decision 0045).
- Never: a clipboard watcher, a timer, a key sent to the game, a repeated screen read. The
  one-press screen read spike (F-212) stays deferred (O-7).

First run - 1 required click:
- The client opens dark, on the largest display the overlay is not on (F-099).
- Play C shows the setup card: row 1 "Allow reading Client.txt" with the log path and the one
  filled button (floor-bound, explicit, revocable); rows 2-4 (your build, prices, overlay)
  show their state, are optional and carry no control of their own (F-069).
- After "Allow" everything fills from the log (LIVE-RESUME reads back, decision 0008); N holds
  "Setup: N steps left" with one button to the controls on Settings; nothing blocks play.
- The overlay shows the key hint in its empty card slot until the first press (F-166).
- No PowerShell, no JSON file: every setting has a control in Settings (F-026, F-018).

## 11. Glance budgets (testable assertions)

Cockpit sizes: 1280x760, 1920x950, 1264x821 (full); 1024x700, 1920x875 (compact). Flow sizes:
1366x650 and 320x640. States: pack states a, a2, b, c, c2, d, e, f, g, plus "c + 3 more
whispers" (5 trades) and a map state. All captures run on a demo core that can never find the
live log (F-001), never on port 8960. Every assertion is at default text settings unless it
names an override.

- G1 No scroll: in every state at every cockpit size, the page overflow is 0 and no element
  under any tab panel has scrollHeight > clientHeight. Same for each card page (list and Full
  text) and each Settings section. At the two flow sizes the page scrolls on the block axis
  only: the document's scrollWidth is at most its clientWidth and no element is a nested
  scroll container.
- G2 Same place: each Play region's bounding box is identical (within 1 px) across all states
  at a given cockpit size, and equals the track table: 100 / 228 / 204 / 96 / 68 / 360 /
  100 px at s = 1 (x 1.25 at 1920x950); 100 / 212 / 204 / 52 / 68 / 348 / 52 px compact
  (x 1.25 at 1920x875).
- G3 Tables: a node test enumerates context mode (7) x open trades (0-5) x item card kind (5)
  x notice kind (8) x build state (4) x size class (compact, full) and asserts, without a DOM,
  that every region's row count fits its track, that all open trades have a row, and that the
  summed tracks equal the grid height.
- G4 Slack, measured after rounding: in the worst state the content bottom of each region is
  at least 2 px above its inner edge at s = 1 and at least 3 px at s = 1.25; region I keeps
  at least 16 px in the full class and at least 6 px in the compact class (tables of 3.7 and
  3.8).
- G5 Words on Play (inside the grid): at most 250 worst case (today 397), per region 20 / 52 /
  50 / 22 / 16 / 60 / 24; at most 150 in a plain campaign zone; at most 110 on first run.
  Visible elements at most 100 (today 133).
- G6 Controls on Play, counted inside the 7 regions (the 4 tabs, the bar status word and the
  footer are not counted): at most 7 with no open trade (4 in I, 1 each in C, N and B, 0 in G
  and U); each open trade adds its own Dismiss and 2 or more add "Dismiss all", so at most 13
  with 5 trades. All at least 24 px, none required to read a value.
- G7 Type: computed font size / root font size is one of 0.8125, 0.875, 1, 1.25, 1.75, 2;
  0.8125 only in the footer; no weight 600 or more under 14 px; no `vw` in any font size; text
  styles: Play at most 9, other tabs at most 8, overlay exactly 2 sizes (16, 14).
- G8 Contrast: every dashboard text pair at least 4.5:1 in dark and light; non-text at least
  3:1; overlay primary, secondary and warn at least 7:1 over #ffffff and #f2e6c8 at plate
  0.86 and at least 5.5:1 at 0.80, plus a rendered glyph-core check at least 5.5 over white;
  with `prefers-color-scheme: light` emulated and no setting, the page background computes to
  rgb(15, 18, 22).
- G9 Time to answer (proxy for one 2 s look): each of the 12 answers sits in its fixed region,
  within the region's first 6 words, at the title step or larger: zone (G, 28), time in zone
  (G, 20), what to do here (C title, 20), is it an upgrade (I head, 28), what is it worth (I
  price row, 20), who wants what (T row 1, 20), level (G, 32), under-levelled (G sub, 20),
  deaths (G, 32), session (G, 32), is it reading (bar, 20), is my build right (B row 1, 20).
  The under-level words are "N lv under" on the dashboard and on the overlay.
- G10 Overlay shape: window 280 x 176; content height at most 130 px; at most 2 HUD lines and
  1 card; zone line at most 28 characters, card, guide and key hint lines at most 34; HUD
  line 2 at most 26 characters with a status word and at most 27 for a word standing alone;
  every guide `short` at most 34 characters or empty; the overlay never renders `line`;
  minimum 14 px; 0 interactive elements; 0 animations. Rendered width, measured: each
  worst-case fixture line is at most 236 px wide and no line's scrollWidth exceeds its
  clientWidth except the zone name: "Lv 100" + "Boots: no speed", "Lv 74  3 deaths" + "3 lv
  under", "not reading - see dashboard", a 34-character capitals-and-digits card line, the
  key hint with an 18-character key name.
- G11 Overlay rules: a table test of `hudLine2` (7 ranks, the 26-character drop rule, the 20 s
  return of level and deaths after a death or level-up under Always, rank 5 never firing
  under On entry) and `cardHolder` (5 holders); line 1 of an answer card or trade card starts
  with its answer (verdict word, price word or buyer), of a status card with its status words
  from the allow-list ("Build loaded", "Not an item", "Copy the item first"), of a moment card
  or the key hint with its subject; the card's near edge is at 62 px in every state; every
  self-leaving card kind has a twin selector.
- G12 Tabs: exactly 4 `role="tab"` elements; news shows Play with 0 acts; Play has at most 4
  live regions; the automatic return never fires within 10 s of a key press in the tab row,
  moves focus only from the tab row and is announced once; the reading status word is visible
  on all 4 tabs in every state, and pressing it shows Settings > Reading and web data with
  focus on "Stop reading Client.txt".
- G13 Presses: item check at most 2 chords and exactly 1 clipboard read per press; build load
  1 chord and 0 clicks; first run to a filled Play 1 click; first card stage under 0.5 s with
  a slow fake calc.
- G14 Motion: 0 running animations and 0 transitions in every capture; no notification API in
  the tree.
- G15 Cost: overlay working set and frame budgets of decision 0002 unchanged after the
  `autoScale` change, measured at zoom 1.2; at most 1 repaint per changed string.

## 12. Migration

Each step is sized for one agent. "Carries" names the finding whose work the step delivers (the
execution plan, section 07, merges them into one package); "needs" names findings that are
their own packages and must land first. Every step that changes UI gets a design-reviewer pass
and a `docs/design/reviews.log` line.

Conflict hotspots (one step at a time; never two live agents): `web/index.html`,
`web/app.css`, `web/app.js`, `server/al/state.py`, `app/main.js`, `app/shared/render_gate.js`,
`app/shared/layout.js`, `server/al/data/zone_guide.json`, `docs/design/0001-design-system.md`,
`tests/test_ux_review.py`, `tests/test_a11y.py`, `app/test/tabs.test.js`.

Wave 0 - foundations, no visible layout change:
- TD-01 Fit harness, red first. Carries F-066. Files: `app/test/cdp/play_fit.mjs` (new),
  `tests/test_play_fit.py` (new), `tests/play_states.py` (new: the state recipes and a
  long-string fixture: 40-character names, 5 trades, the longest guide entry, every composed
  row at its character cap). Sizes: the 5 cockpit sizes and 2 flow sizes of section 11. Proof:
  G1 is red on today's layout (state c, 380 px over); each region's expected-fail entry is removed by
  the step that lands it; the [D] figures of section 3 are confirmed or corrected here. Needs:
  F-001, F-034 (a demo core that cannot find the live log). Parallel with: TD-02 to TD-08.
- TD-02 Slot tables. Files: `web/slots.js` (new), `app/test/slots.test.js` (new). Proof: G3
  and the table half of G11, no DOM. Needs: nothing. Parallel with: all.
- TD-03 Type, spacing and scale tokens. Carries F-053, F-160, F-161. Files: `web/app.css`
  (the `:root` token block and the scale queries only), `tests/test_design_tokens.py` (new),
  `tests/test_ux_review.py` (type floor test), `docs/design/0001-design-system.md` (the four
  control-edge rows of 5.2). Proof: G7 static part; `tests/test_design_contrast.py`. Needs:
  nothing. Parallel with: TD-01, TD-02, TD-04, TD-08. Before TD-05 (shared test and doc).
- TD-04 Dark by default and the Theme choice. Carries F-086. Files: `web/index.html` (the
  `data-theme` attribute only), `web/settingsio.js`, `server/al/settingsio.py` (allow-list),
  `app/main.js`, `app/client/window.js`, `app/client/starting.css`. Proof: G8 luminance part
  through the F-147 capture helper; a node test that `themeSource` is set before the first
  window. Needs: F-147. Parallel with: TD-01 to TD-03, TD-08. Before TD-05 (`app/main.js`).
- TD-05 Overlay legibility recipe and two sizes. Carries F-094, F-144. Files:
  `app/overlay/overlay.css`, `app/shared/layout.js`, `app/main.js`, `web/index.html` (slider
  label), `app/test/layout.test.js`, `tests/test_design_contrast.py`, `tests/test_ux_review.py`,
  `tests/test_overlay_layout.py`, `tests/test_ux_settings_io.py`, design 0001 (overlay rows of
  5.2, in the same commit as the CSS). Proof: G8 overlay part; the rendered-width part of G10
  for the 34-character card fixture at 14 px / 600 (if it does not fit 236 px, the character
  limit drops in `app/shared/format.js` and `server/al/state.py` CARD_LINE in this step,
  never the font size). Needs: TD-03, TD-04.
- TD-06 `autoScale` 1200 with the budgets re-run. Carries F-162. Files:
  `app/shared/layout.js`, `app/test/layout.test.js`. Proof: the DIP table test (1080 -> 1,
  1440 -> 1.2, 2160 -> 1.8, 4320 -> 2) and G15 in the same commit. Needs: TD-05, F-108.
- TD-07 Play view with capped strings. Files: `server/al/state.py` (one `play` block: the
  composed, capped rows of each region), `tests/test_play_view.py` (new). Proof: G5 caps and
  exact-output tests on the pack states and the long-string fixture. Needs: F-131 (one status
  vocabulary), F-043, F-120. Parallel with: TD-01 to TD-06 (not with another `state.py` step).
- TD-08 Guide `short` field. Files: `server/al/zoneguide.py` (field, 34-character cap, view key
  `short`), `server/al/data/zone_guide.json` (93 entries authored in AshLight's own words from
  the allowed fact sources; empty when unsure), a data test. Proof: every entry has `short` as
  ASCII text of at most 34 characters or an empty string; the overlay view carries `short`,
  never `line`. Needs: F-122 (one guide file, same data file), F-097. Parallel with: all others.

Wave 1 - the frame:
- TD-09 Play skeleton. Carries F-025 (layout), F-096 (panel tab stop). Files: `web/index.html`
  (Play panel only), `web/app.css` (cockpit block: full, compact, flow), `web/app.js` (one
  mount hook per region, nothing else). Proof: G2 with placeholder content at the 4 sizes.
  Needs: TD-02, TD-03.

Wave 2 - regions (after TD-09 and TD-07; parallel; each step owns one new renderer file,
removes the renderer it replaces, and touches `web/app.js` only through TD-09's hook):
- TD-10 Strip G, bar and stale look. Carries F-087, F-159. Files: `web/strip.js` (new, from
  the stats code of `web/app.js` and `web/chars.js`), `web/status.js`.
- TD-11 Context C: guide, map, town, none. Carries F-068, F-124. Files: `web/context.js` (new,
  from `web/zoneguide.js`, the map block of `web/runs.js`, `web/search.js`). Needs: F-061 for
  the map prefix (until then map mode is off and the zone shows mode none).
- TD-12 Context C: setup, error, idle. Carries F-069. Files: `web/setupcard.js` (new),
  `web/summary.js`. Needs: TD-11 (the mode hook).
- TD-13 Feed T. Files: `web/feed.js` (new, from `web/trades.js` and the events list).
- TD-14 Notice N. Files: `web/notice.js` (new, from `web/hints.js`, the Checks summary, the
  language box, the setup line).
- TD-15 Build line B. Carries F-041. Files: `web/buildline.js` (new, from `web/buildlive.js`).
- TD-16 Item card I and kept checks U. Carries the card side of F-059, F-060, F-070. Files:
  `web/itemcard.js` (new, from `web/tc.js`, `web/prices.js`, `web/pricewatch.js`).
  Proof for each of TD-10 to TD-16: its region's rows of G1, G4, G5, G6 and G9 in every state
  at the 4 sizes, plus a node test of the renderer; TD-01's expected-fail list is empty when
  all seven have landed.

Wave 2, overlay lane (parallel with the region steps):
- TD-17 Overlay line-2 rule, guide line, moment cards, fixed card anchor. Carries F-119,
  F-163, F-166, F-095. Files: `server/al/state.py` (overlay view; after TD-07),
  `app/shared/format.js`, `app/shared/render_gate.js`, `app/overlay/index.html`,
  `app/overlay/overlay.js`, `server/al/settingsio.py` and `server/al/layout.py` (the zone
  guide setting, default On entry), `tests/test_overlay_layout.py`, `tests/test_budgets.py`,
  `app/test/overlay_gate.test.js`. Proof: G10 (with the measured line widths), G11. Needs:
  TD-02, TD-05, TD-07, TD-08, F-088, F-118.
- TD-18 Card time setting. Files: `server/al/state.py`, `server/al/settingsio.py`,
  `server/al/layout.py`, the Settings > Overlay control. Proof: a unit test of 20 / 60 / 200
  with 20 the default; the twin test. Needs: TD-17. Optional (cut list item 2).

Wave 3 - tabs (serial: all three rewrite parts of `web/index.html`):
- TD-19 Four tabs and the Build and items grid. Carries F-067, F-056. Files: `web/index.html`,
  `web/tabs.js` (name map), `web/pager.js` (new: list pages and the Full text page),
  `web/app.css`, `web/prices.js`, `web/pricewatch.js`, `app/test/tabs.test.js`. Proof: G12; G1
  for the tab, list and Full text pages; the poe.ninja credit line is visible on the Prices
  card while it shows prices.
- TD-20 Run grid. Files: `web/index.html` (Run panel), `web/history.js`, `web/runs.js`,
  `web/acts.js`, `web/app.css`. Proof: G1 for the tab in states f and g; the game data credit
  line is visible on the Acts card while snapshot data shows.
- TD-21 Settings rail and index; footer folds move. Files: `web/index.html` (Settings panel,
  footer, the bar status word as a button), `web/rail.js` (new), `web/checks.js`,
  `web/app.css`. Proof: G1 for each section, against the pane arithmetic of section 4 (a
  section over 448 px of rows pages); every index entry jumps to and focuses its control; the
  disclaimer is still in the footer; the one-line data credits stay on Run > Acts, Build and
  items > Prices and Play I's price row and the full credits are in About and data; the
  reading status word is visible on every tab and lands on "Stop reading Client.txt" (G12).
- TD-22 Accessibility pass. Carries F-096 (focus), F-121, F-151, F-164. Files: `web/app.css`,
  `web/tabs.js`, `web/textspacing.js` (new: the text-spacing probe of 3.9),
  `app/client/window.js` (zoom keys), `app/test/cdp/a11y.mjs` (new), `tests/test_a11y.py`.
  Proof: the browser test of section 9 (ring box, forced-colours tab, target sizes,
  live-region count, the text-spacing run on both axes, the 320 px capture, the focus rule of
  the automatic return). Needs: TD-19 to TD-21.

Wave 4 - records:
- TD-23 Records. Files: `docs/design/0001-design-system.md` (sections 3, 4, 5, 6, 7.2, 9, 10,
  11 rewritten from the amendment of 2026-11-18; the amendment section is then removed), a new
  decision "fixed cockpit Play, four tabs, dark by default" (alternatives: designs B and C, the
  three-tab set; reverses if: section 14; it also records the kept per-row Dismiss and the
  opt-in guide line), dated amendments of decision 0014 (card slot holders, card time, the
  guide line on HUD line 2) and of the placement ruling's record (the HUD is still 2 lines),
  the CLAUDE.md settled entry for decision 0014 (today "one card slot, 20 s"; new: one card
  slot with its holders, card time 20 / 60 / 200 s), `docs/design/reviews.log`. Proof: the
  docs lint,
  `tests/test_design_contrast.py`, the design gate. Needs: all steps above.

Their own packages, needed by the flows of section 10 and not repeated here: F-042 (the press
loads a build), F-059 (staged press, core side), F-060 (keep-or-vendor), F-070 (worn gear,
core side), F-026 (keys in the app), F-099 (second display), F-118 (parts chooser), F-122 (one
guide file).

## 13. Options waiting on the operator

None of these is relied on. Each lands without rework of the design above.
- O-1 Follow the Path of Building builds folder (Q-01: outside the current floor text). If the
  operator adds the read-list line, it becomes build way 0: save in Path of Building, 0 acts.
- O-2 A build file picked in AshLight's own page (Q-02 file half, F-058: blocked on the same
  kind of read-list line).
- O-3 Item key as a roll under Ctrl (Q-09, F-054): 3 key presses per item instead of 5. Needs
  the two one-minute checks (layout flip of Alt+Shift+E / A; one free Ctrl+letter next to C).
- O-4 Three tabs (Play, Review, Setup): the panel's preference, not adopted (0043-X9, F-067).
  On the operator's word, Build and items and Run merge into one Review grid of 6 paged cards
  and Settings becomes Setup; Play, the overlay and every token stay as designed.
- O-5 A third HUD line for the guide: not adopted (0040-X5, decision 0014, the placement
  ruling). Only on a recorded re-ruling; the design does not need it.
- O-6 The operator's real monitor size, resolution and distance (Q-14): changes token values
  and test constants only.
- O-7 One press per item by one screen read on the press (F-212, deferred spike).
- O-8 A peek key for one-screen players (F-208, deferred taste call).
- O-9 One normally played map with the overlay check armed (F-128, Q-18): the in-play proof of
  G15 after the `autoScale` change.

## 14. Risks, and what to cut first

Risks:
- R1 Real strings are longer than fixtures (long item names, localised zone names): the
  ellipsis hides words. Bound: caps at the source, full text in `title` and in a twin, the
  long-string fixture of TD-01, G4 slack.
- R2 The slack is small (2 px in five regions) because the tracks are exact sums of fixed line
  boxes. If TD-01 finds a line box that renders taller, the fix is in the token, not in a
  region; region I holds 18 px in reserve in the full class and only 6 px in the compact
  class, where the right column has no spare track.
- R3 F-053's size test and F-066's "40 px spare" budget are restated (sizes in rem; spare
  replaced by G2 and G4). The execution plan must carry the restated acceptance.
- R4 A fixed grid fights user text settings: handled by section 3.9, but a zoomed viewer loses
  the no-scroll property. Accepted and stated.
- R5 The same row caps at 1920 as at 1280: a player who sits close may prefer density. A
  "compact text" switch (force s = 1) is a later option.
- R6 The scale step jumps when a window is resized across a threshold: one repaint. Text size
  changes at the compact thresholds (875, 1050, 1400 px tall at a 16 px default); between a
  compact and a full threshold only the three evictions change.
- R7 Paging replaces scrolling with clicks on Build and items and Run; acceptable because
  neither is used in play. Settings has a rail (a second level); Checks shows by itself.
- R8 Events share the feed with trades: trades always win slots and carry the edge.
- R9 The guide line replaces the level and deaths text while it shows. It is an opt-in
  (Always); the default (On entry) keeps level and deaths on line 2 for everyone, and under
  Always a death or a level-up brings them back for 20 s.
- R10 93 `short` lines are authoring work; an unsure one stays empty, so coverage may be
  partial at first.
- R11 Wave 2 replaces most Play renderers: tests bound to today's DOM ids
  (`tests/test_a11y.py`, `tests/test_ux_review.py`, `app/test/*.test.js`) change with each
  step; TD-09 must leave only mount hooks in `web/app.js`.
- R12 The harness can tail the live log if built the tests' old way (evidence pack incident):
  TD-01 needs F-001 and never targets port 8960.
- R13 Map mode needs the live map-prefix sighting (F-061); until then C falls back to none.
Reverses if: a play state appears that needs two contexts at once in C; G1 cannot hold with
real strings at s = 1; players report hunting through Settings more than once a session; or
the corner map proves routinely covered by the 2-line HUD (the placement ruling's own clause).

Cut first, in this order, if effort must shrink: (1) the act moment card; (2) TD-18 card time
setting; (3) scale steps 1.5 and 2 (keep 1 and 1.25); (4) U re-rank (show the last 3 checks,
unranked); (5) the event rows of the feed (trades only); (6) pagers (cap each list at 10 rows);
(7) the Settings rail (keep today's folds inside the Settings tab, closed); (8) the compact
class (flow fallback under 1200 x 760, and the scale rule goes back to "largest s whose full
cockpit fits").
Never cut: TD-01, TD-02, TD-03, TD-05, TD-07, TD-08, TD-09, the region steps TD-10 to TD-16,
the 2-line HUD, dark by default.

## Design review record

Date: 2026-11-18. Reviewer: the repo's design-reviewer agent, against
`docs/design/0001-design-system.md`. Reviewed: the draft of this section and the amendment at
the end of design 0001.

Verdict on the draft: FAIL on the specification (one S1). The reviewer recomputed every colour
and contrast number and found them exact (`tests/test_design_contrast.py` 38 passed), found
the 1280 and 1920 sums and the column widths correct, and found no ToS floor, click-through,
non-focusable or one-card-slot violation.

Findings by severity (the verdict line counts S3 as 12; the list holds 14 S3 entries; all 27
entries were handled):

| Severity | Count | Handled |
|---|---|---|
| S1 | 1 | 1 fixed |
| S2 | 7 | 7 fixed |
| S3 | 14 | 12 fixed as asked, 2 fixed in part (declined parts below) |
| S4 | 5 | 5 fixed |

What changed:
- S1 compact U track (3.2, 3.8, G2, G4, the amendment): the draft's sum left one 8 px of
  padding out (58 px of content in a 52 px track). Region U pads 4 + 4 in the compact class:
  2 + 8 + 20 + 20 = 50 of 52. Region I's slack is stated per class (18 full, 6 compact) and G4
  asks for 16 and 6. Both compact sums re-checked: 592 + 108 = 700 and 740 + 135 = 875.
- S2 DOM order (3.9, section 9): one order in every class, bar, G, C, T, N, B, I, U, footer;
  grid placement only; the flow class keeps it.
- S2 card head rule (5.3, G11, amendment O7): three card kinds, each with its own first-line
  rule and an allow-list for the status words.
- S2 the 72-character rows (3.4, 3.9, section 9): character budgets per row at the narrowest
  column with the WCAG 1.4.12 spacing; context rows 52, title 38, and five more caps; a
  text-spacing probe switches rows to wrapping for names and other user styles; the test
  asserts both axes.
- S2 guide line default (5.2, 5.4, G-03, R9, amendment 7.2): On entry for everyone; Always is
  an opt-in; under Always a death or a level-up brings level and deaths back for 20 s; the
  "Died" row is in the amendment.
- S2 HUD line 2 width (5.1, 5.5, G10): 236 px inside the plate; 26 characters with a status
  word, else the deaths text drops; 27 for a word alone; measured strings in G10. The font
  metrics confirm the overflow the reviewer suspected ("Lv 100  999 deaths" plus a 15
  character word is 259 px).
- S2 wrapping card rows (section 4, amendment): list rows are one line; a "Full text" page of
  3 entries x 3 lines (2 x 4 compact) holds the wrapped text, with the arithmetic.
- S2 Settings height (section 4): pane arithmetic and a per-section table; at most 448 px of
  rows a section, paged beyond that.
- S3: reflow rules down to 320 px and two flow captures in G1; a compact class at every scale
  step, so a maximised 1080p browser keeps its text size (the 1366x768 laptop case is stated
  and tested as flow); N7 scoped to the cockpit classes at default text settings; "Old build"
  instead of "Stale"; "[>] reading"; "2 lv under"; "new" moved to the row's right-hand
  segment; accent stated as one meaning, whispers and the other dropped feed kinds listed
  with their twin; the per-row Dismiss kept; the notice state word raised to 20 px; the key
  hint shortened to "<key>: check an item"; one-line data credits kept on the cards that show
  the data and the bar status word made the way to "Stop reading Client.txt"; the CLAUDE.md
  entry for decision 0014 added to TD-23; the focus rule of the automatic return tied to the
  10 s grace and announced.
- S4: G6 recounted (7 controls, 13 with 5 trades, tabs not counted); rounding at s = 1.25
  stated with a 3 px floor; C7 names the two overlay tokens; the guide default no longer
  depends on the display count and the rail names are used exactly; the "New on Play" line is
  visually hidden.
- Found while fixing, not in the review: the event sentence cap is 38, not 42, because "new,
  14:02" widens the right-hand segment; the 34-character card line was checked against the
  new 14 px / 600 size and holds by font metrics (200 to 230 px of 236), with a rendered
  check in TD-05.

Declined, and why:
- S1, the alternative "trim C to give I back height": C is in the left column and I in the
  right, so it cannot help; the padding fix and the per-class G4 floor were used.
- S3 status words, in part: U's kept-check rows stay at 14 px. Three rows at 20 px need 78 px
  of rows against 60, and U is a review list whose verdict was already shown at 28 px in I.
- S3 "Stop reading", in part: no one-click Stop control on the bar. Revoke is 2 clicks from
  any tab (the status word, then "Stop reading Client.txt"). A one-click stop in the always
  visible bar invites a misclick that silently ends reading mid-session, and principle 5
  keeps switches in Settings.
- S3 thresholds, the suggested 56em (896 px) step: replaced by the compact class at s = 1.25
  (875 px), which needs no new track arithmetic.

Arithmetic re-check after the changes (overflow 0 px at every cockpit size): 1280x760: 100 +
8 + 228 + 8 + 204 + 8 + 96 = 652 and 100 + 8 + 68 + 8 + 360 + 8 + 100 = 652, + 108 = 760.
1920x950: 125 + 10 + 285 + 10 + 255 + 10 + 120 = 815 and 125 + 10 + 85 + 10 + 450 + 10 + 125
= 815, + 135 = 950. No region's content changed height except N's head (a 26 px line box in
the same 32 px row) and compact U (58 to 50 px).
