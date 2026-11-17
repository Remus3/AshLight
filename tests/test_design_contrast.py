"""Design system 0001 section 5.2: every documented colour pair meets its
WCAG 2.2 minimum, and the measured ratio written in the doc matches the
ratio recomputed from the token files (kit tokens.json, overlay.css)."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "design" / "0001-design-system.md"
TOKENS = ROOT / "ops" / "fleet_kit" / "tokens.json"
OVERLAY_CSS = ROOT / "app" / "overlay" / "overlay.css"
WORST_SCENE = (255, 255, 255)  # brightest game scene: worst case for light text


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


def resolve(ref):
    scope, name = ref.split(".", 1)
    if scope in ("light", "dark"):
        t = json.loads(TOKENS.read_text(encoding="ascii"))
        if name.startswith("status-"):
            return _hex(t["status"][scope][name[len("status-"):]])
        return _hex(t["themes"][scope][name])
    assert scope == "overlay", ref
    v = _overlay_vars()
    if name == "plate-worst":
        m = re.fullmatch(r"rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)", v["al-plate"])
        assert m, v["al-plate"]
        rgb = tuple(int(m.group(i)) for i in (1, 2, 3))
        return over(rgb, float(m.group(4)), WORST_SCENE)
    return _hex(v["fk-" + name])


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
    t = json.loads(TOKENS.read_text(encoding="ascii"))
    v = _overlay_vars()
    for name in ("surface", "text", "text-muted", "border"):
        assert v["fk-" + name].lower() == t["themes"]["dark"][name].lower(), name
    for name in ("bad", "warn"):
        assert v["fk-status-" + name].lower() == t["status"]["dark"][name].lower(), name


def test_overlay_uses_plate_token_not_literals():
    css = OVERLAY_CSS.read_text(encoding="ascii")
    body = re.sub(r":root\s*\{.*?\}", "", css, count=1, flags=re.S)
    assert "rgba(" not in body, "overlay plate colour must come from --al-plate"


def test_wcag_formula_reference_values():
    assert ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)
