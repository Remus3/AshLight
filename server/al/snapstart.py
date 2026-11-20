"""DATA-SNAP-AT-START (finding F-072, ruling Q-04; decisions 0009 and 0013,
amendments 2026-11-18): game data arrives at start.

The keepalive supervisor calls tick() at most once per supervisor poll.
With web data on and the game-data cache missing or older than 24 h it
starts the existing snapshot tool (python -m server.al.theorycraft.snapshot)
as its own hidden, below-normal-priority process, one at a time and at most
once per 24 h (a pid file under the runtime dir). The tool keeps every rule
it has: it reads the same web_data opt-in itself, sends the AshLight
User-Agent (with the contact for GGG's export), honours AL_NO_SNAPSHOT and
makes no request for a file checked within its own 24 h gate.

This module never imports theorycraft.snapshot and never fetches: the core
(__main__ imports keepalive) stays free of network code for game data
(tests/test_tc_snap.py::test_core_never_imports_snapshot,
tests/test_snap_start.py::test_snapstart_never_imports_snapshot). due()
reads only the local config and the cache manifest. The started tool's
output goes to <sidecar>/Logs/snapshot.log, never next to the repo.
"""

import calendar
import json
import os
import subprocess
import time
from pathlib import Path

from . import jsonfile, paths
from .theorycraft import datacredit

MODULE = "server.al.theorycraft.snapshot"
MAX_AGE_S = 24 * 3600     # the snapshot tool's own MIN_AGE_S (one check a day)
PID_FILE = "snapshot.pid"  # under the runtime dir: {"pid", "created", "started_at"}
LOG_NAME = "snapshot.log"  # under the sidecar Logs dir
LOG_CAP = 256 * 1024       # a bigger log starts over (one short run a day)
OPT_OUT_ENV = "AL_NO_SNAPSHOT"  # the snapshot tool's own opt-out, honoured here too
BELOW_NORMAL = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
NO_WINDOW = 0x08000000     # CREATE_NO_WINDOW
DETACHED = 0x00000008      # DETACHED_PROCESS
NEW_GROUP = 0x00000200     # CREATE_NEW_PROCESS_GROUP


def _parse_utc(text):
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def web_data_on(config):
    """The one opt-in of decision 0013, read strictly as the core does."""
    return isinstance(config, dict) and config.get("web_data") is True


def checked_at(manifest_path):
    """The oldest per-file checked_at in the cache manifest (epoch seconds),
    or None when the manifest is missing, unreadable, lists no file or has
    an entry without a readable time (a missing cache)."""
    doc = jsonfile.read_json(manifest_path, encoding="ascii", kind=dict)
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict) or not files:
        return None
    times = []
    for entry in files.values():
        at = _parse_utc(entry.get("checked_at")) if isinstance(entry, dict) else None
        if at is None:
            return None
        times.append(at)
    return min(times)


def due(config, manifest_path, now):
    """True when web data is on and the cache is missing or older than
    MAX_AGE_S (a check time in the future counts as old, as in the tool)."""
    if not web_data_on(config):
        return False
    at = checked_at(manifest_path)
    if at is None:
        return True
    age = now - at
    return not (0 <= age < MAX_AGE_S)


def command(root=None, environ=None):
    """The windowless snapshot tool start, through the one command builder
    (DEP-06): `-m server.al.theorycraft.snapshot` in a checkout, `boot.py
    server.al.theorycraft.snapshot` in an install. No --opt-in: the tool
    checks web data itself."""
    return paths.python_cmd(MODULE, windowless=True, root=root, environ=environ)


def creation_flags():
    """Hidden, detached and below-normal priority on Windows; 0 elsewhere."""
    if os.name != "nt":
        return 0
    return DETACHED | NEW_GROUP | NO_WINDOW | BELOW_NORMAL


def opted_out(environ=None):
    env = os.environ if environ is None else environ
    return (env.get(OPT_OUT_ENV) or "").strip() not in ("", "0")


