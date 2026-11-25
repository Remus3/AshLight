# Play fit figures (measured)

Date: 2026-11-18. Package PLAY-TD-01B-FIT-HARNESS (MERGE-SEAMS F1).
Status: measured on the two-column Play that the cockpit replaced; folded
into design 0001 section 4 on 2026-11-22 (PLAY-TD-23-RECORDS). Since the
cockpit regions landed, the track table is held by the fit harness itself
(tests/test_play_fit.py checks G1 and G2 in every state and size class),
so the open row below is closed there, not re-measured here.

Source: `python tests/test_play_fit.py --figures` (the fit harness of
tests/test_play_fit.py and app/test/cdp/play_fit.mjs). Headless Chrome on
Windows 10, device scale factor 1, dark scheme emulated, default text
settings (system-ui resolves to Segoe UI), the dashboard served by a test
core pinned to a temp Client.txt on a free port in 8961-8979. States are
the recipes of tests/play_states.py. One sweep of 12 states x 7 sizes took
11 to 12 s.

"Over" is how far Play runs past its box: the page overflow or, today,
the worst element under the Play panel (the two Play columns scroll inside
themselves, so the page itself reads 0). A column figure reads "content
in box" (scrollHeight in clientHeight, px).

## Today's Play: zone guide, build alert, 2 trades (state c2)

| Size | Over | Left column | Right column | Words | Elements | Controls |
|---|---|---|---|---|---|---|
| 1280x760 | 307 | 935 in 628 | 628 in 628 | 237 | 82 | 6 |
| 1920x950 | 47 | 883 in 836 | 836 in 836 | 237 | 82 | 6 |
| 1024x700 | 499 | 1067 in 568 | 568 in 568 | 237 | 82 | 6 |

## The same with the item card up (state c, plan 03 3.2 "state c")

| Size | Over | Left column | Right column | Words | Elements | Controls | Text styles |
|---|---|---|---|---|---|---|---|
| 1280x760 | 406 | 1034 in 628 | 975 in 628 | 393 | 133 | 8 | 10 |
| 1920x950 | 124 | 960 in 836 | 953 in 836 | 393 | 133 | 8 | 10 |
| 1024x700 | 598 | 1166 in 568 | 975 in 568 | 393 | 133 | 8 | 10 |

The 8 controls of state c count the two scrolling column groups
(`.play-main`, `.play-side`, tabindex 0), the item card fold (`summary`),
two Dismiss buttons, Dismiss all and the two trade links.

## Other states at 1280x760 / 1920x950 (over, px)

- a first run: 39 / 52 (157 words)
- b campaign zone: 47 / 5 (196 words)
- d game idle: 567 / 311 (267 words)
- e error: 3 / 5 (68 words)
- f typical filled: 347 / 117 (363 words)
- c5 trade burst: 568 / 248 (429 words, 11 controls)
- long strings: 720 / 320 (439 words, 148 elements, 11 controls)
- map: 110 / 5 (200 words)

## Plan 03 figures confirmed or corrected

| Figure (plan 03) | Plan | Measured | Verdict |
|---|---|---|---|
| State c at 1280x760, left / right over (3.2) | 380 / 321 | 406 / 347 | corrected: the columns are 628 px, not 654, because the footer wraps to 65 px |
| State c at 1920x950, left / right over (3.2) | 124 / 117 | 124 / 117 | confirmed |
| Idle over at 1280x760 / 1920x950 (3.2) | 541 / 311 | 567 / 311 (state d; the left column, the right one fits) | corrected at 1280x760 (the same 26 px of footer), confirmed at 1920x950 |
| Chrome at s = 1 today [M] (3.2) | 106 | 131 at 1280x760 (bar 50, main padding 8 + 8, footer 65); 113 at 1920x950 (bar 50, padding 12 + 12, footer 39) | corrected: the footer wraps to two lines under 1500 px |
| Words on Play today, state c (G5) | 397 | 393 | confirmed within 1 percent |
| Visible elements on Play today (G5) | 133 | 133 | confirmed |
| Text styles on Play today (6) | up to 16 | 10 (size, weight) pairs in state c; the ratios 0.9, 1.3, 1.76 and 2.08 rem are not on the token scale | corrected |
| Track table, full and compact (3.2, 3.8, G2) | [D] | not measurable yet: no #play-* region exists | open: the harness placeholder mode measures it once PLAY-TD-09B-SKELETON lands |

## Character budgets (plan 03 3.4), measured at s = 1

Each composed row of the long-string fixture (tests/play_states.py
LONG_ROWS, real words at exactly the cap), measured alone at its size and
weight, then with the WCAG 1.4.12 override (letter-spacing 0.12em,
word-spacing 0.16em).

| Row | Cap | Size / weight | Width | With override | Narrowest inner width | Verdict |
|---|---|---|---|---|---|---|
| C title | 38 | 20 / 600 | 367.3 | 471.3 | 546 | fits, 75 px spare |
| C body row | 52 | 16 / 400 | 388.1 | 503.3 | 546 | fits, 43 px spare |
| N body row | 52 | 16 / 400 | 383.4 | 498.6 | 554 | fits, 55 px spare |
| T event sentence | 38 | 16 / 400 | 279.7 | 362.9 | 397 | fits, 34 px spare |
| B row 2 | 36 | 16 / 400 | 261.0 | 340.4 | 390 | fits, 50 px spare |
| I sentence, per row | 36 | 16 / 400 | 275.5 | 354.8 | 382 | fits, 27 px spare |
| U row | 42 | 14 / 400 | 267.1 | 351.1 | 398 | fits, 47 px spare |
| N head word | 12 | 20 / 600 | 113.4 | 142.2 | - | - |
| N head title | 20 | 16 / 600 | 155.7 | 199.2 | - | - |
| N head action label | 12 | 16 / 400 | 94.0 | 117.1 | - | - |
| N head in all (word + title + label + 16 px of gaps) | - | mixed | 379.1 | 474.5 | 554 | fits before button padding, 79 px spare |

