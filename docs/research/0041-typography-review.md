# 0041 - Typography review (dashboard and overlay)

Date: 2026-11-18. For the ultraplan (docs/plan/README.md), dimension B5
typography. Scope: every font stack, size, weight, line height, letter
spacing, numeral setting and truncation rule in `web/` and the overlay;
legibility on a second monitor at 60-90 cm and of the overlay at 1080p,
1440p and 4K; a measured overlay scrim / halo recipe; a small type scale
that becomes design-system tokens.
Status: verified

## Sources (all accessed 2026-11-18)

- WCAG-CM: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
  (SC 1.4.3: 4.5:1, large text 3:1 at 24px or 18.5px bold; 4.5 = 3 x 1.5
  to cover the contrast loss of about 20/40 acuity; a thin outline counts
  as part of the glyph, a wide halo counts as background).
- WCAG-CE: SC 1.4.6 Contrast (Enhanced), Level AAA, 7:1 for normal text
  and 4.5:1 for large text,
  https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html
  (re-fetched by the verifier 2026-11-18).
- WCAG-TS: https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
  (SC 1.4.12: content survives line height 1.5, paragraph 2x, letter 0.12em,
  word 0.16em overrides without clipping).
- MS-TYPE: https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography
  (Windows ramp 12/16, 14/20, 18/24, 20/28, 28/36, 40/52, 68/92 epx;
  minimums 14px semibold, 12px regular; Semibold instead of Bold for
  emphasis; ellipsis for truncation in most cases (the page prefers a plain
  clip only where the container is well defined and no "see more" exists);
  50-60 letters per line; Segoe UI Variable is the Windows 11
  face and must be named in CSS for HTML; Selawik is a metric-compatible
  open font for non-Windows use; page updated 2026-07-14).
- MS-FAQ: https://learn.microsoft.com/en-us/typography/fonts/font-faq
  (page dated 2024-11-19; read directly by the verifier: Windows fonts may
  be named in a CSS font stack, but may not be copied to a server for
  self-hosting, converted to WOFF / WOFF2 or other formats, or shipped
  inside an app or game; Segoe UI Variable is not licensable for use
  outside Microsoft products).
- MDN-FF: https://developer.mozilla.org/en-US/docs/Web/CSS/font-family
  (system-ui is meant for UI text; ui-monospace is a newer generic). Not
  re-fetched by the verifier; nothing decision-relevant rests on it.
- CIU: https://caniuse.com/extended-system-fonts (fetched by the verifier:
  ui-serif / ui-sans-serif / ui-monospace / ui-rounded unsupported in every
  listed Chrome version up to 160 and Edge up to 156). Confirmed locally
  by P-FONT.
- SUV: https://tigeroakes.com/posts/segoe-ui-variable (third party,
  published 2022-05-25: `system-ui` does not pick up Segoe UI Variable on
  Windows 11; the face must be named as "Segoe UI Variable Text", "Small"
  or "Display", the bare family name does not work in browsers). The
  article does not say what `system-ui` resolves to instead; "legacy Segoe
  UI on Windows 11" is an inference, UNVERIFIED (no Windows 11 machine).
- LB: Legge and Bigelow 2011, "Does print size matter for reading? A
  review of findings from vision science and typography", Journal of
  Vision 11(5):8, https://pmc.ncbi.nlm.nih.gov/articles/PMC3428264 (read
  directly by the verifier: critical print size about 0.2 deg x-height
  for normal sight, individual values 0.15 to 0.3 deg; fluent range about
  0.2 to 2 deg).
