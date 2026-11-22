/* HUD-ACT: exact output of the dashboard act times and zone level helpers
   (web/acts.js). The core sends the sentences; these only format.
   PLAY-TD-20A-RUN-GRID (TD-20): the Acts card is a fixed cell of the Run
   grid; its lists page at 10 rows (8 compact), its rarer parts are pages,
   and the game data credit shows on the zone level page whenever the zone
   levels do. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const a = web.load("acts.js");

const HTML = web.source("index.html");
const CSS = web.source("app.css");

const CREDIT = "Zone levels: RePoE fork export, downloaded when AshLight was built. Game data (c) Grinding Gear Games.";
const ACTS = {
  splits: [
    { key: "G1", label: "Act 1", started_at: 100, ended_at: 1300, current: false, partial: true },
    { key: "G2", label: "Act 2", started_at: 1300, ended_at: null, current: true, partial: false }
  ],
  zones: [
    { name: "Vastiri Outskirts", level: 16, town: false, here: true },
    { name: "Ardura Caravan", level: 16, town: true, here: false }
  ],
  current: "G2",
  zones_act: "Act 2",
  levels: true,
  source: CREDIT,
  empty_text: "No act times yet. They start by themselves when you enter a campaign zone.",
  no_levels_text: "Zone levels aren't downloaded yet. AshLight fetches them by itself while \"Use web data\" is ticked under Settings, Reading and web data.",
  no_zones_text: "Zone levels show here while you are in a campaign act.",
  partial_text: "partial: counted from the first zone AshLight saw"
};
const HIST = { on: true, best: [
  { key: "G1", label: "Act 1", best_s: 1100, best_text: "18:20", delta_s: 100 },
  { key: "G2", label: "Act 2", best_s: 2900, best_text: "48:20", delta_s: null }] };

test("duration matches the zone timer form", () => {
  assert.equal(a.duration(0), "0:00");
  assert.equal(a.duration(59.9), "0:59");
  assert.equal(a.duration(1200), "20:00");
  assert.equal(a.duration(3725), "1:02:05");
  assert.equal(a.duration(-5), "0:00");
  assert.equal(a.duration(null), "--:--");
  assert.equal(a.duration(NaN), "--:--");
});

test("splitRows: closed and open splits, exact", () => {
  assert.deepEqual(a.splitRows(ACTS, 4900), [
    { key: "G1", label: "Act 1", note: "partial", time: "20:00", total: "20:00", current: false },
    { key: "G2", label: "Act 2", note: "", time: "1:00:00", total: "1:20:00", current: true }
  ]);
  assert.deepEqual(a.splitRows(null, 1), []);
  assert.deepEqual(a.splitRows({ splits: [] }, 1), []);
});

test("bestByKey, actLine and actText: act, time in act, run total, your best", () => {
  const best = a.bestByKey(HIST);
  assert.deepEqual(best, { G1: "18:20", G2: "48:20" });
  assert.deepEqual(a.bestByKey(null), {});
  assert.deepEqual(a.bestByKey({ best: [{ key: "G3", best_s: 65 }, { label: "x" }] }), { G3: "1:05" });
  const rows = a.splitRows(ACTS, 4900);
  const note = a.partialNote(ACTS);
  // the list line puts the key facts first and stays short (no tail loss)
  assert.equal(a.actLine(rows[0], best), "Act 1 (partial): 20:00, total 20:00, best 18:20");
  assert.equal(a.actLine(rows[1], best), "Act 2 (now): 1:00:00, total 1:20:00, best 48:20");
  assert.equal(a.actLine(rows[1], {}), "Act 2 (now): 1:00:00, total 1:20:00");
  // the whole text adds the partial reason (title and Full text page)
  assert.equal(a.actText(rows[0], best, note),
    "Act 1 (partial): 20:00, total 20:00, best 18:20. " +
    "Partial: counted from the first zone AshLight saw.");
  assert.equal(a.actText(rows[1], best, note), "Act 2 (now): 1:00:00, total 1:20:00, best 48:20");
  // a typical act line fits the narrowest cockpit cell (about 37 characters)
  assert.ok(a.actLine({ label: "Act 4", note: "", time: "42:10", total: "2:41:05", key: "G4",
    current: true }, { G4: "39:55" }).length <= 45);
});

test("zoneRows, zoneText, zonesTitle and zonesEmpty, exact", () => {
  assert.deepEqual(a.zoneRows(ACTS), [
    { name: "Vastiri Outskirts", level: "16", note: "you are here", here: true },
    { name: "Ardura Caravan", level: "16", note: "town", here: false }
  ]);
  assert.deepEqual(a.zoneRows(ACTS).map(a.zoneText), [
    "Vastiri Outskirts: level 16 (you are here)", "Ardura Caravan: level 16 (town)"]);
  assert.equal(a.zonesTitle(ACTS), "Zone levels in Act 2");
  assert.equal(a.zonesTitle({}), "Zone levels");
  assert.equal(a.zonesEmpty(ACTS), "");
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { levels: false, zones: [], current: null })),
    "Zone levels show here while you are in a campaign act.");
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { levels: false, zones: [] })),
    "Zone levels aren't downloaded yet. AshLight fetches them by itself while \"Use web data\" is ticked under Settings, Reading and web data.");
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { zones: [] })),
    "Zone levels show here while you are in a campaign act.");
  assert.equal(a.zonesEmpty(null), "");
  // UTIL-1.0-FIXTURES: in an act the downloaded table lacks
  // same text as server/al/acts.py ACT_NO_LEVELS_TEXT (tests/test_util_10_fixtures.py)
  const lacks = "Zone levels for Act 5 aren't downloaded yet. They show here once the " +
    "game data has them. AshLight fetches newer game data by itself, at most once a " +
    "day, while web data is on.";
  assert.equal(a.zonesEmpty(Object.assign({}, ACTS, { zones: [], act_levels_text: lacks })), lacks);
});

test("partialNote: one sentence only when a row is partial (UX-NEW-CARDS)", () => {
  assert.equal(a.partialNote(null), "");
  assert.equal(a.partialNote(Object.assign({}, ACTS, { splits: [{ partial: false }] })), "");
  assert.equal(a.partialNote(ACTS), "Partial: counted from the first zone AshLight saw.");
});

/* ---- a small fake DOM: enough for the card pages and the pagers -------- */
function matches(n, sel) {
  let m;
  if ((m = /^\[([\w-]+)="([^"]*)"\]$/.exec(sel))) { return n.attrs[m[1]] === m[2]; }
  if ((m = /^\[([\w-]+)\]$/.exec(sel))) { return m[1] in n.attrs; }
  if (sel.charAt(0) === ".") { return n.className.split(/\s+/).includes(sel.slice(1)); }
  return n.tagName === sel.toUpperCase();
}

function fakeDoc(size) {
  const doc = { activeElement: null, els: {} };
  doc.createElement = (tag) => {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], parentNode: null,
      attrs: {}, listeners: {}, _text: "", value: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
      replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.els[v] = this; } },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      hasAttribute(k) { return k in this.attrs; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
      contains(x) { return x === this || this.walk().includes(x); },
      walk(out) {
        out = out || [];
        this.children.forEach((c) => { out.push(c); if (c.walk) { c.walk(out); } });
        return out;
      },
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
      querySelectorAll(sel) { return this.walk().filter((c) => matches(c, sel)); },
      focus() { doc.activeElement = this; }
    };
    return n;
  };
  doc.getElementById = (id) => doc.els[id] || null;
  doc.defaultView = { getComputedStyle: () => ({ getPropertyValue: () => size || "full" }) };
  return doc;
}

