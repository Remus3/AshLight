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
