"""REVIEW-GH (operator order 2026-11-27; decision 0088): the GitHub page
watcher. Once every 7 days the main-checkout tick reads the project
repository's public page metadata and files one review-lane row,
REVIEW-GH-<YYYYMMDD>, that asks for a six-lens review (UI/UX, visual,
readability, comprehension, ease of use, ease of setup) of the README,
the player guide and the .github templates.

A network source on api.github.com through the same gh path and web-data
gate as the Dependabot watch (AUTO-20, tools/watch_sources/dependabot.py):
the frame never calls it while web data is off, the check raises
WebDataOff itself, the real gh starts only when ctx["live"] is true (the
main checkout's tick, never a lane), every URL passes
watch_gate.check_url before any process, and gh sends the AshLight
User-Agent. Tests inject ctx["gh"](argv, cwd) -> (returncode, stdout).

Four metadata reads, no file content:
- repos/<R>: description, topics, homepage, has_discussions;
- repos/<R>/releases?per_page=10: the newest non-draft tag;
- repos/<R>/commits?path=README.md&per_page=1: the last commit that
  touched the README (its sha stands for the README version; the
  /readme endpoint serves file content and stays refused by the gate);
- repos/<R>/community/profile: health percentage and the missing
  community files (decision 0069 amendment 2026-11-27).

The lane has no gh, so the snapshot rides in the row's tokens (short
words only, ops/loop/watch_rows/github-page.json).

Filing: every run (7 days apart) yields one finding keyed
'review:<YYYYMMDD>', except when an earlier REVIEW-GH row is still open
and nothing moved since the last filed row (README commit, release tag,
homepage, missing files): then nothing is filed and the open row stands.
The 'why' token names the drift: readme, release (moved since the last
filed row), homepage (empty), community (a file missing); 'first' with no
earlier row, else 'weekly'. Filing itself is tools/watch_file.py's (HALT,
3 a local day per kind, the soft budget gate). Python stdlib only.
"""

import datetime as _dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import watch_gate  # noqa: E402
from watch_sources import ci_issues, dependabot  # noqa: E402

NAME = "github-page"
KIND = "ghreview"
ROW_PREFIX = "REVIEW-GH-"
API = "https://api.github.com/repos/"
REPO_TAIL = ""
RELEASES_TAIL = "/releases?per_page=10"
README_TAIL = "/commits?path=README.md&per_page=1"
COMMUNITY_TAIL = "/community/profile"
WEEK_S = 7 * 24 * 3600
SHA_RX = re.compile(r"[0-9a-f]{40}")
TAG_RX = re.compile(r"v[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:-[0-9A-Za-z.]{1,8})?")
# community/profile "files" key -> the short word the row shows.
COMMUNITY = (("readme", "readme"), ("license", "license"),
             ("contributing", "contributing"), ("code_of_conduct", "conduct"),
             ("issue_template", "issues"), ("pull_request_template", "pr"))
DRIFT_KEYS = ("readme", "release", "homepage", "missing")
# The snapshot words the row carries (health and disc stay in the state).
ROW_KEYS = ("readme", "release", "homepage", "desc", "topics", "missing")


def _uw():
    import upstream_watch
    return upstream_watch


def read(runner, root, repo, tail, shape):
    """One gated gh read of API + repo + tail; the parsed JSON of `shape`."""
    uw = _uw()
    url = API + repo + tail
    watch_gate.check_url(SOURCE, url)  # UrlNotAllowed before any process
    ua = "User-Agent: " + watch_gate.webfetch.user_agent(watch_gate.purpose(SOURCE))
    argv = ["api", "--method", "GET", "-H", "Accept: application/vnd.github+json",
            "-H", ua, url[len("https://api.github.com/"):]]
    code, text = runner(argv, Path(root))
    what = tail.split("?")[0] or "/"
    if code != 0:
        raise uw.SourceError("status", f"gh api exited {code} for {what}")
    try:
        doc = json.loads(text or "")
    except (ValueError, TypeError):
        raise uw.SourceError("shape", f"gh api output is not JSON for {what}") from None
    if not isinstance(doc, shape):
        raise uw.SourceError("shape", f"gh api output has the wrong shape for {what}")
    return doc


