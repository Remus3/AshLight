# 0072 - poe.ninja cadence tiers and the release polling gate (GO-PUBLIC-NINJA)

Date: 2026-11-21. Package: DATA-PRICE-CADENCE (wave 18, finding F-046).
Inputs: decision 0026 (price book, per-type hourly gate), decision 0013
(one web_data opt-in, default off), DATA-PRICE-POLITE (back-off, spacing,
daily retry of a failing type), ruling Q-05 and the close-out ruling of
plan 07 (adjudicator LE-38), operator act OA-2 (docs/plan/09), skipped in
writing on 2026-11-18. Amends decision 0026: the per-type hourly gate of
its item 1 (the plan text calls it item 2).

## Decision

1. Cadence tiers (`server/al/pricebook.py`, `server/al/ninja.py`).
   Currency (rates.json) stays hourly (`ninja.MIN_INTERVAL_S`). The other
   22 overview types (9 Unique* stash overviews, 13 exchange kinds) are
   asked every `pricebook.INTERVAL_S` = 3 h, and every
   `pricebook.PRESSED_INTERVAL_S` = 1 h while a press matched the type in
   the last `pricebook.PRESSED_FOR_S` = 24 h. A day with no press makes at
   most 24 + 22 x 8 = 200 overview GETs; the league list stays on its own
   6 h gate and is not an overview GET.
2. Press tracking. `RatesClient.lookup` calls `PriceBook.note_press(type,
   now)` when a press hit a book type. The press time is kept in memory
   only (no disk write on the press path); the next refresh copies the
   still-live press times into the cache doc (`pressed`) and saves them
   with the round, so a restart keeps them. A plain dict lookup (the price
   watch's cache re-read) is not a press; the press path passes a parsed
   item object. Press times older than 24 h are dropped at the next
   refresh.
3. League change. A type cached for another league id than the one now
   priced waits at most 1 h (decision 0026 item 4: a new league is priced
   within the hour), not its 3 h gate. A failing type keeps the daily
   retry of DATA-PRICE-POLITE.
4. Release gate. `ninja.RELEASE_POLLING = False`. While it is False an
   installed copy (`paths.install_mode() == "installed"`, DEP-05; a
   missing function or an error reads as a checkout for the default, an
   error of an injected `installed` callable reads as installed) makes no
   poe.ninja request at all: `refresh()` returns `off: release build`
   (force included), `refresh_async()` starts nothing, and
   `snapshot()["blocked"]` reads `release build` (after `web data off`,
   before `contact not set`). The item-check press still builds its
   offline trade link (decision 0017); the card has no poe.ninja price. A
   source checkout polls with the constant off. The constant name is the
   contract DEP-08's release build refusal reads.
5. Default in force: no answer from poe.ninja yet (OA-2 skipped in writing
   2026-11-18, optional later). The constant flips only by a new decision
   recording poe.ninja's written yes, an approved mirror or the operator's
   written ruling. Silence is not consent.

## Alternatives

- Keep every type hourly (decision 0026): about 552 overview GETs a day
  per install; rejected as more than one user needs (F-046).
- Fetch a type only on a press: the first press would show no price and
  movers would go empty; rejected as in decision 0026.
- Persist the press time on the press: a disk write on the hotkey path;
  rejected (saved with the next refresh instead).
- Count a price watch re-read as a press: the watch re-reads after every
  book refresh, so a watched type would stay hourly for ever and the 200
  bound would not hold; rejected.
- Q-05 ship-regardless: rejected (stricter reading; adjudicator LE-38).
- Gate release builds on web_data alone: the opt-in is the player's, but
  per-install polling at scale is poe.ninja's call; rejected.

## Why

The tiers keep a pressed type as fresh as before and cut idle polling to
at most 200 conditional GETs a day, within research 0019's "roughly
hourly" guidance for what matters to the player. The release gate takes
the stricter reading of the ToS floor's web-data rules for a third party
that has not yet said yes to per-install polling at release scale.

## Reverses if

poe.ninja says yes in writing (flip RELEASE_POLLING by a new decision),
asks for a mirror or for less polling (a new decision), or blocks the
client; or the press / watch distinction misfires (then a press flag at
the call sites in core.py and price.py).
