/* PLAY-TD-21A-SETTINGS-RAIL (TD-21, F-067; plan 03 section 4): the
   Settings rail in web/rail.js. Settings is a rail of 6 section buttons
   and a pane that shows ONE section; a section holds at most 448 px of
   rows (its .rail-block children page beyond that); the bar status word
   leads to "Stop reading Client.txt" in 2 clicks from any tab; Checks
   shows by itself. The markup and the wiring are read as text. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const web = require("./_web.js");
const R = web.load("rail.js");
const SRC = web.source("rail.js");
const HTML = web.source("index.html");
const CSS = web.source("app.css");
const APP = web.source("app.js");

/* ---- a small fake DOM: ids, parents, hidden, attributes, focus ---- */
function makeDoc() {
  const ids = {};
  const doc = { activeElement: null, ids };
  function el(tag, id, opts) {
    const o = opts || {};
    const n = {
      tagName: tag, id: id || "", children: [], attrs: {}, hidden: !!o.hidden,
      className: o.className || "", parentNode: null, listeners: {},
      offsetHeight: o.h || 0, scrollHeight: o.h || 0, _t: "",
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); if (c.id) { ids[c.id] = c; } return c; },
      addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
      click() { (this.listeners.click || []).forEach((f) => f()); },
      contains(x) { for (let m = x; m; m = m.parentNode) { if (m === this) { return true; } } return false; },
      focus() { doc.activeElement = this; }
    };
    Object.defineProperty(n, "textContent", {
      get() { return this._t; },
      set(v) { this._t = String(v); }
    });
    if (id) { ids[id] = n; }
    return n;
  }
  doc.el = el;
  doc.getElementById = (id) => ids[id] || null;
  doc.createElement = (t) => el(t);
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return Object.values(ids).filter((n) => m && n.getAttribute(m[1]) !== null);
  };
  return doc;
}

/* The Settings panel as web/index.html lays it out: 6 rail buttons, 4
   sections (4 to 6 share #toolsbox), blocks with heights (px). */
function settingsDoc(heights) {
  const doc = makeDoc();
  const h = Object.assign({ checks: [380, 260, 240], "set-reading": [180, 160],
                            "set-overlay": [220, 200], toolsbox: [160, 90] }, heights || {});
  const body = doc.el("body", "body");
  const panel = body.appendChild(doc.el("div", "panel-settings", { hidden: true }));
  const rail = panel.appendChild(doc.el("div", "rail"));
  R.RAIL.forEach(([b, s]) => {
    const btn = rail.appendChild(doc.el("button", b));
    btn.setAttribute("aria-controls", s);
  });
  const pane = panel.appendChild(doc.el("div", "pane"));
  Object.keys(h).forEach((sid) => {
    const sec = pane.appendChild(doc.el("section", sid, { hidden: sid !== "checks" }));
    sec.setAttribute("aria-labelledby", sid + "-h");
    const head = sec.appendChild(doc.el("h3", sid + "-h"));
    head.textContent = sid;
    h[sid].forEach((px, i) => {
      const b = sec.appendChild(doc.el("div", sid + "-b" + i, { className: "rail-block", h: px }));
      b.appendChild(doc.el("button", sid + "-ctl" + i));
    });
  });
  // the targets the jumps name, inside their blocks
  doc.ids["set-reading-b0"].appendChild(doc.el("button", "consent-no"));
  doc.ids["set-reading-b1"].appendChild(doc.el("input", "webdata-on"));
  doc.ids["set-overlay-b1"].appendChild(doc.el("input", "hotkey-eval"));
  doc.ids["checks-b0"].appendChild(doc.el("p", "checks-summary"));
  doc.ids["reading-title"] = doc.ids["set-reading-h"];
  doc.ids["set-reading-h"].id = "reading-title";
  const header = body.appendChild(doc.el("header", "header"));
  header.appendChild(doc.el("button", "reading"));
  const jumpBtn = doc.ids["checks-b0"].appendChild(doc.el("button", "to-web"));
  jumpBtn.setAttribute("data-jump", "webdata-on");
  return doc;
}

function fakeTabs(doc) {
  const calls = [];
  return {
    calls,
    show(d, id, focus) { calls.push([id, focus]); doc.ids["panel-settings"].hidden = id !== "settings"; return id; }
  };
}

