"""UX-REVIEW (docs/design/0004-glance-review.md): glanceability rules from
research 0008 held by tests - contrast at the overlay's real opacity floor,
7:1 for glance text, a high-contrast mode, the type floor, no motion and
the 320 px phone width."""

import json
import re
from pathlib import Path

import pytest

import srcpaths
from test_design_contrast import _hex, over, plate, ratio

ROOT = Path(__file__).resolve().parent.parent
APP_CSS = srcpaths.path("app.css")
OVERLAY_CSS = ROOT / "app" / "overlay" / "overlay.css"
LAYOUT_JS = ROOT / "app" / "shared" / "layout.js"
TOKENS = ROOT / "ops" / "fleet_kit" / "tokens.json"
WEB_JS = srcpaths.web_js() + sorted(
    (ROOT / "app" / "overlay").glob("*.js")) + sorted((ROOT / "app" / "shared").glob("*.js"))
WHITE = (255, 255, 255)
GLANCE = 7.0  # research 0008: "target 7:1 for glance text" (WCAG 2.2 SC 1.4.6)
TEXT = 4.5    # WCAG 2.2 SC 1.4.3
PHONE = 320   # design 0001 section 4
# Content width of a card at 320 px: main padding 2x16, card padding 2x16,
# card border 2x1.
PHONE_CARD = PHONE - 32 - 32 - 2


def _css(path):
    return path.read_text(encoding="ascii")


def _strip_media(css):
    """The base rules only: every @media block removed (brace-balanced)."""
    out, i = [], 0
    while True:
        j = css.find("@media", i)
        if j < 0:
            out.append(css[i:])
            return "".join(out)
        out.append(css[i:j])
        k = css.index("{", j)
        depth = 0
        for n in range(k, len(css)):
            if css[n] == "{":
                depth += 1
            elif css[n] == "}":
                depth -= 1
                if depth == 0:
                    i = n + 1
                    break


def _media(css, query):
    m = re.search(r"@media\s*\(\s*" + re.escape(query) + r"\s*\)\s*\{", css)
    if not m:
        return None
    depth, start = 0, m.end() - 1
    for n in range(start, len(css)):
        if css[n] == "{":
            depth += 1
        elif css[n] == "}":
            depth -= 1
            if depth == 0:
                return css[start + 1:n]
    raise AssertionError("unbalanced @media " + query)


