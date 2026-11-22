"""OVL-CONTRAST-PIXELS (F-144, TD-05): the overlay contrast and width
budgets measured on a rendered page, not only by arithmetic.

app/test/cdp/overlay_pixels.mjs opens this repository's
app/overlay/index.html as a file page in a headless Chrome or Edge (no core,
no port, no token: fixture lines only), at the overlay window size 280 x 176
and device pixel ratios 1.0 and 1.25, with the plate alpha knob at its 0.80
floor. It runs twice: with the page's own overlay.css and with a fixture
copy of the pre-TD-05 CSS (PRE_TD05_CSS below, the overlay.css of the parent
of the OVL-TD05-LEGIBILITY commit, comments and unused rules removed).

- Contrast (design 0001 section 5.2): the brightest 3 percent of the glyph
  box of each secondary-role line (the item card's third line, the trade
  card's where line) against the far plate is >= 5.5:1 with a 5 percent
  tolerance, over a white page and over a 2 px white / black checker.
- Widths (plan 03 budget G10): each worst-case HUD line 2 (made by the
  page's own ALShared.hudLine2) is at most 236 px wide and no row or part
  has a scrollWidth over its clientWidth; the zone name is the one part that
  may clip, and the zone timer never does.
- The pre-TD-05 copy fails the contrast check (the test can fail).

Limit (adjudicator ruling 2026-11-21): the width half is the real rendered
DOM. The contrast half is a canvas proxy: the element's own computed font,
colour, text-shadow halo, plate colour and page opacity, drawn with the real
font rasteriser on an in-page canvas and read back, not the composited DOM.
No page image is taken (the one image path stays app/test/cdp/capture.mjs,
tests/test_floor_static.py unchanged); nothing reads the screen, a window or
the game. Reverses if: MAIN or the operator requires the F-147 helper, or a
real composited capture disagrees with these numbers by more than 5 percent
(then a follow-up extends capture.mjs and replaces the proxy).

Card width: a 34-character capitals-and-digits card line rendered about
292 px at 14 px, over the 236 px budget; CARD-LINE-LIMIT-FLIP dropped the
limit to 26 (app/shared/format.js and state.CARD_LINE), never the font size,
and the worst-case 26-character line (wide capitals and digits) must fit.

Skips, with the reason, when node or Chrome / Edge is missing.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from browser_util import find_browser  # noqa: E402
from ci_timing import ci_scale  # noqa: E402

from server.al.text.common import CARD_LINE  # noqa: E402

DRIVER = ROOT / "app" / "test" / "cdp" / "overlay_pixels.mjs"
NODE = shutil.which("node")
BROWSER = find_browser()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ALPHA = "0.80"          # the plate alpha floor (design 0001 section 5.1)
DPRS = [1, 1.25]
FLOOR = 5.5             # secondary text at the alpha floor over white
TOLERANCE = 0.05
INSIDE = 236            # px inside the plate (plan 03 section 5.1, G10)
SECONDARY_RGB = "rgb(195, 201, 208)"  # --al-ovl-text-2 #c3c9d0

BASE = {"level": "Lv 74", "deaths": "3 deaths", "status": "live", "log": "",
        "trades": "", "under": "", "away": "", "campaign": ""}
# G10 worst-case HUD line 2 inputs and what hudLine2 must make of them
LINE2 = [
    ("lv100_boots", dict(BASE, level="Lv 100", deaths="999 deaths", campaign="Boots: no speed"),
     {"level": "Lv 100", "deaths": "", "status": "Boots: no speed"}),
    ("lv74_under", dict(BASE, under="3 lv under"),
     {"level": "Lv 74", "deaths": "3 deaths", "status": "3 lv under"}),
    ("not_reading", dict(BASE, level="", deaths="", log="not reading - see dashboard"),
     {"level": "", "deaths": "", "status": "not reading - see dashboard"}),
    ("lv100_999", dict(BASE, level="Lv 100", deaths="999 deaths"),
     {"level": "Lv 100", "deaths": "999 deaths", "status": ""}),
]
ZONE = {"text": "The Grelwood Waystone Tower X", "timer": "59m"}  # 29 > 28: clips
CARD_26 = "ABCDEFGHIJKLMNOPQRSTUVW012"  # CARD_LINE characters, M and W included
CARD_IDS = ["evalHead", "evalItem", "evalLine", "tradeItem", "tradeWhere"]
SECONDARY = [{"id": "evalLine", "text": "Better than your boots, +12 life"},
             {"id": "tradeWhere", "text": "Stash tab 2, left 3, top 4"}]

# The pre-TD-05 overlay.css (parent of OVL-TD05-LEGIBILITY): 0.92 plate,
# page opacity 0.9, kit text-muted (#99a1aa) at 13 px for secondary text,
# a 1 px drop shadow. Comments and the rules no measured element uses
# (high contrast, forced colours, the About box) are left out.
PRE_TD05_CSS = """\
:root {
  --fk-text: #e4e8ec;
  --fk-text-muted: #99a1aa;
  --fk-border: #323840;
  --fk-status-warn: #d19a2a;
  --al-plate: rgba(15, 18, 22, 0.92);
  --al-shadow: #000;
  --al-edge: #99a1aa;
}
* { animation: none !important; transition: none !important; }
html { opacity: 0.9; }
html, body { margin: 0; background: transparent; overflow: hidden; user-select: none;
  cursor: default; }
