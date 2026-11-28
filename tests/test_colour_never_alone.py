"""PLAY-F-165-COLOUR-WORD-TEST (F-165): colour never works alone.

Design 0001 section 6: a status colour only repeats a word or a kit glyph,
never carries the meaning by itself. This static test reads every rule in
the dashboard sheets (web/*.css, web/panels/*.css) and the overlay sheet
(app/overlay/overlay.css) that puts a var(--fk-status-*) token in any
property, takes the subject of each selector (its last compound: classes
and id) and proves the element it styles also writes a word or a glyph:

- in the page markup (the assembled dashboard page, app/overlay/index.html)
  every element carrying the subject has text of its own, a descendant
  with text, or an id / class the scripts write text into;
- an element made only by a script (web/*.js, web/panels/*.js, the overlay
  and app/shared scripts) is found by its class or id literal, and the
  script writes text into it (textContent, setText, a text node, a text
  argument of the file's own el() helper, a text: field) on that line,
  within WINDOW lines after it, or through the name it is bound to;
- a rule that draws its own glyph (content: "...") carries its word.

Static, stdlib only, no browser. An explicit allow-list names the few
rules that need none of this, each with its reason; a stale entry fails.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import srcpaths

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "app" / "overlay"
SHARED = ROOT / "app" / "shared"

STATUS = re.compile(r"var\(\s*--fk-status-[a-z0-9-]+\s*\)")
WINDOW = 15
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
NESTING_AT = ("@media", "@supports", "@layer", "@container")
TEXT_WRITE = re.compile(r"\.textContent\s*=|\.innerText\s*=|\bsetText\s*\(|createTextNode\s*\("
                        r"|\.replaceChildren\s*\(|\btext\s*:")

# (sheet path relative to the repo, selector as written) -> reason
ALLOWED = {
    ("web/app.css", ".edge-warn"):
        "a spare edge tone: no markup or script gives an element this class; "
        "an element that takes it must carry a word (notice.css tones do)",
    # PROGRESSION-VIEW (decision 0092): svg paths of the own-drawn tree; the
    # state is carried by the line style (dashed ring, outer ring) and the
    # legend words beside the tree, the warn tone only reinforces it
    ("web/panels/progression.css", ".tv-edge-d"):
        "tree links due next: dashed, named by the legend beside the tree",
    ("web/panels/progression.css", ".tv-node-d"):
        "tree nodes due next: a dashed ring, named by the legend beside the tree",
    ("web/panels/progression.css", ".tv-fresh"):
        "newly due tree nodes: an outer ring, named by the legend beside the tree",
}


# --- CSS -------------------------------------------------------------------

def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def css_rules(css):
    """[(selector, body)] of every style rule, nested @media / @supports
    flattened; other at-rules (@keyframes, @font-face) skipped."""
    css = _strip_comments(css)
    out = []
    i, n = 0, len(css)
    while i < n:
        open_at = css.find("{", i)
        if open_at < 0:
            break
        prelude = css[i:open_at].strip()
        depth, j = 1, open_at + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[open_at + 1:j - 1]
        # a prelude may carry a stray ';' after an @import / @charset line
        prelude = prelude.rsplit(";", 1)[-1].strip()
        if prelude.startswith("@"):
            if prelude.startswith(NESTING_AT):
                out.extend(css_rules(body))
        elif prelude:
            out.append((prelude, body))
        i = j
    return out


def _split_top(text, seps):
    parts, depth, cur, quote = [], 0, [], ""
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and ch in seps:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def status_rules(css):
    """[(selector, body)] for rules with a status token in a property value
    (custom property definitions such as :root's --fk-status-ok excluded)."""
    found = []
    for sel, body in css_rules(css):
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, value = decl.split(":", 1)
            if not prop.strip().startswith("--") and STATUS.search(value):
                found.append((sel, body))
                break
    return found


def subject(selector):
    """(classes, ids, pseudo_element) of the selector's last compound."""
    compounds = _split_top(selector, " >+~")
    last = compounds[-1] if compounds else ""
    pseudo_el = bool(re.search(r"::?(before|after|marker)\b", last))
    bare = re.sub(r"\[[^\]]*\]", "", last)
    bare = re.sub(r"::?[a-zA-Z-]+(\([^)]*\))?", "", bare)
    return (re.findall(r"\.([A-Za-z0-9_-]+)", bare), re.findall(r"#([A-Za-z0-9_-]+)", bare),
            pseudo_el)


def draws_glyph(body):
    m = re.search(r"(?:^|;)\s*content\s*:\s*(\"[^\"]*\"|'[^']*')", body)
    return bool(m and m.group(1)[1:-1].strip())


# --- markup ----------------------------------------------------------------

class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text = [], ""

    def classes(self):
        return (self.attrs.get("class") or "").split()


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None)
        self.cur = self.root
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        self.nodes.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        self.nodes.append(node)

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += data


