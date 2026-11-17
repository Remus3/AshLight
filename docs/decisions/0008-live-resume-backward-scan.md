# 0008 - Live resume: bounded backward scan of Client.txt

Date: 2026-11-16. Trigger: ROADMAP row LIVE-RESUME (LIVE-1 found that a
core restart left zone, character, level and deaths empty until the next
zone change or level-up, because the tailer starts at the end of the file).

## Decision

Scan only, no persisted state. When the tailer first starts at the end of
Client.txt it calls `server/al/resume.py` `scan()` with its start offset.
The scan reads the file BACKWARDS from that offset in 1 MB chunks, capped at
32 MB, and folds the result into `SessionState.restore()`. Nothing is
published on the bus, so no old event is re-listed and no old whisper or
trade card comes back.

- Current run = everything after the newest `***** LOG FILE OPENING *****`
  marker. Zone (last real scene; `(null)`, `(unknown)` and `Act <N>` are
  skipped as in LIVE-1), area id and level, AFK / DND, deaths and level-up
  counts come from the current run only. A zone of an earlier run is not
  shown as current.
- Character, class and level: the newest level-up of the configured
  character, else the newest level-up seen, across runs (a level persists).
- The scan stops at the marker once the character is known, else at the
  cap. A line cut by the cap or still unterminated at the offset is dropped.
- Speed: a C-level keyword search per chunk (scene, area generation, system
  line, marker), narrowed to system lines once zone and area are known and
  to level-ups before the current run; only those lines are parsed. Budget
  in `tests/test_budgets.py`: a full 32 MB scan under 500 ms (measured about
  190 ms realistic, 570 ms for a log made only of event lines).
- `zone_entered_at` is the scene line's local time converted to epoch,
  never in the future, so the zone timer is right after a restart.
- Diagnostics: `tailer.resume` in /api/state = {bytes, ms, hit_marker,
  recovered}.

## Alternatives

- Persist state to `ops/runtime/` on every change and reload it on start:
  rejected as the primary path. It goes stale when the game ran while the
  core was down, needs a write per event, and needs its own invalidation
  rules; the log already holds the truth.
- Scan plus persistence (persist only deaths and counts beyond the cap):
  not needed; at about 0.7 MB of log per hour of play, 32 MB covers a game
  run of well over a day.
- Replay the last N KB forward through the bus (research 0002 section 2):
  rejected; it re-lists old events and old trade whispers, and a fixed N
  either misses the last level-up or reads far more than needed.

## Why

Read-only and Client.txt only (decision 0003), no new runtime file, bounded
time and memory on a log of hundreds of MB, and state matches the log the
moment the tailer starts.

## Reverses if

GGG changes the log so the marker or the level-up line no longer appears,
or a real log shows the 32 MB cap misses the current run's deaths in normal
play; then add persistence of the counts.
