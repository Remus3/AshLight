# 0015 - Price check result contract, overlay card slot, rates panel (PRICE-1-UI, DATA-NINJA-UI)

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
- `error`: a machine string: `not an item` | `no league` | free text (never
  shown; free text reads "Price check failed").

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

STATUS: stub-built. In this branch nothing calls `set_price` yet; the UI
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
