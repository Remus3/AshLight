"""UX-A11Y: a stdlib accessibility check of the dashboard (web/).

Static, no browser and no npm dependency: html.parser walks web/index.html
and regexes read web/*.js and web/app.css. It holds design 0001 section 11
S1 (headings, landmarks), S2 (labels), S4 (keyboard, focus ring), N6
(polite announcements only) and C1 (every text colour is a measured token
pair), plus the rule that pushed updates are not chatty: nothing that a
timer or a state push rewrites sits in a live region, and the live pills
are written only when their words change. Glance review 0004 U14."""

import re
from html.parser import HTMLParser
from pathlib import Path

import srcpaths

ROOT = Path(__file__).resolve().parents[1]
HTML = srcpaths.index_html()
CSS = srcpaths.read("app.css")
JS = {p.name: p.read_text(encoding="ascii") for p in srcpaths.web_js()}
DESIGN = (ROOT / "docs" / "design" / "0001-design-system.md").read_text(encoding="ascii")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
LIVE_ROLES = {"status", "log", "alert", "marquee", "timer"}
# Rewritten by the 1 s tick or on every state push: never inside a live region.
# PLAY-LEGACY-OUT-1: the old tiles and trade list are gone; region G and T
# build their own nodes (web/strip.js, web/feed.js) and are not live regions.
TICKING = ["pace", "acts-rows", "maps-rows", "deaths-list", "events"]


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text = [], ""

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_text(self):
        return self.text + "".join(c.all_text() for c in self.children)


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += data


def tree():
    t = Tree()
    t.feed(HTML)
    return t.root


def nodes(tag=None):
    return [n for n in tree().walk() if tag is None or n.tag == tag]


def by_id():
    return {n.attrs["id"]: n for n in tree().walk() if "id" in n.attrs}


def is_live(n):
    live = n.attrs.get("aria-live")
    return (live is not None and live != "off") or n.attrs.get("role") in LIVE_ROLES


def test_landmarks_once_each_and_main_holds_the_cards():
    body = [n for n in nodes("body")][0]
    top = [c.tag for c in body.children]
    for tag in ("header", "main", "footer"):
        assert top.count(tag) == 1, (tag, top)
    for s in nodes("section"):
        assert any(a.tag == "main" for a in s.ancestors()), s.attrs


def test_headings_start_at_one_and_never_skip_a_level():
    levels = [int(n.tag[1]) for n in nodes() if re.fullmatch(r"h[1-6]", n.tag)]
    assert levels[0] == 1 and levels.count(1) == 1, levels
    for prev, cur in zip(levels, levels[1:]):
        assert cur <= prev + 1, (prev, cur)


def test_every_labelled_section_points_at_its_own_heading():
    for s in nodes("section"):
        ref = s.attrs.get("aria-labelledby")
        if ref is None:
            assert s.attrs.get("aria-label"), s.attrs
            continue
        inside = {n.attrs.get("id"): n for n in s.walk()}
        assert ref in inside and re.fullmatch(r"h[1-6]", inside[ref].tag), ref


def test_announcements_are_polite_never_assertive():
    for n in nodes():
        if "aria-live" in n.attrs:
            assert n.attrs["aria-live"] == "polite", n.attrs
        assert n.attrs.get("role") not in ("alert", "alertdialog", "marquee"), n.attrs
    for name, src in JS.items():
        assert "assertive" not in src, name
        assert not re.search(r"""role["']?\s*,\s*["']alert""", src), name


def test_ticking_values_are_not_live_regions():
    ids = by_id()
    for i in TICKING:
        n = ids[i]
        assert not is_live(n), i
        assert not any(is_live(a) for a in n.ancestors()), i


def test_live_pills_are_written_only_when_they_change():
    src = JS["app.js"]
    m = re.search(r"function setPill\([^)]*\) \{(.*?)\n  \}", src, re.S)
    assert m, "setPill"
    body = m.group(1)
    assert ".textContent =" not in body, "setPill must go through setText"
    assert re.search(r"function setText\(node, text\) \{\s*if \(node\.textContent !== text\)", src)


