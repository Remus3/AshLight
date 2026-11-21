"""AUTO-08 (WATCH-HEALTH, F-125; decision 0069): a broken watcher is itself
a finding.

A local source: it makes no request (hosts and urls are empty, so the
frame's fetch refuses every URL) and runs on every tick. It reads only the
frame's own state file ops/runtime/watch/state.json under the tree root it
is given (ctx["root"]; else this checkout, only when ctx["live"] is true;
with neither it reads nothing and finds nothing, so loop tests on scratch
roots stay hermetic).

For every other source of the registry (ctx["watch_sources"] when given,
else tools/upstream_watch.discover()):
- a source whose record reads 'idle: web data off' is never a failure here;
  the loop step tools/loop_steps/watch_health.py shows it as one checklist
  line;
- a source that failed (fails >= 1) and has had no good read for
  BROKEN_S (7 days), or for twice its cadence when that is longer (a weekly
  source is not broken after one missed read), gives one finding of kind
  watchbroken: row WATCH-BROKEN-<NAME>-<YYYYMMDD> (template
  ops/loop/watch_rows/health.json), tokens NAME (the registry name in upper
  case, '_' as '-') and CAUSE (the record's last cause, one of the frame's
  CAUSES). The 7 days run from last_ok, or, for a source that never read
  well, from the first time this source saw it failing (kept in its own
  data as first_bad). Key "broken:<name>:<streak start>", so the frame
  queues it once per broken streak for all time; a later streak (after a
  good read) can file again.

The three-failures tick line is the loop step's job (a source returns
findings, not lines). Filing, and the HALT check before any commit, is
tools/watch_file.py's. Python stdlib only.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NAME = "health"
KIND = "watchbroken"
DAY_S = 86400
BROKEN_S = 7 * DAY_S
STATE_REL = Path("ops/runtime/watch/state.json")
IDLE_OFF = "idle: web data off"
CAUSES = ("network", "status", "shape", "rate-limit", "workflow")
TOKEN_RX = re.compile(r"^[A-Z][A-Z0-9-]{0,25}$")  # = the template's NAME pattern


def _root(ctx):
    root = ctx.get("root")
    if root:
        return Path(root)
    return ROOT if ctx.get("live") else None


def token_of(name):
    """The NAME token of a registry name, or None when it does not fit."""
    tok = str(name).upper().replace("_", "-")
    return tok if TOKEN_RX.match(tok) else None


def records(root):
    """{name: record} of the frame's state file under root ({} when absent)."""
    import upstream_watch
    return upstream_watch.load_state(root)["sources"]


def registry(ctx):
    """[(name, cadence_s)] of the watcher registry."""
    srcs = ctx.get("watch_sources")
    if srcs is None:
        import upstream_watch
        srcs = upstream_watch.discover()
    out = []
    for s in srcs:
        if isinstance(s, dict) and isinstance(s.get("name"), str):
            out.append((s["name"], float(s.get("cadence_s") or 0)))
    return out


def threshold(cadence_s):
    return max(BROKEN_S, 2 * float(cadence_s or 0))


def _epoch(text):
    import loop_base
    return loop_base.epoch_of(text) if text else None


def check(state, now, fetch, ctx):
    ctx = ctx or {}
    root = _root(ctx)
    if root is None:
        return []
    import loop_base
    recs = records(root)
    data = dict(state.get("data") or {})
    first_bad = {k: v for k, v in (data.get("first_bad") or {}).items()
                 if isinstance(k, str) and isinstance(v, str)}
    found = []
    for name, cadence in registry(ctx):
        if name == NAME:
            continue
        rec = recs.get(name)
        if not isinstance(rec, dict) or rec.get("idle") == IDLE_OFF:
            first_bad.pop(name, None)
            continue
        fails = rec.get("fails") or 0
        if not fails:
            first_bad.pop(name, None)
            continue
        since_text = rec.get("last_ok")
        if not since_text:
            since_text = first_bad.setdefault(name, loop_base.iso(now))
        since = _epoch(since_text)
        tok = token_of(name)
        if since is None or tok is None or now - since < threshold(cadence):
            continue
        cause = rec.get("cause") if rec.get("cause") in CAUSES else "network"
        stamp = re.sub(r"[^0-9]", "", since_text)[:14] or "never"
        found.append({"kind": KIND, "key": f"broken:{name}:{stamp}",
                      "tokens": {"NAME": tok, "CAUSE": cause}})
    data["first_bad"] = first_bad
    state["data"] = data
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": 0,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [],
    "purpose": "dev: watcher health",
    "check": check,
}
