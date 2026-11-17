# 0029 - Game exit detection (TEST-LIVE-EXIT): Client.txt staleness only

Date: 2026-11-17. Ruled by a distinct adjudicator agent (CLAUDE.md FLEET
item 1). Inputs: CLAUDE.md "Game ToS floor" ("It never touches the game
process"), `docs/decisions/0003-read-policy.md`,
`docs/decisions/0006-fps-measurement-method.md`,
`docs/research/0001-ggg-tool-policy.md`, ROADMAP row TEST-LIVE-EXIT.

Problem: a killed or crashed game writes no Client.txt line (live check
2026-11-17), so the dashboard kept the old zone and its timer running
forever.

## Decision

Ruling (verbatim): "Choose (b). Detect an idle or "maybe closed" state from
Client.txt staleness only, with no OS process-list check of any kind. After
20 minutes with no log line, the dashboard shows "Idle / game may be closed"
and pauses the map clock. The zone label stays but is marked stale. The next
log line clears the idle state automatically."

Built (server/al/state.py, core.py; web/status.js, web/app.js,
app/shared/render_gate.js):
- `tailer.last_line_at` = receipt time of the last parsed line; at core
  start the resumed Client.txt's mtime seeds it (a game closed before the
  core started also turns idle). File metadata of the consented log only.
- `check_log_idle` (core main loop, via `tick_summary`): consented, a known
  last line and `summary.IDLE_S` (20 min) of silence set `tailer.idle`.
  The zone is kept and tagged "frozen - log quiet"; the zone, act and map clocks
  (and the Session tile, UX-REGRESSION-SWEEP 2026-11-17) stop at the last line; the open UTIL-SESSION-SUMMARY stretch closes into
  its card with reason `idle`, ended at the last activity. Nothing is
  wiped.
- Any next line (including `log_opened`, a new game run) clears `idle`.
- The copy never says "closed" as fact: an AFK player writes no lines.

## Alternatives

- (a) OS process-list presence check (tasklist / Toolhelp snapshot by image
  name, no VM_READ handle): rejected. Looking for the game's image name in
  the process list is observation of the game process, which a reader of
  "never touches the game process" would reasonably call touching it; the
  floor is an allowlist (Client.txt, per-press clipboard / screen, public
  web data) that does not name it; decision 0006 already refused per-game
  process telemetry even dev-only. Accurate, but no adjudicator can widen
  the floor.
- (c) Both: rejected; inherits (a).
- A verified clean-quit log line only: kept as a later refinement (then a
  firm "closed" state), not a replacement - a kill or crash writes no line.

## Why

Staleness is zero-click and needs nothing beyond the consented log tail.
False positives (AFK in a hideout) are handled by wording ("may be
closed"), full reversibility on the next line, and no data loss. 20 minutes
matches the UTIL-SESSION-SUMMARY idle close, so the two agree.

## Reverses if

GGG or the operator explicitly permits a process-presence check; AFK false
positives make the idle state useless in normal play; or a reliable quit /
crash log line is verified (it then gives a firm "closed" state).
