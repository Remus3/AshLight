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

## Amendment 2026-11-22 (UTIL-MULTICHAR-RELOG, adjudicator ruling)

Trigger: the reverses-if "character changes without a game restart ...
misfile runs" was met in live play. PoE2 writes no `***** LOG FILE OPENING
*****` line on a relog through character select; it writes only
`[INFO Client <pid>] Async connecting to <host>.login.pathofexile2.com:<port>`.
A character died right after a game start (which closed the switch window
on that character), the player relogged as another character, a party
member joined, and the new character's level-ups were dropped as
mid-session. On a core restart the scan took the party member's newer
level-up as the character and the replay then cleared it (unknown).

Decision:
1. server/al/parser.py reads that line as a new event, `char_select`
   (LOGIN_CONNECT). The match is anchored to the whole body and to the
   host suffix: `Async connecting to <label>(.<label>)*.login.pathofexile2.com:<digits>`.
   Any other host is ignored and the host is not kept.
2. char_select opens a relog window. It keeps the set of names seen
   joining or leaving this game run (unlike log_opened, which clears it)
   and resets the party flag. A relog window does NOT consult the party
   flag: a party member can join between the relog and the player's first
   level-up (seen live: the relog, a join ten minutes later, the player's
   first level-up twenty minutes after that), and that join must not
   block the player.
3. In a relog window the first level-up or death of a name never seen
   joining or leaving switches the character and closes the window. Lines
   of known joined / left names neither switch nor close it. A configured
   character never switches. The game-start window keeps the earlier rule
   (party flag included); a second char_select reopens the relog window.
4. resume.scan picks the newest in-run level-up whose name was not seen
   joining or leaving in the scanned run (the configured name when one is
   set). When every in-run level-up is such a name the character is
   unknown, as before; a run with no level-up at all still reads back to
   the newest earlier level-up. resume's keyword scan and run events carry
   char_select, and SessionState._REPLAY_TYPES replays it, so live and
   resumed state agree.
5. The event reads only Client.txt. No ToS floor change.

Known limit (accepted): in a relog window, a party member already in the
zone with no join line of their own (or whose join line was missed) who
levels or dies before the player is taken as the player. This is the same
limit as at game start. It is bounded: the player's own level-up after the
next relog or game start fixes it, and the `character` setting pins it.

Alternatives:
- Reset the party flag at char_select only: rejected. The later join sets
  it again and the player stays blocked, which is the live bug.
- Close the relog window at the first zone entry: rejected. The character
  is learned only from a level-up or death, which comes after the zone
  loads, so the window would never switch.
- Reopen the window on any area_generated: rejected. It would misfile
  mid-session party levels, which this decision exists to prevent.
- Treat char_select like log_opened and clear the joined / left names:
  rejected. It forgets party members seen earlier in the run and lets
  their level-ups be taken as the player.
- Revert a switch when the taken name later joins or leaves: rejected. The
  character would flap.
- Drop the party flag at game start too: rejected. A wider change with no
  evidence beyond relogs.
- Do nothing (players restart the game): rejected. Relog through character
  select is normal play.

Why: the log has no line naming the logged-in character, so the login-host
connect line is the only relog signal, and names seen joining or leaving
are the one reliable "not me" evidence the log gives. Keeping that set
across the relog is what stops a party member from being taken as the
player, live and on resume.

Reverses if: the login-host line also appears on plain reconnects that
keep the character and this misfiles runs; party members with no join line
often level first in normal play; GGG adds a log line naming the logged-in
character (then switch on that line only); or GGG changes the login host
name.
