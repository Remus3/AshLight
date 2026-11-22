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

## Amendment 2026-11-18 (RUN-DURABLE-STORE-FILES, finding F-014)

- Each player-data file keeps one `.bak` of its last good copy: run
  history, map ladder, price watch, session summaries, the hint store, the
  zone-guide visits file and the overlay layout in local.json are written
  through jsonfile with backup=True (temp file, fsync, replace, then the
  same bytes to `<name>.bak`) and read with the .bak restore: a main file
  that exists but does not parse (empty, half written, wrong kind, over
  its cap) is rewritten from its .bak. A missing main file is never
  revived from a stray .bak.
- Privacy: a clear keeps no copy. Clear run history removes the .bak of
  the run history, map ladder and visits files with their data, and the
  price watch Clear removes its .bak; each clear first writes the empty
  document (main and .bak), then deletes the .bak, so a .bak that cannot
  be deleted at that moment holds nothing old. A visits document with no
  character (the cleared book) is written without a .bak.
- The .bak files sit beside their main files (ops/runtime, gitignored;
  local.json.bak beside config/local.json). Player builds
  (theorycraft/store.py) keep their own writer.
- Alternatives: no .bak (rejected: a crash mid-write on a disk that lost
  the rename's data cost the player's history, F-014); keep the .bak
  through a clear for undo (rejected: Clear must leave nothing behind);
  remove the .bak in core's clear paths (rejected here: the store modules
  own their files, and core's own writers are RUN-DURABLE-STORES).
- Reverses if: the .bak doubles a file past its budget, a restore revives
  data the player removed, or decision 0036 itself reverses.

## Amendment 2026-11-21 (TC-WEIGHTS-DELTA-EXPORT, finding F-134)

- The settings file moves to schema 2. Beside "settings" it carries one
  top-level "weights" block: the player's stat weight changes over
  AshLight's defaults and the sidegrade band parts that differ, in the
  weights file's own version 2 form ({"weights": {stat key: number or
  null}, "sidegrade": {abs?, pct?}}; null is a default row the player
  removed; decision 0024, TC-WEIGHTS-DELTA-STORE). The core takes it from
  its weights store; a weights file that did not load (defaults in use)
  adds no block.
- The block is checked by the weights store's own rules (the version 2
  checks, then the merged document, at most weights.MAX_KEYS rows); a bad
  block refuses the whole file with nothing applied, as a bad setting
  does. An import with the block makes the weights the defaults plus the
  file's changes and re-scores the last checked item at once; a file
  without the block, which is every schema 1 file, leaves the weights as
  they are. Schema 1 files still import; a "weights" key in a schema 1
  file is never read. The report gains "weights_applied" and the
  dashboard says "Imported N settings and your stat weights. They
  replace the stat weights you had here."
- The import cap stays 16 KB (server and page; pinned by the security
  surface test). An export whose block would pass it leaves the block out,
  as an export leaves out any stored value that does not validate; about
  100 changed or added rows plus every default removed still fit. The
  download sentence keeps "AshLight's settings only", which stays true
  with or without the block.
- The allow-list is unchanged otherwise: the block holds stat keys and
  numbers only, never the contact, a token, a cookie or a path; an import
  never turns web data or the calc on.
- Alternatives: merge the file's changes over this computer's own
  changes (rejected: the result would match neither computer, and the
  file is meant to move one player's set); put the weights inside
  "settings" (rejected: settings keys are config/local.json keys, the
  weights live in their own store file); full weights document instead
  of the changes (rejected: it would pin today's defaults on the other
  computer, which TC-WEIGHTS-DELTA-STORE exists to avoid); raise the cap
  to 256 KB so a full weights.MAX_KEYS block always fits (rejected here:
  the 16 KB body cap is pinned with every other route cap, and a real
  change set is tens of rows).
- Reverses if: the weights store changes its file form again, players
  expect the import to keep their own weight changes, or a real export
  drops its weights block at the 16 KB cap (then raise the cap with its
  security surface pin).
