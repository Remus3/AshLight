# 03 - Target design

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).

Status: draft

Scope: the target look and behaviour of the dashboard (Play tab, tab set) and the overlay, the
type scale, the colour tokens, and the ordered steps (TD-nn) that get there. It is the judged
result of a three-design panel, corrected against the rulings and findings of
docs/plan/findings.json. The Game ToS floor (CLAUDE.md) is untouched and read strictly.

Reading the numbers: px figures are at scale step 1 (root 16 px) unless marked. [M] = measured
(evidence pack, notes 0040 / 0041 / 0043). [C] = computed for this section (WCAG 2.2 contrast
formula, layout arithmetic; script kept in `<sidecar>\Scratch\up-plan\td_check.py`). [D] = design
budget from the fixed line boxes of section 6; TD-01 must confirm every [D] figure with real long
strings before it is quoted as measured.

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
- G-03 (B): the guide line follows the display count (Electron `screen`): the whole stay with
  1 display, on entry only with 2 or more; setting Always / On entry / Never.
- G-04 (C): one-line 32 px trade rows. Taken further: the feed has 5 rows, so all 5 server
  trade slots (`state.py` TRADE_REQUESTS = 5) show on Play and no trade goes to "+N more".
- G-05 (B, with C's condition): `autoScale` reference 1200 DIP (F-162), and the decision 0002
  overlay budgets re-run in the same step (TD-06).
- G-06 (B): a Theme setting, Dark (default) / Follow Windows / Light (F-086). A's "forced dark,
  no choice" is dropped.
- G-07 (C): a staged item press, first card stage under 0.5 s (F-059, note 0048 R3).
- G-08 (C): a compact step between 1024 x 700 and the full cockpit instead of the scrolling
  fallback, with a written eviction order (section 3.8). Per judge J3 it is a table, not CSS-only.
- G-09 (B): slot priority and eviction are pure functions with an exhaustive table test
  (TD-02), next to A's browser captures (TD-01).
- G-10 (B): every height is labelled [M], [C] or [D]; TD-01 confirms the [D] figures.
- G-11 (A, kept and tightened per J2): rem scale steps chosen by width AND height; the root is
  a percentage (100% x s) and the queries are in em, so the user's default font size applies;
  fixed line boxes per type step; the 1 px borders are counted in every vertical sum.
- G-12 (A): an inset 3 px focus ring (outline-offset -3 px) that no region can clip.
- G-13 (B): on the automatic return to Play, focus moves to the Play tab only when it sat on the
  tab row; a card, trade or notice never moves focus (note 0044 F9, F-096).
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
step s). The step is chosen by media queries in em on width AND height, so a larger default font
moves the thresholds with it.

| Class | min-width x min-height | At a 16 px default | s | Root |
|---|---|---|---|---|
| flow | below compact | under 1024 x 700 | 1 | 16 px |
| compact | 64em x 43.75em | 1024 x 700 | 1 | 16 px |
| full | 75em x 47.5em | 1200 x 760 | 1 | 16 px |
| full | 93.75em x 59.375em | 1500 x 950 | 1.25 | 20 px |
| full | 112.5em x 71.25em | 1800 x 1140 | 1.5 | 24 px |
| full | 150em x 95em | 2400 x 1520 | 2 | 32 px |

