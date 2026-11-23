"""PLAY-F-189A-SPACING-BADGE (F-189): one spacing scale, one badge, one
list row, held by a lint.

- Every margin, padding and gap in web/*.css (longhands and the region
  padding custom properties included) is 0, auto or one of the spacing
  tokens --al-space-0 to --al-space-4; a negative step is
  calc(-1 * var(--al-space-N)) and the one border allowance is
  calc(var(--al-space-N) - 1px) (a 2 px dashed edge giving back its extra
  1 px a side, so the box never moves).
- Exactly 3 radius values are used: --al-radius-card, --al-radius-control
  and --al-radius-pill (0 for a square corner).
- No rule, script or markup names the old badge classes .pill, .verdict,
  .tab-mark or .tag; .badge is the one badge.
- One list-row rule with two densities.

Design 0001 section 4. Reads tracked files only."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
APP_CSS = WEB / "app.css"
DOC = ROOT / "docs" / "design" / "0001-design-system.md"

OLD = ("pill", "verdict", "tab-mark", "tag")
TOKEN = r"var\(--al-space-[0-4]\)"
PART = re.compile(r"^(0|auto|%s|calc\(-1 \* %s\)|calc\(%s - 1px\)|var\(--region-pad\)"
                  r"|var\(--pad-u, %s\))$" % (TOKEN, TOKEN, TOKEN, TOKEN))
SPACING = re.compile(r"(?<![\w-])((?:margin|padding)(?:-[a-z]+)*|gap|row-gap|column-gap"
                     r"|--region-pad|--pad-u)\s*:\s*([^;{}]+)")
RADIUS = re.compile(r"(?<![\w-])border(?:-[a-z]+)*-radius\s*:\s*([^;{}]+)")
RADII = {"var(--al-radius-card)", "var(--al-radius-control)", "var(--al-radius-pill)"}


def _nocomment(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _sheets():
    sheets = sorted(WEB.glob("*.css"))
    assert APP_CSS in sheets and len(sheets) > 1
    return sheets


def _parts(value):
    """The value's space-separated parts, a bracketed part kept whole."""
    v = re.sub(r"\s*!important\s*$", "", value.strip())
    parts, cur, depth = [], "", 0
    for ch in v:
        depth += (ch == "(") - (ch == ")")
        if ch.isspace() and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def spacing_offenders(css):
    """(property, value) pairs whose value is not on the spacing scale."""
    bad = []
    for prop, value in SPACING.findall(_nocomment(css)):
        if not all(PART.match(p) for p in _parts(value)):
            bad.append((prop, value.strip()))
    return bad


def radius_values(css):
    """Every distinct non-zero radius value used in the sheet."""
    out = set()
    for value in RADIUS.findall(_nocomment(css)):
        for p in _parts(value):
            if p != "0":
                out.add(p)
    return out


def old_badge_names(text, kind):
    """Places a text names an old badge class (css, js or html)."""
    names = "|".join(re.escape(n) for n in OLD)
    if kind == "css":
        return re.findall(r"\.(%s)(?![\w-])" % names, _nocomment(text))
    if kind == "html":
        hits = []
        for cls in re.findall(r'class="([^"]*)"', text):
            hits += [c for c in cls.split() if c in OLD]
        return hits
    # js: a selector string or a class name given to the DOM; string
    # literals and comments are read left to right, so code between two
    # strings is never taken for one
    hits = []
    lex = r"""/\*.*?\*/|//[^\n]*|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'"""
    for tok in re.findall(lex, text, flags=re.S):
        if tok[0] in "\"'":
            hits += re.findall(r"\.(%s)(?![\w-])" % names, tok[1:-1])
    hits += re.findall(r"""class(?:Name|List)[^;\n]*["'](%s)["']""" % names, text)
    hits += re.findall(r"""setAttribute\(\s*["']class["']\s*,\s*["'](%s)["']""" % names, text)
    return hits


# --- the lint holds ----------------------------------------------------------

def test_every_spacing_value_is_a_token():
    bad = {}
    for sheet in _sheets():
        got = spacing_offenders(sheet.read_text(encoding="ascii"))
        if got:
            bad[sheet.name] = got
    assert not bad, bad


def test_exactly_three_radius_values():
    used = set()
    for sheet in _sheets():
        used |= radius_values(sheet.read_text(encoding="ascii"))
    assert used == RADII, used


def test_region_padding_properties_are_tokens():
    css = "\n".join(_nocomment(s.read_text(encoding="ascii")) for s in _sheets())
    decls = re.findall(r"--(?:region-pad|pad-u)\s*:\s*([^;{}]+)", css)
    assert decls, "no region padding found"
    for v in decls:
        assert re.fullmatch(r"%s|var\(--pad-u, %s\)" % (TOKEN, TOKEN), v.strip()), v


