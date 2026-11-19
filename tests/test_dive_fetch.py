"""AUTO-04 DIVE-FLOOR (decision 0050, ruling Q-07): a research dive has no
free web tools; every fetch goes through tools/webfetch.py behind one host
allow-list, with the AshLight User-Agent and a host log. Pure: no socket
(the transport is a fake callable), logs under tmp_path."""

import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import loop_base  # noqa: E402
import loop_prompts  # noqa: E402
import webfetch as divefetch  # noqa: E402

from server.al import NAME, webfetch  # noqa: E402

REFERENCE = "https://www.pathofexile.com/developer/docs/reference"
DATA = "https://www.pathofexile.com/developer/docs/data"
REPO = "https://api.github.com/repos/someone/some-tool/releases"
FORUM_HOST = re.compile(r"pathofexile2?\.com/forum|forum\.pathofexile|/forum/view", re.I)


class FakeFetch:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if self.replies:
            return self.replies.pop(0)
        return 200, {"Content-Type": "text/html"}, b"<html><main><p>ok</p></main></html>"


def _get(url, tmp_path, fetch, on=True, contact=None):
    return divefetch.get(url, enabled=lambda: on, contact=contact, fetch=fetch,
                         logs=tmp_path / "logs", now=lambda: 1795000000.0)


def _log(tmp_path):
    p = tmp_path / "logs" / divefetch.LOG_NAME
    return p.read_text(encoding="ascii").splitlines() if p.exists() else []


def test_allow_list_refuses_forum_trade_changelog_poe2db_and_wiki():
    assert divefetch.A01_OTHER_DOCS_PAGES is False  # operator decision A-01, default no
    refused = (
        "https://www.pathofexile.com/forum/view-forum/patch-notes",
        "https://www.pathofexile.com/forum/view-thread/1234567",
        "https://pathofexile.com/forum/view-forum/2212",
        "https://www.pathofexile.com/trade2/search/poe2/Standard",
        "https://www.pathofexile.com/api/trade2/fetch/abc",
        "https://www.pathofexile.com/developer/docs/changelog",
        "https://www.pathofexile.com/developer/docs",
        "https://www.pathofexile.com/developer/docs/authorization",
        "https://www.pathofexile.com/developer/docs/game",
        "https://www.pathofexile.com/",
        "https://www.pathofexile.com/developer/docs/reference?x=1",
        "https://www.pathofexile.com/developer/docs/reference/../changelog",
        "https://www.pathofexile.com/developer/docs/%72eference",
        "https://api.pathofexile.com/league",
        "https://pathofexile2.com/",
        "https://web.poecdn.com/public/news/x.png",
        "https://poe2db.tw/us/",
        "https://www.poe2wiki.net/wiki/Path_of_Exile_2",
        "https://www.poewiki.net/wiki/Item",
        "https://pathofexile.fandom.com/wiki/X",
        "https://github.com/someone/some-tool",
        "https://api.github.com/search/code?q=x",
        "https://api.github.com/repos/grindinggear/x/releases",
        "https://poe.ninja/poe2/economy",
        "http://www.pathofexile.com/developer/docs/reference",
        "https://www.pathofexile.com:8443/developer/docs/reference",
        "https://user" + chr(64) + "www.pathofexile.com/developer/docs/reference",
        "https://127.0.0.1/developer/docs/reference",
    )
    for url in refused:
        ok, reason = divefetch.allowed(url)
        assert not ok, url
        assert reason, url
    assert "forum" in divefetch.allowed(refused[0])[1]
    assert "A-01" in divefetch.allowed(refused[5])[1]
    assert "trade" in divefetch.allowed(refused[3])[1]


def test_allow_list_passes_reference_and_data_pages():
    for url in (REFERENCE, DATA, REFERENCE + "/", DATA + "#exports", REPO,
                "https://api.github.com/repos/someone/some-tool/commits?per_page=5"):
        assert divefetch.allowed(url) == (True, "ok"), url
    out = io.StringIO()
    assert divefetch.main(["check", REFERENCE], out=out) == divefetch.EXIT_OK
    assert out.getvalue().startswith("allowed")
    out = io.StringIO()
    assert divefetch.main(["check", "https://www.pathofexile.com/forum/x"],
                          out=out) == divefetch.EXIT_REFUSED


