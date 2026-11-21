"""Design system 0001 section 5.2: every documented colour pair meets its
WCAG 2.2 minimum, and the measured ratio written in the doc matches the
ratio recomputed from the token files (kit tokens.json, overlay.css).

OVL-TD05-LEGIBILITY: overlay text is opaque and the plate alone carries the
alpha (default from overlay.css, floor 0.80 from design 0001 section 5.2),
so the overlay is checked as text over the plate over a bright scene."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "design" / "0001-design-system.md"
TOKENS = ROOT / "ops" / "fleet_kit" / "tokens.json"
OVERLAY_CSS = ROOT / "app" / "overlay" / "overlay.css"
WORST_SCENE = (255, 255, 255)  # brightest game scene: worst case for light text
WARM_SCENE = (0xf2, 0xe6, 0xc8)  # bright warm scene (sand, parchment, fire glow)
PLATE_FLOOR = 0.80  # design 0001 section 5.2 / plan 03 section 5.6: alpha floor
GLANCE = 7.0        # primary text everywhere; secondary and warn at the default
TEXT_FLOOR = 5.5    # secondary and warn text at the alpha floor
EDGE = 3.0          # card edges, WCAG 2.2 SC 1.4.11


def _hex(h):
    h = h.strip().lstrip("#")
    assert re.fullmatch(r"[0-9a-fA-F]{6}", h), h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def over(fg, alpha, bg):
    return tuple(round(alpha * f + (1 - alpha) * g) for f, g in zip(fg, bg))


def _overlay_vars():
    css = OVERLAY_CSS.read_text(encoding="ascii")
    root = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    out = {}
    for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", root):
        out[name] = value.strip()
    return out


_PLATE_RE = re.compile(
    r"rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*"
    r"(?:var\(\s*--al-plate-a\s*,\s*([\d.]+)\s*\)|([\d.]+))\s*\)")


def plate(v=None):
    """(rgb, default alpha) of --al-plate; the alpha may be the fallback of
    var(--al-plate-a, <default>)."""
    v = v or _overlay_vars()
    m = _PLATE_RE.fullmatch(v["al-plate"])
    assert m, v["al-plate"]
    return tuple(int(m.group(i)) for i in (1, 2, 3)), float(m.group(4) or m.group(5))


def overlay_colour(name, v=None):
    """An overlay colour token: `al-*` by its own name, else `--fk-<name>`."""
    v = v or _overlay_vars()
    return _hex(v[name] if name.startswith("al-") else v["fk-" + name])


_PLATES = {"plate-worst": (None, WORST_SCENE), "plate-floor": (PLATE_FLOOR, WORST_SCENE),
           "plate-warm": (None, WARM_SCENE), "plate-warm-floor": (PLATE_FLOOR, WARM_SCENE)}


def resolve(ref):
    scope, name = ref.split(".", 1)
    if scope in ("light", "dark"):
        t = json.loads(TOKENS.read_text(encoding="ascii"))
        if name.startswith("status-"):
            return _hex(t["status"][scope][name[len("status-"):]])
        return _hex(t["themes"][scope][name])
    assert scope == "overlay", ref
    v = _overlay_vars()
    if name in _PLATES:
        alpha, scene = _PLATES[name]
        rgb, default = plate(v)
        return over(rgb, default if alpha is None else alpha, scene)
    return overlay_colour(name, v)


def pairs():
    text = DOC.read_text(encoding="ascii")
    m = re.search(r"```al-contrast\n(.*?)```", text, re.S)
    assert m, "no al-contrast block in the design doc"
    rows = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fg, bg, minimum, measured = line.split()
        rows.append((fg, bg, float(minimum), float(measured)))
    return rows


def test_block_is_not_empty():
    assert len(pairs()) >= 30


@pytest.mark.parametrize("fg,bg,minimum,measured", pairs(),
                         ids=lambda v: v if isinstance(v, str) else None)
def test_pair_meets_minimum_and_doc_is_current(fg, bg, minimum, measured):
    got = ratio(resolve(fg), resolve(bg))
    assert got >= minimum, f"{fg} on {bg}: {got:.2f} < {minimum}"
    assert round(got, 2) == pytest.approx(measured, abs=0.006), (
        f"{fg} on {bg}: doc says {measured}, measured {got:.2f}")


def test_overlay_mirrors_kit_dark_theme():
    """Every --fk-* copy in overlay.css equals the kit dark value."""
    t = json.loads(TOKENS.read_text(encoding="ascii"))
    v = _overlay_vars()
    kit = [n[3:] for n in v if n.startswith("fk-")]
    assert {"surface", "text", "border", "status-warn", "status-ok"} <= set(kit), kit
    for name in kit:
        if name.startswith("status-"):
            want = t["status"]["dark"][name[len("status-"):]]
        else:
            want = t["themes"]["dark"][name]
        assert v["fk-" + name].lower() == want.lower(), name
    # the plate is the kit surface colour; only its alpha differs
    assert plate(v)[0] == _hex(v["fk-surface"])


# --- OVL-TD05-LEGIBILITY: composite contrast over a bright scene ------------

def _base_rules():
    css = re.sub(r"/\*.*?\*/", "", OVERLAY_CSS.read_text(encoding="ascii"), flags=re.S)
    css = css[:css.index("@media")] if "@media" in css else css
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def overlay_text_tokens():
    """Every var(--x) used as a text `color:` in the overlay base rules."""
    out = set()
    for _sel, body in _base_rules():
        out.update(re.findall(r"(?<![-\w])color\s*:\s*var\(--([\w-]+)\)", body))
    return sorted(out)


def overlay_edge_tokens():
    """Every var(--x) that colours a card edge (border-left) in the base rules."""
    out = set()
    for _sel, body in _base_rules():
        out.update(re.findall(r"border-left(?:-color)?\s*:[^;]*var\(--([\w-]+)\)", body))
    return sorted(out)


def _short(token):
    return token[3:] if token.startswith("fk-") else token


def composite(token, alpha, scene):
    """Opaque text over the plate at `alpha` over `scene`, 8-bit rounding."""
    rgb, _default = plate()
    return ratio(overlay_colour(_short(token)), over(rgb, alpha, scene))


def test_overlay_text_tokens_are_the_three_roles():
    assert overlay_text_tokens() == ["al-ovl-text-2", "al-ovl-warn", "fk-text"]
    assert overlay_edge_tokens() == ["al-edge", "fk-status-ok", "fk-status-warn"]


def test_overlay_plate_default_and_floor():
    _rgb, default = plate()
    assert default == pytest.approx(0.86)
    assert PLATE_FLOOR < default <= 1.0


@pytest.mark.parametrize("scene", [WORST_SCENE, WARM_SCENE], ids=["white", "warm"])
@pytest.mark.parametrize("token", overlay_text_tokens())
def test_overlay_text_over_plate(token, scene):
    """Primary >= 7 at the floor and the default; secondary and warn
    >= 5.5 at the floor and >= 7 at the default."""
    _rgb, default = plate()
    at_default = composite(token, default, scene)
    at_floor = composite(token, PLATE_FLOOR, scene)
    assert at_default >= GLANCE, f"{token} at {default}: {at_default:.2f}"
    floor = GLANCE if token == "fk-text" else TEXT_FLOOR
    assert at_floor >= floor, f"{token} at {PLATE_FLOOR}: {at_floor:.2f}"


@pytest.mark.parametrize("scene", [WORST_SCENE, WARM_SCENE], ids=["white", "warm"])
@pytest.mark.parametrize("token", overlay_edge_tokens())
def test_overlay_edges_over_plate(token, scene):
    _rgb, default = plate()
    for alpha in (PLATE_FLOOR, default):
        got = composite(token, alpha, scene)
        assert got >= EDGE, f"{token} at {alpha}: {got:.2f}"


def test_design_overlay_rows_equal_the_css():
    """The 5.2 overlay rows name every overlay text colour at the default
    plate and at the floor over white, and every card edge at the floor;
    their numbers are checked against the CSS by the parametrized test."""
    rows = {(fg, bg) for fg, bg, _m, _r in pairs() if fg.startswith("overlay.")}
    for token in overlay_text_tokens():
        for bg in ("overlay.plate-worst", "overlay.plate-floor"):
            assert ("overlay." + _short(token), bg) in rows, (token, bg)
    for token in overlay_edge_tokens():
        assert ("overlay." + _short(token), "overlay.plate-floor") in rows, token
    named = {fg[len("overlay."):] for fg, _bg in rows}
    assert named == {_short(t) for t in overlay_text_tokens() + overlay_edge_tokens()}, named


def test_overlay_uses_plate_token_not_literals():
    css = OVERLAY_CSS.read_text(encoding="ascii")
    body = re.sub(r":root\s*\{.*?\}", "", css, count=1, flags=re.S)
    assert "rgba(" not in body, "overlay plate colour must come from --al-plate"


def test_wcag_formula_reference_values():
    assert ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)
