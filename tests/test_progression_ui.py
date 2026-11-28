"""PROGRESSION-VIEW (decision 0092): web/panels/tree.js and
web/panels/progression.js under node, plus their static rules.

The renderer draws every node of a state into one path (decision 0002
element budget), frames the Play mini-tree on the due nodes, maps the
export box into the measured pixel area and finds the node under the
pointer; region I swaps between the item card and the progression with
no click (decide()). The static rules: text through textContent only, no
timer, no storage, no motion, no GGG image, colours only from the tokens.
Skips the node part without node.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import progression_fixtures as pf  # noqa: E402
from server.al.theorycraft import progression  # noqa: E402

TREE = ROOT / "web" / "panels" / "tree.js"
VIEW = ROOT / "web" / "panels" / "progression.js"
CSS = ROOT / "web" / "panels" / "progression.css"


def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    return node


def run(script, data):
    r = subprocess.run([_node(), "-e", script], input=json.dumps(data), capture_output=True,
                       text=True, encoding="utf-8", timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def model():
    t = pf.tree()
    return progression.build_model(tree=t, level=29, area_id="G1_4", zone="Demo Woods",
                                   guide=pf.GUIDE, kindler={"plan": pf.plan(t), "stage": 2,
                                                            "label": "Demo"})


TREE_JS = r"""
const T = require("./web/panels/tree.js");
let data = "";
process.stdin.on("data", (c) => { data += c; });
process.stdin.on("end", () => {
  const m = JSON.parse(data);
  const v = m.tree;
  const full = T.frame(v, "full"), mini = T.frame(v, "mini");
  const p = T.paths(v, full, 500, 400, m["new"]);
  const count = (d) => (d.match(/M/g) || []).length;
  const byState = {};
  v.n.forEach((r) => { byState[r[4]] = (byState[r[4]] || 0) + 1; });
  const map = T.mapper(full, 500, 400);
  const due = v.n.findIndex((r) => r[4] === "d");
  const at = map(v.n[due][1], v.n[due][2]);
  process.stdout.write(JSON.stringify({
    full: full, mini: mini, box: v.box,
    nodes: { o: count(p.nodes.o), l: count(p.nodes.l), h: count(p.nodes.h), d: count(p.nodes.d) },
    byState: byState, fresh: count(p.fresh), rings: count(p.rings),
    edges: Object.keys(p.edges).reduce((a, k) => a + count(p.edges[k]), 0),
    hit: T.hit(v, full, 500, 400, at[0] + 1, at[1]), due: due,
    miss: T.hit(v, full, 500, 400, -50, -50),
    label: T.label(v, due), empty: T.paths(null, null, 1, 1).nodes.h,
    small: T.radius("s", 0.001), big: T.radius("k", 10), miniSmall: T.radius("s", 0.001, true),
    through: T.crosses([-50, 10], [600, 20], 500, 400, 8)
  }));
});
"""


def test_the_renderer_draws_each_state_in_one_path(model):
    out = run(TREE_JS, model)
    assert out["full"] == model["tree"]["box"]
    # every sent node is drawn once, in the path of its state
    assert out["nodes"] == {k: out["byState"].get(k, 0) for k in "olhd"}
    assert out["fresh"] == len(model["new"])
    assert out["rings"] == sum(1 for r in model["tree"]["n"] if r[3] in "ca")
    assert out["edges"] == len(model["tree"]["e"])
    # the mini frame sits on the due nodes: a smaller box than the whole
    assert out["mini"][2] * out["mini"][3] < out["full"][2] * out["full"][3]
    assert out["hit"] == out["due"] and out["miss"] == -1
    assert "(take next)" in out["label"]
    assert out["empty"] == ""
    assert out["small"] == 2 and out["big"] == 12 and out["miniSmall"] == 4
    assert out["through"] is True


DECIDE_JS = r"""
const P = require("./web/panels/progression.js");
const doc = { getElementById: () => null };
const sum = (level, line) => ({ key: "k" + level, level: level, source_line: line || "a",
                                tree: true, next: [] });
