"""UX-REVIEW (docs/design/0004-glance-review.md): glanceability rules from
research 0008 held by tests - contrast at the overlay's real opacity floor,
7:1 for glance text, a high-contrast mode, the type floor, no motion and
the 320 px phone width."""

import json
import re
from pathlib import Path

import pytest

from test_design_contrast import _hex, over, ratio

ROOT = Path(__file__).resolve().parent.parent
APP_CSS = ROOT / "web" / "app.css"
OVERLAY_CSS = ROOT / "app" / "overlay" / "overlay.css"
LAYOUT_JS = ROOT / "app" / "shared" / "layout.js"
TOKENS = ROOT / "ops" / "fleet_kit" / "tokens.json"
WEB_JS = sorted((ROOT / "web").glob("*.js")) + sorted(
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
    m = re.fullmatch(r"rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)", v["al-plate"])
    assert m, v["al-plate"]
    return tuple(int(m.group(i)) for i in (1, 2, 3)), float(m.group(4))


def overlay_ratio(fg_hex, window_opacity, plate_alpha=None):
    """Text over the plate over a white scene, the whole window at
    `window_opacity`; every composite rounded to 8 bits a channel."""
    v = _overlay_vars()
    rgb, alpha = _plate(v)
    plate = over(rgb, alpha if plate_alpha is None else plate_alpha, WHITE)
    bg = over(plate, window_opacity, WHITE)
    fg = over(_hex(fg_hex), window_opacity, WHITE)
    return ratio(fg, bg)


def _overlay_text_colours():
    """Every var(--x) used as a text `color:` in the overlay base rules."""
    used = set()
    for _sel, body in _rules(_strip_media(_css(OVERLAY_CSS))):
        for name in re.findall(r"(?<![-\w])color\s*:\s*var\(--([\w-]+)\)", body):
            used.add(name)
    return sorted(used)


# --- U1: overlay contrast at the opacity floor, not only at 1.0 ------------

def test_overlay_has_text_colours():
    assert "fk-text" in _overlay_text_colours()


@pytest.mark.parametrize("name", _overlay_text_colours())
def test_overlay_text_meets_4_5_at_opacity_floor(name):
    v = _overlay_vars()
    got = overlay_ratio(v[name], _opacity_floor())
    assert got >= TEXT, f"{name} at opacity {_opacity_floor()}: {got:.2f}"


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
    assert re.search(r"--fk-text-muted\s*:\s*var\(--fk-text\)", block), block


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
    got = overlay_ratio(v["fk-text"], _opacity_floor(), plate_alpha=1.0)
    assert got >= GLANCE, got


def test_overlay_card_edge_not_tied_to_muted_text():
    rules = dict(_rules(_strip_media(_css(OVERLAY_CSS))))
    assert "var(--al-edge)" in rules[".evalcard"]
    block = _media(_css(OVERLAY_CSS), "prefers-contrast: more")
    assert "--al-edge" not in block


# --- U4: type floor --------------------------------------------------------

def _sizes(css):
    return re.findall(r"font(?:-size)?\s*:[^;]*?([\d.]+)(rem|px)", css)


def test_dashboard_type_floor_13px():
    for value, unit in _sizes(_css(APP_CSS)):
        px = float(value) * (16 if unit == "rem" else 1)
        assert px >= 13, f"{value}{unit}"


def test_overlay_type_floor_12px_after_zoom():
    sizes = [float(v) for v, _u in _sizes(_css(OVERLAY_CSS))]
    assert sizes and min(sizes) * _scale_floor() >= 12


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
    html = (ROOT / "web" / "index.html").read_text(encoding="ascii")
    m = re.search(r'<meta name="viewport" content="([^"]+)"', html)
    assert m and "width=device-width" in m.group(1)
    assert "maximum-scale" not in m.group(1) and "user-scalable" not in m.group(1)


def test_stat_tile_sub_line_wraps_long_names():
    """UX-U7 (live 320 px pass): an unbroken character name under the level
    overflowed its tile into the deaths tile; the sub line must wrap."""
    bodies = [b for s, b in _rules(_strip_media(_css(APP_CSS))) if s == ".stat .sub"]
    assert bodies and any(re.search(r"overflow-wrap\s*:\s*anywhere", b) for b in bodies)

