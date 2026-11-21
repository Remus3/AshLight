"""CORE-KEEPALIVE: a tiny stdlib supervisor for the AshLight core.

    python -m server.al.keepalive [--port N] [--runtime DIR] [--poll S]
        [--stale S] [--backoff 2,10,30] [--cap N] [--window S]
        [--core-args ARG ...]

scripts/run.ps1 starts it detached (Start-AlDetached, pythonw) on every run;
a second copy exits at once (single-instance lock in the runtime dir). It
adopts a core that is already running (pid from <runtime>/core.alive) and
polls every POLL_S seconds:

- core pid gone, core.alive left behind -> crash -> relaunch after backoff
- core pid alive, heartbeat older than STALE_S and two /api/health checks
  failing RECHECK_S apart (a loop_age_s over LOOP_STALE_S fails a check) ->
  hung -> terminate (only when the image is python) -> relaunch; never
  inside the GAP_GRACE_S after a poll gap (sleep or a stalled machine)
- core pid gone and core.alive removed (clean exit) or stop.request present
  (scripts/stop.ps1) -> user stop -> log it and exit; never restarted
- no heartbeat but /api/health answers (a core from an older build) ->
  left alone; started only once nothing answers
- more than CAP restarts inside WINDOW_S -> logged give-up and exit

Every interval runs on the monotonic clock (RUN-SUPERVISOR-CLOCK); the
wall clock only stamps keepalive.json, whose last_restart (time and reason)
plug/supervisor.py shows in Checks for 10 minutes.

It only ever looks at, starts or stops AshLight's own python core; it never
touches the game process (ToS floor). Decision: docs/decisions/0005.

DATA-SNAP-AT-START (decisions 0009 / 0013, amendments 2026-11-18): at most
once per SNAPSHOT_EVERY_S the injected `snapshot` callable (snapstart.Starter
from main()) starts the game-data snapshot tool as its own hidden,
below-normal process when web data is on and the cache is missing or over
24 h old. This module never fetches and never imports the tool.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import exitrecord, hello, hotreload, jsonfile, logs, paths, ports, prio, snapstart

POLL_S = 5.0
STALE_S = 90.0          # three missed 30 s heartbeats
START_GRACE_S = 60.0    # a fresh core must write its first heartbeat by then
# RUN-SUPERVISOR-CLOCK (F-136, decision 0005 amendment 2026-11-18): every
# interval is measured on the monotonic clock. A stale kill needs two failed
# health checks at least RECHECK_S apart; a check fails when nothing answers
# or the core's loop is older than LOOP_STALE_S (/api/health loop_age_s). A
# step more than POLL_GAP_S after the one before (sleep, hibernate, a stalled
# machine) opens GAP_GRACE_S with no kill.
RECHECK_S = 5.0
LOOP_STALE_S = 60.0
POLL_GAP_S = 30.0
GAP_GRACE_S = 60.0
HEALTH_MAX_BYTES = 64 * 1024
# last_restart reason codes in keepalive.json (plug/supervisor.py words them)
RESTART_REASONS = ("hung", "crash", "start-crash", "start-timeout")
BACKOFF_S = (2.0, 10.0, 30.0, 60.0, 120.0)
CAP = 5                 # restarts allowed inside WINDOW_S
WINDOW_S = 900.0
HEARTBEAT_FILE = "core.alive"
STOP_FILE = "stop.request"
STATE_FILE = "keepalive.json"
LOCK_FILE = "keepalive.lock"
# HOT-RELOAD (decision 0042), source checkout only
DEV_POLL_S = 1.0           # poll cadence while code reload is on (stat only)
RELOAD_DEBOUNCE_S = 1.5    # a burst of saves settles before the preflight
RELOAD_EXIT_S = 20.0       # the old core's clean exit, then it is terminated
PREFLIGHT_TIMEOUT_S = 60.0
# DATA-SNAP-AT-START: the snapshot check runs at most once per normal poll,
# also while the dev poll is faster (it reads two small local files)
SNAPSHOT_EVERY_S = POLL_S
RELOAD_DEAD_NOTE = ("A code change passed the check, but the new version did not "
                    "start. AshLight tries again after your next save.")

_STILL_ACTIVE = 259
_QUERY_LIMITED = 0x1000
_TERMINATE = 0x0001


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD))
    k.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    return ctypes, wintypes, k


def pid_alive(pid):
    """True while process pid runs. No signal is sent (os.kill with signal 0
    terminates the target on Windows)."""
    pid = int(pid or 0)
    if pid <= 0:
        return False
    if os.name != "nt":
        return Path(f"/proc/{pid}").exists()
    ctypes, wintypes, k = _kernel32()
    h = k.OpenProcess(_QUERY_LIMITED, False, pid)
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == _STILL_ACTIVE
    finally:
        k.CloseHandle(h)


def image_path(pid):
    """Full path of the executable of pid ('' when unknown)."""
    if os.name != "nt" or int(pid or 0) <= 0:
        return ""
    ctypes, wintypes, k = _kernel32()
    h = k.OpenProcess(_QUERY_LIMITED, False, int(pid))
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value
    finally:
        k.CloseHandle(h)


def image_name(pid):
    """Base name of the executable of pid ('' when unknown)."""
    value = image_path(pid)
    return Path(value).name if value else ""


def process_created(pid):
    """Creation time of pid as a FILETIME integer (0 when unknown). A pid
    plus its creation time names one process; a reused pid differs."""
    if os.name != "nt" or int(pid or 0) <= 0:
        return 0
    ctypes, wintypes, k = _kernel32()
    k.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    h = k.OpenProcess(_QUERY_LIMITED, False, int(pid))
    if not h:
        return 0
    try:
        t = [wintypes.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(h, *(ctypes.byref(x) for x in t)):
            return 0
        return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
    finally:
        k.CloseHandle(h)


def terminate_core(pid):
    """Terminate pid only when it is a python process (our core)."""
    if os.name != "nt" or not image_name(pid).lower().startswith("python"):
        return False
    ctypes, wintypes, k = _kernel32()
    h = k.OpenProcess(_TERMINATE | _QUERY_LIMITED, False, int(pid))
    if not h:
        return False
    try:
        return bool(k.TerminateProcess(h, 1))
    finally:
        k.CloseHandle(h)


def read_heartbeat(path):
    try:
        data = json.loads(Path(path).read_text(encoding="ascii"))
        return {"pid": int(data["pid"]), "port": int(data.get("port", 0)),
                "updated": float(data["updated"]),
                "created": int(data.get("created") or 0)}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def acquire_lock(runtime):
    """Hold <runtime>/keepalive.lock for this process; None when another
    supervisor holds it. The OS drops the lock when the holder dies."""
    runtime = Path(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    fh = open(runtime / LOCK_FILE, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def release_lock(fh):
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    fh.close()


# Loopback only: an empty ProxyHandler ignores http_proxy and the system proxy,
# so the token never reaches a proxy and a healthy core is never judged hung.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _loop_age(body):
    """loop_age_s from an /api/health body; None when absent (an older
    core, or a core whose loop has not run yet) or unreadable."""
    try:
        value = json.loads(body.decode("utf-8")).get("loop_age_s")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def health_check(runtime, port, timeout=3.0, detail=False):
    """True when the core answers /api/health with the current token.
    detail=True: {"ok": bool, "loop_age_s": float or None} instead
    (RUN-SUPERVISOR-CLOCK: the supervisor also judges the loop age).

    SEC-HELLO-CORE (decision 0054): the listener first proves it is the
    core (hello.verify, once per token value); the token is sent only after
    that. Any request error clears the verification, so the next check
    proves the listener again."""
    def out(ok, age=None):
        return {"ok": ok, "loop_age_s": age} if detail else ok
    try:
        token = (Path(runtime) / "token").read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return out(False)
    if not hello.verify(port, token, opener=_NO_PROXY_OPENER, timeout=timeout):
        return out(False)
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}/api/health",
                                 headers={"X-AL-Token": token})
    try:
        with _NO_PROXY_OPENER.open(req, timeout=timeout) as r:
            if r.status == 200:
                return out(True, _loop_age(r.read(HEALTH_MAX_BYTES)) if detail else None)
    except (OSError, ValueError):
        pass
    hello.forget(port)
    return out(False)


def read_last_restart(path):
    """last_restart of a keepalive.json ({"at": wall time, "reason": a
    RESTART_REASONS code}), or None when absent or malformed."""
    try:
        doc = json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None
    rec = doc.get("last_restart") if isinstance(doc, dict) else None
    if not isinstance(rec, dict) or rec.get("reason") not in RESTART_REASONS:
        return None
    at = rec.get("at")
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    return {"at": float(at), "reason": rec["reason"]}


def answered(result):
    """The core answered /api/health (a bool or a health_check detail)."""
    if isinstance(result, dict):
        return bool(result.get("ok"))
    return bool(result)


def check_passed(result, loop_stale_s=LOOP_STALE_S):
    """One stale-heartbeat health check passed: the core answered and its
    loop is not older than loop_stale_s (no loop age reads as passed: an
    older core)."""
    if not answered(result):
        return False
    age = result.get("loop_age_s") if isinstance(result, dict) else None
    return age is None or age <= loop_stale_s


class Keepalive:
    """The supervisor state machine; step() is one poll."""

    def __init__(self, runtime, port, launch, pid_alive=pid_alive, health=None,
                 terminate=terminate_core, now=time.monotonic, log=None, created=None,
                 stale_s=STALE_S, start_grace_s=START_GRACE_S, backoff=BACKOFF_S,
                 cap=CAP, window_s=WINDOW_S, code_watch=None, preflight=None,
                 reload_debounce_s=RELOAD_DEBOUNCE_S, reload_exit_s=RELOAD_EXIT_S,
                 snapshot=None, snapshot_every_s=SNAPSHOT_EVERY_S, wall=time.time,
                 recheck_s=RECHECK_S, loop_stale_s=LOOP_STALE_S,
                 poll_gap_s=POLL_GAP_S, gap_grace_s=GAP_GRACE_S, poll_s=POLL_S):
        # RUN-SUPERVISOR-CLOCK (F-136): `now` is the monotonic clock every
        # interval uses; `wall` only stamps records other processes read
        # (keepalive.json, last-exit.json, the code reload status, the
        # snapshot starter's file ages) and corrects a fresh heartbeat's
        # sighting by at most one poll.
        self._wall = wall
        self.recheck_s = float(recheck_s)
        self.loop_stale_s = float(loop_stale_s)
        self.poll_gap_s = float(poll_gap_s)
        self.gap_grace_s = float(gap_grace_s)
        self.poll_s = float(poll_s)
        self._beat_key = None      # (pid, created, updated) last seen
        self._beat_at = None       # monotonic time that heartbeat was written
        self._failed_at = None     # monotonic time of the first failed check
        self._last_step = None
        self.grace_until = None    # no kill before this monotonic time
        self._restart_reason = None
        self.last_restart = None   # {"at": wall time, "reason": code}
        # DATA-SNAP-AT-START: snapshot(now) -> pid or None starts the
        # game-data snapshot tool when it is due. None: never (tests).
        self._snapshot = snapshot
        self.snapshot_every_s = float(snapshot_every_s)
        self._snapshot_at = None
        # HOT-RELOAD (decision 0042): code_watch has signature() (the
        # server/ *.py stat set); preflight() -> (ok, error line). None:
        # no code reload (tests, and outside a source checkout).
        self._code_watch = code_watch
        self._preflight = preflight or (lambda: (True, None))
        self.reload_debounce_s = float(reload_debounce_s)
        self.reload_exit_s = float(reload_exit_s)
        self._code_sig = None
        self._code_changed_at = None
        self.reloading_since = None   # restart.request written, old core exiting
        self.hot_launch = False       # the running launch is a code reload
        self.blocked = False          # new code failed to start; wait for an edit
        if code_watch is not None:
            self._code_sig = code_watch.signature()  # changes from here on count
        self.runtime = Path(runtime)
        self.port = int(port)
        self._launch = launch
        self._alive = pid_alive
        self._health = health or (lambda: health_check(self.runtime, self.port, detail=True))
        self._terminate = terminate
        self._created_of = created or process_created
        self._now = now
        self._log = log or (lambda line: None)
        self.stale_s = float(stale_s)
        self.start_grace_s = float(start_grace_s)
        self.backoff = tuple(float(x) for x in backoff) or BACKOFF_S
        self.cap = int(cap)
        self.window_s = float(window_s)
        self.pid = None
        self.seen_beat = False
        self.launched_at = None
        self.next_launch = None
        self.restarts = []
        self._created = process_created(os.getpid())
        # the last restart survives a supervisor restart (run.ps1 re-run)
        self.last_restart = read_last_restart(self.runtime / STATE_FILE)

    def _write_state(self, status):
        data = {"pid": os.getpid(), "created": self._created, "status": status,
                "core_pid": self.pid,
                "restarts": len(self.restarts), "port": self.port,
                "updated": self._wall(), "last_restart": self.last_restart}
        try:
            jsonfile.write_text(self.runtime / STATE_FILE, json.dumps(data) + "\n")
        except OSError:
            pass

    def _beat_age(self, hb, now):
        """Seconds since the heartbeat was written, on the monotonic clock:
        the time a new heartbeat value was first seen, minus its wall age
        clamped to one poll (a wall clock step moves it by at most that)."""
        key = (hb["pid"], hb.get("created") or 0, hb["updated"])
        if key != self._beat_key:
            lag = min(max(self._wall() - hb["updated"], 0.0), self.poll_s)
            self._beat_key = key
            self._beat_at = now - lag
            self._failed_at = None
        return now - self._beat_at

    def _no_kill(self, now):
        return self.grace_until is not None and now < self.grace_until

    def _gap_step(self, now):
        """A step long after the previous one (the machine slept or
        stalled): the core may not have had time to beat; no kill for
        gap_grace_s and the failed-check count starts over."""
        last, self._last_step = self._last_step, now
        if last is None or now - last <= self.poll_gap_s:
            return
        self.grace_until = now + self.gap_grace_s
        self._failed_at = None
        self._log(f"poll gap of {now - last:.0f} s; no kill for "
                  f"{self.gap_grace_s:g} s")

    def step(self):
        now = self._now()
        self._gap_step(now)
        self._snapshot_step(now)
        hb = read_heartbeat(self.runtime / HEARTBEAT_FILE)
        live = bool(hb) and self._alive(hb["pid"]) and self._same_process(hb)
        if not live:
            # SEC-HELLO-CORE: the core that proved itself is gone, so the
            # listener on the port is proven again before it gets the token
            hello.forget(self.port)
        if live:
            if hb["pid"] != self.pid:
                self.pid = hb["pid"]
                self._log(f"watching core pid {self.pid} on port {hb['port']}")
                self._write_state("watching")
            self.seen_beat = True
            self.launched_at = None
            self.hot_launch = False
            self.blocked = False
            age = self._beat_age(hb, now)
            if age <= self.stale_s:
                self._failed_at = None
            elif not self._no_kill(now):
                verdict = self._stale_verdict(now)
                if verdict == "hung":
                    ok = self._terminate(hb["pid"])
                    if ok:  # OBS-CRASH: the killed core cannot write its own record
                        exitrecord.write(self.runtime, exitrecord.SUPERVISOR_KILL,
                                         f"heartbeat {age:.0f} s old",
                                         now=self._wall(), pid=hb["pid"])
                    return self._crashed(now, f"core hung (pid {hb['pid']}, heartbeat "
                                         f"{age:.0f} s old, two failed checks, "
                                         f"terminated={bool(ok)})", code="hung")
                if verdict == "checking":
                    return "checking"
            if self.reloading_since is not None:
                if now - self.reloading_since > self.reload_exit_s:
                    ok = self._terminate(hb["pid"])
                    self._log(f"core did not exit for the code reload in "
                              f"{self.reload_exit_s:g} s (terminated={bool(ok)})")
                    self.reloading_since = now  # one terminate per window
                return "reloading"
            return self._code_step(now) or "ok"
        if self.launched_at is not None and self.pid and self._alive(self.pid):
            if (now - self.launched_at > self.start_grace_s and not self._no_kill(now)
                    and not answered(self._health())):
                ok = self._terminate(self.pid)
                return self._crashed(now, f"core start timed out (pid {self.pid}, "
                                     f"terminated={bool(ok)})", code="start-timeout")
            return "starting"
        if answered(self._health()):
            # a core answers but writes no heartbeat (an older build): leave it
            if self.next_launch is not None:
                self.next_launch = None
                self._log("a core answers /api/health; restart cancelled")
            return "ok"
        if (self.runtime / STOP_FILE).exists():
            # checked before a pending restart: a stop during the backoff wins
            # (a relaunched core would clear stop.request on start)
            self.next_launch = None
            self._log("user stop (stop.request); not restarting; supervisor exits")
            self._write_state("user-stop")
            return "user-stop"
        if self.reloading_since is not None:
            # HOT-RELOAD: the old core left for the code reload; the new
            # code starts at once (no backoff, not a crash restart)
            self.reloading_since = None
            self.pid = None
            self.seen_beat = False
            self._log("core exited for a code reload; starting the new code")
            return self._launch_core(now, hot=True)
        if self.blocked:
            if self._code_due(now) != "ready":
                return "reload-blocked"
            ok, err = self._preflight()
            if not ok:
                self._reload_refused(err)
                return "reload-blocked"
            self.blocked = False
            hotreload.write_status(self.runtime, None, now=self._wall())
            self._log("code changed again and passed the check; starting it")
            return self._launch_core(now, hot=True)
        if self.next_launch is not None:
            if now >= self.next_launch:
                return self._launch_core(now)
            return "waiting"
        if hb is None and self.seen_beat:
            self._log("user stop (core exited cleanly); not restarting; supervisor exits")
            self._write_state("user-stop")
            return "user-stop"
        code = None  # "no core running" is a first start, not a restart
        if self.launched_at is not None:
            reason = f"core crash before first heartbeat (pid {self.pid})"
            code = "start-crash"
        elif hb is not None:
            reason = f"core crash (pid {hb['pid']} gone, heartbeat left behind)"
            code = "crash"
        else:
            reason = "no core running"
        return self._crashed(now, reason, code=code)

    def _stale_verdict(self, now):
        """With a stale heartbeat: "ok" (a check passed), "checking" (the
        first failed check, or the second came too soon) or "hung" (a
        second failed check at least recheck_s after the first)."""
        if check_passed(self._health(), self.loop_stale_s):
            self._failed_at = None
            return "ok"
        if self._failed_at is None:
            self._failed_at = now
            self._log("heartbeat stale and the health check failed; checking again")
            return "checking"
        if now - self._failed_at < self.recheck_s:
            return "checking"
        self._failed_at = None
        return "hung"

    def _snapshot_step(self, now):
        """DATA-SNAP-AT-START: one rate-limited call of the snapshot starter;
        never while a user stop is pending, never fatal to the supervisor."""
        if self._snapshot is None:
            return
        last = self._snapshot_at
        if last is not None and 0 <= now - last < self.snapshot_every_s:
            return
        self._snapshot_at = now
        if (self.runtime / STOP_FILE).exists():
            return
        try:
            pid = self._snapshot(self._wall())  # file ages are wall times
        except Exception as exc:  # noqa: BLE001 - the core watch goes on
            self._log(f"game data snapshot did not start ({type(exc).__name__})")
            return
        if pid:
            self._log(f"game data snapshot started (pid {pid}, hidden, below normal)")

    def _same_process(self, hb):
        """SUP-1: the heartbeat's pid is still the core that wrote it. A
        dead core's pid can be reused by any process; the recorded creation
        time tells them apart (a heartbeat without one keeps the pid rule).
        A reused pid reads as a crash: never terminated, core relaunched."""
        want = hb.get("created") or 0
        if not want:
            return True
        got = self._created_of(hb["pid"])
        return not got or got == want

    def _crashed(self, now, reason, code=None):
        self.restarts = [t for t in self.restarts if now - t < self.window_s]
        self.pid = None
        self.seen_beat = False
        self.launched_at = None
        self._failed_at = None
        self._restart_reason = code  # recorded when the relaunch happens
        if self.hot_launch and self._code_watch is not None:
            # HOT-RELOAD: the new code died before its first heartbeat.
            # Never a crash loop: nothing starts until the code changes
            # again and passes the check.
            self.hot_launch = False
            self.blocked = True
            self.next_launch = None
            self._log(f"{reason}; the new code did not start; waiting for the "
                      f"next code change")
            hotreload.write_status(self.runtime, RELOAD_DEAD_NOTE, now=self._wall())
            self._write_state("reload-blocked")
            return "reload-blocked"
        if len(self.restarts) >= self.cap:
            self._log(f"{reason}; give up: {len(self.restarts)} restarts in "
                      f"{self.window_s:.0f} s; supervisor exits")
            self._write_state("gave-up")
            return "gave-up"
        delay = self.backoff[min(len(self.restarts), len(self.backoff) - 1)]
        self.next_launch = now + delay
        self._log(f"{reason}; restart {len(self.restarts) + 1}/{self.cap} "
                  f"in {delay:g} s")
        self._write_state("restarting")
        return "waiting"

    # -- HOT-RELOAD (decision 0042)

    def _code_due(self, now):
        """None (no change), "pending" (settling) or "ready" (debounced)."""
        if self._code_watch is None:
            return None
        sig = self._code_watch.signature()
        if self._code_sig is None:
            self._code_sig = sig
            return None
        if sig != self._code_sig:
            self._code_sig = sig
            self._code_changed_at = now
            return "pending"
        if self._code_changed_at is None:
            return None
        if now - self._code_changed_at < self.reload_debounce_s:
            return "pending"
        self._code_changed_at = None
        return "ready"

    def _code_step(self, now):
        """With a healthy core: a settled server/ .py change that passes
        the preflight asks the core to exit (restart.request); one that
        fails it keeps the running core and publishes the error."""
        due = self._code_due(now)
        if due is None:
            return None
        if due == "pending":
            return "reload-pending"
        ok, err = self._preflight()
        if not ok:
            self._reload_refused(err)
            return "reload-refused"
        hotreload.write_status(self.runtime, None, now=self._wall())
        try:
            jsonfile.write_text(self.runtime / hotreload.RESTART_FILE, "reload\n")
        except OSError as exc:
            self._log(f"code reload: cannot ask the core to exit ({exc})")
            return "ok"
        self.reloading_since = now
        self._log("code changed and passed the check; asking the core to restart")
        self._write_state("reloading")
        return "reloading"

    def _reload_refused(self, err):
        where = f" ({err})" if err else ""
        note = f"A code change did not load{where}. The running version stays in use."[:300]
        self._log(f"code reload refused: {err}")
        hotreload.write_status(self.runtime, note, now=self._wall())

    def _launch_core(self, now, hot=False):
        self.next_launch = None
        self.hot_launch = bool(hot)
        if not hot:
            self.restarts.append(now)  # a code reload is not a crash restart
        try:
            self.pid = int(self._launch())
        except OSError as exc:
            self.pid = None
            self.launched_at = now
            self._log(f"core launch failed: {exc}")
            return "launched"
        self.launched_at = now
        if not hot and self._restart_reason in RESTART_REASONS:
            # RUN-SUPERVISOR-CLOCK: Checks shows it for 10 minutes
            self.last_restart = {"at": round(self._wall(), 3),
                                 "reason": self._restart_reason}
        self._restart_reason = None
        self._log(f"core launched (pid {self.pid})")
        self._write_state("starting")
        return "launched"

    def run(self, poll_s=POLL_S, sleep=time.sleep):
        while True:
            result = self.step()
            if result in ("user-stop", "gave-up"):
                return result
            sleep(poll_s)


def core_command(port, extra=()):
    """The windowless core start, through the one command builder (DEP-06):
    `-m server.al` in a checkout, `boot.py server.al` in an install."""
    return paths.python_cmd("server.al", "--quiet", "--port", str(int(port)),
                            *extra, windowless=True)


_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')


def preflight_error(text, root):
    """One line from the --check output or an import traceback: the last
    "File ..., line N" (repo-relative) and the last line; no absolute path."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return "the code check failed"
    last = lines[-1]
    where = ""
    for ln in reversed(lines[:-1]):
        m = _FILE_LINE.search(ln)
        if m:
            try:
                rel = Path(m.group(1)).resolve().relative_to(Path(root).resolve()).as_posix()
            except (ValueError, OSError):
                rel = Path(m.group(1)).name
            where = f"{rel}:{m.group(2)}: "
            break
    out = where + last
    out = out.replace(str(root), "").replace(str(root).replace("\\", "/"), "")
    return " ".join(out.split())[:200]


