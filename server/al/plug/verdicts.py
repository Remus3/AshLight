"""RUN-VERDICTS-CORE: GET and POST /api/verdicts through the plug seam
(decision 0056; decision 0040 amendment 2026-11-18).

GET returns every 'Tried in game' check with its newest verdict.
POST {"check": <id>, "result": "worked" | "refused", "note": <optional
ASCII, at most 200 chars>} records one verdict in the runtime dir's
verdicts.json. Both run behind the handler's Host / Origin /
Sec-Fetch-Site / token guard (every plug route is under /api/); the POST
body is capped at the handler's MAX_BODY (4096). Dashboard clicks only:
nothing is sent to the game or anywhere else.
"""

from .. import verdicts

ORDER = 100
SAVE_FAILED = "AshLight couldn't save the verdict."


def attach(core):
    """One store per core, in its runtime dir."""
    core.verdicts = verdicts.VerdictStore(verdicts.default_path(core.runtime))


def _store(req):
    core = req.server.core
    store = getattr(core, "verdicts", None)
    if store is None:  # attach did not run (a core without the plug tail)
        store = verdicts.VerdictStore(verdicts.default_path(core.runtime))
        core.verdicts = store
    return store


def get_verdicts(req, query, extra):
    return req._json(200, _store(req).snapshot(), extra)


def post_verdicts(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    store = _store(req)
    try:
        row = store.add(body.get("check"), body.get("result"), body.get("note"))
    except verdicts.VerdictError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    except OSError:
        return req._json(500, {"error": SAVE_FAILED}, extra)
    return req._json(200, {"verdict": row, "verdicts": store.snapshot()}, extra)


ROUTES = {
    ("GET", "/api/verdicts"): get_verdicts,
    ("POST", "/api/verdicts"): post_verdicts,
}
