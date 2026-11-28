"""PROGRESSION-VIEW (decision 0092): the Progression view keeps the
no-scroll fit at every cockpit size (design 0001 section 4, G4, N7).

Modelled on the KINDLER-FIT-MEASURE part of tests/test_play_fit.py: a
static copy of the assembled page (every stylesheet, the header, every
panel and the footer, no core and no port), the real web/panels/tree.js,
web/panels/progression.js and web/iteminfo.js attached to a fake core
that answers GET /api/progression with an invented worst-case model
(tests/progression_fixtures.py: long names, 8 skills of 6 supports, 3
long next-up steps, every point line). Each size is a srcdoc iframe read
back by the browser's own --dump-dom run.

Three documents per size:
- "play": Play with every region's track fixed (data-fit=yes, as
  web/regions.js sets once the regions start) and region I showing the
  progression by itself (no item check yet);
- "play-eval": the same after an item check and then a level-up, so the
  "Item check" button shows too;
- "build": Build and items with the Progression card open.

In the cockpit a region and the card clip (overflow hidden), so a cut row
would never show as page overflow: the check is the view's own slack (its
box bottom less the bottom of its last shown child) against the region I
minimum of test_play_fit.py (I_SLACK_MIN) or the G4 card minimum
(SLACK_MIN), no clipped content, no target under 24 px and no page
scroll. Flow sizes check horizontal scroll only (flow scrolls the page).
The G5 caps hold too: region I words at most 60, and the mini view at
most MINI_ELEMENTS visible elements (the item card it stands in for
shows more).
"""

import ast
import html as htmllib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import htmlscan  # noqa: E402
import progression_fixtures as pf  # noqa: E402
import srcpaths  # noqa: E402
from browser_util import find_browser  # noqa: E402
from ci_timing import ci_scale  # noqa: E402
from server.al.theorycraft import progression  # noqa: E402

pytestmark = pytest.mark.server

# the sizes and minima of tests/test_play_fit.py (kept equal by
# test_the_figures_match_the_play_fit_harness below)
COCKPIT = ((1280, 760), (1920, 950), (1264, 821), (1024, 700), (1920, 875))
FLOW = ((1366, 650), (320, 640))
SIZES = COCKPIT + FLOW
SLACK_MIN = {1: 2, 1.25: 3}
I_SLACK_MIN = {"full": 16, "compact": 6}
WORD_CAP_I = 60
TARGET_MIN = 24
MINI_ELEMENTS = 24
KINDS = ("play", "play-eval", "build")
OUT = "al-progress-out"


def size_class(w, h):
    """(class, s) by the scale rule of plan 03 3.1 at a 16 px default."""
    steps = [s for s in (1, 1.25, 1.5, 2) if w >= 1024 * s and h >= 700 * s]
    if not steps:
        return "flow", 1
    s = max(steps)
    return ("full" if w >= 1200 * s and h >= 760 * s else "compact"), s


def worst_model():
    t = pf.tree(long_names=True)
    plan = pf.plan(t, long_names=True, skills=8, supports=6)
    m = progression.build_model(tree=t, level=29, area_id="G1_4", zone="Demo Woods",
                                guide=pf.GUIDE, kindler={"plan": plan, "stage": 2,
                                                         "label": "W" * 32})
    prev = dict(m, due=[])
    m = progression.build_model(tree=t, level=29, area_id="G1_4", zone="Demo Woods",
                                guide=pf.GUIDE, kindler={"plan": plan, "stage": 2,
                                                         "label": "W" * 32}, prev=prev)
    # the longest strip the server can compose: three long steps
    m["next"] = [{"kind": k, "text": progression.step_text(t)} for k, t in (
        ("passive", "Take next: " + pf.LONG + ", " + pf.LONG + " (+1 more)"),
        ("gem", "Support at level 31: Demo support 0 with a long name, a b c d e"),
        ("book", "Here: A book of 2 points - beat the demo boss in the woods and more"))]
    m["key"] = progression.digest(m)
    return m