# PLAY-LEGACY-OUT-2 (plan 03 section 9, 4.1.3): Play's live regions are the
# verdict (region I), the trade status (region T), the notice (region N) and
# the bar's reading word; the region files build the first three.
PLAY_LIVE_FILES = {"itemcard.js": "verdict", "feed.js": "trade status",
                   "notice.js": "notice"}
REGION_FILES = ("strip.js", "context.js", "setupcard.js", "feed.js", "notice.js",
                "buildline.js", "itemcard.js", "keptchecks.js")


def test_live_regions_are_few_and_named():
    live = [n for n in nodes() if is_live(n)]
    for n in live:
        assert n.attrs.get("id"), n.attrs  # each is written by id, nowhere else
    # tab news, the one bar status word, item check, price, weights, build
    # (2), web data, layout. The cap was 11 (design 0004, U16; AREA-AUDIT
    # P8-2; PLAY-TD-09C-BAR / MERGE-SEAMS F2 dropped the feed pill);
    # PLAY-LEGACY-OUT-2 removed the consent error with the old consent card,
    # so it is 9: a new one replaces one of these, never adds a tenth.
    # PLAY-TD-21A-SETTINGS-RAIL took the live role off the Settings status
    # lines; PLAY-TD-21B-SETTINGS-ABOUT holds the page to at most 6 (plan
    # 03 4.1.3): the markup's 5 (tab news, the bar status word, item check,
    # price, weights status) and the calc row region web/checks.js builds.
    assert len(live) + 1 <= 6, [n.attrs.get("id") for n in live]
    settings = by_id()["panel-settings"]
    assert not [n.attrs for n in settings.walk() if is_live(n)]
    # Play's own markup holds none: its regions build their own
    play = by_id()["panel-play"]
    assert not [n.attrs for n in play.walk() if is_live(n)]


def test_play_has_at_most_four_live_regions():
    """Plan 03 4.1.3: at most 4 live regions on Play: verdict, trade
    status, notice and the bar's reading word (PLAY-LEGACY-OUT-2)."""
    for name in REGION_FILES:
        src = JS[name]
        polite = re.search(r"""setAttribute\("aria-live", "polite"\)""", src)
        assert bool(polite) == (name in PLAY_LIVE_FILES), name
    head = [n for n in tree().walk() if n.tag == "header"][0]
    bar = [n.attrs.get("id") for n in head.walk() if is_live(n)]
    assert "reading" in bar
    assert len(PLAY_LIVE_FILES) + 1 <= 4


def test_bar_has_one_status_word_on_every_tab():
    # PLAY-TD-09C-BAR (MERGE-SEAMS F2, F-151): the bar holds the character
    # slot and ONE status word; #reading is the visible reading indicator of
    # the ToS floor on every tab (in the header, outside every panel), and
    # the feed pill is gone. The word is the worse of the reading and the
    # feed state, written only through ALDash.barStatus.
    every = list(tree().walk())
    head = [n for n in every if n.tag == "header"][0]
    inside = [n for n in every if head in list(n.ancestors())]
    live = [n.attrs.get("id") for n in inside if is_live(n)]
    assert live == ["tab-news", "reading"], live
    reading = [n for n in inside if n.attrs.get("id") == "reading"][0]
    assert reading.attrs.get("aria-live") == "polite"
    assert not any(a.attrs.get("role") == "tabpanel" for a in reading.ancestors())
    assert [n for n in inside if n.attrs.get("id") == "bar-char"]
    assert not [n for n in every if n.attrs.get("id") == "link"]
    app = JS["app.js"]
    assert 'showPill("link"' not in app and "D.linkView(" not in app
    assert re.search(r'showPill\("reading", D\.barStatus\(', app)
    assert len(re.findall(r'showPill\("reading"', app)) == 1
    # the news line is a polite region that takes no room in the bar
    assert re.search(r"\.tab-news \{ position: absolute; width: 1px; height: 1px;", CSS)


def test_no_positive_tabindex():
    for n in nodes():
        t = n.attrs.get("tabindex")
        assert t is None or int(t) <= 0, n.attrs
    for name, src in JS.items():
        assert not re.search(r"tabIndex\s*=\s*[1-9]", src), name
        assert not re.search(r"""tabindex["']?\s*,\s*["']?[1-9]""", src), name


