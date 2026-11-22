"""PLAY-TD-22C-A11Y-CDP (TD-22, F-121): the in-browser accessibility pass.

tests/test_a11y.py reads the markup and the style sheet; this test holds
the accessibility commitments of plan 03 section 9 on the RENDERED page,
in dark and light, on all four tabs, with every fold open. One headless
Chrome and one page (app/test/cdp/a11y.mjs) on a fixture core of
tests/play_states.py (state c, the worst-case Play, then the long-string
fixture), each pinned to a temp Client.txt on a leased test port (never
8960; the live log is never found):

- the accessibility tree: no unnamed focusable node, headings start at one
  and never skip a level, banner / main / contentinfo once each and no
  landmark outside that set but the labelled regions (1.3.1, 4.1.2);
- a real Tab walk (synthetic Tab keys to this page only) on each tab: the
  cycle comes round, reaches every control, stays out of hidden panels, and
  every stop shows a 3 px ring whose box no ancestor clips (2.1.1, 2.4.7,
  2.4.11);
- every target at least 24 x 24 px, inline links in a sentence excepted
  (2.5.8);
- every text pair at least 4.5:1 (3:1 for large text) (1.4.3);
- at most 4 live regions on Play (the bar and the Play panel) and 6 in the
  page, all polite (4.1.3);
- forced colours: the selected tab has its own bottom border, not weight
  alone (plan 03 section 9);
- 320 px: no horizontal scroll on any tab (1.4.10);
- the four text-spacing overrides on the long-string fixture at 1024x700
  and 1280x760: the probe switches the page, nothing under the Play panel
  clips on either axis and only the page scrolls (1.4.12).

The same pass on a page with three planted defects (a clipped ring, an
unnamed button, a 3:1 text pair) must report each one. Skips cleanly
without Chrome (or Edge) or node. Nothing reaches the game, no clipboard
or screen is read, nothing is captured.

    python tests/test_a11y_render.py --figures   # the measured figures
"""

import contextlib
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import play_states as ps  # noqa: E402
from browser_util import find_browser  # noqa: E402
from ci_timing import ci_scale  # noqa: E402

pytestmark = pytest.mark.server

SCRIPT = ROOT / "app" / "test" / "cdp" / "a11y.mjs"
STATE = "c"         # the worst-case Play: build alert, two trades, item card
LONG = "long"       # the long-string fixture (text spacing)
TABS = ("play", "build", "run", "settings")
THEMES = ("dark", "light")
AUDIT_SIZE = (1280, 760)
REFLOW_SIZE = (320, 640)
SPACING_SIZES = ((1024, 700), (1280, 760))

RING_MIN = 3                    # 2.4.7 / 2.4.11: a 3 px accent ring
TARGET_MIN = 24                 # 2.5.8
CONTRAST, CONTRAST_LARGE = 4.5, 3.0
PLAY_LIVE_MAX, PAGE_LIVE_MAX = 4, 6
LANDMARKS_ONCE = ("banner", "main", "contentinfo")
# a labelled section is a region and a labelled form a form landmark; any
# other landmark role is not part of the set
LANDMARKS_ALLOWED = set(LANDMARKS_ONCE) | {"region", "form"}
PLAY_SCOPES = ("header", "panel-play")
# the polite header line (tab news) speaks for the whole page on every tab
# (plan 03 section 9, 3.2.1); Play's own four are the verdict, the trade
# status, the notice and the bar's reading word
PAGE_LINE = "tab-news"
PLANTS = {"ring": "button#plant-ring", "name": "button#plant-unnamed",
          "contrast": "p#plant-pair"}


# -- verdicts -------------------------------------------------------------------

def _alpha(css):
    """The alpha of a computed colour string (1 when it carries none)."""
    s = (css or "").strip().lower()
    if s in ("", "transparent"):
        return 0.0
    if "/" in s:
        part = s.rsplit("/", 1)[1].strip(" )")
    elif s.startswith("rgba(") and s.count(",") == 3:
        part = s.rsplit(",", 1)[1].strip(" )")
    else:
        return 1.0
    try:
        return float(part[:-1]) / 100 if part.endswith("%") else float(part)
    except ValueError:
        return 1.0