const SECTIONS = ["checks", "set-reading", "set-overlay", "toolsbox"];
const shown = (doc) => SECTIONS.filter((s) => !doc.ids[s].hidden);
const current = (doc) => R.RAIL.map((r) => r[0]).filter((b) => doc.ids[b].getAttribute("aria-current") === "true");

test("pack: blocks in DOM order, at most 448 px a page, a tall block alone", () => {
  assert.equal(R.MAX_PX, 448);
  assert.deepEqual(R.pack([100, 200, 148], 448), [[0, 1, 2]]);
  assert.deepEqual(R.pack([300, 200, 100], 448), [[0], [1, 2]]);
  assert.deepEqual(R.pack([500, 100], 448), [[0], [1]], "a block over the cap is a page alone");
  assert.deepEqual(R.pack([300, 0, 200], 448), [[0, 1], [2]], "a hidden block joins its page");
  assert.deepEqual(R.pack([], 448), [[]]);
  assert.deepEqual(R.pack([0, 0]), [[0, 1]]);
  for (const hs of [[120, 330, 10, 448, 90, 300], [447, 2, 1], [32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32]]) {
    for (const page of R.pack(hs, 448)) {
      const sum = page.reduce((a, i) => a + hs[i], 0);
      assert.ok(sum <= 448 || page.length === 1, JSON.stringify([hs, page]));
    }
  }
  assert.equal(R.pageOf([[0], [1, 2]], 2), 1);
  assert.equal(R.pageOf([[0]], 7), 0);
});

test("the rail lists 6 sections and shows one; a press switches it", () => {
  const doc = settingsDoc();
  R.start(doc, { tabs: fakeTabs(doc) });
  assert.equal(R.RAIL.length, 6);
  assert.deepEqual(shown(doc), ["checks"], "Checks shows at load");
  assert.deepEqual(current(doc), ["rail-checks"]);
  for (const [b, s] of R.RAIL) {
    doc.ids[b].focus();
    doc.ids[b].click();
    assert.deepEqual(shown(doc), [s], b);
    assert.deepEqual(current(doc), [b], "one aria-current, the pressed one");
    assert.equal(doc.activeElement, doc.ids[b], "focus stays on the pressed button");
    assert.equal(R.current(), s);
  }
});

test("Checks shows by itself: the open accessor, and never over the player's focus", () => {
  const doc = settingsDoc();
  R.start(doc, { tabs: fakeTabs(doc) });
  const checks = doc.ids.checks;
  assert.equal(checks.open, true);
  doc.ids["rail-overlay"].click();
  assert.equal(checks.open, false);
  checks.open = true; // web/checks.js on a new failure; notice.js / setupcard.js "Open Checks"
  assert.deepEqual(shown(doc), ["checks"]);
  assert.deepEqual(current(doc), ["rail-checks"]);
  checks.open = false; // nothing closes a section
  assert.deepEqual(shown(doc), ["checks"]);
  // the player works in Overlay: a new failure does not swap it away
  doc.ids["rail-overlay"].click();
  doc.ids["set-overlay-ctl0"].focus();
  checks.open = true;
  assert.deepEqual(shown(doc), ["set-overlay"]);
  // focus elsewhere (Play's "Open Checks" button): it shows
  doc.activeElement = doc.ids.reading;
  checks.open = true;
  assert.deepEqual(shown(doc), ["checks"]);
  // a plain `open` set before start() is kept
  const d2 = settingsDoc();
  d2.ids.checks.open = true;
  R.start(d2, { tabs: fakeTabs(d2) });
  assert.equal(d2.ids.checks.open, true);
});

test("the bar status word: Settings, Reading and web data, focus on Stop reading Client.txt", () => {
  const doc = settingsDoc();
  const tabs = fakeTabs(doc);
  R.start(doc, { tabs });
  // from any tab: one press of the word
  doc.ids.reading.focus();
  doc.ids.reading.click();
  assert.deepEqual(tabs.calls.at(-1), ["settings", false]);
  assert.equal(doc.ids["panel-settings"].hidden, false);
  assert.deepEqual(shown(doc), ["set-reading"]);
  assert.deepEqual(current(doc), ["rail-reading"]);
  assert.equal(doc.activeElement, doc.ids["consent-no"], "the second click is the opt-out");
  // not reading: the opt-out is hidden, the section heading takes the focus
  doc.ids["rail-checks"].click();
  doc.ids["consent-no"].hidden = true;
  doc.ids.reading.click();
  assert.deepEqual(shown(doc), ["set-reading"]);
  assert.equal(doc.activeElement, doc.ids["reading-title"]);
  assert.equal(R.STOP, "consent-no");
  assert.equal(R.READING_HEAD, "reading-title");
});

