"use strict";
/* TEST-WEB-PANELS-A (finding F-135; research 0047 R4 (c)): the dashboard
   blocks that left web/app.js for their own web/panels/ file. Each moved
   panel registers with window.ALApp (web/registry.js) under its name and
   an explicit order, so the page's paint and wire order is kept whatever
   order the scripts load in. The panel reaches the page's shared helpers
   only through window.ALApp.host, which web/app.js sets.
   Moved so far: web/panels/build.js ("loaded-build", the TC-VIEW block;
   TEST-WEB-PANELS-A), and from TEST-WEB-PANELS-B the settings-side blocks
   web/panels/layout.js ("layout"), weights.js ("weights"), gfx.js ("gfx")
   and webdata.js ("webdata"), each under the name and order app.js gave
   it before the move. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const web = require("./_web.js");

const R = web.load("registry.js");
const TC = web.load("tc.js");
const PR = web.load("prices.js");
const APP = web.source("app.js");
const BUILD_SRC = web.source("build.js");

/* one moved panel per row: file, registered name, order */
const MOVED = [["build.js", "loaded-build", 9], ["layout.js", "layout", 200],
  ["weights.js", "weights", 220], ["gfx.js", "gfx", 230], ["webdata.js", "webdata", 250]];
const B_FILES = ["layout.js", "weights.js", "gfx.js", "webdata.js"];

function quietRegistry() {
  const said = [];
  return { reg: R.create({ warn: (t) => said.push(t) }), said };
}

/* Run a panel file as the page does (no module, window.ALApp set). */
function runPanel(src, sandbox) {
  sandbox.window = sandbox;
  vm.runInNewContext(src, sandbox, { filename: "panel.js" });
  return sandbox;
}

/* Run web/app.js against a page that never starts: only its
   registrations (and A.host) happen. */
function runApp(reg) {
  const noop = () => {};
  const win = {
    ALApp: reg, ALDash: {}, ALFmt: { duration: noop, clock: noop, pad: noop },
    ALTc: {}, ALPrices: {}
  };
  const sandbox = {
    window: win,
    document: { readyState: "loading", addEventListener: noop, getElementById: noop },
    location: { hash: "", pathname: "/" },
    sessionStorage: { getItem: () => "", setItem: noop },
    history: { replaceState: noop },
    console
  };
  Object.keys(win).forEach((k) => { sandbox[k] = win[k]; });
  vm.runInNewContext(APP, sandbox, { filename: "app.js" });
  return reg;
}

test("each moved panel registers with its name and order", () => {
  for (const [file, name, order] of MOVED) {
    const mod = web.load(file);
    assert.equal(mod.name, name, file);
    assert.equal(mod.order, order, file);
    const { reg } = quietRegistry();
    runPanel(web.source(file), { ALApp: reg });
    assert.deepEqual(reg.names(), [name], file);
  }
});

test("the loaded build paints and wires just before app.js's build entry, either load order", () => {
  // the page: the panels marker sits before app.js (TEST-WEB-ASSEMBLE)
  const page = quietRegistry().reg;
  runPanel(BUILD_SRC, { ALApp: page });
  runApp(page);
  const names = page.names();
  assert.deepEqual(names.slice(0, 3), ["loaded-build", "build", "eval"]);
  // the explicit order keeps it first even when app.js registers first
  const late = quietRegistry().reg;
  runApp(late);
  runPanel(BUILD_SRC, { ALApp: late });
  assert.deepEqual(late.names(), names);
});

test("the page links the panel at its marker; index.html itself is not edited", () => {
  const html = web.source("index.html");
  assert.ok(html.includes("<!-- al:panels -->"));
  assert.ok(html.indexOf("<!-- al:panels -->") < html.indexOf('<script src="/web/app.js" defer>'));
  assert.ok(!html.includes("/web/panels/"));
});