def _rules(css):
    """(selector, body) pairs of a flat stylesheet without comments."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(s.strip(), b) for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _overlay_vars():
    root = re.search(r":root\s*\{(.*?)\}", _css(OVERLAY_CSS), re.S).group(1)
    return {n: v.strip() for n, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", root)}


def _opacity_floor():
    m = re.search(r"opacity:\s*\[\s*([\d.]+)\s*,", LAYOUT_JS.read_text(encoding="ascii"))
    assert m, "LIMITS.opacity not found in layout.js"
    return float(m.group(1))


def _scale_floor():
    m = re.search(r"scale:\s*\[\s*([\d.]+)\s*,", LAYOUT_JS.read_text(encoding="ascii"))
    assert m, "LIMITS.scale not found in layout.js"
    return float(m.group(1))


def _plate(v):
    return plate(v)


def overlay_ratio(fg_hex, plate_alpha=None):
    """Opaque text over the plate over a white scene, the plate at
    `plate_alpha` (its CSS default when None); every composite rounded to
    8 bits a channel. OVL-TD05-PLATE: the layout's "opacity" sets only
    --al-plate-a (layout.js opacityCss), so text is never faded."""
    v = _overlay_vars()
    rgb, alpha = _plate(v)
    plate = over(rgb, alpha if plate_alpha is None else plate_alpha, WHITE)
    return ratio(_hex(fg_hex), plate)


def _overlay_text_colours():
    """Every var(--x) used as a text `color:` in the overlay base rules."""
    used = set()
    for _sel, body in _rules(_strip_media(_css(OVERLAY_CSS))):
        for name in re.findall(r"(?<![-\w])color\s*:\s*var\(--([\w-]+)\)", body):
            used.add(name)
    return sorted(used)


# --- U1: overlay contrast at the opacity floor, not only at 1.0 ------------

def test_opacity_floor_is_the_plate_floor():
    """OVL-TD05-PLATE: the slider's floor is the plate alpha floor 0.80,
    and the page CSS it drives sets that knob, never a page opacity."""
    assert _opacity_floor() == 0.8
    js = LAYOUT_JS.read_text(encoding="ascii")
    assert '":root { --al-plate-a: "' in js
    assert not re.search(r"html\s*\{\s*opacity", js)


def test_overlay_slider_is_labelled_background():
    """The slider sets the plate behind the text, so it reads 'Background',
    not 'Opacity' (the text never fades)."""
    html = srcpaths.index_html()
    m = re.search(r"<label>\s*([A-Za-z ]+?)\s*<span id=\"layout-opacity-out\"", html)
    assert m and m.group(1) == "Background", m and m.group(1)
    assert re.search(r'id="layout-opacity"[^>]*min="%s"' % _opacity_floor(), html)


def test_overlay_has_text_colours():
    assert "fk-text" in _overlay_text_colours()


@pytest.mark.parametrize("name", _overlay_text_colours())
def test_overlay_text_meets_4_5_at_opacity_floor(name):
    v = _overlay_vars()
    got = overlay_ratio(v[name], _opacity_floor())
    assert got >= TEXT, f"{name} at plate alpha {_opacity_floor()}: {got:.2f}"


# --- U2: glance text 7:1 (research 0008) -----------------------------------

def test_overlay_glance_text_7_to_1_at_opacity_floor():
    # zone line, timer and HUD numbers all use the full text colour
    v = _overlay_vars()
    rules = dict(_rules(_strip_media(_css(OVERLAY_CSS))))
    assert "var(--fk-text)" in rules[".hud"]
    assert "var(--fk-text)" in rules[".timer"]
    got = overlay_ratio(v["fk-text"], _opacity_floor())
    assert got >= GLANCE, got


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_dashboard_glance_values_7_to_1(theme):
    t = json.loads(TOKENS.read_text(encoding="ascii"))["themes"][theme]
    # glance values sit on stat tiles (no own background, inside surface)
    for bg in ("surface", "surface-2"):
        assert ratio(_hex(t["text"]), _hex(t[bg])) >= GLANCE
    # the glance values never take a muted or status colour
    rules = _rules(_strip_media(_css(APP_CSS)))
    for sel, body in rules:
        if ".value" in sel or (".stat-zone .sub .mono" == sel):
            m = re.search(r"(?<![-\w])color\s*:\s*([^;]+);", body)
            assert m is None or m.group(1).strip() == "var(--fk-text)", sel


# --- U3: high-contrast mode (research 0008, Xbox guideline 101) ------------

@pytest.mark.parametrize("path", [APP_CSS, OVERLAY_CSS], ids=["dashboard", "overlay"])
def test_high_contrast_mode_lifts_muted_text(path):
    block = _media(_css(path), "prefers-contrast: more")
    assert block is not None, f"{path.name}: no @media (prefers-contrast: more)"
    # the overlay's secondary text is its own token (OVL-TD05-LEGIBILITY)
    muted = "--al-ovl-text-2" if path == OVERLAY_CSS else "--fk-text-muted"
    assert re.search(re.escape(muted) + r"\s*:\s*var\(--fk-text\)", block), block


def test_overlay_high_contrast_plate_is_opaque():
    css = _css(OVERLAY_CSS)
    block = _media(css, "prefers-contrast: more")
    m = re.search(r"--al-plate\s*:\s*([^;]+);", block or "")
    assert m and re.fullmatch(r"#[0-9a-fA-F]{6}", m.group(1).strip()), block
    # same :root selector, so the override wins only by coming later
    assert css.index("prefers-contrast") > css.index(":root")
    # the opaque plate keeps its rgb, so the plate ratio maths still holds
    rgb, _a = _plate(_overlay_vars())
    assert _hex(m.group(1)) == rgb


def test_overlay_high_contrast_text_at_opacity_floor():
    v = _overlay_vars()
    got = overlay_ratio(v["fk-text"], plate_alpha=1.0)
    assert got >= GLANCE, got


def test_overlay_card_edge_not_tied_to_muted_text():
    rules = dict(_rules(_strip_media(_css(OVERLAY_CSS))))
    assert "var(--al-edge)" in rules[".evalcard"]
    block = _media(_css(OVERLAY_CSS), "prefers-contrast: more")
    assert "--al-edge" not in block


# --- U4: type floor --------------------------------------------------------

def _sizes(css):
    return re.findall(r"font(?:-size)?\s*:[^;]*?([\d.]+)(rem|px)", css)


def _overlay_font_sizes():
    """Every font size the overlay declares, in px: literals in font /
    font-size declarations and the --al-ovl-fs-* tokens they use."""
    css = re.sub(r"/\*.*?\*/", "", _css(OVERLAY_CSS), flags=re.S)
    v = _overlay_vars()
    out = []
    for decl in re.findall(r"(?<![-\w])font(?:-size)?\s*:([^;]+);", css):
        for name in re.findall(r"var\(--([\w-]+)\)", decl):
            assert name.startswith("al-ovl-fs-"), f"font size from --{name}"
            m = re.fullmatch(r"([\d.]+)px", v[name])
            assert m, f"--{name}: {v[name]}"
            out.append(float(m.group(1)))
        stripped = re.sub(r"var\([^)]*\)", "", decl)
        out.extend(float(n) for n, _u in re.findall(r"([\d.]+)(px|rem|em|pt)(?![\w-])", stripped))
    return out


def _al_font_tokens():
    """--al-fs-* token values (rem) from the token block of web/app.css."""
    root = re.search(r":root\s*\{(.*?)\}", _css(APP_CSS), re.S).group(1)
    return {n: float(v) for n, v in
            re.findall(r"--(al-fs-[\w-]+)\s*:\s*([\d.]+)rem\s*;", root)}


def test_dashboard_type_floor_13px():
    """Every dashboard stylesheet (web/*.css, so a later region sheet is
    covered with no test edit): no literal font size and no --al-fs-*
    token used as a font size under 13 px at root 16 px."""
    tokens = _al_font_tokens()
    assert len(tokens) == 6, tokens
    sheets = srcpaths.web_css()
    assert APP_CSS in sheets
    for sheet in sheets:
        css = re.sub(r"/\*.*?\*/", "", _css(sheet), flags=re.S)
        for value, unit in _sizes(css):
            px = float(value) * (16 if unit == "rem" else 1)
            assert px >= 13, f"{sheet.name}: {value}{unit}"
        for name in re.findall(r"font(?:-size)?\s*:[^;]*?var\(--(al-fs-[\w-]+)\)", css):
            assert name in tokens, f"{sheet.name}: unknown token --{name}"
            assert tokens[name] * 16 >= 13, f"{sheet.name}: --{name}"


def test_overlay_type_floor_12px_after_zoom():
    sizes = _overlay_font_sizes()
    assert sizes and min(sizes) * _scale_floor() >= 12


def test_overlay_two_font_sizes_16_and_14():
    """OVL-TD05-LEGIBILITY (design 0001 section 3): two sizes only, 16 px
    for HUD lines and the status word, 14 px for card lines; nothing under
    14 px; sizes only through the two --al-ovl-fs-* tokens."""
    v = _overlay_vars()
    assert {n: v[n] for n in v if n.startswith("al-ovl-fs-")} == {
        "al-ovl-fs-hud": "16px", "al-ovl-fs-card": "14px"}
    sizes = _overlay_font_sizes()
    assert sorted(set(sizes)) == [14.0, 16.0], sizes
    assert min(sizes) >= 14
    rules = dict(_rules(_strip_media(_css(OVERLAY_CSS))))
    assert "var(--al-ovl-fs-hud)" in rules[".hud"]
    for card in (".trade", ".evalcard"):
        assert "var(--al-ovl-fs-card)" in rules[card], card
    # no font size outside the token block and the three plate rules
    for sel, body in rules.items():
        if sel not in (":root", ".hud", ".trade", ".evalcard"):
            assert not re.search(r"(?<![-\w])font(?:-size)?\s*:", body), sel


def test_overlay_has_no_page_opacity():
    """OVL-TD05-LEGIBILITY: text is opaque; the plate alone carries the
    alpha. No opacity rule anywhere in overlay.css, and the plate alpha
    is the --al-plate-a knob with a 0.86 default."""
    css = re.sub(r"/\*.*?\*/", "", _css(OVERLAY_CSS), flags=re.S)
    assert not re.search(r"html\s*\{\s*opacity", css)
    assert not re.search(r"(?<![-\w])opacity\s*:", css)
    assert re.fullmatch(r"rgba\(15, 18, 22, var\(--al-plate-a, 0\.86\)\)",
                        _overlay_vars()["al-plate"])


def test_overlay_halo_on_every_plate():
    """The note 0041 halo, no stroke: every plate's text carries it."""
    v = _overlay_vars()
    assert v["al-halo"] == "0 0 2px #000, 0 0 2px #000, 0 1px 2px #000"
    rules = dict(_rules(_strip_media(_css(OVERLAY_CSS))))
    for sel in (".hud", ".trade", ".evalcard"):
        assert re.search(r"text-shadow\s*:\s*var\(--al-halo\)\s*;", rules[sel]), sel
        assert re.search(r"border\s*:\s*1px solid var\(--fk-border\)", rules[sel]), sel
    assert "text-stroke" not in _css(OVERLAY_CSS)


def test_overlay_separator_is_a_gap_not_a_glyph():
    """F-094: the "|" between level and deaths is a 10 px gap; #sep stays
    in the page (render_gate still fills it) but is never drawn."""
    rules = _rules(_strip_media(_css(OVERLAY_CSS)))
    nums = [b for s, b in rules if s == ".row.nums"]
    assert nums and re.search(r"display\s*:\s*flex", nums[0])
    assert re.search(r"(?<![-\w])gap\s*:\s*10px", nums[0])
    hidden = [s for s, b in rules if re.search(r"display\s*:\s*none", b)]
    assert any(".sep" in [x.strip() for x in s.split(",")] for s in hidden), hidden
    html = (ROOT / "app" / "overlay" / "index.html").read_text(encoding="ascii")
    assert 'id="sep" class="sep"' in html


# --- U5: no motion by default ---------------------------------------------

def test_dashboard_declares_no_motion():
    base = re.sub(r"/\*.*?\*/", "", _strip_media(_css(APP_CSS)), flags=re.S)
    assert "@keyframes" not in base
    assert not re.search(r"(?<![-\w])(animation|transition)\s*:", base)
    assert not re.search(r"scroll-behavior\s*:\s*smooth", base)


def test_reduced_motion_still_honoured():
    block = _media(_css(APP_CSS), "prefers-reduced-motion: reduce")
    assert block and "animation: none" in block and "transition: none" in block


def test_overlay_kills_motion_outright():
    assert re.search(r"\*\s*\{\s*animation:\s*none !important;\s*transition:\s*none !important;",
                     _css(OVERLAY_CSS))


@pytest.mark.parametrize("path", WEB_JS, ids=lambda p: p.name)
def test_scripts_start_no_animation(path):
    js = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="ascii"), flags=re.S)
    js = re.sub(r"//[^\n]*", "", js)
    assert "requestAnimationFrame" not in js
    assert ".animate(" not in js
    assert not re.search(r"behavior\s*:\s*[\"']smooth", js)


