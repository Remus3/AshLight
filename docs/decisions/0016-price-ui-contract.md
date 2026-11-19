# 0016 - Price check result contract, overlay card slot, rates panel (PRICE-1-UI, DATA-NINJA-UI)

Date: 2026-11-17. Trigger: ROADMAP rows DATA-NINJA-UI and PRICE-1-UI,
built while another lane finishes the PRICE-1 server part. No contract for
the PRICE-1 result existed in the repo, so three forks went to an
adjudicator agent the same day (headless, operator away); rulings below.

## Decision

### Fork 1 - the PRICE-1 result contract

RULING: the core publishes the last price check in the state snapshot as
`price` (null when none). The PRICE-1 lane calls
`SessionState.set_price(card, at=<press time>, keep_time=False)` and adds
no endpoint of its own. `card` fields:

- `status`: closed enum `searching` | `waiting` | `done` | `off` | `error`;
- `wait_s`: the limiter wait in seconds while `waiting`, else null;
- `item`: {`name`, `base`, `rarity`};
- `league`: the searched league;
- `count`: listings found in total;
- `listings`: [{`amount`, `currency`}], cheapest first, at most 10 (the
  core trims to 10);
- `error`: a machine string: `not an item` | `no base type` | `no league` |
  free text (never shown; free text reads "Price check failed"); with
  status `off` it is
  null (web data off) or `contact not set` (PRICE-1-COPY amendment below).

The core adds `id`, `at` (press time, server clock s; the same press stamps
both the item check and the price check), `expires_at` (`at` +
`PRICE_CARD_S` = 20, or 20 s after `updated_at` when later) and `text` from `state.py price_card_text` (`head`,
`item`, `line`, `detail` for the overlay; `sentence`, `rows` for the
dashboard; exact-output tests in `tests/test_price_text.py`). A status
update of the same check (searching -> done) passes `keep_time=True`.
Currency conversion into poe.ninja's primary unit is done by the dashboard
from GET /api/rates (`web/prices.js`), never invented when a rate is
missing.

ALTERNATIVES: (B) a polled GET /api/price; (C) wait for the lane.
WHY: the overlay is SSE-only and `Origin: null` is allowed only for
`/events`, `/api/state`, `/api/health`, so B widens that surface and adds
polling; it mirrors the TC-EVAL-UI id / at / expires pattern; C blocks
with the operator away; words stay in `state.py`. Floor: one press = one
clipboard read, shared by item check and price check; the price lane adds
no second read and no input to the game.
REVERSES IF: the lane ships a different, already merged contract (then the
UI adapts and this entry is amended), or the overlay is allowed to fetch.

AMENDMENT 2026-11-17 (PRICE-1-WIRE): wired as ruled. DECISION: the PRICE-1
server keeps this contract unchanged; `price.card_of()` maps its decision
0015 doc to the card (queued / searching -> searching, waiting -> waiting
with wait_s, done -> done with count = search total (or the listing count)
and listings in fetch order, cheapest first because the search sorts by
price ascending, off -> off, skipped -> error "not an item", a missing
league -> error "no league", other failures -> error free text) and calls
`set_price(card, at=<press>)`, then `keep_time=True` with the same `at`.
The press time is taken once in `Core.eval_press` and also stamps the item
check, so `|price.at - eval.at|` is 0 for one press. GET /api/price, which
PRICE-1 had added, is removed (amendment in decision 0015).
ALTERNATIVES: keep GET /api/price beside the state field; change the card
to the 0015 doc. WHY: no caller, SSE-only overlay, the UI was already
built and tested on this card. REVERSES IF: as decision 0015's amendment.

STATUS: wired 2026-11-17 (PRICE-1-WIRE, amendment above). Was stub-built:
in that branch nothing called `set_price`; the UI
was built and checked against fixture cards of this exact shape (tests and
a stand-in server). The hotkey text on the dashboard names the item check
key (Alt+Shift+E, decision 0014 F1); if PRICE-1 lands on another key,
`web/prices.js priceEmpty` changes with it.

### Fork 2 - the overlay card slot

