"""AREA-UX batch 8 (glance review 0004 U25-U27): UX-B9-CARDS,
UX-DASH-DENSITY, UX-OVERLAY-REAL3."""

import re
import srcpaths
from server.al import pricewatch, underlevel

HTML = srcpaths.index_html()
MAIN = HTML[HTML.index("<main>"):HTML.index("</main>")]


def _between(start, end):
    i = MAIN.index(start)
    return MAIN[i:MAIN.index(end, i)]


# -- U25 UX-B9-CARDS

def test_clear_buttons_are_not_primary():
    """A button that throws data away is never the filled primary style."""
    for bid in ("history-clear", "watch-clear"):
        m = re.search(r'<button id="%s"[^>]*>' % bid, MAIN)
        assert m and re.search(r'class="secondary(?: btn-\d+)?"', m.group(0)), bid


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
    js = srcpaths.read("health.js")

    def const(name):
        m = re.search(r'var %s = ((?:"[^"]*"\s*\+?\s*)+);' % name, js)
        return "".join(re.findall(r'"([^"]*)"', m.group(1)))
    # PLAY-TD-19C-BUILD-GRID (review BG-1): the card's short hint, and the
    # calc sentence as a Numbers row naming the optional calc in full
    hint, calc = const("NO_WEIGHTS"), const("NO_WEIGHTS_CALC")
    assert hint == "Check items to see more stats per slot."
    assert "build calc" not in calc and "Path of Building calc" in calc


# -- U26 UX-DASH-DENSITY

def test_tools_group_is_last_and_holds_the_set_once_tools():
    """PLAY-TD-21A-SETTINGS-RAIL (TD-21): Settings is a rail of 6 section
    buttons and a pane of sections in the same order. PLAY-TD-21B-SETTINGS-
    ABOUT split the Tools card: 4 Keys, 5 Appearance and tools (#toolsbox,
    the set-once tools; More, the graphics advisor, is its one fold) and 6
    About and data, the last section. The layout form and the key fields
    are the Overlay section."""
    sections = re.findall(r'<section id="([a-z-]+)"', MAIN)
    assert sections[-1] == "set-about", sections
    settings = MAIN[MAIN.index('id="panel-settings"'):]
    assert re.findall(r'<section id="([a-z-]+)"', settings) == [
        "checks", "set-reading", "set-overlay", "set-keys", "toolsbox", "set-about"]
    rail = re.findall(r'<button id="(rail-[a-z]+)" class="rail-item" type="button" '
                      r'aria-controls="([a-z-]+)"[^>]*>([^<]+)</button>', settings)
    assert [(b, c) for b, c, _ in rail] == [
        ("rail-checks", "checks"), ("rail-reading", "set-reading"),
        ("rail-overlay", "set-overlay"), ("rail-keys", "set-keys"),
        ("rail-tools", "toolsbox"), ("rail-about", "set-about")]
    # the rail names are used exactly (plan 03 section 4, S4)
    assert [t for _, _, t in rail] == ["Checks", "Reading and web data", "Overlay", "Keys",
                                       "Appearance and tools", "About and data"]
    tools = MAIN[MAIN.index('id="toolsbox"'):MAIN.index('id="set-about"')]
    for needle in ('id="settingsbox"', 'id="gfx"', 'id="restart-overlay"', 'id="hints-reset"'):
        assert needle in tools, needle
    assert 'id="layout-form"' not in tools
    # More (the graphics advisor) is the one fold; transfer and restart are rows
    assert tools.count("<details") == 1
    assert tools.index('id="settingsbox"') < tools.index('<details id="gfx"')
    # the hotkey hint is the Keys section, never folded (OVL-KEYS-WEB: as
    # data-hotkey spans the page fills with the bound keys)
    keys = settings[settings.index('id="set-keys"'):settings.index('id="toolsbox"')]
    assert 'data-hotkey="toggle"' in keys and 'data-hotkey="eval"' in keys
    assert "<details" not in keys
    # the version is the last line of About and data, not a fold
    about = settings[settings.index('id="set-about"'):]
    assert 'id="about-version"' in about and 'id="about-fold"' not in MAIN
    # the two change-key fields sit with the layout form, in Overlay
    overlay = settings[settings.index('id="set-overlay"'):settings.index('id="set-keys"')]
    for fid in ("layout-form", "hotkey-eval", "hotkey-toggle"):
        assert 'id="%s"' % fid in overlay, fid


