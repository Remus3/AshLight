"""RUN-METRICS-CORE (finding F-032, decision 0067): AshLight's own counters.

In-memory counters, gauges and small timing rings about AshLight's own
behaviour, read only by the token-gated pull route GET /api/debug
(server/al/plug/debug.py). Nothing here is ever in the state snapshot,
written to a file or sent anywhere.

    metrics.inc("sse.frames")              # a counter (+1, or +n)
    metrics.set_gauge("x", 3)              # a gauge (last value)
    metrics.timing("loop_ms", 1.25)        # a ring of the last RING_SIZE values
    metrics.emit("fetch", ok=True, ms=40)  # a typed event: counted by kind
                                           # and handed to the subscribers
    metrics.subscribe(fn)                  # fn({"kind", "t", **fields}); the
                                           # return value unsubscribes

Names are short code constants (a lower-case word with . _ - : / * | and
digits); a name of another shape raises ValueError, and past MAX_NAMES
names per kind a new name is counted in "metrics.dropped" instead, so the
store stays bounded whatever a caller does. Emitted fields are typed: a
bool, int, float or None, or a WORD (a lower-case token with no space,
slash or backslash, at most 64 characters, such as a host from the
allow-list or a status class). No free-text field type exists, so no
path, name, chat or item text can travel through emit (decision 0067).

Standard library only; this module imports nothing of AshLight, so every
other module can import it. Thread safe (one lock per registry); one
update is a lock, a dict lookup and an add.
"""

import collections
import logging
import os
import re
import sys
import threading
import time

log = logging.getLogger("al.metrics")

RING_SIZE = 64  # values kept per timing ring
MAX_NAMES = 512  # distinct names per kind (counters, gauges, rings)
DROPPED = "metrics.dropped"  # counts updates refused for the cap

NAME_RE = re.compile(r"[a-z0-9][a-z0-9_.:/*|-]{0,95}\Z")
KIND_RE = re.compile(r"[a-z][a-z0-9_.]{0,39}\Z")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}\Z")
FIELD_RE = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
MAX_FIELDS = 16


def _check_name(name):
    if not (isinstance(name, str) and NAME_RE.match(name)):
        raise ValueError(f"bad metric name {name!r}")


def typed_value(value):
    """True when `value` is a typed emit field: bool, int, float, None or a
    WORD (no free text)."""
    if value is None or isinstance(value, (bool, int, float)):
        return True
    return isinstance(value, str) and WORD_RE.match(value) is not None


