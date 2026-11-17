# 0031 - Loot filter snippet as a download only (UTIL-FILTER)

Date: 2026-11-17. Lane AREA-UTIL batch 5. Records the adjudicator ruling
of research 0022 section 3 as built. Inputs: CLAUDE.md "Game ToS floor",
decision 0014 (player-click delivery), research 0022, ROADMAP UTIL-FILTER.

## Decision

- `server/al/theorycraft/lootfilter.py` generates an AshLight-original
  `ashlight.filter`: comments (what it is, the not-affiliated notice, the
  one-line `Import "ashlight.filter" Optional` the player adds) and one
  Show block that highlights rare drops of the item bases the loaded build
  wears. GGG's documented filter syntax only; no text from another filter.
- `GET /api/filter` (token, Host and Origin checks as every API call)
  answers with the text as an attachment. The core writes no file.
- The dashboard's "Download ashlight.filter" button fetches it on the
  player's click and hands it to the browser as a download; the player
  chooses where to save it and adds the Import line themselves.
- AshLight never writes into the game's documents folder or any game
  folder (tests/test_lootfilter.py, tests/test_audit_buildfile.py).
- Not built yet (row UTIL-FILTER-2): price tiers from the cached
  poe.ninja rates and the optional merge into a filter the player hands
  over through the browser file input.

## Alternatives

- Write or refresh the file in the game's filter folder: rejected by the
  adjudicator (game-file modification, GGG's "interact with the game or its
  files" ban).
- Account Item Filters API upload: documented, but OAuth only; blocked on
  TC-OAUTH-REG.
- No feature: fallback only.

## Why

No game-file write, no input to the game; delivery is the player's click,
like the Copy-code clipboard write (decision 0014); the input (the loaded
build) is already local.

## Reverses if

GGG states in writing that filter tools may not be offered or that a
generated filter counts as game-file modification; the operator orders a
filter-folder write in writing; GGG documents such a write as allowed;
the OAuth client exists (then the API upload is added).
