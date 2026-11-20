"""RUN-METRICS-CORE (finding F-032, decision 0067): GET /api/debug.

A token-gated, pull-only view of AshLight's own counters (server/al/
metrics.py), under MAX_BODY bytes and never in the state snapshot or the
SSE stream. Nothing is sampled on a timer for it except one ring value per
core loop pass; every gauge is read at request time:

- tailer: core.tailer's lines, bytes, resets, dropped_lines, running
  (null while no tailer runs);
- lines: Client.txt lines fed to the parser, the ones it ignored and the
  ones whose event a listener failed on (core.feed_line, wrapped at
  attach); lines_read == events.log + ignored + failed;
- events: bus events by type (a bus listener), and "log", the ones parsed
  from Client.txt lines;
- sse: live subscribers (core.bus.subscriber_count) and frames / bytes
  written (http.py _sse_write);
- http: replies by route and status class and the 401 count (http.py
  _send); a route is a table key, never request text;
- loop: age of the last core loop pass and each tick's last ms (RUN-SEAMS);
- process: AshLight's own working set, CPU seconds and thread count (its
  own process handle only, decisions 0006 method 3 and 0029), own uptime;
- timings: the timing rings (n, last, p50, max in ms), "loop_ms" among them;
- counters: any other counter, emit counts among them.

No path, character or account name, chat or item text, pid or token is
in the body: every key is a code constant (an event type, a route key, a
tick name, a metric name) and every value a number, bool or null.
"""

import json
import time

from .. import metrics

ORDER = 900  # after the feature plugs: its tick reads the pass they ran in
PATH = "/api/debug"
MAX_BODY = 4096  # bytes, the cap the body is fitted under
VERSION = 1
TOP_EVENTS = 24  # event types listed; the rest fold into "other"
TOP_ROUTES = 16  # routes listed; the rest fold into "other"
TOP_COUNTERS = 16  # other counters listed
LOOP_RING = "loop_ms"

LINES_FED = "lines.fed"
LINES_IGNORED = "lines.ignored"
LINES_FAILED = "lines.failed"
EVENTS_LOG = "events.log"
EVENT_PREFIX = "event|"
HTTP_PREFIX = "http|"  # http|<route>|<class>
HTTP_401 = "http.401"
SSE_FRAMES = "sse.frames"
SSE_BYTES = "sse.bytes"
_FAMILIES = (EVENT_PREFIX, HTTP_PREFIX)
_NAMED = {LINES_FED, LINES_IGNORED, LINES_FAILED, EVENTS_LOG, HTTP_401,
          SSE_FRAMES, SSE_BYTES}


def _event_type(ev):
    t = ev.get("type") if isinstance(ev, dict) else None
    return t if isinstance(t, str) and metrics.KIND_RE.match(t) else "other"


def on_event(ev):
    """Bus listener: count the event by type, and the Client.txt ones."""
    metrics.inc(EVENT_PREFIX + _event_type(ev))
    if isinstance(ev, dict) and ev.get("source") == "client_log":
        metrics.inc(EVENTS_LOG)


def wrap_feed(feed):
    """core.feed_line counted: every line fed, the ones the parser ignored
    (no event) and the ones a listener failed on (re-raised as before)."""
    def feed_line(line):
        try:
            ev = feed(line)
        except Exception:
            metrics.inc(LINES_FED)
            metrics.inc(LINES_FAILED)
            raise
        metrics.inc(LINES_FED)
        if ev is None:
            metrics.inc(LINES_IGNORED)
        return ev
    feed_line.metrics_wrapped = True
    return feed_line


def attach(core):
    core.debug_t0 = time.monotonic()
    core.bus.add_listener(on_event)
    feed = core.feed_line
    if not getattr(feed, "metrics_wrapped", False):
        # an instance attribute: the tailer takes core.feed_line when it
        # starts, which is after attach (the tail of Core.__init__)
        core.feed_line = wrap_feed(feed)

    def tick_metrics():
        ms = getattr(core, "tick_ms", None) or {}
        total = sum(v for k, v in ms.items() if k != "tick_metrics"
                    and isinstance(v, (int, float)))
        metrics.timing(LOOP_RING, total)

    core.add_tick("tick_metrics", tick_metrics)