/* el("div", {id, class, ...attrs}, children) */
function mk(doc, tag, attrs, kids) {
  const n = doc.createElement(tag);
  Object.keys(attrs || {}).forEach((k) => {
    if (k === "class") { n.className = attrs[k]; } else if (k === "hidden") { n.hidden = !!attrs[k]; } else {
      n.setAttribute(k, attrs[k]);
    }
  });
  (kids || []).forEach((k) => n.appendChild(k));
  return n;
}

/* The Acts card as web/index.html builds it (ids, pages, buttons). */
function actsCard(size) {
  const d = fakeDoc(size);
  const page = (name, label, kids) => mk(d, "div", { class: "card-page", "data-page": name,
    "data-label": label, hidden: name !== "main" }, kids);
  const box = mk(d, "section", { id: "actsbox", class: "card acts grid-card", "data-home": "main" }, [
    mk(d, "div", { class: "card-head" }, [
      mk(d, "h2", { id: "acts-title" }), mk(d, "span", { class: "card-sub", "data-card-sub": "" }),
      mk(d, "button", { class: "card-back", "data-card-back": "", hidden: true })]),
    page("main", "", [mk(d, "p", { id: "acts-empty" }), mk(d, "div", { id: "acts-rows", hidden: true }),
      mk(d, "div", { class: "card-foot" }, [
        mk(d, "button", { "data-card-open": "zones", id: "open-zones" }),
        mk(d, "button", { "data-card-open": "pace", id: "open-pace" }),
        mk(d, "button", { "data-card-open": "guide", id: "open-guide" })])]),
    page("zones", "Zone levels", [mk(d, "p", { id: "zones-empty" }), mk(d, "div", { id: "zones-rows", hidden: true }),
      mk(d, "p", { id: "zones-source", hidden: true })]),
    page("pace", "Levelling pace", [mk(d, "p", { id: "pace" }), mk(d, "select", { id: "char-pick" })]),
    page("guide", "Zone guide", [mk(d, "div", { id: "zone-guide" })])
  ]);
  box.querySelector("h2").textContent = "Acts";
  return d;
}