_JS = r"""
(function () {
  var fe = window.frameElement, doc = document;
  var kind = fe.getAttribute("data-kind");
  var send = function (o) {
    o.vw = innerWidth; o.vh = innerHeight; o.kind = kind;
    parent.document.getElementById(__OUT__).textContent += JSON.stringify(o) + "\n";
  };
  try {
    var model = __MODEL__, sum = __SUMMARY__;
    var panel = kind === "build" ? "panel-build" : "panel-play";
    Array.prototype.forEach.call(doc.querySelectorAll("[role=tabpanel]"), function (p) {
      p.hidden = p.id !== panel;
    });
    Array.prototype.forEach.call(doc.querySelectorAll("[data-region]"), function (r) {
      r.setAttribute("data-fit", "yes");
    });
    /* the first paint shows the item card; a level-up (after the 20 s
       hold of a fresh item check) shows the progression by itself */
    var ev = kind === "play-eval" ? { id: 7 } : null;
    var snap = { progression: sum, eval: ev, now: 1000 };
    var P = window.ALProgression;
    var ctx = { api: function () { return Promise.resolve(model); },
                getSnap: function () { return snap; } };
    P.wire(doc, ctx);
    P.paint(doc, snap);
    snap = { progression: Object.assign({}, sum, { level: sum.level + 1 }), eval: ev, now: 1030 };
    P.paint(doc, snap);
    window.addEventListener("load", function () {
      try {
        if (kind === "build") { P.setOpen(doc, true, false); }
        P.paint(doc, Object.assign({}, snap));
        var de = doc.documentElement;
        var shown = function (e) { return e.getClientRects().length > 0 &&
          getComputedStyle(e).visibility !== "hidden"; };
        var inner = function (e) {
          var cs = getComputedStyle(e), r = e.getBoundingClientRect();
          return r.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
        };
        var lastBottom = function (box) {
          var last = box.getBoundingClientRect().top;
          Array.prototype.forEach.call(box.querySelectorAll("*"), function (k) {
            /* an svg clips its own paths: its box is the one that counts */
            if (k.closest("svg") && k.tagName.toLowerCase() !== "svg") { return; }
            if (shown(k)) { last = Math.max(last, k.getBoundingClientRect().bottom); }
          });
          return last;
        };
        var small = [];
        var host = kind === "build" ? doc.getElementById("pgbox") : doc.getElementById("pg-mini");
        if (!host || !shown(host)) { send({ error: "no progression view shown" }); return; }
        Array.prototype.forEach.call(host.querySelectorAll("button"), function (c) {
          if (!shown(c)) { return; }
          var r = c.getBoundingClientRect();
          if (r.width < 24 - 0.01 || r.height < 24 - 0.01) {
            small.push((c.id || c.className) + " " + r.width.toFixed(1) + "x" + r.height.toFixed(1));
          }
        });
        var out = { doc: { sh: de.scrollHeight, ch: de.clientHeight, sw: de.scrollWidth,
                           cw: de.clientWidth }, small: small };
        var trees = host.querySelectorAll("svg");
        out.svg = [];
        Array.prototype.forEach.call(trees, function (s) {
          var r = s.getBoundingClientRect();
          out.svg.push({ id: s.id, w: Math.round(r.width), h: Math.round(r.height),
                         kids: s.querySelectorAll("*").length,
                         drawn: s.querySelectorAll("path[d]").length });
        });
        if (kind === "build") {
          var card = host;
          out.slack = Math.floor(inner(card)) - Math.ceil(lastBottom(card));
          out.clip = card.scrollHeight - card.clientHeight;
          out.cols = Array.prototype.map.call(card.querySelectorAll(".pg-col"), function (c) {
            return c.scrollHeight - c.clientHeight;
          });
          out.card = { w: Math.round(card.getBoundingClientRect().width),
                       h: Math.round(card.getBoundingClientRect().height) };
          out.grid = Array.prototype.some.call(doc.querySelectorAll("#panel-build > .col"),
            function (c) { return shown(c); });
        } else {
          var region = doc.getElementById("play-i");
          out.slack = Math.floor(inner(region)) - Math.ceil(lastBottom(host));
          out.clip = region.scrollHeight - region.clientHeight;
          out.slotShown = shown(region.querySelector(".slot"));
          var count = 0;
          Array.prototype.forEach.call(host.querySelectorAll("*"), function (k) {
            if (shown(k)) { count += 1; }
          });
          out.elements = count + 1;
          out.words = (host.innerText || "").split(/\s+/).filter(Boolean).length;
          out.button = shown(doc.getElementById("pg-mini-item"));
          out.heading = doc.getElementById("play-i-h").textContent;
          out.region = { h: Math.round(region.getBoundingClientRect().height) };
        }
        send(out);
      } catch (e) { send({ error: String(e && e.stack || e) }); }
    });
  } catch (e) { send({ error: String(e && e.stack || e) }); }
}());
"""


def _file_url(path):
    return Path(path).resolve().as_uri()