- 1280x760: full, s = 1. 1264x821 (the client's default content size [M]): full, s = 1, 61 px
  of extra height. 1024x700: compact.
- 1920x950: full, s = 1.25, root 20 px. 950 / 20 = 47.5 rem: the vertical budget in rem is
  identical to 1280x760, so one arithmetic proves both.
- 1920x1080: s = 1.25, 130 px extra. 2560x1440: s = 1.5, 300 px extra.
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

    full, 1920x950, s = 1.25 (every figure x 1.25; all are multiples of 4 px, so all stay whole)
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

Today [M]: state c puts 1034 px of content into a 654 px column at 1280x760 (380 px over on the
left, 321 px on the right); 124 / 117 px over at 1920x950; idle is 541 / 311 px over.

Widths [C]: at s = 1 main padding 16 + 16, content 1248 px, column gap 12, columns 7fr / 5fr =
721 / 515 px. Strip cells: Zone 708 (flex) | Level 176 | Deaths 152 | Session 176, 3 gaps of 12.
At 1200 px wide: columns 674 / 482, zone cell 628. At 1920 (s = 1.25): padding 20 + 20, content
1880, gap 15, columns 1088 / 777, cells 1205 | 220 | 190 | 220. Compact at 1024: columns
572 / 408, zone cell 452.

### 3.3 Diagram (1280x760)

    +------------------------------------------------------------------------------------------+
    | BAR 52   AshLight  [Play] [Build and items] [Run] [Settings]   Emberdemo  [+] reading    |
    +------------------------------------------------------------------------------------------+
    | G 100  Zone                               | Level           | Deaths      | Session      |
    |        Clearfell                  12:41   | 4               | 1           | 0:42         |
    |        Act 1 - area level 4               | 2 under         | 1 this zone | 2 level-ups  |
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
Region heights therefore do not depend on font metrics or on string length. Every row is one
line with `nowrap` and an ellipsis as the last guard; the full text is in `title` and in the
row's twin. Each sum counts the region's 1 px border twice.

G strip, track 100 [D]: border 2 + padding 4 + 4 + label row 26 + value row 36 + sub row 26
= 98; slack 2.
- Zone: label "Zone" (20 px, muted); value = zone name 28 px / 700, one line, plus the zone or
  map timer at 20 px / 600 right-aligned in the same row (never clipped); sub (20 px) = act,
  area level, tags (hideout, "frozen 14:02", AFK, DND).
- Level: number 32 px / 700; sub = "2 under" with its glyph while under-levelled, else the
  class. Deaths: number; sub "1 this zone". Session: timer; sub "2 level-ups" or "4 maps, 5/h".
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
- Caps: 52 words; each body row is composed at 72 characters or fewer [D] (at 16 px in the
  697 px column that leaves room for the WCAG 1.4.12 letter-spacing override without the
  ellipsis); a guide entry that needs more than 7 rows fails a data test.

T feed, track 204 [D]: border 2 + padding 6 + 6 + head 26 + 5 rows x 32 = 200; slack 4.
- 5 fixed one-line row slots (32 px each; text line box 26).
- Trade row: a 4 px accent edge, the tag "Trade" (14 px / 600), then "<buyer> wants <item> -
  <price>" at 20 px (buyer 600); right-aligned at 16 px: stash tab, position, age. The item
  name takes the ellipsis. A repeated whisper refreshes its row (F-120).
- Event row (16 px): tag (Death, Level, Zone) + the sentence + local time.
- Head: "Trades 5" or "Recent", plus "Dismiss all" (24 px tall) while a trade is open.
- Cap 50 words.

N notice, track 96 [D]: border 2 + padding 8 + 8 + head row 32 + 2 body rows 44 = 94; slack 2.
- One notice. Head: glyph + word + short title (16 px / 600), at most 1 action button (32 px)
  right-aligned in the head row. "+2 more" is a text count; every queued notice also lives in
  Settings (Checks) or on its own card. Cap 22 words.

B build line, track 68 [D]: border 2 + padding 8 + 8 + row 26 + row 22 = 66; slack 2.
- Row 1: state glyph + word at 20 px / 600 ("[+] Build fits", "[?] Stale", "[?] Wrong class",
  "[ ] No build") + build name and level (16 px). Row 2 (16 px, muted): source and age, DPS /
  EHP when the calc is on; or the fix in one line, naming the press of F-042.
- The build alert is a STATE of this region, not a card in a queue: it can never push
  anything. One optional button "Paste a build" (24 px, row 1) only while no build is loaded
  (F-041); it shows Build and items and focuses the paste box. Cap 16 words.

I item check, track 360 [D]: border 2 + padding 12 + 12 + head 32 + 4 + sentence 44 + 8 +
compare (label 20 + 5 rows 110) + 8 + price row 26 + links row 28 + 8 + action row 28 = 342;
slack 18.
- Head: verdict word at 28 px / 700 with its glyph ("[+] Upgrade", "[-] Sidegrade",
  "[-] Downgrade", "[?] Risky", "[-] Not an item"), then the item name at 20 px, ellipsis.
- Sentence: 2 rows, starts with the reason; carries the build caveat while B is not "fits"
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
  memory only, Q-26 b), best first: glyph + word, gain, item, slot, time. A build or weight
  change re-orders it by itself. Empty: one muted line. Cap 24 words.

