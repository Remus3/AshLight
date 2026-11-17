# 0002 - First design audit (dashboard and overlay)

Date: 2026-11-16. Reviewer: the `design-reviewer` agent
(`.claude/agents/design-reviewer.md`) run against
`docs/design/0001-design-system.md`, scope "whole UI": `web/`,
`app/overlay/`, `app/shared/`, `app/main.js`, `server/al/layout.py`, and
`server/al/state.py` `summarize`. Base: commit 9f79bed plus the 0001 overlay
plate token (`--al-plate`, 0.80 -> 0.92 alpha, applied before the audit
because 0.80 measured text-muted 3.91:1 and status-warn 4.07:1 over a white
scene).

Verdict at audit time: FAIL. Counts: S1=3 S2=7 S3=6 S4=3 (19 findings).
After the fixes in this change: 12 fixed, 7 open (S1=1 S2=4 S3=2). Line
numbers below are current as of this commit.

Mechanical checks at audit time: `tests/test_design_contrast.py` 38 passed;
`app/test/shared.test.js` 5 pass; `tests/test_budgets.py` 4 passed;
`tests/test_ascii_lf.py` 3 passed; no `alert` / `confirm` / `prompt`, no
live animation or transition, no `innerHTML` use, no user string ending in
"!".

## Findings, ranked

### S1 - blocker

- F1 [S1, O5 / C1, FIXED by DS-OPACITY] `server/al/layout.py:21`, `app/shared/layout.js:28`,
  `web/index.html:90`. The overlay opacity slider goes down to 0.3. Window
  opacity fades text and plate together, so over a white scene text drops
  to about 1.8:1 and text-muted / status-warn to about 1.5:1; at 0.85
  text-muted is about 4.3:1. Fix: opacity floor 0.9 (section 5.2 floor is
  0.87; 0.9 keeps the 0.05 step grid), clamp saved layouts on load, update
  the limit tests. Not trivial: it changes layout validation. ROADMAP row
  DS-OPACITY below.
- F2 [S1, C2, FIXED] `web/app.css:189`. Selects and the number input used
  kit `border` (1.43:1 light, 1.59:1 dark on surface). Now
  `var(--fk-text-muted)` (6.68 / 7.18).
- F3 [S1, C2, FIXED] `web/app.css:175`. `button.secondary` (Dismiss,
  Dismiss all) edge used kit `border`. Now `var(--fk-text-muted)`.

### S2 - major

- F4 [S2, O3, FIXED by DS-SCALE] `server/al/layout.py:20`, `app/shared/layout.js:28`,
  `web/index.html:87`. Minimum scale 0.75 renders the 13px secondary
  overlay text at 9.75px. Fix: scale floor 0.95 (12.35px). ROADMAP row
  DS-SCALE.
