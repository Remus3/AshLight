"""AUTO-05 (WATCH-CORE, F-030): the upstream watcher sources, one file each.

tools/upstream_watch.py runs every source of this folder; a new source is a
new file here, never an upstream_watch.py edit. A source module defines

    SOURCE = {
        "name": "<registry name>",        # ^[a-z][a-z0-9_-]*$, unique
        "home": "loop" | "ci" | "both",   # default "loop"
        "cadence_s": <seconds>,           # 0 = every tick (default 0)
        "window": None | {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD",
                          "cadence_s": <seconds>} | [<such>, ...],
        "needs_web_data": True,           # False only for the two settled
                                          # sources (decisions 0044, 0025)
        "hosts": ["api.github.com"],      # empty (with urls empty) = local
        "urls": ["https://..."],          # exact URLs beside GitHub metadata
        "purpose": "dev: watcher <name>", # optional User-Agent purpose
        "check": check,
    }

    def check(state, now, fetch, ctx) -> [{"source", "kind", "key", "tokens"}]

`state` is a copy of the source's own record in ops/runtime/watch/state.json
(last_run, last_ok, fails, etag, seen, idle, cause, data); after a good run
the frame keeps the check's changes to "etag" and "data" only. `fetch(url,
etag=None)` -> (status, headers, body) is the frame's gated fetch (web-data
gate, watch_gate.check_url, the source's hosts, at most 2 requests, 10 s
each); a local source's fetch refuses every URL. `ctx` is the caller's dict,
handed over unchanged ({} by default); a source starts a subprocess or reads
a runtime file outside its root only when ctx.get("live") is true.

Loader rule (as tools/loop_steps): each file is imported as
watch_sources.<stem> through importlib.import_module; this folder is never
put on sys.path, so a source named like a tools module never shadows it.
"""

import importlib
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def load(directory=None, errors=None):
    """The source modules of `directory` (default: this folder) in file-name
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
            if old is not None and not _same(getattr(old, "__file__", ""), path):
                del sys.modules[name]
            try:
                mods.append(importlib.import_module(name))
            except Exception as exc:  # noqa: BLE001 - a broken source never stops the tick
                sys.modules.pop(name, None)
                if errors is not None:
                    errors.append((path.stem, exc))
    finally:
        __path__[:] = saved
    return mods
