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

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
HTML = (WEB / "index.html").read_text(encoding="ascii")
CSS = (WEB / "app.css").read_text(encoding="ascii")
JS = {p.name: p.read_text(encoding="ascii") for p in sorted(WEB.glob("*.js"))}
DESIGN = (ROOT / "docs" / "design" / "0001-design-system.md").read_text(encoding="ascii")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
LIVE_ROLES = {"status", "log", "alert", "marquee", "timer"}
# Rewritten by the 1 s tick or on every state push: never inside a live region.
TICKING = ["zone", "zone-time", "level", "who", "pace", "deaths", "levelups", "session",
           "flags", "acts-rows", "maps-rows", "deaths-list", "events", "trade-list"]


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


def test_live_regions_are_few_and_named():
    live = [n for n in nodes() if is_live(n)]
    for n in live:
        assert n.attrs.get("id"), n.attrs  # each is written by id, nowhere else
    # pills, consent error, trade, item check, price, weights, build (2),
    # web data, layout, graphics: a new one is a deliberate change here
    assert len(live) <= 12, [n.attrs.get("id") for n in live]


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
    d = by_id()["deaths"]
    assert [c.attrs for c in d.children] == [{"aria-hidden": "true"}, {"class": "sr-only"}]
    assert d.children[1].all_text() == "Not counted yet"
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