test("app.js no longer holds the moved block and hands over exactly what the panel binds", () => {
  for (const fn of ["loadBuild", "sourceLine", "renderBuildYou", "renderBuild", "renderBuildFile",
    "tellBuildFile", "saveBuildFile", "postJson", "showPaste", "pasteBuild", "linkOffer",
    "linkCancel", "linkConfirm", "copyBuild"]) {
    assert.ok(!new RegExp("function " + fn + "\\(").test(APP), "app.js still defines " + fn);
    assert.ok(new RegExp("\\n  function " + fn + "\\(").test(BUILD_SRC), "panel lacks " + fn);
  }
  for (const v of ["buildDoc", "buildRev", "calcRev", "pobEvalId", "lastPaste", "linkRecover"]) {
    assert.ok(!APP.includes(v), "app.js still names " + v);
  }
  const reg = runApp(quietRegistry().reg);
  const keys = Object.keys(reg.host).sort();
  // TEST-WEB-PANELS-B: every host key is bound by at least one panel file
  const all = MOVED.map(([file]) => web.source(file)).join("\n");
  const bound = [...new Set([...all.matchAll(/\bhost\.([A-Za-z$]+)/g)].map((m) => m[1]))].sort();
  assert.deepEqual(bound, keys);
  keys.forEach((k) => {
    if (k !== "token" && k !== "cardOpener" && k !== "webLink") {
      assert.equal(typeof reg.host[k], "function", k);
    }
  });
  // filled by web/panels/webdata.js on its wire
  assert.deepEqual(Object.keys(reg.host.webLink), []);
});

