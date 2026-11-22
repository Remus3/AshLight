"""RUN-EXPLAIN-ROWS (finding F-129): five cause rows in Checks, through the
plug seam (decision 0056). Checks stays the one player-facing health
surface; there is no second status page.

- Overlay on screen: why the overlay is shown or hidden, from the desktop
  client's own overlay-state.json (app/metrics.js "overlay_state", one of
  shown, hidden_user, hidden_idle, starting; RUN-EXPLAIN-OVERLAY-STATE).
  The sentences are app/overlay_gate.js HINTS word for word. A start that
  lasts STARTING_STUCK_S is a fix row. No row without a fresh file (the
  built-in Overlay row already says whether the client runs).
- Last item check: the item check key's last press, its age (in 5 minute
  steps under an hour, so the view does not change every minute) and its
  outcome, from the core's own `press` metric (RUN-METRICS-SITES). No row
  before the first press.
- Calc in use: the calc at run time (not only installed), from the
  bridge's own `calc` metric and its outcome counters. Only while the calc
  is on and after its first calculation.
- Log lines understood: from the parse ledger's in-memory class counters
  (RUN-LEDGER-WIRE). A fix row once UNDERSTOOD_FAIL_AT game log lines in a
  row gave no event. Chat-like and speech-like lines (players talking)
  and blank lines never count toward the run: they rightly give no event.
- Restarts: the keepalive's restarts of the core (keepalive.json
  last_restart, RUN-SUPERVISOR-CLOCK) counted over the last DAY_S. Each
  restart ends the core that saw the one before, so the times are kept in
  a small bounded file of AshLight's own (<runtime>/restart_history.json,
  at most MAX_RESTARTS times, none older than a day). Shown to players only
  from RESTARTS_SHOWN_AT restarts in a day; a single restart has the
  10 minute Keepalive note.

Every player sentence (labels, details, fixes) lives in the text module
server/al/text/explain.py (design gate; copy sheet
docs/design/copy/explain.md) and is imported here.

Every row is recomputed with the Checks view (Core.DIAG_TICK_S, 5 s); a
new fix row opens Checks by itself (web/checks.js). Only AshLight's own
files and counters are read: never the game, its window or Client.txt
text; no request; nothing sent.
"""

import json
import threading
import time
from pathlib import Path

from .. import jsonfile, keepalive, metrics
from . import supervisor
from ..text.explain import (  # noqa: F401  (re-exported: plug/explain.<name>)
    AGE_DAYS, AGE_HOURS, AGE_MIN, AGE_UNDER_5, CALC_FIX, CALC_WORDS,
    CALC_WORKING, DAY_S, FALLBACK, FIX_CALC_SETUP, FIX_CALC_SLOW,
    LABEL_CALC, LABEL_LINES, LABEL_OVERLAY, LABEL_PRESS, LABEL_RESTARTS,
    LINES_FAIL, LINES_FIX, LINES_PASS, OVERLAY_WORDS, PRESS_DETAIL,
    PRESS_FIX, PRESS_WORDS, RESTARTS_FIX, RESTARTS_TEXT, STUCK_FIX,
    STUCK_TEXT, age_words)

ORDER = 160

# -- overlay on screen (app/metrics.js overlay-state.json, schema 1)
OVERLAY_FILE = "overlay-state.json"
OVERLAY_SCHEMA = 1
OVERLAY_MAX_BYTES = 4096
OVERLAY_FRESH_S = 150.0   # 2.5 client periods, as budgetlog.CLIENT_FRESH_S
STARTING_STUCK_S = 120.0  # a start this long is a fix row
ROW_OVERLAY = "overlay_screen"

# -- last item check (core.eval_press: press|<outcome>)
ROW_PRESS = "item_key_press"

# -- calc in use (theorycraft/bridge.py: calc|<outcome>)
ROW_CALC = "calc_run"

# -- log lines understood (ledger class counters, logshapes.CLASSES)
ROW_LINES = "log_understood"
UNDERSTOOD_FAIL_AT = 500
EVENT_CLASSES = ("event", "near_miss")
QUIET_CLASSES = ("chat_like", "speech_like", "blank")  # never count

# -- restarts (keepalive.json last_restart, kept a day)
ROW_RESTARTS = "restarts"
HISTORY_FILE = "restart_history.json"
HISTORY_SCHEMA = 1
HISTORY_MAX_BYTES = 4096
MAX_RESTARTS = 16
FUTURE_S = 60.0           # a time this far ahead of the clock is dropped
RESTARTS_SHOWN_AT = 3
REASON_WORDS = supervisor.REASON_WORDS


# -- the core's own press and calc metrics (one process-wide subscriber)
_lock = threading.Lock()
_last = {"press": None, "calc": None}
_unsubscribe = None


