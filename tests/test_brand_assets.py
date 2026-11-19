"""BRAND-ICON: the brand SVG sources, rendered PNGs, ICOs and favicon are
present, sized right, in sync, ASCII, and wired into README and dashboard
(docs/design/0005-brand-mark.md)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import make_icons as mi  # noqa: E402
import srcpaths  # noqa: E402


def test_check_mode_is_clean():
    assert mi.check() == []


def test_svg_sources_are_ascii_and_have_no_font_or_raster():
    for svg in (mi.MARK, mi.SMALL, mi.HERO, mi.FAVICON_SVG):
        data = svg.read_bytes()
        data.decode("ascii")
        text = data.decode("ascii").lower()
        assert b"\r" not in data
        assert "<text" not in text and "font-family" not in text, svg.name
        assert "<image" not in text and "http://" not in text.replace(
            "http://www.w3.org/", ""), svg.name


def test_png_sizes_and_transparent_corners():
    for n in mi.SIZES:
        data = mi.png_path(n).read_bytes()
        assert mi.png_size(data) == (n, n)
        assert mi.png_corner_alpha(data) <= 8, n
    for theme in ("light", "dark"):
        assert mi.png_size(mi.hero_path(theme).read_bytes()) == mi.HERO_SIZE


def test_ico_holds_every_size_as_png():
    got = mi.ico_entries(mi.ICO.read_bytes())
    assert [s for s, _ in got] == [16, 24, 32, 48, 64, 128, 256]
    for size, data in got:
        assert mi.png_size(data) == (size, size)
    fav = mi.ico_entries(mi.FAVICON.read_bytes())
    assert [s for s, _ in fav] == [16, 32, 48]


def test_ico_roundtrip():
    pngs = [(16, mi.png_path(16).read_bytes()), (256, mi.png_path(256).read_bytes())]
    assert mi.ico_entries(mi.ico_bytes(pngs)) == pngs


def test_write_if_changed_is_idempotent(tmp_path):
    p = tmp_path / "x.bin"
    assert mi.write_if_changed(p, b"a") is True
    assert mi.write_if_changed(p, b"a") is False
    assert mi.write_if_changed(p, b"b") is True


def test_readme_hero_and_disclaimer():
    text = (ROOT / "README.md").read_text(encoding="ascii")
    head = text[:1200]
    assert "assets/brand/readme-hero-dark.png" in head
    assert "assets/brand/readme-hero-light.png" in head
    assert "alt=\"AshLight" in head
    assert "This product isn't affiliated with or endorsed by Grinding Gear Games in any way." in text


def test_dashboard_links_local_favicon():
    html = srcpaths.index_html()
    assert 'rel="icon" href="/web/favicon.svg"' in html
    assert 'href="/favicon.ico"' in html
    assert "http" not in html.split("<title>")[0].replace("http-equiv", "")


def test_header_shows_the_mark_left_of_the_name():
    # PLAY-TD-09C-BAR (F-190): AshLight's own small mark from the dashboard's
    # own files (no GGG art), decorative (empty alt), in a 20 px box
    html = srcpaths.index_html()
    head = html[html.index('<header class="bar">'):html.index("</header>")]
    h1 = head[head.index("<h1"):head.index("</h1>")]
    img = '<img class="brand-mark" src="/web/favicon.svg" alt="" width="20" height="20">'
    assert img in h1
    assert h1.index(img) < h1.index("AshLight")
    assert head.count("<img") == 1
    css = srcpaths.read("app.css")
    assert ".brand-mark { display: block; flex: 0 0 auto; width: 20px; height: 20px; }" in css
    assert mi.FAVICON_SVG == srcpaths.path("favicon.svg")