const listOf = (d, id) => d.getElementById(id).children[0].children[0]; // host > ul
const texts = (ul) => ul.children.map((li) => li.textContent);
const pageShown = (d) => d.getElementById("actsbox").querySelectorAll(".card-page")
  .filter((p) => !p.hidden).map((p) => p.getAttribute("data-page"));

test("paint: act rows with your best, live tick, empty sentence in place of the list", () => {
  const d = actsCard();
  a.paint(d, ACTS, 4900, true, HIST);
  assert.deepEqual(texts(listOf(d, "acts-rows")), [
    "Act 1 (partial): 20:00, total 20:00, best 18:20",
    "Act 2 (now): 1:00:00, total 1:20:00, best 48:20"]);
  assert.equal(d.getElementById("acts-rows").hidden, false);
  assert.equal(d.getElementById("acts-empty").hidden, true);
  // a row is one line: the whole text rides in title (web/pager.js rowRule)
  assert.equal(listOf(d, "acts-rows").children[0].children[0].getAttribute("title"),
    "Act 1 (partial): 20:00, total 20:00, best 18:20. Partial: counted from the first zone AshLight saw.");
  // and on the Full text page
  d.getElementById("acts-rows").children[0].children[1].children[3].click();
  assert.match(listOf(d, "acts-rows").children[0].textContent, /Partial: counted from/);
  d.getElementById("acts-rows").children[0].children[1].children[3].click();
  // the 1 s tick moves the open act and keeps your best
  a.paint(d, ACTS, 4960, false);
  assert.equal(texts(listOf(d, "acts-rows"))[1], "Act 2 (now): 1:01:00, total 1:21:00, best 48:20");
  // no splits: the list hides and the core's sentence shows
  a.paint(d, Object.assign({}, ACTS, { splits: [] }), 1, true, null);
  assert.equal(d.getElementById("acts-rows").hidden, true);
  assert.equal(d.getElementById("acts-empty").hidden, false);
  assert.equal(d.getElementById("acts-empty").textContent, ACTS.empty_text);
});