def _on_emit(rec):
    kind = rec.get("kind")
    if kind not in _last:
        return
    ms = rec.get("ms")
    with _lock:
        _last[kind] = {"t": rec.get("t"), "outcome": rec.get("outcome"),
                       "ms": ms if isinstance(ms, (int, float)) and not isinstance(ms, bool)
                       else None}


def subscribe():
    """(Re)subscribe to the metric emits and forget the last press and
    calc. A metrics.reset() drops subscribers, so each core attach makes
    a fresh subscription."""
    global _unsubscribe
    with _lock:
        if _unsubscribe is not None:
            _unsubscribe()
        _last["press"] = _last["calc"] = None
        _unsubscribe = metrics.subscribe(_on_emit)


def last(kind):
    with _lock:
        rec = _last.get(kind)
        return dict(rec) if rec else None


def attach(core):
    subscribe()


# -- small helpers
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _parse_utc(text):
    import datetime
    if not isinstance(text, str) or len(text) > 40:
        return None
    try:
        dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def _read_small(path, cap):
    try:
        with open(path, "rb") as fh:
            data = fh.read(cap + 1)
    except OSError:
        return None
    if len(data) > cap:
        return None
    try:
        return json.loads(data.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None


def _stat_key(path):
    try:
        st = Path(path).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


# -- overlay on screen
def overlay_fact(core, now):
    """{"state", "updated", "since"} from a fresh schema 1 overlay-state.json,
    or None. "since" is the wall time the state was first seen."""
    path = Path(core.runtime) / OVERLAY_FILE
    key = _stat_key(path)
    cache = getattr(core, "_explain_overlay", None)
    if cache is None or cache[0] != key:
        doc = _read_small(path, OVERLAY_MAX_BYTES) if key else None
        got = None
        if (isinstance(doc, dict) and doc.get("schema") == OVERLAY_SCHEMA
                and doc.get("overlay_state") in OVERLAY_WORDS):
            at = _parse_utc(doc.get("updated"))
            if at is not None:
                got = (doc["overlay_state"], at)
        since = cache[2] if cache else None
        prev = cache[1] if cache else None
        if got is None:
            since = None
        elif prev is None or prev[0] != got[0]:
            since = now
        cache = (key, got, since)
        core._explain_overlay = cache
    got, since = cache[1], cache[2]
    if got is None or abs(now - got[1]) > OVERLAY_FRESH_S:
        return None
    return {"state": got[0], "updated": got[1], "since": since}


def overlay_row(fact, now):
    if not isinstance(fact, dict) or fact.get("state") not in OVERLAY_WORDS:
        return None
    state = fact["state"]
    since = _num(fact.get("since"))
    if state == "starting" and since is not None and now - since >= STARTING_STUCK_S:
        return {"id": ROW_OVERLAY, "label": LABEL_OVERLAY, "status": "fail",
                "detail": STUCK_TEXT, "fix": STUCK_FIX}
    status, text = OVERLAY_WORDS[state]
    return {"id": ROW_OVERLAY, "label": LABEL_OVERLAY, "status": status,
            "detail": text}


# -- last item check
def press_row(rec, now):
    if not isinstance(rec, dict) or rec.get("outcome") not in PRESS_WORDS:
        return None
    t = _num(rec.get("t"))
    if t is None:
        return None
    status, text = PRESS_WORDS[rec["outcome"]]
    row = {"id": ROW_PRESS, "label": LABEL_PRESS, "status": status,
           "detail": PRESS_DETAIL.format(age=age_words(now - t), text=text)}
    if status == "fail":
        row["fix"] = PRESS_FIX
    return row


# -- calc in use
def calc_row(rec, calc_on):
    if calc_on is not True or not isinstance(rec, dict):
        return None
    outcome = rec.get("outcome")
    if outcome not in CALC_WORDS:
        return None
    status, text = CALC_WORDS[outcome]
    if outcome == "ok":
        ms = _num(rec.get("ms"))
        if ms is None:
            text = CALC_WORKING
        else:
            text = text.format(sec=f"{max(0.1, ms / 1000.0):.1f}")
    row = {"id": ROW_CALC, "label": LABEL_CALC, "status": status, "detail": text}
    if status == "fail":
        row["fix"] = CALC_FIX[outcome]
    return row


# -- log lines understood
def lines_fact(core):
    """{"lines", "events", "since_event"} from the ledger's class counters,
    or None without them. since_event counts the lines (not chat, speech
    or blank) after the last event, measured between two calls."""
    wire = getattr(core, "ledger_wire", None)
    counters = getattr(wire, "counters", None)
    snap = getattr(counters, "snapshot", None)
    if not callable(snap):
        return None
    counts = snap()
    if not isinstance(counts, dict):
        return None
    events = sum(int(counts.get(c) or 0) for c in EVENT_CLASSES)
    lines = sum(int(v or 0) for c, v in counts.items() if c not in QUIET_CLASSES)
    prev = getattr(core, "_explain_lines", None)
    if prev is None:
        # with events already counted, where the last one fell is unknown
        prev = (events, 0 if events == 0 else lines)
    elif lines < prev[1] or events != prev[0]:
        prev = (events, lines)  # a new event (or new counters): a new run
    core._explain_lines = prev
    return {"lines": lines, "events": events, "since_event": lines - prev[1]}


def lines_row(fact):
    if not isinstance(fact, dict):
        return None
    lines, since = _num(fact.get("lines")), _num(fact.get("since_event"))
    if not lines or since is None:
        return None
    if since >= UNDERSTOOD_FAIL_AT:
        return {"id": ROW_LINES, "label": LABEL_LINES, "status": "fail",
                "detail": LINES_FAIL.format(n=UNDERSTOOD_FAIL_AT), "fix": LINES_FIX}
    if not fact.get("events"):
        return None  # not enough lines yet to tell
    return {"id": ROW_LINES, "label": LABEL_LINES, "status": "pass",
            "detail": LINES_PASS}


# -- restarts
def _clean_history(times, now):
    out = []
    for t in times if isinstance(times, list) else ():
        t = _num(t)
        if t is not None and now - DAY_S < t <= now + FUTURE_S and t not in out:
            out.append(float(t))
    out.sort()
    return out[-MAX_RESTARTS:]


def read_history(runtime):
    doc = _read_small(Path(runtime) / HISTORY_FILE, HISTORY_MAX_BYTES)
    if not isinstance(doc, dict) or doc.get("schema") != HISTORY_SCHEMA:
        return [], []
    reasons = doc.get("reasons")
    times = doc.get("at")
    if not (isinstance(times, list) and isinstance(reasons, list)
            and len(times) == len(reasons)):
        return [], []
    return list(times), list(reasons)


def restarts_fact(core, now):
    """{"count", "last": {"at", "reason"}} of the core restarts in the last
    DAY_S. A new keepalive.json last_restart is added to the history file
    (only when its size or mtime changed and the time is new)."""
    runtime = Path(core.runtime)
    ka = runtime / keepalive.STATE_FILE
    key = _stat_key(ka)
    cache = getattr(core, "_explain_restarts", None)
    if cache is None:
        times, reasons = read_history(runtime)
        cache = core._explain_restarts = {"key": None, "hist": list(zip(times, reasons))}
    if cache["key"] != key:
        cache["key"] = key
        rec = keepalive.read_last_restart(ka) if key else None
        if rec is not None and all(abs(rec["at"] - t) > 0.001 for t, _ in cache["hist"]
                                   if _num(t) is not None):
            cache["hist"].append((rec["at"], rec["reason"]))
            _save_history(core, cache, now)
    hist = [(float(t), r) for t, r in cache["hist"]
            if _num(t) is not None and r in REASON_WORDS
            and now - DAY_S < t <= now + FUTURE_S]
    hist.sort()
    if not hist:
        return {"count": 0, "last": None}
    at, reason = hist[-1]
    return {"count": len(hist), "last": {"at": at, "reason": reason}}


def _save_history(core, cache, now):
    keep = sorted({float(t): r for t, r in cache["hist"]
                   if _num(t) is not None and r in REASON_WORDS
                   and now - DAY_S < t <= now + FUTURE_S}.items())[-MAX_RESTARTS:]
    cache["hist"] = keep
    doc = {"schema": HISTORY_SCHEMA, "at": [round(t, 3) for t, _ in keep],
           "reasons": [r for _, r in keep]}
    try:
        jsonfile.write_text(Path(core.runtime) / HISTORY_FILE,
                            json.dumps(doc, separators=(",", ":")) + "\n")
    except (OSError, ValueError):
        pass  # kept in memory; written with the next restart


def restarts_row(fact, localtime=time.localtime):
    if not isinstance(fact, dict):
        return None
    n, rec = _num(fact.get("count")), fact.get("last")
    if n is None or n < RESTARTS_SHOWN_AT or not isinstance(rec, dict):
        return None
    at = _num(rec.get("at"))
    if at is None or rec.get("reason") not in REASON_WORDS:
        return None
    clock = time.strftime("%H:%M", localtime(at))
    return {"id": ROW_RESTARTS, "label": LABEL_RESTARTS, "status": "fail",
            "detail": RESTARTS_TEXT.format(n=int(n), clock=clock,
                                           why=REASON_WORDS[rec["reason"]]),
            "fix": RESTARTS_FIX}


# -- plug hooks
def facts(core, now):
    return {"explain_overlay": overlay_fact(core, now),
            "explain_press": last("press"),
            "explain_calc": last("calc"),
            "explain_lines": lines_fact(core),
            "explain_restarts": restarts_fact(core, now)}


def rows(f, now):
    out = [overlay_row(f.get("explain_overlay"), now),
           press_row(f.get("explain_press"), now),
           calc_row(f.get("explain_calc"), f.get("calc_on")),
           lines_row(f.get("explain_lines")),
           restarts_row(f.get("explain_restarts"))]
    return [r for r in out if r]