# --- U6: phone width (320 px, no horizontal scroll) ------------------------

def test_no_fixed_width_wider_than_a_phone_card():
    css = re.sub(r"min\(\s*\d+px\s*,\s*100%\s*\)", "100%", _css(APP_CSS))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for _sel, body in _rules(_strip_media(css)):
        for prop, val in re.findall(
                r"(?<![-\w])(width|min-width|flex|flex-basis|grid-template-columns)\s*:\s*([^;]+);",
                body):
            for n in re.findall(r"(\d+)px", val):
                assert int(n) <= PHONE_CARD, f"{prop}: {val}"


def test_viewport_meta_allows_zoom():
    html = srcpaths.index_html()
    m = re.search(r'<meta name="viewport" content="([^"]+)"', html)
    assert m and "width=device-width" in m.group(1)
    assert "maximum-scale" not in m.group(1) and "user-scalable" not in m.group(1)


def test_stat_tile_sub_line_wraps_long_names():
    """UX-U7 (live 320 px pass): an unbroken character name under the level
    overflowed its tile into the deaths tile. PLAY-LEGACY-OUT-1: the old
    tiles are gone; the strip's sub lines are .one-line rows, which wrap
    anywhere in the flow sizes (ellipsis, with the full text in title, only
    in the cockpit sizes), and the moved pace line wraps."""
    rules = _rules(_strip_media(_css(APP_CSS)))
    assert not [s for s, _ in rules if ".stat .sub" in s or s.startswith(".stats")]
    one = [b for s, b in rules if s == ".one-line"]
    assert one and any(re.search(r"overflow-wrap\s*:\s*anywhere", b) for b in one)
    strip = srcpaths.read("strip.js", encoding="utf-8")
    assert '"st-sub row-title muted one-line"' in strip
    assert 'setAttr(c.sub, "title", sub)' in strip
    moved = [b for s, b in rules if s == "#actsbox > .sub"]
    assert moved and re.search(r"overflow-wrap\s*:\s*anywhere", moved[0])