test("the act list pages at 10 rows, 8 in the compact class, and never grows", () => {
  const many = { splits: [] };
  for (let i = 0; i < 13; i += 1) {
    many.splits.push({ key: "G" + i, label: "Act " + i, started_at: i * 100, ended_at: (i + 1) * 100,
      current: false, partial: false });
  }
  const full = actsCard("full");
  a.paint(full, many, 2000, true, null);
  const host = full.getElementById("acts-rows").children[0];
  assert.equal(listOf(full, "acts-rows").children.length, 10);
  assert.equal(host.children[1].children[0].textContent, "1-10 of 13");
  const compact = actsCard("compact");
  a.paint(compact, many, 2000, true, null);
  assert.equal(listOf(compact, "acts-rows").children.length, 8);
  // a data change keeps the page the player turned to
  const next = compact.getElementById("acts-rows").children[0].children[1].children[2];
  next.click();
  assert.equal(listOf(compact, "acts-rows").children[0].textContent.slice(0, 7), "Act 8: ");
  a.paint(compact, many, 2001, true, null);
  assert.equal(listOf(compact, "acts-rows").children[0].textContent.slice(0, 7), "Act 8: ");
});

test("zone level page: rows, its label, and the credit line (never cut) whenever zone levels show", () => {
  const d = actsCard();
  a.paint(d, ACTS, 4900, true, null);
  assert.deepEqual(texts(listOf(d, "zones-rows")),
    ["Vastiri Outskirts: level 16 (you are here)", "Ardura Caravan: level 16 (town)"]);
  const src = d.getElementById("zones-source");
  assert.equal(src.hidden, false);
  assert.equal(src.textContent, CREDIT);
  assert.equal(src.getAttribute("title"), CREDIT);
  assert.equal(d.getElementById("zones-empty").hidden, true);
  // two lines of credit under the list: 9 zones a page (8 compact)
  assert.deepEqual(a.ZONE_ROWS, { full: 9, compact: 8 });
  const many = Object.assign({}, ACTS, { zones: [] });
  for (let i = 0; i < 12; i += 1) { many.zones.push({ name: "Zone " + i, level: 10 + i }); }
  const big = actsCard("full");
  a.paint(big, many, 4900, true, null);
  assert.equal(listOf(big, "zones-rows").children.length, 9);
  const zones = d.getElementById("actsbox").querySelector('[data-page="zones"]');
  assert.equal(zones.getAttribute("data-label"), "Zone levels in Act 2");
  // no zone levels on this computer: the download hint, no credit
  a.paint(d, Object.assign({}, ACTS, { zones: [], levels: false, source: null }), 4900, true, null);
  assert.equal(d.getElementById("zones-rows").hidden, true);
  assert.equal(d.getElementById("zones-empty").textContent, ACTS.no_levels_text);
  assert.equal(src.hidden, true);
  assert.equal(src.getAttribute("title"), null);
});

test("card pages: a press opens a page, Back returns home and to the opener", () => {
  const d = actsCard();
  a.paint(d, ACTS, 4900, true, null);
  assert.deepEqual(pageShown(d), ["main"]);
  const back = d.getElementById("actsbox").querySelector("[data-card-back]");
  assert.equal(back.hidden, true);
  d.getElementById("open-zones").click();
  assert.deepEqual(pageShown(d), ["zones"]);
  assert.equal(back.hidden, false);
  assert.equal(d.activeElement, back);
  const sub = d.getElementById("actsbox").querySelector("[data-card-sub]");
  assert.equal(sub.textContent, "Zone levels in Act 2");
  // a new act renames the shown page's label in place
  a.paint(d, Object.assign({}, ACTS, { zones_act: "Act 3" }), 4900, true, null);
  assert.equal(sub.textContent, "Zone levels in Act 3");
  assert.deepEqual(pageShown(d), ["zones"]); // a data change never turns a page
  back.click();
  assert.deepEqual(pageShown(d), ["main"]);
  assert.equal(d.activeElement, d.getElementById("open-zones"));
  assert.equal(back.getAttribute("aria-label"), "Back to the first page of Acts");
  // wired once: a second full paint adds no second listener
  d.getElementById("open-pace").click();
  assert.equal(d.getElementById("open-pace").listeners.click.length, 1);
  assert.deepEqual(pageShown(d), ["pace"]);
});

