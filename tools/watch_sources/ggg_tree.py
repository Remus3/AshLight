"""LOOP-WATCH-META (W5 of docs/plan/06, AUTO-05, F-030; decision 0069): the
GGG passive tree export watcher.

What it reads: two GitHub API metadata requests per run on GGG's listed
PoE2 data-export repository grindinggear/poe2-skilltree-export (the
repository of server/al/theorycraft/snapshot.py GGG_TREE_POE2 and
HOST_PATH_PREFIX; GGG lists it as its one official PoE2 data export,
research 0037 F14): the `main` head commit (id, title, date) and the tag
names. The head is untagged most of the time (0.5.5 is; research 0037
F14), so a version comes from the head title or from a tag name.

What it never reads: the tree file (data.json), raw.githubusercontent or
any GGG host (decisions 0009, 0013; floor audit L3). It sends the frame's
webfetch.user_agent(<purpose>) and no cookie, and makes 0 requests while
web_data is off.

Preview rule: a head title holding the word Preview ("0.5.0 Preview",
pushed about 3.6 days before that launch, research 0037 F14) is noted in
state["data"] (version, title, preview true) and never treated as live:
live_version moves only on a non-preview head title or a tag. When the
first three parts of live_version change, one dive request is written as
the repoe-fork source does (repoe_fork.record). No row template and no
finding of its own (launch rows via AUTO-07, breaks via AUTO-18). The tree
snapshot still refreshes only at build or client start (decision 0009 as
amended), never from the loop.
"""

from watch_sources import repoe_fork as rf

REPO = "grindinggear/poe2-skilltree-export"
API = "https://api.github.com/repos/" + REPO
HEAD_URL = API + "/commits/main"
TAGS_URL = API + "/tags"
DIVE_TOPIC = "GGG passive tree export version"
# GGG's own repositories are not a dive source (decision 0050): the dive
# reads the Data Exports page and PoB-PoE2's repository metadata instead.
DIVE_URLS = ("https://www.pathofexile.com/developer/docs/data",
             "https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2")


def _newest_tag(doc):
    """{version, title, sha, date} of the highest-versioned non-preview tag,
    or None. GitHub does not promise an order, so the version decides."""
    if not isinstance(doc, list):
        raise rf._uw().SourceError("shape", "tag list expected")
    best = None
    for item in doc:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise rf._uw().SourceError("shape", "tag object expected")
        name = rf.clean(item["name"], 60)
        version, nums = rf.version_of(name)
        if not version or rf.PREVIEW_RX.search(name):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        sha = commit.get("sha") if isinstance(commit.get("sha"), str) else ""
        if best is None or nums > best[0]:
            best = (nums, {"version": version, "title": "tag " + name,
                           "sha": sha if rf.SHA_RX.match(sha) else "", "date": ""})
    return best[1] if best else None


def check(state, now, fetch, ctx):
    _s, _e, head_doc = rf.get_json(fetch, HEAD_URL)
    sha, title, date = rf.commit_fields(head_doc)
    _s, _e, tags_doc = rf.get_json(fetch, TAGS_URL)
    tag = _newest_tag(tags_doc)

    version, nums = rf.version_of(title)
    head = {"version": version, "title": title, "sha": sha, "date": date} if version else None
    head_live = head if head and not rf.PREVIEW_RX.search(title) else None

    live = head_live
    if tag and (live is None or rf.version_of(tag["version"])[1] > nums):
        live = tag
    # A Preview head is the newest title (noted), never live.
    newest = head if head and head_live is None else live
    rf.record(state, now, newest, live, DIVE_TOPIC, DIVE_URLS, ctx)
    return []


SOURCE = {
    "name": "ggg-tree",
    "home": "loop",
    "cadence_s": rf.DAY_S,
    "window": {"from": "2026-12-05", "to": "2026-12-24", "cadence_s": rf.DAY_S // 2},
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher GGG passive tree export version",
    "check": check,
}
