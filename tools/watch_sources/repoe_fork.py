"""LOOP-WATCH-META (W4 of docs/plan/06, AUTO-05, F-030; decision 0069): the
repoe-fork data watcher.

What it reads: ONE GitHub API metadata request per run, the newest commits
(titles, ids, dates) of the repoe-fork PoE2 data repository,
https://api.github.com/repos/repoe-fork/poe2/commits. That repository is
the source of the site server/al/theorycraft/snapshot.py REPOE_POE2 fetches
from: its GitHub metadata names https://repoe-fork.github.io/poe2/ as its
homepage, default branch master (read through tools/webfetch.py, accessed
2026-11-20; research 0037 RF-DATA, accessed 2026-11-17). The data
repository commits one "Version <x.y.z.w>" or "Export <x.y.z.w>" per game
client version (research 0037 F10).

What it never reads: a data file, the repoe-fork site, raw.githubusercontent
or any GGG host (decisions 0009, 0013; floor audit L3). It sends the frame's
webfetch.user_agent(<purpose>) and no cookie, and makes 0 requests while
web_data is off (the frame never calls a gated source then).

What it records: state["data"] = {version, title, preview, seen_at,
live_version, sha, date} (read by AUTO-07, the launch gate W11). version /
title / preview describe the newest versioned title; a title holding the
word Preview is noted and never moves live_version. When the first three
parts of live_version change, one dive request is written through
upstream_watch.request_dive (AUTO-13) into ctx["root"] (or, only when
ctx["live"] is true, the checkout root). No row template of its own: launch
rows come from AUTO-07, shape breaks from AUTO-18; check returns no finding.

The snapshot itself still refreshes only at build or client start (decision
0009 as amended), never from the loop.
"""

import re

REPO = "repoe-fork/poe2"
API = "https://api.github.com/repos/" + REPO
COMMITS_URL = API + "/commits"
DIVE_TOPIC = "repoe-fork data version"
DIVE_URLS = ("https://api.github.com/repos/repoe-fork/poe2",
             "https://api.github.com/repos/repoe-fork/repoe")
DAY_S = 24 * 3600
TITLE_MAX = 120

VERSION_RX = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})(?:\.(\d{1,4}))?(?:\.(\d{1,4}))?(?!\.?\d)")
PREVIEW_RX = re.compile(r"\bpreview\b", re.IGNORECASE)
SHA_RX = re.compile(r"^[0-9a-f]{40}$")


def version_of(text):
    """(version string, tuple of 4 ints) of the first version number in
    `text`, or (None, None)."""
    m = VERSION_RX.search(text or "")
    if not m:
        return None, None
    parts = [p for p in m.groups() if p is not None]
    nums = tuple(int(p) for p in parts) + (0,) * (4 - len(parts))
    return ".".join(parts), nums


def first_three(version):
    _v, nums = version_of(version or "")
    return nums[:3] if nums else None


def clean(text, limit=TITLE_MAX):
    """One ASCII line of at most `limit` characters."""
    line = str(text or "").splitlines()[0] if str(text or "").strip() else ""
    line = " ".join(line.split())
    return line.encode("ascii", "replace").decode("ascii")[:limit]


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def get_json(fetch, url, etag=None):
    """(status, etag, parsed JSON) of one metadata read; SourceError on a
    status other than 200 / 304 or a body that is not JSON."""
    import json
    uw = _uw()
    status, headers, body = fetch(url, etag=etag)
    if status == 304:
        return 304, etag, None
    if status != 200:
        raise uw.SourceError("status", f"HTTP {status}")
    new_etag = None
    for k, v in (headers or {}).items():
        if str(k).lower() == "etag":
            new_etag = str(v)
    try:
        return 200, new_etag, json.loads((body or b"").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise uw.SourceError("shape", "response is not JSON") from None


def commit_fields(item):
    """(sha, title, date) of one GitHub commit object; SourceError('shape')."""
    if not isinstance(item, dict) or not isinstance(item.get("commit"), dict):
        raise _uw().SourceError("shape", "commit object expected")
    c = item["commit"]
    who = c.get("committer") if isinstance(c.get("committer"), dict) else {}
    sha = item.get("sha") if isinstance(item.get("sha"), str) else ""
    date = who.get("date") if isinstance(who.get("date"), str) else ""
    return (sha if SHA_RX.match(sha) else ""), clean(c.get("message")), clean(date, 40)


def record(state, now, newest, live, topic, urls, ctx):
    """Store the newest versioned title and the newest live version in
    state["data"]; write one dive request when live_version's first three
    parts change (topic and urls go to the request). `newest` and `live` are
    {version, title, sha, date} or None. Returns the data mapping."""
    import loop_base
    data = state.get("data") if isinstance(state.get("data"), dict) else {}
    data = dict(data)
    old_live = data.get("live_version")
    if newest:
        preview = bool(PREVIEW_RX.search(newest["title"]))
        if (newest["version"], preview) != (data.get("version"), data.get("preview")):
            data["seen_at"] = loop_base.iso(now)
        data.update(version=newest["version"], title=newest["title"], preview=preview,
                    sha=newest.get("sha", ""), date=newest.get("date", ""))
    if live and old_live and version_of(live["version"])[1] < (version_of(old_live)[1] or ()):
        live = None  # live_version never goes back (an older tag behind a Preview head)
    if live and live["version"] != old_live:
        data["live_version"] = live["version"]
        data["live_seen_at"] = loop_base.iso(now)
        if old_live and first_three(old_live) != first_three(live["version"]):
            root = ctx.get("root") or (_uw().ROOT if ctx.get("live") else None)
            if root:
                _uw().request_dive(root, f"{topic} {old_live} -> {live['version']}",
                                   list(urls), now=now)
                data["dive_at"] = loop_base.iso(now)
    state["data"] = data
    return data


def check(state, now, fetch, ctx):
    status, etag, doc = get_json(fetch, COMMITS_URL, state.get("etag"))
    if status == 304:
        return []
    if not isinstance(doc, list):
        raise _uw().SourceError("shape", "commit list expected")
    newest = live = None
    for item in doc:  # newest first
        sha, title, date = commit_fields(item)
        version, _nums = version_of(title)
        if not version:
            continue
        rec = {"version": version, "title": title, "sha": sha, "date": date}
        if newest is None:
            newest = rec
        if not PREVIEW_RX.search(title):
            live = rec
            break
    state["etag"] = etag
    record(state, now, newest, live, DIVE_TOPIC, DIVE_URLS, ctx)
    return []


SOURCE = {
    "name": "repoe-fork",
    "home": "loop",
    "cadence_s": DAY_S,
    "window": {"from": "2026-12-05", "to": "2026-12-24", "cadence_s": DAY_S // 2},
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher repoe-fork data version",
    "check": check,
}