def _label_for(n, labels):
    if n.attrs.get("aria-label") or n.attrs.get("aria-labelledby"):
        return True
    if n.attrs.get("id") in labels:
        return True
    return any(a.tag == "label" for a in n.ancestors())


def test_every_control_has_a_name():
    labels = {n.attrs["for"] for n in nodes("label") if "for" in n.attrs}
    for n in nodes():
        if n.tag == "button":
            assert n.all_text().strip() or n.attrs.get("aria-label"), n.attrs
        if n.tag in ("input", "select", "textarea") and n.attrs.get("type") != "hidden":
            assert _label_for(n, labels), n.attrs
        if n.tag == "summary":
            assert n.all_text().strip(), n.attrs


def test_aria_label_only_where_it_is_allowed():
    # ARIA 1.2: aria-label is prohibited on generic and paragraph roles
    # (p, div, span with no role), so screen readers may skip it there.
    for n in nodes():
        if "aria-label" in n.attrs and n.tag in ("p", "div", "span") and "role" not in n.attrs:
            raise AssertionError(f"aria-label on a bare <{n.tag}>: {n.attrs}")
    assert '$("deaths").setAttribute("aria-label"' not in JS["app.js"]


def test_deaths_dash_has_screen_reader_text():
    # PLAY-LEGACY-OUT-1: the old #deaths tile is gone; the strip's Deaths
    # cell (web/strip.js) hides its dash from screen readers and gives them
    # words instead, in a visually hidden span (web/strip.css .st-said).
    assert 'id="deaths"' not in HTML
    strip = JS["strip.js"]
    assert '{ key: "deaths", label: "Deaths", sr: "not counted yet" }' in strip
    assert re.search(r'if \(empty\) \{ setAttr\(c\.shown, "aria-hidden", "true"\); \}', strip)
    assert "c.said.hidden = !empty;" in strip
    css = srcpaths.read("strip.css")
    assert re.search(r"#play-g \.st-said \{[^}]*clip-path: inset\(50%\)", css)
    assert re.search(r"\.sr-only \{[^}]*clip: rect\(0 0 0 0\)", CSS)


def test_every_focusable_kind_has_a_visible_focus_ring():
    rules = re.findall(r"([^{}]+)\{([^}]*outline:\s*3px solid var\(--fk-text\)[^}]*)\}", CSS)
    sel = " ".join(s for s, _ in rules)
    for kind in ("button", "a", "summary", "textarea", "input", "select"):
        covered = re.search(rf"(^|[\s,]){kind}:focus-visible", sel) or \
            (kind in ("input", "select") and ".layout-form :focus-visible" in sel
             and ".weights-form :focus-visible" in sel and "input:focus-visible" in sel)
        assert covered, kind
    assert "outline: none" not in CSS and "outline:none" not in CSS


def test_text_colours_are_measured_token_pairs():
    """C1: every colour the dashboard paints text in is a kit token whose
    pairs are recomputed by tests/test_design_contrast.py (section 5.2)."""
    block = re.search(r"```al-contrast\n(.*?)```", DESIGN, re.S).group(1)
    measured = set()
    for line in block.splitlines():
        if line.strip() and not line.startswith("#"):
            fg = line.split()[0]
            if fg.startswith(("light.", "dark.")):
                measured.add(fg.split(".", 1)[1])
    used = set(re.findall(r"(?<![-\w])color:\s*var\(--fk-([a-z0-9-]+)\)", CSS))
    assert used, "no text colours found"
    assert used <= measured, used - measured
    # no literal colour on text outside the token blocks (C3)
    assert not re.search(r"(?<![-\w])color:\s*(#|rgb)", CSS)


# -- PLAY-TD-09B-SKELETON (F-025, F-096, F-086; plan 03 sections 3.2, 3.8, 3.9)

REGIONS = "gctnbiu"
# PLAY-LEGACY-OUT-1 removed the g-tiles, t-trades and b-alert groups;
# PLAY-LEGACY-OUT-2 the rest: the consent, language, tip and Zone tip cards
# are gone, the Last session card and the zone guide moved to Run and
# history, the full item check to Items and prices (merged into Build and
# items by PLAY-TD-19B-FOUR-TABS).
GONE = ("consent", "consent-yes", "consent-path", "consent-error", "langbox",
        "lang-dismiss", "hintbox", "hint-text", "zone-note-box", "zone-note",
        "campaign-hints")