def ax_failures(ax):
    """(check, el, detail) for the accessibility tree of one tab."""
    out = []
    for n in ax["unnamed"]:
        if n.get("tabindex") == "-1" and n.get("text"):
            continue  # a jump target out of the Tab order, read by its text
        out.append(("ax-name", n["el"], f"focusable {n['role'] or 'node'} with no name"))
    levels = [h["level"] for h in ax["headings"]]
    if not levels or levels[0] != 1 or levels.count(1) != 1:
        out.append(("ax-heading", "-", f"headings must start at one h1: {levels[:12]}"))
    for i, (prev, cur) in enumerate(zip(levels, levels[1:]), 1):
        if cur > prev + 1:
            out.append(("ax-heading", ax["headings"][i]["name"] or "-",
                        f"level {cur} after level {prev}"))
    marks = ax["landmarks"]
    for role in LANDMARKS_ONCE:
        if marks.get(role, 0) != 1:
            out.append(("ax-landmark", role, f"{marks.get(role, 0)} {role} landmarks (want 1)"))
    for role in sorted(set(marks) - LANDMARKS_ALLOWED):
        out.append(("ax-landmark", role, f"unexpected {role} landmark"))
    return out


def ring_failures(stop):
    """(check, el, detail) for one Tab stop."""
    out = []
    if not stop["visible"]:
        out.append(("ring", stop["el"], "focus on an element with no box"))
    if stop["style"] == "none" or stop["width"] < RING_MIN or _alpha(stop["color"]) == 0:
        out.append(("ring", stop["el"], f"ring {stop['style']} {stop['width']} px "
                    f"{stop['color']} (want {RING_MIN} px solid)"))
    if stop.get("clip"):
        out.append(("ring", stop["el"], f"ring clipped {stop['clip']['px']} px by "
                    f"{stop['clip']['el']}"))
    return out


def walk_failures(tab, page):
    """(check, el, detail) for the Tab walk of one tab."""
    out = []
    walk = page["walk"]
    if not walk["wrapped"]:
        out.append(("walk", "-", f"the Tab cycle did not come round in {len(walk['stops'])} stops"))
    panel = f"panel-{tab}"
    for s in walk["stops"]:
        out += ring_failures(s)
        if s["scope"].startswith("panel-") and s["scope"] != panel:
            out.append(("walk", s["el"], f"focus inside the hidden {s['scope']}"))
    missed = Counter(page["reach"]) - Counter(s["el"] for s in walk["stops"])
    for el, n in sorted(missed.items()):
        out.append(("walk", el, f"{n} control(s) the Tab walk never reached"))
    return out


def target_failures(page):
    out = []
    for c in page["controls"]:
        if c.get("inline"):
            continue
        if c["w"] < TARGET_MIN or c["h"] < TARGET_MIN:
            out.append(("target", c["el"], f"{c['w']:g}x{c['h']:g} px (min {TARGET_MIN})"))
    return out


def contrast_failures(page):
    out = []
    for p in page["pairs"]:
        need = CONTRAST_LARGE if p["large"] else CONTRAST
        if p["ratio"] < need:
            out.append(("contrast", p["el"], f"{p['ratio']}:1 (min {need}:1) "
                        f"{p['fg']} on {p['bg']} {p['text']!r}"))
    return out


def live_failures(page):
    out = []
    live = page["live"]
    shown = [x for x in live if x["rendered"]]
    play = [x for x in shown if x["scope"] in PLAY_SCOPES and x["id"] != PAGE_LINE]
    if len(play) > PLAY_LIVE_MAX:
        out.append(("live", "-", f"{len(play)} live regions on Play (max {PLAY_LIVE_MAX}): "
                    f"{[x['el'] for x in play]}"))
    if len(shown) > PAGE_LIVE_MAX:
        out.append(("live", "-", f"{len(shown)} live regions in the page (max {PAGE_LIVE_MAX}): "
                    f"{[x['el'] for x in shown]}"))
    for x in live:
        if x["role"] in ("alert", "marquee") or x["polite"] not in ("", "polite"):
            out.append(("live", x["el"], f"not polite: role {x['role']!r}, "
                        f"aria-live {x['polite']!r}"))
    return out


def audit_failures(audit):
    """Every failure of one audit run as {check, theme, tab, el, detail}."""
    fails = []
    for tab, page in audit["tabs"].items():
        found = []
        if page["prep"]["selected"] != "true" or not page["prep"]["shown"]:
            found.append(("tab", tab, f"the {tab} tab did not show"))
        found += ax_failures(page["ax"])
        found += walk_failures(tab, page)
        found += target_failures(page)
        found += contrast_failures(page)
        found += live_failures(page)
        fails += [{"check": c, "theme": audit["theme"], "tab": tab, "el": el, "detail": d}
                  for c, el, d in found]
    return fails


