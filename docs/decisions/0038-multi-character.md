# 0038 - Per-character run history, pace, act splits and deaths (UTIL-MULTICHAR)

Date: 2026-11-17. Lane AREA-UTIL batch 10. Row UTIL-MULTICHAR. Renumbered
from 0037 (taken by the trade stat ids decision on main) and its switch
rule tightened by the MULTICHAR-FIX ruling the same day (below). Inputs:
research 0028 section 3 item 3 (multi-character view), decisions 0008
(LIVE-RESUME), 0023 (act splits resume), 0036 (run history file).

## Decision

- Key: the character name exactly as the player's own Client.txt reports
  it in a level-up (`<name> (<class>) is now level <n>`) or death line.
  The name stays on this computer (snapshot, dashboard, ops/runtime file);
  it is never sent anywhere.
- Current character (MULTICHAR-FIX rule): the first level-up names it
  when no character is known yet (unless that name joined or left the
  area this game run). After that the current character switches ONLY on
  the first level-up or death line after a game start (`***** LOG FILE
  OPENING *****`, log_opened), and only when no other player has joined
  or left the area since that game start; the line may name a new or a
  known character. Never mid-session: a party member who was already in
  the area when the player arrived has no join line of their own, so a
  mid-session level-up of an unknown name proves nothing. Names seen in
  "has joined / left the area" lines this game run never switch. A
  configured character (`character` in config/local.json) never switches.
- Per character: level, class, level-ups, deaths, pace, act splits and the
  run's deaths per zone. SessionState keeps the current character's set as
  its attributes and parks the others by name (at most 12 characters,
  least recently used dropped). Map runs, the death recap, the session and
  the zone stay session-wide. The snapshot top-level fields are the current
  character's, so the overlay and every older consumer are unchanged.
- Area generations carry no name, so they fold into the current character.
  A switch takes effect at the new character's first level-up or death
  line; a brand-new character's run still starts at the first campaign
  zone (G1_1) generated since the last name line. Other zones entered
  before the switch count for the previous character (the
  act splits ignore a return to an act already closed, so only a
  first entry into the previous character's next act can be misfiled).
- Restart: LIVE-RESUME's run events (the current game run only) include
  the join / leave lines and the level-up class. The state replays them
  through a scratch SessionState seeded with the scanned character (the
  newest level-up) and a game start when the scan reached the run's
  marker, so the live rule picks the run's character: the scan's newest
  name is replaced when the run's first name line named another
  character, and dropped (character unknown until the player's next
  level-up) when that name joined or left the area. Act splits stay the
  decision 0023 run-wide rebuild. Characters of earlier game runs come
  back only through the run history file. Still no persisted state for
  the live run (decision 0008 not reversed).
- Run history file: schema 2, `{"schema": 2, "characters": {name:
  {"runs": [...]}}}` ("" = unknown character), at most 12 characters and
  20 runs each, 2 MB read cap. A schema 1 file (one flat list) is
  migrated in place on load, runs grouped by their saved character. Bests
  and deaths by zone are per character. Parked characters' runs are saved
  under their own name.
- Dashboard: shows the character being played by default; a small
  selector under the Level tile ("Show numbers for", hidden with fewer
  than 2 characters, at most 12, not a live region) swaps level, pace,
  deaths, act times and run history to another character's numbers.

## MULTICHAR-FIX ruling (main session, 2026-11-17)

- Decision: renumber to 0038 (0037 is the trade stat ids decision; 0038
  is the highest number on main and every branch + 1) and switch only on
  the first name line after a game start with no join / leave since that
  start, or when no character is known.
- Alternatives: keep the eager rule (a level-up of a name never seen
  joining switches): rejected, it misfires on a party member already in
  the area when the player arrives. Track party context per zone change
  only: rejected, a party member already in the new zone has no join line
  either. Treat a first-zone (G1_1) generation as a game start: rejected
  for now, a veteran entering a party member's G1_1 would then switch.
- Why: a wrong switch files a stranger's level, deaths and splits under
  the player; a missed switch only waits for the next game start, and the
  `character` setting pins it.
- Known limits: a change of character through character select without
  restarting the game is followed only at the next game start (or with
  the `character` setting); a party member already in the area at login
  who levels up or dies before the player's own first name line in that
  game run is taken as the player's character.

## Alternatives

- One merged history with a character filter only in the view: rejected;
  the 20-run cap would let one character push out another's bests.
- Treat every level-up name as the player (no join / leave filter):
  rejected; a party member levelling would switch the current character.
- Buffer area generations until the next name line: rejected for now; a
  late-campaign character can go an hour without a level-up, so the act
  card would sit stale. Revisit if LIVE-1 finds a login line that names
  the character.

## Reverses if

A Client.txt line that names the character at login is found (then switch
on that line, not on level-up / death), party play shows misfiled splits
in normal use, character changes without a game restart are common enough
that waiting for the next game start misfiles runs, or the operator rules
character names must not be stored.