test("the panel adds no clipboard read, timer, request or live region (decisions 0014, 0034)", () => {
  assert.doesNotMatch(BUILD_SRC, /[^\x0a\x20-\x7e]/);
  assert.ok(!BUILD_SRC.includes("\r"));
  const code = BUILD_SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "requestAnimationFrame", "XMLHttpRequest", "EventSource",
    "innerHTML", "aria-live", "readText", "clipboard.read", "localStorage", "sessionStorage"]) {
    assert.ok(!code.includes(bad), bad);
  }
  // the clipboard is written in one place, copyBuild (the player's click)
  assert.equal(code.split("navigator.clipboard.writeText(").length - 1, 1);
  const copy = code.slice(code.indexOf("function copyBuild()"), code.indexOf("function paint("));
  assert.ok(copy.includes("navigator.clipboard.writeText(code)"));
  // the two timers moved as they were: the paste event's next turn and the
  // download link's revoke; nothing else
  assert.deepEqual([...code.matchAll(/setTimeout\(([a-zA-Z]+|function)/g)].map((m) => m[1]),
    ["function", "pasteBuild"]);
  // the same three endpoints as before the move, all on the page's origin
  const paths = [...code.matchAll(/"(\/api\/[a-z-]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual([...new Set(paths)], ["/api/build", "/api/build-code", "/api/buildfile"]);
});

/* ---- behaviour, on a fake page */

function node(id) {
  const n = {
    id, hidden: false, disabled: false, value: "", textContent: "", attrs: {}, kids: [],
    listeners: {}, focused: 0, selected: 0, files: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    hasAttribute(k) { return k in this.attrs; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.kids.push(c); return c; },
    replaceChildren(...c) { this.kids = c; },
    focus() { this.focused += 1; },
    select() { this.selected += 1; },
    fire(t) { (this.listeners[t] || []).forEach((f) => f({ type: t })); }
  };
  return n;
}

function fakePage(opts) {
  const els = {};
  const $ = (id) => { if (!els[id]) { els[id] = node(id); } return els[id]; };
  const calls = { api: [], fetch: [], write: [], pager: [], shown: [] };
  const snap = { level: 40, zone: "Clearfell" };
  const host = {
    $, token: "abc123",
    api(method, path, body) { calls.api.push([method, path, body]); return Promise.resolve(opts.buildDoc); },
    getSnap: () => snap,
    serverNow: () => 1000,
    el(tag, cls, text) { const n = node(""); n.tag = tag; n.className = cls || ""; if (text != null) { n.textContent = text; } return n; },
    linkOut(l, name) { const n = node(""); n.link = [l, name]; return n; },
    setLine(n, text) { n.textContent = text; },
    linkPager(slot, label) { calls.pager.push(slot); },
    textPager(slot, label, rows) { calls.pager.push(slot); },
    cardShown: () => "main",
    cardHome() {},
    setCardHome(box, name) { box.setAttribute("data-home", name); },
    showCardPage(box, name) { calls.shown.push(name); },
    cardHeading: () => node("h2"),
    cardOpener: {},
    webDataSaved() {}
  };
  const reg = R.create({ warn: (t) => { throw new Error(t); } });
  reg.host = host;
  const sandbox = {
    ALApp: reg, ALTc: TC, console,
    document: { createDocumentFragment: () => node(""), createElement: () => node(""), body: node("body"),
      activeElement: null },
    navigator: { clipboard: {
      writeText(t) { calls.write.push(t); return Promise.resolve(); },
      readText() { throw new Error("the panel must never read the clipboard"); }
    } },
    fetch(url, o) { calls.fetch.push([url, o]); return Promise.resolve(opts.fetchAnswer); },
    setTimeout(f) { f(); },
    URL: { createObjectURL: () => "blob:x", revokeObjectURL() {} },
    Blob: function Blob(parts) { this.parts = parts; }
  };
  runPanel(BUILD_SRC, sandbox);
  return { reg, els: els, $, calls };
}

const DOC = {
  loaded: true, code: "eNabc", source: "paste", loaded_at: 900,
  build: { class_name: "Monk", ascendancy: "Invoker", level: 87, stats: { Life: 2410 },
           gear: {}, skills: [], notes: "" },
  build_file: { filename: "monk.build", passives: 3, skills: 1, slots: 0, notes: [] }
};

const tickOver = () => new Promise((r) => setImmediate(r));

test("the panel wires the build's clicks and loads the build on a new revision", async () => {
  const p = fakePage({ buildDoc: DOC });
  p.reg.start();
  for (const id of ["build-paste", "link-offer", "link-yes", "link-no", "build-copy", "buildfile-save"]) {
    assert.ok(Object.keys(p.$(id).listeners).length, id);
  }
  assert.deepEqual(Object.keys(p.$("build-paste").listeners).sort(), ["change", "paste"]);
  p.reg.render({ build: { rev: 1 } }, {});
  assert.deepEqual(p.calls.api, [["GET", "/api/build", undefined]]);
  await tickOver();
  assert.equal(p.$("build-name").textContent, "Monk - Invoker");
  assert.equal(p.$("build-you").textContent, "You are level 40 in Clearfell.");
  assert.equal(p.$("build-source").textContent, "Pasted, 1 min ago.");
  assert.equal(p.$("build-code-out").value, "eNabc");
  assert.equal(p.$("buildfile-save").disabled, false);
  assert.deepEqual(p.calls.pager, ["build-gear", "build-skills", "build-notes", "build-chars"]);
  // the same revision reads nothing again
  p.reg.render({ build: { rev: 1 } }, {});
  assert.equal(p.calls.api.length, 1);
});

test("Copy code writes the clipboard only on the click", async () => {
  const p = fakePage({ buildDoc: DOC });
  p.reg.start();
  p.reg.render({ build: { rev: 1 } }, {});
  await tickOver();
  assert.deepEqual(p.calls.write, []);
  p.$("build-copy").fire("click");
  assert.deepEqual(p.calls.write, ["eNabc"]);
  await tickOver();
  assert.equal(p.$("build-copy-status").textContent, "Copied - paste it into Path of Building");
});

test("a paste posts the code once with the page token", async () => {
  const p = fakePage({ buildDoc: DOC,
    fetchAnswer: { status: 200, json: () => Promise.resolve(DOC) } });
  p.reg.start();
  p.$("build-paste").value = "  eNabc  ";
  p.$("build-paste").fire("change");
  p.$("build-paste").fire("change"); // the same text again: no second post
  assert.equal(p.calls.fetch.length, 1);
  const [url, o] = p.calls.fetch[0];
  assert.equal(url, "/api/build-code");
  assert.equal(o.method, "POST");
  assert.equal(o.headers["X-AL-Token"], "abc123");
  assert.deepEqual(JSON.parse(o.body), { code: "eNabc" });
  await tickOver();
  assert.equal(p.$("build-status").textContent, "Loaded: Monk, level 87.");
  assert.equal(p.$("build-paste").value, "");
});

test("the panel says why when web/app.js has not set the host", () => {
  const { reg, said } = quietRegistry();
  runPanel(BUILD_SRC, { ALApp: reg, ALTc: TC });
  reg.start();
  assert.equal(said.length, 1);
  assert.match(said[0], /^panel loaded-build wire failed: loaded-build: no page host/);
});

/* ---- TEST-WEB-PANELS-B: the settings-side panels (layout, weights, gfx,
   web data). Each moved under the name and order app.js gave it, so the
   page's paint and wire order is today's whatever order the scripts load. */

const B_SRC = Object.fromEntries(B_FILES.map((f) => [f, web.source(f)]));
const DASH = web.load("status.js");

/* panel objects come from another vm realm: compare their plain JSON */
const plain = (x) => JSON.parse(JSON.stringify(x));

function strip(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

test("with every panel the page keeps today's paint and wire order, either load order", () => {
  // app/test/registry.test.js's entries, with the loaded build first
  const today = ["loaded-build", "build", "eval", "price", "chars", "pace", "consent", "reading",
    "events", "acts", "runs", "summary", "zonenote", "history", "pricewatch", "hints",
    "checks", "zoneguide", "layout", "filter", "weights", "gfx", "restart-overlay", "webdata",
    "settingsio"];
  const page = quietRegistry().reg;
  MOVED.forEach(([file]) => runPanel(web.source(file), { ALApp: page }));
  runApp(page);
  assert.deepEqual(page.names(), today);
  const late = quietRegistry().reg;
  runApp(late);
  MOVED.slice().reverse().forEach(([file]) => runPanel(web.source(file), { ALApp: late }));
  assert.deepEqual(late.names(), today);
});

test("app.js no longer holds the settings-side blocks; each lives in its panel", () => {
  const blocks = {
    "layout.js": ["option", "fillLayout", "readLayoutForm", "saveLayout", "loadLayout"],
    "weights.js": ["weightLabel", "pointsText", "changedRows", "bandLine", "weightPager",
      "showWeightPage", "fillWeights", "resetWeights", "fillBand", "loadWeights", "saveWeights"],
    "gfx.js": ["renderGfx", "openGfx"],
    "webdata.js": ["fillWebData", "loadWebData", "webDataSaved", "saveContact", "saveLeague",
      "saveWebData"]
  };
  for (const [file, fns] of Object.entries(blocks)) {
    for (const fn of fns) {
      assert.ok(new RegExp("\\n  function " + fn + "\\(").test(B_SRC[file]), file + " lacks " + fn);
      if (fn !== "webDataSaved") {
        assert.ok(!new RegExp("function " + fn + "\\(").test(APP), "app.js still defines " + fn);
      }
    }
  }
  // app.js keeps only a forwarder for the loaded build's link offer
  const fwd = APP.slice(APP.indexOf("  function webDataSaved(doc) {"));
  assert.match(fwd.slice(0, fwd.indexOf("\n  }\n")), /webLink\.saved\(doc\)/);
  for (const v of ["layoutBusy", "weightsBusy", "weightsAgain", "weightsDoc", "WEIGHT_PAGE",
    "CHANGED_ROWS", "gfxLoaded", "webOn", "webBusy", "webDoc"]) {
    assert.ok(!APP.includes(v), "app.js still names " + v);
  }
  for (const name of ["layout", "weights", "gfx", "webdata"]) {
    assert.ok(!APP.includes('name: "' + name + '"'), "app.js still registers " + name);
  }
  // the restart-overlay button stays in app.js: render() clears its note on
  // every push (app/test/client_controls.test.js)
  assert.ok(APP.includes("  function wireRestartOverlay() {"));
  assert.ok(!B_SRC["layout.js"].includes("restartOverlay"));
  // connect() runs the panels' first reads where it read them itself
  const at = APP.indexOf("  function connect() {");
  const conn = APP.slice(at, APP.indexOf("\n  }\n", at));
  assert.ok(conn.indexOf("if (!token)") < conn.indexOf("connectReads.forEach(function (fn) { fn(); });"));
  assert.ok(conn.indexOf("connectReads.forEach") < conn.indexOf("loadRates();"));
  for (const fn of ["loadLayout", "loadWeights", "loadWebData"]) { assert.ok(!conn.includes(fn), fn); }
});

test("the settings-side panels add no clipboard, timer, live region or new request (decisions 0013, 0014)", () => {
  const ENDPOINTS = { "layout.js": ["/api/overlay-layout"], "weights.js": ["/api/weights"],
    "gfx.js": ["/api/gfx"], "webdata.js": ["/api/web-data"] };
  for (const f of B_FILES) {
    const src = B_SRC[f];
    assert.doesNotMatch(src, /[^\x0a\x20-\x7e]/, f);
    assert.ok(!src.includes("\r"), f);
    const code = strip(src);
    for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "XMLHttpRequest",
      "EventSource", "fetch(", "innerHTML", "aria-live", "clipboard", "localStorage",
      "sessionStorage"]) {
      assert.ok(!code.includes(bad), f + ": " + bad);
    }
    const paths = [...new Set([...code.matchAll(/"(\/api\/[a-z-]+)"/g)].map((m) => m[1]))].sort();
    assert.deepEqual(paths, ENDPOINTS[f], f);
  }
  // decision 0013: the web_data switch is posted from one place, with the
  // box the player set, and nothing here ticks the box on
  const wd = strip(B_SRC["webdata.js"]);
  assert.equal(wd.split("enabled:").length - 1, 1);
  assert.match(wd, /var want = \$\("webdata-on"\)\.checked;/);
  assert.doesNotMatch(wd, /checked = true/);
  // decision 0014: the hardware read waits for the player's open of the panel
  assert.match(strip(B_SRC["gfx.js"]), /if \(!\$\("gfx"\)\.open \|\| gfxLoaded\) \{ return; \}/);
});