const out = [];
function push(s, ev, now) {
  P.step(doc, { progression: s, eval: ev ? { id: ev } : null, now: now });
  const st = P.state();
  out.push(st.mode + (st.pending ? "*" : ""));
}
push(sum(10), "", 0);          // first paint: the item card (PG-12)
push(sum(11), "", 10);         // a level-up: progress by itself
push(sum(11), "7", 100);       // a new item check: item
push(sum(12), "7", 105);       // a level-up 5 s after the check: held (PG-1)
push(sum(12), "7", 115);       // still under 20 s: held
push(sum(12), "7", 121);       // the first push after the hold: progress
push(sum(12), "8", 130);       // another check: item
P.state().resync = true;       // the page was hidden meanwhile
push(sum(13), "8", 200);       // what moved while hidden is no news
push(sum(null), "8", 210);     // a core restart: level unknown
push(sum(13), "8", 230);       // null to a level: no move
push(sum(14), "8", 240);       // a real level-up: progress
push(sum(14, "b"), "8", 250);  // stays
push(null, "8", 260);          // nothing to show: item
process.stdout.write(JSON.stringify({ out: out }));
"""


def test_region_i_swaps_by_itself():
    got = run(DECIDE_JS, {})
    assert got["out"] == ["item", "progress", "item", "item*", "item*", "progress", "item",
                          "item", "item", "item", "progress", "progress", "item"]


FAILS_JS = r"""
const P = require("./web/panels/progression.js");
let calls = 0;
const doc = { hidden: false, getElementById: () => null };
const ctx = { api: () => { calls += 1; return Promise.reject(new Error("x")); },
              getSnap: () => null };
P.reset(); P.wire({ getElementById: () => null }, ctx);
const s1 = { progression: { key: "a", level: 1, tree: true, next: [] } };
const tick = (s) => new Promise((r) => { P.paint(doc, Object.assign({}, s)); setImmediate(r); });
(async () => {
  for (let i = 0; i < 5; i++) { await tick(s1); }
  const first = calls;
  await tick({ progression: { key: "b", level: 2, tree: true, next: [] } });
  process.stdout.write(JSON.stringify({ first: first, after: calls }));
})();
"""


def test_a_failing_read_stops_after_two_tries_per_key():
    got = run(FAILS_JS, {})
    assert got == {"first": 2, "after": 3}

def test_the_view_files_keep_the_page_rules():
    for path in (TREE, VIEW):
        src = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="ascii"), flags=re.S)
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "setInterval", "setTimeout",
                    "localStorage", "sessionStorage", "clipboard", "requestAnimationFrame",
                    ".png", ".jpg", "style.", "aria-live", "fetch("):
            assert bad not in src, (path.name, bad)
    css = CSS.read_text(encoding="ascii")
    for bad in ("animation", "transition", "@keyframes", "url("):
        assert bad not in css, bad
    # colours only from the tokens (design 0001 C3)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", css)
    # the page reads the model only through the token-gated route
    assert '"/api/progression"' in VIEW.read_text(encoding="ascii")


OFFER_JS = r"""
const P = require("./web/panels/progression.js");
// a small fake document: elements by id, attributes, children, clicks
function mk(tag) {
  const n = { tagName: tag, id: "", hidden: false, children: [], attrs: {}, on: {},
    textContent: "", className: "", parentNode: null,
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { this.id = v; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children.splice(this.children.indexOf(c), 1); return c; },
    insertBefore(c, ref) { c.parentNode = this; const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) { this.children.push(c); } else { this.children.splice(i, 0, c); } return c; },
    get firstChild() { return this.children[0] || null; },
    get lastChild() { return this.children[this.children.length - 1]; },
    addEventListener(t, f) { this.on[t] = f; },
    focus() { doc.activeElement = this; },
    getBoundingClientRect() { return { width: 0, height: 0 }; } };
  return n;
}
function find(n, id) {
  if (n.id === id) { return n; }
  for (const c of n.children) { const f = find(c, id); if (f) { return f; } }
  return null;
}
const body = mk("body");
const region = body.appendChild(mk("section")); region.id = "play-i";
const head = body.appendChild(mk("h2")); head.id = "play-i-h";
const doc = { hidden: false, activeElement: null,
  createElement: mk, createElementNS: (ns, t) => mk(t),
  getElementById: (id) => find(body, id) };
