"""GGG-DOCS-WATCH (decision 0041): the daily developer docs read, from
recorded fixture HTML only (no network: every fetch is a fake)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ggg_docs_watch as g  # noqa: E402
from server.al import diag, webfetch  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "ggg_docs"
NOW = 1_790_000_000.0
CLOSED = g.CLOSED_SENTENCE


def html(name):
    return (FIX / f"{name}.html").read_text(encoding="ascii")


def pages(**over):
    base = {"index": html("index"), "authorization": html("authorization"),
            "reference": html("plain"), "changelog": html("changelog"),
            "data": html("plain"), "game": html("plain")}
    base.update(over)
    return base


class FakeWeb:
    """fetch(method, url, headers, body) over a {page: html | (status, hdrs)} map."""

    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        name = {u: n for n, u in g.PAGES}[url]
        doc = self.docs[name]
        if isinstance(doc, tuple):
            return doc[0], doc[1], b""
        return 200, {"Content-Type": "text/html"}, doc.encode("utf-8")


@pytest.fixture()
def dirs(tmp_path):
    return {"root": tmp_path / "repo", "cache": tmp_path / "Cache", "logs": tmp_path / "Logs"}


def run(dirs, web, now=NOW):
    return g.run(dirs["root"], now, fetch=web, sleep=lambda s: None,
                 cache=dirs["cache"], logs=dirs["logs"])


def flag(dirs):
    return dirs["root"] / "ops" / "runtime" / "ggg_docs" / "REG_OPEN"


def notes(dirs):
    p = dirs["root"] / "ops" / "runtime" / "ggg_docs" / "notes.log"
    return p.read_text(encoding="ascii") if p.exists() else ""


# --- extraction ---------------------------------------------------------

def test_extract_main_text_only_with_heading_and_list_marks():
    p = g.extract(html("index"))
    assert p["lines"][0] == "## Introduction"
    assert "### Registering your Application" in p["lines"]
    assert f"#### {CLOSED}" in p["lines"]
    assert any(ln.startswith("- A basic understanding of") for ln in p["lines"])
    text = p["text"]
    assert "__CF$cv$params" not in text and "Overview" not in text  # script, nav
    assert "key=abc" not in text  # attributes never enter the text


def test_extract_none_without_main_and_pre_keeps_lines():
    assert g.extract(html("challenge")) is None
    p = g.extract(html("authorization"))
    assert "GET /oauth/authorize?client_id=example" in p["lines"]
    assert "&redirect_uri=https://example.com" in p["lines"]


def test_whitespace_reflow_does_not_change_the_hash():
    a = g.extract(html("index"))["text"]
    b = g.extract(html("index").replace("<p>\n    Our", "<p>Our   ")
                  .replace("snapshot of data", "snapshot\n   of data"))["text"]
    assert g.sha256(a) == g.sha256(b)


def test_registration_states():
    assert g.registration(g.extract(html("index"))) == "closed"
    gone = html("index").replace(CLOSED, "Apply with the form below.")
    assert g.registration(g.extract(gone)) == "open"
    assert g.registration(None) == "unknown"
    # not the page we know (no Getting Started): never a false alarm
    other = html("index").replace("Getting Started", "Hello").replace(CLOSED, "x")
    assert g.registration(g.extract(other)) == "unknown"
    sec = g.reg_section(g.extract(html("index")))
    assert sec[0] == "### Registering your Application" and len(sec) == 3


def test_changelog_entries_newest_first():
    assert g.changelog_entries(g.extract(html("changelog"))) == ["3.30.0", "3.29.3b"]


# --- the run ------------------------------------------------------------

def test_first_run_is_a_baseline_six_sequential_gets(dirs):
    web = FakeWeb(pages())
    st = run(dirs, web)
    assert [c[1] for c in web.calls] == [u for _, u in g.PAGES]
    for method, url, headers in web.calls:
        assert method == "GET" and url.startswith("https://www.pathofexile.com/")
        assert headers["User-Agent"].startswith("AshLight/")
        assert "cookie" not in {k.lower() for k in headers}
    assert st["status"] == "ok" and st["last_read"] == 6 and st["changes"] == []
    assert st["reg"] == "closed" and st["changelog_latest"] == "3.30.0"
    assert st["next_check"] == NOW + g.CHECK_EVERY_S
    assert (dirs["cache"] / "pages" / "index.txt").is_file()
    assert not flag(dirs).exists() and notes(dirs) == ""
    assert not dirs["logs"].exists()  # no diff on a baseline
    assert "6/6 pages read, registration closed" in g.summary(st)


def test_unchanged_second_run_writes_nothing_new(dirs):
    run(dirs, FakeWeb(pages()))
    st = run(dirs, FakeWeb(pages()), now=NOW + 90000)
    assert st["changes"] == [] and notes(dirs) == "" and not dirs["logs"].exists()


def test_registration_reopened_raises_the_flag_and_a_note(dirs):
    run(dirs, FakeWeb(pages()))
    reopened = html("index").replace(
        f"<h4>{CLOSED}</h4>",
        '<p>Send your application to <a href="mailto:apps@example.com">us</a>.</p>')
    st = run(dirs, FakeWeb(pages(index=reopened)), now=NOW + 90000)
    assert st["reg"] == "open" and flag(dirs).is_file()
    n = notes(dirs)
    assert "REGISTRATION closed -> open" in n
    assert "REGISTRATION channels changed" in n and "apps@example.com" in n
    assert "CHANGED page=index" in n and "registration" in n
    assert "REGISTRATION MAY BE OPEN" in g.summary(st)
    diff = (dirs["logs"] / st["changes"][0]["diff"]).read_text(encoding="utf-8")
    assert f"-#### {CLOSED}" in diff
    # closed again: the flag goes away by itself
    st = run(dirs, FakeWeb(pages()), now=NOW + 200000)
    assert st["reg"] == "closed" and not flag(dirs).exists()
    assert "REGISTRATION open -> closed" in notes(dirs)


def test_token_lifetime_scope_and_redirect_changes_are_tagged(dirs):
    run(dirs, FakeWeb(pages()))
    auth = (html("authorization").replace("10 hours", "24 hours")
            .replace("<code>account:characters</code>", "<code>account:characters:poe2</code>")
            .replace("http://127.0.0.1:8080/callback", "http://localhost/callback"))
    st = run(dirs, FakeWeb(pages(authorization=auth)), now=NOW + 90000)
    (c,) = st["changes"]
    assert c["page"] == "authorization"
    for t in ("token-lifetime", "scopes", "redirect", "poe2"):
        assert t in c["topics"]
    assert st["reg"] == "closed" and not flag(dirs).exists()


def test_new_changelog_entry_is_named(dirs):
    run(dirs, FakeWeb(pages()))
    new = html("changelog").replace(
        '<article id="3-30-0">',
        '<article id="3-31-0"><h3>3.31.0:</h3><ul><li>PoE2 characters endpoint '
        'now returns the backpack.</li></ul><small>Updated 01/12/2026.</small>'
        '</article>\n<article id="3-30-0">')
    st = run(dirs, FakeWeb(pages(changelog=new)), now=NOW + 90000)
    (c,) = st["changes"]
    assert c["new_entries"] == ["3.31.0"] and "poe2" in c["topics"]
    assert st["changelog_latest"] == "3.31.0"
    assert "new_entries=3.31.0" in notes(dirs)


def test_challenge_page_never_raises_a_false_alarm(dirs):
    run(dirs, FakeWeb(pages()))
    st = run(dirs, FakeWeb(pages(index=html("challenge"))), now=NOW + 90000)
    assert st["reg"] == "closed" and not flag(dirs).exists()
    assert st["status"] == "partial" and st["last_read"] == 5
    assert st["next_check"] == NOW + 90000 + g.RETRY_S


def test_429_stops_the_run_and_obeys_retry_after(dirs):
    web = FakeWeb(pages(authorization=(429, {"Retry-After": "7200"})))
    st = run(dirs, web)
    assert len(web.calls) == 2  # index, then the 429: nothing after it
    assert st["status"] == "rate-limited" and st["next_check"] == NOW + 7200
    web = FakeWeb(pages(index=(503, {})))
    st = run(dirs, web, now=NOW + 10000)
    assert len(web.calls) == 1 and st["next_check"] == NOW + 10000 + g.RATE_MIN_S


def test_network_error_retries_in_three_hours(dirs):
    def down(method, url, headers, body=None):
        raise webfetch.FetchError("network: down")
    st = run(dirs, down)
    assert st["status"] == "error" and st["next_check"] == NOW + g.RETRY_S
    assert st.get("reg") is None and not flag(dirs).exists()


def test_loop_check_gate_is_24_hours(dirs):
    web = FakeWeb(pages())
    kw = dict(fetch=web, sleep=lambda s: None, cache=dirs["cache"], logs=dirs["logs"])
    assert g.loop_check(dirs["root"], NOW, **kw).startswith("ggg docs: 6/6")
    assert g.loop_check(dirs["root"], NOW + 3600, **kw) is None
    assert len(web.calls) == 6
    assert g.loop_check(dirs["root"], NOW + g.CHECK_EVERY_S, **kw) is not None
    assert len(web.calls) == 12


def test_only_the_docs_host_is_fetched():
    assert g.HOSTS == ("www.pathofexile.com",)
    for _, url in g.PAGES:
        webfetch.check_url(url, g.HOSTS)
    with pytest.raises(webfetch.UrlNotAllowed):
        g.fetch_page("https://api.pathofexile.com/character", NOW, fetch=FakeWeb({}))


# --- loop and dashboard wiring -----------------------------------------

def test_tick_runs_the_watch_even_while_halted(tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    import al_loop
    import al_loopkit as L
    root = L.make_root(tmp_path)
    calls = []
    d = L.deps(root, docs_watch=lambda r, now: calls.append(now) or "ggg docs: 6/6")
    (root / al_loop.HALT_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / al_loop.HALT_REL).write_text("halt\n", encoding="ascii")
    doc = al_loop.tick(deps=d, no_push=True)
    assert calls and doc["state"] == "halted"
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert len(calls) == 1  # a dry run never reads the web


def test_tick_hook_never_fails_the_tick(tmp_path, monkeypatch):
    def boom(root, now):
        raise RuntimeError("parser broke")
    monkeypatch.setattr(g, "loop_check", boom)
    assert g.safe_check(tmp_path, NOW) == "ggg docs: RuntimeError: parser broke"


def test_diag_lists_the_dev_note_only_while_flagged():
    ids = [r["id"] for r in diag.checks({}, NOW)]
    assert "dev_docs" not in ids
    rows = diag.checks({"ggg_reg_open": True}, NOW)
    row = rows[-1]
    assert row["id"] == "dev_docs" and row["status"] == diag.NOTE
    assert row["fix"] is None and row["detail"].isascii()
    v = diag.view({"ggg_reg_open": True}, "0.0.0", now=NOW)
    assert "GGG developer API" in v["report"]
