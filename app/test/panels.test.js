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
   and webdata.js ("webdata"), and from TEST-WEB-PANELS-C1 the Play-side
   blocks web/panels/itemcheck.js ("eval"), rates.js ("price") and
   events.js ("events"), and from TEST-WEB-PANELS-C2 the rest:
   web/panels/pager.js ("build" and the shared page plumbing), consent.js
   ("consent", "reading", "rail"), filter.js ("filter"), restart.js
   ("restart-overlay"), settingsio.js ("settingsio", "hotkeys") and
   version.js ("version"), plus feedpace.js (no panel: feedLink and pacer
   on the host), each under the name and order app.js gave it before the
   move; the web/*.js view modules register themselves too. Fixture values
   are invented. */
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
const MOVED = [["build.js", "loaded-build", 9], ["itemcheck.js", "eval", 20],
  ["rates.js", "price", 40], ["events.js", "events", 90], ["layout.js", "layout", 200],
  ["weights.js", "weights", 220], ["gfx.js", "gfx", 230], ["webdata.js", "webdata", 250],
  // TEST-WEB-PANELS-C2 (pager.js and settingsio.js by their panels/ path:
  // web/ has a file of the same name)
  ["panels/pager.js", "build", 10], ["consent.js", "consent", 70], ["filter.js", "filter", 210],
  ["restart.js", "restart-overlay", 240], ["panels/settingsio.js", "settingsio", 260],
  ["version.js", "version", 270]];
const PAGER_SRC = web.source("panels/pager.js");
const FEED_SRC = web.source("feedpace.js");
/* the view modules that register themselves (TEST-WEB-PANELS-C2): file,
   then the names they register in run order */
const VIEWS = [["acts.js", ["pace", "acts"]], ["chars.js", ["chars"]],
  ["checks.js", ["checks", "verdicts"]], ["hints.js", ["hints"]], ["history.js", ["history"]],
  ["pricewatch.js", ["pricewatch"]], ["runs.js", ["runs"]], ["summary.js", ["summary"]],
  ["zoneguide.js", ["zoneguide"]]];
const FMT = web.load("fmt.js");

/* Run a view module as the page does (window.ALApp and window.ALFmt set). */
function runView(file, reg) {
  const sandbox = { ALApp: reg, ALFmt: FMT };
  sandbox.window = sandbox;
  vm.runInNewContext(web.source(file), sandbox, { filename: file });
  return sandbox;
}
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
    // a file with more entries (consent.js, settingsio.js) lists them in more
    const want = [[name, order]].concat(mod.more || []).sort((a, b) => a[1] - b[1]).map((e) => e[0]);
    assert.deepEqual(reg.names(), want, file);
  }
});