test("jump and focus: data-jump buttons and the page holding the target", () => {
  const doc = settingsDoc({ "set-overlay": [300, 260] });
  R.start(doc, { tabs: fakeTabs(doc) });
  doc.ids["to-web"].click();
  assert.deepEqual(shown(doc), ["set-reading"]);
  assert.equal(doc.activeElement, doc.ids["webdata-on"]);
  // the key fields sit on page 2 of Overlay (300 + 260 > 448)
  assert.equal(R.jump(doc, "hotkey-eval"), doc.ids["hotkey-eval"]);
  assert.deepEqual(shown(doc), ["set-overlay"]);
  assert.equal(doc.ids["set-overlay-b0"].getAttribute("data-off"), "true");
  assert.equal(doc.ids["set-overlay-b1"].getAttribute("data-off"), null);
  assert.equal(doc.activeElement, doc.ids["hotkey-eval"]);
  assert.equal(R.jump(doc, "no-such-id"), null);
});

test("pager: a section over 448 px pages; Prev / Next only on a press; ends do nothing", () => {
  const doc = settingsDoc();
  R.start(doc, { tabs: fakeTabs(doc) });
  // Checks: rows 380, Tried in game 260, report 240 -> [rows], [tried], [report]
  const off = () => [0, 1, 2].map((i) => doc.ids["checks-b" + i].getAttribute("data-off"));
  assert.deepEqual(off(), [null, "true", "true"], "page 1 holds the rows");
  const bar = doc.ids.checks.children.find((c) => /rail-pager/.test(c.className));
  assert.ok(bar && !bar.hidden);
  const [count, prev, next] = bar.children;
  assert.equal(count.textContent, "Page 1 of 3");
  assert.equal(prev.getAttribute("aria-disabled"), "true");
  assert.equal(prev.getAttribute("aria-label"), "Previous page of checks");
  prev.click();
  assert.equal(count.textContent, "Page 1 of 3");
  next.click();
  assert.deepEqual(off(), ["true", null, "true"]);
  next.click();
  assert.deepEqual(off(), ["true", "true", null]);
  assert.equal(next.getAttribute("aria-disabled"), "true");
  next.click();
  assert.equal(count.textContent, "Page 3 of 3");
  assert.equal(bar.children[2], next, "the pressed button is never re-created");
  // shown pages hold at most 448 px
  const pages = R._state.pages.checks;
  for (const page of pages) {
    assert.ok(page.reduce((a, i) => a + doc.ids["checks-b" + i].offsetHeight, 0) <= 448);
  }
  // a block that grows pages the section again, keeping the shown page
  doc.ids["checks-b2"].scrollHeight = 100;
  doc.ids["checks-b2"].offsetHeight = 100;
  R.repage(doc, "checks");
  assert.equal(count.textContent, "Page 2 of 2");
  assert.deepEqual(off(), ["true", null, null]);
  // a section that fits shows no pager
  doc.ids["rail-reading"].click();
  assert.ok(!doc.ids["set-reading"].children.some((c) => /rail-pager/.test(c.className) && !c.hidden));
  assert.deepEqual([0, 1].map((i) => doc.ids["set-reading-b" + i].getAttribute("data-off")), [null, null]);
  // "Open Checks" lands on the rows page
  doc.ids.checks.open = true;
  assert.equal(doc.ids["checks-b0"].getAttribute("data-off"), null);
});

test("a ResizeObserver, when the page has one, pages the shown section again", () => {
  const doc = settingsDoc();
  let fire = null;
  const seen = [];
  class RO {
    constructor(f) { fire = f; }
    observe(n) { seen.push(n.id); }
  }
  R.start(doc, { tabs: fakeTabs(doc), observe: RO });
  assert.ok(seen.includes("checks-b0") && seen.includes("toolsbox-b1"));
  doc.ids["checks-b0"].scrollHeight = 40;
  doc.ids["checks-b0"].offsetHeight = 40;
  fire();
  assert.deepEqual(R._state.pages.checks, [[0, 1], [2]]);
});

