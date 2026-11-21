# 0001 - AshLight design system

Status: accepted 2026-11-16 (operator order 2026-11-16). Owner of reviews:
the `design-reviewer` agent (`.claude/agents/design-reviewer.md`). First
audit: `docs/design/0002-first-audit.md`.

**NLM** means natural-language messaging: how AshLight phrases events,
statuses and notifications as short natural sentences, and the rules for
making that text from log events (section 9; ruling Q-15, 2026-11-18).

## 1. Scope and sources of truth

- Surfaces: the second-screen dashboard (`web/`), the overlay HUD
  (`app/overlay/`, `app/shared/`), and every user-facing string the core
  produces (`server/al/state.py` `summarize`, status words in `web/app.js`).
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

Dashboard (root 16px; rem values are the source):

| Token (proposed) | Size | Weight | Use |
|---|---|---|---|
| `--al-fs-caption` | 0.8125rem (13px) | 600-700 | uppercase kind tags only; the floor |
| `--al-fs-label` | 0.85rem (13.6px) | 600 | stat labels (uppercase, 0.05em tracking) |
| `--al-fs-small` | 0.9rem (14.4px) | 400 | pills, form labels, footer |
| `--al-fs-body` | 1rem (16px) | 400 | body, card titles (700) |
| `--al-fs-sub` | 1.6rem (25.6px) | 600 | zone timer |
| `--al-fs-zone` | clamp(1.5rem, 4.5vw, 2.4rem) | 700 | zone name |
| `--al-fs-glance` | clamp(2rem, 6vw, 3.25rem) | 700 | level, deaths, session |

Rules: nothing under 13px; line-height 1.4 for body, 1.1 for glance
numbers; uppercase only for labels of 3 words or fewer.

Shell sizes (UI-GLANCE): at 900px wide and 560px tall or more the Play
tab is two columns, so the glance sizes scale with the column, not the
window: glance numbers clamp(2rem, 2.6vw, 2.75rem), zone name
clamp(1.5rem, 2.2vw, 2.25rem), zone timer 1.3rem; tiles pad 8px 12px
(4px 10px at 820px tall or less), stat sub lines 0.9rem, footer 0.8125rem.

Overlay (CSS px at zoom 1.0; the window zoom is the layout `scale`). Two
sizes only, both weight 600, line-height 1.3, tabular numerals, set by two
tokens in `app/overlay/overlay.css` (TD-05, OVL-TD05-LEGIBILITY):

| Token | Size | Roles |
|---|---|---|
| `--al-ovl-fs-hud` | 16px | HUD lines: zone line, zone timer (full text colour, never clipped), level and deaths, the status word |
| `--al-ovl-fs-card` | 14px | card lines: trade card, item check card, price card (the guide line and key hint take it when they land) |

Nothing on the overlay is under 14px. Overlay rule: rendered text never
under 12px **after** zoom, so the smallest overlay size times the minimum
`scale` must be >= 12px; with 14px that means `scale >= 0.86`.

## 4. Spacing and shape

- 4px grid: 4, 8, 12, 16, 24, 32. Cards pad 16px; stat tiles 12px 16px;
  gaps 16px (8px under 600px width).
- Radius: 8px cards, 6px controls and overlay plates, 999px pills.
- Hit targets on the dashboard: at least 24x24 CSS px (WCAG 2.2 SC 2.5.8);
  aim for 32px tall buttons.
- The layout must work at 320px width (dashboard on a phone or a narrow
  second screen) with no horizontal scroll.
- Tabs (UI-GLANCE, 2026-11-17; replaces the UX-NARROW fold): the
  dashboard is five tabs in the header (ARIA tablist, web/tabs.js): Play,
  Run and history, Build, Items and prices, Settings. Play is the glance
  tab: zone tile with its guide (zone tip, the `#zone-guide` slot;
  campaign hints are hint rows of context region C), level / deaths /
  session, the `#build-alert` slot, trades, the new-character tip, and the item card (verdict, upgrade
  search, price). Both slots are filled only through
  `ALTabs.fill(document, id, node)`. The picked tab is remembered per
  viewer (localStorage, try/catch). ZERO-CLICK: a new item card, trade
  request or build alert shows Play by itself unless focus is inside the
  shown tab (the player is working there); then Play carries the word
  "new". Settings carries "fix" while a self-check needs one. No focus
  moves, nothing animates; the selected tab is bold with a bar and
  aria-selected (never colour alone). Arrow keys, Home and End move
  between tabs (one Tab stop for the row).
- App shell at 900px wide and 560px tall or more: the page never scrolls;
  Play is two columns (glance left, item card right) and every tab's
  columns scroll on their own. Headless Chrome read back (synthetic
  session, 2 trades, 3 item checks): 1920x950 Play left column fits
  exactly, 1280x760 is within 26px with two open trades; the item card
  scrolls inside its column below the verdict; each column is a
  labelled group with tabindex 0 so it scrolls from the keyboard. Under
  820px tall the tiles tighten further. The game-data credit (decision
  0009) is a footer fold, shown only while snapshot data exists, so the
  footer stays one or two lines; the GGG disclaimer and trademark lines
  stay open in the footer.