- DOB: Dobres et al. 2016, Ergonomics 59(10):1377-1391,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC5213401 (glance legibility:
  light-on-dark needed about 40 percent longer exposure than dark-on-light
  (119.4 vs 85.3 ms table means; the paper's text says 38.6 percent);
  3 mm text raised thresholds 26 percent for a
  humanist face, 62 percent for a square grotesque, vs 4 mm; thresholds
  rise with age, about 70 ms at 20 to 126 ms at 65).
- PACK: the ultraplan evidence pack (`<sidecar>\Scratch\up-evidence`),
  cited by name relative to it: `README.txt`, `run/summary_lines.txt`,
  `run/<state>/dash-<tab>-<W>x<H>.json`, `run/<state>/overlay.json`,
  `run/<state>/overlay-1920x1080-<backdrop>.png`.
- P-FONT: own probe, `<sidecar>\Scratch\up-0041\probe\fonts.json` and
  `fonts2.dom.txt` (headless Chrome 157 on this Windows 10 machine: which
  families resolve, Segoe UI metrics, per-digit advance widths at
  400 / 600 / 700 with and without tabular-nums, line widths).
- P-REC: own probe, `<sidecar>\Scratch\up-0041\probe\recipes.html` rendered
  at device pixel ratio 1.0 and 1.25 (`recipes-1.png`, `recipes-125.png`),
  measured by `measure_recipes.py`: 9 overlay recipes x 7 backdrops (white,
  warm #f2e6c8, grey #808080, black, a 2 px black / white checker, bright
  "fire" stripes, a half white / half black split), contrast of the
  rendered glyph core (brightest 3 percent of pixels in the role box)
  against the plate 4+ px away from any glyph ("far") and 2 px away
  ("near").
- P-PX: own probe, `px_probe.py` on PACK `run/c` (real pixels of the
  overlay composites).
- Repo: `web/app.css`, `app/overlay/overlay.css`, `app/client/starting.css`,
  `app/shared/layout.js`, `app/main.js`, `docs/design/0001-design-system.md`
  sections 3, 5.2 and 10.

## Summary

- One sans family everywhere (`system-ui, "Segoe UI", sans-serif`), which
  resolves to Segoe UI on Windows 10 (P-FONT) and, per SUV, never to Segoe
  UI Variable on Windows 11 (what it does pick there is UNVERIFIED). No
  font is bundled and none should be: Segoe UI ships with Windows and may
  not be redistributed (MS-FAQ). The `ui-monospace` head of the mono stack
  is dead in Chromium (CIU, P-FONT); Consolas renders.
- The dashboard renders 11 sizes over three window sizes (13 to 44 px), up
  to 16 distinct styles in one Play view, because glance values use
  `clamp(..vw..)` and three meta sizes (13, 13.6, 14.4 px) sit 5 percent
  apart. Six fixed steps on the Windows ramp do the same job: 13 micro
  (legal line only), 14 meta, 16 body, 20 title, 28 glance, 40 hero.
- The overlay uses 4 sizes (16 / 15 / 14 / 13) 1 px apart: steps of 7
  percent are not a readable hierarchy. Two sizes (16 primary, 14
  secondary) fit the 258 px plate.
- The pack's "13 px secondary under 4.5:1 on bright backdrops" (3.81 white)
  is a modelling error: it faded the text over the already-faded plate.
  Real pixels (P-PX) give 4.88 white / 5.06 warm for the muted colour, so
  it passes with a 0.38 margin, but the antialiased 13 px glyph core
  measures 4.56 over white, 4.18 over a fine checker, and the 15 px "|"
  separator 3.75 (P-REC r0). Small text deserves 7:1 (WCAG-CE).
- Recipe (R1): the window opacity fades the plate only, never the text;
  plate alpha 0.86 default, 0.80 floor; secondary text #c3c9d0 and warn
  #f0bd55; a soft 2 px halo; 14 px minimum. Solid-colour worst case over
  white at 0.86: primary 10.28, secondary 7.59, warn 7.30 (all >= 7:1).
- Numerals: Segoe UI Regular and Bold have tabular digits by default, but
  Semibold (600) is proportional (P-FONT: "1" is 4.02 vs 5.55 units). Two
  600-weight number spots lack `tabular-nums` (price values, tab marks).
- Physical size: the overlay's 13 px secondary line is 8.0 arcmin x-height
  at the 1440p reference (65 cm), two thirds of the 12 arcmin critical
  print size (LB); 14 px gives 8.6, 16 px 9.9. Dashboard glance values
  (28 / 40 px) clear 12 arcmin even at 90 cm on a 24 inch 1080p screen.

## Current state

Font stacks (3 in use, plus one in the client splash):
- Sans: `web/app.css:12` (body, 16px/1.4), overlay `app/overlay/overlay.css:52`,
  `:84`, `:107`. 11325 of 12105 text elements in the pack (PACK
  `run/*/dash-*.json` text_styles, aggregated).
- Mono: `ui-monospace, Consolas, monospace` at `web/app.css:46` (pill
  glyphs), `:366`, `:467`; 762 elements. `ui-monospace` does not resolve
  in Chromium: its measured width equals the generic fallback (P-FONT
  `width_of_probe_100px`), so Consolas renders.
- `code` with the UA default `monospace` (consent path, filter lines): 18
  elements at 16 px Consolas.
- Splash: `app/client/starting.css:8` puts `"Segoe UI"` first, the reverse
  of the app order; same face in practice.
- Segoe UI Variable is not installed on this Windows 10 machine (P-FONT:
  the named Variable faces fall back). No `@font-face` anywhere; the
  overlay CSP (`app/overlay/index.html`) is `default-src 'none'` with no
  `font-src`, so a bundled font could not even load there.

Sizes (declarations in `web/app.css`, by value):
- 0.9rem (14.4px) x17, 0.85rem (13.6px) x7, 0.8125rem (13px) x4 (event
  kind tags `:173`, tab marks `:500`, and two inside media queries: footer
  `:558`, short-window stat label `:567`), 1rem x3, 1.6rem x1 (`:149`), 1.3rem x1 (`:541`),
  clamp glance `:122` and `:539`, clamp zone `:132` and `:540`.
- Rendered over the pack (PACK key measurement 9; aggregate): 13, 13.6,
  14.4, 16, 20.8, 24, 28.16, 32, 33.28, 36, 44 px. Share of visible
  characters: 16px 45.3 percent, 13px 33.2 (mostly the footer and event
  kind tags), 14.4px 19.3, 13.6px 2.1, all glance sizes under 0.1.
- Per view: Play 12-16 styles and 6-7 sizes; Build 8-12 / 3-4; Items 9-10
  / 3-4; Run 9-10 / 3-4; Settings 10 / 3 (aggregate of PACK text_styles).
- Overlay (`app/overlay/overlay.css`): zone 16px (`:59`), HUD numbers 15px
  (`:52`), cards 14px (`:84`, `:107`), secondary 13px (`:67`, `:89`,
  `:116`); all weight 600, line height 1.3.

Weights: 400 / 600 / 700. Characters by weight: 400 89.7 percent, 700
7.3, 600 3.1 (aggregate). 700 is used for headings, kind tags, the
selected tab (`web/app.css:492`) and glance values; 600 for labels, table
heads, item names, price values (`:319`).

Line height: 1.4 inherited everywhere (11997 elements), 1.1 on glance
values (`:124`). Overlay 1.3.

Letter spacing: brand 0.02em (`:34`), stat labels 0.05em uppercase
(`:118`). Uppercase also on event kind tags (`:176`, 13px 700).

Numerals: `font-variant-numeric: tabular-nums` only via `.mono`
(`web/app.css:18`), applied to level, deaths, session, zone timer
(`web/index.html:96`, `:112`, `:125`, `:130`), act / run / history tables
(`web/acts.js:132`, `web/runs.js:119-121`, `web/history.js:118-119`) and
some `dd` values (`web/app.js:365`, `web/health.js:110`). The overlay sets
it on every plate (`overlay.css:53`, `:85`, `:108`). Not set: price values
(`web/app.css:319`, weight 600), tab marks (`:501`, 600), event times
(`:170`, 400 so already tabular by the font).

Truncation and wrapping: dashboard has 30 `overflow-wrap: anywhere`, 8
`nowrap`, 2 `pre-wrap`, no `text-overflow`; the pack found 0 truncated
strings in 135 captures. Glance numbers never break (`:131`); the zone name
wraps between words (`:132`). Overlay: every row is one line with ellipsis
(`overlay.css:58`); the zone name and the trade sender shrink first so the
timer and "+N more" stay (`:61-62`, `:91-93`). PACK key measurement 15
notes a long seller name ellipsed.

Overlay compositing: page CSS `html { opacity: 0.9 }` (`overlay.css:28`),
re-applied from the layout slider by `app/main.js:163-175` through
`layout.js` `opacityCss` (`app/shared/layout.js:139-141`), LIMITS opacity
[0.9, 1.0] and scale [0.95, 2.0] (`layout.js:31`); plate
rgba(15, 18, 22, 0.92) (`overlay.css:16`); shadow `0 1px 1px #000`
(`:54`). `autoScale` zooms the HUD so its text is never physically smaller
than at 1440 DIP height (`layout.js:44-52`).

Design system: `docs/design/0001-design-system.md` section 3 proposes 7
dashboard size tokens (`--al-fs-caption` .. `--al-fs-glance`) that were
never created: `web/app.css` has no `--al-fs-*` variable. Tests pin the
13 px floor (`tests/test_ux_review.py:198`), the plate colour
(`tests/test_design_contrast.py:63`, `tests/test_ux_review.py:94`, `:170`)
and the opacity / scale floors (`app/test/layout.test.js:22-35`, `:160`,
`tests/test_overlay_layout.py:49`).

## Findings

F1. The pack's overlay contrast model under-reports bright scenes; the real
margin is thin, not negative.
- Evidence: PACK `run/c/overlay.json` "method" composites "text x page
  opacity over" the faded plate, giving muted text #8f979f on #383b3e =
  3.81 over white. Group opacity actually fades the finished layer, so a
  text pixel is 0.9 text + 0.1 backdrop: P-PX samples #a3aab2 on #373a3d =
  4.88 over white, 5.06 warm, 5.69 grey, 6.03 black (the plate pixel
  matches the pack, the text pixel does not). Design 0001 section 5.2
  already states 4.80 at 0.9, which agrees with the pixels.
- Rendered glyph cores at today's recipe (P-REC r0, far field, dpr 1.0 /
  1.25): zone 16px 9.33 / 9.33 over white; numbers 15px 9.20 / 9.33; card
  head 14px 8.92 / 9.15; amber status 13px 4.82 / 4.98 (4.15 over the
  split, 4.62 over the checker); muted 13px 4.56 / 4.65 (4.18 checker);
  "|" separator 15px 3.75 / 4.24.
