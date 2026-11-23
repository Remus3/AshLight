"""PLAY-F-189B-OVERLAY-PLATE (F-189): the three overlay plate blocks (.hud,
.trade, .evalcard) are one .plate class with the same rendered pixels.

- overlay.css has one plate rule: the only base rule that paints the plate
  colour, the halo or the plate border is .plate, and the forced-colours
  opt-in is that one class too.
- the HUD and both cards carry the class in index.html.
- same pixels: each plate's resolved declarations (the .plate rule, then its
  own kind rule, shorthands expanded to longhands) equal the declarations
  of the three blocks before the change (PRE_BLOCKS). This is the proof for
  the trade and item cards, which the overlay page never shows in its
  waiting state. The HUD plate was also captured before and after through
  the shared capture helper (app/test/cdp/capture.mjs, F-147) on a demo
  core, 280 x 200, dark and light grounds: the decoded pixels were
  byte-identical (the result line of the package records it).

Reverses if: a later package changes a plate's look on purpose (then
PRE_BLOCKS moves with it, in the same commit), or the overlay needs a plate
that is not this class.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app" / "overlay" / "overlay.css"
HTML = ROOT / "app" / "overlay" / "index.html"

KINDS = ("hud", "trade", "evalcard")

# The three blocks as they stood before F-189 (overlay.css of wave 35),
# kept only to prove the class change moved no pixel. The HUD's place
# (position / top / left / right) is not a plate property and stays in .hud.
PRE_BLOCKS = {
    "hud": """
  margin: 0;
  padding: 6px 10px;
  border: 1px solid var(--fk-border);
  border-radius: 6px;
  background: var(--al-plate);
  color: var(--fk-text);
  font: 600 var(--al-ovl-fs-hud)/1.3 system-ui, "Segoe UI", sans-serif;
  font-variant-numeric: tabular-nums;
  text-shadow: var(--al-halo);
  max-width: 258px;
""",
    "trade": """
  margin: 0;
  padding: 5px 10px;
  border: 1px solid var(--fk-border);
  border-left: 3px solid var(--fk-status-warn);
  border-radius: 6px;
  background: var(--al-plate);
  color: var(--fk-text);
  font: 600 var(--al-ovl-fs-card)/1.3 system-ui, "Segoe UI", sans-serif;
  font-variant-numeric: tabular-nums;
  text-shadow: var(--al-halo);
  max-width: 258px;
""",
    "evalcard": """
  margin: 0;
  padding: 5px 10px;
  border: 1px solid var(--fk-border);
  border-left: 3px solid var(--al-edge);
  border-radius: 6px;
  background: var(--al-plate);
  color: var(--fk-text);
  font: 600 var(--al-ovl-fs-card)/1.3 system-ui, "Segoe UI", sans-serif;
  font-variant-numeric: tabular-nums;
  text-shadow: var(--al-halo);
  max-width: 258px;
""",
}

HUD_PLACE = {"position", "top", "left", "right"}
SIDES = ("top", "right", "bottom", "left")


def _css():
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="ascii"), flags=re.S)


def _media(css, query):
    i = css.find("@media (" + query + ")")
    if i < 0:
        return None
    j = css.index("{", i) + 1
    depth = 1
    k = j
    while depth:
        depth += {"{": 1, "}": -1}.get(css[k], 0)
        k += 1
    return css[j:k - 1]


def _base(css):
    out = css
    for q in ("prefers-contrast: more", "forced-colors: active"):
        block = _media(out, q)
        if block is not None:
            out = out.replace(block, "")
    return out


def _rules(css):
    return [(s.strip(), b) for s, b in re.findall(r"([^{}@]+)\{([^{}]*)\}", css)]


def _decls(body):
    out = []
    for d in body.split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            out.append((k.strip(), " ".join(v.split())))
    return out


def _box(v):
    p = v.split()
    if len(p) < 4:
        p = (p * 4)[:4] if len(p) < 3 else p + [p[1]]
    return dict(zip(SIDES, p))


def _longhands(k, v):
    """The longhands of one declaration (only the forms overlay.css uses)."""
    if k in ("margin", "padding"):
        return {f"{k}-{s}": x for s, x in _box(v).items()}
    if k == "border":
        w, st, c = v.split(" ", 2)
        return {f"border-{s}-{p}": x for s in SIDES
                for p, x in (("width", w), ("style", st), ("color", c))}
    if k.startswith("border-") and k[7:] in SIDES:
        w, st, c = v.split(" ", 2)
        return {f"{k}-width": w, f"{k}-style": st, f"{k}-color": c}
    if k == "font":
        m = re.fullmatch(r"(\d+) (\S+)/(\S+) (.+)", v)
        assert m, v
        # the shorthand resets the font-variant longhands too
        return {"font-weight": m.group(1), "font-size": m.group(2),
                "line-height": m.group(3), "font-family": m.group(4),
                "font-variant-numeric": "normal"}
    return {k: v}


def _resolve(*bodies):
    out = {}
    for body in bodies:
        for k, v in _decls(body):
            out.update(_longhands(k, v))
    return out


def _rule(rules, sel):
    got = [b for s, b in rules if s == sel]
    assert len(got) == 1, (sel, len(got))
    return got[0]


def test_one_plate_rule():
    rules = _rules(_base(_css()))
    _rule(rules, ".plate")
    for prop in (r"background\s*:\s*var\(--al-plate\)", r"text-shadow\s*:",
                 r"(?<![-\w])border\s*:", r"border-radius\s*:", r"max-width\s*:"):
        owners = [s for s, b in rules if re.search(prop, b)]
        assert owners == [".plate"], (prop, owners)
    # the plate rule comes before every kind rule, so a kind rule wins a tie
    order = [s for s, _b in rules]
    for kind in KINDS:
        assert order.index(".plate") < order.index("." + kind), kind


def test_forced_colours_opt_in_is_the_plate_class():
    block = _media(_css(), "forced-colors: active")
    rules = _rules(block)
    adj = [s for s, b in rules if re.search(r"forced-color-adjust\s*:\s*auto", b)]
    assert adj == [".plate"], adj


def test_every_plate_element_carries_the_class():
    html = HTML.read_text(encoding="ascii")
    for kind, elid in zip(KINDS, ("hud", "trade", "evalCard")):
        m = re.search(r'<div id="%s" class="([^"]+)"' % elid, html)
        assert m, elid
        assert m.group(1).split() == ["plate", kind], m.group(1)


@pytest.mark.parametrize("kind", KINDS)
def test_same_declarations_as_before(kind):
    """The plate class plus the kind rule resolve to exactly the old block."""
    rules = _rules(_base(_css()))
    now = _resolve(_rule(rules, ".plate"), _rule(rules, "." + kind))
    for k in HUD_PLACE:
        now.pop(k, None)
    assert now == _resolve(PRE_BLOCKS[kind])
