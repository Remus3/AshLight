"""TEST-WEB-ASSEMBLE (F-194, research 0047 R8): the core inserts one tag per
web/panels/*.js and *.css at the marker in index.html, so a new panel edits
no shared file.

The server binds an ephemeral port on 127.0.0.1 with a temp web root and
runtime under tmp_path; nothing real is started or changed.
"""

import http.client
import os
import re
import shutil
import threading
from html.parser import HTMLParser
from pathlib import Path

import pytest

import srcpaths
from server.al import webpage
from server.al.core import Core
from server.al.http import CSP, serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "w" * 48
APP_TAG = '<script src="/web/app.js" defer></script>'


def _web(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    shutil.copyfile(srcpaths.path("index.html"), web / "index.html")
    (web / "app.js").write_text("// app\n", encoding="ascii")
    return web


def _panel(web, name, text="// panel\n"):
    folder = web / "panels"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(text.encode("ascii"))
    return folder / name


@pytest.fixture
def web(tmp_path):
    return _web(tmp_path)


@pytest.fixture
def srv(tmp_path, web):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=web)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def get(server, path, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request(method, path, headers={"Host": "127.0.0.1:%d" % server.port})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == "id":
                self.ids.append(v)

    handle_startendtag = handle_starttag


def _dupes(html):
    p = _Ids()
    p.feed(html)
    return sorted({i for i in p.ids if p.ids.count(i) > 1})


def _head_order(html):
    return re.findall(r'<(?:script src|link rel="stylesheet" href)="([^"]+)"', html)


def test_index_html_holds_one_marker_before_app_js():
    raw = srcpaths.read("index.html")
    assert raw.count(webpage.MARKER.decode("ascii")) == 1
    assert raw.index(webpage.MARKER.decode("ascii")) < raw.index(APP_TAG)


def test_a_new_panel_js_is_tagged_before_app_js_with_no_index_edit(srv, web):
    before = (web / "index.html").read_bytes()
    _panel(web, "x.js")
    r, body = get(srv, "/")
    assert r.status == 200 and "text/html" in r.getheader("Content-Type")
    html = body.decode("ascii")
    tag = '<script src="/web/panels/x.js" defer></script>'
    assert tag in html
    assert html.index(tag) < html.index(APP_TAG)
    assert (web / "index.html").read_bytes() == before
    r2, body2 = get(srv, "/index.html")
    assert r2.status == 200 and body2 == body


def test_panel_tags_are_sorted_and_css_adds_a_link(srv, web):
    for name in ("zeta.js", "alpha.js", "mid.js", "b.css", "a.css"):
        _panel(web, name)
    _, body = get(srv, "/")
    order = [u for u in _head_order(body.decode("ascii")) if "/panels/" in u]
    assert order == ["/web/panels/a.css", "/web/panels/b.css", "/web/panels/alpha.js",
                     "/web/panels/mid.js", "/web/panels/zeta.js"]


def test_a_file_added_while_the_server_runs_shows_on_the_next_get(srv, web):
    _, first = get(srv, "/")
    assert b"/web/panels/" not in first
    r, _ = get(srv, "/web/panels/late.js")
    assert r.status == 404
    _panel(web, "late.js", "// late\n")
    _, second = get(srv, "/")
    assert b'<script src="/web/panels/late.js" defer></script>' in second
    # the tag and its file arrive together: the /web/ map lists again
    r, data = get(srv, "/web/panels/late.js")
    assert r.status == 200 and data == b"// late\n"
    assert "javascript" in r.getheader("Content-Type")
    _panel(web, "late.css", "p{}\n")
    _, third = get(srv, "/")
    assert b'<link rel="stylesheet" href="/web/panels/late.css">' in third
    os.remove(web / "panels" / "late.js")
    _, fourth = get(srv, "/")
    assert b"late.js" not in fourth and b"late.css" in fourth


def test_csp_and_headers_unchanged_on_the_assembled_page(srv, web):
    _panel(web, "x.js")
    r, _ = get(srv, "/")
    assert r.getheader("Content-Security-Policy") == CSP
    assert "script-src 'self'" in CSP and "unsafe-inline" not in CSP
    assert r.getheader("X-Content-Type-Options") == "nosniff"
    r, body = get(srv, "/", method="HEAD")
    assert r.status == 200 and body == b""


def test_no_inline_script_and_no_remote_origin(web):
    for name in ("x.js", "y.css"):
        _panel(web, name)
    html = webpage.assemble(web).decode("ascii")
    for tag in re.findall(r"<script[^>]*>", html):
        assert "src=" in tag
    assert re.search(r"<script[^>]*>\s*[^<\s]", html) is None
    for url in re.findall(r'(?:src|href)="([^"]*)"', html):
        assert url.startswith("/") and not url.startswith("//"), url
    assert "http:" not in html and "https:" not in html


def test_the_served_page_has_unique_ids(srv, web):
    _panel(web, "x.js")
    _, body = get(srv, "/")
    assert _dupes(body.decode("ascii")) == []
    assert _dupes(srcpaths.index_html()) == []


def test_no_panel_serves_index_html_byte_identical(srv, web):
    _, body = get(srv, "/")
    assert body == (web / "index.html").read_bytes()
    (web / "panels").mkdir()
    _, body = get(srv, "/")
    assert body == (web / "index.html").read_bytes()
    assert srcpaths.index_html() == srcpaths.read("index.html")


def test_only_safe_regular_panel_files_are_tagged(web):
    for name in (".hidden.js", "a b.js", "x.mjs", "notes.txt", "-dash.js", "ok_1.js"):
        _panel(web, name)
    (web / "panels" / "sub").mkdir()
    (web / "panels" / "sub" / "deep.js").write_text("//\n", encoding="ascii")
    (web / "panels" / "dir.js").mkdir()
    page, names = webpage.page(web)
    assert names == ("panels/ok_1.js",)
    assert page.count(b"/web/panels/") == 1


def test_a_page_without_the_marker_links_no_panel(web):
    raw = (web / "index.html").read_bytes().replace(webpage.MARKER, b"")
    (web / "index.html").write_bytes(raw)
    _panel(web, "x.js")
    assert webpage.assemble(web) == raw


def test_cache_follows_names_sizes_and_index_edits(web):
    p = _panel(web, "x.js", "// one\n")
    first = webpage.assemble(web)
    assert webpage.assemble(web) is first  # unchanged folder: cached bytes
    p.write_text("// longer text\n", encoding="ascii")
    assert webpage.assemble(web) is not first
    page = (web / "index.html").read_bytes()
    (web / "index.html").write_bytes(page.replace(b"<title>AshLight</title>",
                                                  b"<title>AshLight test</title>"))
    assert b"<title>AshLight test</title>" in webpage.assemble(web)


def test_missing_root_or_page_is_none(tmp_path):
    assert webpage.assemble(None) is None
    assert webpage.page(tmp_path / "nowhere") is None
    assert webpage.assemble(tmp_path) is None


def test_srcpaths_index_html_is_the_assembled_page():
    assert srcpaths.index_html() == webpage.assemble(srcpaths.WEB).decode("ascii")
