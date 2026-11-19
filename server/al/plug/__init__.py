"""RUN-SEAMS (decision 0056): the plug-in folder.

A later feature adds a core tick, a Checks row or a token-gated /api/
route by adding ONE module to this folder; no shared file (core.py,
__main__.py, diag.py, http.py) changes. Modules are found by name
(pkgutil over this package's __path__; a name starting with "_" is
skipped) and imported once, in (ORDER, name) order. Every hook is
optional:

    ORDER = 100                      # sort key (default DEFAULT_ORDER)
    def attach(core): ...            # once, at the tail of Core.__init__;
                                     # core.add_tick(name, fn) adds a tick
    def facts(core, now): ...        # dict merged into Core.diag_facts
                                     # (a built-in key always wins)
    def rows(f, now): ...            # a Checks row dict, a list of them,
                                     # or None; shown after the built-ins
    ROUTES = {("GET", "/api/x"): fn} # fn(req, query, extra), req = the
                                     # http.Handler; GET or POST only

Routes run only from the HTTP handler's fall-through, after its Host /
Origin / Sec-Fetch-Site / token guard, and only for an exact path under
/api/ (every /api/ path needs the token). A route outside /api/, with
another verb or a non-callable handler is refused at discovery and
logged; it is never served and never listed. A built-in route of the
same path wins (the fall-through runs after the if-chain).

A module that fails to import, or a hook that raises, is logged (at most
one line a minute per hook after the first traceback) and skipped; it
never stops the core. Standard library only; this package imports
nothing of AshLight, so core, diag and http can import it.
"""

import importlib
import logging
import pkgutil
import sys
import threading
import time

log = logging.getLogger("al.plug")

DEFAULT_ORDER = 100
API_PREFIX = "/api/"
ROUTE_VERBS = ("GET", "POST")
ERROR_EVERY_S = 60.0  # after the first traceback, one line a minute per name

_lock = threading.Lock()
_found = None  # [(order, name, module)] once discovered
_routes = None  # {(verb, path): fn}


class ErrorThrottle:
    """Logs a repeating error without flooding core.log: the first failure
    of a name with its traceback, then at most one line every `every_s`
    seconds with the number of failures since the last line."""

    def __init__(self, logger, every_s=ERROR_EVERY_S):
        self.log = logger
        self.every_s = float(every_s)
        self._state = {}  # name -> [failures since the last line, next line at]

    def failed(self, name, exc, now=None):
        """Record one failure of `name` (call inside the except block).
        Returns True when a line was written."""
        now = time.monotonic() if now is None else now
        st = self._state.get(name)
        if st is None:
            self._state[name] = [0, now + self.every_s]
            self.log.error("%s failed", name, exc_info=exc)
            return True
        st[0] += 1
        if now < st[1]:
            return False
        self.log.error("%s failed again, %d time(s) since the last line: %s",
                       name, st[0], _short(exc))
        st[0] = 0
        st[1] = now + self.every_s
        return True

    def count(self, name):
        """Failures of `name` not yet reported in a line."""
        st = self._state.get(name)
        return st[0] if st else 0


def _short(exc):
    text = " ".join(str(exc).split())[:200]
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


_throttle = ErrorThrottle(log)


def _module_names():
    return sorted(name for _, name, _ in pkgutil.iter_modules(__path__)
                  if not name.startswith("_"))


def _valid_routes(name, mod):
    table = getattr(mod, "ROUTES", None)
    out = {}
    if table is None:
        return out
    if not isinstance(table, dict):
        log.error("plug %s: ROUTES is not a dict; no route served", name)
        return out
    for key, fn in table.items():
        ok = (isinstance(key, tuple) and len(key) == 2
              and key[0] in ROUTE_VERBS and isinstance(key[1], str)
              and key[1].startswith(API_PREFIX) and len(key[1]) > len(API_PREFIX)
              and "?" not in key[1] and "#" not in key[1] and callable(fn))
        if not ok:
            log.error("plug %s: route %r refused (GET or POST, an exact /api/ "
                      "path and a callable only)", name, key)
            continue
        out[key] = fn
    return out