- Per role over the brief's three backdrops (P-REC r0, dpr 1.0, far field;
  white / warm #f2e6c8 / grey #808080): zone 16px 9.33 / 9.76 / 11.30;
  card head 14px 8.92 / 9.35 / 10.82; amber status 13px 4.82 / 5.06 /
  5.71; muted secondary 13px 4.56 / 4.75 / 5.34; "|" separator 3.75 /
  3.87 / 4.32. Worst case for every role is white (the fine checker and
  the split are lower still for the two small roles, above). Only the two
  13 px secondary roles and the separator sit under 7:1 anywhere; the
  separator is the only glyph under 4.5:1.
- Why: the plan must not size a fix to a wrong number, and must not call
  the overlay compliant either. Secondary lines carry the trade location
  and the item-check reason, read in one glance during play; at 13 px and
  under 5:1 they are the first text to fail over snow, sand or a bright
  spell.

F2. The fade lands on the text, the one place it should not.
- Evidence: `overlay.css:28` and `layout.js:139-141` fade the whole page.
  The overlay comment at `overlay.css:14-15` ("keeps 4.5:1 even over a
  pure white game scene") is true only at window opacity 1.0 (P-REC r1:
  muted 5.57, status 6.01 over white). Design 0001 section 10 already says
  "decorative transparency comes from the plate, not from fading the
  text", and the code does the opposite.
- Why: the same see-through look is reachable with opaque text and a
  lighter plate (P-REC r2 / r8), which buys 1.0-1.5 ratio points for free.

F3. Four overlay sizes 1 px apart are noise, not hierarchy.
- Evidence: 16 / 15 / 14 / 13 px (`overlay.css:59`, `:52`, `:84`, `:67`),
  ratios 1.07. PACK key measurement 13 lists the same 4 sizes. The colour
  already separates primary from secondary.
- Width check (P-FONT `fit`, 600 weight): HUD line 2 "Lv 47 | 3 deaths" is
  125.7 px at 15 and 134.1 px at 16; status word 86.7 px at 13, 93.4 at 14;
  card line "5 exalted | tab Sale (3,7)" 218.3 at 13, 225.6 at 14. The plate
  has 238 px for text (258 max minus 2 x 10 padding). Line 2 at 16 + 14
  with a short status: 134 + 6 + 93 = 233 px, fits; a long status word
  (166.6 px at 13) already overflows today and keeps its ellipsis.
- Height: 2 x 16 x 1.3 + 3 x 14 x 1.3 + paddings = about 128 px of the 176
  px window (PACK key measurement 13: 125.6 today).

F4. The overlay's smallest text is physically small for a glance.
- Evidence: Segoe UI x-height is 0.500 em (P-FONT metrics). At 65 cm, 13 px
  CSS gives x-height 1.80 mm / 9.5 arcmin on a 24 inch 1080p panel and 1.52
  mm / 8.0 arcmin at the 1440 DIP reference that `autoScale` normalises to
  (27 inch 1440p at 100 percent, 27 inch 4K at 100 or 150 percent); 14 px
  gives 8.6 and 16 px 9.9 arcmin there. The critical print size for full
  reading speed is about 0.2 deg = 12 arcmin (LB).