- Auto-switch grace: a click, key press or scroll inside the shown tab or
  the tab row holds that tab for 10 s; a new item card, trade or build
  alert in that time marks Play "new" and the header line says once
  "New on Play: <what>." (a polite region outside the panels, since
  Play's own regions are silent while it is hidden). When the game has
  focus Play is always shown. Build-alert nodes carry their own words.
- Narrow side window (under 520px width): main and card padding 12px,
  main gap 12px; below the shell the page flows in one column in DOM
  order (Tab order = screen order), the tab row wraps under the brand.
  Status lines in a hidden tab speak once that tab is shown, after the
  player's own click there (paste, copy, a setting, a save).

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
`border` edge (#323840) is decorative only. Interim until OVL-TD05-PLATE:
the overlay CSS has no page opacity, but `app/main.js` still inserts the
layout's page opacity (`layout.js` LIMITS.opacity, 0.9 to 1.0) over the
whole window; at its 0.9 floor with the 0.86 plate the white-scene values
are text 7.69, secondary 5.86, warn 5.68, still above the old 4.5:1 floor
that `tests/test_ux_review.py` keeps checking until the slider sets the
plate alpha only. High-contrast mode (`prefers-contrast: more`) lifts
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
  by colour, also a shape cue (left rule, border).
- Never pair red and green as the only difference between two adjacent
  things. Where a categorical palette is needed (charts), use the kit
  `chart` palette with direct labels, or Okabe-Ito hues (source 5).
- Test new colour pairs in a deuteranopia / protanopia simulator before
  merging (Chrome DevTools: Rendering > Emulate vision deficiencies).

### 5.4 Light and dark

The dashboard follows `prefers-color-scheme` through the kit tokens.css and
honours `data-theme` overrides. Every colour reference is a `var(--fk-*)`
or `var(--al-*)`; no literal hex in component CSS. The overlay is always
dark (5.1).

## 6. State-colour semantics

Kit state vocabulary (tokens.json `states`) mapped to AshLight meanings:

| AshLight condition | Kit state | Glyph | Token | Example word |
|---|---|---|---|---|
| reading Client.txt | running | [>] | status-running | reading Client.txt |
| dashboard feed live | done | [+] | status-ok | live |
| connecting / reconnecting | pending | [ ] | status-idle | reconnecting |
| opted in but file missing / quiet | blocked | [#] | status-warn | waiting for Client.txt |
| opted in, no log line for 20 min (TEST-LIVE-EXIT, decision 0029) | blocked | [#] | status-warn | quiet for 20 min - game closed or AFK? (the overlay hides in this state, decision 0029 amendment 2026-11-17; the dashboard Tools card says "Overlay hidden: no game activity for 20 min. It comes back with the next log line.") |
| not opted in | idle | [-] | status-idle | not reading Client.txt |
| cannot reach AshLight | failed | [x] | status-bad | can't reach AshLight |

Event semantics (dashboard list and overlay card):

- trade request: `status-warn` edge + `TRADE` tag. Warn means "needs you
  soon", not "error".
- trade accepted / cancelled: muted `TRADE` tag, no edge.
- whisper: `accent` edge + `FROM` / `TO` tag.
- death: `status-bad` tag `DEATH`; never a full red row (a death is news,
  not an alarm).
- level up, zone: muted tag only.

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
  click-through.
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
| In a map / zone | zone, time in zone, level, deaths | glance stats |
| In town or hideout | zone with "(HO)" tag; trade card if any | recent events, trades |
| Trade request arrives | trade card (who, what, price, where) | trade list with dismiss |
| Died | deaths count changes; no flash, no pop-up | death in recent events |
| AFK / DND | status word on the HUD line | flag under Session |
| Under-levelled for the zone (UTIL-UNDERLEVEL) | status word `N lv under` (gap at or above the setting, default 3) | line under the Level tile naming the zone level (the tile already shows the player level; UX-B9-CARDS) |
| Not reading / offline | one status word ("offline") | pill with the fix |
| Item check hotkey pressed | item check card for 20 s (verdict, item, top stat) in the card slot | Item check card (Play tab, right column) with every compared slot; the stat weights it adds up are in the Item check scoring card (Items and prices tab); a new card shows Play by itself |
| In a map (UTIL-MAPS, UTIL-MAPRUN-OVL) | row-1 timer is the time in this map (kept across hideout trips) instead of this zone instance; no new line or word; map deaths stay on the dashboard | Maps card: open map time (counts only while in the map, `(paused)` outside), last 5 maps, average |
| Died (UTIL-DEATHS) | no change | Death recap card: newest first, local time, zone and level |
| In a campaign act (HUD-ACT) | no change | Act times card (Run and history tab): splits, zone levels for the current act; in endgame the splits stay, the zone table empties |
| Waystone check (UTIL-WAYSTONE-REWARD) | reward line (`+38% rarity, +12% pack`) replaces the item name in that card | `Rewards: ...` sentence under the risk sentence in the Item check card |
| Campaign hint (UTIL-CAMPAIGN-CHECKS) | status word, last in the slot order (`Cold res 32%`, `Better flask`, `Boots: no speed`, `Boss: cold`) | Up to 3 hint rows in the Play tab's context region C (web/context.js): the boss row as `Boss: <element> damage. Your <element> res: N%.`, the gear rows as their sentence, each sentence in the row's title; a guide block carries its own (PLAY-CAMPAIGN-HINTS-C) |
| Price check from the same press (web data on) | price line replaces the item name in that card; price-only card when no build is loaded (decision 0016) | Price section in the Item check card, listings with "about N <primary>" |
| Item check from the same press | none on the overlay | Upgrade search sub-section under the item check (TC-UPGRADE) |

Progressive disclosure (source 9): the overlay holds the 2-line HUD plus at
most one trade card ("+N more" for the rest). Everything else (history,
stash coordinates in full, settings) lives on the dashboard. Never add a
third HUD line to fit a feature; add a dashboard card instead.

Dashboard density (UX-DASH-DENSITY, glance review 0004 U26): play cards
come first and stay open. Set-once tools (overlay position, moving
settings, graphics settings) live in one folded Tools card on the
Settings tab, with the hotkey hint outside the fold. A tool made from one
card's content (the .build file from the Build card, the loot filter
add-on from the Search strings card) folds inside that card instead, so it
stays beside what it is made from and hides with it. A destructive action
(Clear ...) is a secondary button, never the filled primary style.

## 8. Voice and tone (prose and readability)

Rules (sources 10, 11, 12):

1. Plain English, about a 9-year-old reading age. Short words, short
   sentences (dashboard prose <= 20 words a sentence).
2. Sentence case everywhere except uppercase kind tags.
3. Present tense, active voice, subject first: "Quietfox wants Plain Belt".
4. Use the player's words (zone, hideout, level, trade, whisper). Never
   expose internals: "core", "token", "SSE", "tailer", "HTTP 500" in the
   main line.
5. Errors say what happened, then what to do. Never blame the user. No
   exclamation marks, no ALL CAPS shouting, no "Oops".
6. Numbers as digits; units with a space ("12 deaths", "3m").
7. Front-load the key word so a truncated line still makes sense.
8. ASCII only (FLEET item 8): "..." not an ellipsis character, "-" not a
   dash, straight quotes.
9. Empty states explain what will appear and when.

Good / bad examples:

| Bad | Good | Why |
|---|---|---|
| token rejected or core stopped | can't reach AshLight - restart it | no internals; gives the fix |
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
one place (`server/al/state.py`: `summarize`, `trade_card_text`, and for
the item check `eval_card_text` / `stat_delta_text`) and the overlay formats in
`app/shared/format.js`; no other site invents event wording.

Generation rules:

1. **Deterministic templates, no language model.** Text is built from
   fixed templates and the event's own fields; the same event always gives
   the same words. Nothing is sent off the machine to phrase text.
2. **One event, one sentence**, subject first: `<who> <verb> <what>`.
   Example templates:
   - level up: `<character> reached level <n>`
   - death: `<character> died` (suicide: `<character> died (self-inflicted)`)
   - zone: `Entered <zone>` (hideout: `Entered <zone> (hideout)`)
   - trade: `<from> wants <item> - <price>` (no price: `- no price set`)
   - whisper in / out: `<from>: "<text>"` / `To <to>: "<text>"`
   - AFK / DND: `You're AFK` / `You're back`, `Do not disturb on` / `off`
   - party: `<character> joined the area` / `<character> left the area`
   - log state: `Reading Client.txt`, `Client.txt was reset (<reason>)`;
     the game's server connect line is not listed (it came before every
     zone, UX-COPY); overlay status slot before the opt-in `not reading -
     see dashboard` (UX-FIRSTRUN), opted in `waiting for log` when
     the file is known but quiet (15 characters at most next to the
     numbers), `no Client.txt` when it is not found
     (UX-COPY); dashboard deaths tile before the opt-in `-` over `Counts
     once reading starts` (UX-FIRSTRUN)
   - item check (TC-EVAL-UI): overlay head `<Verdict> <+delta> vs <slot>`
     (empty slot: `<Verdict> <+delta> - <slot> empty`), item name, top
     counted stat (`+35 to maximum Life`; a flag mod `Gains: <mod>` /
     `Loses: <mod>`); dashboard `Upgrade: <n> points more than your <slot>
     (<name>).`, `Downgrade: <n> points less than ...`, `Sidegrade: about
     the same as your <slot> (<name>), <+n> points.`; errors `No build
     loaded`, `Not an item`, `Can't compare this` with the next step;
     a press that held a copied build (TC-PRESS-BUILD) is a status card:
     word and head `Build loaded` (edge tone note, never colour alone),
     line 2 `<ascendancy or class>, level <n>`, line 3 `Item checks use it
     now`, one dashboard note naming the build and character; a share link
     not loaded reads `Build not loaded` (word `Not checked`), `See the
     dashboard`, with the reason as the dashboard note
   - item check scoring source (TC-DELTA, decision 0024, `_calc_text`):
     when Path of Building scored the item the overlay third line is `DPS
     <+pct>%, EHP <+pct>%` (a 0 base reads `unknown`) and the dashboard adds
     `Path of Building: this item in <slot> replaces <name>. DPS <+pct>%
     (from <old> to <new>). EHP <+pct>% (from <old> to <new>).` (`this item
     goes in the empty <slot> slot.` for an empty slot; `(the better of the
     <n> slots it fits)` after the slot when it fits several; MATH-COMPARE,
     decision 0032) and each other compared slot shows `Path of Building:
     DPS <+pct>%, EHP <+pct>%.` under its sentence; when PoB's numbers make
     no sense (MATH-DPS-SANITY) it adds `Scored with your stat weights. DPS
     and EHP are not shown because Path of Building's numbers for this item
     don't add up. Try the check again.` (implausible); when PoB says the
     main skill cannot use the checked weapon type (MATH-WEAPON-TYPE,
     decision 0032 amendment) the overlay head is `Downgrade - wrong weapon
     type`, the third line `Main skill can't use this weapon`, the dashboard
     adds `Your main skill can't use this weapon type, so this item is a
     downgrade for this build. Path of Building counts no damage from
     <skill> with it in <slot>.` (`that skill` without a name) and that
     slot's sentence reads `Downgrade: your main skill can't use this weapon
     type in <slot> (<name>).` (no name for an empty slot); otherwise the dashboard
     adds `Scored with your stat weights. To see DPS and EHP, turn on the
     optional Path of Building calc in AshLight's settings file.` (off) or
     `Scored with your stat weights. DPS and EHP are not shown because Path
     of Building could not be reached. Try the check again.` (failed); with
     PoB scoring, uncounted mods read `Not counted (the mod has no number):
     <mods>.`
   - cached PoB weights (MATH-WEIGHTS, `CALC_CACHED_TEXT`): with the calc
     off or failing but weights Path of Building measured earlier for the
     same build, the dashboard adds `Scored with the stat weights Path of
     Building measured for this build earlier. DPS and EHP are not shown
     because the Path of Building calc is off.` (off) or `... because Path
     of Building could not be reached. Try the check again.` (failed) or
     `... because its numbers for this item don't add up. Try the check
     again.` (implausible); uncounted mods read `Not counted (Path of
     Building has not measured
     these for this build yet): <mods>.`
   - build alert and upgrade notices (BUILD-LIVE, decision 0045,
     `build_alert_text` / `upgrade_notice_text` / `upgrades_text` in
     state.py, shown by web/buildlive.js in the #build-alert card titled
     `Your build`, hidden when the build fits and nothing is an upgrade;
     not a live region): `No build saved for <name> yet. Paste a PoB code
     on the Build tab to check items for <name>.`, `Build is for a
     <class>, but <name> is a <class>. Paste <name>'s own PoB code so item
     checks fit.`, `Build is from level <n>; you are level <n>. Paste a
     fresh PoB code to keep item checks right.`; list `Upgrades from items
     you checked`, `1 item you checked is an upgrade now.` / `<n> items you
     checked are upgrades now.` (no list and no text with none), rows `New upgrade for <slot>: <item>` (or
     `Upgrade for ...`), `Replaces <name>, <+n points|+n%>.` / `Goes in
     your empty <slot> slot, <delta>.`, fit `Fits your <class> build.` or
     `Needs level <n>; you are level <n>.` The card clears by itself when
     the build is fixed (re-pasted, or the character's file changes) or a
     re-score drops the item; no timer and no dismiss button.
   - price and points (MATH-VALUE-UI, web/prices.js `valueView`): `Asking
     price: <n> <currency>, about <n> <primary>.` (`Buyout price: ...` for
     a b/o note; no "about" when already the primary), `<n> points per
     <primary>.`, `These currency values may be out of date.`, the
     poe.ninja credit; without rates `No currency values are saved yet, so
     AshLight can't compare the item's price with its points.`, without a
     rate for that currency `There is no saved value for <currency> yet,
     so AshLight can't compare the item's price with its points.`; hidden
     when the item has no note price.
   - roll potential (MATH-POTENTIAL-UI, web/tc.js `rollsText`): muted line
     on the item check card, `Rolls: worth <n> points now, <n> at the worst
     and <n> at the best, so <pct>% of the way up.`; at the top `Rolls:
     worth <n> points now, the best these rolls can be.`; hidden when there
     is no spread, the numbers are junk or the check failed.
   - price check (PRICE-1-UI, `price_card_text`): overlay `Price: <item>`,
     `<n> listed, ~<middle>` / `Lowest <amount> <currency>`, `Searching
     prices...`, `Prices in about <n> s`, `Web data is off`, `No listings found`,
     `Price check failed`; dashboard `<n> listed in <league>. The cheapest
     is <a>; the middle of the <k> cheapest is <b>.`; the one card is
     chosen by `overlay_card` (decision 0016)
   - open trade count (UX-REVIEW F1, `format.js tradeCount`): HUD status
     slot `1 trade` / `<n> trades` while a card hides the trade card;
     slot order: connection, Client.txt state, trade count, under-level
     word (UTIL-UNDERLEVEL `N lv under`, at most 11 characters), AFK / DND,
     campaign hint word (UTIL-CAMPAIGN-CHECKS, at most 15 characters)
   - new trade request (UX-REVIEW F6, `web/trades.js`): dashboard polite
     live region `New trade request from <from>.` (no name: `New trade
     request.`; several at once: `<n> new trade requests.`), only when the
     set of open trade ids grows
   - act times (HUD-ACT, `server/al/acts.py`, `web/acts.js`): dashboard
     only; rows `Act <n>` / `Cruel Act <n>` / `Interlude <n>` with `Time in
     act` and `Run total` (m:ss or h:mm:ss); one note per row in one pair of
     parentheses: `(now)`, `(partial)`, joined with ", ", and under the
     table, when a row is partial, `Partial: counted from the first zone
     AshLight saw.` (UX-NEW-CARDS); zone heading `Zone levels in <act>`, zone notes `(you
     are here)` / `(town)`; empty `No act times yet. They start by
     themselves when you enter a campaign zone.`, `Zone levels show here
     while you are in a campaign act.`, `Zone levels aren't downloaded yet.
     Run AshLight's build step (scripts/build.ps1) to get them.`, and in
     an act the downloaded table lacks (UTIL-1.0-FIXTURES) `Zone levels for
     <act> aren't downloaded yet. They show here once the game data has
     them: after a game update, run AshLight's build step again
     (scripts/build.ps1).`; source
     line `Zone levels: RePoE fork export, downloaded when AshLight was
     built. Game data (c) Grinding Gear Games.` (decision 0020)
   - map runs (UTIL-MAPS, `server/al/runs.py`, `web/runs.js`): dashboard
     only; rows `<map>` with `Level` (missing: `unknown`), `Time in map`
     (m:ss or h:mm:ss) and `Deaths` as a bare count (UX-NEW-CARDS: the
     words ran into the time at 320 px); open row note `(now)` or
     `(paused)`; summary `Average map: <m:ss> over <n> finished map(s).`
     then `<n> death(s) in maps.` or `No deaths in maps.`; empty `No maps
     yet. Map times start by themselves when you open a map.`
   - level pace (UTIL-PACE, `server/al/pace.py`): dashboard only, one
     line under the Level tile, hidden while empty, key word first:
     `Pace: about <m:ss> a level over the last <n>, <x.x> levels an
     hour.` (one level: `about <m:ss> for the last level`; `1.0 level an
     hour`; the hourly part needs 2+ level-ups seen live and 10 minutes
     since AshLight started; m:ss matches the dashboard timers; shortened
     for 320 px, UX-NEW-CARDS)
   - death recap (UTIL-DEATHS, same files): dashboard only; one line per
     death, newest first, `HH:MM` local time then `Died in <zone> (area
     level <n>) at level <n>, <m:ss> into the zone.` (parts without data
     are left out; no zone: `Died at level <n>.`); `Most deaths: <zone>
     (<n>).` from 2 deaths in one zone; empty `No deaths this session.
     Each one shows here with its zone and level.`; deaths counted
     before AshLight started reading (LIVE-RESUME restores the count,
     not the details): empty `<n> death(s) came before AshLight started
     reading, so their zones aren't known. New deaths show here with
     their zone and level.`, else `<n> death(s) came before AshLight
     started reading.` after the worst-zone line (UX-NEW-CARDS)
   - last session (UTIL-SESSION-SUMMARY, `server/al/summary.py`,
     `web/summary.js`): dashboard only, hidden until the first card; lines
     `Played <m:ss|h:mm:ss> and reached level <n>.` (no levels gained: `at
     level <n>`; no level known: `Played <t>.`), `Levels: <a> to <b>, at
     <x.x> an hour.` (pace from 10 minutes of play), `Maps: <n>.`,
     `Deaths: <n>.`, `Price movers: <name> up|down <n>%, ...` (top 3 by
     size); then `Session ended at <HH:MM> after 20 minutes with no game
     activity.` / `... when the game closed.` (date added for an older
     card); not a live region (not urgent, never announced; reachable via
     its labelled `Last session` heading; keeps the 12-region cap)
   - upgrade search (TC-UPGRADE, `web/prices.js upgradeView`): dashboard
     only, `Your build wears <base> in <slot>, so this finds rare items of
     that base.` (empty slot: `Your build has nothing in <slot>, so this
     uses the checked item's base, <base>.`) then `It matches base type and
     rarity only, not stats.`; link `Search the official trade site for
     rare <base> (<slot>)`
3. **Player text is quoted, never rewritten.** Whisper bodies and names
   are shown verbatim (textContent only, never innerHTML), clipped with
   "..." at the line limit.
4. **Missing fields read honestly**: "level unknown", "character unknown",
   "no price set" - never "None", "undefined", "?" or an empty gap.
5. **Overlay register is telegraphic**: drop verbs and articles when a
   line must fit (`Lv 12 | 3 deaths`, `Trade: Quietfox`). The dashboard
   register is the full sentence.
6. **Line limits**: overlay zone 28 chars, trade card and item check card
   34 chars per line;
   dashboard event lines wrap, never truncate.
7. **Plurals are correct**: `1 death`, `2 deaths`, `1 level-up`.
8. **Time words are relative on the overlay** (`3m`, `1h05m`) and local
   clock time on the dashboard (`14:05`).
9. **Notifications are passive.** A new event changes text in place; it
   does not pop up, chime or take focus. At most one overlay card is new at
   a time.
10. Every new template gets a unit test of its exact output.
11. Waystone rewards (decision 0039): `Rewards: +N% item quantity, +N%
    item rarity, ...` / `Rewards: none found in the item text.` /
    `Rewards: identify it to see them.`; overlay `+N% quantity, +N% rarity
    +K more` (34 chars). Campaign hints: `This zone's boss deals mostly
    <element> damage. Your build has N% <element> resistance (the cap is
    75%).` (or `(at the cap)`, or `... resistance is unknown.`), `A(n)
    <base> can drop at your level; your build has a(n) <base>.`, `Your
    build's boots have no movement speed. Boots with it help in the
    campaign.`; words `<Element> res N%`, `Boss: <element>`, `Better
    flask`, `Boots: no speed` (15 chars).

## 10. Overlay rules

- Window: separate, transparent, always-on-top, click-through,
  non-focusable (CLAUDE.md). It exists only while the desktop client runs
  and hides while the game looks closed (decision 0041; decision 0029
  amendment 2026-11-17). Base size 280 x 176 DIP at scale 1.0
  (`app/shared/layout.js` BASE); HUD plates max-width 258px.
- Content cap: 2 HUD lines + one 3-line card. Nothing else. The card slot
  holds the trade card, or for 20 s after the item check hotkey press the
  item check card (TC-EVAL-UI; the player just asked for it), after which
  the trade card comes back by itself. Never two cards at once. A price
  check from the same press shares that card (decision 0016: merged card,
  or the price-only card when no build is loaded).
- Plate: `--al-plate` (86 percent by default, `--al-plate-a` 0.80 to 1.0)
  with a 1px kit-border edge and the halo `0 0 2px #000, 0 0 2px #000,
  0 1px 2px #000`, no stroke (`--al-halo`; source 4: outlines and shadows
  separate text from busy scenes). Text is opaque. In high-contrast mode
  (`prefers-contrast: more`) the plate is opaque and secondary text takes
  the text colour (audit 0004 U3). In Windows forced colours the plate is opaque
  Canvas, text and edges take the system theme (the trade, upgrade and
  risky-waystone edges use Highlight; elsewhere the risky waystone edge
  is status-warn, audit 0004 U24), the page root opts out so the window stays
  transparent, and contrast is the theme's own, not measured here; the
  window opacity slider still multiplies (audit 0004 U8).
- Opacity: overlay text pairs >= 7:1 at the default plate and >= 5.5:1 at
  the alpha floor over a white scene, card edges >= 3:1 (5.2). Decorative
  transparency comes from the plate, never from fading the text; the
  overlay CSS has no page opacity (until OVL-TD05-PLATE, main.js still
  inserts the layout's 0.9 to 1.0 page opacity, 5.2).
- Size: two sizes, 16px HUD and 14px card; >= 12px after zoom (section 3).
- No flashing, ever (WCAG 2.3.1; the overlay is in peripheral vision during
  combat). No animation, no transition, no blinking caret, no colour
  cycling. A change is a single repaint.
- Repaint budget: only when a visible string changes; the zone timer
  repaints at most once a minute (`render_gate.js`, `test_budgets.py`).
  The row-1 timer is the time in the open map while the player stands in
  that map (an idle log freezes it there), otherwise the time in this zone
  instance (`render_gate.js timerSeconds`; UTIL-MAPRUN-OVL): same text,
  same once-a-minute repaint, no marker.
- Glance time target: each line readable in one fixation (< 1 s): <= 5
  words, number or name first, no wrapping (`nowrap` + ellipsis).
- Glance rule (F-095): a card's first line starts with its answer, inside
  the 34-character clip: the verdict word on an item check card (Upgrade,
  Sidegrade, Downgrade, Risky, No risky mods), the price word on a price
  card (`Price:`), the buyer on a trade card (`Trade: <buyer>`), or one of
  the fixed status words of a card that has no verdict (No build loaded,
  Not an item, Can't compare this, Build loaded, Build not loaded, Can't
  check this item, Waystone unidentified). A merged card starts with its
  item check head.
- Every card that leaves the overlay by itself has a dashboard twin that
  stays: the item check card and the price card (and the merged card) stay
  in Play > Item check (`#eval-result`, `#price-result`), the trade card in
  Trade requests (`#trade-list`) while it is open and in Recent (`#events`)
  after it closes. `tests/test_glance_rules.py` walks every
  card kind the core can publish and fails when a kind has no twin; a
  later card holder declares its twin (or a reason it needs none) where it
  is defined.
- Placement: corners only, user-chosen; default top-right. In PoE2 that
  corner holds the game's corner map (with the quest tracker below it),
  so the 2-line HUD covers its top edge and a card covers more for its
  20 s; every other region costs more in a fight (top-left: buffs and
  party frames; top-center: the boss life bar; bottom: globes, flasks,
  skill bar, XP bar). The player moves it in one change on the dashboard
  (UX-DPI ruling 2026-11-17; reverses if play shows the corner map is
  routinely needed and covered, or the HUD grows past 2 lines).
- Size follows the monitor: the window is in DIPs, so Windows scaling
  applies by itself, and on a monitor taller than 1440 DIPs (4K at 100
  or 125 percent) `layout.js autoScale` grows the HUD by DIP height /
  1440 (at most 2x) so text is never physically smaller than at 1440p
  and 100 percent (UX-DPI). User size times that factor is capped at
  2.5, and the window never exceeds the work area.
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

Prose and messaging
- P1: plain words, sentence case, present tense, subject first.
- P2: no internals (core, token, SSE, tailer, HTTP codes) in a main line.
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
  ="polite"`), never assertively. Exempt: the non-urgent last-session card
  (`#summarybox`), which stays silent and is reached by its heading, and
  the build card (`#build-alert`, BUILD-LIVE): it changes only when the
  character or build changes, is not urgent, and the polite-region cap
  (12, test_a11y) keeps its last slot for urgent states, so it is
  reached by its heading too.

Overlay
- O1: no animation, transition, keyframes, blink or flash.
- O2: repaint only on a visible change; budgets test green.
- O3: smallest rendered text >= 12px at the minimum scale.
- O4: each line within the section 9 rule 6 limits, nowrap + ellipsis, readable in one glance.
- O5: effective opacity keeps overlay text >= 4.5:1 over white.
- O6: window stays click-through and non-focusable; no input is sent.

Structure and access (dashboard)
- S1: headings in order; landmarks (header, main, footer) present.
- S2: every control has a visible label or aria-label; hit target >= 24px.
- S3: works at 320px width with no horizontal scroll.
- S4: keyboard reachable with a visible focus ring.
- S5: GGG disclaimer present in the dashboard footer and overlay About.

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

## Amendment 2026-11-18 - target design (not yet shipped; lands with the TD-nn packages of docs/plan/03-target-design.md)

Status: not in force yet. Each rule, token and limit below changes only when
the named TD-nn package of `docs/plan/03-target-design.md` lands. Until
then every rule in sections 1 to 11 above stays in force for shipped UI, and
reviews of shipped UI use those sections unchanged. A package that lands
edits the section it names (and, for colours, the measured block of 5.2 in
the same commit as the CSS); when TD-23 lands, this section is removed.
Heights are design budgets until TD-01 has measured them.

Section 3 - type scale (TD-03; overlay roles TD-05):
- Dashboard tokens. Old: `--al-fs-caption` 13px, `--al-fs-label` 13.6px,
  `--al-fs-small` 14.4px, `--al-fs-body` 16px, `--al-fs-sub` 25.6px,
  `--al-fs-zone` clamp(1.5rem, 4.5vw, 2.4rem), `--al-fs-glance` clamp(2rem,
  6vw, 3.25rem). New: six rem tokens: `--al-fs-micro` 0.8125rem (13px),
  `--al-fs-meta` 0.875rem (14px), `--al-fs-body` 1rem (16px),
  `--al-fs-title` 1.25rem (20px), `--al-fs-glance` 1.75rem (28px),
  `--al-fs-hero` 2rem (32px). No `vw` and no `clamp()` in any font size.
- Line height. Old: 1.4 for body, 1.1 for glance numbers. New: one fixed
  rem line box per token: 18, 20, 22, 26, 32, 36px at root 16px.
- Minimum. Old: nothing under 13px. New: nothing under 14px on the
  dashboard except the two footer sentences (13px); no weight 600 or more
  under 14px; in-play text (strip labels, sub lines, status words in the
  bar, strip, notice, build line and item check, the top answers) at the
  20px token or larger; the kept-check rows are review text at 14px.
- Root scale. Old: none; the shell sizes scale with `vw` and the tiles
  tighten at 820px tall or less. New: root font size 100% x s, s the
  largest of 1, 1.25, 1.5, 2 whose compact cockpit fits (a viewport of at
  least 64em x 43.75em times s); the class is full from 75em x 47.5em
  times s, else compact; the 820px query and the UI-GLANCE shell clamps
  go.
- Distance rule (new): in-play text is at least 16 arcmin of cap height at
  the reference setup (24 inch 1080p, dashboard at 80 cm, overlay at 60 cm).
- Overlay roles. Old: zone line 16px, timer 16px, HUD numbers 15px, trade
  card 14px, secondary 13px. New: two sizes only: 16px (HUD lines, status
  word) and 14px (card lines, guide line, key hint), weight 600,
  line-height 1.3. The rule "rendered text never under 12px after zoom"
  stays.

Section 4 - spacing and shape:
- Tabs (TD-19). Old: five tabs (Play, Run and history, Build, Items and
  prices, Settings). New: four tabs: Play, Build and items, Run, Settings;
  a stored `items` tab name maps to `build`.
- App shell (TD-09, TD-19 to TD-21). Old: at 900px wide and 560px tall or
  more the page never scrolls, Play is two columns, every tab's columns
  scroll on their own and each column is a labelled group with tabindex 0.
  New: no column and no card scrolls. Play is a fixed grid of 7 regions
  (strip G; context C, feed T, notice N on the left; build line B, item
  check I, kept checks U on the right) with tracks 100 / 228 / 204 / 96 /
  68 / 360 / 100px at root 16px (grid 652px + 108px chrome = 760px), the
  same in every state; a compact class from 64em x 43.75em times s with
  tracks 100 / 212 / 204 / 52 / 68 / 348 / 52px (grid 592px + 108px =
  700px; region U pads 4px there, so its label and one row are 2 + 8 + 20
  + 20 = 50px in the 52px track); below that, one column with one page
  scroll. One DOM order in every class (strip, context, feed, notice,
  build line, item check, kept checks), placed by grid placement only, so
  Tab order = screen order still holds. Regions are not scroll containers
  and have no tab stop. The other tabs are fixed 3 x 2 card grids whose
  lists page at 10 one-line rows, with a "Full text" page of 3 entries of
  up to 3 wrapped lines; Settings is a rail with one visible section of at
  most 448px of rows (14 rows of 32px), paged beyond that.
- Narrow widths (TD-09, TD-22). The 320px rule stays and gets its parts:
  under 40em the Zone cell takes a full strip row and Level, Deaths and
  Session share the next; the tab row wraps under the brand; a trade
  row's right-hand segment moves under its lead line; the footer
  sentences stack; rows wrap, nothing takes the ellipsis.
- Header line (TD-09). The "New on Play: <what>." polite region stays but
  is visually hidden (no box, no height in the 52px bar); the count on
  the Play tab is its visible twin.
- Reading indicator and footer (TD-21). Old: "Stop reading Client.txt"
  and the game-data credit are footer folds. New: the bar status word is
  the reading indicator on every tab and a button that shows Settings >
  Reading and web data with focus on "Stop reading Client.txt"; the full
  credits move to Settings > About and data, and a one-line credit stays
  on each card that shows the credited data (Run > Acts, Build and items
  > Prices, the price row of the item check).
- Play content (TD-10 to TD-16). Old: zone tile with its guide, level /
  deaths / session, the `#build-alert` slot, trades, the tip, the item
  card. New: the 7 regions; the build alert is a state of region B; the
  tip, language note, setup line and part-is-broken notes share region N
  (one at a time); trades are one line each and all 5 open requests show.
- Padding and gaps. Old: cards pad 16px, stat tiles 12px 16px, gaps 16px.
  New (rem, scaling with s): region padding 12px (8px in N, B and U, 6px
  in T, 4px in G; U 4px in the compact class); 8px between regions, 12px
  between the two columns.
- Focus ring (TD-22). New: a 3px accent ring drawn inside the element
  (outline-offset -3px).
- Auto-switch (TD-22). Old: "No focus moves". New: Play is shown by
  itself only after the 10 s grace (unchanged), so never while the user
  is pressing keys in the tab row; if focus then sits on the tab row it
  moves to the Play tab and the header line says once "Showing Play.
  <what>."; a focus inside a panel is never moved.
- Unchanged: the 4px grid, the radii, the 24px minimum target (aim 32px),
  320px width with no horizontal scroll, the 10 s auto-switch grace.

Section 5 - colour:
- 5.1 `--al-plate` (TD-05). Old: rgba(15, 18, 22, 0.92). New: rgba(15, 18,
  22, 0.86), user range 0.80 to 1.0.
- 5.1 control boundary (TD-03). Old: `var(--fk-text-muted)`. New:
  `--al-control-edge`, #737c88 dark and #7a828c light (4.44 on surface and
  4.05 on surface-2 dark; 3.89 and 3.53 light).
- 5.1 new token `--al-text-body` (TD-03): #c5ccd3 dark and #30353c light,
  for sentences and rows (11.58 and 10.55 dark; 12.35 and 11.22 light).
- 5.1 new overlay-only tokens (TD-05): `--al-ovl-text-2` #c3c9d0
  (secondary text) and `--al-ovl-warn` #f0bd55 (warn word). Old: the
  overlay uses kit `text-muted` and `status-warn` for those roles.
- 5.2 overlay rows over the white scene (TD-05). Text: old 12.50, new
  10.28. Secondary: old 5.89 (text-muted), new 7.59 (`--al-ovl-text-2`).
  Warn: old 6.13 (status-warn), new 7.30 (`--al-ovl-warn`). `status-bad`:
  old 4.78 as text, new an edge only (3.93). At the 0.80 alpha floor the
  three text values are 8.30, 6.13 and 5.90. Minimum: old 4.5 for every
  overlay text pair; new 7.0 at the default plate and 5.5 at the alpha
  floor.
- 5.2 opacity rule (TD-05). Old: the window opacity multiplies text and
  plate; slider floor 0.9. New: text is always opaque; the slider (named
  "Background") sets the plate alpha only, floor 0.80; no page opacity.
- 5.4 (TD-04). Old: the dashboard follows `prefers-color-scheme`. New:
  dark by default (`data-theme="dark"`, native theme source dark) with one
  setting, Theme: Dark / Follow Windows / Light. The overlay stays dark.

Section 6 - state colours (TD-10, TD-13):
- Trade request. Old: `status-warn` edge + `TRADE` tag. New: `accent` edge
  + the word "Trade". Warn keeps one meaning: act when you can (old
  build, risky waystone, under-level, blocked).
- Accent. One meaning, "you can act here": links, the selected tab, the
  focus ring, the one filled button, and the edge of a trade request that
  waits for a reply.
- Whisper. Old: `accent` edge + `FROM` / `TO` tag. New: a whisper that is
  not a trade request is not on the Play tab; in Run > Recent it keeps the
  muted `FROM` / `TO` tag and has no edge. Also Run > Recent only: trade
  accepted / cancelled lines and party joins and leaves.
- Build state words (TD-15): "Build fits", "Old build", "Wrong class",
  "No build". "Old build" takes `[?]` and `status-warn`; the kit word
  `stale` is not used for it.
- The state table above is unchanged: reading Client.txt stays `[>]`
  (running). For 60 s a new row says "new" at the start of its right-hand
  segment ("new, 2m"); the row's own sentence is not changed.
- Normal states are neutral: the reading word and normal rows carry no
  colour while all is well.
- Stale data (new): while the log is idle or AshLight cannot be reached,
  strip values, timers and feed rows use `text-muted` and the zone sub
  line says "frozen <time>".

Section 7.2 - context (TD-17):
- Progressive disclosure. Old: "the 2-line HUD plus at most one trade
  card". New: the 2-line HUD plus one card slot whose holder is, first
  match: the press card, the newest open trade card, a zone or act card
  (12 s, only into a free slot), the key hint line, nothing. "Never add a
  third HUD line" stays.
- HUD line 2. Old: level, deaths and one status word. New: the same by
  default. Setting "Zone guide on the overlay": On entry (default; the
  zone card only) / Always / Never. Only under Always (an opt-in), in a
  guided campaign zone, the zone-guide line (the guide entry's `short`
  field, at most 34 characters, shown as authored or not at all) replaces
  the level text while no connection, log state, trade count, under-level
  or AFK / DND word is due.
- Row "Died". Old: deaths count changes; no flash, no pop-up. New: the
  same; while the opt-in guide line holds line 2, a death or a level-up
  puts the level and deaths text back for 20 s.
- HUD line 2 width (new): level text and status word together at most 26
  characters (the plate is 236px inside); over that the deaths text
  drops; a status word over 20 characters stands alone (at most 27).
- Rows "Trade request arrives" and "Under-levelled". The dashboard keeps
  the trade list with a Dismiss on every row (plus "Dismiss all" from 2
  open requests); the line under the Level tile uses the overlay's words,
  "N lv under".

Section 9 - messaging (TD-07, TD-17):
- Rule 6 line limits. Old: overlay zone 28 chars, card lines 34 chars;
  dashboard event lines wrap, never truncate. New: the same overlay limits
  plus the guide `short` line at 34 chars and the key hint "<key>: check
  an item"; on the Play tab every row is one line, composed under a
  character cap that fits the narrowest column even with the WCAG 1.4.12
  spacing (context title 38, context and notice rows 52, event sentence
  38, build row 36, item sentence 2 x 36, kept row 42); only a name can
  take the ellipsis, with the full text in `title` and on the "Full text"
  page of its card on Run or Build and items (list rows there are one
  line too). Under a text-spacing override rows wrap and the page
  scrolls.
- Status slot order. Old: connection, Client.txt state, trade count,
  under-level word, AFK / DND, campaign hint word. New: the zone-guide
  line sits after AFK / DND and before the campaign hint word.

Section 10 - overlay rules:
- Content cap (TD-17). The count is unchanged: 2 HUD lines + one 3-line
  card, never two cards. Holders: old the trade card or, for 20 s after
  the press, the item check card; new the list under 7.2 above. The card's
  near edge is anchored 62px from the window's anchored edge in every
  state.
- Card time (TD-18). Old: 20 s. New: 20 s by default, setting 20 / 60 /
  200 s.
- Plate (TD-05). Old: 92 percent plate and a `0 1px 1px #000` text shadow.
  New: 86 percent plate (80 to 100) and the text shadow `0 0 2px #000,
  0 0 2px #000, 0 1px 2px #000`; no stroke.
- Opacity (TD-05). Old: the effective opacity keeps every overlay text
  pair >= 4.5:1 over a white scene. New: text is opaque; text pairs >= 7:1
  at the default plate and >= 5.5:1 at the alpha floor; edges >= 3:1.
- Size (TD-06). Old: `autoScale` grows the HUD by DIP height / 1440. New:
  DIP height / 1200 (1440 DIPs give 1.2); the 2x cap stays; the overlay
  budgets of decision 0002 are re-run in the same package.
- Glance (TD-17). New: the first line of an answer card or a trade card
  starts with its answer (verdict word, price word or buyer); a status
  card starts with its status words ("Build loaded", "Not an item", "Copy
  the item first"); a zone or act card and the key hint start with their
  subject. Every card that leaves by itself has a dashboard twin.
- Unchanged: the window flags, base size 280 x 176 DIP, plates max-width
  258px, corners only with the top-right default (the UX-DPI ruling is not
  reversed: the HUD stays at 2 lines), no flashing, the repaint budget,
  the display mode, the About text.

Section 11 - checklist (ids added at the end of their groups by TD-23):
- C7: dashboard text sizes come only from the six type tokens; overlay
  sizes only from the two overlay tokens (16px and 14px).
- N7: in the full and compact classes at default text settings, no Play
  region scrolls, moves or changes size between states.
- N8: every item that leaves by itself has a twin that stays.
- O7: a press or trade card starts with its answer (verdict word, price
  word or buyer); a status card starts with its status words; a moment
  card or the key hint starts with its subject.
- O8: overlay text pairs >= 7:1 at the default plate and >= 5.5:1 at the
  alpha floor over white (replaces O5 when TD-05 lands).
- S6: the focus ring is drawn inside the element and is never clipped.