def run_preflight(root=None, timeout=PREFLIGHT_TIMEOUT_S, run=subprocess.run):
    """HOT-RELOAD: (True, None) when `python -m server.al --check` loads the
    changed code, else (False, one-line error). It runs in a child process,
    so the running core and this supervisor never import the new code."""
    root = Path(root) if root else paths.repo_root()
    # pipes need a console-subsystem python; the one command builder (DEP-06)
    cmd = paths.python_cmd("server.al", "--check", windowless=False, root=root)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    flags = prio.below_normal(flags)  # RUN-CALC-PRIORITY (F-107): a batch child
    try:
        r = run(cmd, cwd=str(root),
                stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                creationflags=flags)
    except subprocess.TimeoutExpired:
        return False, "the code check timed out"
    except OSError as exc:
        return False, f"the code check did not run ({type(exc).__name__})"
    if r.returncode == 0:
        return True, None
    text = (r.stdout or b"").decode("utf-8", "replace") + "\n" + \
        (r.stderr or b"").decode("utf-8", "replace")
    return False, preflight_error(text, root)


class _Launcher:
    def __init__(self, cmd):
        self.cmd = cmd
        self.child = None

    def __call__(self):
        if self.child is not None:
            self.child.poll()  # reap the previous core
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        self.child = subprocess.Popen(self.cmd, cwd=str(paths.repo_root()),
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, close_fds=True,
                                      creationflags=flags)
        return self.child.pid