Bar, 52: mark and name; the 4 tabs (16 px); the character name and class (16 px, muted); one
status word, "[+] reading" (20 px; the worse of the reading state and the feed state, from the
one status table of F-131; neutral while ok, F-159). Footer, 32: the disclaimer sentence
(13 px, text colour) and the trademark sentence (13 px, muted) on one row; the two footer folds
(what AshLight does and never does, game data credits) move to Settings > About and data,
open; "Stop reading Client.txt" moves to Settings > Reading.

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
  GGG docs flag); (6) new-character tip (10 min); (7) key reminder "<key>: check a copied item",
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
    build alert up         live    as zone as queued       as queued    Stale/Wrong  caveat     any
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

| Region | Tallest mode | Content | Track | Slack |
|---|---|---|---|---|
| G | live | 98 | 100 | 2 |
| C | guide (setup 216, idle 204, error 198, town 192, map 182) | 226 | 228 | 2 |
| T | 5 rows | 200 | 204 | 4 |
| N | notice with action | 94 | 96 | 2 |
| B | any state | 66 | 68 | 2 |
| I | full card | 342 | 360 | 18 |
| U | 3 rows | 98 | 100 | 2 |

- 1280x760: left 100 + 8 + 228 + 8 + 204 + 8 + 96 = 652; right 100 + 8 + 68 + 8 + 360 + 8 + 100
  = 652; + 108 chrome = 760. Overflow 0 px in every state, because no state changes a track.
- 1920x950: every rem figure x 1.25: 815 + 135 = 950. Overflow 0 px. Inside a region the rem
  content grows x 1.25 while the 2 px of border do not, so the slack grows (never shrinks).
- 1264x821 (client default): 61 px extra, shared by C and I. 1024x700: section 3.8.
- Word total, worst case: 20 + 52 + 50 + 22 + 16 + 60 + 24 = 244 in the grid (today 397 [M]).

### 3.8 Compact class (1024 x 700 up to the full cockpit)

Same 7 regions, same order, s = 1, three evictions in this order:
1. N keeps its head row only (track 52: border 2 + padding 16 + head 32 = 50); notice kinds 6
   and 7 (tip, key reminder) are not shown.
2. C keeps 6 body rows (track 212: 2 + 24 + 26 + 132 + 20 = 204); setup drops its promise line.
3. U keeps the best kept check only (track 52: 2 + 8 + label 20 + 1 row 20 = 50).
Never evicted: the strip, the 5 feed rows, the build line, the verdict, sentence, compare rows
and price of I (track 348 for 342 of content).
Sum: left 100 + 8 + 212 + 8 + 204 + 8 + 52 = 592; right 100 + 8 + 68 + 8 + 348 + 8 + 52 = 592;
+ 108 = 700. Overflow 0 px.

### 3.9 Outside the cockpit: zoom, text spacing, small windows

- Flow class (under 64em x 43.75em; also 200 percent zoom and a 320 px wide window): one
  column in DOM order G, I, T, N, B, C, U, with one page scroll. This is the WCAG reflow path,
  not a play state.
- Text-spacing overrides (WCAG 1.4.12) and user style sheets: region tracks are minimums
  (`minmax(track, auto)`), no Play element clips on the block axis, and the page is the only
  scroll container. Under an override the tracks grow and the page scrolls; nothing is cut and
  no nested scroll box appears. In the tested states at default text settings no track grows.
- The no-scroll guarantee is therefore stated for default text settings at 1024 x 700 and up.

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
+ 26 + 176 + 28 = 256). Settings is a rail (220 px, 6 sections, one visible) and a detail pane
(1016 x 652 at s = 1; 760 x 592 compact), each section fitted to the pane [D].

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
2. Reading and web data - stop reading, the log path, the one web-data switch with contact and
   league, price book state.
3. Overlay - parts chooser with presets (F-118), corner, size, Background, zone guide (Always /
   On entry / Never), card time, sample card.
4. Keys - the real bound keys, change key (F-026).
5. Appearance and tools - Theme, autostart, settings transfer, restart overlay; "More": the
   graphics advisor.
