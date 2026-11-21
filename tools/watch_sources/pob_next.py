"""LOOP-WATCH-POBNEXT (W3 of docs/plan/06; AUTO-05, F-030; decision 0069):
the PoB-PoE2 next-release watcher.

What it reads, weekly and only while web_data is on (the frame never calls
a gated source otherwise: 0 requests), at most two GitHub API metadata
requests of the repository named by config/tc_pins.json (pob2.repo, read
through tools/tc_pin.py load_pins, never a constant of its own):

- <api>/commits?sha=master&per_page=100: the master head commit id and date,
  and how many commits it is past the pinned commit (pob2.commit): the
  pin's position in that list, or "at least 100" when the pin is not in it;
- <api>/releases/latest: the newest release tag and its published date
  (404 = no release yet).

What it never reads: a source file, an archive, raw.githubusercontent or any
GGG host (decisions 0009, 0013; floor audit L3). The static rehearsal of a
new head stays a session act (tc_drift.py trial --ref <sha>, AUTO-12).

Findings:
- kind "pobnextmove" (template act note), key "move-<sha>": once per new
  master head that is past the pin. The frame turns it into one tick line;
  tick_line(n) is the text 'PoB master moved <n> commits past the pin'.
- kind "pobnext" (row TC-NEXT-<YYYYMMDD>, lane review, BLOCKED: session),
  key "tcnext-<YYYYMMDD>": when the head is past the pin and no release
  appeared for 28 days (with no release at all: 28 days since the head was
  first seen past the pin), at most once per 28 days (state data filed_at).

State data: {head_sha, head_date, n, n_more, release_tag, release_at,
moved_since, filed_at, release_etag}; the commits read keeps the frame's
etag. A 304 answer reuses the stored values, so the 28-day test still runs.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tc_pin  # noqa: E402

NAME = "pob-next"
KIND_MOVE = "pobnextmove"
KIND_ROW = "pobnext"
API = "https://api.github.com/repos/"
BRANCH = "master"
PER_PAGE = 100
DAY_S = 24 * 3600
WEEK_S = 7 * DAY_S
QUIET_S = 28 * DAY_S
N_MAX = 9999
SHA_RX = re.compile(r"^[0-9a-f]{40}$")
TAG_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$")


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def _loop_base():
    import loop_base
    return loop_base


def tick_line(n, more=False):
    """The W3 tick line text for a head `n` commits past the pin."""
    return f"PoB master moved {'at least ' if more else ''}{n} commits past the pin"


def _root(ctx):
    return Path(ctx["root"]) if ctx.get("root") is not None else ROOT


def pins(root):
    """(repo, pinned commit) from <root>/config/tc_pins.json via tc_pin."""
    try:
        doc = tc_pin.load_pins(Path(root) / "config" / "tc_pins.json")
    except tc_pin.PinError as exc:
        raise _uw().SourceError("shape", f"pin file: {exc}") from None
    pob = doc["pob2"]
    return pob["repo"], pob["commit"]


def urls(repo):
    """(commits URL, latest release URL): repository metadata only."""
    base = API + repo
    return (f"{base}/commits?sha={BRANCH}&per_page={PER_PAGE}", f"{base}/releases/latest")


def _get_json(fetch, url, etag, allow_404=False):
    """(status, etag, parsed JSON or None)."""
    import json
    uw = _uw()
    status, headers, body = fetch(url, etag=etag)
    if status == 304:
        return 304, etag, None
    if status == 404 and allow_404:
        return 404, None, None
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


def head_and_distance(doc, pin):
    """(head sha, head date, n, more) of a commit list, newest first. n is
    the pin's index (0 = the head is the pin); more is True when the pin is
    not in the list (n is then the list length)."""
    if not isinstance(doc, list) or not doc:
        raise _uw().SourceError("shape", "commit list expected")
    shas = []
    for item in doc:
        sha = item.get("sha") if isinstance(item, dict) else None
        if not (isinstance(sha, str) and SHA_RX.match(sha)):
            raise _uw().SourceError("shape", "commit sha expected")
        shas.append(sha)
    first = doc[0].get("commit") if isinstance(doc[0].get("commit"), dict) else {}
    who = first.get("committer") if isinstance(first.get("committer"), dict) else {}
    date = who.get("date") if isinstance(who.get("date"), str) else ""
    date = date if _loop_base().epoch_of(date) is not None else ""
    if pin in shas:
        return shas[0], date, shas.index(pin), False
    return shas[0], date, len(shas), True


def release_fields(doc):
    """(tag, published date) of a releases/latest answer."""
    if not isinstance(doc, dict):
        raise _uw().SourceError("shape", "release object expected")
    tag, at = doc.get("tag_name"), doc.get("published_at")
    if not (isinstance(tag, str) and TAG_RX.match(tag)):
        raise _uw().SourceError("shape", "release tag expected")
    if not isinstance(at, str) or _loop_base().epoch_of(at) is None:
        raise _uw().SourceError("shape", "release date expected")
    return tag, at


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    lb = _loop_base()
    repo, pin = pins(_root(ctx))
    commits_url, release_url = urls(repo)
    old = state.get("data") if isinstance(state.get("data"), dict) else {}
    data = dict(old)

    status, etag, doc = _get_json(fetch, commits_url, state.get("etag"))
    if status == 200:
        head, date, n, more = head_and_distance(doc, pin)
        data.update(head_sha=head, head_date=date, n=n, n_more=more)
        state["etag"] = etag
    elif not (isinstance(data.get("head_sha"), str) and isinstance(data.get("n"), int)):
        state["etag"] = None  # a 304 with no stored head: read in full next time
        raise _uw().SourceError("shape", "304 without a stored head")

    status, retag, rdoc = _get_json(fetch, release_url, data.get("release_etag"),
                                    allow_404=True)
    if status == 200:
        data["release_tag"], data["release_at"] = release_fields(rdoc)
        data["release_etag"] = retag
    elif status == 404:
        data.update(release_tag=None, release_at=None, release_etag=None)

    head, n, more = data["head_sha"], data["n"], bool(data.get("n_more"))
    found = []
    if n < 1:
        data["moved_since"] = None
        state["data"] = data
        return found
    if not data.get("moved_since"):
        data["moved_since"] = lb.iso(now)
    old_n = old.get("n") if isinstance(old.get("n"), int) else 0
    if head != old.get("head_sha") or old_n < 1:
        found.append({"kind": KIND_MOVE, "key": f"move-{head}",
                      "tokens": {"n": str(min(n, N_MAX))}})
    since = lb.epoch_of(data.get("release_at")) if data.get("release_at") else None
    if since is None:
        since = lb.epoch_of(data["moved_since"])
    filed = lb.epoch_of(data.get("filed_at")) if data.get("filed_at") else None
    if since is not None and now - since >= QUIET_S and (filed is None
                                                         or now - filed >= QUIET_S):
        day = lb.iso(now)[:10].replace("-", "")
        found.append({"kind": KIND_ROW, "key": f"tcnext-{day}",
                      "tokens": {"sha": head, "n": str(min(n, N_MAX))}})
        data["filed_at"] = lb.iso(now)
    state["data"] = data
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": WEEK_S,
    "window": None,
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher PoB-PoE2 master head",
    "check": check,
}
