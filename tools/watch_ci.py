"""AUTO-19 (CI-WATCH, F-150; decision 0076): the CI half of the upstream
watcher. .github/workflows/watch.yml runs it once a day on a GitHub runner:

    python tools/watch_ci.py --sources <name>[,<name>...] [--dry-run]

Scope (decision 0076): decision 0013 governs the app and the dev host; this
entry runs only on a GitHub runner (GITHUB_ACTIONS 'true', else it refuses
before anything else), reads only URLs that pass watch_gate.check_url, never
a GGG or poe.ninja host, and is not a web_data path. It never commits, opens
no pull request and downloads no data file (no repoe-fork or tree file).

What it does, per run:
1. Runs each named registry source (tools/watch_sources/, AUTO-05) with its
   own fetch: watch_gate.check_url on the URL and on every redirect hop,
   then server/al/webfetch.request with the CI User-Agent (AshLight, its
   version, and the project's issues page built from the runner's own
   GITHUB_SERVER_URL and GITHUB_REPOSITORY, ruling Q-03), no cookie, at most
   MAX_REQUESTS per source. The runner's job token goes only to
   api.github.com. The runner keeps no state between runs, so each check
   starts from a fresh record; the comparison is with the tracked pins
   (app/package.json, config/electron_pin.json, config/tc_pins.json) and
   the tracked BASELINE below.
2. Turns the findings into keys `<source>:<key>` and syncs the repository's
   issues labelled al-watch: one open issue per key, body exactly
   `AL-WATCH key=<source>:<key> v=1`; an open issue of a source that ran
   clean this run whose key is no longer found is closed (gone). Only
   issues opened by the workflow's bot account with a body that matches the
   strict pattern are touched; every other issue is left alone. A source
   that failed this run keeps its issues (a failed read is not "gone").

Per source (the CI side; the sources themselves are never edited):
- pob-release: the registry source drives tc_drift through the tick's seam
  and runs a local trial, which a runner never does. CI reads the releases
  /latest metadata of the pinned repository (config/tc_pins.json pob2.repo)
  and finds the tag when it is newer than the pin.
- electron: the source's own check with ctx root = this checkout. The
  3-day age of a line head counts from the GitHub release's published_at
  (repository metadata), never from now, so the wait is kept, not cut.
- npm-audit: the source's own check against a scratch copy of app/
  package.json, app/package-lock.json and app/.npmrc; npm makes the one
  advisory request. The scratch root's config/local.json says only what
  this scope rule says: a runner is not a user host (decision 0076).
- repoe-fork, ggg-tree: the source's own check (metadata only); the found
  live_version is compared with BASELINE; a different version is a finding
  keyed by that version. A session moves BASELINE after acting on it.

Python stdlib only.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import upstream_watch  # noqa: E402
import watch_gate  # noqa: E402

from server.al import webfetch  # noqa: E402

LABEL = "al-watch"
LABEL_COLOR = "c5def5"
LABEL_TEXT = "AshLight upstream watcher key (CI-WATCH, decision 0076)"
BOT_LOGIN = "github-actions[bot]"
API_HOST = "api.github.com"
API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
MAX_REQUESTS = 6
ISSUE_PAGES = 5
KEY_MAX = 200
TITLE_PREFIX = "al-watch: "
BODY_RX = re.compile(r"^AL-WATCH key=([a-z][a-z0-9_-]{0,47}):([\x21-\x7e]{1,200}) v=1$")
REPO_RX = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SERVER_URL = "https://github.com"
RATE_STATUSES = (429, 503)

# The sources a CI run may name: the ones docs/plan/06 AUTO-19 lists, plus
# any registry source whose home is "ci" or "both". ggg-docs never runs here.
CI_SOURCES = ("pob-release", "pob-next", "repoe-fork", "ggg-tree", "electron", "npm-audit")
NEVER = ("ggg-docs",)

# Tracked baseline: the live versions the project last acted on. A session
# moves a value after it has acted on the finding (the issue then closes).
BASELINE = {
    "repoe-fork": {"live_version": "0.5.5.10"},
    "ggg-tree": {"live_version": "0.5.5"},
}

EXIT_OK, EXIT_FAIL, EXIT_REFUSED = 0, 1, 2


class Refused(Exception):
    """The run may not start (not a runner, bad name, missing variable)."""


# ---------------------------------------------------------------- runner

def on_runner(environ):
    return str(environ.get("GITHUB_ACTIONS", "")) == "true"


def repo_of(environ):
    repo = str(environ.get("GITHUB_REPOSITORY", ""))
    if not REPO_RX.match(repo):
        raise Refused("GITHUB_REPOSITORY is missing or malformed")
    return repo


def issues_page(environ):
    """https://github.com/<owner>/<repo>/issues from the runner's variables."""
    server = str(environ.get("GITHUB_SERVER_URL") or SERVER_URL).rstrip("/")
    if server != SERVER_URL:
        raise Refused("only github.com is supported")
    return f"{server}/{repo_of(environ)}/issues"