- Glance research: light-on-dark already costs about 40 percent more
  exposure time, and the small-size penalty grows with smaller text (DOB).
  The overlay is light-on-dark by necessity (a dark plate is the only thing
  that holds contrast over any scene), so size is the lever left.
- Why: a 1 px floor raise (13 to 14) is cheap; normalising `autoScale` to a
  lower reference (R6) lifts every 1440p / 4K user by 20 percent.

F5. The dashboard has too many sizes and they drift with the window.
- Evidence: 11 sizes across 3 windows, 6-7 per Play view, up to 16 styles
  in one view (PACK key measurement 9; `run/e/dash-play-1024x700.json`).
  Causes: (a) `clamp(2rem, 2.6vw, 2.75rem)` and siblings (`web/app.css:122`,
  `:132`, `:539`, `:540`) make the zone name 24 / 28.16 / 36 px and level
  32 / 33.28 / 44 px at 1024 / 1280 / 1920 wide; (b) three meta sizes
  13 / 13.6 / 14.4 px used for near-identical roles (labels, sub-headings,
  table heads, pills, footer); (c) card titles `h2` 16px bold are the same
  size as body (`:75`), so hierarchy rests on weight alone.
- Why: viewport-relative glance sizes change when the player resizes the
  companion window, so the zone name jumps 50 percent between layouts;
  near-duplicate sizes read as inconsistency, not as hierarchy. The design
  system's own token table (0001 section 3) was never implemented.

F6. Semibold text under 14 px and bold under 16 px break the Windows
minimum.
- Evidence: MS-TYPE sets 14 px as the minimum for semibold and 12 px for
  regular, and keeps Bold out of the ramp. AshLight renders stat labels at
  13 / 13.6 px weight 600 uppercase (`web/app.css:112-119`, `:567`), event
  kind tags 13 px weight 700 uppercase (`:171-178`), tab marks 13 px 600
  (`:495-502`), table heads 13.6 px 600 (`:239`), the "frozen" / zone tag
  13.6 px. 606 + 72 + 36 + 24 + 183 elements in the pack.
- Why: these are labels the player reads before the value; uppercase at
  13 px with tracking is the hardest text on the page and the target of
  the 13 px floor test.

F7. Semibold numbers jitter where `tabular-nums` is missing.
- Evidence: P-FONT digit advances at 10 px: Segoe UI 400 and 700 digits are
  all equal by default (5.391 / 5.752) but 600 gives "1" 4.023, "4" 5.762,
  "7" 5.361 against 5.552; with tabular-nums all become 5.552 except "7"
  (5.361, a 0.3 px difference at 16 px, a font quirk). Price values
  `.rates-list .rate-value` are 600 without tabular-nums (`web/app.css:319`),
  so a column of prices does not line up (a "1" is 2.4 px narrower at 16
  px); tab marks (counts, 600) shift too. The overlay already sets
  tabular-nums.
- Why: prices and counts update in place; misaligned or shifting digits
  are read as change.

F8. The selected tab widens by 7 percent and shifts its neighbours.
- Evidence: 400 to 700 on selection (`web/app.css:490-492`); P-FONT widths
  per 100 px probe 2223.9 (400) vs 2383.1 (700), +7.2 percent; "Items and
  prices" at 16 px grows about 8 px, moving every tab to its right on each
  click.
- Why: a shifting target under the pointer; a visible jump on every tab
  change in a UI that otherwise has zero motion (PACK key measurement 12).

F9. Dashboard contrast is fine; overlay colours are the gap.
- Evidence: dashboard minimum 5.31 dark (`#f0605a` on `#181c22`, 13 px, Run
  tab) and 4.90 light (PACK key measurement 10). Overlay secondary colours
  are the kit's dark muted / warn, chosen for a solid surface
  (`overlay.css:9`, `:12`), not for a translucent plate over a bright scene.
- Why: the overlay can take its own two secondary colours without touching
  the fleet kit tokens (`ops/fleet_kit/` is never edited locally).

F10. Truncation rules are sound; one decorative glyph fails contrast.
- Evidence: the zone name and sender shrink first so live numbers stay
  (`overlay.css:61-64`, `:91-93`); PoE mod lines start with the number, so
  an end ellipsis keeps the meaning. The "|" separator in muted grey is the
  lowest-contrast glyph on the overlay (3.75 rendered over white, F1) and
  carries no information a 10 px gap would not.
- Dashboard: `overflow-wrap: anywhere` x30 lets long item and zone names
  break inside a word only when a word alone overflows; 0 clipped strings
  in the pack. No WCAG 1.4.12 override was captured (PACK GAPS); the
  overlay rows are single-line ellipsis by design, so a spacing override
  would clip there.

F11. Line length and line height are inside guidance.
- Evidence: average 16 px character 7.53 px (P-FONT `fit` avg16), so a
  1600 px column holds far more than 60 characters only in prose blocks;
  prose is short (tips, zone guide notes) and sits in half-width columns
  (`web/app.css:550-551`). Body line height 1.4 is below the 1.5 a user
  may force (WCAG-TS), which is a survival test, not a target; MS-TYPE
  uses 14/20 (1.43) and 18/24 (1.33) for UI text.
- Why: no change needed beyond 1.5 for multi-line prose (R8).

## Recommendations

R1. Overlay legibility recipe: opaque text, translucent plate, lifted
secondary colours, soft halo.
- Action: drop the page `opacity` fade; the layout slider sets the plate
  alpha only (default 0.86, floor 0.80, max 1.0); overlay-only tokens
  `--al-ovl-text-2: #c3c9d0` (replaces muted on the overlay) and
  `--al-ovl-warn: #f0bd55`; text shadow `0 0 2px #000, 0 0 2px #000,
  0 1px 2px #000` in place of `0 1px 1px #000`; no text stroke.