def forced_failures(forced):
    tabs = forced["tabs"]
    sel = [t for t in tabs if t["selected"]]
    rest = [t for t in tabs if not t["selected"]]
    out = []
    if not tabs or not all(t["forced"] for t in tabs):
        return [f"{forced['theme']}: forced colours were not active"]
    if len(sel) != 1:
        return [f"{forced['theme']}: {len(sel)} selected tabs"]
    s = sel[0]
    if s["width"] < 2 or s["style"] in ("none", "hidden") or _alpha(s["color"]) == 0:
        out.append(f"{forced['theme']}: the selected tab has no bottom border "
                   f"({s['style']} {s['width']} px {s['color']})")
    for t in rest:
        if t["color"] == s["color"] and t["width"] == s["width"]:
            out.append(f"{forced['theme']}: {t['id']} has the selected tab's border "
                       f"({s['color']}): only the weight tells them apart")
    return out


def reflow_failures(reflow):
    out = []
    for tab, d in reflow["tabs"].items():
        if not d["prep"]["shown"]:
            out.append(f"{reflow['theme']} {tab}: the tab did not show")
        if d["sw"] > d["cw"]:
            out.append(f"{reflow['theme']} {tab}: horizontal scroll {d['sw'] - d['cw']} px "
                       f"at {reflow['size'][0]} px")
    return out


def spacing_failures(spacing):
    out = []
    for key, m in spacing["sizes"].items():
        if m["attr"] != "user":
            out.append(f"{key}: the text-spacing probe did not switch the page "
                       f"(data-text-spacing {m['attr']!r})")
        if not m["checked"]:
            out.append(f"{key}: nothing measured under the Play panel")
        for b in m["block"]:
            out.append(f"{key}: {b['el']} clips on the block axis ({b['sh']} > {b['ch']})")
        for i in m["inline"]:
            out.append(f"{key}: {i['el']} clips on the inline axis ({i['sw']} > {i['cw']})")
        for s in m["scrollers"]:
            out.append(f"{key}: {s['el']} scrolls inside the page")
        if m["doc"]["sw"] > m["doc"]["cw"]:
            out.append(f"{key}: horizontal page scroll {m['doc']['sw'] - m['doc']['cw']} px")
    return out


# -- the sweep -------------------------------------------------------------------