def _num(v):
    return v if isinstance(v, (bool, int, float)) or v is None else None


def _top(counts, n):
    """The n largest of {key: count}; the rest summed under "other"."""
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = dict(items[:n])
    rest = sum(v for _, v in items[n:])
    if rest:
        out["other"] = out.get("other", 0) + rest
    return out


def _tailer(core):
    t = getattr(core, "tailer", None)
    if t is None:
        return None
    return {"running": bool(getattr(t, "running", False)),
            "lines": _num(getattr(t, "lines", None)),
            "bytes": _num(getattr(t, "bytes", None)),
            "resets": _num(getattr(t, "resets", None)),
            "dropped_lines": _num(getattr(t, "dropped_lines", None))}


def _subscribers(core):
    count = getattr(getattr(core, "bus", None), "subscriber_count", None)
    if callable(count):
        count = count()
    return count if isinstance(count, int) else None


def _http(counts):
    routes = {}
    totals = {}
    for name, n in counts.items():
        parts = name.split("|")
        if len(parts) != 3:
            continue
        routes.setdefault(parts[1], {})[parts[2]] = n
        totals[parts[1]] = totals.get(parts[1], 0) + n
    keep = set(_top(totals, TOP_ROUTES)) - {"other"}
    out = {}
    for route in sorted(routes):
        dest = route if route in keep else "other"
        slot = out.setdefault(dest, {})
        for cls, n in routes[route].items():
            slot[cls] = slot.get(cls, 0) + n
    return out


def body(core, now=None):
    """The /api/debug document (a dict, fitted under MAX_BODY as JSON)."""
    now = time.monotonic() if now is None else now
    every = metrics.counters()
    events = {k[len(EVENT_PREFIX):]: v for k, v in every.items()
              if k.startswith(EVENT_PREFIX)}
    events["log"] = every.get(EVENTS_LOG, 0)
    loop_at = getattr(core, "loop_at", None)
    t0 = getattr(core, "debug_t0", None)
    tick_ms = {k: v for k, v in (getattr(core, "tick_ms", None) or {}).items()
               if isinstance(k, str) and metrics.NAME_RE.match(k)
               and isinstance(v, (int, float))}
    other = {k: v for k, v in every.items()
             if k not in _NAMED and not k.startswith(_FAMILIES)}
    doc = {
        "v": VERSION,
        "uptime_s": None if t0 is None else round(now - t0, 1),
        "process": metrics.own_process(),
        "tailer": _tailer(core),
        "lines": {"fed": every.get(LINES_FED, 0), "ignored": every.get(LINES_IGNORED, 0),
                  "failed": every.get(LINES_FAILED, 0)},
        "events": _top(events, TOP_EVENTS),
        "sse": {"subscribers": _subscribers(core), "frames": every.get(SSE_FRAMES, 0),
                "bytes": every.get(SSE_BYTES, 0)},
        "http": {"replies": _http({k: v for k, v in every.items()
                                   if k.startswith(HTTP_PREFIX)}),
                 "unauthorized": every.get(HTTP_401, 0)},
        "loop": {"age_s": None if loop_at is None else round(now - loop_at, 2),
                 "tick_ms": tick_ms},
        "timings": metrics.timings(),
        "counters": _top(other, TOP_COUNTERS),
    }
    return fit(doc)


def encode(doc):
    return json.dumps(doc, separators=(",", ":"))


# the parts dropped, in order, while the body is over MAX_BODY
_SHED = (("counters",), ("timings",), ("loop", "tick_ms"), ("http", "replies"),
         ("events",))


def fit(doc):
    """Drop the detail parts in _SHED order until the JSON is under
    MAX_BODY bytes; a dropped part reads {} and "trimmed" names it."""
    trimmed = []
    for path in _SHED:
        if len(encode(doc)) < MAX_BODY:
            break
        parent = doc
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = {}
        trimmed.append(".".join(path))
    if trimmed:
        doc["trimmed"] = trimmed
    return doc


def _get_debug(req, query, extra):
    return req._json(200, body(req.server.core), extra)


ROUTES = {("GET", PATH): _get_debug}