6. About and data - what AshLight does and never does, game data credits, the trademark line,
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
the item card's sub-headings; per-row Dismiss on Play ("Dismiss all" stays). Hidden under
"More" pages: the `.build` download, the graphics advisor, settings transfer. Frozen (no
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
as long as it is due and yields at once to ranks 1-4.

### 5.3 Card slot (one card, 3 lines of 14 px, 34 characters each)

Holder, first match:
1. The press card (item verdict, price, waystone, "Build loaded: <name>", "Not an item", "Copy
   the item first"): from the press for the card time (20 s default; setting 20 / 60 / 200 s);
   the newest press wins; first stage under 0.5 s (F-059).
2. The newest open trade request, until it closes (accept / cancel line, dismiss, 10 min),
   with "+N" in its first line. It returns by itself when a press card leaves.
3. A moment card (F-119), 12 s, only into a free slot, never waiting, never interrupting: the
   zone card on the first entry of a guided campaign zone per game run, or the act card when
   an act split closes.
4. The key hint line "<key>: check a copied item" (F-166): until the first press or 3 game
   sessions.
5. Nothing: the card plate is absent. The sample card shows only on its Settings button (10 s).
Card grammar: line 1 = the answer (verdict word and size, or the buyer); line 2 = what (item
name; the price only when a poe.ninja value exists, F-163); line 3 = why or worth (top stat, DPS
/ EHP, where; the build caveat head while a build alert is set, F-043). The edge only repeats
the word: ok green for an upgrade, accent for a trade, warn for risky, neutral otherwise.
Never two cards. The card's near edge is anchored 62 px from the window's anchored edge (the
2-line HUD height 55.6 + 6), whatever line 2 shows, so a card never jumps.

### 5.4 Zone-guide line (S5-FOLLOWUP a)

- Text: the guide entry's new `short` field: authored, AshLight's own words, at most 34
  characters, for every guide entry (93 today [M]); empty when unsure. The overlay never reads
  the 120-character `line` (that stays the dashboard form). No `short`, no text.
- Two forms from the same field. The zone card (5.3 rank 3): line 1 = `short`, line 2 = bonus
  or "Next: <zone>", line 3 = level advice or boss element. The guide line: `short` on HUD
  line 2 (5.2 rank 5), 14 px, secondary colour.
- Setting "Zone guide on the overlay" (Settings > Overlay): On entry = the zone card only;
  Always = the zone card, then the guide line for the rest of the stay; Never = neither. With no
  stored choice it is Always with 1 display and On entry with 2 or more. The display count comes
  from Electron `screen` in the client; nothing looks at the game.
- Absent in maps, towns, the hideout and unguided zones. Twin: Play C (guide mode), no timer.

### 5.5 Heights [C]

HUD, 2 lines of 16 px: border 2 + padding 12 + 20.8 + 20.8 = 55.6 px (53.0 with the 14 px guide
line; 34.8 with 1 line). Card: border 2 + padding 10 + 3 x 18.2 = 66.6 px. Tallest content: 62
+ 66.6 = 128.6 px of 176 (47.4 px spare; today 125.6 [M]).

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
| `--fk-status-warn` | #d19a2a | #946200 | needs you: stale build, risky, under-level, blocked | 7.48 / 6.81 | 5.24 / 4.76 |
| `--fk-status-bad` | #f0605a | #c4262f | failed, lost, death | 5.83 / 5.31 | 5.73 / 5.21 |
| `--fk-status-idle` | #8a929b | #5b636c | idle, neutral verdict, pending | 5.96 / 5.43 | 6.09 / 5.54 |
| `--al-plate` | rgba(15, 18, 22, 0.86) | same | overlay plate (alpha 0.80 to 1.0) | section 5.6 | - |
| `--al-ovl-text-2` | #c3c9d0 | same | overlay secondary text | 7.59 worst | - |
| `--al-ovl-warn` | #f0bd55 | same | overlay warn word | 7.30 worst | - |

- Floors: every text pair at least 4.5:1 (lowest: light warn on a card 4.76; dark bad on a card
  5.31); non-text (control edges, focus ring, glyph strokes) at least 3:1 (lowest 3.53).
- One meaning per colour: ok = good or working; warn = act when you can; bad = failed, lost or
  a death; accent = news that wants a reply (a trade) and navigation. Trade rows move from
  amber to accent, so amber no longer sits beside the green / red pair.
- Never colour alone: every state is a glyph and a word from the kit vocabulary (`[+]`, `[ ]`,
  `[?]`, `[#]`, `[x]`, `[-]`, `[>]`; no AshLight-made glyph); one table maps states to words
  (F-131). Verdicts are words (Upgrade, Sidegrade, Downgrade, Risky). An edge only repeats it.
- Colour marks exceptions: the normal "reading" word, normal buttons and normal rows are
  neutral (F-159); red is never used for attention, prices or a downgrade.
- Stale is visible (F-087): `body[data-fresh="no"]` (idle, AshLight lost) draws strip values,
  timers and feed rows in `--fk-text-muted` and adds "frozen <time>" to the zone sub line.

## 8. Motion and attention

- Nothing moves on either surface: 0 CSS animations, 0 transitions, 0 scrolling or blinking
  text, no sound, no OS toast, no taskbar flash in play (F-095; kept as a test).
  `prefers-reduced-motion` therefore changes nothing.
- Urgency is encoded, in this order, by: (1) the region (trades always in T, build trouble
  always in B, broken parts in N, the asked-for answer always in I and in the overlay card);
  (2) glyph + word; (3) a 4 px left edge in the status colour (3 px on the overlay); (4) for
  60 s after arrival the word "new" after the row's first word (a text change, not motion).
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
  with no horizontal scroll; the client restores Ctrl + plus / minus / 0 (note 0044 F4).
- 1.4.12: section 3.9. A test injects the four text-spacing overrides and asserts that no
  element clips on the block axis and that only the page scrolls. One-line rows are composed
  under their caps; any row that still takes the ellipsis has its full text in `title` and in
  a keyboard-reachable twin.
- 2.1.1 / 2.4.3: every control by keyboard; focus order = bar, G, C, T, N, B, I, U, footer (DOM
  order = reading order). Regions do not scroll, so they need no tab stop; `#panel-play` loses
  its `tabindex` (F-096). One tab stop for the tab row (arrow keys, Home, End).
- 2.4.7 / 2.4.11: a 3 px accent ring drawn inside the element (`outline-offset: -3px`), never
  clipped by a parent (note 0044 F2); an outside ring only on the one filled accent button.
- 2.5.8: every target at least 24 x 24 px; buttons 32 px where the row allows (28 px in I,
  24 px in B and the T head); the two 20 px checkboxes grow to 24 (F-164).
- 2.2.1 / 2.2.2 / 2.3.1: section 8; nothing flashes, nothing advances by itself (pagers move
  only on a press).
- 3.2.1 / focus: a card, trade, notice or mode change never moves focus. The automatic return
  to Play moves focus to the Play tab only when focus sat on the tab row (G-13).
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
3. Stale by itself: 5 or more levels behind (or a class mismatch) turns B to "[?] Stale" /
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

Sizes: 1280x760, 1920x950, 1024x700, and 1264x821. States: pack states a, a2, b, c, c2, d, e,
f, g, plus "c + 3 more whispers" (5 trades) and a map state. All captures run on a demo core
that can never find the live log (F-001), never on port 8960.

- G1 No scroll: in every state at every size, the page overflow is 0 and no element under any
  tab panel has scrollHeight > clientHeight. Same for each card page and each Settings section.
- G2 Same place: each Play region's bounding box is identical (within 1 px) across all states
  at a given size, and equals the track table: 100 / 228 / 204 / 96 / 68 / 360 / 100 px at
  s = 1 (x 1.25 at 1920x950); 100 / 212 / 204 / 52 / 68 / 348 / 52 px compact.
- G3 Tables: a node test enumerates context mode (7) x open trades (0-5) x item card kind (5)
  x notice kind (8) x build state (4) x size class (compact, full) and asserts, without a DOM,
  that every region's row count fits its track, that all open trades have a row, and that the
  summed tracks equal the grid height.
- G4 Slack: in the worst state the content bottom of each region is at least 2 px above its
  inner edge; region I keeps at least 16 px.
- G5 Words on Play (inside the grid): at most 250 worst case (today 397), per region 20 / 52 /
  50 / 22 / 16 / 60 / 24; at most 150 in a plain campaign zone; at most 110 on first run.
  Visible elements at most 100 (today 133).
- G6 Controls on Play: at most 8 visible (at most 4 in I, 1 in each other region), all at
  least 24 px, none required to read a value.
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
- G10 Overlay shape: window 280 x 176; content height at most 130 px; at most 2 HUD lines and
  1 card; zone line at most 28 characters, every other line at most 34; every guide `short`
  at most 34 characters or empty; the overlay never renders `line`; minimum 14 px; 0
  interactive elements; 0 animations.
- G11 Overlay rules: a table test of `hudLine2` (7 ranks) and `cardHolder` (5 holders); every
  card head starts with the verdict word or the buyer; the card's near edge is at 62 px in
  every state; every self-leaving card kind has a twin selector.
- G12 Tabs: exactly 4 `role="tab"` elements; news shows Play with 0 acts; Play has at most 4
  live regions; focus follows the automatic return only from the tab row.
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
  long-string fixture: 40-character names, 5 trades, the longest guide entry). Proof: G1 is
  red on today's layout (state c, 380 px over); each region's expected-fail entry is removed by
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
  5.2, in the same commit as the CSS). Proof: G8 overlay part. Needs: TD-03, TD-04.
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
  `app/overlay/overlay.js`, `app/main.js` (display count from Electron `screen`, sent with
  the layout), `tests/test_overlay_layout.py`, `tests/test_budgets.py`,
  `app/test/overlay_gate.test.js`. Proof: G10, G11. Needs: TD-02, TD-05, TD-07, TD-08, F-088,
  F-118.
