# 0088 - Session sales tally on the summary card (UTIL-SALES-TALLY)

Status: accepted 2026-11-27 (ROADMAP row UTIL-SALES-TALLY, research 0064
gap G8). No adjudicator was needed: the row fixed the rule; this records it.

## Decision

1. A sale is a `trade_accepted` event ("Trade accepted.") that closed an
   open trade card by the decision 0019 pairing (the named counterparty's
   card, else the oldest). An accepted trade with no open card (for
   example the player buying, or a card already expired or dismissed) and
   every `trade_cancelled` are not sales.
2. The open play stretch (server/al/summary.py `Tracker`,
   UTIL-SESSION-SUMMARY) keeps a `Sales` tally in memory: the sale count,
   the listed price of each closed card added up per currency (the
   whisper template's `price_amount` and `price_currency`; for an exchange
   whisper, the buyer's offered currency), and the count of sales with no
   usable price. At most 4 currencies are summed per stretch; a currency
   word must be letters, digits, spaces, ' or - and at most 32 characters;
   an amount must be a finite number above 0. Anything else counts as a
   sale but is not in the sum.
3. When the stretch closes, the card gets `sales`, `sales_sums` ([currency,
   amount] pairs), `sales_unsummed` and one line, made only by
   server/al/text/events.py `sales_line` (copy sheet
   docs/design/copy/events.md): `Sales: 3, about 12 exalted and 2 divine
   (an estimate).` No sale, no line. The card is saved exactly as before
   (session_summaries.json, MAX_SAVED = 20 cards, decision 0036 bounds);
   it holds counts and sums only, never an item, a sender, a stash tab or
   whisper text.
4. No request, no new file, no new route, tick or Checks row; the web card
   (web/summary.js) shows the line like every other summary sentence.

## Alternatives

- (b) Count every "Trade accepted." line. Rejected: the player buying also
  ends in "Trade accepted.", so purchases would count as sales.
- (c) Keep a per-trade log (item, buyer, price). Rejected: research 0064
  G8's floor is counts and sums only; names and chat text stay out of
  stored records (decision 0036).
- (d) Convert the sums to one currency with poe.ninja rates. Rejected for
  now: the card would mix a guess on a guess, and release builds make no
  poe.ninja request (decision 0072).

## Why

The whisper already carries the listed price and decision 0019 already
pairs a finished trade with one card, so a tally needs no new reading. The
oldest-card guess can pair the wrong card, so the sum is labelled an
estimate.

## Reverses if

A PoE2 log line names the trade counterparty or the traded item (then pair
exactly and drop the estimate label), players report the tally counting
purchases or missing sales in normal play, decision 0019 reverses, or the
operator rules the sales line unwanted.

## Tests

tests/test_sales_tally.py (fixture log of three sales in two currencies,
cancelled and card-less accepts, unpriced and exchange cards, currency cap
and bad words, a new stretch, no item or name in the saved card, the exact
words).