def user_agent(environ, name="issues"):
    """AshLight/<version> (...; ci watcher <name>) (contact: <issues page>)."""
    return webfetch.user_agent(f"ci watcher {name}", contact=issues_page(environ))


def api_base(environ):
    base = str(environ.get("GITHUB_API_URL") or API_BASE).rstrip("/")
    if base != API_BASE:
        raise Refused("only api.github.com is supported")
    return base


# ---------------------------------------------------------------- source fetch

def source_fetch(src, environ, transport, counter=None, limit=MAX_REQUESTS):
    """fetch(url, etag=None) -> (status, headers, body) for one source: the
    watch_gate.check_url rules on the URL and every hop, the CI User-Agent,
    no cookie, the job token only to api.github.com, at most `limit`
    requests. No web_data read: a runner is not a user host (decision 0076)."""
    counter = counter if counter is not None else [0]
    inner = transport or webfetch.make_transport(timeout=upstream_watch.REQUEST_TIMEOUT_S)
    token = str(environ.get("GITHUB_TOKEN") or "")
    ua = user_agent(environ, src["name"])

    def fetch(url, etag=None):
        parts = watch_gate.check_url(src, url)
        if counter[0] >= limit:
            raise upstream_watch.SourceError("network", f"request budget of {limit} spent")
        counter[0] += 1
        host = (parts.hostname or "").lower()

        def hop(method, hop_url, headers, body=None):
            hop_parts = watch_gate.check_url(src, hop_url)
            headers = dict(headers)
            if (hop_parts.hostname or "").lower() == API_HOST:
                headers["Accept"] = "application/vnd.github+json"
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            else:
                headers.pop("Authorization", None)
            if etag:
                headers["If-None-Match"] = str(etag)
            return inner(method, hop_url, headers, body)

        status, headers, body = webfetch.request("GET", url, {"User-Agent": ua}, [host],
                                                 fetch=hop)
        if status in RATE_STATUSES:
            raise upstream_watch.SourceError("rate-limit", f"HTTP {status}")
        return status, headers, body

    return fetch