def parse_html(html):
    t = Tree()
    t.feed(html)
    return t.nodes


# --- scripts ---------------------------------------------------------------

def _text_helpers(js):
    """Names of the file's own builder helpers that take a text argument
    right after the class argument, e.g. el(doc, tag, cls, text)."""
    names = set()
    for name, params in re.findall(r"function\s+(\w+)\s*\(([^)]*)\)", js):
        ps = [p.strip() for p in params.split(",")]
        if "cls" in ps and "text" in ps and ps.index("text") == ps.index("cls") + 1:
            names.add(name)
    return names


def _writes_text(line, helpers):
    if TEXT_WRITE.search(line):
        return True
    for h in helpers:
        # a helper call whose class literal is followed by a text argument
        if re.search(r"\b%s\s*\([^;]*[\"'][^\"']*[\"']\s*,\s*[^)\s]" % re.escape(h), line):
            return True
    return False


def js_worded(token, scripts):
    """True when a script makes or finds the token (a class word or an id in
    a string literal, or nodes.<id>) and writes text into that element."""
    lit = re.compile(r"[\"'](?:[^\"'\n]*\s)?%s(?:\s[^\"'\n]*)?[\"']" % re.escape(token))
    prop = re.compile(r"\.%s\.textContent\s*=" % re.escape(token))
    for js in scripts:
        if prop.search(js):
            return True
        helpers = _text_helpers(js)
        lines = js.split("\n")
        for i, line in enumerate(lines):
            if not lit.search(line):
                continue
            if any(_writes_text(l, helpers) for l in lines[i:i + WINDOW + 1]):
                return True
            bound = re.match(r"\s*(?:var|let|const)?\s*([A-Za-z_$][\w$]*)\s*[:=]", line)
            if bound:
                name = re.escape(bound.group(1))
                if re.search(r"\b%s\.textContent\s*=|\bsetText\s*\([^,)]*\b%s\b" % (name, name),
                             js):
                    return True
    return False


def node_worded(node, scripts):
    if node.text.strip():
        return True
    tokens = ([node.attrs["id"]] if node.attrs.get("id") else []) + node.classes()
    if any(js_worded(t, scripts) for t in tokens):
        return True
    return any(node_worded(c, scripts) for c in node.children)


# --- the check -------------------------------------------------------------

def findings(sheets, html, scripts, allowed=None):
    """[(sheet, selector, why)] for every status-coloured selector whose
    element carries no word or glyph. sheets: [(name, css text)]."""
    allowed = ALLOWED if allowed is None else allowed
    nodes = parse_html(html)
    out = []
    for name, css in sheets:
        for sel_list, body in status_rules(css):
            for sel in _split_top(sel_list, ","):
                if (name, sel) in allowed:
                    continue
                classes, ids, pseudo_el = subject(sel)
                if pseudo_el and draws_glyph(body):
                    continue
                if not classes and not ids:
                    out.append((name, sel, "no class or id to trace the element"))
                    continue
                hits = [n for n in nodes
                        if all(c in n.classes() for c in classes)
                        and all(n.attrs.get("id") == i for i in ids)]
                if hits:
                    bad = [n for n in hits if not node_worded(n, scripts)]
                    if bad:
                        out.append((name, sel, "a %s in the markup has no word or glyph"
                                    % bad[0].tag))
                    continue
                if not any(js_worded(t, scripts) for t in ids + classes):
                    out.append((name, sel, "no element with a word or glyph carries it"))
    return out


