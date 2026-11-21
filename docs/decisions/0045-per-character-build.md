# 0045 - Per-character build, stale-build alert, upgrade notices (BUILD-LIVE)

Date: 2026-11-17 (drafted as 0041, renumbered to 0045 at merge). Row BUILD-LIVE (operator order: item upgrade notices
tied to the build of the character being played, live, without stopping
to find a PoB link). Inputs: decisions 0003 (read policy), 0004
(theorycraft via PoB interop), 0014 (build view, item card), 0024
(TC-DELTA), 0032 (MATH-COMPARE), 0038 (per-character key), research 0033
(live character data: the official API shape).

## Decision

- One build per character. The key is the character name decision 0038
  takes from the player's own Client.txt. Files: ops/runtime/build/chars/
  `c-<name>-<sha1 8>.txt` (plain names; the hash keeps names that differ
  only in case apart on Windows) or `x-<utf-8 hex>.txt`, each holding a
  PoB code or a character JSON; `build/active-character.txt` names the
  character played last so its build is back on start before the log
  names anyone. Names stay on this computer.
- Swap with no click: the core loop tick (`Core.tick_build`, also at each
  item press) calls `BuildStore.sync()`, which follows `state.character`.
  A new character loads its own file (or no build); the store's listeners
  then publish the build summary (now with `character`), re-score the
  last item card and the checked items, and refresh PoB outputs. An
  unknown character (None) never swaps.
- Migration: the single legacy build/last-code.txt moves to the first
  character known when that character has no file of its own, once; the
  old file is renamed last-code.txt.migrated, never deleted. A paste made
  while no character is known still goes to last-code.txt.
- Hot reload: `sync()` re-reads the active file when its (mtime, size)
  moves, and re-checks its bytes while the mtime is under 2.5 s old (the
  coarse-mtime rule of core._config, AREA-AUDIT P5-4). A broken file never
  replaces a good build; the error shows on the build view.
- Stale-build alert (`build_alert` in the snapshot, words in
  state.build_alert_text, dashboard slot #build-alert via
  web/buildlive.js): `missing` (the log names a character with no saved
  build), `class` (the log's class or ascendancy does not fit the build's;
  base class and its ascendancies fit each other until the player
  ascends), `level` (the log level is 5 or more past the build's level; a
  build planned for a higher level never alerts).
- Upgrade notices: each item-hotkey press (the one clipboard read,
  decision 0003) adds the item text to a per-character list in memory only
  (10 items, 12 characters, least recently used dropped; never written to
  disk, never sent). On every build or weight change (`LastEval.rerun`)
  and every press the list is re-scored with the stat weights, or the
  weights PoB measured for this build earlier (MATH-WEIGHTS cache); no new
  PoB calc run, so a swap stays quick. `upgrades` in the snapshot lists the
  ones that are upgrades now: slot, the item it replaces, the delta, and a
  fit line (the item's level requirement against the log level, else the
  build's class); `new` marks those that were not upgrades before the
  last change.
- Build sources are pluggable (`theorycraft/providers.py`):
  `PasteProvider` now, and a `GggApiProvider` stub modelled on research
  0033 (OAuth public client with PKCE, scope `account:characters`,
  /character/poe2 and /character/poe2/<name> returning equipment,
  jewels, skills and passives, no backpack) that reports "not set up" and
  raises NotConfigured. It makes no request and holds no token; its
  answer will be character JSON the existing charjson path reads, so it
  drops in without a UI change (`providers` in GET /api/build,
  `BuildStore.import_from`). Turning it on is its own decision.

## Alternatives

- Keep one build and only warn on a character change: rejected; the
  player would still have to find and paste a PoB link on every switch,
  which is the friction the operator named.
- Persist the checked items to disk so notices survive a restart:
  rejected for now; item text from the clipboard stays in memory only
  (live.py contract), and the list refills with the next presses.
- Re-score the checked items with the live PoB calc: rejected; up to 10
  calc runs per change would make a swap slow (decision 0024 R7 budgets).
  The cached PoB weights give the same ranking when PoB measured them.
- Call the official character API now: rejected; no OAuth client is
  registered, and the ToS floor allows only documented endpoints with
  their headers obeyed. The stub keeps the seam ready.
- Alert when the build is ahead of the character: rejected; a planned
  endgame build is the normal case for levelling with a guide.

## Why

The player switches characters and levels faster than they re-import;
the item check silently scored against the wrong build. Keying by the
character the log already names makes the check follow the player with no
click, the alert says when the saved build is behind, and the checked-item
list turns every build or weight change into upgrade notices.

## Reverses if

Decision 0038 reverses (no character key), a Client.txt login line or the
official API gives a better key, the 5-level gap misfires in normal play,
item text must not be held in memory between presses, or the operator
rules the checked-item list unwanted.

## Amendment 2026-11-18 (TC-PRESS-SAMPLES, plan unit F-082, ruling Q-27)

A dated additive clarification of "checked items kept in memory only".

- Dev-host fixture capture is the one exception: while the gitignored
  config/local.json key `dev_press_samples` is exactly true (off by
  default; a dev-host switch, not a player setting: not in
  settingsio.ALLOWED, never exported or imported, shown nowhere), the card
  part server/al/theorycraft/cardparts/sample.py saves a sanitized copy of
  each pressed item text as a fixture candidate under
  <sidecar>/Scratch/press-samples/. Its compute() returns None always, so
  the card never changes.
- Same reads as normal use: the text is the one clipboard read of the
  press (decision 0003); nothing new is read and nothing is sent.
- Sanitized: the Note line keeps only a `~price` / `~b/o` price form and
  masks every other word; every @name is masked; anything after a whisper
  marker is masked; control characters dropped; 8000 characters at most.
- Bounded: at most 50 candidates; at the cap a new one is not written
  (nothing is deleted); a candidate is named by the hash of its sanitized
  text, so a re-score writes nothing new. An installed copy has no Scratch
  folder and never writes; a pytest run writes only into a test sidecar.
- tools/press_samples.py lists and checks the candidates and promotes one
  after the developer's review: it writes only a rewritten form (invented
  name and base lines, invented words for every non-structural word, the
  shape kept) into tests/fixtures/press_samples/ and refuses a candidate
  that still matches a mask pattern or would be copied verbatim
  (decision 0009).
- Alternatives: a player setting (rejected: no player needs it, and it
  would ride the settings export); a log-shape style ledger only (F-061
  covers Client.txt shapes; item texts need whole samples); evicting the
  oldest candidate at the cap (rejected: no delete path in the core);
  promoting verbatim after review (rejected: decision 0009, a pressed item
  is game text).
- Why: real item texts drive parser fixes, and the normal presses are the
  samples with no extra act in play.
- Reverses if: a sanitized candidate is found holding an account,
  character or chat word, the operator rules local item-text files
  unwanted even on a dev host, or GGG restricts derived local records.
