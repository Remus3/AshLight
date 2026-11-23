# 0075 - Fixed cockpit Play, four tabs, dark by default

Date: 2026-11-22. Status: accepted; records what shipped. Trigger: the
target design of `docs/plan/03-target-design.md` (ruled 2026-11-18,
decision 0078: target design A is the base), built by the TD-01 to TD-22
packages and recorded by PLAY-TD-23-RECORDS (plan unit TD-23, finding
F-017 reserved this number). Design system: `docs/design/0001-design-system.md`
sections 3 to 11, rewritten the same day.

## Decision

1. Play is a fixed cockpit of 7 regions: strip G across the top; context
   C, feed T and notice N on the left; build line B, item check I and kept
   checks U on the right. One DOM order (G, C, T, N, B, I, U), placed by
   grid placement only, so Tab order is screen order. The tracks are fixed
   and the same in every play state: full 100 / 228 / 204 / 96 / 68 / 360
   / 100 px at root 16 px (grid 652 + 108 chrome = 760), compact 100 / 212
   / 204 / 52 / 68 / 348 / 52 px (592 + 108 = 700). Only the row under C
   and I grows with a taller window. No region scrolls, moves or changes
   size between states, and regions have no tab stop.
2. Size classes come from em media queries on width and height: full
   from 75em x 47.5em times s, compact from 64em x 43.75em times s, flow
   (one column, one page scroll) below. The root font size is 100% x s,
   s the largest of 1, 1.25, 1.5 and 2 whose compact cockpit fits, so a
   larger window buys larger text, not more words. Type comes from six rem
   tokens (13, 14, 16, 20, 28, 32 px at s = 1), no `vw` and no `clamp()`.
3. Four tabs: Play, Build and items, Run, Settings (finding F-067). A
   remembered `items` tab opens Build and items. Build and items and Run
   are fixed 3 x 2 card grids whose lists page; Settings is a rail with
   one section shown at a time.
4. Dark by default with a choice (finding F-086): the page ships
   `data-theme="dark"` and the client starts with the native theme dark;
   one setting, Theme: Dark (default) / Follow Windows / Light. The
   overlay stays dark and never reads the choice.
5. Every trade row keeps its own Dismiss (plus "Dismiss all" from 2 open
   requests). Trade rows are one line each in feed T and all 5 open
   requests show; a request still leaves by itself when it expires or is
   accepted or cancelled, so Dismiss stays optional.
6. The zone-guide line on HUD line 2 is an opt-in. The setting "Zone
   guide on the overlay" is On entry (the default: the zone card only),
   Always or Never. Only under Always, in a guided campaign zone, the
   guide entry's authored `short` (at most 34 characters) replaces the
   level and deaths text while no higher status word is due; a death or
   a level-up brings them back for 20 s.
7. The overlay stays 2 HUD lines plus one card slot, never a third HUD
   line and never a second card. The slot's holders, first match: the
   press card, the newest open trade card, a zone or act card (12 s, only
   into a free slot), the key hint line. The press card shows for 20 s by
   default, with a card time setting of 20 / 60 / 200 s (decision 0014
   amendment 2026-11-22). The top-right placement ruling is not reversed
   (audit 0004 U11 amendment 2026-11-22).

## Alternatives

- Design B, phase-adaptive: the layout changes with the play phase
  (campaign, maps, town). Not taken as base: its band heights contradict
  its own row metrics, a phase change swaps a whole column, and compare
  rows vanish while being read. Its grafts were kept: 2 HUD lines with
  one line-2 priority order, the opt-in guide line, the 1200 DIP
  `autoScale` reference, the Theme choice, the card time setting and the
  focus rule of the automatic return to Play.
- Design C, overlay-first: more on the overlay, less on the dashboard.
  Not taken as base: its item check slot sums exceed its own budgets, it
  needs 3 HUD lines plus a queue line, and its window is 30 percent larger
  than the decision 0002 budgets were measured for. Its grafts were kept:
  the authored guide `short`, one-line trade rows, the compact step, the
  #737c88 control edge and the text-spacing fallback.
- The three-tab set (Play, Review, Setup), the design panel's preference:
  not adopted (0043-X9, F-067). Build and items and Run serve different
  moments (planning gear versus looking back on a run), and four tabs
  keep each grid at 6 cards. It stays plan option O-4: on the operator's
  word the two merge into one Review grid with no rework of Play or the
  overlay.
- A scrolling two-column Play (what shipped before): measured over its
  box by 124 to 598 px with the item card up (`docs/design/play-fit-figures.md`),
  so the player hunted for content in play.
- Forced dark with no choice (design A as written): dropped for the Theme
  setting, since a player on a light desktop had no way back.
- The guide line on HUD line 2 by default: dropped; the default keeps
  level and deaths on line 2 for everyone, so nothing a player relies on
  changes unless they opt in.

## Why

Fixed tracks do not depend on content, so "no scroll" and "same place"
hold by construction and are cheap to test (`tests/test_play_fit.py`
checks G1 and G2 in every state and size class). One rem arithmetic
proves both reference sizes, and the em queries honour the viewer's own
default font size. The build state is always visible in region B. The
overlay window stays 280 x 176 DIP, so the decision 0002 budgets are not
reopened, and the HUD stays at 2 lines, so decision 0014 and the
placement ruling hold. Judges scored A first by total (238 against 219
for B and 195 for C) and first for the player in play and for
feasibility (plan 03 section 1). Dark suits a second screen beside a
dark game, and the choice keeps it from being forced. Per-row Dismiss
keeps one fast way to clear a request without a modal or a second step.

## Reverses if

A play state needs two contexts at once in region C; the no-scroll rule
cannot hold with real strings at s = 1; players report hunting through
Settings more than once a session; or the corner map proves routinely
covered by the 2-line HUD (the placement ruling's own clause).