def dashboard():
    sheets = [(p.relative_to(ROOT).as_posix(), p.read_text(encoding="ascii"))
              for p in srcpaths.web_css()]
    scripts = [p.read_text(encoding="ascii") for p in srcpaths.web_js()]
    return sheets, srcpaths.index_html(), scripts


def overlay():
    sheet = OVERLAY / "overlay.css"
    sheets = [(sheet.relative_to(ROOT).as_posix(), sheet.read_text(encoding="ascii"))]
    scripts = [p.read_text(encoding="ascii")
               for p in sorted(OVERLAY.glob("*.js")) + sorted(SHARED.glob("*.js"))]
    return sheets, (OVERLAY / "index.html").read_text(encoding="ascii"), scripts


PLANT_CSS = "\n.foo { color: var(--fk-status-ok) }\n"
PLANT_NODE = '<span class="foo"></span>'


def _plant(html, node):
    return html.replace("</body>", node + "\n</body>", 1)


# --- tests -----------------------------------------------------------------

def test_dashboard_colour_never_alone():
    sheets, html, scripts = dashboard()
    assert sum(len(status_rules(css)) for _, css in sheets) >= 10, "the scan found no rules"
    assert findings(sheets, html, scripts) == []


def test_overlay_colour_never_alone():
    sheets, html, scripts = overlay()
    assert status_rules(sheets[0][1]), "the scan found no overlay rules"
    assert findings(sheets, html, scripts) == []


def test_planted_rule_on_wordless_node_fails():
    sheets, html, scripts = dashboard()
    sheets = sheets + [("web/planted.css", PLANT_CSS)]
    got = findings(sheets, _plant(html, PLANT_NODE), scripts)
    assert [(s, sel) for s, sel, _ in got] == [("web/planted.css", ".foo")]
    # the same rule in an existing sheet, and with no node at all
    name, css = sheets[0]
    got = findings([(name, css + PLANT_CSS)], html, scripts)
    assert [sel for _, sel, _ in got] == [".foo"]


def test_planted_border_and_overlay_fail():
    sheets, html, scripts = dashboard()
    plant = "\n.foo[data-tone=\"ok\"] { border-left: 3px solid var(--fk-status-bad); }\n"
    got = findings([("web/planted.css", plant)], _plant(html, PLANT_NODE), scripts)
    assert [sel for _, sel, _ in got] == ['.foo[data-tone="ok"]']
    osheets, ohtml, oscripts = overlay()
    got = findings([(osheets[0][0], osheets[0][1] + PLANT_CSS)], _plant(ohtml, PLANT_NODE),
                   oscripts)
    assert [sel for _, sel, _ in got] == [".foo"]


def test_planted_rule_with_a_word_passes():
    sheets, html, scripts = dashboard()
    for node in ('<span class="foo">[+] ok</span>',
                 '<p class="foo"><span class="glyph">[#]</span></p>'):
        got = findings([("web/planted.css", PLANT_CSS)], _plant(html, node), scripts)
        assert got == [], node
    glyph = '\n.foo::before { content: "[+] "; color: var(--fk-status-ok); }\n'
    assert findings([("web/planted.css", glyph)], html, scripts) == []


def test_custom_property_definitions_are_not_rules():
    assert status_rules(":root { --fk-status-ok: #46b85c; --x: var(--fk-status-ok); }") == []
    rules = status_rules("@media (forced-colors: active) { .a .b { color: var(--fk-status-ok); } }")
    assert rules and subject(rules[0][0])[0] == ["b"]


def test_allow_list_entries_are_live_and_reasoned():
    sheets, _, _ = dashboard()
    osheets, _, _ = overlay()
    live = {(name, sel) for name, css in sheets + osheets
            for sel_list, _ in status_rules(css) for sel in _split_top(sel_list, ",")}
    for key, reason in ALLOWED.items():
        assert key in live, "stale allow-list entry %r" % (key,)
        assert len(reason.split()) >= 5, key
    # each entry is needed: without the list exactly these rules are found
    sheets, html, scripts = dashboard()
    got = findings(sheets, html, scripts, allowed={})
    osheets, ohtml, oscripts = overlay()
    got += findings(osheets, ohtml, oscripts, allowed={})
    assert {(s, sel) for s, sel, _ in got} == set(ALLOWED)
