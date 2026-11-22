"""RUN-REPORT-ROUTE (finding F-109, folded into RUN-VERDICTS-UI) and
RUN-REPORT-FIELDS (F-109, research 0051 R6, audit P8-7, folded F-185):
GET /api/report through the plug seam (decision 0056).

RUN-QUIET-FEED took the report out of the state snapshot: no report text
and no minute stamp ride in the snapshot any more, and the Checks rows
carry an absolute time where an age goes (the dashboard steps the ages at
5 minutes, web/checks.js). The report text is built only here, on the
player's click: the route reads the same local facts the Checks tick
reads (Core.diag_facts), makes the rows (diag.checks) and returns
diag.report() of them, which writes the ages in at the click's time and
draws every line from the allow-list in server/al/report.py: the build,
the OS build number, the Python and Electron versions, the counters, the
Checks rows, the last keepalive restart, the session's not counted mod
lines (plug/unknownitems.py) and, only while the ledger consent is on,
the ledger's confirmed masked shapes. Every free-text part goes through
the whole-word redactor (no path, user name, contact, token, character
name, address or chat; ruling J).

No log tails by default. GET /api/report?tails=1, sent only when the
player ticks the preview's second choice, adds the last lines of
AshLight's own core.log and overlay.log through the same redactor; never
Client.txt (decision 0067).

The reply is {"report": <ASCII text, LF>}. The dashboard shows it in a
read-only preview and writes the clipboard only inside the player's Copy
report click, synchronously, with the previewed text (decision 0014).
Nothing is uploaded, ever; nothing is kept.

facts() adds "_characters": every character name the state knows (the
current one, the parked ones of decision 0038 and the other players seen
this game run), so the report and the Checks view mask all of them, not
only the current one (research 0051 F7). A "_" key is never shown.

The route runs behind the handler's Host / Origin / Sec-Fetch-Site /
token guard (every plug route is under /api/); it reads no body.
"""

import time

from .. import VERSION, diag
from .. import report as report_mod

ORDER = 100
PATH = "/api/report"
TAILS_ARG = "tails"

_now = time.time  # tests pin the clock (the report header carries the minute)


def known_characters(core):
    """Every character name the state holds (memory only, never shown)."""
    st = getattr(core, "state", None)
    lock = getattr(st, "_lock", None)
    if st is None or lock is None:
        return []
    with lock:
        names = [getattr(st, "character", None)]
        names += list(getattr(st, "_parked", None) or ())
        names += sorted(getattr(st, "_others", None) or ())
    return [n for n in names if isinstance(n, str) and n.strip()]


def facts(core, now):
    return {"_characters": known_characters(core)}


def ledger_shapes(core):
    """The confirmed masked shapes, "kind: shape (n)", only while the
    ledger consent is on (decision 0071); [] otherwise."""
    wire = getattr(core, "ledger_wire", None)
    if wire is None:
        return []
    try:
        if not wire.on():
            return []
        with wire.lock:
            items = list(wire.ledger.shapes.items())
    except Exception:  # noqa: BLE001 - no shapes, never a failed report
        return []
    out = []
    for key, rec in items:
        if not (isinstance(key, tuple) and len(key) == 2 and isinstance(rec, list)
                and len(rec) >= 4 and rec[3] is True):
            continue
        out.append(f"{key[0]}: {key[1]} ({rec[0]})")
    return out[:report_mod.MAX_SHAPES]


def extra(core, facts):
    """The core's own report parts (report.compose `extra`)."""
    unknown = getattr(core, "unknown_items", None)
    return {"restart": facts.get("supervisor_restart"),
            "unknown": unknown.lines() if unknown is not None else [],
            "shapes": ledger_shapes(core)}


def build(core, now=None, tails=False):
    """The report text, made now from the core's local facts; `tails`
    (the player's second choice) adds AshLight's own two log tails."""
    now = _now() if now is None else now
    facts = core.diag_facts(now)
    rows = diag.checks(facts, now)
    log_dir = getattr(core, "overlay_log", None)
    got = (report_mod.log_tails(log_dir.parent)
           if tails and log_dir is not None else None)
    return diag.report(rows, VERSION, now, diag.secrets(facts),
                       extra=extra(core, facts), tails=got)


def get_report(req, query, extra_headers):
    tails = (query or {}).get(TAILS_ARG) == ["1"]
    return req._json(200, {"report": build(req.server.core, tails=tails)}, extra_headers)


ROUTES = {("GET", PATH): get_report}
