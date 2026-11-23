"""RUN-CHARACTER-PIN (F-157): the picker's 'This is my character' pin and
the live config tick, through the plug seam (decision 0056).

POST /api/character {"name": <a character AshLight has seen> | "" | null}
writes the "character" setting of config/local.json (the same local key
players could set by hand; "" frees it) and applies it at once
(Core.pin_character; decision 0038: a configured character never
switches). The route runs behind the handler's Host / Origin /
Sec-Fetch-Site / token guard (every plug route is under /api/); the body
is capped at the handler's MAX_BODY. One dashboard click: nothing is sent
to the game or anywhere else, and the name stays on this computer.

The tick (Core.tick_config) re-reads poll_ms and character from the
config file on every core loop pass and applies an edit of either
within that pass, with no restart.
"""

ORDER = 100
SAVE_FAILED = "AshLight couldn't save your character."
BAD_BODY = "Send a character name, or nothing to unpin."


def attach(core):
    """The live config tick, looked up on the core at each pass."""
    core.add_tick("tick_config")


def post_character(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    name = body.get("name")
    if name is not None and not isinstance(name, str):
        return req._json(400, {"error": BAD_BODY}, extra)
    try:
        view = req.server.core.pin_character(name)
    except ValueError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    except OSError:
        return req._json(500, {"error": SAVE_FAILED}, extra)
    return req._json(200, view, extra)


ROUTES = {
    ("POST", "/api/character"): post_character,
}