def page(sizes=SIZES, theme=None, model=None):
    """The outer page: one srcdoc iframe per size and kind, each the
    assembled page without its scripts plus the three view scripts."""
    html = srcpaths.index_html(encoding="utf-8")
    links = []
    for href in re.findall(r'<link rel="stylesheet" href="([^"]+)">', html):
        if href == "/tokens.css":
            links.append(ROOT / "ops" / "fleet_kit" / "tokens.css")
        elif href.startswith("/web/"):
            links.append(srcpaths.path(href[len("/web/"):]))
    body = html[html.index("<body>") + len("<body>"):html.index("</body>")]
    body = htmlscan.cut(body, comments=False, repl="", eat_space=True)
    m = model or worst_model()
    js = (_JS.replace("__OUT__", json.dumps(OUT)).replace("__MODEL__", json.dumps(m))
          .replace("__SUMMARY__", json.dumps(progression.summary(m))))
    head = "".join(f'<link rel="stylesheet" href="{_file_url(p)}">\n' for p in links)
    attr = f' data-theme="{theme}"' if theme else ""
    scripts = "".join(f'<script src="{_file_url(srcpaths.path(n))}"></script>\n'
                      for n in ("iteminfo.js", "panels/tree.js", "panels/progression.js"))
    inner = (f"<!doctype html>\n<html lang=\"en\"{attr}>\n<head>\n<meta charset=\"utf-8\">\n"
             "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
             f"<title>progression</title>\n{head}</head>\n<body>\n{body}\n{scripts}"
             f"<script>{js}</script>\n</body>\n</html>\n")
    frames = "".join(f'<iframe data-kind="{kind}" width="{w}" height="{h}" '
                     f'style="border: 0; display: block" '
                     f'srcdoc="{htmllib.escape(inner, quote=True)}"></iframe>\n'
                     for w, h in sizes for kind in KINDS)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>progression sizes</title>\n</head>\n<body style=\"margin: 0\">\n"
            f"<pre id=\"{OUT}\"></pre>\n{frames}</body>\n</html>\n")