let snap = null;
P.reset(); P.wire(doc, { api: () => new Promise(() => {}), getSnap: () => snap });
const out = {};
const push = (s) => { snap = s; P.paint(doc, s); };
// no progression: no offer
push({ now: 1 });
out.none = doc.getElementById("pg-offer") ? !doc.getElementById("pg-offer").hidden : false;
// a progression with a tree, nothing checked, no level-up yet: the item card
// shows and the offer is there
push({ now: 2, progression: { key: "a", level: 5, tree: true, next: [] } });
const offer = doc.getElementById("pg-offer");
out.mode1 = region.getAttribute("data-pg");
out.offer1 = !!offer && !offer.hidden;
out.flag1 = region.getAttribute("data-pg-offer");
out.first1 = region.children[0] === offer;
out.name1 = offer.getAttribute("aria-label");
// one click opens the view at once, with its way back, focus on it
offer.on.click();
out.mode2 = region.getAttribute("data-pg");
out.head2 = head.textContent;
out.offer2 = !offer.hidden;
out.back2 = !doc.getElementById("pg-mini-item").hidden;
out.focus2 = doc.activeElement && doc.activeElement.id;
// it stays on the next push of the same state
push({ now: 3, progression: { key: "a", level: 5, tree: true, next: [] } });
out.mode3 = region.getAttribute("data-pg");
// Item check gives the card back and the offer returns, focused
doc.getElementById("pg-mini-item").on.click();
out.mode4 = region.getAttribute("data-pg");
out.offer4 = !offer.hidden;
out.focus4 = doc.activeElement && doc.activeElement.id;
// a progression with nothing to draw offers nothing
push({ now: 4, progression: { key: "b", level: 5, tree: false, next: [] } });
out.offer5 = !offer.hidden;
process.stdout.write(JSON.stringify(out));
"""


def test_region_i_offers_the_view_before_any_level_up():
    """PROGRESSION-OFFER: the item card carries a 'Next up' button while the
    progression has something to draw, so Play shows the view exists without
    waiting for a level-up (operator report 2026-11-28)."""
    got = run(OFFER_JS, {})
    assert got == {"none": False, "mode1": "off", "offer1": True, "flag1": "on",
                   "first1": True, "name1": "Next up and passive tree",
                   "mode2": "on", "head2": "Next up", "offer2": False, "back2": True,
                   "focus2": "pg-mini-item", "mode3": "on", "mode4": "off", "offer4": True,
                   "focus4": "pg-offer", "offer5": False}


GEM_LEVEL_JS = r"""
const P = require("./web/panels/progression.js");
let data = "";
process.stdin.on("data", (c) => { data += c; });
process.stdin.on("end", () => {
  const rows = JSON.parse(data);
  process.stdout.write(JSON.stringify(rows.map((r) => {
    const v = P.gemLevel(r);
    return v === undefined ? "none" : v;
  })));
});
"""


def test_gem_buttons_carry_the_socket_level_only():
    """GEM-LEVEL-WIRE: a pasted PoB build's skill row sends its socket gem
    level to the item popover; a Kindler plan's row (whose levels are
    character levels) sends none, so the popover shows level 1."""
    t = pf.tree()
    b = pf.build(t, skills=[[("Spark", "SparkPlayer", 3), ("Demo Support", "SupportDemo", 1)]])
    pob = progression.build_model(build=b, tree=t, level=30)
    assert pob["source"] == "pob"
    spark = [r for r in pob["skills"] if r["name"] == "Spark"]
    assert spark and spark[0]["level"] == 3
    kin = progression.build_model(tree=t, level=29, kindler={"plan": pf.plan(t), "stage": 2,
                                                             "label": "Demo"})
    assert kin["source"] == "kindler" and kin["skills"]
    assert all(r["level"] is None for r in kin["skills"])
    got = run(GEM_LEVEL_JS, [spark[0], kin["skills"][0], {"level": 0}, {"level": "3"}, {}])
    assert got == [3, "none", "none", "none", "none"]
    src = VIEW.read_text(encoding="utf-8")
    assert "info.button(doc, r.name, gemLevel(r))" in src


def test_kindler_gem_buttons_send_no_level():
    """GEM-LEVEL-WIRE: the Kindler plan knows no gem level (its gem levels
    are the character level a gem is usable from), so its buttons name the
    gem only and never guess one."""
    src = (ROOT / "web" / "kindler.js").read_text(encoding="utf-8")
    calls = re.findall(r"info\.button\(([^)]*)\)", src)
    assert calls == ["s.doc, name"]


ASC_NONE_JS = r"""
const P = require("./web/panels/progression.js");
function mk(tag, ns) {
  const n = { tagName: tag, namespaceURI: ns || "http://www.w3.org/1999/xhtml", id: "",
    hidden: false, children: [], attrs: {}, on: {}, textContent: "", className: "",
    scrollHeight: 0, clientHeight: 0,
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { this.id = v; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    hasAttribute(k) { return k in this.attrs; },
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children.splice(this.children.indexOf(c), 1); return c; },
    replaceChildren() { this.children = []; },
    get lastChild() { return this.children[this.children.length - 1]; },
    addEventListener(t, f) { this.on[t] = f; },
    focus() {},
    getBoundingClientRect() { return { width: 0, height: 0 }; } };
  return n;
}
function find(n, id) {
  if (n.id === id) { return n; }
  for (const c of n.children) { const f = find(c, id); if (f) { return f; } }
  return null;
}
let data = "";
process.stdin.on("data", (c) => { data += c; });
process.stdin.on("end", () => {
  const models = JSON.parse(data);
  const body = mk("body");
  const panel = body.appendChild(mk("section")); panel.id = "panel-build";
  const doc = { hidden: false, createElement: (t) => mk(t), createElementNS: (ns, t) => mk(t, ns),
    getElementById: (id) => find(body, id) };
  P.reset();
  P.wire(doc, { api: () => new Promise(() => {}), getSnap: () => null });
  const out = [];
  models.forEach((m) => {
    P.state().model = m; P.state().key = m.key; P.state().filled = null;
    P.setOpen(doc, true, false);
    const asc = doc.getElementById("pg-asc"), none = doc.getElementById("pg-asc-none");
    out.push({ svgHidden: asc.hasAttribute("hidden"), line: none.textContent,
               lineShown: !none.hidden, muted: none.className.indexOf("muted") >= 0 });
  });
  process.stdout.write(JSON.stringify(out));
});
"""


def test_an_empty_ascendancy_box_shows_one_line():
    """PROGRESSION-ASC-EMPTY: with no ascendancy to draw the svg frame is
    hidden (an svg has no hidden property, so the attribute) and the
    server's one muted line shows instead; a drawn ascendancy hides it."""
    import dataclasses
    t = pf.tree()
    b = pf.build(t)
    drawn = progression.build_model(build=b, tree=t, level=30)
    none = progression.build_model(build=dataclasses.replace(b, ascendancy=None), tree=t,
                                   level=30)
    got = run(ASC_NONE_JS, [none, drawn, none])
    line = "No ascendancy in this build yet."
    assert got[0] == {"svgHidden": True, "line": line, "lineShown": True, "muted": True}
    assert got[1]["svgHidden"] is False and got[1]["lineShown"] is False
    assert got[1]["line"] == ""
    assert got[2] == got[0]
