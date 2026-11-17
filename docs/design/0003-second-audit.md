# 0003 - Second design audit (live dashboard, overlay, messaging)

Date: 2026-11-16. Operator order: UI/UX review (UI-REVIEW-2), headless.
Two inputs merged here: (1) a live look at the running dashboard
(127.0.0.1, read-only: no click, no form change, every non-GET request
blocked by the test harness) at 1366, 360 and 320 px wide in light and dark,
plus an offline and a no-token run, and the overlay rendered standalone from
the branch with synthetic state over a white and a dark scene; (2) the
`design-reviewer` agent over the whole UI (`web/`, `app/overlay/`,
`app/shared/`, `app/main.js`, `server/al/state.py` event text) against
`docs/design/0001-design-system.md` and the minimal-interaction rule in
`docs/decisions/0004-scope-theorycraft.md`. Screenshots live in the AL
sidecar Scratch folder (`ui-review-2/`), never in the repo.

Tooling note: the Playwright and Chrome DevTools MCP browsers failed to
start on this host (GPU process launch error 18 / profile cache locked), so
the live pass ran through the Python `playwright` package driving the
installed Chrome headless with `--disable-gpu`. Same engine, same pages.

Contrast was measured in the live page (WCAG 2.2 relative luminance on each
text node's computed colour over its composited background): every text pair
on the dashboard is >= 4.5:1 in both themes (lowest: kit muted text on
surface-2, 6.07 light / 6.54 dark). No new colour was added by the fixes,
so the 0001 section 5.2 block stands; `tests/test_design_contrast.py` green.

## Counts

- Before (merged, de-duplicated): S1=0 S2=4 S3=8 S4=7 (19).
- After this change: S1=0 S2=0 S3=0 S4=0 open; two reviewer suggestions kept
  by decision (K1, K2 below).
- Reviewer verdicts: pass 1 PASS WITH FINDINGS (S1=0 S2=2 S3=7 S4=3, the live
  pass added two S2 and four smaller ones); pass 2 on the fixes PASS WITH
  FINDINGS (S1=0 S2=0 S3=0 S4=3), all three S4 then fixed.

Zero-click count (DESIGN-AUDIT rule): a play session still needs 0 clicks
after the one-time opt-in; nothing in this change adds a click, a modal or a
focus steal. The hotkey (Alt+Shift+A) is now named on the dashboard.

## S2 - major (all fixed)

- G1 [S2, N4 / P8 / P5; reviewer F1 + live] `app/shared/render_gate.js:44`,
  `:64`, `:71`. The overlay ignored the Client.txt state: before the opt-in
  it read "No zone yet -- / Lv unknown | 0 deaths" (made-up numbers, no
  hint), and with the file missing it looked live. Fix: a `log` field in the
  render gate. Not opted in: HUD reads "AshLight" + "not reading", no
  numbers. Opted in but not reading: known values stay, the slot says "no
  Client.txt". Slot order: connection, then log, then AFK / DND. Tests:
  `app/test/shared.test.js` "UI-REVIEW-2" cases.
- G2 [S2, P3 / principle 7; live + reviewer F7] `web/app.js:62`, `:286`,
  `:291`, `web/status.js:20`, `:31`. With AshLight down the dashboard kept
  saying "reading Client.txt" (or "not reading" at load), the timers kept
  counting stale data, and "can't reach AshLight - restart it" was
  overwritten by "reconnecting". Fix: `linkView` / `readingView` helpers; a
  first failure says what to do, a later one says "reconnecting"; the log
  pill reads "Client.txt status unknown" while the feed is down; timers stop
  until the feed is live again. Tests: `app/test/dashboard.test.js`.
- G3 [S2, glance readability; live] `web/app.css:120`, `:122`. On a 1366 px
  desktop the zone, the main glance value, broke mid-word ("Encampmen / t")
  because the four tiles were 222 px wide and the value used
  `overflow-wrap: anywhere`; a 7-char session time could break the same
  way. Fix: the zone tile takes the whole first row and wraps only between
  words; the other three tiles share the next row; glance numbers are
  `nowrap`. Verified at 320, 360, 520 and 1366 px, no horizontal scroll.
- G4 [S2, P4 / P5; reviewer F2 + live] `web/app.js` (old `tradeLine`),
  `server/al/state.py:85`, `:354`, `web/status.js:64`. The dashboard built
  its own trade wording, so a missing amount printed "undefined" or "for
  undefined", and its stash text ("tab Sale, left 3, top 7") disagreed with
  the overlay ("tab Sale (3,7)"). Fix: the snapshot now carries `text` and
  `where` for each open card from the one section 9 template
  (`trade_card_text`); the dashboard prints them, with an honest fallback
  for an older core. Tests: `tests/test_trade_text.py`.

## S3 - minor (all fixed)

- G5 [S3, P8; reviewer F3] `web/app.js:219`, `:236`. First run: Recent said
  "show up here as you play" though nothing can appear before the opt-in;
  the zone read "-". Now "Nothing yet. Allow reading Client.txt above, then
  ..." and "No zone yet" (the overlay's words).
- G6 [S3, P1 / P3; reviewer F4] `web/index.html:34`. The opt-in said "You
  can stop it at any time" without saying where. Now names the "Stop reading
  Client.txt" control at the bottom of the page.
- G7 [S3, N6; reviewer F5] `web/index.html:39`. `consent-error` was revealed
  by un-hiding, so it was not announced. Now a polite live region.
- G8 [S3, P3; reviewer F6] `web/app.js:138`, `web/index.html:70`. A failed
  Dismiss was silent. Now "Not dismissed. Try again." in a polite status
  line.
- G9 [S3, N3; reviewer F8] `web/index.html:101`. The one mid-game action,
  the show / hide hotkey, was named nowhere. Now stated under Overlay
  position, with the note that it can be changed in the settings file.
- G10 [S3, S2 target size; reviewer F9, measured 16 px live]
  `web/app.css:199`. Range inputs now `min-height: 24px`.
- G11 [S3, O4; live] `app/overlay/index.html:19`, `overlay.css:74-76`. A
  long sender name pushed "+1 more" out of the trade card, so the player
  could not tell more requests were waiting. The name now clips itself;
  "+N more" is always visible.
- G12 [S3, P5; live] `app/shared/render_gate.js` (`timer`). With no zone yet
  the HUD showed a stray "--" timer. Now blank until a zone is known.

## S4 - nit (all fixed)

- G13 [S4, P1; reviewer F10] `app/overlay/overlay.js:13`, `:49`. Status words:
  "waiting" -> "connecting" before the first push; "AshLight offline" and
  "offline" unified to "offline" (the zone line already reads "AshLight"
  in that state, so the old text read "AshLight / AshLight offline").
- G14 [S4, voice rule 2; reviewer F11] `web/status.js:73`. Corner options in
  sentence case ("Top right").
- G15 [S4, type scale; reviewer F12 / pass 2 R1] `web/app.css:31`. Brand
  1.1rem -> 1rem (bold h1), on the scale.
- G16 [S4, P1; live] `web/status.js:41`. Every log-status event was tagged
  "INFO". Kinds now: `log` (Client.txt start / reset), `status` (AFK / DND),
  `party` (joined / left), `info` only for the rest.
- G17 [S4, spacing; pass 2 R2] `web/app.css:71`. Empty error paragraph left
  32 px of dead space in the opt-in card; `:empty` margin 0.
- G18 [S4, S3 width; pass 2 R3] `web/app.css:210`,
  `docs/design/0001-design-system.md` section 4. Two-column breakpoint
  480 -> 600 px so a 1-hour session time never spills its tile.
- G19 [S4, P5; live] `web/app.js` `tick`. The Session timer counted from
  AshLight's start even before the opt-in. Now "--:--" until opted in.

## Kept by decision

- K1 (reviewer F3 part): the Level tile keeps "-" before a level is known
  instead of "unknown". Why: it is a 52 px glance number; "unknown" does not
  fit a narrow tile, and the sub-line already says "character unknown".
  Reverses if: a later pass finds players misread "-".
- K2 (reviewer F10 part): the reviewer offered "AshLight offline" for both
  offline paths; "offline" was chosen (G13) because the status shares the
  258 px numbers row and "Lv 12 | 3 deaths AshLight offline" clips.
  Reverses if: the status word moves to its own row.

## DS-REVIEW-HOOK - adjudicator ruling

RULING: B + D. A warn-only pre-commit reminder (`tools/design_gate.py`,
chained in `.githooks/pre-commit` before the leak sweep, always exit 0) and
the binding rule in the lane prompts (`tools/loop_prompts.py`: `DESIGN_RULE`
appended to `GATES`, and `verify_prompt` FAILs a UI diff without a new
`docs/design/reviews.log` line). Ledger: `docs/design/reviews.log`, one line
per review: `YYYY-MM-DD | scope=<paths> | verdict=<verdict> S1=<n> S2=<n>
S3=<n> S4=<n> | <row id> | audit=<file or ->`.
ALTERNATIVES: A hard pre-commit refusal; C a commit-msg trailer check; D
the lane prompt alone. WHY: the reviewer is an agent and cannot run inside a
hook, so a refusal would stall headless lanes (FLEET rule 1) or train a
meaningless skip; the row's ACCEPT ("rule named in the lane prompt or
loop") is met by D; the reminder costs nothing for interactive commits; no
kit file is touched. Deviation recorded: the ledger counts use S1-S4 (the
reviewer's own scale) instead of the ruling's blocker / major / minor words.
REVERSES IF: UI commits keep landing without a ledger line (check the
ledger against `git log -- web app/overlay app/shared` after about two
weeks) - then promote to a refusal with a logged skip; or the kit spawn
helper can run the reviewer non-interactively.
Tests: `tests/test_design_gate.py`.