test("the loaded build paints and wires just before app.js's build entry, either load order", () => {
  // the page: the panels marker sits before app.js (TEST-WEB-ASSEMBLE)
  const page = quietRegistry().reg;
  runPanel(BUILD_SRC, { ALApp: page });
  runPanel(PAGER_SRC, { ALApp: page });
  runApp(page);
  const names = page.names();
  // TEST-WEB-PANELS-C2: the "build" entry is web/panels/pager.js's now
  assert.deepEqual(names, ["loaded-build", "build"]);
  // the explicit order keeps it first even when it registers last
  const late = quietRegistry().reg;
  runApp(late);
  runPanel(PAGER_SRC, { ALApp: late });
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
  // TEST-WEB-PANELS-C2: pager.js and feedpace.js add their members when
  // they load, before app.js, which merges its own into the same object
  const reg = quietRegistry().reg;
  runPanel(PAGER_SRC, { ALApp: reg });
  runPanel(FEED_SRC, { ALApp: reg });
  runApp(reg);
  const keys = Object.keys(reg.host).sort();
  // TEST-WEB-PANELS-B: every host key is bound by at least one panel file,
  // view module or the shell (A.host.loadRates, feedLink, pacer)
  const all = MOVED.map(([file]) => web.source(file)).concat(VIEWS.map(([file]) => web.source(file)),
    [APP]).join("\n");
  const bound = [...new Set([...all.matchAll(/\bhost\.([A-Za-z$]+)/g)].map((m) => m[1]))].sort();
  assert.deepEqual(bound, keys);
  keys.forEach((k) => {
    if (!["token", "cardOpener", "webLink", "evalLink", "ratesLink", "readLink", "charLink"].includes(k)) {
      assert.equal(typeof reg.host[k], "function", k);
    }
  });
  // filled by web/panels/webdata.js, itemcheck.js, rates.js, consent.js and
  // web/chars.js on their wires
  for (const link of ["webLink", "evalLink", "ratesLink", "readLink", "charLink"]) {
    assert.deepEqual(Object.keys(reg.host[link]), [], link);
  }
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
  // app/test/registry.test.js's entries (TEST-WEB-PANELS-C2: every one from
  // a panel file or a view module; "zonenote" is gone)
  const today = ["hotkeys", "loaded-build", "build", "eval", "price", "chars", "pace", "consent",
    "reading", "events", "acts", "runs", "summary", "history", "pricewatch", "hints",
    "checks", "zoneguide", "layout", "filter", "weights", "gfx", "restart-overlay", "webdata",
    "settingsio", "version", "verdicts", "rail"];
  const page = quietRegistry().reg;
  MOVED.forEach(([file]) => runPanel(web.source(file), { ALApp: page }));
  VIEWS.forEach(([file]) => runView(file, page));
  runApp(page);
  assert.deepEqual(page.names(), today);
  const late = quietRegistry().reg;
  runApp(late);
  VIEWS.slice().reverse().forEach(([file]) => runView(file, late));
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
  // TEST-WEB-PANELS-C2: the restart-overlay button left app.js too; its
  // note clears through host.onPush (app/test/client_controls.test.js)
  assert.ok(!APP.includes("wireRestartOverlay"));
  assert.ok(web.source("restart.js").includes("  function wireRestartOverlay() {"));
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

/* ---- TEST-WEB-PANELS-C1: the Play-side blocks (item check, rates and
   price, recent events). The trades block is not recreated: the redesign
   replaced it by Play's feed region (web/feed.js). */
const C_FILES = ["itemcheck.js", "rates.js", "events.js"];
const C_SRC = Object.fromEntries(C_FILES.map((f) => [f, web.source(f)]));

test("app.js no longer holds the Play-side blocks; each lives in its panel", () => {
  const blocks = {
    "itemcheck.js": ["paintEvalRows", "textRow", "renderEval"],
    "rates.js": ["textRow", "paintPricesList", "renderRates", "renderMovers", "loadRates",
      "pollRates", "renderPrice"],
    "events.js": ["evTag", "evShows", "evChips", "evStart", "renderEvents"]
  };
  for (const [file, fns] of Object.entries(blocks)) {
    for (const fn of fns) {
      assert.ok(new RegExp("\\n  function " + fn + "\\(").test(C_SRC[file]), file + " lacks " + fn);
      assert.ok(!new RegExp("function " + fn + "\\(").test(APP), "app.js still defines " + fn);
    }
  }
  // the package's accept grep, and the trades block stays gone
  assert.doesNotMatch(APP, /function (renderEvents|renderTrades|dismissTrade|renderEval|renderRates|renderPrice)\(/);
  for (const f of C_FILES) { assert.doesNotMatch(strip(C_SRC[f]), /renderTrades|dismissTrade|ALTrades/, f); }
  for (const v of ["evalShown", "EVAL_ROWS", "evalRows", "RATES_POLL_MS", "ratesDoc", "ratesAgain",
    "priceShown", "PRICE_ROWS", "rateRows", "trendRows", "renderedEvents", "evPager", "EV_SIZE",
    "EV_NONE", "window.ALTc", "window.ALPrices"]) {
    assert.ok(!APP.includes(v), "app.js still names " + v);
  }
  for (const name of ["eval", "price", "events"]) {
    assert.ok(!APP.includes('name: "' + name + '"'), "app.js still registers " + name);
  }
  // connect() still reads the rates right after the panels' first reads,
  // and start() no longer sets the poll timer (the rates panel's wire does)
  const at = APP.indexOf("  function connect() {");
  const conn = APP.slice(at, APP.indexOf("\n  }\n", at));
  assert.ok(conn.indexOf("connectReads.forEach") < conn.indexOf("A.host.loadRates();"));
  assert.ok(!APP.includes("setInterval(pollRates"));
});

test("the Play-side panels add no clipboard, live region or new request; the timers moved as they were", () => {
  const ENDPOINTS = { "itemcheck.js": [], "rates.js": ["/api/rates"], "events.js": [] };
  for (const f of C_FILES) {
    const src = C_SRC[f];
    assert.doesNotMatch(src, /[^\x0a\x20-\x7e]/, f);
    assert.ok(!src.includes("\r"), f);
    const code = strip(src);
    for (const bad of ["requestAnimationFrame", "XMLHttpRequest", "EventSource", "fetch(",
      "innerHTML", "aria-live", "clipboard", "localStorage", "sessionStorage"]) {
      assert.ok(!code.includes(bad), f + ": " + bad);
    }
    const paths = [...new Set([...code.matchAll(/"(\/api\/[a-z-]+)"/g)].map((m) => m[1]))].sort();
    assert.deepEqual(paths, ENDPOINTS[f], f);
    if (f !== "rates.js") {
      assert.ok(!code.includes("setInterval") && !code.includes("setTimeout"), f);
    }
  }
  // the rates panel keeps app.js's two timers: the 3 s re-read after a
  // refresh the core just started and the 5 minute poll
  const r = strip(C_SRC["rates.js"]);
  assert.deepEqual([...r.matchAll(/set(Interval|Timeout)\(([a-zA-Z]+), ([A-Z_0-9]+)\)/g)].map((m) => m.slice(1)),
    [["Timeout", "loadRates", "3000"], ["Interval", "pollRates", "RATES_POLL_MS"]]);
  assert.match(r, /var RATES_POLL_MS = 5 \* 60 \* 1000;/);
  assert.match(r, /if \(!document\.hidden && isLive\(\)\) \{ loadRates\(\); \}/);
});

/* a fake page for the Play-side panels */
function playPage(answers) {
  const els = {};
  const $ = (id) => { if (!els[id]) { els[id] = node(id); } return els[id]; };
  const calls = { api: [], pager: [], timers: [], evRows: [] };
  const snap = { price: null, price_watch: null, eval: null };
  const host = {
    $, token: "abc123", clock: () => "12:00",
    api(method, path, body) {
      calls.api.push([method, path, body]);
      return Promise.resolve(answers[method + " " + path]);
    },
    getSnap: () => snap,
    el(tag, cls, text) {
      const n = node("");
      n.tag = tag;
      n.className = cls || "";
      if (text != null) { n.textContent = text; }
      return n;
    },
    setLine(n, text) { n.textContent = text; },
    setText(n, text) { n.textContent = text; },
    setPill(n, state, glyph, word) { n.setAttribute("data-state", state); n.textContent = word; },
    isLive: () => true,
    linkPager(slot, label, size, opts) { calls.pager.push([slot, opts.rows.map((r) => r.text)]); },
    webLink: {},
    webState: () => ({ on: false, busy: false, doc: null }),
    evalLink: {},
    ratesLink: {}
  };
  const reg = R.create({ warn: (t) => { throw new Error(t); } });
  reg.host = host;
  const sandbox = {
    ALApp: reg, ALTc: TC, ALPrices: PR, ALDash: DASH, console,
    ALSearch: {
      sizeClass: () => "full",
      rowPager() {
        return { node: node("pager"), set(rows) { calls.evRows.push(rows); }, state: () => ({ hasPrev: false }) };
      }
    },
    document: { hidden: false, createDocumentFragment: () => node(""), querySelectorAll: () => [] },
    setInterval(f, ms) { calls.timers.push(["interval", f.name, ms]); return 1; },
    setTimeout(f, ms) { calls.timers.push(["timeout", f.name, ms]); return 2; },
    clearTimeout() {}
  };
  C_FILES.forEach((f) => runPanel(C_SRC[f], sandbox));
  return { reg, host, $, calls, snap };
}

test("the Play-side panels register in today's order and fill app.js's links on their wires", async () => {
  const p = playPage({ "GET /api/rates": { web_data: false } });
  assert.deepEqual(p.reg.names(), ["eval", "price", "events"]);
  p.reg.start();
  assert.deepEqual(p.calls.api, []); // wiring reads nothing
  assert.deepEqual(Object.keys(p.host.evalLink), ["price"]);
  assert.deepEqual(Object.keys(p.host.ratesLink).sort(),
    ["getRatesDoc", "loadRates", "paintPricesList", "renderPrice", "renderRates"]);
  assert.deepEqual(p.calls.timers, [["interval", "pollRates", 5 * 60 * 1000]]);
  // connect()'s read through the host forwarder: one GET, then the cards
  assert.equal(p.host.ratesLink.getRatesDoc(), null);
  p.host.ratesLink.loadRates();
  await tickOver();
  assert.deepEqual(p.calls.api, [["GET", "/api/rates", undefined]]);
  assert.deepEqual(plain(p.host.ratesLink.getRatesDoc()), { web_data: false });
  assert.notEqual(p.$("rates-pill").getAttribute("data-state"), "failed");
  assert.ok(p.calls.pager.some(([slot]) => slot === "prices-list"));
  // the price rows reach the Last item card's one list through evalLink
  assert.deepEqual(plain(p.calls.pager[p.calls.pager.length - 1]), ["eval-rows", []]);
});

test("the item check and recent events paint as before the move", () => {
  const p = playPage({});
  p.reg.start();
  p.reg.render({ eval: { id: 5, ok: false, text: { item: "Iron Ring" } }, price: null, recent_events: [
    { at: 1, type: "level_up", text: "Reached level 2." },
    { at: 2, type: "death", text: "You died." }] });
  assert.equal(p.$("eval-empty").hidden, true);
  assert.equal(p.$("eval-body").hidden, false);
  assert.equal(p.$("eval-word").textContent, "Not checked");
  assert.ok(p.calls.pager.some(([slot]) => slot === "eval-rows"));
  assert.equal(p.$("price-body").hidden, true);
  // the same check again paints nothing; a push with no check empties the card
  const painted = p.calls.pager.length;
  p.reg.render({ eval: { id: 5, ok: false, text: { item: "Iron Ring" } }, price: null, recent_events: [] });
  assert.equal(p.calls.pager.filter(([slot]) => slot === "eval-rows").length,
    p.calls.pager.slice(0, painted).filter(([slot]) => slot === "eval-rows").length);
  p.reg.render({ eval: null, price: null, recent_events: [
    { at: 1, type: "level_up", text: "Reached level 2." },
    { at: 2, type: "death", text: "You died." }] });
  assert.equal(p.$("eval-empty").hidden, false);
  assert.equal(p.$("eval-body").hidden, true);
  // newest first, with the local time and the tag
  const rows = p.calls.evRows[p.calls.evRows.length - 1];
  assert.deepEqual(plain(rows.map((r) => r.text)), ["12:00 Death: You died.", "12:00 Level: Reached level 2."]);
  assert.equal(p.$("events").hidden, false);
  assert.equal(p.$("events-empty").hidden, true);
  assert.equal(p.$("events-none").hidden, true);
});

test("each Play-side panel says why when web/app.js has not set the host", () => {
  for (const [file, name] of MOVED.filter(([f]) => C_FILES.includes(f))) {
    const { reg, said } = quietRegistry();
    runPanel(C_SRC[file], { ALApp: reg, ALTc: TC, ALPrices: PR, ALDash: DASH });
    if (file === "events.js") { reg.render({}); } else { reg.start(); }
    assert.equal(said.length, 1, file);
    assert.match(said[0], new RegExp("^panel " + name + " (wire|paint) failed: " + name + ": no page host"));
  }
});

/* ---- TEST-WEB-PANELS-C2: the settings-side blocks (consent and ledger,
   filter, restart overlay, settings import / export, the pagers and card
   pages, version and credit) and the feed / pacer block leave web/app.js;
   the view modules register themselves; app.js is a shell. */
const C2_SRC = {
  "consent.js": web.source("consent.js"), "filter.js": web.source("filter.js"),
  "restart.js": web.source("restart.js"), "panels/settingsio.js": web.source("panels/settingsio.js"),
  "panels/pager.js": PAGER_SRC, "version.js": web.source("version.js"), "feedpace.js": FEED_SRC
};

test("app.js is a shell: under 300 lines, no feature module named, the blocks in their files", () => {
  assert.ok(APP.split("\n").length - 1 < 300, "web/app.js has " + (APP.split("\n").length - 1) + " lines");
  // the package's accept grep: only the four shared shims are named
  const named = [...APP.matchAll(/window\.AL[A-Z][A-Za-z]*/g)].map((m) => m[0]);
  assert.deepEqual(named.filter((n) => !/^window\.AL(App|Fmt|Regions|Tabs)$/.test(n)), []);
  const blocks = {
    "consent.js": ["showPill", "showReading", "stopReading", "readingView", "ledgerView",
      "paintLedger", "toggleLedger"],
    "filter.js": ["downloadFilter", "mergeFilter"],
    "restart.js": ["wireRestartOverlay"],
    "version.js": ["versionText", "loadDataCredit"],
    "feedpace.js": ["feedLink", "pacer"]
  };
  for (const [file, fns] of Object.entries(blocks)) {
    for (const fn of fns) {
      assert.ok(new RegExp("\\n  function " + fn + "\\(").test(C2_SRC[file]), file + " lacks " + fn);
      assert.ok(!new RegExp("function " + fn + "\\(").test(APP), "app.js still defines " + fn);
    }
  }
  // the page plumbing sits inside pager.js's parts()
  for (const fn of ["el", "linkOut", "setLine", "cardHomeName", "cardShown", "cardHeading",
    "showCardPage", "cardHome", "setCardHome", "wireCard", "sizeClass", "textPager", "linkPager",
    "relayoutPagers"]) {
    assert.ok(new RegExp("\\n    function " + fn + "\\(").test(PAGER_SRC), "pager.js lacks " + fn);
    assert.ok(!new RegExp("function " + fn + "\\(").test(APP), "app.js still defines " + fn);
  }
  for (const marker of ["READING-VIEW", "LEDGER-VIEW", "BUILD-STAMP", "FEED-PACE"]) {
    assert.ok(!APP.includes(marker + ":begin"), "app.js still holds " + marker);
  }
  for (const v of ["charPick", "restartSaid", "ledgerSend", "buildPagers", "cardOpener = {}",
    "FEED_RETRY_MS", "name: \"zonenote\""]) {
    assert.ok(!APP.includes(v), "app.js still names " + v);
  }
  // pad, duration and clock: the formatters live in web/fmt.js; app.js
  // keeps only the clock alias (app/test/fmt.test.js)
  assert.doesNotMatch(APP, /function (pad|duration|clock)\(/);
});

test("each view module registers itself once, with its name and order", () => {
  const orders = {};
  for (const [file, want] of VIEWS) {
    const { reg } = quietRegistry();
    const spy = reg.register;
    const specs = [];
    reg.register = (spec) => { specs.push([spec.name, spec.order]); return spy(spec); };
    runView(file, reg);
    assert.deepEqual(reg.names(), want, file);
    assert.equal(specs.length, want.length, file);
    specs.forEach(([n, o]) => { orders[n] = o; });
    // without a registry (a page that has none, or a test sandbox) it
    // registers nothing and still loads
    const bare = { ALFmt: FMT };
    bare.window = bare;
    vm.runInNewContext(web.source(file), bare, { filename: file });
  }
  // the names and orders web/app.js gave these entries before the move
  assert.deepEqual(orders, { pace: 60, acts: 110, chars: 50, checks: 180, verdicts: 300, hints: 170,
    history: 150, pricewatch: 160, runs: 120, summary: 130, zoneguide: 190 });
});

test("the C2 panels add no clipboard, live region or new request; the timers moved as they were", () => {
  const ENDPOINTS = { "consent.js": ["/api/consent"], "filter.js": ["/api/filter"], "restart.js": [],
    "panels/settingsio.js": [], "panels/pager.js": [], "version.js": ["/api/version"],
    "feedpace.js": [] };
  // the download links' revoke timers, as before the move; nothing else
  const TIMERS = { "filter.js": 2, "panels/settingsio.js": 1 };
  for (const [f, src] of Object.entries(C2_SRC)) {
    assert.doesNotMatch(src, /[^\x0a\x20-\x7e]/, f);
    assert.ok(!src.includes("\r"), f);
    const code = strip(src);
    for (const bad of ["setInterval", "requestAnimationFrame", "XMLHttpRequest", "EventSource",
      "innerHTML", "aria-live", "clipboard", "localStorage", "sessionStorage"]) {
      assert.ok(!code.includes(bad), f + ": " + bad);
    }
    assert.equal(code.split("setTimeout(").length - 1, TIMERS[f] || 0, f);
    const paths = [...new Set([...code.matchAll(/"(\/api\/[a-z-]+)"/g)].map((m) => m[1]))].sort();
    assert.deepEqual(paths, ENDPOINTS[f], f);
  }
  // the shell keeps the feed, the health read and the state read
  const shell = [...new Set([...strip(APP).matchAll(/"(\/(?:api\/)?[a-z-]+)/g)].map((m) => m[1]))].sort();
  assert.deepEqual(shell, ["/api/health", "/api/state", "/events"]);
});

/* a fake page for the C2 panels */
function c2Page() {
  const els = {};
  const $ = (id) => { if (!els[id]) { els[id] = node(id); } return els[id]; };
  const calls = { api: [], reads: [], readFns: [], pushes: [], renders: [], pills: [] };
  let snap = null;
  const host = {
    $, token: "abc123",
    api(method, path, body) {
      calls.api.push([method, path, body]);
      if (path === "/api/version") { return Promise.resolve({ build: "0.4.2+0123456789ab" }); }
      return Promise.resolve({ state: { v: 2 } });
    },
    render(s) { calls.renders.push(s); },
    getSnap: () => snap,
    getLink: () => ({ event: "open", everLive: true }),
    setText(n, t) { n.textContent = t; },
    setPill(n, state, glyph, word) { calls.pills.push([n.id, state, word]); },
    setLine(n, t) { n.textContent = t; },
    onConnect(fn, late) { calls.reads.push([fn.name, !!late]); calls.readFns.push(fn); },
    onPush(fn) { calls.pushes.push(fn); },
    readLink: {}
  };
  const reg = R.create({ warn: (t) => { throw new Error(t); } });
  reg.host = host;
  const sandbox = {
    ALApp: reg, ALDash: DASH, console,
    document: { createElement: () => node(""), body: node("body") }
  };
  ["consent.js", "restart.js", "version.js"].forEach((f) => runPanel(C2_SRC[f], sandbox));
  return { reg, host, $, calls, setSnap: (s) => { snap = s; } };
}

test("the consent, restart and version panels hand app.js their hooks on their wires", async () => {
  const p = c2Page();
  assert.deepEqual(p.reg.names(), ["consent", "reading", "restart-overlay", "version", "rail"]);
  p.reg.start();
  assert.deepEqual(p.calls.api, []); // wiring reads nothing
  // the bar status word through readLink; the version read after the rates
  assert.equal(typeof p.host.readLink.show, "function");
  assert.deepEqual(p.calls.reads, [["loadDataCredit", true]]);
  assert.equal(p.calls.pushes.length, 1);
  // the consent paint and the bar word, as before the move
  const s = { tailer: { consented: true, reading: true, path: "logs/Client.txt", ledger: false } };
  p.setSnap(s);
  p.reg.render(s);
  assert.equal(p.$("reading-state").textContent, "AshLight is reading Client.txt.");
  assert.equal(p.$("reading-path").textContent, "Log file: logs/Client.txt");
  assert.equal(p.$("consent-no").hidden, false);
  assert.equal(p.$("ledger-allow").textContent, "Allow the log record");
  assert.equal(p.calls.pills.length, 1);
  assert.equal(p.calls.pills[0][0], "reading");
  p.host.readLink.show();
  assert.equal(p.calls.pills.length, 2);
  // the ledger click posts only the ledger flag, then paints the answer
  p.$("ledger-allow").fire("click");
  await tickOver();
  assert.deepEqual(plain(p.calls.api), [["POST", "/api/consent", { ledger: true }]]);
  assert.deepEqual(plain(p.calls.renders), [{ v: 2 }]);
  // connect()'s late read fills the version lines
  p.calls.api.length = 0;
  p.calls.readFns[0]();
  await tickOver();
  assert.deepEqual(plain(p.calls.api.map((c) => c.slice(0, 2))), [["GET", "/api/version"]]);
  // WEB-PLAY-FOOT-ONE-ROW: the footer cuts the build to 7 hex, Settings keeps 12
  assert.equal(p.$("build-line").textContent, "Version 0.4.2, build 0123456");
  assert.equal(p.$("build-line").hidden, false);
  assert.equal(p.$("about-version").textContent, "Version 0.4.2, build 0123456789ab");
  // the next push clears nothing while no restart was asked
  p.$("restart-overlay-said").textContent = "x";
  p.calls.pushes[0]({});
  assert.equal(p.$("restart-overlay-said").textContent, "x");
});

test("each C2 panel says why when web/app.js has not set the host", () => {
  for (const [file, name] of [["panels/pager.js", "build"], ["consent.js", "consent"],
    ["filter.js", "filter"], ["restart.js", "restart-overlay"], ["panels/settingsio.js", "settingsio"],
    ["version.js", "version"]]) {
    const { reg, said } = quietRegistry();
    const sandbox = { ALApp: reg, ALDash: DASH };
    runPanel(C2_SRC[file], sandbox);
    if (file === "panels/pager.js") { reg.host = {}; } // pager.js made an empty host
    reg.start();
    assert.equal(said.length, 1, file);
    assert.match(said[0], new RegExp("^panel " + name + " wire failed: " + name + ": no page host"));
  }
});