def measure(browser, folder, sizes=SIZES):
    """{"<w>x<h> <kind>": measures} for every frame."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "progress.html"
    p.write_text(page(sizes), encoding="utf-8")
    cmd = [browser, "--headless=new", "--disable-gpu", "--in-process-gpu", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
           "--force-device-scale-factor=1", f"--user-data-dir={folder / 'profile'}",
           "--window-size=2000,2400", "--dump-dom", p.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=ci_scale(120))
    found = re.search(r'<pre id="' + OUT + r'">(.*?)</pre>', r.stdout, re.S)
    assert found and found.group(1).strip(), f"no measures; stderr: {r.stderr[-1500:]}"
    out = {}
    for line in htmllib.unescape(found.group(1)).splitlines():
        if not line:
            continue
        row = json.loads(line)
        h = next(hh for ww, hh in sizes if ww == row["vw"] and hh == row["vh"])
        out[f"{row['vw']}x{h} {row['kind']}"] = row
    return out


def failures(measures):
    """Every view that is missing, cut, short of its slack, holds a target
    under 24 px, breaks a G5 cap or makes the page scroll."""
    fails = []
    for key, m in sorted(measures.items()):
        if "error" in m:
            fails.append(f"{key}: {m['error'][:300]}")
            continue
        w, h = (int(v) for v in key.split()[0].split("x"))
        kind = key.split()[1]
        cls, s = size_class(w, h)
        d = m["doc"]
        if d["sw"] > d["cw"]:
            fails.append(f"{key}: horizontal scroll {d['sw'] - d['cw']} px")
        for c in m["small"]:
            fails.append(f"{key}: target {c} px (min {TARGET_MIN})")
        if kind != "build":
            if m.get("elements", 0) > MINI_ELEMENTS:
                fails.append(f"{key}: {m['elements']} elements (max {MINI_ELEMENTS})")
            if m.get("words", 0) > WORD_CAP_I:
                fails.append(f"{key}: {m['words']} words (max {WORD_CAP_I})")
            if m.get("slotShown"):
                fails.append(f"{key}: the item card still shows under the view")
        if cls == "flow":
            continue
        if d["sh"] > d["ch"]:
            fails.append(f"{key}: page {d['sh'] - d['ch']} px over")
        need = I_SLACK_MIN[cls] * s if kind != "build" else SLACK_MIN.get(s, 3)
        if m["slack"] < need:
            fails.append(f"{key}: slack {m['slack']} px (min {need:g})")
        if m["clip"] > 1:
            fails.append(f"{key}: clips {m['clip']} px")
        for i, c in enumerate(m.get("cols") or ()):
            if c > 1:
                fails.append(f"{key}: column {i + 1} clips {c} px")
        for sv in m.get("svg") or ():
            if sv["h"] < 60:
                fails.append(f"{key}: tree {sv['id']} only {sv['h']} px tall")
        if kind == "build" and m.get("grid"):
            fails.append(f"{key}: the card grid still shows under the view")
    return fails


def figures(measures):
    out = []
    for key, m in sorted(measures.items()):
        if "error" in m:
            out.append(f"- {key}: error")
            continue
        out.append(f"- {key}: slack {m.get('slack')}, clip {m.get('clip')}, svg "
                   + ", ".join(f"{s['id']} {s['w']}x{s['h']} ({s['kids']} el)"
                               for s in m.get("svg") or ())
                   + (f", {m['elements']} elements, {m['words']} words"
                      if "elements" in m else ""))
    return out


def _fake(slack=20, clip=0, sh=700, small=(), elements=10, words=20, slot=False, kind="play"):
    m = {"doc": {"sh": sh, "ch": 700, "sw": 1024, "cw": 1024}, "small": list(small),
         "slack": slack, "clip": clip, "svg": [{"id": "pg-mini-tree", "w": 400, "h": 150,
                                                 "kids": 10, "drawn": 10}]}
    if kind == "build":
        m.update(cols=[0, 0, 0], grid=False)
    else:
        m.update(elements=elements, words=words, slotShown=slot)
    return m


def test_failures_catch_each_cut():
    assert failures({"1024x700 play": _fake()}) == []
    assert failures({"1024x700 build": _fake(kind="build")}) == []
    bad = failures({"1024x700 play": _fake(slack=2, clip=9, sh=720, small=("x 20x20",),
                                           elements=40, words=70, slot=True)})
    assert len(bad) == 7, bad
    assert len(failures({"1024x700 build": dict(_fake(kind="build"), cols=[0, 5, 0],
                                                 grid=True)})) == 2
    # a flow size checks horizontal scroll, targets and the G5 caps only
    assert failures({"320x640 play": _fake(slack=-90, sh=2000)}) == []
    assert failures({"1280x760 play": {"error": "boom"}}) == ["1280x760 play: boom"]


def test_the_figures_match_the_play_fit_harness():
    src = (ROOT / "tests" / "test_play_fit.py").read_text(encoding="utf-8")
    found = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    for name, value in (("COCKPIT", COCKPIT), ("FLOW", FLOW), ("SLACK_MIN", SLACK_MIN),
                        ("I_SLACK_MIN", I_SLACK_MIN)):
        assert found.get(name) == value, name
    assert found["WORD_CAPS"]["i"] == WORD_CAP_I


def test_the_worst_model_is_bounded():
    m = worst_model()
    assert len(json.dumps(m, separators=(",", ":"))) <= progression.MAX_BYTES
    assert len(m["next"]) == 3 and len(m["skills"]) == 8


@pytest.fixture(scope="module")
def measures(tmp_path_factory):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    return measure(browser, tmp_path_factory.mktemp("progress_fit"))


def test_every_size_and_kind_was_measured(measures):
    want = {f"{w}x{h} {k}" for w, h in SIZES for k in KINDS}
    assert set(measures) == want, sorted(measures)
    for key, m in measures.items():
        assert "error" not in m, (key, m)
        # every tree view is one svg of at most 10 parts (decision 0002 budget)
        for sv in m["svg"]:
            assert sv["kids"] <= 10, (key, sv)
        if not key.endswith(" build"):
            assert m["heading"] == "Next up", key
        # PROGRESSION-OFFER: the way back to the item card shows with or
        # without an item check (the empty card teaches the item key)
        if key.endswith(" play-eval") or key.endswith(" play"):
            assert m["button"], key


def test_the_progression_view_fits_every_size(measures):
    fails = failures(measures)
    assert not fails, "\n".join(fails[:40]) + "\n\n" + "\n".join(figures(measures))


if __name__ == "__main__":
    import tempfile
    _b = find_browser()
    if not _b:
        sys.exit("no headless Chrome / Edge")
    from server.al import paths
    _tmp = paths.sidecar_dir("Temp")
    _tmp.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="al-progress-fit-", dir=_tmp) as tmp:
        _m = measure(_b, tmp)
    print("\n".join(figures(_m)))
    _f = failures(_m)
    print("\n".join(_f) if _f else "fits")
    sys.exit(1 if _f else 0)
