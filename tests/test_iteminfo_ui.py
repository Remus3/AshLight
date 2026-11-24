"""ITEM-INFO-UI (decision 0082 part 1, decision 0083 points 1, 5 and 6):
item names as link-like buttons and the one shared item info popover.

Static checks read web/index.html (the one popover element and the
script tag), web/iteminfo.js (no network but the token api, no timer,
text through textContent only), web/panels/iteminfo.css (fixed, sized,
scrolling inside; linked by the al:panels marker, adjudicator ruling
2026-11-23) and the Prices list wiring (web/panels/rates.js,
web/panels/pager.js, web/search.js; adjudicator ruling 2026-11-23).
Behavioural checks drive web/iteminfo.js, web/prices.js,
web/pricewatch.js and web/search.js under node with a small fake DOM;
they skip without node."""

import json
import re
import shutil
import subprocess

import pytest

import srcpaths

HTML = srcpaths.read("index.html")
JS = srcpaths.read("iteminfo.js")
CSS = srcpaths.read("panels/iteminfo.css")
RATES = srcpaths.read("panels/rates.js")
PAGER = srcpaths.read("panels/pager.js")
SEARCH = srcpaths.read("search.js")

PB_CREDIT = "Path of Building (MIT), community-written, may be out of date"


def _code(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _pop():
    m = re.search(r'<div id="iteminfo-pop"[^>]*>(.*?)\n</div>', HTML, re.S)
    assert m, "the popover element"
    return m.group(0)


# --- the markup -------------------------------------------------------------

def test_one_popover_element_outside_every_card():
    assert HTML.count('id="iteminfo-pop"') == 1
    pop = _pop()
    head = pop.split(">", 1)[0]
    for attr in ('popover="manual"', 'role="dialog"', 'aria-label="Item info"', 'tabindex="-1"'):
        assert attr in head, attr
    # outside main, so it never sits inside (or grows) a card
    assert HTML.index('id="iteminfo-pop"') > HTML.index("</main>")
    assert HTML.index('id="iteminfo-pop"') < HTML.index("</body>")


def test_popover_heading_takes_focus_and_the_poe2db_link_is_a_click():
    pop = _pop()
    assert re.search(r'<h2 id="iteminfo-title"[^>]*tabindex="-1"', pop)
    assert ">Drops, vendor and disenchant: see poe2db (community site)</p>" in pop
    m = re.search(r'<a id="iteminfo-poe2db"[^>]*>More on poe2db</a>', pop, re.S)
    assert m
    link = m.group(0)
    # no web address in the page itself (tests/test_webpage.py): the
    # script sets the href from the name
    assert "href=" not in link
    assert 'target="_blank"' in link and 'rel="noopener noreferrer"' in link
    assert "(opens in a new tab)" in link


def test_script_tag_loads_after_prices_and_before_app():
    tag = '<script src="/web/iteminfo.js" defer></script>'
    assert HTML.count(tag) == 1
    assert HTML.index('src="/web/prices.js"') < HTML.index(tag) < HTML.index('src="/web/app.js"')
    assert HTML.index(tag) < HTML.index('src="/web/slots.js"')
    # the sheet comes from the panels marker, not a tag of its own
    assert "/web/iteminfo.css" not in HTML


# --- the script --------------------------------------------------------------

def test_script_reads_only_the_cache_route_through_the_token_api():
    code = _code(JS)
    for bad in ("fetch(", "XMLHttpRequest", "EventSource", "innerHTML", "outerHTML",
                "insertAdjacentHTML", "setTimeout", "setInterval", "clipboard",
                "localStorage", "sessionStorage", "aria-live", "createElement(\"img\")",
                "window.open", "trade2"):
        assert bad not in code, bad
    assert '"/api/iteminfo?name="' in code
    assert "encodeURIComponent(name)" in code
    assert 'ctl.api("GET", PATH' in code


def test_script_registers_itself_after_price_watch():
    assert re.search(r'var NAME = "iteminfo";', JS)
    assert re.search(r"var ORDER = 165;", JS)
    assert "root.ALApp.register(" in JS


# --- the sheet ---------------------------------------------------------------

def test_popover_is_fixed_bounded_and_scrolls_inside():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    m = re.search(r"\.iteminfo-pop \{(.*?)\}", css, re.S)
    assert m
    body = m.group(1)
    for rule in ("position: fixed;", "width: min(22rem, 90vw);", "max-height: 60vh;",
                 "overflow: auto;", "margin: 0;"):
        assert rule in body, rule
    assert not re.search(r"(?<![-\w])(animation|transition)\s*:", css)


def test_name_button_keeps_the_24px_target():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    m = re.search(r"button\.link\.iteminfo-name \{(.*?)\}", css, re.S)
    assert m and "min-height: 1.5rem;" in m.group(1)


# --- the Prices list wiring --------------------------------------------------

def _block(src, start):
    i = src.index(start)
    return src[i:src.index("\n  }\n", i)]


def test_prices_list_rows_carry_item_name_buttons():
    body = _block(RATES, "function paintPricesList()")
    assert re.search(r"watch\.concat\(rateRows, trendRows\)", body)
    assert "parts: itemParts" in body
    assert "window.ALItemInfo.sync()" in body
    parts = _block(RATES, "function itemParts(")
    assert "I.parts(document, r.text, r.item)" in parts
    assert "[{ text: r.text }]" in parts  # plain text without the file
    assert "item: r.name" in RATES
    assert "P.trendList(ratesDoc)" in RATES


def test_pager_forwards_parts_and_search_takes_a_node_part():
    assert 'if (typeof opts.parts === "function") { po.parts = opts.parts; }' in PAGER
    assert "part && part.node ? part.node" in SEARCH


# --- behaviour under node ----------------------------------------------------

def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    return node


HARNESS = r"""
const path = require("path");
const web = process.argv[2];
const I = require(path.join(web, "iteminfo.js"));
const P = require(path.join(web, "prices.js"));
const PW = require(path.join(web, "pricewatch.js"));
const S = require(path.join(web, "search.js"));

function makeDoc() {
  const doc = { listeners: {}, activeElement: null, byId: {} };
  function node(tag) {
    const n = {
      tagName: tag.toUpperCase(), nodeType: 1, className: "", hidden: false, children: [],
      attrs: {}, listeners: {}, parentNode: null, style: {}, href: "", type: "", _text: "",
      rect: { top: 100, bottom: 124, left: 40, width: 80, height: 24 },
      get classList() {
        const self = this;
        return { contains: (c) => self.className.split(/\s+/).includes(c) };
      },
      get firstChild() { return this.children[0] || null; },
      get textContent() {
        return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
      },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; return c; },
      replaceChildren() { this.children.forEach((c) => { c.parentNode = null; }); this.children = []; this._text = ""; },
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.byId[v] = this; } },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
      contains(o) { for (let x = o; x; x = x.parentNode) { if (x === this) { return true; } } return false; },
      focus() { doc.activeElement = this; },
      getBoundingClientRect() { return this.rect; },
      get isConnected() { return doc.body.contains(this); }
    };
    return n;
  }
  doc.createElement = node;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.addEventListener = (t, fn) => { (doc.listeners[t] = doc.listeners[t] || []).push(fn); };
  doc.contains = (o) => doc.body.contains(o);
  doc.hasFocus = () => true;
  doc.defaultView = { innerWidth: 1280, innerHeight: 720, addEventListener() {} };
  doc.body = node("body");
  const pop = node("div");
  pop.setAttribute("id", "iteminfo-pop");
  pop.open = false;
  pop.showPopover = () => { pop.open = true; };
  pop.hidePopover = () => { pop.open = false; };
  pop.rect = { top: 0, bottom: 300, left: 0, width: 352, height: 300 };
  ["iteminfo-title", "iteminfo-body", "iteminfo-more", "iteminfo-poe2db"].forEach((id, i) => {
    const c = node(["h2", "div", "p", "a"][i]);
    c.setAttribute("id", id);
    pop.appendChild(c);
  });
  doc.body.appendChild(pop);
  const list = node("ul");
  doc.body.appendChild(list);
  const other = node("p");
  doc.body.appendChild(other);
  doc.list = list; doc.pop = pop; doc.other = other;
  return doc;
}

function fire(doc, type, ev) {
  ev.preventDefault = () => { ev.prevented = true; };
  (doc.listeners[type] || []).forEach((fn) => fn(ev));
}

function texts(n) { return n.children.map((c) => c.textContent); }

const out = {};
const FULL = {
  name: "Mjolner", sources: ["repoe-fork", "path-of-building", "poe.ninja"],
  fields: {
    rarity: "Unique", item_class: "One Hand Mace", release_state: "legacy",
    description: "Right click to use.", flavour: "The hammer sings.",
    icon: "https://web.poecdn.com/x.png",
    market: { value: 2.5, unit: "Divine Orb", divine: 2.5, change_7d: 12.4, listings: 3,
              few: true, league: "Dawn", age_s: 300, credit: "Prices: poe.ninja" },
    where_found: { drops: [{ boss: "Count Geonor", zone: "Ogham Manor", map: false },
                           { boss: "The Arbiter" }], no_longer_obtainable: true }
  }
};
out.full = I.view(FULL, "mjolner");
out.empty = I.view({ name: "Odd Thing", fields: {}, sources: [] }, "odd thing");
out.stack = I.view({ name: "Transmutation Shard", sources: ["repoe-fork"],
  fields: { item_class: "Stackable Currency", stack_size: 20,
            full_stack_turns_into: "Orb of Transmutation" } }, "x");
out.flavourOnly = I.view({ name: "X", sources: ["poe.ninja"], fields: { flavour: "Quiet." } }, "X");
out.marketNoSource = I.view({ name: "M", sources: [], fields: { market: { value: 1, unit: "Exalted Orb" } } }, "M");
out.iconOnly = I.view({ name: "Y", sources: ["poe.ninja"], fields: { icon: "https://a/b.png" } }, "Y");
out.unknownSource = I.view({ name: "Z", sources: [], fields: { where_found: { drops: [{ boss: "B" }] } } }, "Z");
out.below = I.place({ top: 100, bottom: 124, left: 40 }, { width: 352, height: 300 }, { width: 1280, height: 720 });
out.above = I.place({ top: 600, bottom: 624, left: 1200 }, { width: 352, height: 300 }, { width: 1280, height: 720 });
out.neither = I.place({ top: 100, bottom: 124, left: 0 }, { width: 352, height: 700 }, { width: 1280, height: 720 });
out.href = I.poe2dbHref("Orb of Augmentation");

const d0 = makeDoc();
const b = I.button(d0, "Exalted Orb");
out.button = { tag: b.tagName, type: b.type, cls: b.className, text: b.textContent, attrs: b.attrs };
out.parts = I.parts(d0, "You checked Exalted Orb: up 30%", "Exalted Orb").map((p) =>
  p.node ? { node: p.node.textContent } : p);
out.partsNone = I.parts(d0, "No price changes to show yet.", "");
out.partsMissing = I.parts(d0, "Divine Orb: 1", "Chaos Orb");

// prices.js / pricewatch.js rows with their item names
const movers = { web_data: true, movers: { up: [{ name: "Ember Veil", change: 61, value: 0.35, unit: "Divine Orb" }],
  down: [{ change: -20, value: 2, unit: "Divine Orb" }] } };
out.trend = P.trendList(movers);
out.trendRows = P.trendRows(movers);
out.trendEmpty = P.trendList({ web_data: true, movers: { up: [], down: [] } });
out.watch = PW.items({ count: 1, moved: [{ name: "Ember Veil", text: "Ember Veil: up 30%", change_pct: 30 }] });
out.watchQuiet = PW.items({ count: 1, text: "Watching 1 item. No price moved.", moved: [] });

// search.js rowPager takes a ready node as a row part
const d1 = makeDoc();
const pg = S.rowPager(d1, { rows: [{ text: "Exalted Orb: 1", item: "Exalted Orb" }], label: "prices",
  size: { full: 7, compact: 4 }, sizeClass: "full", text: (r) => r.text,
  parts: (r) => I.parts(d1, r.text, r.item), controls: () => [] });
const li = pg.list.children[0];
out.row = { cls: li.className, kids: li.children[0].children.map((c) => [c.tagName, c.textContent]) };

// the popover: open, fill, Escape, outside click, toggle, re-render
(async () => {
  const doc = makeDoc();
  const calls = [];
  let reply = FULL;
  const api = (m, p) => { calls.push([m, p]); return Promise.resolve(reply); };
  out.attached = I.attach(doc, { api });
  const btn = I.button(doc, "Mjolner");
  doc.list.appendChild(btn);
  fire(doc, "click", { target: btn });
  out.openState = { open: doc.pop.open, expanded: btn.getAttribute("aria-expanded"),
    focus: doc.activeElement && doc.activeElement.attrs.id, title: doc.byId["iteminfo-title"].textContent };
  await new Promise((r) => setImmediate(r));
  out.calls = calls.slice();
  const body = doc.byId["iteminfo-body"];
  out.body = body.children.map((c) => [c.tagName, c.className, c.children.length ? texts(c) : c.textContent]);
  out.link = { href: doc.byId["iteminfo-poe2db"].href, label: doc.byId["iteminfo-poe2db"].attrs["aria-label"],
    hidden: doc.byId["iteminfo-poe2db"].hidden };
  out.placed = Object.assign({}, doc.pop.style);
  fire(doc, "keydown", { key: "Escape" });
  out.afterEscape = { open: doc.pop.open, expanded: btn.getAttribute("aria-expanded"),
    focusBack: doc.activeElement === btn, isOpen: I.isOpen() };
  // a click inside keeps it open, a click outside closes it (no focus move)
  fire(doc, "click", { target: btn });
  fire(doc, "click", { target: doc.byId["iteminfo-body"] });
  out.insideKeeps = doc.pop.open;
  doc.activeElement = null;
  fire(doc, "click", { target: doc.other });
  out.outsideCloses = { open: doc.pop.open, focus: doc.activeElement === null };
  // the same button again toggles; a second button moves the one popover
  fire(doc, "click", { target: btn });
  fire(doc, "click", { target: btn });
  out.toggle = doc.pop.open;
  const btn2 = I.button(doc, "Divine Orb");
  doc.list.appendChild(btn2);
  fire(doc, "click", { target: btn });
  fire(doc, "click", { target: btn2 });
  out.one = { open: doc.pop.open, first: btn.getAttribute("aria-expanded"), second: btn2.getAttribute("aria-expanded") };
  // a list re-render takes the button away: sync() closes
  doc.list.removeChild(btn2);
  I.sync();
  out.synced = doc.pop.open;
  // Tab out of the popover closes it; focus inside keeps it
  fire(doc, "click", { target: btn });
  doc.pop.listeners.focusout.forEach((fn) => fn({ relatedTarget: doc.byId["iteminfo-poe2db"] }));
  out.focusInside = doc.pop.open;
  doc.pop.listeners.focusout.forEach((fn) => fn({ relatedTarget: doc.other }));
  out.tabOut = doc.pop.open;
  // an empty reply and a failed read
  reply = { name: "Odd Thing", fields: {}, sources: [] };
  fire(doc, "click", { target: btn });
  await new Promise((r) => setImmediate(r));
  out.emptyBody = body.children.map((c) => c.textContent);
  I.close(false);
  const bad = () => Promise.reject(new Error("HTTP 500"));
  I.attach(doc, { api: bad });
  fire(doc, "click", { target: btn });
  await new Promise((r) => setImmediate(r));
  out.failedBody = body.children.map((c) => c.textContent);
  console.log(JSON.stringify(out));
})();
"""


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    node = _node()
    script = tmp_path_factory.mktemp("iteminfo") / "harness.js"
    script.write_text(HARNESS, encoding="ascii")
    res = subprocess.run([node, str(script), str(srcpaths.WEB)],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_view_orders_fields_and_credits_only_shown_sources(run):
    v = run["full"]
    assert v["name"] == "Mjolner"
    assert v["rows"] == [
        {"label": "Item class", "value": "One Hand Mace"},
        {"label": "Rarity", "value": "Unique"},
        {"label": "Price", "value": "2.5 Divine Orb"},
        {"label": "7-day trend", "value": "up 12.4%"},
        {"label": "Listings", "value": "3 (few listings)"},
        {"label": "Release state", "value": "Legacy"},
    ]
    assert v["texts"] == [{"cls": "iteminfo-desc", "text": "Right click to use."},
                          {"cls": "iteminfo-flavour", "text": "The hammer sings."}]
    assert v["where"] == {"title": "Where found", "rows": [
        "Drops from Count Geonor in Ogham Manor", "Drops from The Arbiter",
        "No longer obtainable"]}
    assert v["credits"] == [
        "Item data: RePoE fork export. Game data (c) Grinding Gear Games",
        "Prices: poe.ninja, Dawn, updated 5 min ago",
        PB_CREDIT,
    ]
    assert v["empty"] is False
    assert v["more"] == {"line": "Drops, vendor and disenchant: see poe2db (community site)",
                         "text": "More on poe2db", "href": "https://poe2db.tw/us/Mjolner",
                         "label": "More on poe2db about Mjolner (opens in a new tab)"}
    # the icon is a web address: never shown, never fetched
    assert "poecdn" not in json.dumps(v)


def test_view_leaves_unknown_out_and_says_so_once(run):
    e = run["empty"]
    assert e["empty"] is True and e["rows"] == [] and e["credits"] == []
    assert e["name"] == "Odd Thing"
    assert run["stack"]["rows"] == [{"label": "Item class", "value": "Stackable Currency"},
                                    {"label": "Full stack",
                                     "value": "20 become 1 Orb of Transmutation"}]
    assert run["flavourOnly"]["credits"] == ["Flavour text: poe.ninja"]
    # an icon alone is nothing shown: no credit, the empty line
    assert run["iconOnly"]["empty"] is True and run["iconOnly"]["credits"] == []
    # a source the reply does not name is never credited
    assert run["unknownSource"]["credits"] == []
    # shown prices always carry their credit
    assert run["marketNoSource"]["credits"] == ["Prices: poe.ninja"]


def test_place_below_flips_above_and_stays_inside(run):
    assert run["below"] == {"top": 128, "left": 40}
    assert run["above"] == {"top": 296, "left": 920}
    assert run["neither"] == {"top": 12, "left": 8}
    assert run["href"] == "https://poe2db.tw/us/Orb_of_Augmentation"


def test_name_button_is_a_link_like_button(run):
    b = run["button"]
    assert b["tag"] == "BUTTON" and b["type"] == "button" and b["text"] == "Exalted Orb"
    assert b["cls"] == "link iteminfo-name"
    assert b["attrs"]["aria-expanded"] == "false"
    assert b["attrs"]["aria-controls"] == "iteminfo-pop"
    assert b["attrs"]["data-item"] == "Exalted Orb"
    assert run["parts"] == [{"text": "You checked "}, {"node": "Exalted Orb"},
                            {"text": ": up 30%"}]
    assert run["partsNone"] == [{"text": "No price changes to show yet."}]
    assert run["partsMissing"] == [{"text": "Divine Orb: 1"}]


def test_price_rows_name_their_items(run):
    assert run["trend"] == [
        {"text": "Ember Veil is rising: up 61% this week (0.35 Divine Orb)", "item": "Ember Veil"},
        {"text": "Unnamed item is falling: down 20% this week (2 Divine Orb)", "item": ""},
    ]
    assert run["trendRows"] == [r["text"] for r in run["trend"]]
    assert run["trendEmpty"][0]["item"] == ""
    assert run["watch"] == [{"text": "You checked Ember Veil: up 30%", "item": "Ember Veil"}]
    assert run["watchQuiet"] == [{"text": "Watching 1 item. No price moved.", "item": ""}]
    assert run["row"]["cls"] == "al-row-ctl"
    assert run["row"]["kids"] == [["BUTTON", "Exalted Orb"], ["SPAN", ": 1"]]


def test_popover_opens_fills_and_closes_by_the_rules(run):
    assert run["attached"] is True
    assert run["openState"] == {"open": True, "expanded": "true", "focus": "iteminfo-title",
                                "title": "Mjolner"}
    assert run["calls"] == [["GET", "/api/iteminfo?name=Mjolner"]]
    tags = [b[0] for b in run["body"]]
    assert tags == ["DL", "P", "P", "H3", "UL", "P", "P", "P"]
    assert run["body"][4][2] == ["Drops from Count Geonor in Ogham Manor",
                                 "Drops from The Arbiter", "No longer obtainable"]
    assert run["body"][-1][2] == PB_CREDIT
    assert run["link"] == {"href": "https://poe2db.tw/us/Mjolner",
                           "label": "More on poe2db about Mjolner (opens in a new tab)",
                           "hidden": False}
    assert run["placed"] == {"top": "128px", "left": "40px"}
    assert run["afterEscape"] == {"open": False, "expanded": "false", "focusBack": True,
                                  "isOpen": False}
    assert run["insideKeeps"] is True
    assert run["outsideCloses"] == {"open": False, "focus": True}
    assert run["toggle"] is False
    assert run["one"] == {"open": True, "first": "false", "second": "true"}
    assert run["synced"] is False
    assert run["focusInside"] is True
    assert run["tabOut"] is False
    assert run["emptyBody"] == ["No saved info for this item yet"]
    assert run["failedBody"] == ["AshLight can't read item info right now. Try again in a moment."]
