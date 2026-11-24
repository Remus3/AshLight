"""AREA-UX batch 6 (glance review 0004 U22-U24): the search strings card,
the loot filter words, the promises (Settings > About and data since
PLAY-TD-21B-SETTINGS-ABOUT) and the waystone card text.
Static reads of web/ plus the core's waystone template; stdlib only."""

import re
from pathlib import Path

import srcpaths
from server.al.state import overlay_card, waystone_text
from server.al.text.common import CARD_LINE

ROOT = Path(__file__).resolve().parents[1]
HTML = srcpaths.index_html()
CSS = srcpaths.read("app.css")
SEARCH = srcpaths.read("search.js")
APP = srcpaths.read("app.js")
DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."
CARD_MAX = CARD_LINE  # design 0001 section 9 rule 6 (26 since CARD-LINE-LIMIT-FLIP)


def _footer():
    m = re.search(r"<footer[^>]*>(.*?)</footer>", HTML, re.S)
    assert m, "footer"
    return m.group(1)


def _flat(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def test_search_strings_wrap_instead_of_a_one_line_input():
    """UX-B5-CARDS: no one-line input. PLAY-TD-19C-BUILD-GRID: a string is a
    one-line pager row (full text in title) whose Full text page is the
    keyboard-reachable twin; the import line still breaks anywhere."""
    assert 'createElement("input")' not in SEARCH
    assert "P.rowRule(span, t)" in SEARCH and "P.wrap(t, shape.cols, shape.lines)" in SEARCH
    assert re.search(r"\.filter-line \{[^}]*overflow-wrap: anywhere", CSS)


def test_copy_feedback_adds_no_live_region():
    # the outcome rides on the clicked button's own name, never a live region
    assert "aria-live" not in SEARCH and '"role"' not in SEARCH
    assert 'btn.setAttribute("aria-label", name + " ("' in SEARCH
    assert 'id="search-status"' not in HTML
    # TEST-WEB-PANELS-C2 (adjudicator ruling): downloadFilter lives in
    # web/panels/filter.js
    m = re.search(r"function downloadFilter\(\) \{(.*?)\n  \}", srcpaths.read("panels/filter.js"), re.S)
    assert m and "aria-live" not in m.group(1)
    assert 'setAttribute("aria-label"' in m.group(1)


def test_copy_buttons_are_real_buttons():
    assert 'var btn = el(doc, "button", "secondary btn-24", "Copy");' in SEARCH
    assert 'btn.type = "button"' in SEARCH


def test_filter_words_say_what_it_does_and_that_nothing_is_written():
    m = re.search(r'<section id="searchbox".*?</section>', HTML, re.S)
    text = _flat(m.group(0))
    # PLAY-TD-19C-BUILD-GRID (review BG-3): the loot filter page's words
    assert "AshLight adds its dated blocks at the top and hides nothing." in text
    assert "Your own file is not changed." in text
    assert "The copy goes to your downloads." in text
    assert "Move it to the game's filter folder yourself." in text
    # the Build file page keeps the promise for the planner folder
    assert "AshLight writes nothing into your game folders." in _flat(HTML)


def _section(sid):
    i = HTML.index('<section id="%s"' % sid)
    return HTML[i:HTML.index("</section>", i)]


def test_footer_keeps_the_disclaimer_and_folds_the_promises():
    """PLAY-TD-21B-SETTINGS-ABOUT (plan 03 section 3.4): the footer keeps the
    disclaimer sentence, words unchanged and in the text colour, beside the
    trademark sentence on one row; the promises fold left the footer and
    reads open in Settings > About and data, always on the page."""
    foot = _footer()
    assert "<p>%s</p>" % DISCLAIMER in foot
    assert '<p class="muted">Path of Exile is a trademark of Grinding Gear Games.</p>' in foot
    assert "<details" not in foot and 'id="promises"' not in foot
    about = _section("set-about")
    m = re.search(r'<div id="promises" class="rail-block promises"[^>]*>(.*?)</div>', about, re.S)
    assert m, "promises in About and data"
    assert "<details" not in about
    text = _flat(m.group(1))
    assert "What AshLight does and never does" in text
    for words in ("Client.txt, only after you allow it",
                  "clipboard once each time you press the item check hotkey",
                  "Sends a key press, click or chat message to the game",
                  "Reads or changes the game's memory",
                  "Writes into your game folders",
                  "Asks for your account, password or login cookie"):
        assert words in text, words
    assert "aria-live" not in m.group(1) and "role=" not in m.group(1)


def test_waystone_card_lines_fit_the_overlay_card():
    risky = [{"label": "extra fire damage", "short": "Extra fire dmg"},
             {"label": "less recovery", "short": "Less recovery"},
             {"label": "monster crits", "short": "Monster crits"},
             {"label": "chilled ground", "short": "Chilled ground"}]
    for ws in ({"tier": 15, "risky": risky, "build_loaded": True},
               {"tier": 15, "risky": risky, "build_loaded": False},
               {"tier": 3, "risky": [], "build_loaded": True},
               {"tier": 9, "unidentified": True}):
        t = waystone_text(ws)
        assert 0 < len(t["head"]) <= CARD_MAX, t
        assert len(t["line"]) <= CARD_MAX, t
    assert waystone_text({"tier": 15, "risky": risky, "build_loaded": True})["head"] == \
        "Risky for this build"


RISKY_WS = {"tier": 15, "build_loaded": False, "risky": [
    {"id": "extra_element", "label": "extra fire damage", "short": "Extra fire dmg"}]}


def _ws_eval(ws, error="no gear slot for this item class"):
    return {"ok": False, "error": error, "verdict": None, "at": 1000.0,
            "item": {"name": "Doom Trail", "base": "Waystone (Tier 15)"}, "waystone": ws}


def test_risky_waystone_card_takes_the_warn_edge():
    card = overlay_card(_ws_eval(RISKY_WS), None, 1001.0)
    assert card["head"] == "Risky waystone" and card["verdict"] == "risky"
    calm = dict(RISKY_WS, risky=[])
    assert overlay_card(_ws_eval(calm), None, 1001.0)["verdict"] == "note"
    unid = {"tier": 9, "unidentified": True}
    assert overlay_card(_ws_eval(unid), None, 1001.0)["verdict"] == "note"
    css = (ROOT / "app" / "overlay" / "overlay.css").read_text(encoding="ascii")
    assert re.search(r'\.evalcard\[data-verdict="risky"\] \{ border-left-color: '
                     r'var\(--fk-status-warn\); \}', css)
    assert re.search(r'\.evalcard\[data-verdict="risky"\] \{ border-left-color: Highlight; \}',
                     css)


def test_waystone_verdict_is_not_replaced_by_the_price_card_without_a_build():
    price = {"at": 1000.2, "status": "link", "league": "Standard"}
    ev = _ws_eval(RISKY_WS, error="no build loaded")
    card = overlay_card(ev, price, 1001.0)
    assert card["head"] == "Risky waystone", card
    assert card["verdict"] == "risky"
