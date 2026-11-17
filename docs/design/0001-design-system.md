# 0001 - AshLight design system

Status: accepted 2026-11-16 (operator order 2026-11-16). Owner of reviews:
the `design-reviewer` agent (`.claude/agents/design-reviewer.md`). First
audit: `docs/design/0002-first-audit.md`.

> **Interpretation note - "NLM" (operator, please correct if wrong).** The
> order listed "NLM" without expanding it. This document reads it as
> **natural-language messaging**: how AshLight phrases events, statuses and
> notifications as short natural sentences, plus the rules for generating
> that text from log events (section 9). If NLM meant something else (for
> example a language model, or "no learning mode"), say so and section 9 is
> rewritten; nothing else in this document depends on the reading.

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

Overlay (CSS px at zoom 1.0; the window zoom is the layout `scale`):

| Role | Size | Weight |
|---|---|---|
| zone line | 16px | 600 |
| zone timer (full text colour, never clipped) | 16px | 600 |
| HUD numbers | 15px | 600 |
| trade card | 14px | 600 |
| secondary (where, more, status) | 13px | 600 |

Overlay rule: rendered text never under 12px **after** zoom, so the
smallest overlay size times the minimum `scale` must be >= 12px. With the
13px secondary size that means `scale >= 0.93`; see audit 0002 for the
current 0.75 floor.

## 4. Spacing and shape

- 4px grid: 4, 8, 12, 16, 24, 32. Cards pad 16px; stat tiles 12px 16px;
  gaps 16px (8px under 600px width).
- Radius: 8px cards, 6px controls and overlay plates, 999px pills.
- Hit targets on the dashboard: at least 24x24 CSS px (WCAG 2.2 SC 2.5.8);
  aim for 32px tall buttons.
- The layout must work at 320px width (dashboard on a phone or a narrow
  second screen) with no horizontal scroll.

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
| `--al-plate` (overlay) | rgba(15, 18, 22, 0.92) | HUD plate; 0.92 keeps all overlay text >= 4.5:1 over a pure white scene |
| control boundary | `var(--fk-text-muted)` | inputs, selects and secondary buttons; kit `border` is 1.3-1.6:1, too faint for SC 1.4.11 |

Overlay colours mirror the kit dark theme (`text`, `text-muted`, `border`,
`status-warn`, `status-bad`). The overlay is always dark: it sits on a game
scene, not on a page, so it does not follow `prefers-color-scheme`.

### 5.2 Measured contrast

