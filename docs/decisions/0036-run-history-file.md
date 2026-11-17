# 0036 - Run history and price watch files; settings export / import (UTIL-RUN-HISTORY, UTIL-PRICE-WATCH, UX-SETTINGS-IO)

Date: 2026-11-17. Lane AREA-UTIL batch 9. Rows UTIL-UNDERLEVEL,
UTIL-RUN-HISTORY, UTIL-PRICE-WATCH, UX-SETTINGS-IO. Inputs: research 0028
sections 3-6 (adjudicator rulings B, C, D, E), decisions 0008 (LIVE-RESUME),
0013 (web data opt-in), 0026 (price book), 0031 / 0034 (download pattern).

## Decision

- UTIL-RUN-HISTORY (ruling C): each time a campaign act split closes, and
  when the run finishes, the core saves the run's closed, complete act
  splits, its deaths per zone, character and class to ONE local file,
  `<runtime>/run_history.json` (ops/runtime, gitignored, resolved through
  server/al/paths.py). At most 20 runs, 16 splits and 40 zones per run,
  64-character strings, 256 KB read cap. The Run history card shows the
  best time per act from the OTHER saved runs, this run's delta to it and
  the top 5 zones by deaths across runs, with a visible "Run history is
  on" line, a switch ("run_history": false turns it off; nothing is
  saved) and a Clear button. A partial first split (core started
  mid-campaign) is never a best.
- Decision 0008 is NOT reversed: LIVE-RESUME still rebuilds the current
  run from Client.txt and persists no state of its own. The history file
  is a separate record of finished act splits; a resumed run matches its
  saved record by character and start time (300 s window), so a restart
  never duplicates a run.
- UTIL-PRICE-WATCH (ruling D): an item-check press that priced an item
  from the cached poe.ninja book records what it already read (name, base,
  rarity, corrupted, value, unit, time) in memory and in
  `<runtime>/price_watch.json` (20 items, 64 KB cap). On each price book
  refresh (a new checked_at stamp) and only while web data is on, the core
  re-reads those items from the same cache (RatesClient.lookup: no
  request) and flags a move of at least "price_watch_pct" percent (default
  25) since the press. No clipboard or screen read on refresh, no trade
  call, no URL opened; web data off flags nothing. Clearable.
- UTIL-UNDERLEVEL (ruling B): area level from the log's generation line
  (fallback: the world_areas snapshot level) minus the player's level from
  their own level-ups; at or above "underlevel_gap" (default 3) the act
  card shows a sentence and the overlay status slot the word "N lv under"
  (<= 15 characters, after the trade count, before AFK / DND). Towns,
  hideouts and an unknown player level show nothing. No XP formula.
- UX-SETTINGS-IO (ruling E): GET /api/settings-export (token) answers an
  allow-list of AshLight settings as a download; POST
  /api/settings-import takes the JSON of a file the player picked in a
  browser file input (16 KB cap). Allowed keys only (character, poll_ms,
  hotkeys, league, web_data, tc_calc, overlay layout, underlevel_gap,
  run_history, price_watch_pct). Never exported or taken: contact,
  client_log, port, loop, token, any cookie. Unknown keys are not applied
  and are named back to the player; one bad value refuses the whole file.
  An import never switches web data on: the player is told to tick the
  existing switch (their confirm); switching it off is applied.

## Alternatives

- Rescan Client.txt for old runs: rejected; the player may delete or trim
  it and the resume scan caps at 32 MB (decision 0008).
- Reject a whole import file on any unknown key (strict reading of ruling
  E's "unknown keys rejected"): rejected; a file from a newer AshLight
  would then never import. Unknown keys are rejected per key (never
  applied) and listed, which keeps the ruling's intent (nothing outside the
  allow-list is taken).
- Price watch polling the book on a timer of its own: rejected; it rides
  the existing hourly refresh (decision 0026) and makes zero requests.

## Reverses if

The operator rules local history files unwanted, GGG policy restricts
derived local records, or decision 0013 changes so the cache may be read
while web data is off.
