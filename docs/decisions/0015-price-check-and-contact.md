# 0015 - Price check per press and the User-Agent contact (PRICE-1, UA-CONTACT)

Date: 2026-11-17. Trigger: ROADMAP rows PRICE-1 (server side) and
UA-CONTACT, worked by the build lane (round 4). No adjudicator was needed:
every fork below follows from CLAUDE.md, decisions 0003 / 0013 / 0014 and
research 0004 / 0011.

## Decision

1. Contact (UA-CONTACT). An optional `"contact"` key read ONLY from the
   gitignored `config/local.json` (a test core: its runtime `local.json`);
   `config/local.example.json` documents it with an empty value and no
   example address. `webfetch.user_agent(purpose, contact)` appends
   `(contact: <value>)`; the value must be printable ASCII without
   parentheses or backslash, at most 120 characters, else it counts as
   unset (no header injection, no broken comment). The value is never
   echoed by the API (`GET /api/web-data` says only `contact_set`).
2. Gate. poe.ninja (`ninja.RatesClient`), trade2 (`trade.TradeClient`,
   checked at submit and again right before sending) and GGG sources of
   the build-time snapshot (`snapshot.needs_contact`: the skill tree
   source, pathofexile.com, grindinggear paths) send nothing without a
   contact, even with web_data on. The reason is exposed as `"blocked":
   "contact not set"` (or "web data off") in `GET /api/rates`, `GET
   /api/web-data`, `GET /api/price` and the state's `price` field. pobb.in
   and pastebin share links keep working without one (research 0011 lists
   the contact ask only for GGG and poe.ninja) and do not send it.
   Alternatives: send name / version only (decision 0013 open item; rejected:
   both GGG and poe.ninja docs ask for a contact); a contact in a tracked
   file (rejected: CLAUDE.md hygiene, leak sweep).
3. Price check (PRICE-1, `server/al/price.py`). The app's one clipboard read
   per press of the item hotkey already posts the text to POST /api/eval
   (decision 0014); the server queues at most ONE price check for that same
   POST - no second read, no second app call. Flow through the shared
   TradeClient / RateLimiter: the trade2 stat-id table (`/data/stats`,
   cached in `<sidecar>\Cache\trade\trade_data.json`, at most one attempt a
   day, persisted, a failed attempt counts), the league (config "league",
   else the first softcore poe2 league of `/data/leagues`, daily, else
   Standard), `build_query`, one search, one fetch of the first 10 ids, a
   summary (main currency, min / median of the cheapest 5, listing count,
   search total). Same text within 30 s reuses the last result; a newer
   press supersedes an older check that has not searched yet, so a press
   never causes more than one search. "waiting N s" comes live from the
   limiter. The result is a neutral data field `price` in the state (no new
   event text) and `GET /api/price` (token, Host, Origin as every endpoint;
   a GET never starts a check). The card is PRICE-1-UI.
   Alternatives: a separate price hotkey and clipboard read (rejected:
   decision 0003 / ruling F1, one read per press); the league from
   poe.ninja's cache (rejected: its ids are not proven to equal trade2's).

## Open (UNVERIFIED)

- trade2 `/data/stats`, `/data/leagues` and `/fetch` response shapes and the
  league list order (research 0004); parsers are defensive.
  Amendment 2026-11-18 (LOOP-DECISION-TIDY): moot since decision 0017;
  the app calls no trade2 endpoint, so none of these shapes is read.

## Reverses if

GGG or poe.ninja drop the contact ask, a share host starts asking for one,
or the operator rules price checks need their own hotkey.

## Amendment 2026-11-17 (PRICE-1-WIRE): GET /api/price removed

DECISION: the price check reaches the UI only through the state field
`price` (the decision 0016 Fork 1 card, pushed over SSE); the route
`GET /api/price` is deleted. The checker keeps its own result doc (this
decision's item 3 fields, incl. queued / skipped and the reason) in memory
as `PriceChecker.doc` / `latest()`, and `price.card_of()` turns each change
into the card. One press stamps one time: `Core.eval_press` takes the
server clock once and passes it to the item check (`set_eval(at=)`) and to
`PriceChecker.request(text, at=)`; the first publish of a press calls
`set_price(card, at=<press>)`, later updates `keep_time=True` with the same
`at`, and a reused result (same text within 30 s) is re-published with the
new press time. The "blocked" reason stays visible in `GET /api/web-data`,
`GET /api/rates` and the card's `off` status.
ALTERNATIVES: keep GET /api/price as a debug / dashboard read (rejected:
no caller in web/ or app/, the overlay is SSE-only and cannot use it, and
every extra token-gated route is attack surface and test surface for no
user); keep it but return the card (rejected: duplicates /api/state).
WHY: decision 0016 ruled no endpoint of the price lane's own; one path to
the UI keeps the overlay and dashboard in step and the token / Origin
surface unchanged.
REVERSES IF: a caller needs the live limiter wait or the internal doc
outside the state (then a GET returning `latest()` returns with the same
guards), or the overlay is allowed to fetch.

## Amended by 0017

Amended by 0017 (2026-11-17): item 3 (trade2 search queue): removed; the
press builds a trade-search URL offline. See docs/decisions/0017-trade-no-
app-calls-and-floor-wording.md.

## Amendment 2026-11-20

DATA-CONTACT-FIELD (F-018): the contact can be typed in the dashboard's
"Prices and web data" card. POST /api/web-data takes "contact" (text,
cleaned by webfetch.clean_contact; '' removes it; an unusable value is a
400 with a plain sentence and nothing written) and Core.set_contact writes
the same gitignored config/local.json key, still its only store. The value
is write-only: every read-back (GET /api/web-data, GET /api/rates, the
Checks report, the settings export) says only contact_set, and the Checks
fix names the card, never a file path. A set contact starts a due price
refresh at once. Reverses if: a second store for the contact is wanted, or
a read-back must show the value.

## Amendment 2026-11-23

DATA-CONTACT-DEFAULT (F-018, ruling Q-03), item 1 (contact): once the
repository address is in the tree (config/public_repo.json, read only
through updates.load_repo, the one address source; never a literal), the
default contact is the project's issues page (webfetch.default_contact,
`https://github.com/<repo>/issues`, cleaned like a typed value). Requests
send webfetch.effective_contact: the typed "contact" of config/local.json
when usable, else that default, else none ("contact not set" as before).
Core.effective_contact feeds the poe.ninja client, the blocked reason and
the Checks facts; snapshot.py main() uses the same fallback. Core.contact
and the /api/web-data contact_set stay the typed contact only, so the
dashboard field is an optional per-install override. Only the real core
reads the address file; a test or demo core uses the update_repo it is
handed ('' when none: no default). Release builds still make no poe.ninja
request (decision 0072).
ALTERNATIVES: (B) Core.contact itself falls back, so contact_set reads true
and the field hides (rejected: the override could then only be typed by
hand in local.json); (C) keep the typed contact mandatory (rejected: every
player must type something before prices work).
WHY: poe.ninja and GGG ask for a way to reach the tool's maker; the public
issues page is that, and no player has to type anything.
REVERSES IF: poe.ninja or GGG asks for a personal contact instead of a
project page, the repository is withdrawn, or the operator rules the
default unwanted.
