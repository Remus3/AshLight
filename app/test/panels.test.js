"use strict";
/* TEST-WEB-PANELS-A (finding F-135; research 0047 R4 (c)): the dashboard
   blocks that left web/app.js for their own web/panels/ file. Each moved
   panel registers with window.ALApp (web/registry.js) under its name and
   an explicit order, so the page's paint and wire order is kept whatever
   order the scripts load in. The panel reaches the page's shared helpers
   only through window.ALApp.host, which web/app.js sets.
   Moved so far: web/panels/build.js ("loaded-build", the TC-VIEW block).
   Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const web = require("./_web.js");

const R = web.load("registry.js");
const TC = web.load("tc.js");
const APP = web.source("app.js");
const BUILD_SRC = web.source("build.js");

/* one moved panel per row: file, registered name, order */
const MOVED = [["build.js", "loaded-build", 9]];

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
  const bound = [...new Set([...BUILD_SRC.matchAll(/\bhost\.([A-Za-z$]+)/g)].map((m) => m[1]))].sort();
  assert.deepEqual(bound, keys);
  keys.forEach((k) => {
    if (k !== "token" && k !== "cardOpener") { assert.equal(typeof reg.host[k], "function", k); }
  });
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
