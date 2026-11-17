# 0019 - A finished trade closes one open trade card (OVL-TRADE-CANCEL)

Date: 2026-11-17. Trigger: ROADMAP row OVL-TRADE-CANCEL (design review
2026-11-16) and UX-REVIEW finding F2 (2026-11-17): ": Trade accepted." and
": Trade cancelled." were parsed (server/al/parser.py) but left the open
trade card up for its full 10 minutes (DS-TRADE-EXPIRE). No adjudicator
was needed: the task brief fixed the rule; this records it.

## Decision

1. On `trade_accepted` or `trade_cancelled` the core drops ONE open trade
   card (server/al/state.py `SessionState._close_trade`): the card from the
   counterparty when the event carries a `name`, else the OLDEST open card.
   Today neither PoE2 line carries a name (both are bare system lines), so
   the oldest card goes; the name path is ready for a future line that
   names the other player. An unknown name falls back to the oldest.
2. Accepted and cancelled are handled the same: the trade window closed, so
   the request it answered is no longer waiting. A buyer who wants to retry
   whispers again and gets a new card.
3. Nothing else changes: the 10 minute expiry, Dismiss and Dismiss all stay;
   "Trade accepted" stays in the Recent list; nothing is sent to the game.

## Alternatives

- (b) Mark the card ("cancelled" / "done") instead of dropping it. Rejected:
  the overlay has one card slot (design 0001 section 10); a finished trade
  holding it hides the next live request.
- (c) Match the counterparty by the last player who joined the area
  (`player_joined_area`). Rejected for now: in a hideout with several
  visitors it guesses wrong, and a wrong drop is worse than the oldest
  (the usual first-come order of trades).
- (d) Drop every open card. Rejected: one trade window answers one request.
- (e) Keep the cards and rely on expiry. Rejected: F2 - a finished trade
  stays up to 10 minutes and hides newer requests.

## Why

Trades are usually served first come, first served, so the oldest open
request is the best guess for the window that just closed, and it needs no
extra log reading. The name match makes the rule exact as soon as a log
line carries the name.

## Reverses if

A PoE2 log line is found that names the trade counterparty (then match by
name only and never guess), or players report the oldest-card guess drops
the wrong request in normal play (then revisit alternative (c) or (b)).

## Tests

tests/test_trade_close.py (oldest, named, unknown name, parsed log lines,
no open card, Recent list kept, dashboard wiring).