def read_record(runtime):
    doc = jsonfile.read_json(Path(runtime) / PID_FILE, encoding="ascii", kind=dict)
    return doc if isinstance(doc, dict) else {}


def running(record, pid_alive, created=None):
    """True while the recorded tool process still runs (a reused pid, told
    apart by its creation time, does not count)."""
    pid = record.get("pid")
    if not isinstance(pid, int) or pid <= 0 or pid_alive is None:
        return False
    if not pid_alive(pid):
        return False
    want = record.get("created") or 0
    if want and created is not None:
        got = created(pid)
        if got and got != want:
            return False
    return True


def blocked(runtime, now, pid_alive=None, created=None):
    """None when a start may go ahead, else the reason (one run at a time,
    at most one start per MAX_AGE_S)."""
    rec = read_record(runtime)
    if running(rec, pid_alive, created):
        return "running"
    started = rec.get("started_at")
    if isinstance(started, (int, float)) and 0 <= now - started < MAX_AGE_S:
        return "started recently"
    return None


def _log_file(environ=None):
    """The tool's output file in the sidecar Logs dir; os.devnull when it
    cannot be opened (the run never depends on its log)."""
    try:
        logs = paths.sidecar_dir("Logs", environ)
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / LOG_NAME
        try:
            big = path.stat().st_size > LOG_CAP
        except OSError:
            big = False
        return open(path, "wb" if big else "ab")
    except (OSError, ValueError):
        return open(os.devnull, "wb")


def start(runtime, now, popen=subprocess.Popen, environ=None, pid_alive=None,
          created=None, root=None):
    """Launch the tool once, hidden and below normal; returns its pid, or
    None when one runs or one started inside MAX_AGE_S. Raises OSError when
    the launch fails (the pid file then records the attempt)."""
    if blocked(runtime, now, pid_alive, created) is not None:
        return None
    root = Path(root) if root is not None else paths.repo_root()
    rec = {"pid": 0, "created": 0, "started_at": now}
    try:
        with _log_file(environ) as out:
            proc = popen(command(root=root, environ=environ), cwd=str(root),
                         stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                         close_fds=True, creationflags=creation_flags())
        rec["pid"] = int(proc.pid)
        rec["created"] = (created(rec["pid"]) if created is not None else 0) or 0
        return rec["pid"]
    finally:
        try:
            Path(runtime).mkdir(parents=True, exist_ok=True)
            jsonfile.write_text(Path(runtime) / PID_FILE, json.dumps(rec) + "\n")
        except OSError:
            pass


def tick(runtime, now, config=None, manifest_path=None, environ=None,
         popen=subprocess.Popen, pid_alive=None, created=None, root=None):
    """One supervisor call: start the tool when due() and not blocked.
    config None reads config/local.json; manifest_path None is the cache
    manifest (datacredit.MANIFEST in datacredit.cache_dir)."""
    if opted_out(environ):
        return None
    cfg = paths.load_local_config() if config is None else config
    if manifest_path is None:
        manifest_path = datacredit.cache_dir(environ) / datacredit.MANIFEST
    if not due(cfg, manifest_path, now):
        return None
    return start(runtime, now, popen=popen, environ=environ, pid_alive=pid_alive,
                 created=created, root=root)


class Starter:
    """The keepalive's injected 'snapshot' callable: starter(now) -> pid or
    None. Built by keepalive.main() with the supervisor's own pid checks."""

    def __init__(self, runtime, pid_alive, created=None, popen=subprocess.Popen,
                 environ=None):
        self.runtime = Path(runtime)
        self._pid_alive = pid_alive
        self._created = created
        self._popen = popen
        self._environ = environ

    def __call__(self, now):
        return tick(self.runtime, now, environ=self._environ, popen=self._popen,
                    pid_alive=self._pid_alive, created=self._created)
