"""LOOP-CI-ISSUES (CI-WATCH tick half, F-150; decisions 0076 item 6, 0069):
read the CI watch workflow's key issues and fail over when CI is silent.

A network source on api.github.com, gated on web data like every new
source. The repository address comes from the checkout's own remote, never
a tracked constant: ctx["remote_url"] when given (tests), else
`git remote get-url origin` of this checkout, only when ctx["live"] is
true. No address (or not a github.com address) means no request and
nothing filed.

The frame calls it at most every CADENCE_S (3 h) and allows 2 requests a
run. Inside, its own timers (kept in its state data) decide the read:
- the workflow state once a day (WORKFLOW_S): the workflow object
  /actions/workflows/watch.yml and its last successful run
  /actions/workflows/watch.yml/runs?status=success&per_page=1 (2 requests);
- otherwise, while CI is healthy, the open issues labelled al-watch once
  per 6 h (ISSUES_S; one request, one page of 100).

Trust: only an issue opened by the workflow's bot account
(watch_ci.BOT_LOGIN), never a pull request, whose whole body full-matches
watch_ci.BODY_RX ('AL-WATCH key=<source>:<key> v=1', nothing more) counts;
the key must also be a short word (watch_rows.SAFE_VALUE, no row tag word)
and the source name must fit the template's SRC token. A key already in
that source's own seen list in ops/runtime/watch/state.json is skipped
(the loop queued it itself). Each counted key is one finding of kind
cikey (template ops/loop/watch_rows/ci.json): row CI-WATCH-<SRC>-<KEYID>,
finding key '<source>:<key>' so the frame queues it once for all time.

Failover: CI is silent when the workflow state is not 'active' (disabled
by hand or for inactivity), the workflow is gone (404), or no successful
run is newer than SILENT_S (48 h). While silent, a run that makes no own
request runs ONE due ci-home source itself (oldest first, the source's own
cadence) through upstream_watch._bound_fetch, so the 2-request budget of
the run holds; its record lives in this source's data, its findings keep
their kind and are keyed '<source>:<key>' (the same key a CI issue would
carry). After BROKEN_S (7 days) of failover one finding of kind
watchbroken (template ops/loop/watch_rows/health.json, NAME CI, CAUSE
workflow), key 'broken:ci:<failover start>', is filed once per streak.

Fixtures only in tests (ctx["transport"] is the transport handed to a
failover source's fetch). Python stdlib only.
"""

import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NAME = "ci-issues"
KIND = "cikey"
BROKEN_KIND = "watchbroken"
HOUR_S = 3600
DAY_S = 24 * HOUR_S
CADENCE_S = 3 * HOUR_S
ISSUES_S = 6 * HOUR_S
WORKFLOW_S = DAY_S
SILENT_S = 48 * HOUR_S
BROKEN_S = 7 * DAY_S
API = "https://api.github.com/repos/"
WORKFLOW_FILE = "watch.yml"
LABEL = "al-watch"
ACTIVE = "active"
STATE_REL = Path("ops/runtime/watch/state.json")
KEY_MAX = 200
SRC_RX = re.compile(r"^[A-Z][A-Z0-9-]{0,25}$")  # = the template's SRC pattern
KEYID_MAX = 40
_SEG = r"[A-Za-z0-9_.-]{1,100}"
REMOTE_RXS = (
    re.compile(r"^https://github\.com/(" + _SEG + r")/(" + _SEG + r")/?$"),
    re.compile(r"^git@github\.com:(" + _SEG + r")/(" + _SEG + r")$"),
    re.compile(r"^ssh://git@github\.com/(" + _SEG + r")/(" + _SEG + r")/?$"),
)


# ---------------------------------------------------------------- address

def repo_of(url):
    """'<owner>/<repo>' of a github.com remote URL, else None."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    for rx in REMOTE_RXS:
        m = rx.match(url)
        if m:
            owner, repo = m.group(1), m.group(2)
            if repo.endswith(".git"):
                repo = repo[:-4]
            if not repo or owner in (".", "..") or repo in (".", ".."):
                return None
            return f"{owner}/{repo}"
    return None


def _git_remote():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def repository(ctx):
    """The repository of this checkout's remote, or None (nothing filed)."""
    if "remote_url" in ctx:
        return repo_of(ctx.get("remote_url"))
    if ctx.get("live"):
        return repo_of(_git_remote())
    return None


