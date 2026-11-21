"""RUN-SECOND-LINE-PY (finding F-127, decision 0005 amendment 2026-11-18):
the core starts a missing keepalive supervisor, through the plug seam
(decision 0056).

The supervisor restarts a dead core; nothing restarted a dead supervisor.
Now the core checks once per Checks tick (Core.DIAG_TICK_S, 5 s) whether a
supervisor watches its runtime dir (procs.supervisor_live: the recorded
pid proven by pid and creation time, else the single-instance lock). After
MISSING_TICKS ticks in a row with none, it starts one
(procs.start_supervisor: hidden, detached, the one command builder):

- never while stop.request exists (scripts/stop.ps1 is stopping AshLight;
  the core exits on it too),
- at most once per EVERY_S (5 minutes, monotonic clock), however it ends,
- only in the real core (no runtime dir given and no AL_RUNTIME_DIR): a
  test or demo core never starts a process.

A start shows a Checks note for SHOW_S:

    Keepalive was not running; AshLight started it again.

It starts only AshLight's own python supervisor (never Electron, decision
0041; never the game). No request, nothing sent; no new watchdog process.
"""

import logging
import os
import time

from .. import keepalive, paths, procs

ORDER = 100

log = logging.getLogger("al.secondline")

ROW_ID = "supervisor_started"
LABEL = "Keepalive"
TEXT = "Keepalive was not running; AshLight started it again."
MISSING_TICKS = 3     # Checks ticks in a row with no live supervisor
EVERY_S = 300.0       # at most one start per 5 minutes
TICK_S = 5.0          # the Checks tick (Core.DIAG_TICK_S)
SHOW_S = 600.0        # the note shows for 10 minutes after a start
FUTURE_S = 60.0       # a start this far ahead of the clock (a clock step) hides


class SecondLine:
    """One core's supervisor check; tick() runs from the core loop and
    does its work at most once per tick_s."""

    def __init__(self, runtime, port, live=None, start=None, now=time.monotonic,
                 wall=time.time, tick_s=TICK_S, missing_ticks=MISSING_TICKS,
                 every_s=EVERY_S):
        self.runtime = runtime
        self._port = port            # callable: the served port at start time
        self._live = live or (lambda: procs.supervisor_live(self.runtime))
        self._start = start or (lambda p: procs.start_supervisor(p))
        self._now = now
        self._wall = wall
        self.tick_s = float(tick_s)
        self.missing_ticks = int(missing_ticks)
        self.every_s = float(every_s)
        self.missing = 0
        self._next = None            # monotonic time of the next check
        self._started_mono = None    # monotonic time of the last start
        self.started_at = None       # wall time of the last start (Checks)
        self.child = None

    def tick(self):
        """One check when due: None (not due), "stop", "live", "missing",
        "capped", "started" or "failed"."""
        now = self._now()
        if self._next is not None and now < self._next:
            return None
        self._next = now + self.tick_s
        if self.child is not None:
            self.child.poll()  # reap a supervisor that exited
        if (self.runtime / keepalive.STOP_FILE).exists():
            self.missing = 0
            return "stop"
        if self._live():
            self.missing = 0
            return "live"
        self.missing += 1
        if self.missing < self.missing_ticks:
            return "missing"
        last = self._started_mono
        if last is not None and 0 <= now - last < self.every_s:
            return "capped"
        self._started_mono = now
        self.missing = 0
        try:
            self.child = self._start(int(self._port()))
        except (OSError, ValueError) as exc:
            log.warning("keepalive supervisor was not running and did not start "
                        "(%s)", type(exc).__name__)
            return "failed"
        self.started_at = self._wall()
        pid = getattr(self.child, "pid", None)
        log.warning("keepalive supervisor was not running; started it again (pid %s)",
                    pid)
        return "started"


def enabled(core, environ=None):
    """Only the real core starts a supervisor: no runtime dir given (a test
    or demo core has one) and no AL_RUNTIME_DIR (an isolated instance)."""
    env = os.environ if environ is None else environ
    return bool(getattr(core, "_real", False)) and not (
        env.get(paths.RUNTIME_ENV) or "").strip()


def attach(core):
    if not enabled(core):
        return
    tick_s = getattr(core, "DIAG_TICK_S", TICK_S)
    line = SecondLine(core.runtime, lambda: core.port, tick_s=tick_s)
    core._second_line = line
    core.add_tick("tick_second_line", line.tick)


def facts(core, now):
    line = getattr(core, "_second_line", None)
    return {"supervisor_started": line.started_at if line is not None else None}


def rows(f, now):
    at = f.get("supervisor_started")
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    if not -FUTURE_S <= now - at < SHOW_S:
        return None
    return {"id": ROW_ID, "label": LABEL, "status": "note", "detail": TEXT}