_WARN_WORDS = ("failed", "refused", "give up", "did not", "timed out", "cannot",
               "hung", "killed")


def _file_logger(path):
    """RUN-OBS-LOGS-PY (F-090): keepalive.log rotates at start when over
    1 MB (one old file kept) and opens this start with the build banner;
    each line is the one format of server/al/logs.py (UTC ISO stamp, a
    level word, keepalive[pid], no absolute path). A line that reports a
    failure reads WARNING, the rest INFO."""
    logs.start_file(path, "keepalive", "keepalive")

    def log(line):
        level = "WARNING" if any(w in str(line) for w in _WARN_WORDS) else "INFO"
        text = logs.format_line("keepalive", level, line) + "\n"
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="ascii", errors="replace", newline="\n") as fh:
                fh.write(text)
        except OSError:
            pass
    return log


def build_parser():
    p = argparse.ArgumentParser(prog="python -m server.al.keepalive",
                                description="restart the AshLight core when it dies")
    p.add_argument("--port", type=int, default=None,
                   help="core port (default: ports.resolve, as the core)")
    p.add_argument("--runtime", help="runtime dir (default: the core's)")
    p.add_argument("--poll", type=float, default=POLL_S)
    p.add_argument("--stale", type=float, default=STALE_S)
    p.add_argument("--backoff", default=",".join(f"{x:g}" for x in BACKOFF_S))
    p.add_argument("--cap", type=int, default=CAP)
    p.add_argument("--window", type=float, default=WINDOW_S)
    p.add_argument("--core-args", nargs=argparse.REMAINDER, default=[],
                   help="extra arguments for the core (must be last)")
    return p


