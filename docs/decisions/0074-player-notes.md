# 0074 - Player notes: one bounded file, a token route and the your-note row (PLAY-F-186A)

Date: 2026-11-22. Wave 31, package PLAY-F-186A-PLAYER-NOTES-STORE (finding
F-186). Inputs: decision 0036 (bounded player-data files), decision 0038
(the character key), decision 0042 (hot reload), decision 0043 (the zone
guide), decision 0029 / RUN-ZONE-RESET (the zone a snapshot names). The UI
edit box and the export option are PLAY-F-186B.

## Decision

1. The player may keep their own plain-text note per zone and character.
   The notes live in ONE local file, `<runtime>/player_notes.json`
   (ops/runtime, gitignored, the runtime dir from server/al/paths.py):
   `{"schema": 1, "notes": [{"character", "area_id", "text", "at"}]}`.
   Bounds: at most 300 notes in the whole file, each at most 200
   characters, at most 12 characters (decision 0038), a character name at
   most 64 characters, a 2 MB read cap. Over a bound on a Save the oldest
   note leaves (the character whose newest note is oldest, for the
   character bound); the note just saved always stays.
2. The key is the Client.txt area id the log already gives and the
   character name of decision 0038. No new read: nothing game-side, no
   clipboard, no screen.
3. Written only by `POST /api/player-note` on the player's Save: the
   token, the Host / Origin and Sec-Fetch-Site checks of every POST, a
   `text/plain` body (UTF-8; any other type is 415) of at most 4096 bytes
   (413). The body is the note; an empty body removes it. `?area=<id>`
   (letters, digits, underscore, at most 64) names the zone, else the zone
   being played; the character is always the one being played. With no
   character or zone known the Save is refused. The text is never logged.
4. Plain text, no markup: whitespace runs fold to one space; control,
   format, surrogate, private-use and unassigned characters are refused;
   a text over 200 characters is refused, never cut. Renderers show it as
   text only.
5. The core loads the file into the hot reload registry (decision 0042).
   A hand edit is taken on its next stat change. A malformed file (bad
   JSON, wrong schema, a bound broken, a bad entry) keeps the last good
   copy and shows one Checks note ("Your notes did not load ... The last
   good copy stays in use."). At start a malformed file falls back to its
   `.bak` (jsonfile keeps one, a copy of the last good write) as the last
   good copy; the broken file is left alone until the next Save writes
   over it.
6. The snapshot carries one key, `player_note`: `{"area_id", "text",
   "at"}` of the current character's note for the zone being played, or
   null. It is looked up at snapshot time, so a zone entry or a character
   switch changes it at once.
7. Play view guide mode (server/al/playcards.py) shows it as its last row,
   kind "note": "Your note: <text>", at most 52 characters shown (cut at a
   word with "..."), the whole note in the row's `full` (the title text).
   The row keeps its place: AshLight's guide parts leave first when the
   block runs over 7 rows or 52 composed words. The note's own words are
   the player's data and are not counted.
8. Names and notes stay local. They are not in the report, the debug
   counters or the event log. The settings export carries them only when
   the player picks that option (PLAY-F-186B). Clear run history does not
   remove them: they are the player's own writing, not a record AshLight
   made.

## Alternatives

- A JSON body (`{"area_id", "text"}`): rejected; the package asks for
  plain text only, and a text body leaves no fields to validate. The zone
  rides in the query instead.
- Notes in the guide file or config/local.json: rejected; the guide file
  is AshLight's own tracked words (decision 0043) and config is settings,
  not player data.
- Show the note in every Play mode (town, map): rejected for this package;
  the package names guide mode, and a later row can widen it.
- Restore a malformed main file from its .bak (jsonfile read_json
  backup=True, the durable stores' route): rejected; a hand edit gone
  wrong would be overwritten silently. Keeping the last good copy with a
  Checks note is the hot reload contract the package asks for.
- Clear the notes with run history: rejected (item 8).

## Why

The player's own reminders ("the exit is north of the camp") fit the
zone-guide moment exactly and need no new read. One bounded file under
the runtime dir with a token-gated write is the decision 0036 pattern the
other player-data stores already follow.

## Reverses if

The operator rules local note files unwanted, a note reaches a report or
an export unasked, or decision 0036 changes.
