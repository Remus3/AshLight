"""PLAY-TD-03-TOKENS (F-053, F-160, F-161): AshLight's own type, line-box,
spacing, radius, scale and control-edge tokens are declared once, in the
token block at the top of web/app.css, and the rules that use them hold.

Design 0001: section 3 (type, amendment 2026-11-18), section 4 (spacing
and shape), section 5.1 / 5.2 (the --al-control-edge and --al-text-body
rows of the al-token-contrast block), and the NLM definition (ruling
Q-15). Reference setup for the distance rule: ruling Q-14."""

import json
import math
import re
from pathlib import Path

import pytest


def _hex(h):
    h = h.strip().lstrip("#")
    assert re.fullmatch(r"[0-9a-fA-F]{6}", h), h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
APP_CSS = WEB / "app.css"
INDEX = WEB / "index.html"
DOC = ROOT / "docs" / "design" / "0001-design-system.md"
TOKENS = ROOT / "ops" / "fleet_kit" / "tokens.json"

FS = {"micro": 0.8125, "meta": 0.875, "body": 1.0, "title": 1.25,
      "glance": 1.75, "hero": 2.0}
LINE_PX = {"micro": 18, "meta": 20, "body": 22, "title": 26,
           "glance": 32, "hero": 36}
SPACE_PX = [2, 4, 8, 12, 16]
STEPS = (1, 1.25, 1.5, 2)
COMPACT_EM = (64, 43.75)
FULL_EM = (75, 47.5)
EDGE = {"light": "#7a828c", "dark": "#737c88"}
BODY = {"light": "#30353c", "dark": "#c5ccd3"}

# Q-14 reference setup: 24 inch 16:9 1080p panel, dashboard at 80 cm;
# cap height of system-ui / Segoe UI is 0.7 em.
DIAG_IN = 24
RES_W = 1920
DIST_MM = 800
CAP_EM = 0.7
ARCMIN_FLOOR = 16


def _src():
    return APP_CSS.read_text(encoding="ascii")


