"""LOOP-WATCH-GATE (F-030, AUTO-05): the watcher web-data gate and URL
check in tools/watch_gate.py. Pure: no socket (the transport is a fake
callable), config under tmp_path."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import watch_gate  # noqa: E402

from server.al import NAME, webfetch  # noqa: E402

REPO = "https://api.github.com/repos/someone/some-tool"
SCHEDULE = "https://releases.electronjs.org/schedule.json"
NPM = "https://registry.npmjs.org/-/package/electron/dist-tags"
SOURCE = {"name": "test-src", "purpose": "dev: watcher test", "urls": [SCHEDULE, NPM]}


class FakeTransport:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if self.replies:
            return self.replies.pop(0)
        return 200, {}, b"{}"


def _root(tmp_path, cfg):
    (tmp_path / "config").mkdir(exist_ok=True)
    if cfg is not None:
        text = cfg if isinstance(cfg, str) else json.dumps(cfg)
        (tmp_path / "config" / "local.json").write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("cfg", [None, {}, {"web_data": False}, {"web_data": "true"},
                                 {"web_data": 1}, "not json", "[true]"])
def test_web_data_off_raises_before_any_request(tmp_path, cfg):
    root = _root(tmp_path, cfg)
    assert watch_gate.web_data_on(root) is False
    t = FakeTransport()
    with pytest.raises(webfetch.WebDataOff):
        watch_gate.fetch(root, SOURCE, REPO + "/releases/latest", transport=t)
    assert t.calls == []
    # off wins even for a URL the gate would refuse anyway
    with pytest.raises(webfetch.WebDataOff):
        watch_gate.fetch(root, SOURCE, "https://www.pathofexile.com/", transport=t)
    assert t.calls == []
    # the setting is read at call time: turning it on lets the same call through
    _root(tmp_path, {"web_data": True})
    assert watch_gate.web_data_on(root) is True
    status, _h, _b = watch_gate.fetch(root, SOURCE, REPO + "/releases/latest", transport=t)
    assert status == 200 and len(t.calls) == 1


@pytest.mark.parametrize("url", [
    "https://example.com/feed.json",
    "https://releases.electronjs.org/other.json",
    SCHEDULE + "?x=1",
    "http://releases.electronjs.org/schedule.json",
    "https://registry.npmjs.org/electron",
    "https://poe.ninja/api/data/whatever",
    "https://github.com/someone/some-tool",
    "https://api.github.com/orgs/someone",
    "https://api.github.com/search/repositories?q=x",
    "https://127.0.0.1/x",
    "https://user" + "@api.github.com/repos/a/b",
    "https://api.github.com:8443/repos/a/b",
    "not a url",
    "https://[bad",
])
def test_request_outside_the_source_hosts_is_refused(tmp_path, url):
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.check_url(SOURCE, url)
    root = _root(tmp_path, {"web_data": True})
    t = FakeTransport()
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.fetch(root, SOURCE, url, transport=t)
    assert t.calls == []


@pytest.mark.parametrize("url", [
    REPO + "/contents/data/items.json",
    REPO + "/readme",
    REPO + "/tarball/v1.0",
    REPO + "/zipball/main",
    REPO + "/releases/assets/12345",
    REPO + "/git/blobs/abc123",
    REPO + "/git/trees/main",
    "https://raw.githubusercontent.com/someone/some-tool/main/data.json",
    "https://codeload.github.com/someone/some-tool/zip/main",
    "https://objects.githubusercontent.com/github-production-release-asset/x",
    "https://github.com/someone/some-tool/archive/refs/tags/v1.zip",
    "https://github.com/someone/some-tool/releases/download/v1/x.zip",
    "https://github.com/someone/some-tool/raw/main/data.json",
    "https://github.com/someone/some-tool/blob/main/data.json",
])
def test_data_file_url_is_refused_for_a_gated_source(tmp_path, url):
    listing = dict(SOURCE, urls=[url])  # listing a data file never lets it through
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.check_url(listing, url)
    root = _root(tmp_path, {"web_data": True})
    t = FakeTransport()
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.fetch(root, listing, url, transport=t)
    assert t.calls == []
    # a redirect from a metadata path to a data file is refused before the hop
    t = FakeTransport([(302, {"Location": REPO + "/contents/x.json"}, b"")])
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.fetch(root, SOURCE, REPO + "/releases/latest", transport=t)
    assert [c[1] for c in t.calls] == [REPO + "/releases/latest"]


GGG_URLS = [
    "https://www.pathofexile.com/developer/docs/reference",
    "https://www.pathofexile.com/developer/docs",
    "https://pathofexile.com/api/leagues",
    "https://api.pathofexile.com/league",
    "https://www.pathofexile.com/trade2/search/poe2/Standard",
    "https://www.pathofexile.com/api/trade2/search/Standard",
    "https://pathofexile2.com/",
    "https://web.poecdn.com/image/x.png",
    "https://www.grindinggear.com/",
]


def test_listed_exact_url_passes_and_a_ggg_host_never_does(tmp_path):
    for url in (SCHEDULE, NPM, REPO, REPO + "/", REPO + "/releases", REPO + "/releases/latest",
                REPO + "/releases/tags/v0.1.0", REPO + "/releases/123", REPO + "/tags",
                REPO + "/commits?per_page=1", REPO + "/commits/main", REPO + "/branches/main",
                REPO + "/git/refs/tags/v1"):
        assert watch_gate.check_url(SOURCE, url).scheme == "https"
    # a module carrying SOURCE works as well as the mapping
    mod = type("Mod", (), {"SOURCE": SOURCE})
    assert watch_gate.check_url(mod, SCHEDULE)
    root = _root(tmp_path, {"web_data": True})
    for url in GGG_URLS:
        listing = dict(SOURCE, urls=[url])
        with pytest.raises(webfetch.UrlNotAllowed):
            watch_gate.check_url(listing, url)
        t = FakeTransport()
        with pytest.raises(webfetch.UrlNotAllowed):
            watch_gate.fetch(root, listing, url, transport=t)
        assert t.calls == []
    # a redirect off a listed URL to a GGG host is refused before that hop
    t = FakeTransport([(301, {"Location": GGG_URLS[0]}, b"")])
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.fetch(root, SOURCE, SCHEDULE, transport=t)
    assert [c[1] for c in t.calls] == [SCHEDULE]
    t = FakeTransport()
    status, _h, body = watch_gate.fetch(root, SOURCE, SCHEDULE, transport=t)
    assert (status, body) == (200, b"{}") and t.calls[0][1] == SCHEDULE


def test_user_agent_names_ashlight_and_no_cookie_is_sent(tmp_path):
    root = _root(tmp_path, {"web_data": True, "contact": "someone"})
    t = FakeTransport()
    watch_gate.fetch(root, SOURCE, REPO + "/releases/latest", transport=t)
    watch_gate.fetch(root, {"name": "bare", "urls": [NPM]}, NPM, transport=t)
    assert len(t.calls) == 2
    for method, _url, headers in t.calls:
        assert method == "GET"
        names = {k.lower() for k in headers}
        assert "cookie" not in names and "authorization" not in names
        ua = headers["User-Agent"]
        assert ua.startswith(NAME + "/") and ua.isascii()
    assert t.calls[0][2]["User-Agent"] == webfetch.user_agent("dev: watcher test")
    assert t.calls[1][2]["User-Agent"] == webfetch.user_agent("dev: watcher bare")


@pytest.mark.parametrize("tail", ["/issues", "/issues?labels=al-watch&state=open&per_page=100",
                                  "/actions/workflows/watch.yml",
                                  "/actions/workflows/watch.yml/runs",
                                  "/actions/workflows/watch.yml/runs?status=success&per_page=1"])
def test_ci_issue_tails_pass_and_other_actions_paths_are_refused(tmp_path, tail):
    """Decision 0069 amendment 2026-11-21 (LOOP-CI-ISSUES): exactly the issue
    list and the watch workflow's own state and runs pass; every other
    /actions/ and /issues/ sub-path stays refused."""
    assert watch_gate.check_url(SOURCE, REPO + tail).hostname == "api.github.com"
    for bad in ("/actions/runs/1/logs", "/actions/artifacts", "/actions/secrets",
                "/issues/1/comments", "/issues/1", "/issues/comments",
                "/actions/workflows", "/actions/workflows/ci.yml",
                "/actions/workflows/watch.yml/runs/1", "/actions/workflows/watch.yml/dispatches",
                "/actions/workflows/watchxyml", "/actions/runs", "/actions/caches"):
        with pytest.raises(webfetch.UrlNotAllowed):
            watch_gate.check_url(SOURCE, REPO + bad)
    root = _root(tmp_path, {"web_data": True})
    t = FakeTransport()
    status, _h, _b = watch_gate.fetch(root, SOURCE, REPO + tail, transport=t)
    assert status == 200 and len(t.calls) == 1
    t2 = FakeTransport()
    with pytest.raises(webfetch.UrlNotAllowed):
        watch_gate.fetch(root, SOURCE, REPO + "/actions/runs/1/logs", transport=t2)
    assert t2.calls == []
