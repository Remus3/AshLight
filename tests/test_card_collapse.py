"""UI-CARD-COLLAPSE (decision 0082 part 3 and its amendment 2026-11-19):
collapsible cards on Build and items and Run, in the desktop client only.

Static checks read web/index.html (the script tag, the card ids),
web/collapse.js (no browser storage, no timer, no inline style, requests
only through the page host's token api), web/app.css (the hooks, the
cockpit tracks) and the pager seams (web/pager.js fitRows / refit,
web/search.js rowPager; adjudicator ruling 2026-11-23). Behavioural checks
drive web/collapse.js, web/pager.js and web/search.js under node with a
small fake DOM; they skip without node.
"""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths
from server.al import uilayout

HTML = srcpaths.read("index.html")
JS = srcpaths.read("collapse.js")
CSS = srcpaths.read("app.css")
PAGER = srcpaths.read("pager.js")
SEARCH = srcpaths.read("search.js")


def _code(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


# --- static ------------------------------------------------------------------

def test_script_tag_before_the_region_files():
    tags = re.findall(r'<script src="/web/([a-z]+)\.js" defer></script>', HTML)
    assert tags.count("collapse") == 1
    assert tags.index("registry") < tags.index("collapse") < tags.index("slots")
    # no collapse button in the markup: only web/collapse.js adds them
    assert "card-collapse" not in HTML


def test_card_ids_match_the_core_allow_list():
    m = re.search(r"var PANELS = \{(.*?)\};", JS, re.S)
    ids = re.findall(r'"([a-z]+box)"', m.group(1))
    assert tuple(ids) == uilayout.CARD_IDS
    build = HTML[HTML.index('id="panel-build"'):HTML.index('id="panel-run"')]
    run = HTML[HTML.index('id="panel-run"'):HTML.index('id="panel-settings"')]
    found_b = re.findall(r'<section id="([a-z]+box)" class="card[^"]*grid-card', build)
    found_r = re.findall(r'<section (?:id="([a-z]+box)" )?class="card[^"]*grid-card( events)?', run)
    found_r = [i or ("eventsbox" if e else "") for i, e in found_r]
    assert tuple(found_b) == uilayout.BUILD_CARDS  # grid order is page order
    assert tuple(found_r) == uilayout.RUN_CARDS
    play = HTML[HTML.index('id="panel-play"'):HTML.index('id="panel-build"')]
    settings = HTML[HTML.index('id="panel-settings"'):]
    for cid in uilayout.CARD_IDS:
        assert cid not in play and f'id="{cid}"' not in settings


def test_collapse_js_is_app_only_and_quiet():
    code = _code(JS)
    for bad in ("localStorage", "sessionStorage", "indexedDB", "setTimeout", "setInterval",
                "requestAnimationFrame", "fetch(", "XMLHttpRequest", "EventSource",
                "clipboard", "innerHTML", "aria-live", ".style", "cssText", "focus("):
        assert bad not in code, bad
    assert "alClient" in code  # the client gate
    assert 'host.api("PUT", PATH' in code and 'host.api("GET", PATH)' in code
    assert '"/api/ui/layout"' in code
    assert re.fullmatch(r"[\x0a\x20-\x7e]*", JS)
    assert 'BY_CLASS = { eventsbox: "events" }' in code


def test_css_hooks():
    assert '.grid-card[data-collapsed="true"] > :not(.card-head)' in CSS
    assert ".card-collapse" in CSS and "min-width: 1.5rem; min-height: 1.5rem" in CSS
    block = CSS[CSS.index("UI-CARD-COLLAPSE (decision 0082"):]
    media = block[block.index("@media (min-width: 64em) and (min-height: 43.75em)"):]
    assert "grid-template-rows: minmax(var(--cc-head), auto) minmax(0, 1fr) minmax(0, 1fr)" in media
    for cc, rows in (("top", "1 / 3"), ("top-head", "1 / 2"), ("top-tall", "1 / 4"),
                     ("bot", "3 / 5"), ("bot-head", "4 / 5"), ("bot-tall", "2 / 5"),
                     ("bot-under", "2 / 3")):
        assert f'.col[data-cc="{cc}"] {{ grid-row: {rows};' in media, cc
    # the text-spacing override keeps its own tracks
    assert media.count(':root:not([data-text-spacing="user"])') == 11


def test_pager_seams():
    assert "fitRows: fitRows, refit: refit" in PAGER
    assert "FREED_PX = { full: 264, compact: 236 }" in PAGER
    assert "P.fitRows(node, k, sizes[k]" in SEARCH
    assert "lastRows !== fitted(klass())" in SEARCH


# --- behaviour under node ------------------------------------------------------

HARNESS = r"""
const path = require("path");
const web = process.argv[2];
const C = require(path.join(web, "collapse.js"));
const P = require(path.join(web, "pager.js"));
const S0 = require(path.join(web, "search.js"));
const out = {};

function makeDoc() {
  const byId = {};
  function node(tag) {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], attrs: {},
      listeners: {}, parentNode: null, _text: "", type: "",
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); byId[v] = this; },
      get classList() {
        const self = this;
        return {
          contains: (c) => self.className.split(/\s+/).includes(c),
          add: (c) => { if (!self.classList.contains(c)) { self.className = (self.className + " " + c).trim(); } }
        };
      },
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text; },
      set textContent(v) { this.children = []; this._text = String(v); },
      setAttribute(k, v) { if (k === "id") { this.id = v; } else { this.attrs[k] = String(v); } },
      getAttribute(k) { return k === "id" ? (this.attrs.id || null) : (k in this.attrs ? this.attrs[k] : null); },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; },
      replaceChildren(...cs) { this.children = []; cs.forEach((c) => this.appendChild(c)); },
      addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn()); },
      querySelector(sel) { return find(this, sel); }
    };
    return n;
  }
  function match(n, sel) {
    if (sel[0] === ".") { return n.classList.contains(sel.slice(1)); }
    return n.tagName === sel.toUpperCase();
  }
  function find(root, sel) {
    for (const c of root.children) {
      if (match(c, sel)) { return c; }
      const d = find(c, sel);
      if (d) { return d; }
    }
    return null;
  }
  const doc = {
    documentElement: node("html"),
    createElement: node,
    getElementById: (id) => byId[id] || null
  };
  doc.byId = byId;
  return doc;
}

function card(doc, col, id, titleText) {
  const box = doc.createElement("section");
  // the Recent card has no id of its own (web/collapse.js BY_CLASS)
  if (id === "eventsbox") { box.className = "card grid-card events"; } else {
    box.id = id;
    box.className = "card grid-card";
  }
  const head = doc.createElement("div");
  head.className = "card-head";
  const h = doc.createElement("h2");
  h.textContent = titleText;
  head.appendChild(h);
  box.appendChild(head);
  const page = doc.createElement("div");
  page.className = "card-page";
  page.setAttribute("data-page", "main");
  box.appendChild(page);
  const slot = doc.createElement("div");
  slot.id = id + "-slot";
  page.appendChild(slot);
  col.appendChild(box);
  return box;
}

function page() {
  const doc = makeDoc();
  Object.keys(C.PANELS).forEach((pid) => {
    const p = doc.createElement("div");
    p.id = pid;
    p.className = "panel panel-grid panel-cards";
    C.PANELS[pid].forEach((id) => {
      const col = doc.createElement("div");
      col.className = "col";
      p.appendChild(col);
      card(doc, col, id, id.replace("box", "").replace(/^./, (c) => c.toUpperCase()));
    });
  });
  return doc;
}

function host(answer) {
  const calls = [];
  const reads = [];
  return {
    calls, reads,
    onConnect: (fn) => reads.push(fn),
    api: (method, p, body) => {
      calls.push([method, p, body === undefined ? null : body]);
      return { then: (ok) => { ok(answer); return { catch: () => null }; }, catch: () => null };
    }
  };
}

function win(cls) {
  return { getComputedStyle: () => ({ getPropertyValue: () => cls }),
    addEventListener: () => null, ALPager: P };
}

// cells
out.cells = {
  none: C.cells([false, false, false, false, false, false]).map((c) => c.cc),
  top1: C.cells([true, false, false, false, false, false]).map((c) => [c.col, c.cc, c.tall]),
  bot2: C.cells([false, false, false, false, true, false]).map((c) => [c.cc, c.tall]),
  both3: C.cells([false, false, true, false, false, true]).map((c) => c.cc)
};

// a plain browser: nothing
{
  const doc = page();
  const h = host({});
  const pan = C.panel(() => h, win("full"));
  out.browser = { wired: pan.wireDoc(doc, null), calls: h.calls.length, reads: h.reads.length,
    cls: doc.getElementById("panel-build").className,
    head: doc.getElementById("buildbox").children[0].children.length };
}

// the client
{
  const doc = page();
  const h = host({ schema: 1, collapsed: { buildbox: true, actsbox: true, zzq: true, evalbox: "yes" } });
  const pan = C.panel(() => h, win("full"));
  const wired = pan.wireDoc(doc, { name: "client" });
  const b = doc.getElementById("buildbox").children[0].children[1];
  const before = { expanded: b.getAttribute("aria-expanded"), sr: b.children[1].textContent,
    controls: b.getAttribute("aria-controls"), cls: b.className, type: b.type,
    panel: doc.getElementById("panel-build").className, reads: h.reads.length };
  h.reads.forEach((fn) => fn());
  const box = (id) => doc.getElementById(id) || doc.getElementById(id + "-slot").parentNode.parentNode;
  const after = {
    build: box("buildbox").getAttribute("data-collapsed"),
    evalFit: box("evalbox").getAttribute("data-fit"),
    evalCol: box("evalbox").parentNode.getAttribute("data-cc"),
    buildCol: box("buildbox").parentNode.getAttribute("data-cc"),
    colNo: box("pricesbox").parentNode.getAttribute("data-cc-col"),
    acts: box("actsbox").getAttribute("data-collapsed"),
    deathsCol: box("deathsbox").parentNode.getAttribute("data-cc"),
    eventsCol: box("eventsbox").parentNode.getAttribute("data-cc"),
    expanded: b.getAttribute("aria-expanded"), sr: b.children[1].textContent,
    evalSaved: box("evalbox").getAttribute("data-collapsed")
  };
  // a click opens it and saves the one id
  b.click();
  const click = { build: box("buildbox").getAttribute("data-collapsed"),
    evalFit: box("evalbox").getAttribute("data-fit"), expanded: b.getAttribute("aria-expanded"),
    last: h.calls[h.calls.length - 1] };
  // alerts: collapse build again, then a build alert opens it without a save
  b.click();
  const n = h.calls.length;
  pan.paint({ deaths: 2, trade_requests: [] });
  const deathsBtn = box("deathsbox").children[0].children[1];
  deathsBtn.click();  // collapse Deaths
  pan.paint({ deaths: 2, trade_requests: [], build_alert: { text: "Your build is 5 levels behind." } });
  const alertBuild = box("buildbox").getAttribute("data-collapsed");
  const noDeathYet = box("deathsbox").getAttribute("data-collapsed");
  pan.paint({ deaths: 3, trade_requests: [], build_alert: { text: "Your build is 5 levels behind." } });
  const alertDeath = box("deathsbox").getAttribute("data-collapsed");
  // the player collapses Build while the alert shows; a reconnect (a new
  // GET) does not reopen it
  b.click();
  h.reads.forEach((fn) => fn());
  const afterReconnect = box("buildbox").getAttribute("data-collapsed");
  // a new trade request opens Recent (found by its class)
  const recent = doc.getElementById("eventsbox-slot").parentNode.parentNode;
  recent.children[0].children[1].click();
  const recentShut = recent.getAttribute("data-collapsed");
  pan.paint({ deaths: 3, trade_requests: [{ id: 7 }], build_alert: { text: "Your build is 5 levels behind." } });
  const recentOpen = recent.getAttribute("data-collapsed");
  out.client = { wired, before, after, click,
    alerts: { build: alertBuild, deathsBefore: noDeathYet, deaths: alertDeath,
      saves: h.calls.slice(n, n + 1).map((c) => c[0] + " " + JSON.stringify(c[2])),
      afterReconnect, recentShut, recentOpen,
      recentId: recent.id, recentControls: recent.children[0].children[1].getAttribute("aria-controls") } };
  // flow class: no tall card
  const doc2 = page();
  const h2 = host({ schema: 1, collapsed: { buildbox: true } });
  const pan2 = C.panel(() => h2, win("flow"));
  pan2.wireDoc(doc2, {});
  h2.reads.forEach((fn) => fn());
  out.flow = { fit: doc2.getElementById("evalbox").getAttribute("data-fit"),
    collapsed: doc2.getElementById("buildbox").getAttribute("data-collapsed") };
}

// the pagers: fitRows, refit, rowPager relayout
{
  const doc = page();
  const slot = doc.getElementById("evalbox-slot");
  const rows = Array.from({ length: 40 }, (_, i) => "row " + i);
  const pg = P.build(doc, { rows: rows, sizeClass: "full", label: "x" });
  slot.appendChild(pg.node);
  const rp = S0.rowPager(doc, { rows: rows, sizeClass: "compact", label: "y",
    text: (r) => r, parts: (r) => [{ text: r }] });
  doc.getElementById("actsbox-slot").appendChild(rp.node);
  const first = [pg.state().items.length, rp.state().items.length];
  doc.getElementById("evalbox").setAttribute("data-fit", "tall");
  doc.getElementById("actsbox").setAttribute("data-fit", "tall");
  P.refit();
  S0.relayout();
  const tall = [pg.list.children.length, rp.state().items.length];
  out.pager = { first, tall,
    fit: [P.fitRows(slot, "full", 10, 22), P.fitRows(slot, "compact", 8, 22),
      P.fitRows(slot, "compact", 8, 24), P.fitRows(doc.getElementById("buildbox-slot"), "full", 10, 22),
      P.fitRows(slot, "flow", 10, 22)] };
}
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    script = tmp_path_factory.mktemp("collapse") / "h.js"
    script.write_text(HARNESS, encoding="ascii")
    res = subprocess.run([node, str(script), str(srcpaths.WEB)], capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_cells(run):
    c = run["cells"]
    assert c["none"] == ["top", "top", "top", "bot", "bot", "bot"]
    assert c["top1"][0] == [1, "top-head", False]
    assert c["top1"][3] == [1, "bot-tall", True]
    assert [x[0] for x in c["top1"][1:3]] == [2, 3]
    assert c["bot2"][1] == ["top-tall", True] and c["bot2"][4] == ["bot-head", False]
    assert c["both3"] == ["top", "top", "top-head", "bot", "bot", "bot-under"]


def test_plain_browser_has_no_button_no_state_no_request(run):
    assert run["browser"] == {"wired": False, "calls": 0, "reads": 0,
                              "cls": "panel panel-grid panel-cards", "head": 1}


def test_client_buttons_and_loaded_state(run):
    c = run["client"]
    assert c["wired"] is True
    b = c["before"]
    assert b["expanded"] == "true" and b["sr"] == "Collapse Build"
    assert b["controls"] == "buildbox-part-main"
    assert b["cls"] == "card-collapse btn-24" and b["type"] == "button"
    assert "cc-on" in b["panel"] and b["reads"] == 1
    a = c["after"]
    assert a["build"] == "true" and a["buildCol"] == "top-head"
    assert a["evalCol"] == "bot-tall" and a["evalFit"] == "tall"
    assert a["colNo"] == "2" and a["acts"] == "true" and a["eventsCol"] == "bot-tall"
    assert a["deathsCol"] == "bot"
    assert a["expanded"] == "false" and a["sr"] == "Expand Build"
    assert a["evalSaved"] is None  # a bad value in the answer is dropped


def test_click_saves_one_id(run):
    k = run["client"]["click"]
    assert k["build"] is None and k["evalFit"] is None and k["expanded"] == "true"
    assert k["last"] == ["PUT", "/api/ui/layout", {"collapsed": {"buildbox": False}}]


def test_alerts_open_the_card_without_a_save(run):
    a = run["client"]["alerts"]
    assert a["build"] is None  # a new build alert opened the collapsed Build card
    assert a["deathsBefore"] == "true"  # no new death: Deaths stays collapsed
    assert a["deaths"] is None  # a new death opened it
    # the only save after the alerts started is the player's Deaths click
    assert a["saves"] == ['PUT {"collapsed":{"deathsbox":true}}']
    # a reconnect does not reopen a Build card collapsed while the alert showed
    assert a["afterReconnect"] == "true"
    # the Recent card (no id, found by its class) opens for a new trade request
    assert a["recentShut"] == "true" and a["recentOpen"] is None
    assert a["recentId"] == "" and a["recentControls"] == "eventsbox-part-main"


def test_flow_class_collapses_without_a_tall_card(run):
    assert run["flow"] == {"fit": None, "collapsed": "true"}


def test_pagers_show_the_rows_that_fit(run):
    p = run["pager"]
    assert p["first"] == [10, 8]
    assert p["tall"] == [10 + 264 // 22, 8 + 236 // 22]
    assert p["fit"] == [22, 18, 17, 10, 10]