def test_overlay_forced_colours_keeps_window_transparent():
    """UX-U8: in forced colours Chromium paints the viewport Canvas, which
    would make the click-through overlay an opaque block over the game. The
    root opts out and stays transparent; the plates opt back in."""
    block = _media(_css(OVERLAY_CSS), "forced-colors: active")
    assert block, "overlay needs a forced-colors block"
    rules = dict(_rules(block))
    root = rules.get("html, body", "")
    assert re.search(r"forced-color-adjust\s*:\s*none", root)
    assert re.search(r"background\s*:\s*transparent", root)
    plates = rules.get(".hud, .trade, .evalcard", "")
    assert re.search(r"forced-color-adjust\s*:\s*auto", plates)


def test_overlay_forced_colours_plate_is_opaque_canvas():
    """UX-U8: the plate is the system Canvas colour, opaque, so plate text
    keeps the player's system contrast over any scene."""
    block = _media(_css(OVERLAY_CSS), "forced-colors: active")
    assert re.search(r"--al-plate\s*:\s*Canvas\s*;", block)


def test_overlay_forced_colours_card_edges_use_highlight():
    """UX-U8: the trade warn edge and the upgrade green edge fell to plain
    CanvasText in forced colours; both use the kept Highlight colour."""
    rules = dict(_rules(_media(_css(OVERLAY_CSS), "forced-colors: active")))
    edge = rules.get('.trade, .evalcard[data-verdict="upgrade"]', "")
    assert re.search(r"border-left-color\s*:\s*Highlight", edge)


