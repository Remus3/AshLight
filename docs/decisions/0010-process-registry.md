# 0010 - Process registry: one of each, stop all of ours, nothing else

Date: 2026-11-16. Trigger: ROADMAP rows OPS-STOP and OPS-RUN-IDEMP
(stop.ps1 left the keepalive supervisor and the overlay running; run.ps1
-NoBrowser did not start the overlay; every run.ps1 launched another
supervisor that then exited on the single-instance lock).

## Decision

- `server/al/procs.py` (stdlib, ctypes) is the one place that decides which
  AshLight processes are live and which pids are ours:
  - core: pid in `ops/runtime/core.alive`, image `python*`, and the
    process creation time the core now records there;
  - supervisor: pid and creation time in `ops/runtime/keepalive.json`
    (written at supervisor start, status `started`); liveness from its
    single-instance lock `keepalive.lock`;
  - overlay: pid and creation time in `ops/runtime/overlay.pid` (recorded
    by run.ps1 right after it starts Electron), plus every `electron.exe`
    whose full image path is inside this checkout's
    `app/node_modules/electron/dist` (catches the renderer / utility
    children and an overlay started before pids were recorded). The scan is
    off for a tmp runtime (AL_RUNTIME_DIR) unless AL_ELECTRON_DIR names the
    dir, so a test can never reach a live overlay.
- `scripts/stop.ps1`: stop.request and the core as before (decision 0005),
  then `python -m server.al.procs stop`: waits for the supervisor to exit
  on stop.request, forces it only after the timeout, terminates the
  overlay processes, removes overlay.pid; exit 1 if anything is left.
- The supervisor now checks stop.request before a pending restart (a stop
  during the backoff used to launch a core that cleared stop.request).
- `scripts/run.ps1` asks `procs plan` and starts each of core, supervisor
  and overlay only when it is not live. The overlay is part of the full
  running set: it starts whenever it is installed, independent of
  -NoBrowser; `-NoOverlay` opts out; `-Overlay` is accepted and does
  nothing extra (compatibility).
- Termination re-checks the image name at kill time; a pid is never killed
  on its name alone, and the game client can never match (wrong image, not
  under the repo, no recorded creation time).

## Alternatives

- Kill by image name (`taskkill /IM electron.exe`, all pythonw): rejected,
  hits unrelated Electron apps and other python tools.
- Match command lines through WMI (Win32_Process.CommandLine): workable from
  PowerShell, but slow (about 1 s per query), not testable in stdlib Python,
  and a command line is weaker than pid + creation time.
- A stop endpoint on the core that also stops the overlay: the overlay has
  no control channel and must not grow one only for this; the supervisor
  already exits on stop.request.
- Keep the overlay opt-in (-Overlay): rejected by the ROADMAP ZERO-CLICK
  line "any run.ps1 call converges to the full running set"; a user who
  does not want it says -NoOverlay once.

## Why

pid + creation time names exactly one process, so a reused pid is never
mistaken for ours; an image path inside the repo is ours alone. The
decision logic is plain Python with unit tests (plan convergence over
repeated runs) and an end-to-end test that runs the real stop.ps1 against a
real supervisor, core and fake overlay on a tmp runtime
(`tests/test_procs.py`).

## Reverses if

The overlay gains a clean-exit channel (then stop asks instead of
terminating), Electron moves out of app/node_modules (then the scan path
moves with it), or the operator wants the overlay opt-in again.