Computed with the WCAG 2.2 relative-luminance formula (sRGB linearised,
`(L1 + 0.05) / (L2 + 0.05)`), not estimated. `overlay.plate-worst` is
`--al-plate` composited over #ffffff: the brightest possible game scene is
the worst case for light text on a translucent dark plate. Each row is
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
# control boundaries and focus ring (SC 1.4.11, 3:1)
light.text-muted light.surface 3.0 6.68
light.text light.surface-2 3.0 15.37
dark.text-muted dark.surface 3.0 7.18
dark.text dark.surface-2 3.0 13.89
# overlay over the worst-case (white) scene
overlay.text overlay.plate-worst 4.5 12.50
overlay.text-muted overlay.plate-worst 4.5 5.89
overlay.status-warn overlay.plate-worst 4.5 6.13
overlay.status-bad overlay.plate-worst 4.5 4.78
```

Not allowed as a boundary or text colour: kit `border` (light 1.43:1 on
surface, 1.30:1 on surface-2; dark 1.59:1 / 1.45:1). It is a decorative
divider only; anything a user must find (an input, a button edge) uses the
control-boundary colour.

Overlay window opacity multiplies text and plate together. Measured over a
white scene with the 0.92 plate, every alpha composite rounded to 8 bits a
channel as the framebuffer stores it (unrounded maths gives about +0.03),
text / text-muted: window opacity 1.0
gives 12.50 / 5.89, 0.9 gives 9.34 / 4.80, 0.85 gives 7.94 / 4.29, 0.7
gives 4.99 / 3.05, 0.5 gives 2.83 / 2.01. Rule: the effective overlay
opacity floor is the value that keeps `text-muted` at 4.5:1 over white,
0.87 with the 0.92 plate (measured 0.867); the slider floor is 0.9
(`layout.js` LIMITS.opacity, DS-OPACITY).
At the 0.9 default and floor (`layout.js` LIMITS) status-warn reads 4.96
and status-bad 3.92, so status-bad is never an overlay text colour;
`tests/test_ux_review.py` checks every overlay text colour at the floor
(audit 0004 U1). High-contrast mode (`prefers-contrast: more`) lifts muted
text to the text colour on both surfaces and drops the plate's own alpha
(the window opacity still applies); the overlay card's neutral edge keeps
its `--al-edge` colour (U3).

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
| Not reading / offline | one status word ("offline") | pill with the fix |
| Item check hotkey pressed | item check card for 20 s (verdict, item, top stat) in the card slot | Item check card with every compared slot |
| In a campaign act (HUD-ACT) | no change | Act times card (below Item check): splits, zone levels for the current act; in endgame the splits stay, the zone table empties |
| Price check from the same press (web data on) | price line replaces the item name in that card; price-only card when no build is loaded (decision 0016) | Price section in the Item check card, listings with "about N <primary>" |
| Item check from the same press | none on the overlay | Upgrade search sub-section under the item check (TC-UPGRADE) |

Progressive disclosure (source 9): the overlay holds the 2-line HUD plus at
most one trade card ("+N more" for the rest). Everything else (history,
stash coordinates in full, settings) lives on the dashboard. Never add a
third HUD line to fit a feature; add a dashboard card instead.

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
   - log state: `Reading Client.txt`, `Client.txt was reset (<reason>)`
   - item check (TC-EVAL-UI): overlay head `<Verdict> <+delta> vs <slot>`
     (empty slot: `<Verdict> <+delta> - <slot> empty`), item name, top
     counted stat (`+35 to maximum Life`; a flag mod `Gains: <mod>` /
     `Loses: <mod>`); dashboard `Upgrade: <n> points more than your <slot>
     (<name>).`, `Downgrade: <n> points less than ...`, `Sidegrade: about
     the same as your <slot> (<name>), <+n> points.`; errors `No build
     loaded`, `Not an item`, `Can't compare this` with the next step
   - item check scoring source (TC-DELTA, decision 0022, `_calc_text`):
     when Path of Building scored the item the overlay third line is `DPS
     <+pct>%, EHP <+pct>%` (a 0 base reads `unknown`) and the dashboard adds
     `Path of Building: DPS <+pct>% (from <old> to <new>), EHP <+pct>% (from
     <old> to <new>), with this item in <slot>.`; otherwise the dashboard
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
     of Building could not be reached. Try the check again.` (failed);
     uncounted mods read `Not counted (Path of Building has not measured
     these for this build yet): <mods>.`
   - price and points (MATH-VALUE-UI, web/prices.js `valueView`): `Asking
     price: <n> <currency>, about <n> <primary>.` (`Buyout price: ...` for
     a b/o note; no "about" when already the primary), `<n> points per
     <primary>.`, `These currency values may be out of date.`, the
     poe.ninja credit; without rates `No currency values are saved yet, so
     AshLight can't compare the item's price with its points.`, without a
     rate for that currency `There is no saved value for <currency> yet,
     so AshLight can't compare the item's price with its points.`; hidden
     when the item has no note price.
   - price check (PRICE-1-UI, `price_card_text`): overlay `Price: <item>`,
     `<n> listed, ~<middle>` / `Lowest <amount> <currency>`, `Searching
     prices...`, `Prices in about <n> s`, `Web data is off`, `No listings found`,
     `Price check failed`; dashboard `<n> listed in <league>. The cheapest
     is <a>; the middle of the <k> cheapest is <b>.`; the one card is
     chosen by `overlay_card` (decision 0016)
   - open trade count (UX-REVIEW F1, `format.js tradeCount`): HUD status
     slot `1 trade` / `<n> trades` while a card hides the trade card;
     slot order: connection, Client.txt state, trade count, AFK / DND
   - new trade request (UX-REVIEW F6, `web/trades.js`): dashboard polite
     live region `New trade request from <from>.` (no name: `New trade
     request.`; several at once: `<n> new trade requests.`), only when the
     set of open trade ids grows
   - act times (HUD-ACT, `server/al/acts.py`, `web/acts.js`): dashboard
     only; rows `Act <n>` / `Cruel Act <n>` / `Interlude <n>` with `Time in
     act` and `Run total` (m:ss or h:mm:ss); one note per row in one pair of
     parentheses: `(now)`, `(partial: counted from when AshLight started)`,
     joined with ", "; zone heading `Zone levels in <act>`, zone notes `(you
     are here)` / `(town)`; empty `No act times yet. They start by
     themselves when you enter a campaign zone.`, `Zone levels show here
     while you are in a campaign act.`, `Zone levels aren't downloaded yet.
     Run AshLight's build step (scripts/build.ps1) to get them.`; source
     line `Zone levels: RePoE fork export, downloaded when AshLight was
     built. Game data (c) Grinding Gear Games.` (decision 0020)
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

## 10. Overlay rules

- Window: separate, transparent, always-on-top, click-through,
  non-focusable (CLAUDE.md). Base size 280 x 176 DIP at scale 1.0
  (`app/shared/layout.js` BASE); HUD plates max-width 258px.
- Content cap: 2 HUD lines + one 3-line card. Nothing else. The card slot
  holds the trade card, or for 20 s after the item check hotkey press the
  item check card (TC-EVAL-UI; the player just asked for it), after which
  the trade card comes back by itself. Never two cards at once. A price
  check from the same press shares that card (decision 0016: merged card,
  or the price-only card when no build is loaded).
- Plate: `--al-plate` (92 percent) with a 1px kit-border edge and a
  `0 1px 1px #000` text shadow (source 4: outlines and shadows separate
  text from busy scenes). In high-contrast mode (`prefers-contrast:
  more`) the plate has no alpha of its own; the window opacity still
  applies (audit 0004 U3). In Windows forced colours the plate is opaque
  Canvas, text and edges take the system theme (the trade and upgrade
  edges use Highlight), the page root opts out so the window stays
  transparent, and contrast is the theme's own, not measured here; the
  window opacity slider still multiplies (audit 0004 U8).
- Opacity: the effective opacity must keep every overlay text pair >= 4.5:1
  over a white scene (5.2). Decorative transparency comes from the plate,
  not from fading the text.
- Size: secondary text >= 12px after zoom (section 3).
- No flashing, ever (WCAG 2.3.1; the overlay is in peripheral vision during
  combat). No animation, no transition, no blinking caret, no colour
  cycling. A change is a single repaint.
- Repaint budget: only when a visible string changes; the zone timer
  repaints at most once a minute (`render_gate.js`, `test_budgets.py`).
- Glance time target: each line readable in one fixation (< 1 s): <= 5
  words, number or name first, no wrapping (`nowrap` + ellipsis).
- Placement: corners only, user-chosen; default top-right away from the
  game's own minimap and life / mana globes.
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
  ="polite"`), never assertively.

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
