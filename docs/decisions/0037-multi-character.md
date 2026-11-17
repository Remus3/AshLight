# 0037 - Per-character run history, pace, act splits and deaths (UTIL-MULTICHAR)

Date: 2026-11-17. Lane AREA-UTIL batch 10. Row UTIL-MULTICHAR. Inputs:
research 0028 section 3 item 3 (multi-character view), decisions 0008
(LIVE-RESUME), 0023 (act splits resume), 0036 (run history file).

## Decision

- Key: the character name exactly as the player's own Client.txt reports
  it in a level-up (`<name> (<class>) is now level <n>`) or death line.
  The name stays on this computer (snapshot, dashboard, ops/runtime file);
  it is never sent anywhere.
- Current character: the first level-up names it (unchanged). After that,
  a level-up of another name switches to that character (a new or known
  one), and a death line switches only to a character the player already
  has. Names seen in "has joined / left the area" lines this game run are
  other players and never switch. A configured character
  (`character` in config/local.json) never switches, which is the escape
  hatch for party play.
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
- Restart: LIVE-RESUME's run events now include the join / leave lines;
  when they name more than one of the player's characters the state
  replays them through a scratch SessionState (the live rules) and takes
  its per-character sets. One character keeps the decision 0023 path.
  Still no persisted state for the live run (decision 0008 not reversed).
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
in normal use, or the operator rules character names must not be stored.