/* a fake page for the settings-side panels */
function bnode(id) {
  const n = node(id);
  n.checked = false;
  n.open = false;
  Object.defineProperty(n, "options", { get() { return this.kids; } });
  n.querySelectorAll = function (sel) {
    const want = sel === "li" ? (k) => k.tag === "li"
      : (k) => k.tag === "input" && k.hasAttribute("data-key");
    const out = [];
    const walk = (x) => x.kids.forEach((k) => { if (want(k)) { out.push(k); } walk(k); });
    walk(this);
    return out;
  };
  return n;
}

function settingsPage(answers, files) {
  const els = {};
  const $ = (id) => { if (!els[id]) { els[id] = bnode(id); } return els[id]; };
  const calls = { api: [], reads: [], price: [], rates: 0, shownRates: 0, shown: [], pager: [] };
  const snap = { price: { id: 7 }, eval: null };
  const mk = (tag) => { const n = bnode(""); n.tag = tag; return n; };
  const host = {
    $, token: "abc123",
    api(method, path, body) {
      calls.api.push([method, path, body]);
      const a = answers[method + " " + path];
      return Promise.resolve(typeof a === "function" ? a(body) : a);
    },
    getSnap: () => snap,
    el(tag, cls, text) {
      const n = mk(tag);
      n.className = cls || "";
      if (text != null) { n.textContent = text; }
      return n;
    },
    setLine(n, text) { n.textContent = text; },
    linkPager(slot, label, size, opts) { calls.pager.push([slot, opts.rows.map((r) => r.text)]); },
    sizeClass: () => "full",
    showCardPage(box, name) { calls.shown.push(name); },
    cardHeading: () => bnode("h2"),
    getRatesDoc: () => null,
    renderRates() { calls.shownRates += 1; },
    renderPrice(pr, force) { calls.price.push([pr, force]); },
    loadRates() { calls.rates += 1; },
    webLink: {},
    onConnect(fn) { calls.reads.push(fn); }
  };
  const reg = R.create({ warn: (t) => { throw new Error(t); } });
  reg.host = host;
  const sandbox = {
    ALApp: reg, ALTc: TC, ALPrices: PR, ALDash: DASH, console,
    document: { createDocumentFragment: () => mk("#fragment"), createElement: mk, activeElement: null },
    addEventListener() {}
  };
  (files || B_FILES).forEach((f) => runPanel(B_SRC[f], sandbox));
  return { reg, host, $, calls, snap };
}

