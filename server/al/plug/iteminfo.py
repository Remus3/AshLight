"""ITEM-INFO-CORE (decision 0083, decision 0082 part 1): GET /api/iteminfo
through the plug seam (decision 0056).

GET /api/iteminfo?name=<exact item name> answers server/al/iteminfo.py's
lookup: {"name", "fields", "sources"} from the local caches only (the
repoe-fork base_items and uniques snapshots, the poe.ninja price book
while web data is on). An unknown name is 200 with empty fields; a
missing, repeated, over-long or multi-line name is 400. The route runs
behind the handler's Host / Origin / Sec-Fetch-Site / token guard (every
plug route is under /api/); it reads no body and makes no request.

The lookup is made on the first call, not at core start, from the paths
the core already uses: the base list's cache folder (a test core's
runtime gamedata folder, else the sidecar cache) and the core's rates.
"""

import threading
from pathlib import Path

ORDER = 100
PATH = "/api/iteminfo"

_lock = threading.Lock()


def lookup_of(core):
    """The core's ItemInfo, made once on first use."""
    from .. import iteminfo  # lazy: this package imports nothing at load
    with _lock:
        info = getattr(core, "item_info", None)
        if info is None:
            bases = Path(core.base_names.path)
            info = iteminfo.ItemInfo(bases, bases.with_name(iteminfo.UNIQUES_NAME),
                                     rates=getattr(core, "rates", None))
            core.item_info = info
        return info


def get_iteminfo(req, query, extra):
    from ..text import iteminfo as text  # lazy, as lookup_of
    names = (query or {}).get("name") or []
    if len(names) > 1:
        return req._json(400, {"error": text.MANY_NAMES}, extra)
    if not names:
        return req._json(400, {"error": text.NO_NAME}, extra)
    try:
        reply = lookup_of(req.server.core).lookup(names[0])
    except ValueError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    return req._json(200, reply, extra)


ROUTES = {
    ("GET", PATH): get_iteminfo,
}
