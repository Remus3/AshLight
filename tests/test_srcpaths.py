"""TEST-WEB-SRCPATHS-PY (F-135): tests/srcpaths.py, the one helper that
knows where the dashboard sources live."""

from pathlib import Path

import srcpaths

ROOT = Path(__file__).resolve().parents[1]


def test_index_html_is_the_dashboard_page():
    html = srcpaths.index_html()
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert '<script src="/web/app.js" defer></script>' in html
    assert html == srcpaths.read("index.html")
    assert srcpaths.index_html("utf-8") == html


def test_read_and_path_resolve_under_web():
    web = (ROOT / "web").resolve()
    assert srcpaths.WEB.resolve() == web
    css = srcpaths.path("app.css")
    assert css.resolve().parent == web and css.is_file()
    assert srcpaths.read("app.css") == css.read_text(encoding="ascii")
    ico = srcpaths.path("favicon.ico")
    assert ico.resolve().parent == web and ico.is_file()
    assert srcpaths.read_bytes("favicon.ico") == ico.read_bytes()


def test_web_js_lists_every_dashboard_script():
    js = srcpaths.web_js()
    assert js == sorted((ROOT / "web").glob("*.js")) + sorted(
        (ROOT / "web" / "panels").glob("*.js"))
    names = [p.name for p in js]
    assert "app.js" in names and "tc.js" in names
    assert all(p.suffix == ".js" and p.is_file() for p in js)


def test_web_css_lists_every_dashboard_sheet():
    css = srcpaths.web_css()
    assert srcpaths.path("app.css") in css
    assert all(p.suffix == ".css" and p.is_file() for p in css)


def _fake_web(tmp_path, monkeypatch, panels):
    web = tmp_path / "web"
    web.mkdir()
    for name in ("app.js", "tabs.js", "app.css"):
        (web / name).write_text("x\n", encoding="ascii")
    if panels:
        (web / "panels").mkdir()
        for name in ("play.js", "build.js", "play.css"):
            (web / "panels" / name).write_text("x\n", encoding="ascii")
    monkeypatch.setattr(srcpaths, "WEB", web)
    monkeypatch.setattr(srcpaths, "PANELS", web / "panels")
    return web


def test_web_js_takes_the_panels_folder_when_present(tmp_path, monkeypatch):
    web = _fake_web(tmp_path, monkeypatch, panels=True)
    assert srcpaths.web_js() == [web / "app.js", web / "tabs.js",
                                 web / "panels" / "build.js", web / "panels" / "play.js"]
    assert srcpaths.web_css() == [web / "app.css", web / "panels" / "play.css"]
    assert srcpaths.path("app.css") == web / "app.css"


def test_web_js_without_a_panels_folder(tmp_path, monkeypatch):
    web = _fake_web(tmp_path, monkeypatch, panels=False)
    assert srcpaths.web_js() == [web / "app.js", web / "tabs.js"]
    assert srcpaths.web_css() == [web / "app.css"]