test("each settings panel's first read waits for connect and runs in wire order", async () => {
  const p = settingsPage({});
  p.reg.start();
  assert.deepEqual(p.calls.api, []); // wiring reads nothing
  assert.deepEqual(p.calls.reads.map((f) => f.name), ["loadLayout", "loadWeights", "loadWebData"]);
  p.calls.reads.forEach((f) => f());
  assert.deepEqual(p.calls.api.map((c) => c[0] + " " + c[1]),
    ["GET /api/overlay-layout", "GET /api/weights", "GET /api/web-data"]);
  await tickOver();
});

test("the layout panel fills the form and saves the player's change", async () => {
  const LAYOUT = { layout: { display: "primary", corner: "top-right", scale: 1.25, opacity: 0.8, margin: 12 },
    corners: ["top-left", "top-right"], displays: [{ index: 0, primary: true, width: 1920, height: 1080 }] };
  const p = settingsPage({ "GET /api/overlay-layout": LAYOUT, "POST /api/overlay-layout": LAYOUT },
    ["layout.js"]);
  p.reg.start();
  p.calls.reads[0]();
  await tickOver();
  assert.equal(p.$("layout-corner").kids.length, 2);
  assert.equal(p.$("layout-corner").value, "top-right");
  assert.equal(p.$("layout-display").kids[1].textContent, "Monitor 1 (primary) - 1920x1080");
  assert.equal(p.$("layout-scale-out").textContent, "125%");
  assert.equal(p.$("layout-opacity-out").textContent, "80%");
  p.$("layout-margin").value = "20";
  p.$("layout-form").fire("change");
  assert.deepEqual(plain(p.calls.api[1]), ["POST", "/api/overlay-layout",
    { display: "primary", corner: "top-right", scale: 1.25, opacity: 0.8, margin: 20 }]);
  assert.equal(p.$("layout-status").textContent, "Saving...");
  await tickOver();
  assert.equal(p.$("layout-status").textContent, "Saved. The overlay moves within a second.");
});

