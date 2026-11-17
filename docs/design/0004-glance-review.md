# 0004 - Glanceability review (UX-REVIEW)

Date: 2026-11-17. ROADMAP row UX-REVIEW: dashboard (`web/`) and overlay
(`app/overlay/`, `app/shared/`) against the glanceable-UI rules of
research 0008 (contrast, type scale, motion, phone width). ACCEPT: findings
fixed or filed. Earlier passes: audits 0002 and 0003.

Method: static review of the stylesheets, scripts and layout limits, and
contrast recomputed with the WCAG 2.2 formula from the token files (the
same maths as `tests/test_design_contrast.py`). Every rule below is now held
by `tests/test_ux_review.py`, so a later change that breaks it fails a test
instead of waiting for the next review.

## Research 0008 rules checked

- R1 high contrast, 7:1 target for glance text (WCAG 2.2 SC 1.4.6).
- R2 colour is a secondary signal (SC 1.4.1).
- R3 no animation by default, honour prefers-reduced-motion (SC 2.2.2,
  2.3.3).
- R4 large type, player-configurable text size and a high-contrast mode
  (Xbox accessibility guideline 101).
- R5 repaint at most 4-10 Hz; highlight only on meaningful change.
- Phone / narrow width: design 0001 section 4 (320 px, no horizontal
  scroll).

## Findings

- U1 [S3, R1; fixed] Design 0001 section 5.2 measures overlay text only at
  window opacity 1.0, but the default and the floor (`layout.js`
  LIMITS.opacity) are 0.9. Measured over a white scene at 0.9: text 9.34,
  text-muted 4.80, status-warn 4.96, status-bad 3.92. status-bad would fail
  4.5:1 at the default opacity; it is not used as overlay text today. Fix:
  a test computes every `color:` the overlay actually uses at the opacity
  floor read from `layout.js` and fails under 4.5:1; 0001 section 5.2 now
  says status-bad is not an overlay text colour.
- U2 [S3, R1; fixed] The 7:1 glance target was written in research 0008
  but held nowhere. Measured: dashboard glance values (zone, level, deaths,
  session, zone timer) use the full text colour, 13.89 / 15.37 and up in
  both themes; overlay zone line, timer and numbers 9.34 at the opacity
  floor. Fix: tests for both, plus a test that no glance value takes a
  muted or status colour.
- U3 [S2, R4; fixed] No high-contrast mode. Fix: both surfaces follow the
  OS / browser "more contrast" setting (`@media (prefers-contrast: more)`),
  zero clicks: muted text takes the full text colour; the overlay plate
  drops its own alpha (the window opacity, 0.9 to 1.0, still applies, so
  about a tenth of the scene can still show through). The item-check card's
  neutral edge moved to its own `--al-edge` token so it stays grey and
  distinct from the green upgrade edge (design review UX2). In this mode
  the `|` separator and secondary labels lose their grey hierarchy; that
  is the intent of the mode. Status colours (warn, bad, ok) are unchanged.
- U4 [-, R4; holds, guarded] Type floor: dashboard smallest 13px (kind
  tags), overlay smallest 13px x scale floor 0.95 = 12.35px >= 12px.
  Text size is configurable: the dashboard by browser zoom (the viewport
  meta does not block zoom), the overlay by the Size slider (0.95-2.0).
  Tests guard both floors and the viewport meta.
- U5 [-, R3 / R5; holds, guarded] No animation, transition, keyframes or
  smooth scroll in the dashboard; the overlay kills both outright; no
  script uses requestAnimationFrame or the Web Animations API; the
  reduced-motion block stays. SSE pushes are coalesced to 4 Hz
  (`server/al/http.py` SSE_MIN_INTERVAL_S); dashboard timers tick at 1 Hz,
  the overlay timer only on its minute roll-over. Tests guard the CSS and
  scripts.
- U6 [-, phone width; holds, guarded] No fixed width, min-width, flex basis
  or grid track in the dashboard is wider than a card's content box at
  320 px (254 px); the three wide grids use `min(Npx, 100%)`. The live
  320 / 360 px pass of audit 0003 (G3, G18) stands for the tiles.
- U7 [S4, phone width; filed] Not re-measured live: the cards added after
  audit 0003 (Act times table, item check, price / upgrade link, build
  view) at 320 px in a real browser. This headless lane has no browser;
  the static test above is the guard. Filed for the next interactive
  design pass (hand-off / ROADMAP by the loop), no code change expected.
  Done 2026-11-17 (ROADMAP UX-U7): headless Chrome over a core fed a
  replayed Client.txt fixture plus a pasted build and one item check, at
  320 / 768 / 1440 px in dark, light and forced colours. No horizontal
  scroll at any width (scrollWidth = clientWidth). One defect: a long
  unbroken character name under the level ran past its tile into the
  deaths tile at 320 px; fixed with `overflow-wrap: anywhere` on
  `.stat .sub` and a test. Forced colours drop the status hues, but every
  badge (Upgrade, link ready, live, TRADE / DEATH tags) carries its word,
  so no meaning is lost (R2 holds).
