"""KINDLER-STORE (decision 0081 points 7, 11 and 17): the Kindler tabs
store and its token-gated tab route, through the plug seam (decision
0056).

attach(core) makes one theorycraft.genstore.GenStore per core
(core.gen_builds, ops/runtime/gen_builds.json), its jsonfile.Saver in
core.savers["genbuilds"] (the core's store clock; plug/stores.py shows
the one Checks row while it is unsaved), a tick that retries an unsaved
save with the Saver's back-off, and a run history clear hook: Clear run
history empties the tabs file too (decision 0036).

GET /api/gen-builds answers the tab view. POST /api/gen-builds takes one
change a click makes, {"op": ...}:

    add     {"label"?, "class"?, "league"?}   a new tab at the end, shown
    rename  {"id", "label"}                   "" = the default label
    move    {"id", "dir": "left" | "right"}
    close   {"id"}                            the page confirms inline first
    show    {"id"}
    set     {"id", "class"?, "league"?, "toggles"?, "template"?, "follow"?}

and answers the new view plus "saved" (false while the change waits for
its retry; it is kept in memory). A refused change is a 400 with the
player's sentence. The result summary is written only by the engine
(GenStore.set_result), never by the route. Both run behind the handler's
Host / Origin / Sec-Fetch-Site / token guard; the body is capped at the
handler's MAX_BODY (4096). Saved on every change; nothing is sent to the
game or anywhere else.
"""

import logging
import time

from .. import jsonfile
from ..theorycraft import genstore

ORDER = 100
SAVER = "genbuilds"
SAVE_FAILED = "AshLight couldn't save your Kindler tabs."
OPS = ("add", "rename", "move", "close", "show", "set")
DIRS = {"left": -1, "right": 1}

log = logging.getLogger("al.genbuilds")


def attach(core):
    """One store per core, its Saver, its retry tick and the clear hook."""
    store = genstore.GenStore(genstore.default_path(core.runtime))
    core.gen_builds = store
    saver = jsonfile.Saver(store.save, clock=lambda: getattr(
        core, "store_clock", time.monotonic)())
    savers = getattr(core, "savers", None)
    if savers is None:
        savers = core.savers = {}
    savers[SAVER] = saver
    core.add_tick("tick_gen_builds", lambda: tick(core))
    history = getattr(core, "history", None)
    hooks = getattr(history, "on_clear", None)
    if hooks is not None:
        hooks.append(lambda: clear(core))


def tick(core):
    """Retry an unsaved change (back-off in the Saver). True when nothing
    is left unsaved."""
    saver = core.savers.get(SAVER)
    return True if saver is None else saver.flush()


def _op(core, fn):
    """Run one store change; a failed write keeps the change in memory and
    marks the Saver. (result, saved)."""
    try:
        return fn(), True
    except OSError as exc:
        log.warning("Kindler tabs not saved yet: %s", type(exc).__name__)
        core.savers[SAVER].mark()
        return None, False


def clear(core):
    """Clear run history: empty the tabs (a failed write is retried)."""
    return _op(core, core.gen_builds.clear)[1]


def _store(req):
    core = req.server.core
    if getattr(core, "gen_builds", None) is None:  # attach did not run
        attach(core)
    return core, core.gen_builds


def get_gen_builds(req, query, extra):
    _core, store = _store(req)
    return req._json(200, store.view(), extra)


def _change(store, body):
    """The store call of one POST body; raises GenError when refused."""
    op = body.get("op")
    if op not in OPS:
        raise genstore.GenError(genstore.BAD_TEXT)
    allowed = {"add": {"op", "label", "class", "league"},
               "rename": {"op", "id", "label"}, "move": {"op", "id", "dir"},
               "close": {"op", "id"}, "show": {"op", "id"},
               "set": {"op", "id", "class", "league", "toggles", "template", "follow"}}[op]
    if set(body) - allowed:
        raise genstore.GenError(genstore.BAD_TEXT)
    tab_id = body.get("id")
    if op != "add" and not isinstance(tab_id, str):
        raise genstore.GenError(genstore.BAD_TEXT)
    if op == "add":
        return lambda: store.add(body.get("label"), body.get("class"), body.get("league"))
    if op == "rename":
        return lambda: store.rename(tab_id, body.get("label"))
    if op == "move":
        step = DIRS.get(body.get("dir")) if isinstance(body.get("dir"), str) else None
        if step is None:
            raise genstore.GenError(genstore.BAD_TEXT)
        return lambda: store.move(tab_id, step)
    if op == "close":
        return lambda: store.close(tab_id)
    if op == "show":
        return lambda: store.show(tab_id)
    fields = {k: v for k, v in body.items() if k not in ("op", "id")}
    return lambda: store.update(tab_id, fields)


def post_gen_builds(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    core, store = _store(req)
    try:
        fn = _change(store, body)
        _result, saved = _op(core, fn)
    except genstore.GenError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    return req._json(200, dict(store.view(), saved=saved), extra)


ROUTES = {
    ("GET", "/api/gen-builds"): get_gen_builds,
    ("POST", "/api/gen-builds"): post_gen_builds,
}