test("the weights panel lists the weights and saves a change", async () => {
  const W = { weights: { "+# to maximum Life": 1.5, "#% increased Armour": 0.5 },
    sidegrade: { abs: 2, pct: 5 }, changed: { weights: { "+# to maximum Life": 1.5 } },
    defaults: { weights: { "+# to maximum Life": 1, "#% increased Armour": 0.5 },
      sidegrade: { abs: 2, pct: 5 } } };
  const p = settingsPage({ "GET /api/weights": W, "PUT /api/weights": W }, ["weights.js"]);
  p.reg.start();
  p.calls.reads[0]();
  await tickOver();
  const inputs = p.$("weights-list").querySelectorAll("input[data-key]");
  assert.deepEqual(inputs.map((i) => i.getAttribute("data-key")),
    ["#% increased Armour", "+# to maximum Life"]);
  assert.equal(p.$("weights-abs").value, "2");
  assert.equal(p.$("weights-band-line").textContent,
    "About the same within 2 points or 5% of your item's score.");
  assert.deepEqual(plain(p.calls.pager),
    [["weights-changed", ["+N to maximum Life: 1.5 points (default 1 point)"]]]);
  inputs[1].value = "2";
  p.$("weights-form").fire("change");
  const [method, path, body] = p.calls.api[1];
  assert.equal(method + " " + path, "PUT /api/weights");
  assert.equal(body.weights["+# to maximum Life"], 2);
  assert.equal(body.weights["#% increased Armour"], 0.5);
  await tickOver();
  assert.equal(p.$("weights-status").textContent, "Saved.");
});

