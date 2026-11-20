"""WATCH-CORE (AUTO-05, F-030; decision 0069): the one tool that runs every
upstream source of tools/watch_sources/.

- discover(directory=None) -> sources: the registry, one SOURCE per file of
  tools/watch_sources/ in file-name order (contract: that folder's
  __init__.py). A broken file is skipped with one tick line.
- run_due(root, now, halted=False, fetch=None, directory=None, ctx=None)
  -> tick lines. Every due source of home loop or both runs:
    * every-tick group: local sources (hosts and urls empty) and the two
      settled sources (needs_web_data False, decisions 0044 and 0025, which
      keep their own reads through ctx); all of them run when due;
    * network group: every other source; at most ONE runs per tick, the
      oldest due first (never-run first, then file-name order), with at
      most 2 requests and 10 s per request. While web data is off a gated
      source is not called at all: 0 requests, and its state reads
      'idle: web data off'.
  A HALTed run still reads and queues (ruling Q-13); filing is the job of
  tools/watch_file.py, which never files while HALT exists.
- State: ops/runtime/watch/state.json
  {sources: {<name>: {last_run, last_ok, fails, etag, seen, idle, cause, data}}}
  (times are local ISO strings; seen holds every queued key for all time).
- Findings: ops/runtime/watch/pending.json
  {findings: [{source, kind, key, tokens, found}]}, queued once per
  (source, key) for all time.
- request_dive(root, topic, urls) writes ops/runtime/watch/dive_request.json
  {topic, urls, at} (read by the dive step, AUTO-13).

Every request goes through tools/watch_gate.fetch (LOOP-WATCH-GATE): the
web-data gate, repository metadata or the exact URLs the source lists,
webfetch.user_agent(<purpose>), no cookie. Writes are atomic
(loop_base.atomic_write) until the hardened write path of F-014 exists.

CLI:  python tools/upstream_watch.py run      one due pass now
      python tools/upstream_watch.py status   one line per source

Python stdlib only; a watcher costs 0 headless runs.
"""

import argparse
import copy
import datetime as _dt
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_base  # noqa: E402
import watch_gate  # noqa: E402
import watch_sources  # noqa: E402
import webfetch as dive_fetch  # noqa: E402  tools/webfetch.py: the dive allow-list

from server.al import webfetch  # noqa: E402

web_data_on = watch_gate.web_data_on  # re-exported (LOOP-WATCH-GATE)

WATCH_REL = Path("ops/runtime/watch")
STATE_REL = WATCH_REL / "state.json"
PENDING_REL = WATCH_REL / "pending.json"
DIVE_REL = WATCH_REL / "dive_request.json"
HALT_REL = loop_base.HALT_REL

HOMES = ("loop", "ci", "both")
LOOP_HOMES = ("loop", "both")
MAX_REQUESTS = 2
REQUEST_TIMEOUT_S = 10.0
IDLE_OFF = "idle: web data off"
CAUSES = ("network", "status", "shape", "rate-limit", "workflow")
RATE_STATUSES = (429, 503)
LINE_MAX = 200

NAME_RX = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
KIND_RX = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
TOKEN_RX = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY_MAX = 200
TOKEN_MAX = 300


class SourceError(webfetch.FetchError):
    """A source's read failed for a named cause (one of CAUSES)."""

    def __init__(self, cause, text=""):
        super().__init__(text or cause)
        self.cause = cause if cause in CAUSES else "shape"


class SourceInvalid(ValueError):
    """A SOURCE mapping breaks the registry contract."""


# ---------------------------------------------------------------- registry

def _str_list(value, what):
    if value is None:
        return []
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SourceInvalid(f"{what} must be a list of strings")
    if not all(isinstance(v, str) and v for v in value):
        raise SourceInvalid(f"{what} must be a list of strings")
    return list(value)