MOVED = {"summarybox": "panel-run", "zone-guide": "panel-run", "evalbox": "panel-build"}


def test_play_is_seven_regions_with_no_tab_stop_and_no_columns():
    ids = by_id()
    play = ids["panel-play"]
    assert "tabindex" not in play.attrs, play.attrs  # F-096: no panel tab stop
    assert not any(c in n.attrs.get("class", "").split() for n in nodes()
                   for c in ("play-main", "play-side"))
    regions = [c for c in play.children if c.tag == "section"]
    assert [c.attrs.get("id") for c in play.children] == ["play-" + r for r in REGIONS]
    for r, sec in zip(REGIONS, regions):
        assert sec.attrs.get("data-region") == r and "tabindex" not in sec.attrs, sec.attrs
        kids = sec.children
        assert kids[0].tag == "h2" and kids[0].attrs["id"] == sec.attrs["aria-labelledby"]
        assert kids[0].all_text().strip(), r
        # a screen reader never hears the region heading twice (review TD9B-2)
        inner = {n.all_text().strip() for k in kids[1:] for n in k.walk() if n.tag == "h2"}
        assert kids[0].all_text().strip() not in inner, r
        assert kids[1].attrs.get("class") == "slot" and not kids[1].children, r
        assert len(kids) == 2, (r, [k.attrs for k in kids[2:]])  # no legacy group
    assert not [n.attrs for n in nodes() if "data-legacy" in n.attrs]
    ids = by_id()
    for gone in GONE:
        assert gone not in ids, gone
    for card, panel in MOVED.items():
        assert ids[panel] in list(ids[card].ancestors()), (card, panel)
    # the zone guide sits in the Act times card
    assert ids["actsbox"] in list(ids["zone-guide"].ancestors())


def _media_blocks(css):
    out = []
    for m in re.finditer(r"@media \(min-width: ([\d.]+)em\) and \(min-height: ([\d.]+)em\) \{",
                         css):
        depth, k = 0, m.end() - 1
        for n in range(k, len(css)):
            depth += {"{": 1, "}": -1}.get(css[n], 0)
            if depth == 0:
                out.append((float(m.group(1)), float(m.group(2)), css[k + 1:n]))
                break
    return out


def test_cockpit_classes_follow_the_token_block_queries():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    i = css.index(".panel-play {")
    tokens = [(w, h, re.search(r"--al-size-class:\s*(\w+)", b).group(1))
              for w, h, b in _media_blocks(css[:i]) if "--al-size-class" in b]
    assert len(tokens) == 8, tokens
    classes = []
    for w, h, b in _media_blocks(css[i:]):
        nine = re.search(r"--track-9:\s*([\d.]+)rem", b)
        if nine and "grid-template-areas" not in b:
            classes.append((w, h, {"3.25": "compact", "6": "full"}[nine.group(1)]))
    assert classes == tokens, classes
    # the cockpit starts at the lowest compact threshold; under it is flow
    assert tokens[0][:2] == (64.0, 43.75)
    assert re.search(r"@media \(min-width: 64em\) and \(min-height: 43\.75em\) \{\s*"
                     r"main \{ max-width: 100rem;", css)


def test_the_short_window_query_and_the_play_shell_are_gone():
    """F-086: the 820px query and the Play half of the 900 x 560 shell go;
    the shell stays for the other tabs, and Play is never a scroll box."""
    assert "max-height: 820px" not in CSS
    assert ".play-main" not in CSS and ".play-side" not in CSS
    shell = CSS[CSS.index("@media (min-width: 900px) and (min-height: 560px)"):]
    shell = shell[:shell.index("\n}\n")]
    for sel in (".stat", ".stats", ".panel-play", ".trade", "#panel-play {"):
        assert sel not in shell.replace("#panel-play:not", ""), sel
    assert re.search(r"html \{ font-size: calc\(100% \* var\(--al-s\)\); \}", CSS)