/* ---- the markup and the stylesheet ------------------------------------ */
const run = HTML.slice(HTML.indexOf('id="panel-run"'), HTML.indexOf('id="panel-settings"'));
const sectionOf = (id) => {
  const at = run.indexOf('id="' + id + '"');
  return run.slice(at, run.indexOf("</section>", at));
};

test("Run is a card grid; Acts, Maps and Deaths are its card cells, no tables inside", () => {
  assert.match(run, /^id="panel-run" class="panel panel-grid panel-cards"/);
  ["actsbox", "mapsbox", "deathsbox"].forEach((id) => {
    // one card per column: the column holds only this card
    assert.match(run, new RegExp('<div class="col">\\s*(<!--[\\s\\S]*?-->\\s*)?<section id="' + id +
      '" class="card [a-z ]*grid-card"[^>]*data-home="main">'), id);
    const box = sectionOf(id);
    assert.ok(box.includes('class="card-head"') && box.includes("data-card-back"), id);
    assert.ok(!/<table|<details/.test(box), id + ": a list pages, a fold never grows a card");
  });
  // Run history is a page of the Last session card
  assert.match(sectionOf("summarybox"), /id="historybox" class="card-page" data-page="history"/);
  const order = ["summarybox", "historybox", "actsbox", "mapsbox", "deathsbox", "events-title", "charsbox"]
    .map((id) => run.indexOf('id="' + id + '"'));
  assert.deepEqual(order.slice().sort((x, y) => x - y), order);
  assert.equal((run.match(/<div class="col">/g) || []).length, 6);
});

test("the Acts card: rows, zone levels with the credit, pace and guide pages", () => {
  const box = sectionOf("actsbox");
  assert.match(box, /<h2 id="acts-title" tabindex="-1">Acts<\/h2>/);
  ["zones", "pace", "guide"].forEach((p) => {
    assert.ok(box.includes('data-card-open="' + p + '"'), p);
    assert.ok(box.includes('data-page="' + p + '"'), p);
  });
  const zones = box.slice(box.indexOf('data-page="zones"'), box.indexOf('data-page="pace"'));
  assert.ok(zones.includes('id="zones-rows" class="pager-slot"'));
  // the credit wraps (no .one-line): it is never cut
  assert.ok(zones.includes('id="zones-source" class="row-meta muted zones-credit"'));
  assert.ok(box.includes('id="acts-rows" class="pager-slot"'));
  // the pace line and the zone guide stay inside the card; the picker moved
  // to the Characters card
  ["pace", "zone-guide"].forEach((id) => assert.ok(box.includes('id="' + id + '"'), id));
  assert.ok(!box.includes('id="char-pick-box"'));
  assert.ok(sectionOf("charsbox").includes('id="char-pick-box"'));
});

test("the card rows fit: two 24 px button rows in the Run cards, pages that wait say so", () => {
  assert.match(CSS, /\.panel-cards > \.col:has\(> \.grid-card\) \{ max-height: none; overflow: visible;/);
  assert.match(CSS, /#panel-run \.grid-card \.al-pager, #panel-run \.grid-card \.card-foot \{ min-height: 1\.5rem; \}/);
  assert.match(CSS, /#pace:not\(\[hidden\]\) ~ \.pace-none, #zone-guide:not\(\[hidden\]\) \+ \.guide-none \{ display: none; \}/);
  assert.match(CSS, /\.panel-cards \{ align-items: stretch; grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);\s*grid-template-rows: repeat\(2, minmax\(0, 1fr\)\);/);
});