RULING: one card, chosen by the core (`state.py overlay_card`, snapshot
field `card` = {`kind`, `head`, `line2`, `line3`, `verdict`, `expires_at`}
or null); the overlay only clips and shows it (`format.js cardText`,
`render_gate.js`). Rules: item check and price check both fresh and from
one press (|price.at - eval.at| < 2 s): a merged card - item check head,
price line ("Searching prices...", "Prices in about 8 s", "5 listed, ~12
exalted"), item check top stat; a price error or `off` leaves the item
check card unchanged; a "no build loaded" item check gives the price-only
card ("Price: <item>", price line, lowest / detail line). Different
presses: the newest. The price card leaves 20 s after the press or 20 s
after its last update, whichever is later (design review F1: a result that
waited on the trade site's limit still shows for the full time; the core
stores `updated_at`, and `at` stays the press time for grouping). An older
core without `card` keeps the item check path.
ALTERNATIVES: (b) newest replaces the item check card; (c) price on the
dashboard only.
WHY: (b) hides the verdict after a couple of seconds; (c) wastes the main
mid-play use; (a) keeps design 0001 section 10 (2 HUD lines + ONE 3-line
card), no new slot, no window change. The item name is dropped in the
merged card because the player just hovered it.
REVERSES IF: playtest finds the merged card too dense or the 2 s window
misgroups results (then (b) with a hold of at least 6 s on the verdict),
or section 10 changes.

### Fork 3 - rates panel and the web-data opt-in

RULING: one dashboard card, "Prices and web data": the opt-in is a
checkbox (never pre-ticked) that saves on change through POST
/api/web-data, reverts and says "Not saved. Try again." on failure, and
states exactly what it fetches (poe.ninja rates about hourly, a pasted
build link once, trade prices when you check an item; no account,
password or cookie). Currency values show the top 8 by traded volume in
the primary unit with a kit-state pill (updated / old values / not
updating - web data is off / getting / can't reach), league, the "Prices:
poe.ninja" credit and the full attribution; cached values stay visible
when off, labelled. The panel polls the local GET /api/rates every 5
minutes while the page is visible (the core still asks poe.ninja at most
hourly); no refresh button. Dashboard trade rows get "about N <primary>"
with the rate age as a tooltip, omitted when no rate fits. The item check
card gains a Price section (state word, the core's sentence, each listing
with its conversion). The overlay trade card is unchanged.
ALTERNATIVES: separate rates and settings cards; a confirm dialog before
enabling; conversions on the overlay.
WHY: the consent words sit next to the control they govern; save on
change matches the other settings (design 0001 N1); labelled stale values
are useful and honest; the overlay is at its glance limit.
REVERSES IF: the operator wants an explicit confirm step for web data, or
the poe.ninja attribution changes.

AMENDMENT 2026-11-17 (PRICE-1-COPY; design review of PRICE-1-WIRE, S3 x3).
DECISION: `price.card_of()` matches exact source strings only: skipped
with reason `not an item` (trade.build_query) -> error "not an item",
`item has no base type` -> error "no base type" ("Can't price this item /
Try a different item", retry badge; design review F1), any other skip
reason -> error free text; the
exact trade.search_url error `league required` -> error "no league", any
other error text -> free text; off -> off with `error` = `contact not set`
when that is the reason, else null. `state.py PRICE_TEXT["contact not
set"]` says to add the contact in config/local.json; the dashboard badge
reads "no contact" instead of "web data off".
ALTERNATIVES: (B) a new `reason` card field; (C) keep substring matching.
WHY: B widens the closed card contract when `error` already carries a
machine string; C gave wrong advice (a trade 400 mentioning a league read
"League unknown", a parsed item read "Not an item", a missing contact read
"Web data is off").
REVERSES IF: the card contract gains a reason field, or the source strings
in trade.py / webfetch.py change (the constants in price.py follow them).

## Amended by 0017

Amended by 0017 (2026-11-17): Fork 1: the card gains status "link" with a
`url`; the dashboard shows a click-through link, the overlay a short
notice. See docs/decisions/0017-trade-no-app-calls-and-floor-wording.md.

AMENDMENT 2026-11-17 (PRICE-TRADE-LINK, built). DECISION: Fork 1's card is
now `status` link | error (searching / waiting / done / off stay in the
enum and keep their words in `state.py` for older readers, but the core no
longer produces them), plus a new field `url`: the trade2 search URL
`https://www.pathofexile.com/trade2/search/poe2/<league>?q=<url-encoded
JSON>` while `link`, else null (research 0016). `price.card_of()` emits
`link` only when `trade.is_search_link(url)` holds; `wait_s`, `count` stay
null and `listings` empty. `league` is config/local.json "league", else
"Standard"; nothing is fetched. The press builds the link offline, so the
web-data opt-in and the contact no longer gate the price card (`off` and
`contact not set` are not produced); `error` is `not an item` | `no base
type` | free text. Words (`state.py PRICE_TEXT["link"]`): overlay line
"Trade link ready", empty detail; the merged card carries that line; the
dashboard sentence names the league, and `web/prices.js` shows the URL as
a link (target _blank, rel noopener noreferrer, shown only when it matches
the trade2 search shape) with the badge "link ready". The core never opens
the URL. The dashboard's web-data copy no longer lists trade prices.
ALTERNATIVES: a new card kind beside `price`; keep `done` with the link in
it. WHY: one card slot and one contract field; `done` implied prices the
app no longer has. REVERSES IF: decision 0017 reverses (then `url` stays
null and the enum is unchanged).

AMENDMENT 2026-11-18 (DATA-PRICE-CARD-TEXT; findings F-036, F-031, F-018).
DECISION: the card's `ninja` part gains two keys, `checked_at` (when the
cached price was read from poe.ninja) and `league_changed_at` (when the
priced league last changed; decision 0026, DATA-LEAGUE-IDENTITY), both
epoch seconds or null, passed by `price.ninja_of` (`NINJA_KEYS`). The
words in `state.py` read them against the press time `at`: a price more
than 2 h old says "Price from N h ago" on the detail line ("Rough price
from N h ago" for few listings) and "This price is from N h ago." in the
sentence; more than 24 h old, the card is the link card alone and the
sentence says the poe.ninja price is over a day old; for 24 h after a
league change the overlay price line reads "About <price> in <league>",
or, past the 34-character line, the detail line reads "League:
<league>"; a non-ASCII league name stays in the sentence only. A stamp
after the press (a clock step) or a missing one ages nothing. The `off`
and `contact not set` words name poe.ninja and the Prices and web data
card instead of config/local.json (the card's contact field lands with
DATA-CONTACT-FIELD; until then decision 0017's amendment means neither
state is produced, so no player meets the pointer early). Exact tests:
tests/test_price_card_age.py, tests/test_price_text.py.
ALTERNATIVES: (B) the age as a top-level card field; (C) hide every price
over 2 h old; (D) a league tag on every price line.
WHY: the age belongs to the cached price, so it rides with it; a 3 h old
price is still useful when it says its age, a day-old one misleads after
a reset; the league only needs naming while a change is fresh, and a
permanent tag costs the glance line.
REVERSES IF: poe.ninja's refresh cadence makes a 2 h price normal, the
core gains a refresh that keeps the cache under 2 h in play, or decision
0026 drops league_changed_at.
DPC-1 (design review of DATA-PRICE-CARD-TEXT, adjudicator ruling
2026-11-18). DECISION: keep the spec copy for `off` and `contact not
set`; DPC-1 is downgraded from S2 to S3 and deferred to
DATA-CONTACT-FIELD (wave 17).
ALTERNATIVES: a "settings file" pointer; card-neutral wording.
WHY: the states are unreachable until the contact field lands (price.py
only emits status "link" since decision 0017), and the spec bars naming
a file.
REVERSES IF: DATA-CONTACT-FIELD is dropped or moved out of the Prices and
web data card, or any code path emits status "off" / "contact not set"
before wave 17 (then DPC-1 reopens as S2 and the copy becomes "Contact
not set - turn on Use web data in Prices and web data").