def test_build_file_and_loot_filter_fold_in_their_own_cards():
    """UX-DASH-DENSITY kept the .build file and the loot filter add-on in
    their own cards. PLAY-TD-19C-BUILD-GRID (TD-19, plan 03 section 4):
    folds become pages of those cards, so no fold can grow a card. The
    .build file is the Build card's More page; the loot filter add-on is the
    Search strings card's filter page, a plain div the card's page buttons
    show (PLAY-TD-19D-ITEMS-GRID, review BG-10: no details, no summary)."""
    build = _between('id="buildbox"', "</section>")
    assert "<details" not in build
    assert '<div id="buildfile-more" class="card-page" data-page="more"' in build
    assert build.index('id="buildfile-more"') < build.index('id="buildfile-save"')
    assert 'data-card-open="more"' in build
    search = _between('id="searchbox"', "</section>")
    assert "<details" not in search and "<summary" not in search
    assert re.search(r'<div id="filter-more" class="card-page tool-page" data-page="filter"'
                     r'[^>]* hidden>', search)
    i = search.index('id="filter-more"')
    # TC-FILTER-ONE-CONTROL: the merge is the page's one primary control;
    # the plain download follows it as the small "Or" line
    assert i < search.index('id="filter-merge-file"') < search.index('id="filter-download"')
    assert 'data-card-open="filter"' in search
    # the search strings themselves are on the card's first page
    assert search.index('id="search-list"') < i
    css = srcpaths.read("app.css", encoding="utf-8")
    assert "summary" not in css[css.index(".tool-page"):css.index("/* The pager")]


def test_build_and_items_is_a_fixed_three_by_two_grid():
    """PLAY-TD-19C-BUILD-GRID (TDF-1): the panel is 3 x 2 fixed cells in the
    cockpit classes, not auto-fit columns; Build, Health and next and Search
    strings are its first three cells, cards with pages and no fold.
    PLAY-TD-19D-ITEMS-GRID: Last item, Prices and Item scoring are the other
    three, cards the same way; every column is a cell."""
    css = srcpaths.read("app.css", encoding="utf-8")
    m = re.search(r"@media \(min-width: 64em\) and \(min-height: 43\.75em\) \{\s*"
                  r"\.panel-cards \{([^}]*)\}", css)
    assert m, "the card grid rule in the cockpit query"
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in m.group(1)
    assert "grid-template-rows: repeat(2, minmax(0, 1fr))" in m.group(1)
    panel = MAIN[MAIN.index('id="panel-build"'):MAIN.index('id="panel-run"')]
    assert re.match(r'id="panel-build" class="panel panel-grid panel-cards"', panel)
    cells = re.findall(r'<div class="col">\s*(?:<!--.*?-->\s*)?<section id="([a-z]+)"', panel, re.S)
    assert cells == ["buildbox", "healthbox", "searchbox", "evalbox", "pricesbox",
                     "weightsbox"], cells
    assert panel.count('<div class="col">') == 6
    assert ".panel-cards > .col { display: grid;" in css
    for card in cells:
        sec = _between('id="%s"' % card, "</section>")
        assert "grid-card" in sec.split(">")[0] and " hidden" not in sec.split(">")[0], card
        assert 'class="card-head"' in sec and "data-card-back" in sec, card
        assert re.search(r'class="card-page" data-page="main"', sec), card
    # no element inside the three cards holds a live region (page-wide cap)
    three = panel[:panel.index('id="evalbox"')]
    assert not re.findall(r'aria-live="polite"|role="status"|role="alert"', three)
    # the last three keep three (verdict, price state and weights status)
    # and add none; the tab mark is no live region. PLAY-TD-21A-SETTINGS-RAIL
    # moved the web data switch and its status to Settings
    rest = panel[panel.index('id="evalbox"'):]
    assert len(re.findall(r'aria-live="polite"', rest)) == 3
    assert 'id="webdata-on"' not in panel
    assert "<details" not in panel


