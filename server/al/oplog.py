"""RUN-OPLOG (F-153, decision 0067): one JSON line per own event.

events.jsonl records what AshLight itself did, one typed JSON object per
line, for the probe command and the click-built report:

- start (build id, pid, port) and stop (reason word, its detail word),
  written by the entry point (server/al/__main__.py);
- reader start / reset / death / unreadable / readable, from the bus's
  tailer status events (event word, reset reason word; never the path);
- consent and web data switches and a dashboard reload, seen by
  plug/oplog.py comparing the core's state once a second;
- a fetch result per host, a calc request (outcome ok, error, timeout,
  crash or unavailable, with its ms) and a press outcome with its ms,
  from metrics.emit; calc starts from the calc.start / calc.restart
  counters.

Every field is typed: a bool, int, float or None, or a TOKEN (a lower-case
word with no space, slash or backslash, at most 64 characters; `+` is
allowed for the SemVer build id). No free-text field type exists: a value
of another shape is dropped and counted (OpLog.dropped and the
"oplog.dropped" counter), so no path, name, chat or item text is ever
written. A kind outside KINDS is refused the same way.

The file lives in the sidecar Logs dir (a test core: its own tmp runtime
dir). It is bounded: before a write that finds it at MAX_BYTES or more it
moves to `events.jsonl.1` through logs.rotate_at_start (one old file
kept). A write that fails is counted, never raised. Standard library only;
nothing is sent anywhere.
"""

import json
import math
import os
import re
import threading
import time
import weakref
from pathlib import Path

from . import logs, metrics

FILE_NAME = "events.jsonl"
MAX_BYTES = 512 * 1024  # rotate past this; at most 2 x MAX_BYTES on disk
DROPPED = "oplog.dropped"

KINDS = frozenset({"start", "stop", "reader", "consent", "web_data", "reload",
                   "fetch", "calc_start", "calc", "press"})
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.:+-]{0,63}\Z")
FIELD_RE = metrics.FIELD_RE
MAX_FIELDS = metrics.MAX_FIELDS

# bus status event type -> reader event word (AshLight's own words)
READER_EVENTS = {"tailer_started": "start", "tailer_reset": "reset",
                 "tailer_restarted": "death", "tailer_unreadable": "unreadable",
                 "tailer_readable": "readable"}
# the bus fields a reader line keeps (typed values only; never "path")
READER_FIELDS = ("reason", "resumed", "restarts")
EMIT_KINDS = ("fetch", "calc", "press")