def test_every_fetch_is_logged_with_the_ashlight_user_agent(tmp_path):
    fake = FakeFetch()
    for url in (REFERENCE, DATA, REPO):
        status, _h, _b = _get(url, tmp_path, fake, contact="issues page")
        assert status == 200
    assert [c[1] for c in fake.calls] == [REFERENCE, DATA, REPO]
    for _m, _u, headers in fake.calls:
        ua = headers["User-Agent"]
        assert ua.startswith(NAME + "/") and "research dive" in ua and "(contact: " in ua
        assert "Cookie" not in headers
    lines = _log(tmp_path)
    assert len(lines) == 3
    for line, host in zip(lines, ("www.pathofexile.com", "www.pathofexile.com",
                                  "api.github.com")):
        assert f"host={host} " in line and "status=200" in line
        assert "ua=" + NAME + "/" in line


def test_refused_url_sends_nothing_and_is_logged(tmp_path):
    fake = FakeFetch()
    with pytest.raises(webfetch.UrlNotAllowed):
        _get("https://www.pathofexile.com/forum/view-thread/1", tmp_path, fake)
    assert fake.calls == []
    (line,) = _log(tmp_path)
    assert "refused=" in line and "sent=no" in line


def test_redirect_off_the_allow_list_is_refused_per_hop(tmp_path):
    fake = FakeFetch([(302, {"Location": "/forum/view-forum/patch-notes"}, b"")])
    with pytest.raises(webfetch.UrlNotAllowed):
        _get(REFERENCE, tmp_path, fake)
    assert [c[1] for c in fake.calls] == [REFERENCE]  # the forum hop was never sent
    lines = _log(tmp_path)
    assert "status=302" in lines[0] and "refused=" in lines[1]


def test_web_data_off_sends_nothing(tmp_path):
    fake = FakeFetch()
    with pytest.raises(webfetch.WebDataOff):
        _get(REFERENCE, tmp_path, fake, on=False)
    assert fake.calls == [] and _log(tmp_path) == []
    out = io.StringIO()
    rc = divefetch.main(["get", REFERENCE], fetch=fake, logs=tmp_path / "logs",
                        config={"web_data": "yes"}, out=out)  # strictly True only
    assert rc == divefetch.EXIT_OFF and fake.calls == []


def test_retry_after_is_obeyed_per_host(tmp_path):
    fake = FakeFetch([(429, {"Retry-After": "120"}, b"")])
    with pytest.raises(divefetch.RateLimited):
        _get(REFERENCE, tmp_path, fake)
    with pytest.raises(divefetch.RateLimited):
        _get(DATA, tmp_path, fake)
    assert len(fake.calls) == 1  # the second read waited, nothing sent


def test_cli_get_prints_page_text(tmp_path):
    fake = FakeFetch([(200, {"Content-Type": "text/html"},
                       b"<html><script>x()</script><h1>API Reference</h1><p>a b</p></html>")])
    out = io.StringIO()
    rc = divefetch.main(["get", REFERENCE], fetch=fake, logs=tmp_path / "logs",
                        config={"web_data": True}, out=out)
    assert rc == divefetch.EXIT_OK
    text = out.getvalue()
    assert "API Reference\na b" in text and "x()" not in text


def test_no_forum_host_in_the_dive_prompt_or_the_runbook(tmp_path):
    (tmp_path / "docs" / "research").mkdir(parents=True)
    prompt = loop_prompts.deep_dive_prompt(tmp_path, "20261118", 1, {})
    runbook = (ROOT / "docs" / "ops" / "1.0-launch-runbook.md").read_text(encoding="ascii")
    for text in (prompt, runbook):
        assert not FORUM_HOST.search(text)
        assert "forum" not in text.lower()
        assert "/developer/docs/reference" in text and "/developer/docs/data" in text
        assert "tools/webfetch.py" in text
    assert "patch notes" not in prompt.lower()
    assert "WebFetch or WebSearch" in prompt  # it is told it has neither
    step1 = runbook.split("## 1. ", 1)[1].split("\n## ", 1)[0]
    assert "operator-pasted text only" in step1 and "changelog" not in step1


def test_dive_spawn_arguments_hold_no_free_web_tool():
    joined = " ".join(loop_base.DEEP_EXTRA)
    assert "WebFetch" not in joined and "WebSearch" not in joined
    assert loop_base.DIVE_FETCH_TOOL in joined