- TD-18 Card time setting. Files: `server/al/state.py`, `server/al/settingsio.py`,
  `server/al/layout.py`, the Settings > Overlay control. Proof: a unit test of 20 / 60 / 200
  with 20 the default; the twin test. Needs: TD-17. Optional (cut list item 2).

Wave 3 - tabs (serial: all three rewrite parts of `web/index.html`):
- TD-19 Four tabs and the Build and items grid. Carries F-067, F-056. Files: `web/index.html`,
  `web/tabs.js` (name map), `web/pager.js` (new), `web/app.css`, `web/prices.js`,
  `web/pricewatch.js`, `app/test/tabs.test.js`. Proof: G12; G1 for the tab.
- TD-20 Run grid. Files: `web/index.html` (Run panel), `web/history.js`, `web/runs.js`,
  `web/acts.js`, `web/app.css`. Proof: G1 for the tab in states f and g.
- TD-21 Settings rail and index; footer folds move. Files: `web/index.html` (Settings panel,
  footer), `web/rail.js` (new), `web/checks.js`, `web/app.css`. Proof: G1 for each section;
  every index entry jumps to and focuses its control; the disclaimer is still in the footer.
- TD-22 Accessibility pass. Carries F-096 (focus), F-121, F-151, F-164. Files: `web/app.css`,
  `web/tabs.js`, `app/client/window.js` (zoom keys), `app/test/cdp/a11y.mjs` (new),
  `tests/test_a11y.py`. Proof: the browser test of section 9 (ring box, forced-colours tab,
  target sizes, live-region count, text-spacing run). Needs: TD-19 to TD-21.