def _json(fetch, url):
    status, _h, body = fetch(url)
    if status != 200:
        raise upstream_watch.SourceError("status", f"HTTP {status}")
    try:
        return json.loads((body or b"").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise upstream_watch.SourceError("shape", "response is not JSON") from None


def _epoch(text):
    import datetime as _dt
    if not isinstance(text, str):
        return None
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ---------------------------------------------------------------- CI checks

def _state(name):
    return {"etag": None, "seen": [], "data": json.loads(json.dumps(BASELINE.get(name, {})))}


def check_pob_release(src, fetch, now, root):
    import tc_drift
    import tc_pin
    pob = tc_pin.load_pins(Path(root) / "config" / "tc_pins.json")["pob2"]
    repo, pin = pob["repo"], pob["tag"]
    doc = _json(fetch, f"{API_BASE}/repos/{repo}/releases/latest")
    tag = doc.get("tag_name") if isinstance(doc, dict) else None
    if not isinstance(tag, str):
        raise upstream_watch.SourceError("shape", "release without tag_name")
    if tc_drift.compare(pin, tag) != "new":
        return []
    return [{"kind": "pobrelease", "key": tag, "tokens": {"tag": tag, "pin": pin}}]


def check_electron(src, fetch, now, root):
    from watch_sources import electron as el
    ctx = {"root": str(root)}
    state = _state(src["name"])
    found = src["check"](state, now, fetch, ctx)
    data = state.get("data") or {}
    head, pin = data.get("head"), data.get("pin")
    if head and pin and el.vtuple(head) and el.vtuple(head) > el.vtuple(pin) \
            and not any(f.get("kind") == el.KIND_BUMP for f in found):
        doc = _json(fetch, f"{API_BASE}/repos/electron/electron/releases/tags/v{head}")
        published = _epoch(doc.get("published_at") if isinstance(doc, dict) else None)
        if published is not None and published <= now:
            state = _state(src["name"])
            state["data"]["heads"] = {head: published}
            found = src["check"](state, now, fetch, ctx)
    return found


def check_npm_audit(src, fetch, now, root, runner=None):
    from watch_sources import npm_audit as na
    with tempfile.TemporaryDirectory(prefix="al-watch-ci-") as tmp:
        scratch = Path(tmp)
        (scratch / "app").mkdir()
        (scratch / "config").mkdir()
        for rel in ("app/package.json", "app/package-lock.json", "app/.npmrc"):
            path = Path(root) / rel
            if path.is_file():
                shutil.copyfile(path, scratch / rel)
        # A runner is not a user host (decision 0076): the opt-in this source
        # reads is the dev host's; the scratch root states the CI scope.
        (scratch / "config" / "local.json").write_text('{"web_data": true}\n', encoding="ascii")
        ctx = {"root": str(scratch), "npm_audit": runner or na.run_npm_audit}
        return src["check"](_state(src["name"]), now, fetch, ctx)


def check_versioned(src, fetch, now, root):
    """repoe-fork / ggg-tree: the source's own check, then live_version
    against BASELINE."""
    state = _state(src["name"])
    src["check"](state, now, fetch, {})
    live = (state.get("data") or {}).get("live_version")
    base = BASELINE.get(src["name"], {}).get("live_version")
    if not isinstance(live, str) or not live or live == base:
        return []
    return [{"kind": "version", "key": live, "tokens": {"version": live}}]


ADAPTERS = {
    "pob-release": check_pob_release,
    "electron": check_electron,
    "npm-audit": check_npm_audit,
    "repoe-fork": check_versioned,
    "ggg-tree": check_versioned,
}


def run_source(src, environ, transport, now, root, npm_runner=None):
    """(ok, keys, line). keys are the `<source>:<key>` strings found."""
    fetch = source_fetch(src, environ, transport)
    adapter = ADAPTERS.get(src["name"])
    try:
        if adapter is check_npm_audit:
            found = adapter(src, fetch, now, root, npm_runner)
        elif adapter is not None:
            found = adapter(src, fetch, now, root)
        else:
            found = src["check"](_state(src["name"]), now, fetch, {"root": str(root)})
        found = list(found or [])
    except Exception as exc:  # noqa: BLE001 - one broken source never stops the run
        return False, [], f"watch {src['name']}: failed: {type(exc).__name__}: {exc}"
    keys = []
    for f in found:
        key = f.get("key") if isinstance(f, dict) else None
        full = make_key(src["name"], key)
        if full is None:
            continue
        if full not in keys:
            keys.append(full)
    return True, keys, f"watch {src['name']}: ok, {len(keys)} finding(s)"


# ---------------------------------------------------------------- key protocol

def make_key(source, key):
    """'<source>:<key>' when it fits the strict pattern, else None."""
    if not isinstance(key, str):
        return None
    full = f"{source}:{key}"
    return full if BODY_RX.match(body_for(full)) else None


def body_for(full_key):
    """The whole issue body: exactly one line, no newline."""
    return f"AL-WATCH key={full_key} v=1"


def key_of(issue):
    """The key of an issue this protocol owns, or None (forged, edited or
    foreign issues are never ours)."""
    if not isinstance(issue, dict) or "pull_request" in issue:
        return None
    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    if user.get("login") != BOT_LOGIN:
        return None
    m = BODY_RX.match(issue.get("body") or "")
    return f"{m.group(1)}:{m.group(2)}" if m else None


# ---------------------------------------------------------------- issues API

class Issues:
    """The al-watch issues of one repository through webfetch.request,
    api.github.com only, the job token, the CI User-Agent."""

    def __init__(self, environ, transport=None):
        self.repo = repo_of(environ)
        self.base = api_base(environ)
        self.token = str(environ.get("GITHUB_TOKEN") or "")
        if not self.token:
            raise Refused("GITHUB_TOKEN is not set")
        self.ua = user_agent(environ)
        self.transport = transport or webfetch.make_transport()

    def call(self, method, path, doc=None, ok=(200, 201)):
        url = f"{self.base}/repos/{self.repo}{path}"
        headers = {"User-Agent": self.ua, "Accept": "application/vnd.github+json",
                   "Authorization": f"Bearer {self.token}",
                   "X-GitHub-Api-Version": API_VERSION}
        body = None
        if doc is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(doc).encode("utf-8")
        status, _h, data = webfetch.request(method, url, headers, [API_HOST], body=body,
                                            fetch=self.transport)
        if status not in ok:
            raise webfetch.FetchError(f"{method} {path.split('?')[0]}: HTTP {status}")
        try:
            return status, json.loads((data or b"null").decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return status, None

    def ensure_label(self):
        status, _doc = self.call("GET", f"/labels/{LABEL}", ok=(200, 404))
        if status == 404:
            self.call("POST", "/labels", {"name": LABEL, "color": LABEL_COLOR,
                                          "description": LABEL_TEXT})

    def open_issues(self):
        out = []
        for page in range(1, ISSUE_PAGES + 1):
            q = urllib.parse.urlencode({"labels": LABEL, "state": "open",
                                        "per_page": 100, "page": page})
            _s, doc = self.call("GET", f"/issues?{q}")
            if not isinstance(doc, list):
                raise webfetch.FetchError("issue list expected")
            out += [i for i in doc if isinstance(i, dict)]
            if len(doc) < 100:
                break
        return out

    def open(self, full_key):
        title = (TITLE_PREFIX + full_key)[:250]
        self.call("POST", "/issues", {"title": title, "body": body_for(full_key),
                                      "labels": [LABEL]})

    def close(self, number):
        self.call("PATCH", f"/issues/{int(number)}",
                  {"state": "closed", "state_reason": "completed"})


def sync(issues, found, ran_ok):
    """Open one issue per found key, close our open issues of the sources in
    `ran_ok` whose key is gone, close duplicates. Returns lines."""
    lines = []
    open_by_key = {}
    for issue in sorted(issues.open_issues(), key=lambda i: int(i.get("number") or 0)):
        key = key_of(issue)
        if key is None:
            continue
        if key in open_by_key:
            issues.close(issue["number"])
            lines.append(f"closed duplicate #{issue['number']} {key}")
            continue
        open_by_key[key] = issue
    for key in found:
        if key not in open_by_key:
            issues.open(key)
            lines.append(f"opened {key}")
    for key, issue in open_by_key.items():
        source = key.split(":", 1)[0]
        if source in ran_ok and key not in found:
            issues.close(issue["number"])
            lines.append(f"closed #{issue['number']} {key} (gone)")
    return lines


# ---------------------------------------------------------------- CLI

def names_of(values):
    out = []
    for value in values or ():
        for name in str(value).split(","):
            name = name.strip()
            if name and name not in out:
                out.append(name)
    return out


def select(names, sources):
    by_name = {s["name"]: s for s in sources}
    picked = []
    for name in names:
        src = by_name.get(name)
        if src is None:
            raise Refused(f"unknown source: {name}")
        if name in NEVER or (name not in CI_SOURCES and src["home"] not in ("ci", "both")):
            raise Refused(f"source {name} does not run in CI")
        picked.append(src)
    if not picked:
        raise Refused("no source named")
    return picked


def main(argv=None, environ=None, transport=None, out=None, now=None, root=None,
         directory=None, npm_runner=None):
    environ = os.environ if environ is None else environ
    out = out or sys.stdout
    root = Path(root) if root else ROOT
    if not on_runner(environ):
        print("watch_ci: refused: runs only on a GitHub runner (GITHUB_ACTIONS is not 'true')",
              file=out)
        return EXIT_REFUSED
    ap = argparse.ArgumentParser(prog="watch_ci.py")
    ap.add_argument("--sources", action="append", required=True,
                    help="registry source names, comma separated")
    ap.add_argument("--dry-run", action="store_true", help="print keys, write no issue")
    args = ap.parse_args(argv)
    try:
        issues_page(environ)
        picked = select(names_of(args.sources), upstream_watch.discover(directory))
        issues = None if args.dry_run else Issues(environ, transport)
    except Refused as exc:
        print(f"watch_ci: refused: {exc}", file=out)
        return EXIT_REFUSED
    now = time.time() if now is None else now
    found, ran_ok, failed = [], set(), []
    for src in picked:
        ok, keys, line = run_source(src, environ, transport, now, root, npm_runner)
        print(line, file=out)
        if ok:
            ran_ok.add(src["name"])
            found += [k for k in keys if k not in found]
        else:
            failed.append(src["name"])
            print(f"::warning::{line}", file=out)
    for key in found:
        print(f"key {key}", file=out)
    if issues is not None:
        try:
            issues.ensure_label()
            for line in sync(issues, found, ran_ok):
                print(line, file=out)
        except (webfetch.FetchError, OSError) as exc:
            print(f"::error::watch_ci: issue sync failed: {exc}", file=out)
            return EXIT_FAIL
    return EXIT_FAIL if failed and not ran_ok else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
