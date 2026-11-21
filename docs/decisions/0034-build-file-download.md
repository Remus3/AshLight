# 0034 - The game's `.build` file as a download only (TC-BUILDFILE, AUDIT-BUILDFILE)

Date: 2026-11-17. Lane AREA-MATH batch 6. Rows TC-BUILDFILE and
AUDIT-BUILDFILE. Inputs: CLAUDE.md "Game ToS floor", decision 0009
(build-time data), 0014 (player-click delivery), 0031 (same save pattern
for the loot filter), research 0018 section 3 (adjudicator ruling),
research 0020 item 5, research 0027 (schema and id mapping).

## Adjudicator ruling (2026-11-17, research 0018 section 3)

A `.build` file only as a user-saved file (a download on the player's
click); the app never writes into the game's planner folder.

## Decision

- `server/al/theorycraft/buildfile.py` builds GGG's documented Build
  object (one bare JSON object, no version key) from the loaded PoB build:
  name, description, ascendancy, passives, skills with supports, inventory
  slots. It has no file, path or OS code (test).
- Passive ids: PoB node id == GGG tree export `skill` -> that node's `id`
  (e.g. `strength89`), from the cached export (decision 0009); no bundled
  table. Ascendancy: the export's ascendancy id for PoB's name. Gems: PoB's
  `gemId` when it matches `Metadata/Items/Gems/<word>`. Inventory: only the
  nine inventory ids GGG's page shows.
- Unknown or unmapped parts are dropped, never guessed, and each drop is
  named in a plain note on the dashboard (`build_file.notes` in GET
  /api/build).
- `validate()` checks a document against the documented fields; tests run
  it on AshLight's output and on GGG's example shapes.
- GET /api/buildfile (token, Host, Origin checks) answers with the text as
  `Content-Disposition: attachment`; the file name is made from the build's
  own name, letters, digits and `-` only, never from request input; 404
  without a build. The core writes no file.
- The dashboard's "Save .build file" button hands the text to the browser
  as a download; the player moves it into the game's folder. The summary
  and the notes are ready as soon as a build is loaded (no click).
- AUDIT-BUILDFILE: tests/test_audit_buildfile.py fails if any source under
  server/, web/, app/, tools/ or scripts/ names the game's planner folder
  or its documents folder, so no code path can build a path there;
  tests/test_tc_buildfile.py checks the generator and the endpoint hold no
  write code and that a served request leaves no `.build` file behind.

## Alternatives

- Write the file into the game's planner folder (what Path of Building
  does): rejected by the adjudicator ("never modify any game file" floor;
  the game consumes tool output unprompted).
- A bundled PoB-id -> string-id table: rejected; GGG's own export carries
  the ids (decision 0009, research 0027).
- No export: needlessly strict; GGG invites tool-made files ("created
  manually or by tools").

## Why

No game-file write, no input to the game; the player's click and the
player's move place the file, as for the loot filter (0031) and the
Copy-code clipboard write (0014). The data is GGG's documented format and
GGG's published tree export.

## Reverses if

GGG explicitly permits tools to write into the planner folder; the
operator rules a click-triggered write acceptable; a file made this way
fails to load in game (then the mapping is re-researched, research 0027);
GGG's page names another passive id source.

## Addendum 2026-11-21 (TC-BUILDFILE-EXIT-WATCH, F-187): the exit trigger

Recorded as an addendum, not an amendment: it adds a watch and changes
no rule of the Settled line (CLAUDE.md is not edited by this row).

- Decision: the download is planned to retire once Path of Building
  PoE2 exports `.build` itself. `tools/tc_drift.py` reads the body of the
  one daily releases reply it already fetches (decision 0025; no extra
  request, the body is read as text and never stored); a line naming an
  export together with `.build` records a sticky `build_export` {tag,
  seen} in ops/runtime/tc_drift.json, and every loop-tick summary and
  `tc_drift.py note` HOLD line then carries "PoB exports .build itself:
  retire AshLight's .build download by an amendment of decision 0034".
  The note fires the review; nothing is removed automatically. The
  retirement itself lands as a further dated amendment here (the
  section above does not cover a retirement), which also clears the
  state key.
- Alternatives: retire automatically when the note fires (rejected: a
  release-note word match is a hint, not proof the export works in
  game); a separate watch or a read of PoB's changelog file (rejected:
  a new request, decision 0025 allows one releases read per 24 h);
  re-raise only for the release that says it (rejected: the next
  release's notes would silence it before anyone acted, so the flag
  stays until the amendment).
- Why: ZERO-CLICK, the loop tick's existing check raises the exit with
  no reminder; players who paste a share link and have no PoB keep the
  route until a person confirms PoB's export.
- Reverses if: the word match misfires on real release notes (then a
  tighter phrase), PoB announces the export somewhere other than its
  release notes, or the operator rules the download stays regardless.
