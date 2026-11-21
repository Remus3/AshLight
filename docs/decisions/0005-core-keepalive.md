# 0005 - Core keepalive: detached stdlib supervisor

Date: 2026-11-16. Trigger: ROADMAP row CORE-KEEPALIVE (the core died
unexplained on 2026-11-16; CORE-DETACH made the next death diagnosable).
Fork ruled by an adjudicator agent the same day; ruling recorded below.

## Decision

Option A. `python -m server.al.keepalive` (stdlib only) is started detached
(Start-AlDetached, pythonw) by `scripts/run.ps1` on every run. A
single-instance lock (`ops/runtime/keepalive.lock`) makes a second copy exit
at once. It adopts a running core through `ops/runtime/core.alive`
({pid, port, updated}) and polls every 5 s:

- core pid gone and core.alive left behind: crash, relaunch.
- core pid alive, heartbeat older than 90 s and /api/health failing: hung,
  terminate (only when the image is python), relaunch.
- no heartbeat but /api/health answers (a core from an older build): left
  alone; it is started only once nothing answers.
- core pid gone and core.alive removed (clean exit), or
  `ops/runtime/stop.request` present: user stop. Logged, not restarted, the
  supervisor exits.

User stop: `scripts/stop.ps1` writes stop.request; the core's 0.5 s main loop
sees it and exits cleanly (removes core.alive and its token). After a
timeout stop.ps1 force-stops the pid (python only); stop.request still marks
it a user stop. The core and run.ps1 remove a stale stop.request on start.

Backoff 2, 10, 30, 60, 120 s; cap 5 restarts in a rolling 15 min, then a
logged give-up (`Logs/keepalive.log`, `ops/runtime/keepalive.json` status
`gave-up`) and the supervisor exits. Worst case after a death: 5 s poll +
2 s backoff + core start, well inside the 2 min budget; a hang takes at most
90 + 5 + 2 s. Consent and tail state live in ops/runtime and the config, so
a relaunched core resumes tailing by itself.

Never touches the game process: it only reads, starts and stops AshLight's
own python core (decision 0003 floor).

## Alternatives

- B: a scheduled task polling every minute. Rejected: state between runs is
  fragile, a 1 min cadence plus start latency leaves little margin, and it
  needs a new mechanism.
- C: A plus a logon scheduled task for autostart. Rejected for now:
  autostart is a separate concern with its own opt-in; file it as its own
  row if wanted.

## Reverses if

The supervisor itself proves unreliable (single point of failure) or logon
or reboot survival is wanted (then C, or a scheduled task watching the
supervisor); or the stale-heartbeat kill gives false positives on slow
machines (then restart only on pid death).

## Amendment 2026-11-18 (RUN-SUPERVISOR-CLOCK, plan unit F-136)

The liveness verdict cannot misfire on a clock step, a sleep or one slow
answer. Every interval in `server/al/keepalive.py` (heartbeat age, start
grace, backoff, restart window, reload and snapshot pacing) runs on
`time.monotonic`; the wall clock only stamps records other processes read
(keepalive.json, last-exit.json, the code reload status, the snapshot
starter's file ages). The heartbeat age is the monotonic time since a new
heartbeat value was first seen, corrected by its wall age clamped to one
poll, so a wall step of any size moves it by at most 5 s. A stale kill now
needs two failed `/api/health` checks at least 5 s apart; a check fails when
nothing answers or the new `loop_age_s` field (seconds since the core
loop's last pass, `core.loop_at`; null before the first) is over 60. A step
more than 30 s after the one before (sleep, hibernate, a stalled machine)
opens a 60 s grace with no kill (stale or start timeout) and starts the
failed-check count over. keepalive.json records `last_restart` (wall time
and a reason code: hung, crash, start-crash, start-timeout; a first start
and a code reload are not restarts) when a relaunch happens, carried over
by a new supervisor, and `server/al/plug/supervisor.py` shows it in Checks
as a note for 10 minutes ("AshLight restarted its core at 21:14 (it had
stopped answering)."). Worst-case hang recovery: 90 + 5 + 5 + 2 = 102 s,
inside the 120 s budget.

Alternatives: keep the wall clock and clamp negative ages (a forward step
still kills a healthy core); three checks (recovery past 107 s for no
measured gain); a loop-age-only verdict without the heartbeat (an older
core reports no loop age). Reverses if: a real hang takes longer than the
budget to recover, the grace hides a real hang in play, or the loop age
misfires on a slow tick.