class Driver:
    """The a11y.mjs process: one JSON command in, one JSON line out."""

    def __init__(self, node, browser, profile):
        self.proc = subprocess.Popen(
            [node, str(SCRIPT), browser, str(profile)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.lines = queue.Queue()
        self.err = []
        threading.Thread(target=self._pump, args=(self.proc.stdout, self.lines.put),
                         daemon=True).start()
        threading.Thread(target=self._pump, args=(self.proc.stderr, self.err.append),
                         daemon=True).start()
        self._read(ci_scale(60))

    @staticmethod
    def _pump(stream, put):
        for line in stream:
            put(line)

    def _read(self, timeout):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(f"a11y.mjs gave no answer in {timeout} s; "
                               f"stderr: {''.join(self.err)[-1500:]}") from None
        doc = json.loads(line)
        if "error" in doc:
            raise RuntimeError(f"a11y.mjs: {doc['error']}")
        return doc

    def call(self, cmd, timeout=60):
        self.proc.stdin.write(json.dumps(cmd) + "\n")
        self.proc.stdin.flush()
        return self._read(ci_scale(timeout))  # decision 0080: 3x under AL_CI=1

    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=15)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait(timeout=15)


def run_sweep(root, browser, node):
    """The audit of state c in both themes (tree, walk, targets, pairs, live
    regions, forced colours, 320 px), the planted page, then the text
    spacing run on the long-string fixture. Returns the sweep document."""
    root = Path(root)
    t0 = time.monotonic()
    drv = Driver(node, browser, root / "chrome")
    sweep = {"live": {}, "audits": {}, "forced": {}, "reflow": {}, "plant": None,
             "spacing": None, "seconds": 0.0}
    try:
        with ps.open_state(STATE, root / STATE) as st:
            sweep["live"][STATE] = drv.call({"cmd": "load", "url": st.url})["live"]
            for theme in THEMES:
                sweep["audits"][theme] = drv.call({"cmd": "audit", "theme": theme,
                                                   "tabs": list(TABS), "size": list(AUDIT_SIZE)})
                sweep["forced"][theme] = drv.call({"cmd": "forced", "theme": theme,
                                                   "size": list(AUDIT_SIZE)})
                sweep["reflow"][theme] = drv.call({"cmd": "reflow", "theme": theme,
                                                   "tabs": list(TABS), "size": list(REFLOW_SIZE)})
            drv.call({"cmd": "plant"})
            sweep["plant"] = drv.call({"cmd": "audit", "theme": "dark", "tabs": ["play"],
                                       "size": list(AUDIT_SIZE)})
        with ps.open_state(LONG, root / LONG) as st:
            sweep["live"][LONG] = drv.call({"cmd": "load", "url": st.url})["live"]
            sweep["spacing"] = drv.call({"cmd": "spacing",
                                         "sizes": [list(s) for s in SPACING_SIZES]})
    finally:
        drv.close()
    sweep["seconds"] = round(time.monotonic() - t0, 1)
    return sweep


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    browser = find_browser()
    node = shutil.which("node")
    if not browser or not node:
        pytest.skip("headless Chrome / Edge or node not found")
    return run_sweep(tmp_path_factory.mktemp("a11y_render"), browser, node)


def _report(fails, limit=40):
    lines = [f"[{f['theme']} {f['tab']}] {f['check']} {f['el']}: {f['detail']}"
             if isinstance(f, dict) else str(f) for f in fails[:limit]]
    if len(fails) > limit:
        lines.append(f"... {len(fails) - limit} more")
    return "\n".join(lines)


def figures(sw):
    lines = [f"seconds: {sw['seconds']}"]
    for theme, a in sw["audits"].items():
        for tab, p in a["tabs"].items():
            lines.append(f"{theme} {tab}: ax {p['ax']['count']} nodes, headings "
                         f"{[h['level'] for h in p['ax']['headings']]}, landmarks "
                         f"{p['ax']['landmarks']}, stops {len(p['walk']['stops'])} "
                         f"(wrapped {p['walk']['wrapped']}), controls {len(p['controls'])}, "
                         f"text pairs {p['measured']}, live {len(p['live'])}")
    return lines


# -- tests without a browser ---------------------------------------------------------

def _stop(**kw):
    s = {"id": 1, "el": "button#x", "scope": "panel-play", "style": "solid", "width": 3,
         "offset": -3, "color": "rgb(255, 170, 0)", "w": 40, "h": 32,
         "ring": {"left": 0, "top": 0, "right": 40, "bottom": 32}, "clip": None,
         "visible": True, "focusVisible": True}
    s.update(kw)
    return s


def _live(el, scope, polite="polite", role="", rendered=True):
    return {"el": el, "id": el.split("#", 1)[1].split(".")[0] if "#" in el else "",
            "scope": scope, "rendered": rendered, "polite": polite, "role": role}


def _page(**kw):
    p = {"prep": {"selected": "true", "shown": True},
         "ax": {"count": 9, "unnamed": [], "landmarks": {"banner": 1, "main": 1,
                                                         "contentinfo": 1, "region": 7},
                "headings": [{"level": 1, "name": "A"}, {"level": 2, "name": "B"},
                             {"level": 3, "name": "C"}, {"level": 2, "name": "D"}]},
         "walk": {"stops": [_stop()], "wrapped": True}, "reach": ["button#x"],
         "controls": [{"el": "button#x", "scope": "panel-play", "w": 40, "h": 32,
                       "inline": False, "role": ""}],
         "pairs": [], "measured": 10,
         "live": [_live("button#reading", "header")]}
    p.update(kw)
    return p


def _audit(page, tab="play"):
    return {"theme": "dark", "size": list(AUDIT_SIZE), "tabs": {tab: page}}


def test_a_clean_page_has_no_failure():
    assert audit_failures(_audit(_page())) == []


def test_alpha_reads_every_colour_form():
    assert _alpha("rgb(1, 2, 3)") == 1.0
    assert _alpha("rgba(1, 2, 3, 0)") == 0.0
    assert _alpha("rgb(1 2 3 / 0.5)") == 0.5
    assert _alpha("rgb(1 2 3 / 0%)") == 0.0
    assert _alpha("transparent") == 0.0
    assert _alpha("oklch(0.7 0.1 60)") == 1.0


def test_tree_verdicts():
    ax = _page()["ax"]
    assert ax_failures(ax) == []
    bad = dict(ax, unnamed=[{"role": "button", "el": "button#u", "tabindex": None, "text": 0}])
    assert [f[:2] for f in ax_failures(bad)] == [("ax-name", "button#u")]
    target = dict(ax, unnamed=[{"role": "paragraph", "el": "p#t", "tabindex": "-1", "text": 9}])
    assert ax_failures(target) == []
    empty = dict(ax, unnamed=[{"role": "generic", "el": "div#e", "tabindex": "-1", "text": 0}])
    assert [f[:2] for f in ax_failures(empty)] == [("ax-name", "div#e")]
    skip = dict(ax, headings=[{"level": 1, "name": "A"}, {"level": 3, "name": "C"}])
    assert [f[:2] for f in ax_failures(skip)] == [("ax-heading", "C")]
    two = dict(ax, headings=[{"level": 1, "name": "A"}, {"level": 1, "name": "B"}])
    assert [f[0] for f in ax_failures(two)] == ["ax-heading"]
    marks = dict(ax, landmarks={"banner": 1, "main": 2, "contentinfo": 1, "navigation": 1,
                                "form": 1})
    assert sorted(f[1] for f in ax_failures(marks)) == ["main", "navigation"]


def test_ring_verdicts():
    assert ring_failures(_stop()) == []
    assert ring_failures(_stop(style="none", width=0))
    assert ring_failures(_stop(width=2))
    assert ring_failures(_stop(color="rgba(0, 0, 0, 0)"))
    clipped = ring_failures(_stop(clip={"el": "div#box", "px": 5}))
    assert [f[0] for f in clipped] == ["ring"] and "div#box" in clipped[0][2]


def test_walk_verdicts():
    page = _page(walk={"stops": [_stop(), _stop(id=2, el="a#y", scope="panel-run")],
                       "wrapped": False}, reach=["button#x", "a#z"])
    got = {(c, el) for c, el, _d in walk_failures("play", page)}
    assert got == {("walk", "-"), ("walk", "a#y"), ("walk", "a#z")}


def test_target_contrast_and_live_verdicts():
    small = _page(controls=[{"el": "button#s", "w": 20, "h": 32, "inline": False},
                            {"el": "a#in", "w": 30, "h": 18, "inline": True}])
    assert [f[1] for f in target_failures(small)] == ["button#s"]
    pairs = [{"el": "p#a", "ratio": 3.0, "large": False, "fg": [0, 0, 0], "bg": [0, 0, 0],
              "text": "x"},
             {"el": "h2#b", "ratio": 3.2, "large": True, "fg": [0, 0, 0], "bg": [0, 0, 0],
              "text": "y"}]
    assert [f[1] for f in contrast_failures(_page(pairs=pairs))] == ["p#a"]
    live = [_live(f"p#l{i}", "panel-play") for i in range(5)]
    assert [f[0] for f in live_failures(_page(live=live))] == ["live"]
    # the header line is the page's, and a region in a hidden panel is silent
    four = [_live("p#tab-news", "header")] + live[:4] + [_live("p#r", "panel-run", rendered=False)]
    assert live_failures(_page(live=four)) == []
    seven = [_live(f"p#l{i}", "panel-run") for i in range(7)]
    assert len(live_failures(_page(live=seven))) == 1
    loud = [_live("p#a", "footer", polite="assertive")]
    assert [f[1] for f in live_failures(_page(live=loud))] == ["p#a"]


def test_forced_reflow_and_spacing_verdicts():
    tab = {"forced": True, "style": "solid", "width": 3, "weight": 400}
    good = {"theme": "dark", "tabs": [dict(tab, id="tab-play", selected=True, color="rgb(0, 0, 255)"),
                                      dict(tab, id="tab-run", selected=False, color="rgb(0, 0, 0)")]}
    assert forced_failures(good) == []
    same = {"theme": "dark", "tabs": [dict(t, color="rgb(0, 0, 0)") for t in good["tabs"]]}
    assert len(forced_failures(same)) == 1
    off = {"theme": "dark", "tabs": [dict(t, forced=False) for t in good["tabs"]]}
    assert forced_failures(off)
    reflow = {"theme": "dark", "size": [320, 640],
              "tabs": {"play": {"prep": {"shown": True}, "sw": 320, "cw": 320},
                       "run": {"prep": {"shown": True}, "sw": 340, "cw": 320}}}
    assert [f.split(":")[0] for f in reflow_failures(reflow)] == ["dark run"]
    m = {"attr": "user", "checked": 50, "block": [], "inline": [], "scrollers": [],
         "doc": {"sw": 1024, "cw": 1024, "sh": 900, "ch": 700}}
    assert spacing_failures({"sizes": {"1024x700": m}}) == []
    bad = dict(m, attr="", block=[{"el": "p#x", "sh": 30, "ch": 20}],
               scrollers=[{"el": "div#s", "sh": 9, "ch": 1, "sw": 1, "cw": 1}])
    assert len(spacing_failures({"sizes": {"1024x700": bad}})) == 3


# -- the browser sweep -------------------------------------------------------------

def test_every_tab_and_theme_was_audited(sweep):
    assert sweep["live"] == {STATE: True, LONG: True}, sweep["live"]
    assert set(sweep["audits"]) == set(THEMES)
    for theme, a in sweep["audits"].items():
        assert tuple(a["tabs"]) == TABS, theme
        for tab, p in a["tabs"].items():
            assert p["theme"] == theme, (theme, tab)
            assert (p["vw"], p["vh"]) == AUDIT_SIZE, (theme, tab)
            assert p["walk"]["stops"] and p["controls"] and p["measured"], (theme, tab)


def test_the_rendered_page_holds_every_commitment(sweep):
    fails = []
    for theme in THEMES:
        fails += audit_failures(sweep["audits"][theme])
    assert not fails, _report(fails)


def test_forced_colours_keep_the_selected_tab_cue(sweep):
    fails = [f for theme in THEMES for f in forced_failures(sweep["forced"][theme])]
    assert not fails, "\n".join(fails)


def test_320px_has_no_horizontal_scroll_on_any_tab(sweep):
    fails = [f for theme in THEMES for f in reflow_failures(sweep["reflow"][theme])]
    assert not fails, "\n".join(fails)


def test_text_spacing_overrides_clip_nothing_on_play(sweep):
    sp = sweep["spacing"]
    assert set(sp["sizes"]) == {f"{w}x{h}" for w, h in SPACING_SIZES}
    fails = spacing_failures(sp)
    assert not fails, "\n".join(fails[:40])


def test_each_planted_defect_is_caught(sweep):
    fails = audit_failures(sweep["plant"])
    by = {(f["check"], f["el"]) for f in fails}
    assert ("ring", PLANTS["ring"]) in by, _report(fails)
    assert ("ax-name", PLANTS["name"]) in by, _report(fails)
    assert ("contrast", PLANTS["contrast"]) in by, _report(fails)
    pair = [p for p in sweep["plant"]["tabs"]["play"]["pairs"] if p["el"] == PLANTS["contrast"]]
    assert pair and abs(pair[0]["ratio"] - 3.0) < 0.05, pair
    # the planted page differs from the clean one only by the plants
    clean = {(f["check"], f["el"]) for f in audit_failures(
        {"theme": "dark", "tabs": {"play": sweep["audits"]["dark"]["tabs"]["play"]}})}
    extra = by - clean - {(c, el) for c, el in by if el.startswith(("button#plant", "p#plant"))}
    assert not extra, sorted(extra)


if __name__ == "__main__":
    if "--figures" not in sys.argv[1:]:
        sys.exit("usage: python tests/test_a11y_render.py --figures [--dump <file>]")
    _browser, _node = find_browser(), shutil.which("node")
    if not _browser or not _node:
        sys.exit("headless Chrome / Edge or node not found")
    with tempfile.TemporaryDirectory(prefix="al-a11y-", ignore_cleanup_errors=True) as tmp:
        _sweep = run_sweep(tmp, _browser, _node)
    print("\n".join(figures(_sweep)))
    _fails = [*audit_failures(_sweep["audits"]["dark"]), *audit_failures(_sweep["audits"]["light"])]
    print(_report(_fails, 200))
    for _k, _fn in (("forced", forced_failures), ("reflow", reflow_failures)):
        for _t in THEMES:
            print("\n".join(_fn(_sweep[_k][_t])))
    print("\n".join(spacing_failures(_sweep["spacing"])))
    if "--dump" in sys.argv:
        with contextlib.suppress(IndexError):
            Path(sys.argv[sys.argv.index("--dump") + 1]).write_text(json.dumps(_sweep),
                                                                    encoding="ascii")