Wave 4 - records:
- TD-23 Records. Files: `docs/design/0001-design-system.md` (sections 3, 4, 5, 6, 7.2, 9, 10,
  11 rewritten from the amendment of 2026-11-18; the amendment section is then removed), a new
  decision "fixed cockpit Play, four tabs, dark by default" (alternatives: designs B and C, the
  three-tab set; reverses if: section 14), dated amendments of decision 0014 (card slot
  holders, card time, the guide line on HUD line 2) and of the placement ruling's record (the
  HUD is still 2 lines), `docs/design/reviews.log`. Proof: the docs lint,
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
  region; region I holds 18 px in reserve.
- R3 F-053's size test and F-066's "40 px spare" budget are restated (sizes in rem; spare
  replaced by G2 and G4). The execution plan must carry the restated acceptance.
- R4 A fixed grid fights user text settings: handled by section 3.9, but a zoomed viewer loses
  the no-scroll property. Accepted and stated.
- R5 The same row caps at 1920 as at 1280: a player who sits close may prefer density. A
  "compact text" switch (force s = 1) is a later option.
- R6 The scale step jumps when a window is resized across a threshold: one repaint.
- R7 Paging replaces scrolling with clicks on Build and items and Run; acceptable because
  neither is used in play. Settings has a rail (a second level); Checks shows by itself.
- R8 Events share the feed with trades: trades always win slots and carry the edge.
- R9 The guide line replaces the level and deaths text while it shows (1-display default).
  The parts chooser and the Always / On entry / Never setting are the remedy.
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
class (flow fallback under 1200 x 760).
Never cut: TD-01, TD-02, TD-03, TD-05, TD-07, TD-08, TD-09, the region steps TD-10 to TD-16,
the 2-line HUD, dark by default.