- Numbers (solid colour over the composited plate, own calculation, plate
  rgba(15, 18, 22, a)):
  - a 0.86 over white / warm / grey / black: primary #e4e8ec 10.28 /
    10.76 / 13.09 / 15.58; secondary #c3c9d0 7.59 / 7.94 / 9.66 / 11.50;
    warn #f0bd55 7.30 / 7.65 / 9.30 / 11.07.
  - a 0.80 (floor): primary 8.30 white; secondary 6.13; warn 5.90.
  - Rendered glyph core at a 0.80 with 16 / 14 px and the halo (P-REC r3,
    dpr 1.0): zone 8.30, numbers 8.23, status 5.74, card head 7.90,
    secondary 5.88 over white; the same over the 2 px checker and the fire
    stripes; near-field 6.1-6.3 over the checker and fire. At 0.86 the core
    is estimated at about 7.2 for secondary (r3 core / solid = 0.96).
  - Today for comparison (P-REC r0): secondary 4.56, status 4.82, "|"
    3.75 over white.
- Why the alternatives lose (P-REC): r4 / r5 (plate 0.70 / 0.60, 2 px
  stroke) drop primary to 5.71 / 3.98 over white; r6 (no plate, outline
  only) reads 1.22-1.28 far-field over white, warm and fire (1.00 over the
  checker, 1.37 over the split); r8 (0.86 with
  today's colours) leaves secondary at 4.63.
- Impact: H. Every overlay text colour holds >= 7:1 (solid-colour
  calculation, re-computed by the verifier) at the default over a white
  scene (WCAG-CE level for small text), and the rendered glyph cores are
  estimated at 7.1-7.3 there; still >= 5.7 rendered at the floor.
- Mechanism constraint: the plate alpha stays page CSS inserted by
  `app/main.js` `applyOpacity` (`app/main.js:163-175`), never
  `BrowserWindow.setOpacity` (that comment records that window-level alpha
  drew nothing on the real desktop); the `prefers-contrast: more` block
  keeps its opaque `--al-plate: #0f1216` (`app/overlay/overlay.css:134-139`).
- Effort: S (CSS, `layout.js` opacityCss to a plate-alpha variable, tests).
- Risk: the slider's meaning changes from "whole HUD" to "background";
  saved layouts with 0.9-1.0 map linearly onto 0.86-1.0 so nobody's HUD
  gets lighter than the new default. Halo blur costs one rasterisation per
  text change (no animation; render_gate unchanged).
- ToS check: overlay rule (separate, transparent, click-through,
  non-focusable window; FPS budget in decision 0002): CSS only, no new
  window behaviour, no repaint frequency change. Nothing reads the screen
  to adapt the plate (that would be a screen watcher).
- Depends on: none. Amend design 0001 sections 5.2 and 10 (the opacity
  table and the "fade the plate, not the text" rule become the mechanism).
- Files likely touched: `app/overlay/overlay.css`, `app/shared/layout.js`,
  `app/main.js`, `web/index.html` (slider label "Background"),
  `app/test/layout.test.js`, `tests/test_ux_review.py`,
  `tests/test_design_contrast.py`, `tests/test_overlay_layout.py` (14
  `opacity` references, verifier grep), `tests/test_ux_settings_io.py`
  (1 reference: settings import of the old opacity value),
  `docs/design/0001-design-system.md`.
- Acceptance test: a unit test composites every overlay text token over
  the plate at the floor and default alpha over #ffffff and #f2e6c8 with
  8-bit rounding and asserts primary >= 7, secondary and warn >= 5.5 at
  the floor, >= 7 at the default; the CDP overlay smoke renders the plate
  over a white page and asserts the brightest-3-percent glyph core of the
  secondary role >= 5.5 at the floor; `html` has no `opacity` rule.
- ZERO-CLICK: applies at the next overlay start; nothing to press.

R2. Overlay type: two sizes, 16 and 14, and no separator glyph.
- Action: HUD both lines 16 px; cards (head and lines) 14 px; status word
  14 px; replace the "|" span with a 10 px gap (keep the screen-reader
  text); keep weight 600 and line height 1.3.
- Impact: M-H. Removes 2 near-duplicate sizes; the smallest overlay text
  grows 7.7 percent (8.0 to 8.6 arcmin at the reference); removes the
  worst-contrast glyph (F10).
- Effort: S.
- Risk: line 2 width 233 of 238 px with a short status (F3); a long
  status word ellipses as it does today. Re-check the HUD fits 280 x 176
  with the tallest card (about 128 px).
- ToS check: overlay rule as R1; CSS only.
- Depends on: R1 (same files; ship together).
- Files likely touched: `app/overlay/overlay.css`, `app/overlay/index.html`,
  `app/overlay/*.js` that renders the separator, `tests/test_overlay_layout.py`,
  design 0001 section 3 overlay table.
- Acceptance test: overlay CSS declares exactly two font sizes (16px,
  14px); the CDP smoke at scale 1.0 shows no role under 14 px computed,
  content height <= 176 px with HUD plus the tallest card, and line 2
  "Lv 100 3 deaths" plus "2 trades" not truncated.
- ZERO-CLICK: automatic.

R3. Dashboard type scale as tokens: six fixed steps on the Windows ramp.
- Action: define and use these (root 16 px, rem as the source):
  - `--al-fs-micro` 0.8125rem (13px), weight 400, line height 1.4: the
    legal / disclaimer footer only.
  - `--al-fs-meta` 0.875rem (14px), 400 or 600, 1.4: labels (uppercase,
    600, tracking `--al-track-caps` 0.04em), event kind tags (600, not
    700), table heads, pills, sub-headings, tab marks. Replaces 13, 13.6
    and 14.4.
  - `--al-fs-body` 1rem (16px), 400, strong 600, 1.4 (1.5 for prose).
  - `--al-fs-title` 1.25rem (20px), 600, 1.3: card titles (`h2`), the zone
    timer, the item-check verdict line.
  - `--al-fs-glance` 1.75rem (28px), 700, 1.15: zone name.
  - `--al-fs-hero` 2.5rem (40px), 700, 1.1: level, deaths, session; 2rem
    (32px) inside the existing short-window query (`web/app.css:565`).
  - Weights `--al-fw-regular` 400, `--al-fw-strong` 600, `--al-fw-hero`
    700 (glance and hero numbers only, MS-TYPE). Line heights
    `--al-lh-tight` 1.1, `--al-lh-snug` 1.3, `--al-lh-body` 1.4,
    `--al-lh-prose` 1.5. Numerals `--al-num: tabular-nums` (R4).
- Where: an AL-owned `:root` block at the top of `web/app.css` (the kit's
  `/tokens.css` stays colour-only and is never edited here); overlay sizes
  as `--al-ovl-fs-1` 16px / `--al-ovl-fs-2` 14px in `overlay.css` (it
  cannot load the core's CSS under its file:// CSP).
- Ratios: 14 / 16 / 20 / 28 / 40 matches the Windows ramp steps 14, 20,
  28, 40 (MS-TYPE) plus the web body 16; each step is at least 1.14x the
  one below, so every step is visibly distinct.
- Physical check at 90 cm, 24 inch 1080p, 100 percent (x-height 0.5 em):
  hero 40px 21.1 arcmin, glance 28px 14.8, title 20px 10.6, body 16px 8.5,
  meta 14px 7.4. Glance and hero clear 12 arcmin (LB) at the far end of
  the 60-90 cm range; title clears it up to 75 cm (12.7); body and meta
  are lean-in text, as today. At 125 / 150 percent Windows scaling the
  Electron zoom scales every step alike.
- Impact: H. Sizes per Play view 6-7 to 6 and constant across windows
  (11 to 7 overall including the short-window hero); distinct styles per
  view target <= 10 (from 16); fixes F5 and F6.
- Effort: M (about 40 declarations, one test update, design 0001 section
  3 table replaced).
- Risk: hero 40 vs 33.28 px today in the 1280 x 760 window would add
  height to an already overflowing left column (PACK key measurement 2:
  380 px); hence 32 px there. Card titles at 20 px add about 6 px per card;
  sequence after the Play layout work of 0042 / 0043 so the overflow fix
  and the scale land on the same measurements.
- ToS check: dashboard only (127.0.0.1 page); no floor rule touched.
- Depends on: the Play-tab layout recommendations in research 0042 / 0043
  and the target design (docs/plan/03-target-design.md) for which strings
  are glance strings.
- Files likely touched: `web/app.css`, `tests/test_ux_review.py`
  (`test_dashboard_type_floor_13px` becomes "13 px only for the footer,
  >= 14 px elsewhere, no 600/700 under 14 px"), `docs/design/0001-design-system.md`.
- Acceptance test: re-run the evidence pack at 1024x700, 1280x760,
  1920x950: every capture renders only sizes in {13, 14, 16, 20, 28, 32,
  40} px; 13 px appears only under `footer.foot`; no element with weight
  >= 600 under 14 px; no `vw` in any font-size declaration; Play distinct
  styles <= 10.
- ZERO-CLICK: automatic.

R4. Tabular numerals everywhere numbers live.
- Action: set `font-variant-numeric: tabular-nums` on `body` (dashboard)
  and keep it on the overlay plates; drop the `.mono` class's role as the
  only switch (keep the class for nowrap rules); right-align price values
  in `.rates-list` and give them `min-width` in `ch` so a column lines up.
- Impact: M. Fixes F7 (price column, tab counts) and stops any future 600
  number from jittering. Segoe UI 400 / 700 are unchanged (already
  tabular).
- Effort: S.
- Risk: tabular "1" looks a little loose in running text at 600; prose is
  400, where the font's default figures are already tabular, so no change
  shows there.
- ToS check: dashboard and overlay CSS only.
- Depends on: none (can ship before R3).
- Files likely touched: `web/app.css`, a CSS test in `tests/test_ux_review.py`.
- Acceptance test: CSS test asserts `body` declares tabular-nums; a CDP
  probe measures the advance of "1" and "8" inside `.rate-value` and `.tab-mark`
  as equal within 0.05 px.
- ZERO-CLICK: automatic.

R5. Tabs keep their width when selected.
- Action: selected weight 600 (not 700, MS-TYPE), and reserve the bold
  width: each tab label carries `data-label` and a `::after` copy at 600
  with `height: 0; visibility: hidden; overflow: hidden`, so the box is
  always as wide as its bold form. The bar and aria-selected stay.
- Impact: M. No tab bar shift on click (F8).
- Effort: S.
- Risk: none beyond a template change; screen readers ignore the hidden
  pseudo-element.
- ToS check: dashboard only.
- Depends on: none.
- Files likely touched: `web/app.css`, `web/index.html`.
- Acceptance test: CDP: the x position of the last tab is identical
  (within 0.5 px) with each tab selected in turn.
- ZERO-CLICK: automatic.

R6. Overlay physical size: normalise `autoScale` to 1200 DIP instead of
1440.
- Action: `AUTO_REF_HEIGHT` 1440 to 1200 (`app/shared/layout.js:44`), so
  1440p at 100 percent and 4K at 150 percent (both 1440 DIP tall) get zoom
  1.2, 4K at 125 percent (1728 DIP) 1.45 instead of 1.2, and 4K at 100
  percent 1.8 (`autoScale` caps at 2.0, `layout.js:51`); 1080p unchanged.
- Numbers: 14 px secondary (after R2) becomes 1.96 mm / 10.4 arcmin
  x-height at 65 cm on those screens (from 8.0 today at 13 px), about the
  1080p physical size; window 280 x 176 becomes 336 x 211 DIP.
- Impact: M. Most 1440p and 4K players get 20 percent larger overlay text
  with no setting.
- Effort: S.
- Risk: a larger window covers more of the game corner (it stays
  click-through and transparent outside the plates); the user scale
  slider still multiplies, MAX_ZOOM 2.5 still caps.
- ToS check: overlay rule and FPS budget (decision 0002): window size only,
  same repaint gate; research 0048 owns the budget check.
- Depends on: R2 (measure after the size change).
- Files likely touched: `app/shared/layout.js`, `app/test/layout.test.js`
  (`autoScale` expectations at `:98-106`), design 0001 section 10.
- Acceptance test: `autoScale` takes DIP bounds (`layout.js:49`), so the
  updated test asserts by DIP height: 1080 gives 1, 1440 (1440p at 100
  percent, 4K at 150 percent) 1.2, 1728 (4K at 125 percent) 1.45, 2160
  (4K at 100 percent) 1.8, 4320 (8K) 2; the overlay budget test stays
  green.
- ZERO-CLICK: follows the monitor; no click.

R7. Fix the contrast gate so it measures what the eye sees.
- Action: the overlay contrast test composites group opacity correctly
  (text = alpha x text + (1 - alpha) x backdrop over the layer) or, after
  R1, with opaque text; add a rendered-pixel check (glyph core vs far
  plate, as P-REC) to the overlay CDP smoke for the secondary role over
  white and a 2 px checker; record the evidence-pack model error in the
  pack's successor tooling.
- Impact: M. Stops a future false alarm (3.81) or a false pass (solid
  colour 4.88 while the antialiased glyph is 4.56).
- Effort: S-M.
- Risk: pixel thresholds depend on antialiasing; use a 5 percent tolerance
  and dpr 1.0 and 1.25 (P-REC shows the two agree within 0.3).
- ToS check: test tooling only, synthetic backdrops, no game capture.
- Depends on: R1.
- Files likely touched: `app/test/cdp/` overlay smoke, `tests/test_ux_review.py`.
- Acceptance test: the new check fails on today's CSS (secondary core 4.56
  < 5.5) and passes after R1.
- ZERO-CLICK: runs in the suite.

R8. Small stack and spacing cleanup.
- Action: mono stack `Consolas, "Cascadia Mono", monospace` (drop the dead
  `ui-monospace`, CIU); splash stack in app order (`app/client/starting.css:8`);
  uppercase tracking 0.04em (one value); line height 1.5 on multi-line
  prose (zone guide, tips, help text); keep 1.4 for UI rows.
- Impact: L. Honest stacks, one tracking value, prose a little airier.
- Effort: S.
- Risk: Cascadia Mono is absent on some Windows 10 installs; Consolas
  comes first and ships with every Windows since Vista, so nothing changes
  visually.
- ToS check: none touched.
- Depends on: R3 (same files).
- Files likely touched: `web/app.css`, `app/client/starting.css`.
- Acceptance test: no `ui-monospace` in tracked CSS; one letter-spacing
  value for uppercase.
- ZERO-CLICK: automatic.

R9. Text-spacing survival check (WCAG 1.4.12) for the dashboard.
- Action: a CDP test injects the four 1.4.12 overrides and asserts no
  dashboard text is clipped (scrollWidth <= clientWidth on text boxes,
  no overlap of tiles); the overlay is a fixed-size HUD with ellipsis by
  design and is documented as out of scope.
- Impact: L-M (accessibility evidence; today unknown, PACK GAPS).
- Effort: S.
- Risk: may surface nowrap glance numbers in narrow tiles; fix by wrapping
  the tile, never by shrinking the number.
- ToS check: test only.
- Depends on: R3.
- Files likely touched: `app/test/cdp/` (new test).
- Acceptance test: the test runs green at 1024x700 and 1280x760.
- ZERO-CLICK: runs in the suite.

## Cut or merge

- Merge 13 / 13.6 / 14.4 px into meta 14 px; 13 px stays only for the
  footer disclaimer (R3).
- Merge zone 24 / 28.16 / 36 px into glance 28 px; level 32 / 33.28 / 44 px
  into hero 40 (32 in short windows); zone timer 20.8 / 25.6 px into title
  20 px (R3).
- Cut the overlay 15 px and 13 px steps (R2).
- Cut weight 700 from labels, kind tags and the selected tab; 700 stays
  for glance and hero numbers only (R3, R5).
- Cut the second letter-spacing value and the dead `ui-monospace` (R8).
- Cut design 0001's unimplemented 7-token table and its 0.93 scale note;
  replace with the R3 / R2 tables.

## Rejected

- Bundling a web font (Inter, Selawik or similar): Segoe UI is on every
  supported Windows; a bundled file needs a licence record, adds bytes,
  and the overlay CSP has no `font-src` (would need loosening). Segoe UI
  itself may not be shipped (MS-FAQ). Revisit only for a non-Windows
  target.
- A game-style display face (the game's own UI lettering): reads as GGG
  branding and imitates the game's look; ToS floor "no GGG trademarks,
  art or logos in the app name, icon or branding", plus licence unknown.
- A plate that adapts to the scene brightness by sampling the screen:
  needs a continuous screen read, which the floor forbids (screen only
  once per manual hotkey press, no watcher, no timer).
- Outline-only text with no plate (P-REC r6): 1.22-1.28 far-field over
  white, warm and fire, 1.00 over the checker; fails at any size.
- `-webkit-text-stroke` outlines (P-REC r4 / r5): thicken and blur 13-14 px
  glyphs and only work with a weaker plate, which costs more than they add.
- Flashing, pulsing or colour cycling to raise salience: design 0001
  section 10 and WCAG 2.3.1; also costs repaints against the FPS budget.
- Making overlay text 16 px everywhere: the 3-line card would not fit 258
  px for typical trade lines (the P-FONT card line, 225.6 px at 14 px,
  extrapolates to about 258 px at 16 px, against 238 px of room)
  and the window would need to grow; 14 px with R6 reaches the same
  physical size on 1440p / 4K.

## Open questions

- Segoe UI Variable on Windows 11 (MS-TYPE, SUV): naming `"Segoe UI
  Variable Text"` first would give Windows 11 players the optical-size
  small-text design. Its default figures and metrics were not measured
  (this machine is Windows 10). Needs a Windows 11 measurement of digit
  advances and line widths before any change; not blocking.
- Electron's transparent overlay window may antialias text in greyscale
  rather than ClearType; P-REC used headless Chrome on opaque backdrops.
  The R1 margin (>= 7 solid, about 7.2 rendered at the default) is meant to
  absorb that; confirm with one real overlay capture over a white desktop
  when the operator is not playing (no game involved).
- The slider relabel ("Background" in place of "Opacity") is a wording call
  for the target design (docs/plan/03-target-design.md); no adjudicator
  needed.

## Verification

Independent verifier, 2026-11-18.

Checked:
- Code (A): about 40 path:line citations opened in `web/app.css`,
  `app/overlay/overlay.css`, `app/overlay/index.html`,
  `app/shared/layout.js`, `app/main.js`, `app/client/starting.css`,
  `web/index.html`, `web/acts.js`, `web/runs.js`, `web/history.js`,
  `web/app.js`, `web/health.js`, `docs/design/0001-design-system.md` and
  the cited tests; all hold. Declaration counts re-counted (0.9rem x17,
  0.85rem x7, 0.8125rem x4, `overflow-wrap: anywhere` x30, `white-space:
  nowrap` x8).
- Evidence (A): PACK `run/summary_lines.txt` re-aggregated (135 dashboard
  captures: Play 12-16 styles / 6-7 sizes, Build 8-12 / 3-4, Items 9-10 /
  3-4, Run 9-10 / 3-4, Settings 10 / 3, minimum ratio 5.31, 0 truncated;
  light run minimum 4.90); PACK `run/c/overlay.json` method string and
  its 3.81 confirmed; `px_probe.py` re-run on PACK `run/c` reproduces
  4.88 / 5.06 / 5.69 / 6.03; P-REC measurement JSON re-read for every
  r0 / r1 / r3 / r4 / r5 / r6 / r8 figure quoted; P-FONT JSON re-read for
  digit advances, widths, metrics and line fits.
- Arithmetic: every R1 solid-colour ratio (alpha 0.86 and 0.80 over four
  backdrops) and the pack's 3.81 model re-computed independently; every
  x-height / arcmin figure in F4, R3 and R6 re-derived from panel
  geometry (24 inch 1080p 0.277 mm/px, 27 inch 1440p 0.234 mm/px).
- Web (B): 9 sources re-fetched (WCAG-CM, WCAG-CE, WCAG-TS, MS-TYPE,
  MS-FAQ, CIU, SUV, LB, DOB); all claims used hold except as corrected.
- ToS floor (C): R1-R9 are CSS, window-size or test-tooling changes; none
  reads the screen, the clipboard, the game or Client.txt, sends input, or
  uses GGG branding. The scene-adaptive plate (screen watcher) and a
  game-style face (GGG look) stay under Rejected.
- Settled decisions (D): no CLAUDE.md settled entry covers overlay
  opacity, type sizes or fonts; R1 / R2 / R6 stay inside decision 0002
  (separate click-through overlay, budgets) and do not touch decision
  0041 (overlay inside the desktop client). R1 does reverse design 0001
  section 5.2's opacity-floor rule and test pins, which are design-doc
  rules, not settled decisions; the file says so (R1 Depends on).
- Completeness (E): every brief point is covered: stacks, sizes, weights,
  line height, tracking with counts; bundling and licence; numerals;
  truncation; 60-90 cm and 1080p / 1440p / 4K with scaling; per-role
  worst case over white / warm / grey (added by the verifier to F1);
  recipe with numbers; scale and tokens; cited guidance.
- Recommendations (F): all nine carry the required fields.

Corrected (8):
- WCAG-CE, MS-FAQ, CIU and LB were unread or read via summaries; now
  fetched directly and labelled so (WCAG-CE no longer UNVERIFIED).
- SUV overclaimed: the article says only that `system-ui` does not use
  Segoe UI Variable; the "legacy Segoe UI on Windows 11" reading is now
  marked UNVERIFIED in Sources and Summary.
- DOB polarity cost 39 to about 40 percent (table means 119.4 vs 85.3 ms;
  the paper's text says 38.6).
- 0.8125rem count: x4 in total including the two media-query
  declarations, not 4 plus 2.
- r6 outline-only range: 1.22-1.28 over white / warm / fire (1.00 checker,
  1.37 split), not 1.00-1.37 over white / warm / fire (R1, Rejected).
- R6 acceptance test restated in DIP heights (the test helper passes DIP
  bounds, so "3840x2160 / 1.5" was not a valid input), the 4K at 125
  percent case added (1.2 to 1.45), test line range `:98-106`.
- R1 impact split into solid-colour (>= 7.30) and rendered estimate
  (7.1-7.3); mechanism constraint added (page CSS via insertCSS, never
  setOpacity; high-contrast plate stays opaque); two more test files that
  pin opacity named.
- MS-TYPE nuance on ellipsis vs clip and the 50-60 letters line-length
  guidance added.

UNVERIFIED (remaining):
- What `system-ui` resolves to on Windows 11, and Segoe UI Variable's
  default figures and metrics (no Windows 11 machine).
- All P-REC numbers come from headless Chrome on opaque backdrops, not
  the real Electron transparent window (Open questions).
- MDN-FF not re-fetched (no decision rests on it).