test("the graphics panel reads the hardware once, on the player's open", async () => {
  const G = { ok: true, hardware: { cpu: { name: "Test CPU", cores: 8 } },
    advice: { tier_text: "Middle settings suit this computer.", settings: [], warnings: [] } };
  const p = settingsPage({ "GET /api/gfx": G }, ["gfx.js"]);
  p.reg.start();
  assert.deepEqual(p.calls.reads, []);
  p.$("gfx").fire("toggle"); // closed: nothing is read
  assert.deepEqual(p.calls.api, []);
  p.$("gfx").open = true;
  p.$("gfx").fire("toggle");
  assert.deepEqual(p.calls.api, [["GET", "/api/gfx", undefined]]);
  assert.equal(p.$("gfx-status").textContent, "Checking this computer's hardware...");
  await tickOver();
  assert.equal(p.$("gfx-body").hidden, false);
  assert.equal(p.$("gfx-tier").textContent, "Middle settings suit this computer.");
  assert.equal(p.$("gfx-status").textContent, "");
  p.$("gfx").fire("toggle"); // kept for the session
  assert.equal(p.calls.api.length, 1);
});

test("the web data panel keeps the switch the player's and fills app.js's link", async () => {
  const OFF = { web_data: false, contact_set: true };
  const ON = { web_data: true, contact_set: true };
  const p = settingsPage({ "GET /api/web-data": OFF, "POST /api/web-data": ON }, ["webdata.js"]);
  p.reg.start();
  assert.equal(p.$("webdata-sentence").textContent, TC.WEB_DATA_OPT_IN);
  const link = p.host.webLink;
  assert.deepEqual(Object.keys(link).sort(), ["fill", "saved", "state"]);
  assert.deepEqual({ ...link.state() }, { on: false, busy: false, doc: null });
  p.calls.reads[0]();
  await tickOver();
  assert.equal(p.$("webdata-on").checked, false);
  assert.equal(p.$("webdata-status").textContent, PR.webDataView(OFF).status);
  assert.deepEqual(p.calls.price, [[p.snap.price, true]]);
  // the player's own change of the switch is the one thing that posts it
  p.$("webdata-on").checked = true;
  p.$("webdata-form").fire("change");
  assert.deepEqual(plain(p.calls.api[1]), ["POST", "/api/web-data", { enabled: true }]);
  assert.equal(link.state().busy, true);
  await tickOver();
  assert.deepEqual({ ...link.state() }, { on: true, busy: false, doc: null });
  assert.equal(p.$("webdata-status").textContent, PR.savedText(true, ON));
  assert.equal(p.calls.rates, 1);
  // app.js's rates follow a switch saved elsewhere through the link
  link.fill({ web_data: false });
  assert.equal(p.$("webdata-on").checked, false);
  assert.equal(link.state().on, false);
  assert.equal(p.calls.api.length, 2);
});

test("each settings panel says why when web/app.js has not set the host", () => {
  for (const [file, name] of MOVED.filter(([f]) => B_FILES.includes(f))) {
    const { reg, said } = quietRegistry();
    runPanel(B_SRC[file], { ALApp: reg, ALTc: TC, ALPrices: PR });
    reg.start();
    assert.equal(said.length, 1, file);
    assert.match(said[0], new RegExp("^panel " + name + " wire failed: " + name + ": no page host"));
  }
});