def test_no_old_badge_class_in_rules_scripts_or_markup():
    bad = {}
    for p in sorted(WEB.glob("*.css")):
        got = old_badge_names(p.read_text(encoding="ascii"), "css")
        if got:
            bad[p.name] = got
    for p in sorted(WEB.glob("*.js")):
        got = old_badge_names(p.read_text(encoding="ascii"), "js")
        if got:
            bad[p.name] = got
    for p in sorted(WEB.glob("*.html")):
        got = old_badge_names(p.read_text(encoding="ascii"), "html")
        if got:
            bad[p.name] = got
    assert not bad, bad


def test_one_badge_rule_carries_the_states():
    css = _nocomment(APP_CSS.read_text(encoding="ascii"))
    assert re.search(r"(^|\})\s*\.badge\s*\{[^}]*border-radius:\s*var\(--al-radius-pill\)", css)
    for state in ("running", "done", "idle", "pending", "blocked", "failed"):
        assert '.badge[data-state="%s"]' % state in css, state
    for verdict in ("upgrade", "risky"):
        assert '.badge[data-verdict="%s"]' % verdict in css, verdict
    html = (WEB / "index.html").read_text(encoding="ascii")
    for ident in ("reading", "eval-word", "price-badge", "rates-pill", "book-state"):
        m = re.search(r'id="%s" class="([^"]*)"' % ident, html)
        assert m and "badge" in m.group(1).split(), ident
    assert html.count('<span class="badge" hidden></span></button>') == 4
    tabs = (WEB / "tabs.js").read_text(encoding="ascii")
    assert 'querySelector(".badge")' in tabs


def test_tab_mark_has_no_600_under_14px():
    # TD23-1: the tab mark word takes the badge's meta step, not the micro one
    css = _nocomment(APP_CSS.read_text(encoding="ascii"))
    rule = re.search(r"button\.tab \.badge\s*\{([^}]*)\}", css)
    assert rule, "no tab mark rule"
    assert "font-size" not in rule.group(1)
    base = re.search(r"(^|\})\s*\.badge\s*\{([^}]*)\}", css).group(2)
    assert "var(--al-fs-meta)" in base


def test_one_list_row_rule_with_two_densities():
    css = _nocomment(APP_CSS.read_text(encoding="ascii"))
    dense = re.search(r"\.checks-list > li, \.gfx-list > li, \.al-pager-list > li, "
                      r"\.health-list > li\s*\{\s*min-width: 0; padding: 0; \}", css)
    roomy = re.search(r"\.checks-list > li, \.gfx-list > li\s*\{\s*border-top: 1px solid "
                      r"var\(--fk-border\); padding: var\(--al-space-1\) 0; \}", css)
    assert dense and roomy
    assert not re.search(r"\.(checks|gfx)-list li\s*\{[^}]*padding", css)


def test_design_doc_states_the_badge_and_row_rules():
    doc = DOC.read_text(encoding="ascii")
    sec = doc[doc.index("## 4. Spacing and shape"):]
    sec = sec[:sec.index("\n## ", 4)]
    for needle in ("`.badge`", "List row: one rule, two densities", "tests/test_spacing_scale.py"):
        assert needle in sec, needle


# --- the lint catches what it should -----------------------------------------

def test_lint_catches_literals_and_allows_the_forms():
    assert spacing_offenders("a { padding: 6px 8px; }") == [("padding", "6px 8px")]
    assert spacing_offenders("a { margin-left: 0.5rem; }")
    assert spacing_offenders("a { gap: 0 0.3em; }")
    assert spacing_offenders("a { --region-pad: 0.375rem; }")
    assert not spacing_offenders(
        "a { margin: 0 auto; padding: var(--al-space-1) var(--al-space-3); gap: 0;"
        " margin-bottom: calc(-1 * var(--al-space-1)); padding: 0 calc(var(--al-space-2) - 1px);"
        " padding: var(--region-pad) var(--al-space-3) !important; }")
    assert not spacing_offenders("/* padding: 6px */ a { margin: 0; }")


def test_lint_catches_old_badges():
    assert old_badge_names(".pill { margin: 0; }", "css") == ["pill"]
    assert old_badge_names("#x.tab-mark:hover {}", "css") == ["tab-mark"]
    assert not old_badge_names(".pills {} #rates-pill {} .ev-tag {}", "css")
    assert old_badge_names('<span class="a verdict">', "html") == ["verdict"]
    assert not old_badge_names('<p id="rates-pill" class="badge">', "html")
    assert old_badge_names('b.querySelector(".tab-mark")', "js") == ["tab-mark"]
    assert old_badge_names('n.className = "tag";', "js") == ["tag"]
    assert not old_badge_names('kind: "verdict", v.pill.state, r.tag', "js")
    assert radius_values("a { border-radius: 4px; } b { border-radius: 0 var(--al-radius-control) 0 0; }") == {
        "4px", "var(--al-radius-control)"}