def typed(value):
    """True when value may be written: bool, int, finite float, None or a
    TOKEN. No free text."""
    if value is None or isinstance(value, (bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, str) and TOKEN_RE.match(value) is not None


def word(value):
    """A short label as a TOKEN where it can be one (lower case, spaces as
    _), else the value unchanged (and then dropped by write)."""
    if isinstance(value, str):
        return "_".join(value.strip().lower().split())
    return value


class OpLog:
    """One bounded events.jsonl. Thread safe; write() never raises."""

    def __init__(self, path, max_bytes=MAX_BYTES, clock=time.time):
        self.path = Path(path)
        self.max_bytes = int(max_bytes)
        self.clock = clock
        self.dropped = 0
        self.errors = 0
        self.written = 0
        self.closed = False
        self._lock = threading.Lock()
        self._size = None
        self._made = False

    def _drop(self, n=1):
        self.dropped += n
        metrics.inc(DROPPED, n)

    def write(self, kind, **fields):
        """Append one line {"t", "kind", **typed fields}. Returns the record
        written, or None (closed, refused kind, or a failed write)."""
        if self.closed:
            return None
        if kind not in KINDS:
            with self._lock:
                self._drop()
            return None
        rec = {"t": logs.stamp(self.clock()), "kind": kind}
        bad = 0
        for k, v in list(fields.items())[:MAX_FIELDS]:
            if isinstance(k, str) and FIELD_RE.match(k) and k not in rec and typed(v):
                rec[k] = v
            else:
                bad += 1
        bad += max(0, len(fields) - MAX_FIELDS)
        line = json.dumps(rec, ensure_ascii=True, separators=(",", ":")) + "\n"
        with self._lock:
            if bad:
                self._drop(bad)
            try:
                self._append(line)
            except OSError:
                self.errors += 1
                return None
            self.written += 1
        return rec

    def _append(self, line):
        if not self._made:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._made = True
        if self._size is None:
            try:
                self._size = self.path.stat().st_size
            except OSError:
                self._size = 0
        if self._size >= self.max_bytes:
            logs.rotate_at_start(self.path, self.max_bytes - 1)
            try:
                self._size = self.path.stat().st_size
            except OSError:
                self._size = 0
        with open(self.path, "a", encoding="ascii", newline="\n") as fh:
            fh.write(line)
        self._size += len(line)

    # -- sources
    def on_emit(self, rec):
        """A metrics.emit record (fetch, calc, press) as one line."""
        kind = rec.get("kind")
        if kind in EMIT_KINDS:
            self.write(kind, **{k: v for k, v in rec.items() if k not in ("kind", "t")})

    def on_bus(self, ev):
        """A bus event: tailer status events become reader lines (the event
        word plus typed fields; the path is never copied)."""
        what = READER_EVENTS.get(ev.get("type")) if isinstance(ev, dict) else None
        if what is None:
            return
        fields = {k: word(ev[k]) for k in READER_FIELDS if k in ev}
        self.write("reader", event=what, **fields)

    def watch_metrics(self):
        """Make this log the one that records the process's metrics.emit
        events. Emits are process wide, and a process runs one core: the
        newest attached log owns them, an older one (an earlier test core)
        gets none. One subscription per process, holding the owner by a
        weak reference, so nothing piles up."""
        with _RELAY_LOCK:
            _OWNER[0] = weakref.ref(self)
            if _SUB[0] is not None:
                _SUB[0]()  # re-subscribe: a metrics.reset() drops subscribers
            _SUB[0] = metrics.subscribe(_relay)

    def owns_metrics(self):
        ref = _OWNER[0]
        return ref is not None and ref() is self

    def close(self):
        """No further lines; the log gives up the metrics events."""
        self.closed = True
        with _RELAY_LOCK:
            ref = _OWNER[0]
            if ref is not None and ref() is self:
                _OWNER[0] = None


_RELAY_LOCK = threading.Lock()
_OWNER = [None]  # weakref of the OpLog that records metrics.emit events
_SUB = [None]  # the one metrics subscription's unsubscribe function


def _relay(rec):
    ref = _OWNER[0]
    log = ref() if ref is not None else None
    if log is not None and not log.closed:
        log.on_emit(rec)


SWITCH_EVERY_S = 1.0  # the switch compare runs at most once a second


class SwitchWatch:
    """The switches no event announces (core.record_consent and
    core.set_web_data publish none): compares the Client.txt and ledger
    consent, web data, the dashboard reload count and the calc start
    counters once a second and writes a line on a change. The values at
    attach are the baseline (no line)."""

    def __init__(self, core, log, clock=time.monotonic, every_s=SWITCH_EVERY_S):
        self.core = core
        self.log = log
        self.clock = clock
        self.every_s = float(every_s)
        self._next = 0.0
        self.state = self.read()

    def read(self):
        c = self.core
        return {"log": _safe_bool(getattr(c, "consented", None)),
                "ledger": _safe_bool(getattr(c, "ledger_consented", None)),
                "web_data": _safe_bool(getattr(c, "web_data_enabled", None)),
                "reload": int(getattr(c, "reload_web", 0) or 0),
                "calc_start": metrics.counter("calc.start"),
                "calc_restart": metrics.counter("calc.restart")}

    def tick(self, force=False):
        now = self.clock()
        if not force and now < self._next:
            return False
        self._next = now + self.every_s
        old, new = self.state, self.read()
        self.state = new
        for what in ("log", "ledger"):
            if new[what] is not None and new[what] != old[what]:
                self.log.write("consent", what=what, on=new[what])
        if new["web_data"] is not None and new["web_data"] != old["web_data"]:
            self.log.write("web_data", on=new["web_data"])
        if new["reload"] > old["reload"]:
            self.log.write("reload", what="web", n=new["reload"] - old["reload"])
        starts = max(0, new["calc_start"] - old["calc_start"])
        restarts = max(0, new["calc_restart"] - old["calc_restart"])
        if starts or restarts:
            self.log.write("calc_start", n=starts, restarts=restarts)
        return True


def _safe_bool(fn):
    if not callable(fn):
        return None
    try:
        return bool(fn())
    except Exception:  # noqa: BLE001 - an unreadable switch is skipped
        return None


# -- the entry point's two lines (server/al/__main__.py)
def record_start(core):
    """The start line: build id, pid and the served port."""
    log = getattr(core, "oplog", None)
    if log is None:
        return None
    try:
        from . import buildinfo
        build = word(buildinfo.build_id())
    except Exception:  # noqa: BLE001 - a start line never stops a start
        build = None
    port = getattr(core, "port", None)
    return log.write("start", build=build, pid=os.getpid(),
                     port=port if isinstance(port, int) else None)


def record_stop(core, reason, detail=None):
    """The stop line (reason stop / signal / reload, its detail as a word),
    then the log closes."""
    log = getattr(core, "oplog", None)
    if log is None:
        return None
    rec = log.write("stop", reason=word(reason), detail=word(detail))
    log.close()
    return rec