class Registry:
    """Counters, gauges, timing rings and emit subscribers of one process."""

    def __init__(self, ring_size=RING_SIZE, max_names=MAX_NAMES):
        self.ring_size = int(ring_size)
        self.max_names = int(max_names)
        self._lock = threading.Lock()
        self._counters = {}
        self._gauges = {}
        self._rings = {}
        self._subs = []
        self.subscriber_errors = 0

    # -- updates
    def _room(self, table, name):
        """Validate a new name; False (and one dropped count) when its kind
        is full. Called with the lock held."""
        _check_name(name)
        if len(table) >= self.max_names:
            self._counters[DROPPED] = self._counters.get(DROPPED, 0) + 1
            return False
        return True

    def inc(self, name, n=1):
        """Add n (default 1) to counter `name`."""
        with self._lock:
            c = self._counters
            if name in c:
                c[name] += n
            elif self._room(c, name):
                c[name] = n

    def set_gauge(self, name, value):
        with self._lock:
            g = self._gauges
            if name in g or self._room(g, name):
                g[name] = value

    def add_gauge(self, name, delta):
        """Move gauge `name` by delta (an up / down count); returns the new value."""
        with self._lock:
            g = self._gauges
            if name in g:
                g[name] += delta
            elif self._room(g, name):
                g[name] = delta
            return g.get(name)

    def timing(self, name, ms):
        """Append one duration (ms) to ring `name` (the last ring_size kept)."""
        with self._lock:
            r = self._rings.get(name)
            if r is None:
                if not self._room(self._rings, name):
                    return
                r = self._rings[name] = collections.deque(maxlen=self.ring_size)
            r.append(float(ms))

    # -- reads
    def counter(self, name):
        with self._lock:
            return self._counters.get(name, 0)

    def gauge(self, name, default=None):
        with self._lock:
            return self._gauges.get(name, default)

    def ring(self, name):
        with self._lock:
            return list(self._rings.get(name, ()))

    def counters(self, prefix=""):
        """{name: count} of the counters whose name starts with prefix."""
        with self._lock:
            return {k: v for k, v in self._counters.items() if k.startswith(prefix)}

    def gauges(self):
        with self._lock:
            return dict(self._gauges)

    def timings(self):
        """{name: {"n", "last", "p50", "max"}} of every ring (ms, rounded)."""
        with self._lock:
            rings = {k: list(v) for k, v in self._rings.items()}
        return {k: ring_stats(v) for k, v in rings.items() if v}

    # -- typed events
    def subscribe(self, fn):
        """fn(record) for every emit; returns a function that unsubscribes."""
        if not callable(fn):
            raise ValueError("a subscriber must be callable")
        with self._lock:
            self._subs.append(fn)

        def unsubscribe():
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)
        return unsubscribe

    def emit(self, kind, **fields):
        """One typed event: counted as "emit|<kind>" and handed to every
        subscriber as {"kind", "t" (epoch s), **fields}. A field that is
        not typed (typed_value) raises ValueError; a subscriber that raises
        is counted and skipped. Returns the record."""
        if not (isinstance(kind, str) and KIND_RE.match(kind)):
            raise ValueError(f"bad emit kind {kind!r}")
        if len(fields) > MAX_FIELDS:
            raise ValueError("too many emit fields")
        for k, v in fields.items():
            if k in ("kind", "t") or not FIELD_RE.match(k):
                raise ValueError(f"bad emit field name {k!r}")
            if not typed_value(v):
                raise ValueError(f"emit field {k} is not a typed value")
        rec = {"kind": kind, "t": round(time.time(), 3)}
        rec.update(fields)
        self.inc("emit|" + kind)
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(dict(rec))
            except Exception:  # noqa: BLE001 - a subscriber never breaks a caller
                with self._lock:
                    self.subscriber_errors += 1
                log.debug("metrics subscriber failed", exc_info=True)
        return rec

    def reset(self):
        """Forget every value and subscriber (tests)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._rings.clear()
            self._subs.clear()
            self.subscriber_errors = 0


def ring_stats(values):
    """{"n", "last", "p50", "max"} of a non-empty list of ms values."""
    s = sorted(values)
    return {"n": len(values), "last": round(values[-1], 3),
            "p50": round(s[len(s) // 2], 3), "max": round(s[-1], 3)}


# -- the process registry and its module-level shortcuts
REGISTRY = Registry()
inc = REGISTRY.inc
set_gauge = REGISTRY.set_gauge
add_gauge = REGISTRY.add_gauge
timing = REGISTRY.timing
emit = REGISTRY.emit
subscribe = REGISTRY.subscribe
counter = REGISTRY.counter
counters = REGISTRY.counters
gauge = REGISTRY.gauge
gauges = REGISTRY.gauges
timings = REGISTRY.timings
reset = REGISTRY.reset


# -- AshLight's own process (its own handle only; no other process is
# listed or opened: decisions 0006 method 3 and 0029)
def _working_set_windows():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32 = ctypes.WinDLL("kernel32")
    psapi = ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = wintypes.HANDLE  # a pseudo handle to itself
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                           wintypes.DWORD]
    if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return int(pmc.WorkingSetSize)
    return None


def _working_set_proc():
    with open("/proc/self/statm", "r", encoding="ascii") as fh:
        resident_pages = int(fh.read().split()[1])
    return resident_pages * os.sysconf("SC_PAGE_SIZE")


def working_set_bytes():
    """This process's working set (resident) bytes, or None when unknown."""
    try:
        if sys.platform == "win32":
            return _working_set_windows()
        if os.path.exists("/proc/self/statm"):
            return _working_set_proc()
    except (OSError, ValueError, AttributeError, IndexError):
        return None
    return None


def own_process():
    """{"working_set_mb", "cpu_s", "threads"} of this process: working set
    (None when unknown), CPU seconds (user + system) and live Python
    threads. No pid, no path, no name."""
    ws = working_set_bytes()
    return {"working_set_mb": None if ws is None else round(ws / (1024 * 1024), 1),
            "cpu_s": round(time.process_time(), 2),
            "threads": threading.active_count()}