def _root(ctx):
    root = ctx.get("root")
    if root:
        return Path(root)
    return ROOT if ctx.get("live") else None


# ---------------------------------------------------------------- helpers

def _iso(t):
    import loop_base
    return loop_base.iso(t)


def _epoch(text):
    import loop_base
    try:
        return loop_base.epoch_of(text) if isinstance(text, str) and text else None
    except (ValueError, TypeError):
        return None


def _gh_time(text):
    """Epoch of a GitHub 'YYYY-MM-DDTHH:MM:SSZ' time, else None."""
    if not isinstance(text, str):
        return None
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _json(body):
    from upstream_watch import SourceError
    try:
        return json.loads((body or b"null").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SourceError("shape", "GitHub reply is not JSON") from None


def _due(stamp, now, every):
    last = _epoch(stamp)
    return last is None or now - last >= every


def src_token(source):
    tok = str(source).upper().replace("_", "-")
    return tok if SRC_RX.match(tok) else None


def keyid_of(key):
    kid = re.sub(r"[^A-Z0-9]+", "-", key.upper()).strip("-")
    if not kid or len(kid) > KEYID_MAX or kid.count("-") > 15:
        return None
    return kid


# ---------------------------------------------------------------- reads

def read_workflow(fetch, repo, now, data):
    """Two requests: the workflow object and its last successful run."""
    from upstream_watch import SourceError
    base = f"{API}{repo}/actions/workflows/{WORKFLOW_FILE}"
    status, _h, body = fetch(base)
    if status == 404:
        data.update(workflow_state="missing", last_success=None)
    elif status != 200:
        raise SourceError("status", f"workflow: HTTP {status}")
    else:
        doc = _json(body)
        state = doc.get("state") if isinstance(doc, dict) else None
        if not isinstance(state, str) or not re.fullmatch(r"[a-z_]{1,40}", state):
            raise SourceError("shape", "workflow state missing")
        data["workflow_state"] = state
        status, _h, body = fetch(base + "/runs?status=success&per_page=1")
        if status != 200:
            raise SourceError("status", f"workflow runs: HTTP {status}")
        doc = _json(body)
        runs = doc.get("workflow_runs") if isinstance(doc, dict) else None
        if not isinstance(runs, list):
            raise SourceError("shape", "workflow runs missing")
        last = None
        for run in runs:
            if isinstance(run, dict):
                t = _gh_time(run.get("created_at"))
                if t is not None and (last is None or t > last):
                    last = t
        data["last_success"] = _iso(last) if last is not None else None
    data["workflow_at"] = _iso(now)


def silent(data, now):
    """True when CI counts as silent (needs a workflow read first)."""
    if not data.get("workflow_at"):
        return False
    if data.get("workflow_state") != ACTIVE:
        return True
    last = _epoch(data.get("last_success"))
    return last is None or now - last >= SILENT_S


def key_of(issue):
    """'<source>:<key>' of an issue the tick trusts, else None."""
    import watch_ci
    if not isinstance(issue, dict) or "pull_request" in issue:
        return None
    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    if user.get("login") != watch_ci.BOT_LOGIN:
        return None
    body = issue.get("body")
    m = watch_ci.BODY_RX.fullmatch(body) if isinstance(body, str) else None
    return (m.group(1), m.group(2)) if m else None


def issue_finding(source, key):
    """The cikey finding of one trusted key, or None when it does not fit
    the template (never a long or tagged upstream string)."""
    import watch_rows
    if not watch_rows.SAFE_VALUE.fullmatch(key) or watch_rows.TAG_WORD_RX.search(key):
        return None
    if watch_rows.TAG_WORD_RX.search(source):
        return None
    tok, kid = src_token(source), keyid_of(key)
    if tok is None or kid is None:
        return None
    return {"kind": KIND, "key": f"{source}:{key}",
            "tokens": {"SRC": tok, "KEYID": kid, "src": source, "KEY": key}}


def read_issues(fetch, repo, now, data, seen_of):
    from upstream_watch import SourceError
    url = f"{API}{repo}/issues?labels={LABEL}&state=open&per_page=100"
    status, _h, body = fetch(url)
    if status != 200:
        raise SourceError("status", f"issues: HTTP {status}")
    doc = _json(body)
    if not isinstance(doc, list):
        raise SourceError("shape", "issue list expected")
    data["issues_at"] = _iso(now)
    found, keys = [], set()
    for issue in doc:
        got = key_of(issue)
        if got is None:
            continue
        source, key = got
        if (source, key) in keys or key in seen_of(source):
            continue
        rec = issue_finding(source, key)
        if rec is not None:
            keys.add((source, key))
            found.append(rec)
    return found


# ---------------------------------------------------------------- failover

def _registry(ctx):
    import upstream_watch
    srcs = ctx.get("watch_sources")
    if srcs is None:
        srcs = upstream_watch.discover()
    out = []
    for s in srcs:
        try:
            src = s if isinstance(s, dict) and "local" in s else upstream_watch.normalize(s)
        except upstream_watch.SourceInvalid:
            continue
        if src["home"] == "ci" and src["name"] != NAME:
            out.append(src)
    return out


def run_failover(root, now, ctx, data):
    """Run one due ci-home source; return its re-keyed findings."""
    import upstream_watch
    recs = data.get("failover") if isinstance(data.get("failover"), dict) else {}
    due = []
    for order, src in enumerate(_registry(ctx)):
        rec = recs.get(src["name"]) if isinstance(recs.get(src["name"]), dict) else {}
        last = _epoch(rec.get("last_run"))
        if last is None or now - last >= upstream_watch.cadence_at(src, now):
            due.append((last or 0.0, order, src))
    if not due:
        data["failover"] = recs
        return []
    _l, _o, src = min(due, key=lambda d: (d[0], d[1]))
    name = src["name"]
    entry = upstream_watch._entry(recs.get(name))
    view = dict(entry, seen=list(entry["seen"]), data=dict(entry["data"]))
    entry["last_run"] = _iso(now)
    fetch = upstream_watch._bound_fetch(root, src, ctx.get("transport"), [0])
    try:
        got = src["check"](view, now, fetch, ctx) or []
        if not isinstance(got, (list, tuple)):
            raise upstream_watch.SourceError("shape", "check must return a list")
    except Exception as exc:  # noqa: BLE001 - a failover source never breaks this one
        entry["fails"] = int(entry.get("fails") or 0) + 1
        entry["cause"] = upstream_watch._cause(exc)
        recs[name] = entry
        data["failover"] = recs
        return []
    entry.update(last_ok=_iso(now), fails=0, cause=None, etag=view.get("etag"),
                 data=view.get("data") if isinstance(view.get("data"), dict) else {})
    found = []
    for f in got:
        if not isinstance(f, dict) or not isinstance(f.get("key"), str):
            continue
        key = f"{name}:{f['key']}"
        if len(key) > KEY_MAX:
            continue
        found.append({"kind": f.get("kind"), "key": key, "tokens": f.get("tokens", {})})
    recs[name] = entry
    data["failover"] = recs
    return found


# ---------------------------------------------------------------- check

def _seen_reader(root):
    if root is None:
        return lambda _source: ()
    import upstream_watch
    recs = upstream_watch.load_state(root)["sources"]

    def seen_of(source):
        rec = recs.get(source)
        return rec.get("seen") or () if isinstance(rec, dict) else ()

    return seen_of


def check(state, now, fetch, ctx):
    ctx = ctx or {}
    repo = repository(ctx)
    if repo is None:
        return []
    root = _root(ctx)
    data = dict(state.get("data") or {})
    state["data"] = data
    found = []
    if _due(data.get("workflow_at"), now, WORKFLOW_S):
        read_workflow(fetch, repo, now, data)
    elif not silent(data, now):
        if _due(data.get("issues_at"), now, ISSUES_S):
            found += read_issues(fetch, repo, now, data, _seen_reader(root))
    elif root is not None:
        found += run_failover(root, now, ctx, data)
    if silent(data, now):
        start = data.get("failover_since")
        if not isinstance(start, str) or _epoch(start) is None:
            start = data["failover_since"] = _iso(now)
        if now - _epoch(start) >= BROKEN_S:
            stamp = re.sub(r"[^0-9]", "", start)[:14]
            found.append({"kind": BROKEN_KIND, "key": f"broken:ci:{stamp}",
                          "tokens": {"NAME": "CI", "CAUSE": "workflow"}})
    else:
        data.pop("failover_since", None)
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": CADENCE_S,
    "window": None,
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher ci-issues",
    "check": check,
}