def snapshot(meta, releases, commits, profile):
    """The short-word page snapshot of the four reads."""
    tag = "none"
    for rel in releases:
        if isinstance(rel, dict) and rel.get("draft") is not True:
            name = rel.get("tag_name")
            tag = name if isinstance(name, str) and TAG_RX.fullmatch(name) else "other"
            break
    sha = "none"
    if commits and isinstance(commits[0], dict) and isinstance(commits[0].get("sha"), str):
        full = commits[0]["sha"].lower()
        sha = full[:12] if SHA_RX.fullmatch(full) else "other"
    topics = meta.get("topics")
    topics = [t for t in topics if isinstance(t, str)] if isinstance(topics, list) else []
    files = profile.get("files") if isinstance(profile.get("files"), dict) else {}
    missing = [word for key, word in COMMUNITY if not files.get(key)]
    health = profile.get("health_percentage")
    if isinstance(health, bool) or not isinstance(health, int) or not 0 <= health <= 100:
        health = 0
    desc = meta.get("description")
    home = meta.get("homepage")
    return {
        "readme": sha,
        "release": tag,
        "homepage": "set" if isinstance(home, str) and home.strip() else "empty",
        "missing": ".".join(missing) if missing else "none",
        "health": str(health),
        "topics": str(min(len(topics), 99)),
        "desc": "set" if isinstance(desc, str) and desc.strip() else "empty",
        "disc": "on" if meta.get("has_discussions") is True else "off",
    }


def drift(snap, filed):
    """The drift words of `snap` against the last filed snapshot (or None)."""
    out = []
    if filed:
        out += [k for k in ("readme", "release") if snap[k] != filed.get(k)]
    if snap["homepage"] == "empty":
        out.append("homepage")
    if snap["missing"] != "none":
        out.append("community")
    return out


def open_review(root):
    """True when an earlier REVIEW-GH row is still open (ROADMAP.md or a
    docs/roadmap/new/ file, done files applied)."""
    import roadmap
    try:
        rows = roadmap.load_rows(root)
    except (OSError, ValueError):
        return False
    return any(r["open"] and r["id"].startswith(ROW_PREFIX) for r in rows)


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = dependabot._root(ctx)
    if root is None:
        return []
    if not watch_gate.web_data_on(root):
        raise watch_gate.WebDataOff("web data is off (opt-in setting web_data)")
    repo = ci_issues.repository(ctx)
    runner = dependabot._runner(ctx)
    old = state.get("data") if isinstance(state.get("data"), dict) else {}
    filed = old.get("filed") if isinstance(old.get("filed"), dict) else None
    if repo is None or runner is None:
        state["data"] = dict(old, idle="no github.com remote or no gh runner")
        return []
    meta = read(runner, root, repo, REPO_TAIL, dict)
    releases = read(runner, root, repo, RELEASES_TAIL, list)
    commits = read(runner, root, repo, README_TAIL, list)
    profile = read(runner, root, repo, COMMUNITY_TAIL, dict)
    snap = snapshot(meta, releases, commits, profile)
    words = drift(snap, filed)
    moved = filed is None or any(snap[k] != filed.get(k) for k in DRIFT_KEYS)
    data = {"last": snap}
    if filed is not None:
        data["filed"] = filed
    if not moved and open_review(root):
        data["skipped"] = "an earlier REVIEW-GH row is still open"
        state["data"] = data
        return []
    day = _dt.datetime.fromtimestamp(now).strftime("%Y%m%d")
    why = "-".join(words) if words else ("first" if filed is None else "weekly")
    data["filed"] = dict(snap, day=day)
    state["data"] = data
    tokens = {k: snap[k] for k in ROW_KEYS}
    tokens["why"] = why
    return [{"kind": KIND, "key": f"review:{day}", "tokens": tokens}]


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": WEEK_S,
    "window": None,
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher github-page",
    "check": check,
}
