"""AREA-UX batch 8 (glance review 0004 U25-U27): UX-B9-CARDS,
UX-DASH-DENSITY, UX-OVERLAY-REAL3."""

import re
from pathlib import Path

from server.al import pricewatch, underlevel

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="ascii")
MAIN = HTML[HTML.index("<main>"):HTML.index("</main>")]


def _between(start, end):
    i = MAIN.index(start)
    return MAIN[i:MAIN.index(end, i)]


# -- U25 UX-B9-CARDS

def test_clear_buttons_are_not_primary():
    """A button that throws data away is never the filled primary style."""
    for bid in ("history-clear", "watch-clear"):
        m = re.search(r'<button id="%s"[^>]*>' % bid, MAIN)
        assert m and 'class="secondary"' in m.group(0), bid


def test_price_watch_off_and_empty_still_says_how_it_fills(tmp_path):
    w = pricewatch.PriceWatch(tmp_path / pricewatch.FILE_NAME)
    v = w.view(False)
    assert v["text"] == pricewatch.OFF_EMPTY_TEXT
    assert "web data" in v["text"] and "item check hotkey" in v["text"]


def test_underlevel_sentence_does_not_repeat_the_level_tile():
    u = underlevel.view(4, 15, "MapSunTemple", "Sun Temple", False)
    assert u["text"] == "11 levels under this zone (zone level 15)."
    assert len(u["word"]) <= underlevel.WORD_MAX


def test_look_for_next_hint_has_no_jargon():
    js = (ROOT / "web" / "health.js").read_text(encoding="ascii")
    m = re.search(r'var NO_WEIGHTS = ((?:"[^"]*"\s*\+?\s*)+);', js)
    text = "".join(re.findall(r'"([^"]*)"', m.group(1)))
    assert "build calc" not in text and "Path of Building calc" in text


# -- U26 UX-DASH-DENSITY

def test_tools_group_is_last_and_holds_the_set_once_tools():
    sections = re.findall(r'<section id="([a-z-]+)"', MAIN)
    assert sections[-1] == "toolsbox", sections
    tools = MAIN[MAIN.index('id="toolsbox"'):]
    for needle in ('id="layout-form"', 'id="settingsbox"', 'id="gfx"'):
        assert needle in tools, needle
    # folded behind one summary; the hotkey hint stays outside the fold
    fold = tools.index('<details id="tools-more">')
    assert tools.index("Alt+Shift+A") < fold


def test_build_file_and_loot_filter_fold_in_their_own_cards():
    build = _between('id="buildbox"', "</section>")
    assert '<details id="buildfile-more" class="tool-fold">' in build
    assert build.index('id="buildfile-more"') < build.index('id="buildfile-save"')
    search = _between('id="searchbox"', "</section>")
    assert '<details id="filter-more" class="tool-fold">' in search
    i = search.index('id="filter-more"')
    assert i < search.index('id="filter-download"') < search.index('id="filter-merge-file"')
    # the search strings themselves stay open
    assert search.index('id="search-list"') < i


def test_no_nested_fold_for_the_overlay_layout():
    tools = MAIN[MAIN.index('id="toolsbox"'):]
    assert 'id="layout-more"' not in tools


def test_live_regions_stay_within_the_cap():
    live = re.findall(r'aria-live="polite"|role="status"|role="alert"', HTML)
    ids = set(re.findall(r'<[^>]*(?:aria-live="polite"|role="status")[^>]*>', HTML))
    assert len(ids) <= 12, len(ids)
    assert live


def test_dom_order_is_tab_order():
    css = (ROOT / "web" / "app.css").read_text(encoding="utf-8")
    assert not re.search(r"(^|[;{\s])order\s*:", css)
    assert "tabindex=\"1" not in HTML and "tabindex=\"2" not in HTML
    # PLAY-TD-09B-SKELETON: the Play regions are placed by grid-area only,
    # so their DOM order (G, C, T, N, B, I, U) is the Tab order in every class
    play = MAIN[MAIN.index('id="panel-play"'):MAIN.index('id="panel-run"')]
    assert re.findall(r'<section id="play-([a-z])"', play) == list("gctnbiu")
    for r in "gctnbiu":
        assert re.search(r"#play-%s \{ grid-area: %s; \}" % (r, r), css), r
