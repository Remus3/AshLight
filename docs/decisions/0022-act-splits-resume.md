# 0022 - HUD-ACT-RESUME: act splits rebuild from Client.txt at core start

Date: 2026-11-17. Trigger: ROADMAP row HUD-ACT-RESUME ("act splits survive
a core restart ... also confirm the cruel `C_G<n>_` / interlude `P<n>_` id
prefixes from a live log (LIVE-1)"). Inputs: decision 0008 (LIVE-RESUME),
decision 0020 (HUD-ACT). Amends decision 0020 item 1 ("a core restart
starts an empty run"). Number check: main held 0001-0021 at merge time (0021 = tc-code-real), so this is 0022;
renumbered from the lane draft 0021.

## Decision

1. `resume.scan` also returns `act_areas`: the current game run's campaign
   and endgame area generations (run = since the newest
   `***** LOG FILE OPENING *****` marker, the same boundary as deaths),
   oldest first, each with its line time and the character's level then.
   A streak of ids in one act (or of maps) keeps only its first entry,
   except `G1_1` (it can start a new character's run). That is exactly what
   `acts.ActSplits.fold` reacts to, so the rebuilt splits equal a live fold
   and the list stays small (3000 maps compress to one entry).
2. `SessionState.restore` folds them into a fresh `ActSplits`, timed by the
   log lines (local time to epoch, capped at now). An empty list keeps the
   current splits. The core lists `acts` in `tailer.resume.recovered`.
   Still no persisted state (decision 0008); nothing is listed.
3. The level before the run's first level-up of the character is that
   level minus one, else the character's current level; it only feeds the
   new-character test of `fold`.
4. Prefix check (LIVE-1): NOT done in this lane. The lane had no read
   access to the live Client.txt, and LIVE-1 is itself blocked on the
   operator's in-game acts (cruel / interlude zones must be played first).
   `acts.act_of` keeps the inferred `C_G<n>_` / `P<n>_` prefixes; an
   unknown id changes nothing (the open split keeps running), so a wrong
   guess degrades to "no new split", never to a wrong one.

## Alternatives

- Persist the splits to a runtime file: rejected, decision 0008 rules no
  persisted state and the log already holds every needed line.
- Scan across earlier game runs: rejected, the time between game runs
  (the game closed overnight) would count into an act.
- Return every area generation uncompressed: rejected, a long endgame run
  holds thousands; the compression is lossless for `fold`.

## Reverses if

- Live cruel / interlude ids differ from the inferred prefixes (fix
  `acts.act_of`, LIVE-1), or GGG drops the area generation line.
- Decision 0008 reverses (persisted state), or the 32 MB scan cap misses
  the start of a normal play session's run.
- Players want act splits that span game restarts (then a persisted run).

## Copy

The partial-split note read "partial: counted from when AshLight started",
false after a resume (the time counts from the game run's first act zone
in the log). Design review 2026-11-17 (R1) reworded it to "partial:
counted from the first zone AshLight saw", true for both a live start and
a resume.