def modules():
    """[(order, name, module)] of every plug module, discovered and
    imported once (thread safe), in (ORDER, name) order."""
    global _found, _routes
    with _lock:
        if _found is not None:
            return list(_found)
        found = []
        routes = {}
        for name in _module_names():
            try:
                mod = importlib.import_module(f"{__name__}.{name}")
            except Exception as exc:  # noqa: BLE001 - a broken plug never stops the core
                _throttle.failed(f"plug {name} import", exc)
                continue
            order = getattr(mod, "ORDER", DEFAULT_ORDER)
            if not isinstance(order, (int, float)) or isinstance(order, bool):
                order = DEFAULT_ORDER
            found.append((order, name, mod))
        found.sort(key=lambda t: (t[0], t[1]))
        for _, name, mod in found:
            for key, fn in _valid_routes(name, mod).items():
                if key in routes:
                    log.error("plug %s: route %s %s already taken; refused", name, *key)
                    continue
                routes[key] = fn
        _found = found
        _routes = routes
        return list(found)


def reset():
    """Forget the discovery (tests point __path__ elsewhere, then call
    this); the plug submodules are dropped from sys.modules so the next
    discovery imports them again."""
    global _found, _routes, _throttle
    with _lock:
        _found = None
        _routes = None
        _throttle = ErrorThrottle(log)
        prefix = __name__ + "."
        for key in [k for k in sys.modules if k.startswith(prefix)]:
            del sys.modules[key]


def attach_all(core):
    """Run every module's attach(core) once (Core.__init__ tail)."""
    for _, name, mod in modules():
        fn = getattr(mod, "attach", None)
        if not callable(fn):
            continue
        try:
            fn(core)
        except Exception as exc:  # noqa: BLE001 - a broken plug never stops the core
            _throttle.failed(f"plug {name} attach", exc)


def collect_facts(core, now):
    """One dict of every module's facts(core, now), in module order; an
    earlier module's key wins over a later one's."""
    out = {}
    for _, name, mod in modules():
        fn = getattr(mod, "facts", None)
        if not callable(fn):
            continue
        try:
            got = fn(core, now)
        except Exception as exc:  # noqa: BLE001
            _throttle.failed(f"plug {name} facts", exc)
            continue
        if isinstance(got, dict):
            for k, v in got.items():
                if isinstance(k, str):
                    out.setdefault(k, v)
    return out


ROW_STATUSES = ("pass", "fail", "unknown", "off", "note")  # diag.MARK keys


def _row(r):
    """A clean Checks row (the diag._check shape) or None."""
    if not isinstance(r, dict):
        return None
    cid, label, status, detail = (r.get("id"), r.get("label"), r.get("status"),
                                  r.get("detail"))
    if not (isinstance(cid, str) and cid and isinstance(label, str) and label
            and status in ROW_STATUSES and isinstance(detail, str)):
        return None
    fix = r.get("fix")
    return {"id": cid, "label": label, "status": status, "detail": detail,
            "fix": fix if status == "fail" and isinstance(fix, str) else None}


def collect_rows(f, now, taken=()):
    """Every module's Checks rows for facts `f`, in module ORDER. A row
    with a bad shape or an id already taken is dropped."""
    seen = set(taken)
    out = []
    for _, name, mod in modules():
        fn = getattr(mod, "rows", None)
        if not callable(fn):
            continue
        try:
            got = fn(f, now)
        except Exception as exc:  # noqa: BLE001
            _throttle.failed(f"plug {name} rows", exc)
            continue
        for r in (got if isinstance(got, (list, tuple)) else [got]):
            row = _row(r)
            if row is None:
                if r is not None:
                    log.error("plug %s: a Checks row with a bad shape was dropped", name)
                continue
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            out.append(row)
    return out


def route(verb, path):
    """The plug handler for (verb, exact path), or None. Only ever an
    /api/ path; the caller has already run the handler guard."""
    if not (isinstance(path, str) and path.startswith(API_PREFIX)):
        return None
    modules()
    return (_routes or {}).get((verb, path))


def all_routes():
    """Sorted [(verb, path)] of every plug route (the surface pin reads it)."""
    modules()
    return sorted(_routes or {})