- U8 [S4, R4; filed] Windows forced-colours mode on the transparent overlay
  window is not verified: forced colours may repaint the plate or the
  transparent page background. Filed with U7 for the next live pass.
  Done 2026-11-17 (ROADMAP UX-U8): the overlay page in an Electron 45
  transparent window (capturePage keeps alpha) under forced-colors
  emulation stays transparent outside the plates. Headless Chrome, by
  contrast, paints the viewport Canvas in this mode, so the root now opts
  out of forcing (`forced-color-adjust: none`, background transparent)
  and never depends on the Electron behaviour; the plates opt back in.
  Defects fixed: the trade warn edge and the upgrade green edge both fell
  to plain CanvasText (now Highlight, a kept system colour), and the plate
  became 92 percent Canvas (now opaque Canvas). Tests guard all three. A
  real OS high-contrast theme switch was not exercised (emulation only).

## Live pass, batch 2 (2026-11-17)

Method: a core on a spare port in the AshLight block with its own
runtime and sidecar dirs, a scratch Client.txt fed by
`tools/synth_client.py`, headless Chrome over CDP (`--in-process-gpu`),
and emulated device scale factors.

- U10 UX-FIRSTRUN [S3; fixed] Cold start (no consent, no config, web data
  off, no Path of Building calc). The one required click (Allow reading
  Client.txt) is the first card, and run.ps1 opens the dashboard by
  itself. Friction found: (a) the overlay said only "not reading", not
  where to fix it; now `not reading - see dashboard`, flush left
  (an empty number row left a 6 px indent); (b) the deaths tile showed
  "0" and "0 level-ups" before anything was counted while the overlay
  shows no numbers; now `-` over `Counts once reading starts`; (c) the
  Act times card told a new player to run `scripts/build.ps1` while not
  in an act; that note now shows only inside an act; (d) the consent
  card printed the registry's lower-case Steam path; discovery returns
  the file's real spelling. Every other card already explains itself
  (item check, price, build, web data, Recent).
- U11 UX-DPI [S3; fixed] Overlay at device scale 0.95, 1, 1.25, 1.5 and 2
  over a white scene; dashboard at 1080p 100 / 125 / 150, 1440p 100, 4K
  100 / 200. No clipping, no horizontal scroll (scrollWidth =
  clientWidth everywhere). Gap: 13 px secondary text at 4K and 100
  percent is about 2 mm tall (163 ppi on 27 in), roughly 10 arcmin at
  70 cm, under the about 16 arcmin legibility floor; 1080p 24 in (3.6
  mm, about 18 arcmin) and 1440p 27 in (3.0 mm, about 15 arcmin) pass or
  sit at it. Fix: `layout.js autoScale` (design 0001 section 10).
  Placement ruled by an adjudicator: top-right stays (design 0001
  section 10). The dashboard keeps its 1100 px column on wide screens;
  the player sizes it with browser zoom.
- U12 UX-COPY [S4; fixed] "Connected to a game server" was listed before
  every zone and halved the useful rows in Recent: no longer listed.
  The overlay said "no Client.txt" for a known but quiet file: now
  `waiting for log` (short enough to fit after the numbers; design
  review F1, guarded by a 15-character test). "Graphics
  settings for this PC" (the card says "computer"), "Overlay position"
  (it also sets size and opacity) and "Edge gap (px)" reworded.
- U13 UX-PERF [-; holds] Dashboard fed 20 synthetic sessions (800 log
  lines, about 600 events) in 13 s: 33 state pushes, handler mean 0.39
  ms, max 1.1 ms; 0 long tasks; 1 Hz tick mean 0.09 ms; DOM nodes 1256
  before, 1265 after (after GC; the list is capped at 30 rows); JS heap
  flat. No regression. The recent list now skips its rebuild on pushes
  that do not change it (`status.js eventsKey`).

design-reviewer on batch 2: PASS WITH FINDINGS S1=0 S2=0 S3=2 S4=2, all
fixed (quiet-file word shortened and width-tested, deaths dash has an
aria-label, combined zoom capped at 2.5).

## Kept by decision

- K1 (SC 2.2.2): the zone and session timers keep updating with no pause
  control. Why: the timer is the content itself (the "essential" exception
  of SC 2.2.2), it changes text only, no motion, at 1 Hz or less.
  Reverses if: a timer gains motion or a flash, or a player asks to hide
  it.
- K2 (R1): the overlay status word (offline, AFK, no Client.txt) stays in
  status-warn, 4.96:1 at the opacity floor, under the 7:1 glance target.
  Why: it is a 13px secondary slot; the word itself is the signal and
  meets 4.5:1 (SC 1.4.3). The high-contrast block leaves it at 4.96 too.
  Reverses if: players miss the offline / AFK word in play.

## Design review

design-reviewer on this diff: PASS WITH FINDINGS S1=0 S2=0 S3=2 S4=3.
UX1 (plate wording) and UX3 (stale 0.87 / 0.3 floor text in 0001 5.2)
fixed in the docs; UX2 fixed with `--al-edge`; UX4 fixed with tests for
the override order and the high-contrast ratio; UX5 filed as U8.

## Counts

Before: S1=0 S2=1 S3=2 S4=2. After: S1=0 S2=0 S3=0 open, S4=2 filed (U7,
U8).
