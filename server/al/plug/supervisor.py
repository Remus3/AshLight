"""RUN-SUPERVISOR-CLOCK (finding F-136): a Checks note for 10 minutes after
the keepalive supervisor restarted the core, through the plug seam
(decision 0056).

The supervisor (server/al/keepalive.py) records its last restart in
<runtime>/keepalive.json as "last_restart": {"at": wall time, "reason":
one of keepalive.RESTART_REASONS}. A first start ("no core running") and a
code reload are not restarts and are never recorded. The facts hook reads
that file only when its size or mtime changed; the row shows while the
restart is under SHOW_S old, e.g.

    AshLight restarted itself at 21:14 (it had stopped answering).

Nothing to fix (the core came back by itself), so the row is a note.
Reads only AshLight's own runtime file; no request, nothing sent.
"""

import time
from pathlib import Path

from .. import keepalive

ORDER = 100

ROW_ID = "supervisor_restart"
LABEL = "Keepalive"
SHOW_S = 600.0       # the note shows for 10 minutes after the restart
FUTURE_S = 60.0      # a record this far ahead of the clock (a clock step) hides

REASON_WORDS = {
    "hung": "it had stopped answering",
    "crash": "it had closed unexpectedly",
    "start-crash": "it closed while starting",
    "start-timeout": "it did not finish starting",
}


def restart_text(at, reason, localtime=time.localtime):
    """The note's sentence for a restart at wall time `at`."""
    clock = time.strftime("%H:%M", localtime(at))
    return f"AshLight restarted itself at {clock} ({REASON_WORDS[reason]})."


def facts(core, now):
    """{"supervisor_restart": {"at", "reason"} or None}; keepalive.json is
    re-read only when its size or mtime changed."""
    path = Path(core.runtime) / keepalive.STATE_FILE
    try:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    cache = getattr(core, "_supervisor_restart", None)
    if cache is None or cache[0] != key:
        cache = (key, keepalive.read_last_restart(path) if key else None)
        core._supervisor_restart = cache
    return {"supervisor_restart": cache[1]}


def rows(f, now):
    rec = f.get("supervisor_restart")
    if not isinstance(rec, dict) or rec.get("reason") not in REASON_WORDS:
        return None
    at = rec.get("at")
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    age = now - at
    if not -FUTURE_S <= age < SHOW_S:
        return None
    return {"id": ROW_ID, "label": LABEL, "status": "note",
            "detail": restart_text(at, rec["reason"])}