html, body { height: 100%; }
body { display: flex; flex-direction: column; gap: 6px; }
[hidden] { display: none !important; }
.hud { margin: 0; padding: 6px 10px; border: 1px solid var(--fk-border); border-radius: 6px;
  background: var(--al-plate); color: var(--fk-text);
  font: 600 15px/1.3 system-ui, "Segoe UI", sans-serif; font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 1px var(--al-shadow); max-width: 258px; }
.row { margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.zone { font-size: 16px; }
.row.zone { display: flex; align-items: baseline; }
.zone #zone { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.timer { flex: none; color: var(--fk-text); margin-left: 8px; }
.timer:empty { display: none; }
.sep { color: var(--fk-text-muted); }
.status { color: var(--fk-status-warn); margin-left: 6px; font-size: 13px; }
.status:empty, .sep:empty { display: none; }
#deaths:empty + .status { margin-left: 0; }
.trade { margin: 0; padding: 5px 10px; border: 1px solid var(--fk-border);
  border-left: 3px solid var(--fk-status-warn); border-radius: 6px;
  background: var(--al-plate); color: var(--fk-text);
  font: 600 14px/1.3 system-ui, "Segoe UI", sans-serif; font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 1px var(--al-shadow); max-width: 258px; }
.trade .where, .trade .more { color: var(--fk-text-muted); font-size: 13px; }
.trade .from-row { display: flex; gap: 4px; align-items: baseline; }
.trade .from-row #tradeFrom { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.trade .from-row .more { flex: none; }
.evalcard { margin: 0; padding: 5px 10px; border: 1px solid var(--fk-border);
  border-left: 3px solid var(--al-edge); border-radius: 6px;
  background: var(--al-plate); color: var(--fk-text);
  font: 600 14px/1.3 system-ui, "Segoe UI", sans-serif; font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 1px var(--al-shadow); max-width: 258px; }
.evalcard .line { color: var(--fk-text-muted); font-size: 13px; }
"""

needs_node = pytest.mark.skipif(not NODE, reason="node not found")
needs_browser = pytest.mark.skipif(
    not (NODE and BROWSER),
    reason="node not found" if not NODE else "no Chrome or Edge found (AL_CHROME overrides)")


def run_driver(args, timeout=150):
    r = subprocess.run([NODE, str(DRIVER), *args], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=ci_scale(timeout), creationflags=NO_WINDOW)
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    return r, (json.loads(lines[-1]) if lines else {})


def spec_doc(css_file):
    return {"dprs": DPRS, "alpha": ALPHA,
            "variants": [{"name": "current"}, {"name": "pre_td05", "css_file": str(css_file)}],
            "line2": [{"name": n, "inp": inp} for n, inp, _ in LINE2],
            "zone": ZONE,
            "cards": [{"id": i, "text": CARD_26} for i in CARD_IDS],
            "secondary": SECONDARY}


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    if not NODE:
        pytest.skip("node not found")
    if not BROWSER:
        pytest.skip("no Chrome or Edge found (AL_CHROME overrides)")
    d = tmp_path_factory.mktemp("overlay_pixels")
    css = d / "pre_td05.css"
    css.write_text(PRE_TD05_CSS, encoding="ascii", newline="\n")
    spec = d / "spec.json"
    spec.write_text(json.dumps(spec_doc(css)), encoding="ascii", newline="\n")
    r, doc = run_driver([BROWSER, str(d / "profile"), str(spec)])
    assert r.returncode == 0 and doc.get("ok") is True, (r.returncode, r.stdout, r.stderr)
    runs = {(x["variant"], x["dpr"]): x for x in doc["runs"]}
    assert set(runs) == {(v, p) for v in ("current", "pre_td05") for p in DPRS}, sorted(runs)
    return runs


def min_ratio():
    return FLOOR * (1 - TOLERANCE)


def rows(run, names):
    by = {w["name"]: w for w in run["widths"]}
    return [by[n] for n in names]


# ------------------------------------------------------------- no browser

@needs_node
@pytest.mark.parametrize("case", ["argc", "no_browser", "bad_spec", "bad_alpha"])
def test_a_bad_argument_is_refused_before_any_browser_starts(case, tmp_path):
    profile = tmp_path / "profile"
    spec = tmp_path / "spec.json"
    doc = {"dprs": [1], "alpha": ALPHA, "variants": [{"name": "current"}]}
    if case == "bad_spec":
        spec.write_text("{not json", encoding="ascii")
    else:
        if case == "bad_alpha":
            doc["alpha"] = "0.8; color: red"
        spec.write_text(json.dumps(doc), encoding="ascii")
    browser = str(tmp_path / "no_such_browser.exe") if case == "no_browser" else sys.executable
    args = [browser, str(profile)] if case == "argc" else [browser, str(profile), str(spec)]
    r, out = run_driver(args, timeout=30)
    assert r.returncode == 2 and "refused" in out, (r.returncode, r.stdout, r.stderr)
    assert not profile.exists(), "a refusal started a browser (profile made)"


def test_the_driver_takes_no_page_image():
    """The one image path stays capture.mjs (tests/test_floor_static.py);
    this driver reads its own canvas only and opens only the overlay page."""
    text = DRIVER.read_text(encoding="utf-8")
    assert "Page.navigate" in text and "overlayUrl()" in text and "isOverlayUrl(where)" in text
    # the words are split so this file is no floor-scan hit itself
    for word in ("Screen" + "shot", "Screen" + "cast", "print" + "ToPDF",
                 "desktop" + "Capturer", "capture" + "Page"):
        assert word not in text, word
    assert "getImageData" in text and "Emulation.setDeviceMetricsOverride" in text


# ---------------------------------------------------------------- contrast

@pytest.mark.server
@pytest.mark.slow
@needs_browser
@pytest.mark.parametrize("dpr", DPRS)
def test_secondary_glyph_core_holds_the_floor_at_alpha_080(measured, dpr):
    run = measured[("current", dpr)]
    assert run["plate_a"] == ALPHA
    got = run["contrast"]
    assert {(c["id"], c["backdrop"]) for c in got} == {
        (s["id"], b) for s in SECONDARY for b in ("white", "checker")}
    for c in got:
        assert c["color"] == SECONDARY_RGB, c
        assert c["plate"].replace(" ", "") == "rgba(15,18,22,0.8)", c
        assert c["opacity"] == 1, c
        assert c["core_px"] >= 20, c
        assert c["ratio"] >= min_ratio(), (
            f"{c['id']} over {c['backdrop']} at dpr {dpr}: glyph core "
            f"{c['ratio']:.2f}:1 < {FLOOR} - {int(TOLERANCE * 100)} percent")


@pytest.mark.server
@pytest.mark.slow
@needs_browser
@pytest.mark.parametrize("dpr", DPRS)
def test_the_pre_td05_css_fails_the_same_check(measured, dpr):
    run = measured[("pre_td05", dpr)]
    got = run["contrast"]
    assert got and all(c["color"] != SECONDARY_RGB for c in got), got
    low = [c for c in got if c["ratio"] < min_ratio()]
    assert len(low) == len(got), [(c["id"], c["backdrop"], round(c["ratio"], 2)) for c in got]


# ------------------------------------------------------------------ widths

@pytest.mark.server
@pytest.mark.slow
@needs_browser
@pytest.mark.parametrize("dpr", DPRS)
def test_worst_case_hud_line2_fits_inside_the_plate(measured, dpr):
    run = measured[("current", dpr)]
    for (name, _inp, want), w in zip(LINE2, rows(run, [n for n, _, _ in LINE2])):
        assert w["line2"] == want, (name, w["line2"])
        assert w["width"] <= INSIDE, f"{name} '{w['text']}' is {w['width']:.1f} px > {INSIDE}"
        assert w["scroll"] <= w["client"], (name, w)
        for p in w["parts"]:
            assert p["scroll"] <= p["client"], (name, p)


@pytest.mark.server
@pytest.mark.slow
@needs_browser
@pytest.mark.parametrize("dpr", DPRS)
def test_only_the_zone_name_clips(measured, dpr):
    (z,) = rows(measured[("current", dpr)], ["zone"])
    parts = {p["id"]: p for p in z["parts"]}
    assert parts["timer"]["scroll"] <= parts["timer"]["client"], z
    assert parts["timer"]["text"] == ZONE["timer"]
    assert z["scroll"] <= z["client"], z
    # the zone name is the one exempt part: the 29-character fixture clips
    assert parts["zone"]["scroll"] > parts["zone"]["client"], z


@pytest.mark.server
@pytest.mark.slow
@needs_browser
def test_a_26_character_capitals_card_line_fits(measured):
    # CARD-LINE-LIMIT-FLIP: the worst-case line at the card limit fits
    assert len(CARD_26) == CARD_LINE == 26
    for dpr in DPRS:
        for w in rows(measured[("current", dpr)], CARD_IDS):
            assert w["text"] == CARD_26
            assert w["width"] <= INSIDE, f"{w['name']} {w['width']:.1f} px > {INSIDE}"
            assert w["scroll"] <= w["client"], w
