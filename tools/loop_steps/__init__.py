"""AUTO-01: the loop tick's one step seam (tools/al_loop.py never grows).

Every later watcher, check or request is a new file in this folder, never an
al_loop.py edit. A step module defines any of these functions, one per phase:

    pre_halt(tick)                       tick(), in front of the HALT test
                                         (runs even HALTed; tick.halted is set)
    work(tick)                           Tick.run, after the daily ledger rotate
    post_work(tick, rows, work, skipped) Tick.run, after the dispatch and the
                                         idle dive, before the push launch
    checklist(tick) -> kit rows          appended to a running tick's checklist
                                         and to a HALTed tick's empty one

A line phase returns one line, a list of lines or None; every line becomes one
tick line. A dry run calls no step. A step that raises becomes one tick line
`step <name>: <Error>: <text>` and never stops the tick; a module that fails
to import is skipped with one tick line.

Loader rule: each file is imported as loop_steps.<stem> through
importlib.import_module; this folder is never put on sys.path, so a step
named like a tools module (tc_drift, upstream_watch) never shadows it.

Hermetic rule: a step reaches the outside world only through tick.d seams,
or, for a seam Deps lacks, only when tick.root is the main checkout
(al_loop.ROOT). This package never imports al_loop.
"""

import importlib
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
PHASES = ("pre_halt", "work", "post_work", "checklist")
ROWS_MAX = 20  # the kit fleet_checklist.ROWS_MAX when tick.d has no checklist


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def load(directory=None, errors=None):
    """The step modules of `directory` (default: this folder) in file-name
    order. A file that fails to import is skipped; (stem, exception) goes to
    `errors` when a list is given."""
    folder = Path(directory).resolve() if directory else DIR
    importlib.invalidate_caches()
    saved = list(__path__)
    mods = []
    try:
        __path__[:] = [str(folder)]
        for path in sorted(folder.glob("*.py"), key=lambda p: p.name):
            if path.stem.startswith("_"):
                continue
            name = f"{__name__}.{path.stem}"
            old = sys.modules.get(name)
            if old is not None and (folder != DIR or
                                    not _same(getattr(old, "__file__", ""), path)):
                del sys.modules[name]
            try:
                mods.append(importlib.import_module(name))
            except Exception as exc:  # noqa: BLE001 - a broken step never stops the tick
                sys.modules.pop(name, None)
                if errors is not None:
                    errors.append((path.stem, exc))
    finally:
        __path__[:] = saved
    return mods


def _stem(mod):
    return mod.__name__.rsplit(".", 1)[-1]


def run(phase, tick, *args, directory=None):
    """Call `phase` of every step module that has it, in file-name order.
    Returns the results, None dropped and a returned list flattened. A
    raising step is one tick line; the modules load once per tick."""
    cache = tick.__dict__.setdefault("_loop_steps", {})
    key = str(Path(directory).resolve() if directory else DIR)
    if key not in cache:
        errors = []
        cache[key] = load(directory, errors)
        for stem, exc in errors:
            tick.step(f"step {stem}: import failed: {type(exc).__name__}: {exc}")
    out = []
    for mod in cache[key]:
        fn = getattr(mod, phase, None)
        if not callable(fn):
            continue
        try:
            res = fn(tick, *args)
        except Exception as exc:  # noqa: BLE001 - one tick line, never a stopped tick
            tick.step(f"step {_stem(mod)}: {type(exc).__name__}: {exc}")
            continue
        if isinstance(res, (list, tuple)):
            out.extend(r for r in res if r is not None)
        elif res is not None:
            out.append(res)
    return out


def lines(phase, tick, *args):
    """A line phase: each non-empty result is one tick line. A dry run calls
    no step."""
    if getattr(tick, "dry", False):
        return []
    out = [str(r) for r in run(phase, tick, *args) if str(r).strip()]
    for line in out:
        tick.step(line)
    return out


def rows(tick, have=()):
    """`have` plus the checklist steps' rows (dicts only), capped at the kit
    ROWS_MAX; the overflow is counted on tick.checklist_dropped, never silent.
    A dry run calls no step."""
    have = list(have)
    if getattr(tick, "dry", False):
        return have
    extra = [r for r in run("checklist", tick) if isinstance(r, dict)]
    cap = getattr(getattr(tick.d, "checklist", None), "ROWS_MAX", ROWS_MAX)
    room = max(cap - len(have), 0)
    tick.checklist_dropped = getattr(tick, "checklist_dropped", 0) + max(len(extra) - room, 0)
    return have + extra[:room]