def _cadence(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise SourceInvalid(f"{what} must be a number of seconds >= 0")
    return float(value)


def _windows(value):
    if value is None:
        return []
    items = [value] if isinstance(value, dict) else value
    if not isinstance(items, (list, tuple)):
        raise SourceInvalid("window must be a mapping or a list of mappings")
    out = []
    for w in items:
        if not isinstance(w, dict):
            raise SourceInvalid("window must be a mapping or a list of mappings")
        start, end = w.get("from"), w.get("to")
        if not (isinstance(start, str) and DATE_RX.match(start)
                and isinstance(end, str) and DATE_RX.match(end)):
            raise SourceInvalid("window from / to must be YYYY-MM-DD")
        try:
            d0 = _dt.date.fromisoformat(start)
            d1 = _dt.date.fromisoformat(end)
        except ValueError as exc:
            raise SourceInvalid(f"window date: {exc}") from None
        if d1 < d0:
            raise SourceInvalid("window ends before it starts")
        out.append({"from": d0, "to": d1,
                    "cadence_s": _cadence(w.get("cadence_s"), "window cadence_s")})
    return out


def normalize(source):
    """The checked SOURCE mapping of a module (or a mapping) with defaults
    filled in; SourceInvalid on a contract break."""
    src = getattr(source, "SOURCE", source)
    if not isinstance(src, dict):
        raise SourceInvalid("no SOURCE mapping")
    name = src.get("name")
    if not isinstance(name, str) or not NAME_RX.match(name):
        raise SourceInvalid("name must match ^[a-z][a-z0-9_-]*$")
    home = src.get("home", "loop")
    if home not in HOMES:
        raise SourceInvalid(f"home must be one of {', '.join(HOMES)}")
    needs = src.get("needs_web_data", True)
    if not isinstance(needs, bool):
        raise SourceInvalid("needs_web_data must be true or false")
    check = src.get("check")
    if not callable(check):
        raise SourceInvalid("check must be callable")
    out = dict(src)
    out.update({
        "name": name,
        "home": home,
        "cadence_s": _cadence(src.get("cadence_s", 0), "cadence_s"),
        "windows": _windows(src.get("window")),
        "needs_web_data": needs,
        "hosts": [h.lower() for h in _str_list(src.get("hosts"), "hosts")],
        "urls": _str_list(src.get("urls"), "urls"),
        "check": check,
    })
    out["local"] = not out["hosts"] and not out["urls"]
    return out


def discover(directory=None, errors=None):
    """The registry: every source of `directory` (default
    tools/watch_sources/) in file-name order. A file that fails to import,
    breaks the contract or repeats a name is skipped; (stem, reason) goes
    to `errors` when a list is given."""
    load_errors = []
    mods = watch_sources.load(directory, load_errors)
    bad = [(stem, f"import failed: {type(exc).__name__}: {exc}") for stem, exc in load_errors]
    sources, names = [], set()
    for mod in mods:
        stem = mod.__name__.rsplit(".", 1)[-1]
        try:
            src = normalize(mod)
        except SourceInvalid as exc:
            bad.append((stem, str(exc)))
            continue
        if src["name"] in names:
            bad.append((stem, f"name {src['name']} is used twice"))
            continue
        names.add(src["name"])
        src["module"] = stem
        sources.append(src)
    if errors is not None:
        errors.extend(bad)
    return sources


def is_network(src):
    """True when the source is one of the one-per-tick network group."""
    return not src["local"] and src["needs_web_data"]


def cadence_at(src, now):
    """The source's cadence at `now`: a dated window's when `now`'s local
    date falls in one (the shortest of those), else cadence_s."""
    day = _dt.datetime.fromtimestamp(now).date()
    hits = [w["cadence_s"] for w in src["windows"] if w["from"] <= day <= w["to"]]
    return min(hits) if hits else src["cadence_s"]


# ---------------------------------------------------------------- state files

def _read(root, rel, key):
    doc = loop_base.read_json(Path(root) / rel, None)
    if not isinstance(doc, dict) or not isinstance(doc.get(key), (dict, list)):
        return None
    return doc


def _write(root, rel, doc):
    loop_base.atomic_write(Path(root) / rel, json.dumps(doc, indent=1, sort_keys=True) + "\n")


def _entry(raw=None):
    e = {"last_run": None, "last_ok": None, "fails": 0, "etag": None,
         "seen": [], "idle": None, "cause": None, "data": {}}
    if isinstance(raw, dict):
        for k in e:
            if k in raw:
                e[k] = raw[k]
    if not isinstance(e["seen"], list):
        e["seen"] = []
    if not isinstance(e["data"], dict):
        e["data"] = {}
    if isinstance(e["fails"], bool) or not isinstance(e["fails"], int) or e["fails"] < 0:
        e["fails"] = 0
    return e


def load_state(root):
    """ops/runtime/watch/state.json as {sources: {<name>: <record>}}; an
    absent or damaged file reads as no state."""
    doc = _read(root, STATE_REL, "sources")
    raw = doc["sources"] if doc and isinstance(doc["sources"], dict) else {}
    return {"sources": {k: _entry(v) for k, v in raw.items() if isinstance(k, str)}}


def save_state(root, st):
    _write(root, STATE_REL, {"sources": dict((st or {}).get("sources") or {})})


def pending(root):
    """The queued findings, oldest first ([] when none)."""
    doc = _read(root, PENDING_REL, "findings")
    found = doc["findings"] if doc and isinstance(doc["findings"], list) else []
    return [f for f in found if isinstance(f, dict)]


def set_pending(root, findings):
    _write(root, PENDING_REL, {"findings": list(findings or [])})


def request_dive(root, topic, urls, now=None):
    """Write ops/runtime/watch/dive_request.json {topic, urls, at}. Every URL
    must pass the dive allow-list of tools/webfetch.py (decision 0050);
    UrlNotAllowed (nothing written) otherwise."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("a dive request needs a topic")
    urls = _str_list(urls, "urls") if not isinstance(urls, str) else [urls]
    if not urls:
        raise ValueError("a dive request needs at least one URL")
    for url in urls:
        ok, why = dive_fetch.allowed(url)
        if not ok:
            raise webfetch.UrlNotAllowed(why)
    doc = {"topic": loop_base.ascii_text(topic.strip(), 200), "urls": urls,
           "at": loop_base.iso(time.time() if now is None else now)}
    _write(root, DIVE_REL, doc)
    return doc


# ---------------------------------------------------------------- one run

def _line(text):
    return loop_base.ascii_text(" ".join(str(text).split()), LINE_MAX)


def _since(entry):
    return loop_base.epoch_of(entry.get("last_run")) if entry.get("last_run") else None


def _due(src, entry, now):
    last = _since(entry)
    return last is None or now - last >= cadence_at(src, now)


def _bound_fetch(root, src, transport, counter):
    """The fetch handed to a source's check: fetch(url, etag=None) ->
    (status, headers, body)."""
    inner = transport or webfetch.make_transport(timeout=REQUEST_TIMEOUT_S)

    def fetch(url, etag=None):
        if src["local"]:
            raise webfetch.UrlNotAllowed("a local source makes no request")
        if counter[0] >= MAX_REQUESTS:
            raise SourceError("network", f"request budget of {MAX_REQUESTS} spent")
        host = ""
        try:
            host = (urllib.parse.urlsplit(url).hostname or "").lower()
        except (ValueError, AttributeError):
            pass
        if host not in src["hosts"] and url not in src["urls"]:
            raise webfetch.UrlNotAllowed(f"host not listed by the source: {host or '(none)'}")
        counter[0] += 1

        def hop(method, hop_url, headers, body=None):
            if etag:
                headers = dict(headers)
                headers["If-None-Match"] = str(etag)
            return inner(method, hop_url, headers, body)

        status, headers, body = watch_gate.fetch(root, src, url, transport=hop)
        if status in RATE_STATUSES:
            raise SourceError("rate-limit", f"HTTP {status}")
        return status, headers, body

    return fetch


def _cause(exc):
    if isinstance(exc, SourceError):
        return exc.cause
    if isinstance(exc, (webfetch.FetchError, OSError)):
        return "network"
    return "shape"


def _finding(src, raw, now):
    """A checked finding record, or (None, reason)."""
    if not isinstance(raw, dict):
        return None, "not a mapping"
    kind, key, tokens = raw.get("kind"), raw.get("key"), raw.get("tokens", {})
    if not isinstance(kind, str) or not KIND_RX.match(kind):
        return None, "bad kind"
    if not isinstance(key, str) or not key.strip() or len(key) > KEY_MAX or not key.isascii():
        return None, "bad key"
    if not isinstance(tokens, dict):
        return None, "tokens must be a mapping"
    for k, v in tokens.items():
        if not isinstance(k, str) or not TOKEN_RX.match(k):
            return None, "bad token name"
        if not isinstance(v, str) or len(v) > TOKEN_MAX or not v.isascii():
            return None, f"bad token value for {k}"
    return {"source": src["name"], "kind": kind, "key": key, "tokens": dict(tokens),
            "found": loop_base.iso(now)}, None


def _run_one(root, src, entry, now, transport, ctx, queue):
    """Run one source's check; update its record in place; return lines."""
    name = src["name"]
    counter = [0]
    view = copy.deepcopy(entry)
    entry["last_run"] = loop_base.iso(now)
    try:
        found = src["check"](view, now, _bound_fetch(root, src, transport, counter), ctx)
        if found is None:
            found = []
        if not isinstance(found, (list, tuple)):
            raise SourceError("shape", "check must return a list of findings")
    except webfetch.WebDataOff:
        was = entry.get("idle")
        entry["idle"] = IDLE_OFF
        return [] if was == IDLE_OFF else [_line(f"watch {name}: {IDLE_OFF}")]
    except Exception as exc:  # noqa: BLE001 - a broken source never stops the tick
        entry["fails"] = int(entry.get("fails") or 0) + 1
        entry["cause"] = _cause(exc)
        entry["idle"] = None
        return [_line(f"watch {name}: failed ({entry['cause']}, {entry['fails']} in a row): "
                      f"{type(exc).__name__}: {exc}")]
    entry.update(last_ok=loop_base.iso(now), fails=0, cause=None, idle=None,
                 etag=view.get("etag"),
                 data=view.get("data") if isinstance(view.get("data"), dict) else {})
    lines, new = [], 0
    seen = entry["seen"]
    for raw in found:
        rec, why = _finding(src, raw, now)
        if rec is None:
            lines.append(_line(f"watch {name}: finding dropped ({why})"))
            continue
        if rec["key"] in seen:
            continue
        seen.append(rec["key"])
        queue.append(rec)
        new += 1
    if new:
        lines.append(_line(f"watch {name}: {new} new finding(s) queued"))
    return lines


def run_due(root, now, halted=False, fetch=None, directory=None, ctx=None):
    """One due pass (module docstring). `fetch` is webfetch's transport
    fetch(method, url, headers, body) (default: the real one, 10 s);
    `ctx` goes to every check unchanged ({} when None). Returns tick lines."""
    root = Path(root)
    ctx = {} if ctx is None else ctx
    errors = []
    sources = [s for s in discover(directory, errors) if s["home"] in LOOP_HOMES]
    lines = [_line(f"watch: source {stem} skipped: {why}") for stem, why in errors]
    st = load_state(root)
    recs = st["sources"]
    queue = []
    web_on = web_data_on(root)
    changed = False

    candidates = []
    for order, src in enumerate(sources):
        entry = recs.setdefault(src["name"], _entry())
        if not is_network(src):
            if _due(src, entry, now):
                lines += _run_one(root, src, entry, now, fetch, ctx, queue)
                changed = True
            continue
        if web_on and entry.get("idle") == IDLE_OFF:
            entry["idle"] = None
            changed = True
        if not web_on:
            if entry.get("idle") != IDLE_OFF:
                entry["idle"] = IDLE_OFF
                changed = True
                lines.append(_line(f"watch {src['name']}: {IDLE_OFF}"))
            continue
        if _due(src, entry, now):
            candidates.append((_since(entry) or 0.0, order, src))
    if candidates:
        _last, _order, src = min(candidates, key=lambda c: (c[0], c[1]))
        lines += _run_one(root, src, recs[src["name"]], now, fetch, ctx, queue)
        changed = True

    if changed:
        save_state(root, st)
    if queue:
        set_pending(root, pending(root) + queue)
        if halted:
            lines.append(_line(f"watch: HALT: {len(queue)} finding(s) queued, nothing filed"))
    return lines


# ---------------------------------------------------------------- CLI

def status_lines(root, directory=None):
    errors = []
    sources = discover(directory, errors)
    recs = load_state(root)["sources"]
    web = "on" if web_data_on(root) else "off"
    out = [f"web data: {web}; pending findings: {len(pending(root))}"]
    for src in sources:
        e = recs.get(src["name"]) or _entry()
        kind = "local" if src["local"] else ("network" if is_network(src) else "settled")
        state = e.get("idle") or (f"failing ({e.get('cause')}, {e.get('fails')})"
                                  if e.get("fails") else "ok")
        out.append(_line(f"{src['name']} ({src['home']}, {kind}): {state}; "
                         f"last run {e.get('last_run') or 'never'}; "
                         f"last ok {e.get('last_ok') or 'never'}"))
    out += [_line(f"skipped {stem}: {why}") for stem, why in errors]
    return out


def main(argv=None, root=None, out=None, fetch=None, directory=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="upstream_watch.py",
                                 description="AshLight upstream watcher frame (decision 0069).")
    ap.add_argument("cmd", choices=("run", "status"))
    args = ap.parse_args(argv)
    root = Path(root) if root else ROOT
    if args.cmd == "status":
        lines = status_lines(root, directory)
    else:
        halted = (root / HALT_REL).exists()
        lines = run_due(root, time.time(), halted=halted, fetch=fetch, directory=directory)
        lines = lines or ["watch: nothing due"]
    for line in lines:
        out.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