/* ---- the markup, the stylesheet and the wiring ---- */

test("markup: the rail, its 6 names in order, 4 sections, one shown at load", () => {
  const panel = HTML.slice(HTML.indexOf('<div id="panel-settings"'), HTML.indexOf("</main>"));
  assert.match(panel, /^<div id="panel-settings" class="panel panel-settings" role="tabpanel"/);
  const rail = [...panel.matchAll(/<button id="(rail-[a-z]+)" class="rail-item" type="button" aria-controls="([a-z-]+)"( aria-current="true")?>([^<]+)<\/button>/g)];
  assert.deepEqual(rail.map((m) => [m[1], m[2], m[4]]),
    R.RAIL.map(([b, s], i) => [b, s, ["Checks", "Reading and web data", "Overlay", "Keys",
      "Appearance and tools", "About and data"][i]]));
  assert.deepEqual(rail.filter((m) => m[3]).map((m) => m[1]), ["rail-checks"]);
  assert.ok(!/role="tab"/.test(panel), "exactly 4 role=tab in the page: the rail is buttons (G12)");
  const secs = [...panel.matchAll(/<section id="([a-z-]+)" class="card rail-section[^"]*"[^>]*?( hidden)?>/g)];
  assert.deepEqual(secs.map((m) => m[1]), SECTIONS);
  assert.deepEqual(secs.filter((m) => !m[2]).map((m) => m[1]), ["checks"]);
  // Reading and web data holds the opt-out, the log path, the ledger line,
  // the one web data switch (default OFF) and the price book state
  const reading = panel.slice(panel.indexOf('<section id="set-reading"'), panel.indexOf('<section id="set-overlay"'));
  for (const id of ["reading-title", "reading-state", "reading-path", "consent-no", "consent-said",
    "ledger-line", "webdata-on", "webdata-status", "webdata-sentence", "book-state"]) {
    assert.ok(reading.includes('id="' + id + '"'), id);
  }
  assert.match(reading, /<h3 id="reading-title" tabindex="-1">Reading and web data<\/h3>/);
  assert.match(reading, /<input id="webdata-on" type="checkbox">/, "never pre-ticked (decision 0013)");
  assert.match(reading, /<button id="consent-no" type="button" class="secondary" hidden\s+aria-describedby="consent-said">Stop reading Client\.txt<\/button>/);
  // the Prices card keeps a jump to the switch, not a second switch
  const prices = HTML.slice(HTML.indexOf('<section id="pricesbox"'), HTML.indexOf("</section>", HTML.indexOf('<section id="pricesbox"')));
  assert.ok(!prices.includes('id="webdata-on"') && !prices.includes('data-page="web"'));
  assert.match(prices, /data-jump="webdata-on" aria-describedby="reading-to">Web data<\/button>/);
  // Checks: the rows block first, then Tried in game, then the report
  const checks = panel.slice(panel.indexOf('<section id="checks"'), panel.indexOf('<section id="set-reading"'));
  const order = ["checks-summary", "checks-list", "checks-pager", "verdicts", "checks-copy", "checks-preview-box", "checks-said"]
    .map((id) => checks.indexOf('id="' + id + '"'));
  assert.ok(order.every((x, i) => x > 0 && (i === 0 || x > order[i - 1])), JSON.stringify(order));
  assert.equal((checks.match(/class="rail-block"/g) || []).length, 3);
  assert.ok(!checks.includes("<details"), "rows page, no fold");
  // the script loads before app.js
  assert.equal(HTML.split('src="/web/rail.js"').length - 1, 1);
  assert.ok(HTML.indexOf("/web/rail.js") < HTML.indexOf("/web/app.js"));
});

test("the bar status word is a 32 px button and stays the polite reading indicator", () => {
  const head = HTML.slice(HTML.indexOf("<header"), HTML.indexOf("</header>"));
  assert.match(head, /<button id="reading" class="pill bar-word" type="button" data-state="pending" aria-live="polite"\s+aria-describedby="reading-to">\s*<span class="glyph" aria-hidden="true">\[ \]<\/span>\s*<span class="word">connecting<\/span>\s*<\/button>/);
  assert.match(head, /<span id="reading-to" hidden>Opens Reading and web data in Settings\.<\/span>/);
  assert.ok(!/<button id="reading"[^>]*role=/.test(head), "a button keeps its own role");
  assert.match(CSS, /button\.bar-word \{ min-height: 32px;/);
  assert.match(CSS, /\.bar > #reading \{ grid-area: status;/);
  // the footer keeps the disclaimer and loses the opt-out
  const foot = HTML.slice(HTML.indexOf("<footer"), HTML.indexOf("</footer>"));
  assert.ok(foot.includes("This product isn't affiliated with or endorsed by Grinding Gear Games in any way."));
  assert.ok(!foot.includes('id="consent-no"') && !foot.includes('id="ledger-line"'));
});

test("stylesheet: a 220 px rail, one rule folds off-page blocks, no motion", () => {
  assert.match(CSS, /\.panel-settings \{ grid-template-columns: 220px minmax\(0, 1fr\); \}/);
  assert.match(CSS, /\.rail-block\[data-off\] \{ height: 0; margin: 0; padding: 0; overflow: hidden; visibility: hidden; \}/);
  assert.match(CSS, /button\.rail-item\[aria-current="true"\] \{ border-left-color: var\(--fk-accent\); font-weight: 600; \}/);
  assert.match(CSS, /button\.rail-item \{[^}]*min-height: 32px;/);
  const rail = CSS.slice(CSS.indexOf("PLAY-TD-21A-SETTINGS-RAIL (TD-21, F-067"), CSS.indexOf("@media (min-width: 900px) {\n  .panel-settings"));
  assert.ok(!/transition|animation/.test(rail));
});

test("app.js starts the rail once, from start(), before the first push", () => {
  const start = APP.slice(APP.indexOf("  function start() {"), APP.indexOf("\n  }\n", APP.indexOf("  function start() {")));
  assert.equal(APP.split("window.ALRail.start(").length - 1, 1);
  assert.ok(start.indexOf("window.ALRail.start(document") > start.indexOf("A.start();"));
  assert.ok(start.indexOf("window.ALRail.start(document") < start.indexOf("connect();"));
  assert.match(start, /tabs: window\.ALTabs \|\| null/);
});

test("readingView: the reading state, the log path and the opt-out", () => {
  const m = /\/\* READING-VIEW:begin[\s\S]*?\*\/([\s\S]*?)\/\* READING-VIEW:end \*\//.exec(APP);
  assert.ok(m, "READING-VIEW markers in web/app.js");
  const box = {};
  vm.runInNewContext(m[1] + "\nout.f = readingView;", { out: box });
  const v = (tl) => JSON.parse(JSON.stringify(box.f(tl)));
  assert.deepEqual(v({}), { state: "AshLight is not reading Client.txt. The setup card on Play asks first.",
    path: "", stop: false });
  assert.equal(v({ consented: true, reading: true, path: " logs/Client.txt " }).path, "Log file: logs/Client.txt");
  assert.equal(v({ consented: true, reading: true }).state, "AshLight is reading Client.txt.");
  assert.equal(v({ consented: true, reading: true }).stop, true);
  assert.match(v({ consented: true, reading: false }).state, /not reading Client\.txt now\. Checks says why\.$/);
  assert.equal(v({ consented: "yes" }).stop, false, "only consented === true shows the opt-out");
  for (const tl of [{}, { consented: true, reading: true }, { consented: true }]) {
    for (const sentence of v(tl).state.split(/(?<=\.) /)) {
      assert.ok(sentence.split(" ").length <= 12, sentence);
    }
  }
  assert.match(APP, /\$\("consent-no"\)\.hidden = !rv\.stop;/);
  assert.match(APP, /setPill\(\$\("book-state"\), v\.pill\.state, v\.pill\.glyph, v\.pill\.word\);/);
});

test("rail.js: no timer, request, clipboard, live region or inline style; ASCII", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  for (const bad of ["setTimeout", "setInterval", "fetch(", "XMLHttpRequest", "EventSource",
    "clipboard", "innerHTML", "aria-live", ".style", "localStorage", "sessionStorage"]) {
    assert.ok(!code.includes(bad), bad);
  }
  assert.ok(/^[\x09\x0a\x20-\x7e]*$/.test(SRC));
});