def test_no_nested_fold_for_the_overlay_layout():
    tools = MAIN[MAIN.index('id="toolsbox"'):]
    assert 'id="layout-more"' not in tools
    # PLAY-TD-21B-SETTINGS-ABOUT: no fold inside a fold anywhere in Settings;
    # the graphics advisor is the one fold left there
    settings = MAIN[MAIN.index('id="panel-settings"'):]
    assert re.findall(r"<details[^>]*>", settings) == ['<details id="gfx" class="tool gfx">']


def test_live_regions_stay_within_the_cap():
    live = re.findall(r'aria-live="polite"|role="status"|role="alert"', HTML)
    ids = set(re.findall(r'<[^>]*(?:aria-live="polite"|role="status")[^>]*>', HTML))
    # PLAY-TD-09C-BAR (MERGE-SEAMS F2): one bar status word, cap 12 to 11;
    # PLAY-LEGACY-OUT-2: the consent error left with the old card, 11 to 9;
    # PLAY-TD-21A-SETTINGS-RAIL: the web data and layout status lines beside
    # their forms lost the live role, 9 to 5: tab news, the reading word,
    # item check, price, weights status. With the calc row's own region
    # (web/checks.js) that is 6, the page cap of plan 03 4.1.3 (Play's
    # region files build their 3, checked by tests/test_a11y.py)
    assert len(ids) <= 5, len(ids)
    for quiet in ("webdata-status", "layout-status"):
        tag = re.search(r'<[^>]*\bid="%s"[^>]*>' % quiet, HTML).group(0)
        assert "aria-live" not in tag and "role=" not in tag, quiet
    assert live
    # Play's markup holds none; its live regions (verdict, trade status,
    # notice) are built by the region files, the reading word is the bar's
    play = MAIN[MAIN.index('id="panel-play"'):MAIN.index('id="panel-build"')]
    assert not re.findall(r'aria-live="polite"|role="status"|role="alert"', play)


def test_dom_order_is_tab_order():
    css = srcpaths.read("app.css", encoding="utf-8")
    assert not re.search(r"(^|[;{\s])order\s*:", css)
    assert "tabindex=\"1" not in HTML and "tabindex=\"2" not in HTML
    # PLAY-TD-19B-FOUR-TABS (TD-19): four tabs, and the panels follow the
    # tab row in DOM order
    tabs = re.findall(r'<button id="tab-([a-z]+)"[^>]*role="tab"', HTML)
    assert tabs == ["play", "build", "run", "settings"], tabs
    panels = re.findall(r'<div id="panel-([a-z]+)"[^>]*role="tabpanel"', MAIN)
    assert panels == tabs, panels
    # PLAY-TD-09B-SKELETON: the Play regions are placed by grid-area only,
    # so their DOM order (G, C, T, N, B, I, U) is the Tab order in every class
    play = MAIN[MAIN.index('id="panel-play"'):MAIN.index('id="panel-build"')]
    assert re.findall(r'<section id="play-([a-z])"', play) == list("gctnbiu")
    for r in "gctnbiu":
        assert re.search(r"#play-%s \{ grid-area: %s; \}" % (r, r), css), r


# -- OVL-KEYS-WEB (F-026): no page text names a key that is not bound

def test_no_literal_default_key_in_the_page_or_the_hints():
    """Every key the dashboard or a hint names is the bound one (web/
    hotkeys.js paint, hints.town_text), so no 'Alt+Shift+' default is
    written into web/ or server/al/hints.py."""
    paths = [p for p in srcpaths.WEB.rglob("*") if p.is_file()
             and p.suffix in (".html", ".js", ".css")]
    assert paths
    paths.append(srcpaths.ROOT / "server" / "al" / "hints.py")
    hits = [p.name for p in paths if "Alt+Shift+" in p.read_text(encoding="utf-8")]
    assert hits == [], hits


def test_every_hotkey_span_is_a_known_key():
    spans = re.findall(r'data-hotkey="([^"]*)"', HTML)
    assert spans and set(spans) <= {"eval", "toggle"}, spans
    assert '<script src="/web/hotkeys.js" defer></script>' in HTML
    assert HTML.index("/web/hotkeys.js") < HTML.index("/web/app.js")