# -- UX-NEWEST / UX-DASH-LAYOUT (glance review 0004 U17, U18)

def _main_order():
    html = srcpaths.index_html(encoding="utf-8")
    main = html[html.index("<main>"):html.index("</main>")]
    ids = re.findall(r'<section(?: id="([a-z-]+)")?(?: class="([a-z -]+)")?', main)
    return [i or c.split()[-1] for i, c in ids], main


def test_last_session_card_opens_run_and_history():
    """U17: the Last session card has no live region, so it is noticed by its
    place. PLAY-LEGACY-OUT-2 moved it as it is from Play to the first card
    of the Run and history tab (Run since PLAY-TD-19B-FOUR-TABS), where
    the run is looked back on; the consent card it shared region C with is
    gone (region C's setup card asks instead)."""
    order, main = _main_order()
    run = main[main.index('id="panel-run"'):main.index('id="panel-settings"')]
    first = re.search(r'<section id="([a-z-]+)"', run).group(1)
    assert first == "summarybox", first
    assert "consent" not in order
    play = main[main.index('id="panel-play"'):main.index('id="panel-build"')]
    assert 'id="summarybox"' not in play


def test_last_session_card_has_a_steady_edge():
    """U17: a steady accent edge, never motion (design 0001 principle 3)."""
    css = srcpaths.read("app.css", encoding="utf-8")
    assert re.search(r"\.card\.session\s*\{[^}]*border-left\s*:\s*4px solid var\(--fk-accent\)", css)


def test_dashboard_card_order_glance_first():
    """U18: glance first, then the run in progress, then reference and
    settings. DOM order is the visual and Tab order (no CSS order). Since
    PLAY-TD-09B-SKELETON the cards sit in the Play regions (G, C, T, N, B,
    I, U). PLAY-LEGACY-OUT-2: Play holds only the regions; the Last session
    card opens Run and history and the full item check opens Items and
    prices, ahead of the price tools. PLAY-TD-19B-FOUR-TABS (TD-19): the
    tabs are Play, Build and items, Run, Settings; the item cards follow
    the build cards in Build and items, and Run opens with Last session."""
    order, _ = _main_order()
    regions = [x for x in order if x.startswith("play-")]
    assert regions == ["play-%s" % r for r in "gctnbiu"], regions
    assert order[:7] == regions, order
    want = ["buildbox", "evalbox", "pricesbox", "summarybox", "actsbox", "mapsbox",
            "deathsbox", "events", "toolsbox"]
    seen = [x for x in order if x in want]
    assert seen == want, seen
    css = srcpaths.read("app.css", encoding="utf-8")
    assert not re.search(r"(^|[;{\s])order\s*:", css), "CSS order breaks Tab order"


