"""PoB's output table for the loaded build, when the optional calc is on.

MATH-SKILL-SPLIT and MATH-DEF-BREAKDOWN show some values that exist only
in PoB's calc outputs (CalcDefence / CalcPerform; research 0031 section
2). This cache asks the calc for them once per build, in a background
thread, so GET /api/build never waits on the external process. `get()`
returns the table when it is ready, else None (the calc-only rows stay
hidden); `on_ready` lets the core bump the build view so the dashboard
reads it again with no click. With the calc off nothing runs and get()
is always None. Values are PoB's own; nothing is recomputed (decision
0004).
"""

import logging
import threading
import time

from .. import num
from . import pobweights

log = logging.getLogger("al.theorycraft")
RETRY_S = 60.0


def clean(raw):
    """Only finite numbers and booleans from a PoB output table."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, bool) or num.finite(v) is not None:
            out[k] = v
    return out


class OutputsCache:
    """`get_calc()`: the core's calc provider result (None while off); a
    calc with a `raw(build, keys)` attribute (calcwire.make_calc) can give
    the extra outputs. `keys`: the PoB output names to ask for."""

    def __init__(self, get_calc, keys, on_ready=None, clock=time.monotonic, sync=False):
        self.get_calc = get_calc
        self.keys = tuple(keys)
        self.on_ready = on_ready
        self._clock = clock
        self._sync = sync  # tests: run in the caller's thread
        self._lock = threading.Lock()
        self._bid = None
        self._table = None
        self._pending = None
        self._failed = {}  # build id -> clock time of the failure

    def _raw(self):
        try:
            calc = self.get_calc() if callable(self.get_calc) else None
        except Exception:  # noqa: BLE001 - a bad provider reads as off
            return None
        raw = getattr(calc, "raw", None)
        return raw if callable(raw) else None

    def get(self, build):
        """PoB's outputs for `build` when ready, else None (and a fetch is
        started when the calc is on)."""
        bid = pobweights.build_id(build)
        if bid is None:
            return None
        raw = self._raw()
        if raw is None:  # calc off (or turned off): calc-only rows hide
            return None
        with self._lock:
            if self._bid == bid:
                return dict(self._table)
            if self._pending == bid:
                return None
            failed = self._failed.get(bid)
            if failed is not None and self._clock() - failed < RETRY_S:
                return None
            if self._pending is not None:
                return None
            self._pending = bid
        if self._sync:
            self._fetch(raw, build, bid)
            with self._lock:
                return dict(self._table) if self._bid == bid else None
        threading.Thread(target=self._fetch, args=(raw, build, bid),
                         name="al-pob-outputs", daemon=True).start()
        return None

    def _fetch(self, raw, build, bid):
        try:
            table = clean(raw(build, self.keys))
        except Exception:  # noqa: BLE001 - external process: any failure
            log.warning("PoB outputs for the build view failed", exc_info=True)
            with self._lock:
                self._pending = None
                self._failed[bid] = self._clock()
            return
        with self._lock:
            self._pending = None
            self._failed.pop(bid, None)
            self._bid, self._table = bid, table
        if callable(self.on_ready):
            try:
                self.on_ready()
            except Exception:  # noqa: BLE001 - never break the fetch
                log.exception("outputs on_ready failed")