- F5 [S2, P4 / P1 / P5, FIXED by DS-NLM] `server/al/state.py:25` (`summarize`, lines
  29-64). Templates do not follow 0001 section 9 ("AFK on", "is now
  level", "Zone: X"); missing fields print "None" ("None died"); line 33
  shows the internal area id; the fallback prints the raw event type; no
  exact-output test. Fix: the section 9 templates with "character unknown"
  defaults, a fallback "Something happened in the log", and
  `tests/test_summarize.py` with one exact-string assert per template.
  ROADMAP row DS-NLM.
- F6 [S2, P2 / P3, FIXED] `web/app.js`. Internal / blaming copy replaced:
  "token rejected or core stopped" -> "can't reach AshLight - restart it";
  "no token - open the link AshLight printed" -> "open AshLight from the
  link it showed at start"; "Layout unavailable (core stopped?)" -> "Can't
  load the overlay settings. Is AshLight running?"; "Not saved: HTTP nnn" ->
  "Not saved. Try again."; "Could not record your choice: HTTP nnn" ->
  "Your choice was not saved. Try again." (the HTTP detail goes to
  console.warn).
- F7 [S2, P2, FIXED] `app/overlay/overlay.js:49`. Overlay status "core not
  running" -> "AshLight offline".
- F8 [S2, N5, FIXED by DS-TRADE-EXPIRE] `server/al/state.py:14` / `:89`. Trade cards leave only
  by eviction (5 max) or a dashboard click, so a stale request sits on the
  overlay forever. Fix: expire a request 10 minutes after `at` in the
  snapshot, say "Requests clear after 10 minutes." under the Trade
  requests heading, keep Dismiss. ROADMAP row DS-TRADE-EXPIRE.
- F9 [S2, N4, FIXED by DS-HUD-AFK] `app/shared/render_gate.js:28`. The HUD never shows
  AFK / DND although 0001 section 7.2 asks for it. Fix: put "AFK" / "DND"
  in the status slot when live, add a shared.test.js case. ROADMAP row
  DS-HUD-AFK.
- F10 [S2, P5, FIXED] `app/shared/format.js:80`, `web/app.js:114`. A missing
  sender showed "?". Now "unknown player".
- F11 [S2, P8, FIXED] `web/index.html:75`. Empty state "No events yet." ->
  "Nothing yet. Zones, level-ups, deaths and whispers show up here as you
  play."

### S3 - minor

- F12 [S3, P5, FIXED] `app/shared/format.js:74`, `web/app.js:110`. "no
  price" -> "no price set" (test updated in `app/test/layout.test.js`).
- F13 [S3, P1, FIXED] `web/app.js:256`. "Client.txt waiting" -> "waiting
  for Client.txt"; "Client.txt not found" -> "Client.txt not found - start
  the game once".
- F14 [S3, type scale, FIXED] `web/app.css:143`. Event kind tags 0.8rem
  (12.8px) -> 0.8125rem (13px floor).
- F15 [S3, P8 / P5, FIXED by DS-HUD-EMPTY] `app/shared/render_gate.js:30`. Before the first
  snapshot the model blanks zone / level / deaths, so the "AshLight"
  placeholder disappears and a lone "|" shows. Fix: null-snapshot model
  `zone: "AshLight", level: "", deaths: ""` and hide `.sep` when a side is
  empty. ROADMAP row DS-HUD-EMPTY.
- F16 [S3, P5, FIXED] `app/shared/format.js:38`. Unknown level "Lv -" ->
  "Lv unknown" (test updated in `app/test/shared.test.js`).
- F17 [S3, O4, FIXED by DS-HUD-CLIP] `app/shared/format.js:50` and `:78`. The " (HO)"
  suffix is added after the 28-char clip (line can reach 33 chars); stash
  text "tab N L3 T5" is not glanceable. Fix: clip to `max - 5` in a
  hideout; write `tab Sale (3,7)`. ROADMAP row DS-HUD-CLIP.

### S4 - nit

- F18 [S4, C3, FIXED] `app/overlay/overlay.css`. Literal `#000` text-shadow
  -> `--al-shadow` token.
- F19 [S4, doc drift, FIXED] `docs/design/0001-design-system.md` 5.2. The
  reviewer recomputed the window-opacity figures without per-channel
  rounding (+0.03). The doc now states the method (8-bit rounded
  composites, as the framebuffer stores them); the numbers stand.
- F20 [S4, S2, FIXED] `web/app.css:88`. "Stop reading Client.txt"
  link-button now has 4px vertical padding and `min-height: 24px`.

## Checklist result at audit time

FAIL: C1, C2, P1, P2, P3, P4, P5, P8, N4, N5, O3, O5. PASS: C3, C4, C5, C6,
P6, P7, N1, N2, N3, N6, O1, O2, O4, O6, S1-S5. After this change C2, P2,
P3 and P8 pass; C1 / O5 (F1), O3 (F4), P1 / P4 / P5 (F5), N4 (F9) and N5
(F8) stay open.

## Proposed ROADMAP rows (for the ROADMAP owner; not added here)

- DS-OPACITY (S1): raise the overlay opacity floor to 0.9 in
  `server/al/layout.py`, `app/shared/layout.js` and the dashboard slider;
  clamp older saved layouts; update layout tests. Accept: no overlay text
  pair under 4.5:1 over a white scene at the floor (0001 5.2).
- DS-SCALE (S2): raise the overlay scale floor to 0.95 in the same three
  places so 13px text never renders under 12px. Accept: layout tests and a
  0001 O3 check.
- DS-NLM (S2): rewrite `summarize` to the 0001 section 9 templates with
  honest defaults and no internal ids; add `tests/test_summarize.py` with
  one exact-output assert per template.
- DS-TRADE-EXPIRE (S2): trade requests expire 10 minutes after arrival;
  the dashboard states the rule; Dismiss stays.
- DS-HUD-AFK (S2): show AFK / DND in the overlay status slot; add the
  field to the render gate and a test.
- DS-HUD-EMPTY (S3): a sensible HUD before the first snapshot (no lone
  separator).
- DS-HUD-CLIP (S3): clip the zone before adding "(HO)"; glanceable stash
  position text.
- DS-REVIEW-HOOK (process): run the `design-reviewer` agent on every
  change to `web/`, `app/overlay/`, `app/shared/` or `summarize` before
  commit (lane prompt or pre-commit reminder).

## Follow-up: DS-* rows (2026-11-16)

All seven open findings fixed by the DS-OPACITY, DS-SCALE, DS-HUD-EMPTY,
DS-HUD-CLIP, DS-NLM, DS-HUD-AFK and DS-TRADE-EXPIRE rows (one branch, see
`git log --grep DS-`). Second design-reviewer pass on that change: PASS,
S1=0 S2=0 S3=2 S4=2.

- R1 [S3, P1] exchange trades read "Coin wants 10 Chaos Orb - for 1 Divine
  Orb". Kept: "for" is what the overlay card (`format.js` tradeCard) and the
  dashboard trade list already print, and without it "10 Chaos Orb - 1
  Divine Orb" does not say which side is paid. Reverses if: a later pass
  changes all three sites together.
- R2 [S3, N5] an expired card clears on the next SSE heartbeat (15 s), so it
  can stay up to 15 s past 10 minutes. Accepted: the stated rule stays
  true to the minute the dashboard shows.
- R3 [S4] layout.py line-continuation style: fixed.
- R4 [S4] this doc and ROADMAP updated (this section).

Decision: lenient layout load now clamps an out-of-range number to its
bound instead of resetting it to the default (alternatives: reset, or a
one-off migration). Why: keeps the user's nearest choice and matches the
`layout.js` mirror. Reverses if: the section 5.2 floors change.