def test_price_and_points_follows_price():
    """U17: the item's own price against its points reads next to Price.
    PLAY-TD-19D-ITEMS-GRID: both are rows of the Last item card's one list,
    the price rows first and price and points right after them, before the
    Item scoring card's weights."""
    _, main = _main_order()
    assert main.index('id="price-result"') < main.index('id="eval-rows"') < main.index('id="weights"')
    js = srcpaths.read("app.js", encoding="utf-8")
    assert "evalRows.check.concat(evalRows.price, evalRows.after)" in js
    ev = js[js.index("  function renderEval(ev) {"):js.index("  function fillBand(doc) {")]
    assert ev.index("P.valueView(ev.value)") < ev.index("P.upgradeView(ev.upgrade)")


def test_overlay_settings_fold_but_hotkey_hint_stays_open():
    """U18, amended by U26 (UX-DASH-DENSITY): set-once overlay settings fold
    away inside the Tools group; the hotkey hint stays outside the fold. The
    save status sits next to the form, so it is shown whenever a save can
    happen (the form is only usable with the fold open; review F1)."""
    _, main = _main_order()
    tools = main[main.index('id="toolsbox"'):]
    fold = tools[tools.index('<details id="tools-more">'):]
    assert 'id="layout-form"' in fold and 'id="layout-status"' in fold
    assert fold.index('id="layout-form"') < fold.index('id="layout-status"')
    # OVL-KEYS-WEB: the hint names the bound keys through data-hotkey spans
    hint = tools[:tools.index('<details id="tools-more">')]
    assert 'data-hotkey="toggle"' in hint and 'data-hotkey="eval"' in hint


# --- F-159: colour only for exceptions; one filled button --------------------

_FILL = re.compile(r"(?<![-\w])background(?:-color)?\s*:\s*([^;]+)")
_LOUD = re.compile(r"var\(--fk-(?:accent|status-[\w-]+)\)")


def _button_rules():
    """(selector, body) of every app.css rule, @media blocks included,
    whose selector names a button element."""
    css = re.sub(r"/\*.*?\*/", "", _css(APP_CSS), flags=re.S)
    pairs = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    out = []
    for sel, body in pairs:
        sel = sel.strip()
        if sel.startswith("@"):
            continue
        if any(re.match(r"button(?![-\w])", s.strip().split()[-1])
               for s in sel.split(",") if s.strip()):
            out.append((sel, body))
    return out


def test_one_filled_button_rule():
    """F-159: app.css has exactly one filled button rule, button.primary;
    a fill is a background in the accent or a status colour."""
    filled = [sel for sel, body in _button_rules()
              for v in _FILL.findall(body) if _LOUD.search(v)]
    assert filled == ["button.primary"], filled


def test_base_button_is_quiet():
    """F-159: the bare button has no fill and the control edge as border."""
    base = [body for sel, body in _rules(_strip_media(_css(APP_CSS))) if sel == "button"]
    assert len(base) == 1, base
    body = base[0]
    assert re.search(r"(?<![-\w])background\s*:\s*transparent\s*;", body), body
    assert re.search(r"(?<![-\w])border\s*:\s*1px solid var\(--al-control-edge\)", body), body
    assert re.search(r"(?<![-\w])color\s*:\s*var\(--fk-text\)\s*;", body), body


def test_only_the_setup_card_uses_button_primary():
    """F-159: the one button.primary in web/ is the setup card's consent
    button (web/setupcard.js); no other script or the page sets it."""
    html = srcpaths.index_html()
    assert not re.search(r'class="[^"]*(?<![-\w])primary(?![-\w])', html)
    hits = []
    for path in srcpaths.web_js():
        src = path.read_text(encoding="ascii")
        for pat in (r'"button"[^;\n]*\bprimary\b',
                    r'className\s*=[^;\n]*["\' ]primary["\' ]',
                    r'classList\.(?:add|toggle|replace)\([^)]*["\']primary["\']'):
            if re.search(pat, src):
                hits.append(path.name)
                break
    assert hits == ["setupcard.js"], hits
    setup = srcpaths.read("setupcard.js")
    assert re.search(r'r\.action === "consent" \? "primary" : "secondary"', setup)
