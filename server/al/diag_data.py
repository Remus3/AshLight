"""DATA-DIAG-SEAM (research 0047 F1, units F-085 F-140 F-143 F-155): one
hook for the data modules' Checks rows, facts and start-up wiring.

The data modules named in MODULES add a Checks row, a diag fact or a
start-up hook by adding a function to THEIR OWN module; core.py and
diag.py call this file and are not edited again. Every hook is optional
per module:

    def attach(core): ...         # once, at the end of Core.__init__
    def diag_facts(core): ...     # dict merged into Core.diag_facts
                                  # (a built-in or plug key always wins)
    def diag_rows(f, now): ...    # a list of diag._check dicts (or one),
                                  # shown before the reload and dev-docs rows

A module is imported lazily, on the first call. A module or a function
that does not exist yet is skipped; a module that fails to import, or a
hook that raises, is logged (plug.ErrorThrottle: the first traceback,
then one line a minute) and reads as nothing, so it never breaks the
Checks card or the core start. A row with a bad shape or an id already
taken is dropped.

This file makes no request and reads no file: it imports only the
standard library and AshLight's plug helpers (the error throttle and the
row shape check); what a hook does is that module's business and its
own tests'.
"""

import importlib
import logging
import threading

from . import plug

log = logging.getLogger("al.diag_data")

# The data modules that may carry the three hooks, in the order their rows
# show. A name that is not a module yet (a later package creates it) is
# skipped without a log line.
MODULES = (
    "server.al.pricebook",
    "server.al.ninjashape",
    "server.al.theorycraft.snapprobe",
    "server.al.tradestats",
)

_lock = threading.Lock()
_found = None  # (MODULES tuple, [(name, module)]) once imported
_throttle = plug.ErrorThrottle(log)


def _missing(exc, name):
    """True when `exc` says the module `name` itself (or a parent package
    of it) does not exist, not that one of its own imports failed."""
    missing = getattr(exc, "name", None)
    return isinstance(missing, str) and (name == missing or name.startswith(missing + "."))


def modules():
    """[(name, module)] of the MODULES that import, in MODULES order;
    imported once per MODULES value (thread safe)."""
    global _found
    names = tuple(MODULES)
    with _lock:
        if _found is not None and _found[0] == names:
            return list(_found[1])
        out = []
        for name in names:
            try:
                out.append((name, importlib.import_module(name)))
            except ModuleNotFoundError as exc:
                if not _missing(exc, name):
                    _throttle.failed(f"diag_data {name} import", exc)
            except Exception as exc:  # noqa: BLE001 - a broken module never stops the core
                _throttle.failed(f"diag_data {name} import", exc)
        _found = (names, out)
        return list(out)


def reset():
    """Forget the imports and the error throttle (tests)."""
    global _found, _throttle
    with _lock:
        _found = None
        _throttle = plug.ErrorThrottle(log)


def _hooks(hook):
    for name, mod in modules():
        fn = getattr(mod, hook, None)
        if callable(fn):
            yield name, fn


def attach(core):
    """Run every module's attach(core) once (the end of Core.__init__)."""
    for name, fn in _hooks("attach"):
        try:
            fn(core)
        except Exception as exc:  # noqa: BLE001
            _throttle.failed(f"diag_data {name} attach", exc)


def facts(core, base=None):
    """`base` (the plug facts) plus every module's diag_facts(core), in
    MODULES order; a key already present wins over a later one."""
    out = dict(base) if isinstance(base, dict) else {}
    for name, fn in _hooks("diag_facts"):
        try:
            got = fn(core)
        except Exception as exc:  # noqa: BLE001
            _throttle.failed(f"diag_data {name} diag_facts", exc)
            continue
        if isinstance(got, dict):
            for k, v in got.items():
                if isinstance(k, str):
                    out.setdefault(k, v)
    return out


def rows(f, now, taken=()):
    """Every module's Checks rows for facts `f`, in MODULES order, each
    in the diag._check shape. A bad row or an id in `taken` (or an
    earlier row's) is dropped."""
    seen = set(taken)
    out = []
    for name, fn in _hooks("diag_rows"):
        try:
            got = fn(f, now)
        except Exception as exc:  # noqa: BLE001
            _throttle.failed(f"diag_data {name} diag_rows", exc)
            continue
        for r in (got if isinstance(got, (list, tuple)) else [got]):
            row = plug._row(r)  # the plug folder's row check, one rule for both
            if row is None:
                if r is not None:
                    log.error("diag_data %s: a Checks row with a bad shape was dropped", name)
                continue
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            out.append(row)
    return out