def snapshot_starter(runtime, runtime_arg=None, environ=None):
    """DATA-SNAP-AT-START: the snapshot starter for the live runtime dir.
    A supervisor given its runtime dir (--runtime or AL_RUNTIME_DIR: tests
    and other isolated instances) gets None and never starts a fetch, as a
    core given a runtime dir never scans (decision 0003 amendment)."""
    env = os.environ if environ is None else environ
    if runtime_arg or (env.get(paths.RUNTIME_ENV) or "").strip():
        return None
    return snapstart.Starter(runtime, pid_alive, created=process_created)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.port is None:
        args.port = ports.resolve(os.environ, paths.load_local_config())
    runtime = Path(args.runtime) if args.runtime else paths.runtime_dir()
    log = _file_logger(paths.all_runtime_paths()["keepalive_log"])
    lock = acquire_lock(runtime)
    if lock is None:
        return 0  # another supervisor is already watching this runtime dir
    try:
        backoff = tuple(float(x) for x in args.backoff.split(",") if x.strip())
        # HOT-RELOAD (decision 0042): server/ *.py edits restart the core,
        # in a source checkout only; a stale code note from an earlier run
        # is cleared either way
        hotreload.write_status(runtime, None)
        code_watch = None
        poll = args.poll
        if hotreload.dev_enabled(paths.load_local_config()):
            code_watch = hotreload.TreeWatch([paths.repo_root() / "server"],
                                             suffixes=(".py",), every_s=0.0)
            poll = min(poll, DEV_POLL_S)
        sup = Keepalive(runtime, args.port, _Launcher(core_command(args.port, args.core_args)),
                        log=log, stale_s=args.stale, backoff=backoff, cap=args.cap,
                        window_s=args.window, code_watch=code_watch, poll_s=poll,
                        preflight=run_preflight if code_watch is not None else None,
                        snapshot=snapshot_starter(runtime, args.runtime))
        sup._write_state("started")  # records this supervisor's pid for stop.ps1
        log(f"supervisor started (port {args.port}, poll {poll:g} s, code reload "
            f"{'on' if code_watch is not None else 'off'})")
        result = sup.run(poll_s=poll)
        return 0 if result == "user-stop" else 3
    except Exception as exc:  # noqa: BLE001 - last-resort record, pythonw has no stderr
        log(f"supervisor failed: {exc!r}")
        raise
    finally:
        release_lock(lock)


if __name__ == "__main__":
    sys.exit(main())