The [C] check of plan 03 3.4 (52 characters at 16 px: 349 px, 477 px with
the override) measured 388 px and 503 px with real words here: real text
runs about 0.47em a character, still under the 0.5em budget, so every cap
of the table holds with 27 px or more to spare. The caps stand.

## G5 totals on the cockpit (PLAY-FIT-G5-TOTALS, 2026-11-24)

Words and visible elements on Play at 1280x760 (the full class, the
heaviest size; the compact class hides the notice rows), before and
after the package, from `python tests/test_play_fit.py --figures` (13
states x 7 sizes in about 13 s). The element maximum is 100 plus 6 per
open trade row; the word maxima are 250, 110 in state a and 150 in
state b (design 0001 section 4, G5 totals ruling; b read 153 after this
package and is back to 150 since PLAY-FIT-B-WORDS, below).

| State | Open trades | Words before | Words after | Elements before | Elements after | Element max |
|---|---|---|---|---|---|---|
| a | 0 | 127 | 104 | 93 | 73 | 100 |
| a2 | 0 | 115 | 95 | 80 | 64 | 100 |
| b | 0 | 169 | 153 | 98 | 79 | 100 |
| c | 2 | 217 | 214 | 143 | 110 | 112 |
| c2 | 2 | 198 | 185 | 117 | 92 | 112 |
| d | 2 | 169 | 156 | 115 | 90 | 112 |
| e | 0 | 139 | 129 | 108 | 83 | 100 |
| f | 1 | 155 | 150 | 128 | 98 | 106 |
| g | 1 | 156 | 151 | 128 | 98 | 106 |
| map | 2 | 147 | 131 | 111 | 86 | 112 |
| long | 5 | 213 | 214 | 155 | 116 | 130 |
| c5 | 5 | 213 | 214 | 155 | 116 | 130 |
| rows10 | 0 | 118 | 102 | 87 | 69 | 100 |

State b now reads 150; see "State b words" below. The element maximum
from 2026-11-24 is 94 plus 6 per open trade row, counting visible
elements only; see "G5 screen-reader count" below.

The feed spends the words its cut tags freed on longer item names (its
own 50-word ladder), so long and c5 read one word more than before.

## G5 screen-reader count (PLAY-FIT-SR-COUNT, 2026-11-24)

The harness now counts visible elements only: an element that it or an
ancestor clips to nothing (clip rect(0px, 0px, 0px, 0px) or clip-path
inset(50%)) is screen-reader text and is reported apart as "hidden"
(design 0001 section 4, G5 screen-reader count ruling). The element
maximum is 94 plus 6 per open trade row. Words and G6 controls are
counted as before. Figures at 1280x760 from `python tests/test_play_fit.py
--figures` (13 states x 7 sizes); "old count" is visible plus hidden, the
count the G5 totals table above shows. Every state reads at most
these figures at the other sizes.

| State | Open trades | Words | Visible | Hidden | Old count | Element max |
|---|---|---|---|---|---|---|
| a | 0 | 104 | 65 | 8 | 73 | 94 |
| a2 | 0 | 95 | 57 | 7 | 64 | 94 |
| b | 0 | 150 | 73 | 6 | 79 | 94 |
| c | 2 | 211 | 104 | 6 | 110 | 106 |
| c2 | 2 | 182 | 86 | 6 | 92 | 106 |
| d | 2 | 153 | 84 | 6 | 90 | 106 |
| e | 0 | 129 | 76 | 7 | 83 | 94 |
| f | 1 | 150 | 92 | 6 | 98 | 100 |
| g | 1 | 151 | 92 | 6 | 98 | 100 |
| map | 2 | 131 | 80 | 6 | 86 | 106 |
| long | 5 | 211 | 110 | 6 | 116 | 124 |
| c5 | 5 | 211 | 110 | 6 | 116 | 124 |
| rows10 | 0 | 102 | 63 | 6 | 69 | 94 |

The 6 hidden elements in every state are the 6 screen-reader region
headings; a, a2 and e (first run, idle strip, error) hold 1 or 2 more
screen-reader texts. The tightest state
is c, 104 of 106.

## State b words (PLAY-FIT-B-WORDS, 2026-11-24)

State b measured 153 words against the G5 maximum of 150; the 3 words
over were server text. The campaign-death notice tip
(server/al/hints.py) went from 16 words to 13 and now names the card by
its title: before "Deaths in the campaign cost no experience. The Death
recap card shows where each one happened.", after "Campaign deaths cost
no experience. The Deaths card shows where each one happened." Region N
reads 17 words (was 20), so state b reads 150 at 1280x760, and
WORDS_STATE_MAX["b"] in tests/test_play_fit.py is 150 again. The build
line (server/al/playview.py BUILD_FIX, "Copy a PoB code, press the item
key.") is unchanged. States c, c2, d, c5 and long show the same tip, so
each reads 3 words fewer (c 211, c2 182, d 153, c5 and long 211).