def _nocomment(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _block(css, head):
    """Body of the first `head {` block (brace-balanced), or None."""
    i = css.find(head)
    if i < 0:
        return None
    k = css.index("{", i)
    depth = 0
    for n in range(k, len(css)):
        if css[n] == "{":
            depth += 1
        elif css[n] == "}":
            depth -= 1
            if depth == 0:
                return css[k + 1:n]
    raise AssertionError("unbalanced " + head)


def _token_block():
    css = _src()
    start = css.index("--- AshLight token block")
    end = css.index("--- end of the token block")
    return css[start:end]


def _outside_token_block():
    css = _src()
    return _nocomment(css[:css.index("--- AshLight token block")] +
                      css[css.index("--- end of the token block"):])


def _vars(body):
    return {n: v.strip() for n, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", body)}


def _light():
    return _vars(_block(_nocomment(_token_block()), ":root {"))


def _dark_selectors():
    tb = _nocomment(_token_block())
    media = _block(tb, "@media (prefers-color-scheme: dark)")
    assert media is not None, "no dark media block in the token block"
    a = _block(media, ':root:not([data-theme="light"])')
    b = _block(tb, ':root[data-theme="dark"]')
    assert a is not None and b is not None, "kit dark selectors missing"
    return _vars(a), _vars(b)


def _rules(css):
    return [(s.strip(), b) for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", _nocomment(css))]


# --- the token block ---------------------------------------------------------

def test_token_block_is_the_first_rule():
    first = re.search(r"[^{}]+\{", _nocomment(_src())).group(0)
    assert first.strip() == ":root {", first


def test_six_type_tokens_in_rem_without_vw_or_clamp():
    v = _light()
    got = {k[len("al-fs-"):]: val for k, val in v.items() if k.startswith("al-fs-")}
    assert set(got) == set(FS), got
    for name, rem in FS.items():
        m = re.fullmatch(r"([\d.]+)rem", got[name])
        assert m, f"--al-fs-{name}: {got[name]}"
        assert float(m.group(1)) == rem, name
    for val in v.values():
        assert "vw" not in val and "clamp(" not in val, val


def test_each_type_token_has_a_fixed_rem_line_box():
    v = _light()
    for name, px in LINE_PX.items():
        val = v.get("al-lh-" + name, "")
        m = re.fullmatch(r"([\d.]+)rem", val)
        assert m, f"--al-lh-{name}: {val!r} is not a fixed rem line box"
        assert float(m.group(1)) * 16 == px, name
        assert px >= FS[name] * 16, name


def test_spacing_radius_tracking_and_mono_tokens():
    v = _light()
    for i, px in enumerate(SPACE_PX):
        assert v["al-space-%d" % i] == ("%grem" % (px / 16)), i
    assert "al-space-5" not in v
    assert v["al-radius-card"] == "0.5rem"
    assert v["al-radius-control"] == "0.375rem"
    assert v["al-radius-pill"] == "999px"
    assert v["al-track-caps"] == "0.04em"
    assert v["al-font-mono"] == "Consolas, monospace"
    assert v["al-lh-prose"] == "1.5"


def test_tokens_are_declared_once():
    names = re.findall(r"(?<![\w-])(--al-[\w-]+)\s*:", _outside_token_block())
    # the one allowed redefinition outside the block: high contrast
    assert set(names) <= {"--al-control-edge"}, names
    for sheet in sorted(WEB.glob("*.css")):
        if sheet == APP_CSS:
            continue
        css = _nocomment(sheet.read_text(encoding="ascii"))
        assert not re.search(r"--al-(fs|lh|space|radius)-[\w-]*\s*:", css), sheet.name


# --- colour tokens -----------------------------------------------------------

def test_colour_tokens_under_the_kit_light_and_dark_selectors():
    light = _light()
    assert light["al-control-edge"].lower() == EDGE["light"]
    assert light["al-text-body"].lower() == BODY["light"]
    for dark in _dark_selectors():
        assert dark["al-control-edge"].lower() == EDGE["dark"]
        assert dark["al-text-body"].lower() == BODY["dark"]


def _token_pairs():
    text = DOC.read_text(encoding="ascii")
    m = re.search(r"```al-token-contrast\n(.*?)```", text, re.S)
    assert m, "no al-token-contrast block in design 0001 5.2"
    rows = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            fg, bg, minimum, measured = line.split()
            rows.append((fg, bg, float(minimum), float(measured)))
    return rows


def _resolve(ref):
    theme, name = ref.split(".", 1)
    assert theme in ("light", "dark"), ref
    if name.startswith("al-"):
        v = _light() if theme == "light" else _dark_selectors()[0]
        return _hex(v[name])
    t = json.loads(TOKENS.read_text(encoding="ascii"))
    return _hex(t["themes"][theme][name])


def test_token_contrast_block_has_the_eight_rows():
    rows = {(fg, bg): mn for fg, bg, mn, _m in _token_pairs()}
    for theme in ("light", "dark"):
        for bg in ("surface", "surface-2"):
            assert rows[(theme + ".al-control-edge", theme + "." + bg)] == 3.0
            assert rows[(theme + ".al-text-body", theme + "." + bg)] == 4.5


@pytest.mark.parametrize("fg,bg,minimum,measured", _token_pairs(),
                         ids=lambda v: v if isinstance(v, str) else None)
def test_token_pair_meets_minimum_and_doc_is_current(fg, bg, minimum, measured):
    got = ratio(_resolve(fg), _resolve(bg))
    assert got >= minimum, f"{fg} on {bg}: {got:.2f} < {minimum}"
    assert round(got, 2) == pytest.approx(measured, abs=0.006), (
        f"{fg} on {bg}: doc says {measured}, measured {got:.2f}")


def test_palette_table_names_the_new_tokens():
    text = DOC.read_text(encoding="ascii")
    sec = text[text.index("### 5.1 Palette"):text.index("### 5.2")]
    edge = re.search(r"\| `--al-control-edge` \|([^|]*)\|", sec)
    body = re.search(r"\| `--al-text-body` \|([^|]*)\|", sec)
    assert edge and EDGE["light"] in edge.group(1) and EDGE["dark"] in edge.group(1)
    assert body and BODY["light"] in body.group(1) and BODY["dark"] in body.group(1)
    assert "`var(--fk-text-muted)`" not in sec


def test_no_rule_uses_muted_text_as_a_border():
    for sheet in sorted(WEB.glob("*.css")):
        css = sheet.read_text(encoding="ascii")
        if sheet == APP_CSS:
            css = _outside_token_block()
        for sel, body in _rules(css):
            assert not re.search(r"(border|outline)[\w-]*\s*:[^;]*--fk-text-muted", body), (
                sheet.name, sel)


def test_control_edges_use_the_token():
    rules = _rules(_strip_media(_outside_token_block()))
    edged = [s for s, b in rules if "var(--al-control-edge)" in b]
    for sel in (".char-pick select", "button.secondary", ".layout-form select",
                "textarea", ".check input"):
        assert any(sel in s for s in edged), sel


def test_high_contrast_lifts_control_edges_to_text():
    block = _block(_src(), "@media (prefers-contrast: more)")
    assert re.search(r"--al-control-edge\s*:\s*var\(--fk-text\)", block), block


# --- honest checkbox (F-160) -------------------------------------------------

def _strip_media(css):
    out, i = [], 0
    while True:
        j = css.find("@media", i)
        if j < 0:
            out.append(css[i:])
            return "".join(out)
        out.append(css[i:j])
        body = _block(css[j:], "@media")
        i = j + css[j:].index("{") + len(body) + 2


def test_checkbox_is_an_empty_box_and_filled_when_checked():
    rules = dict(_rules(_strip_media(_outside_token_block())))
    box = rules[".check input"]
    assert re.search(r"appearance\s*:\s*none", box)
    assert re.search(r"background\s*:\s*transparent", box)
    assert re.search(r"border\s*:\s*1px solid var\(--al-control-edge\)", box)
    # 24 px (PLAY-TD-22A-A11Y-CSS, F-164; WCAG 2.2 SC 2.5.8)
    assert re.search(r"(?<![-\w])width\s*:\s*24px", box)
    assert re.search(r"(?<![-\w])height\s*:\s*24px", box)
    assert "outline" not in box and "accent-color" not in box
    checked = rules[".check input:checked"]
    assert "var(--fk-accent)" in checked and "var(--al-check-tick)" in checked
    assert re.search(r"border-color\s*:\s*var\(--fk-accent\)", checked)
    forced = _block(_src(), "@media (forced-colors: active)")
    assert forced and re.search(r"\.check input\s*\{\s*appearance\s*:\s*auto", forced)
    # the data-URI tick must not draw under the native one
    assert re.search(r"\.check input:checked\s*\{\s*background-image\s*:\s*none", forced)


@pytest.mark.parametrize("theme,stroke", [("light", "ffffff"), ("dark", "0f1216")])
def test_check_tick_is_the_surface_colour_on_the_accent(theme, stroke):
    v = _light() if theme == "light" else _dark_selectors()[0]
    tick = v["al-check-tick"]
    assert tick.startswith('url("data:image/svg+xml,'), tick
    assert ("stroke='%23" + stroke + "'") in tick
    t = json.loads(TOKENS.read_text(encoding="ascii"))["themes"][theme]
    assert t["surface"].lstrip("#").lower() == stroke
    assert ratio(_hex(stroke), _hex(t["accent"])) >= 4.5


# --- small type fixes (F-161) ------------------------------------------------

def test_body_declares_tabular_nums_after_the_font_shorthand():
    body = dict(_rules(_strip_media(_outside_token_block())))["body"]
    m = re.search(r"font-variant-numeric\s*:\s*tabular-nums", body)
    assert m, body
    assert body.index("font:") < m.start()


def test_one_mono_stack_without_ui_monospace():
    for sheet in sorted(WEB.glob("*.css")):
        css = sheet.read_text(encoding="ascii")
        assert "ui-monospace" not in css, sheet.name
        for fam in re.findall(r"font-family\s*:\s*([^;]+);", _nocomment(css)):
            if "mono" in fam.lower() or "consolas" in fam.lower():
                assert fam.strip() == "var(--al-font-mono)", (sheet.name, fam)


def test_one_uppercase_tracking_value():
    for sheet in sorted(WEB.glob("*.css")):
        css = sheet.read_text(encoding="ascii")
        if sheet == APP_CSS:
            css = _outside_token_block()
        for sel, body in _rules(css):
            for val in re.findall(r"letter-spacing\s*:\s*([^;]+);", body):
                assert val.strip() == "var(--al-track-caps)", (sheet.name, sel, val)
            if re.search(r"text-transform\s*:\s*uppercase", body):
                assert "letter-spacing: var(--al-track-caps)" in body, (sheet.name, sel)


def test_multiline_prose_reads_at_1_5():
    rules = dict(_rules(_strip_media(_outside_token_block())))
    for sel in (".zone-note", ".zone-guide", ".campaign-hints", ".card.hint p",
                ".notes", ".promises ul"):
        assert "line-height: var(--al-lh-prose)" in rules[sel], sel


def _tab_labels():
    html = INDEX.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'<button id="([\w-]+)" class="tab"[^>]*>([^<]*)<', html):
        out[m.group(1)] = m.group(2).strip()
    return out


def test_selected_tab_is_600_and_keeps_its_width():
    rules = dict(_rules(_strip_media(_outside_token_block())))
    sel = rules['button.tab[aria-selected="true"]']
    assert re.search(r"font-weight\s*:\s*600", sel), sel
    after = rules["button.tab::after"]
    for decl in ("display: block", "height: 0", "overflow: hidden",
                 "visibility: hidden", "font-weight: 600"):
        assert decl in after, decl
    labels = _tab_labels()
    assert len(labels) >= 4, labels
    for tab_id, label in labels.items():
        body = rules.get("#%s::after" % tab_id, "")
        assert ('content: "%s"' % label) in body, (tab_id, label)


# --- whole-sheet type rule (plan 03 section 11, G7 static part) ---------------

def test_every_font_size_in_every_sheet_is_a_type_token():
    """PLAY-TD-22A-A11Y-CSS (F-053, G7): every font-size in web/*.css is one
    var(--al-fs-*) token, and every font shorthand is inherit or starts
    with one; the one exception is the root scale on html (100% x s),
    which sets no text size of its own."""
    for sheet in sorted(WEB.glob("*.css")):
        css = _nocomment(sheet.read_text(encoding="ascii"))
        if sheet == APP_CSS:
            css = _outside_token_block()
        for sel, body in _rules(css):
            for val in re.findall(r"(?<![-\w])font-size\s*:\s*([^;]+);", body):
                val = val.strip()
                if sheet == APP_CSS and sel == "html":
                    assert val == "calc(100% * var(--al-s))", (sheet.name, sel, val)
                    continue
                assert re.fullmatch(r"var\(--al-fs-(%s)\)" % "|".join(FS), val), (
                    sheet.name, sel, val)
            for val in re.findall(r"(?<![-\w])font\s*:\s*([^;]+);", body):
                val = val.strip()
                assert val == "inherit" or re.match(
                    r"var\(--al-fs-(%s)\)(/|\s)" % "|".join(FS), val), (sheet.name, sel, val)


# --- root scale queries (applied later by PLAY-TD-09B-SKELETON) --------------

def _scale_queries():
    tb = _nocomment(_token_block())
    out = []
    for w, h, body in re.findall(
            r"@media \(min-width: ([\d.]+)em\) and \(min-height: ([\d.]+)em\) \{(.*?)\}\s*\}",
            tb):
        v = _vars(body + ";")
        out.append((float(w), float(h), float(v["al-s"]), v["al-size-class"]))
    return out


def test_scale_queries_follow_the_rule_in_em():
    got = _scale_queries()
    want = []
    for s in STEPS:
        want.append((COMPACT_EM[0] * s, COMPACT_EM[1] * s, float(s), "compact"))
        want.append((FULL_EM[0] * s, FULL_EM[1] * s, float(s), "full"))
    assert got == want, got
    base = _light()
    assert base["al-s"] == "1" and base["al-size-class"] == "flow"


def test_scale_is_applied_to_the_root():
    """PLAY-TD-09B-SKELETON applies the step: html takes 100% x s, and the
    token block's :root sets no font of its own."""
    css = _nocomment(_src())
    html = [b for sel, b in _rules(css) if sel == "html" and re.search(r"font-size", b)]
    assert len(html) == 1, html
    assert re.search(r"(?<![-\w])font-size\s*:\s*calc\(100% \* var\(--al-s\)\)\s*;", html[0]), html
    for sel, body in _rules(css):
        if sel == ":root":
            assert not re.search(r"(?<![-\w])font(-size)?\s*:", body), (sel, body)


# --- distance rule (Q-14 reference setup) ------------------------------------

def _arcmin(px):
    pitch_mm = DIAG_IN * 25.4 * 16 / math.hypot(16, 9) / RES_W
    cap_mm = CAP_EM * px * pitch_mm
    return math.degrees(2 * math.atan(cap_mm / 2 / DIST_MM)) * 60


def test_title_step_meets_16_arcmin_at_the_reference_setup():
    title_px = float(_light()["al-fs-title"][:-3]) * 16
    assert _arcmin(title_px) >= ARCMIN_FLOOR, _arcmin(title_px)
    # the steps above the title meet it too; body and meta are lean-in text
    for name in ("glance", "hero"):
        assert _arcmin(FS[name] * 16) >= ARCMIN_FLOOR, name
    assert _arcmin(FS["body"] * 16) < ARCMIN_FLOOR


# --- NLM (ruling Q-15) -------------------------------------------------------

def test_nlm_is_defined_plainly():
    text = DOC.read_text(encoding="ascii")
    head = text[:text.index("## 1.")]
    assert "Interpretation note" not in head
    assert "please correct" not in head
    assert re.search(r"\*\*NLM\*\* means natural-language messaging", head), head
