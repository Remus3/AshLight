"""RUN-REPORT-ROUTE (finding F-109, folded into RUN-VERDICTS-UI): GET
/api/report through the plug seam (decision 0056).

The Checks report is built on the player's click, not kept warm: the
route reads the same local facts the Checks tick reads
(Core.diag_facts), makes the rows (diag.checks) and returns
diag.report() of them, redacted exactly as the snapshot's copy is (no
path, user name, contact, token, character name or chat; ruling J).
The reply is {"report": <ASCII text, LF>}. The dashboard shows it in a
read-only preview and writes the clipboard only inside the player's
Copy report click, synchronously, with the previewed text (decision
0014). Nothing is uploaded, ever; nothing new is read.

The route runs behind the handler's Host / Origin / Sec-Fetch-Site /
token guard (every plug route is under /api/); it reads no body. The
snapshot keeps its own report until RUN-QUIET-FEED drops it.
"""

import time

from .. import VERSION, diag

ORDER = 100
PATH = "/api/report"

_now = time.time  # tests pin the clock (the report header carries the minute)


def build(core, now=None):
    """The report text, made now from the core's local facts."""
    now = _now() if now is None else now
    facts = core.diag_facts(now)
    rows = diag.checks(facts, now)
    return diag.report(rows, VERSION, now, diag.secrets(facts))


def get_report(req, query, extra):
    return req._json(200, {"report": build(req.server.core)}, extra)


ROUTES = {("GET", PATH): get_report}
