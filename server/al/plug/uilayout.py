"""UI-CARD-COLLAPSE (decision 0082 amendment 2026-11-19): the card layout
store and its token-gated routes, through the plug seam (decision 0056).

attach(core) makes one uilayout.UiLayout per core (core.ui_layout,
ops/runtime/ui_layout.json), its jsonfile.Saver in core.savers["uilayout"]
(plug/stores.py shows the one Checks row while it is unsaved) and a tick
that retries an unsaved save with the Saver's back-off. No Clear run
history hook: the layout is a view preference (decision 0082).

GET /api/ui/layout answers {"schema", "cards", "collapsed"}.
PUT /api/ui/layout takes {"collapsed": {"<card id>": true | false}} (a
partial map; unknown ids are dropped) and answers the new view plus
"saved" (false while the change waits for its retry; it is kept in
memory). A body of another shape is a 400. Both run behind the handler's
Host / Origin / Sec-Fetch-Site / token guard; the body is capped at the
handler's MAX_BODY (4096). Nothing is sent to the game or anywhere else.
"""

import logging
import time

from .. import jsonfile, uilayout

ORDER = 100
SAVER = "uilayout"

log = logging.getLogger("al.uilayout")


def attach(core):
    """One store per core, its Saver and its retry tick."""
    store = uilayout.UiLayout(uilayout.default_path(core.runtime))
    core.ui_layout = store
    saver = jsonfile.Saver(store.save, clock=lambda: getattr(
        core, "store_clock", time.monotonic)())
    savers = getattr(core, "savers", None)
    if savers is None:
        savers = core.savers = {}
    savers[SAVER] = saver
    core.add_tick("tick_ui_layout", lambda: tick(core))


def tick(core):
    """Retry an unsaved change (back-off in the Saver). True when nothing
    is left unsaved."""
    saver = core.savers.get(SAVER)
    return True if saver is None else saver.flush()


def _store(req):
    core = req.server.core
    if getattr(core, "ui_layout", None) is None:  # attach did not run
        attach(core)
    return core, core.ui_layout


def get_layout(req, query, extra):
    _core, store = _store(req)
    return req._json(200, store.view(), extra)


def put_layout(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    core, store = _store(req)
    saved = True
    try:
        store.update(body)
    except uilayout.LayoutError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    except OSError as exc:
        log.warning("card layout not saved yet: %s", type(exc).__name__)
        core.savers[SAVER].mark()
        saved = False
    return req._json(200, dict(store.view(), saved=saved), extra)


ROUTES = {
    ("GET", "/api/ui/layout"): get_layout,
    ("PUT", "/api/ui/layout"): put_layout,
}
