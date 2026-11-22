/* PLAY-TD-04B-THEME-CHOICE (TD-04, F-086): the page ships dark for every
   browser and one Settings choice (Dark / Follow Windows / Light) changes
   it; the desktop client follows the choice. web/theme.js runs against a
   small fake page; the cascade of /tokens.css, web/app.css and
   web/theme.css is resolved from the files' text for each theme and
   browser scheme; app/client/window.js's reader runs against a fake http.
   Nothing starts a browser or Electron (the pixel half of the proof is
   tests/test_theme_setting.py through the shared capture helper). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { EventEmitter } = require("node:events");
const web = require("./_web.js");
const T = web.load("theme.js");
const ClientWin = require("../client/window.js");

const HTML = web.source("index.html");
const APP_CSS = web.source("app.css");
const THEME_CSS = web.source("theme.css");
const THEME_SRC = web.source("theme.js");
const KIT_CSS = fs.readFileSync(path.join(__dirname, "..", "..", "ops", "fleet_kit", "tokens.css"), "utf8");
const WIN_SRC = fs.readFileSync(path.join(__dirname, "..", "client", "window.js"), "utf8");

/* ---------------------------------------------------------- a fake page */

function el(id, tag) {
  const attrs = {};
  const listeners = {};
  return {
    id: id, tagName: tag || "DIV", value: "", textContent: "",
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; },
    removeAttribute(k) { delete attrs[k]; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k); },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    fire(type) { return (listeners[type] || []).map((fn) => fn({ type: type })); }
  };
}

function page(opts) {
  const o = opts || {};
  const root = el("html", "HTML");
  root.setAttribute("data-theme", "dark"); // as shipped in web/index.html
  const ids = { "theme-pick": el("theme-pick", "SELECT"), "theme-said": el("theme-said"),
    "settings-said": el("settings-said") };
  const observers = [];
  function Observer(cb) { this.cb = cb; observers.push(this); }
  Observer.prototype.observe = function (target, init) { this.target = target; this.init = init; };
  const doc = {
    documentElement: root,
    getElementById: (id) => ids[id] || null,
    defaultView: o.noObserver ? {} : { MutationObserver: Observer }
  };
  return { doc, root, ids, observers };
}

/* A fake ctx.api: answers from `answers` by "METHOD path", records calls. */
function fakeApi(answers) {
  const calls = [];
  function api(method, p, body) {
    calls.push({ method: method, path: p, body: body });
    const a = answers[method + " " + p];
    if (a instanceof Error) { return Promise.reject(a); }
    return Promise.resolve(typeof a === "function" ? a(body) : a);
  }
  return { api, calls };
}

const settle = () => new Promise((r) => setImmediate(r));

/* -------------------------------------------------------- theme.js units */

test("choices, the default and the attribute of each choice", () => {
  assert.deepEqual(T.CHOICES, ["dark", "system", "light"]);
  assert.equal(T.DEFAULT, "dark");
  assert.equal(T.attrFor("dark"), "dark");
  assert.equal(T.attrFor("light"), "light");
  assert.equal(T.attrFor("system"), null, "Follow Windows leaves no attribute");
  for (const bad of [undefined, null, "", "Light", "auto", 1, {}, ["dark"]]) {
    assert.equal(T.clean(bad), "dark");
    assert.equal(T.attrFor(bad), "dark");
  }
  assert.equal(T.themeOf({ theme: "light" }), "light");
  assert.equal(T.themeOf({ theme: "nope" }), "dark");
  assert.equal(T.themeOf(null), "dark");
  assert.equal(T.themeOf("light"), "dark");
});

test("apply sets dark or light and removes the attribute for Follow Windows", () => {
  const p = page();
  assert.equal(T.apply(p.doc, "light"), "light");
  assert.equal(p.root.getAttribute("data-theme"), "light");
  assert.equal(T.apply(p.doc, "system"), "system");
  assert.equal(p.root.hasAttribute("data-theme"), false);
  assert.equal(T.apply(p.doc, "dark"), "dark");
  assert.equal(p.root.getAttribute("data-theme"), "dark");
  assert.equal(T.apply(p.doc, "garbage"), "dark");
  assert.equal(p.root.getAttribute("data-theme"), "dark");
});

test("theme.js is a helper on the region registry, never a Play region", () => {
  assert.equal(T.spec.name, "theme");
  assert.equal(T.spec.region, null);
  assert.equal(typeof T.spec.wire, "function");
  assert.equal(T.spec.paint, undefined);
  assert.equal(T.spec.tick, undefined);
  const R = web.load("regions.js").create({ warn: () => {} });
  R.register(T.spec); // a valid spec
  // no timer, clipboard, storage or live region in the code
  const code = THEME_SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const banned of ["setInterval", "setTimeout", "clipboard", "localStorage",
                        "sessionStorage", "aria-live", "innerHTML", "fetch("]) {
    assert.ok(!code.includes(banned), banned + " in web/theme.js");
  }
});

test("wire reads the stored choice once and shows it", async () => {
  const p = page();
  const f = fakeApi({ "GET /api/theme": { theme: "light", choices: T.CHOICES } });
  T.wire(p.doc, { api: f.api });
  await settle();
  assert.deepEqual(f.calls, [{ method: "GET", path: "/api/theme", body: undefined }]);
  assert.equal(p.root.getAttribute("data-theme"), "light");
  assert.equal(p.ids["theme-pick"].value, "light");
});

test("with no answer the page stays dark", async () => {
  const p = page();
  const f = fakeApi({ "GET /api/theme": new Error("HTTP 503") });
  T.wire(p.doc, { api: f.api });
  await settle();
  assert.equal(p.root.getAttribute("data-theme"), "dark");
  assert.equal(p.ids["theme-said"].textContent, "");
});

test("a change applies at once, posts the one field and keeps the answer", async () => {
  const p = page();
  const f = fakeApi({ "GET /api/theme": { theme: "dark" },
    "POST /api/theme": (body) => ({ theme: body.theme }) });
  T.wire(p.doc, { api: f.api });
  await settle();
  const pick = p.ids["theme-pick"];
  pick.value = "system";
  const done = pick.fire("change")[0];
  assert.equal(p.root.hasAttribute("data-theme"), false, "applied before the answer");
  await done;
  assert.deepEqual(f.calls[1], { method: "POST", path: "/api/theme", body: { theme: "system" } });
  assert.equal(p.root.hasAttribute("data-theme"), false);
  assert.equal(pick.value, "system");
  pick.value = "light";
  await pick.fire("change")[0];
  assert.equal(p.root.getAttribute("data-theme"), "light");
});

test("a change the core refuses goes back to the saved choice and says so", async () => {
  const p = page();
  const f = fakeApi({ "GET /api/theme": { theme: "dark" }, "POST /api/theme": new Error("HTTP 500") });
  T.wire(p.doc, { api: f.api });
  await settle();
  const pick = p.ids["theme-pick"];
  pick.value = "light";
  await pick.fire("change")[0];
  assert.equal(p.root.getAttribute("data-theme"), "dark");
  assert.equal(pick.value, "dark");
  assert.equal(p.ids["theme-said"].textContent, T.NOT_SAVED);
  assert.equal(T.NOT_SAVED, "Your choice was not saved. Try again.");
  // the next good change clears the line
  f.calls.length = 0;
  const g = fakeApi({ "POST /api/theme": (b) => ({ theme: b.theme }) });
  const q = page();
  T.wire(q.doc, { api: g.api });
  q.ids["theme-said"].textContent = T.NOT_SAVED;
  q.ids["theme-pick"].value = "light";
  await q.ids["theme-pick"].fire("change")[0];
  assert.equal(q.ids["theme-said"].textContent, "");
});

test("a settings import's answer line makes the page read the choice again", async () => {
  let stored = "dark";
  const p = page();
  const f = fakeApi({ "GET /api/theme": () => ({ theme: stored }) });
  T.wire(p.doc, { api: f.api });
  await settle();
  assert.equal(p.observers.length, 1);
  const ob = p.observers[0];
  assert.equal(ob.target, p.ids["settings-said"]);
  assert.deepEqual(ob.init, { childList: true, characterData: true, subtree: true });
  // the import clears the line first: no read for an empty line
  ob.cb();
  await settle();
  assert.equal(f.calls.length, 1);
  stored = "light";
  p.ids["settings-said"].textContent = "Imported 3 settings.";
  ob.cb();
  await settle();
  assert.equal(f.calls.length, 2);
  assert.equal(p.root.getAttribute("data-theme"), "light");
});

test("wire needs ctx.api and a page; without an observer it still wires", async () => {
  T.wire(null, { api: () => Promise.resolve({}) });
  const p = page();
  T.wire(p.doc, {});
  T.wire(p.doc, null);
  assert.equal(p.root.getAttribute("data-theme"), "dark");
  const q = page({ noObserver: true });
  const f = fakeApi({ "GET /api/theme": { theme: "light" } });
  T.wire(q.doc, { api: f.api });
  await settle();
  assert.equal(q.root.getAttribute("data-theme"), "light");
});

/* ------------------------------------------------- the page and its CSS */

test("the page ships dark and loads theme.css and theme.js in order", () => {
  assert.match(HTML, /^<!doctype html>\n<html lang="en" data-theme="dark">\n/);
  const css = HTML.indexOf('<link rel="stylesheet" href="/web/theme.css">');
  assert.ok(css > HTML.indexOf('<link rel="stylesheet" href="/web/app.css">'), "theme.css after app.css");
  const js = HTML.indexOf('<script src="/web/theme.js" defer></script>');
  assert.ok(js > HTML.indexOf('<script src="/web/registry.js" defer></script>'), "a page script");
  // with the Settings scripts, before the region files' run from slots.js
  assert.ok(js < HTML.indexOf('<script src="/web/slots.js" defer></script>'), "before slots.js");
  assert.equal(HTML.split("/web/theme.js").length, 2);
});

test("in the page theme.js registers on the region registry once it exists", () => {
  const vm = require("node:vm");
  const registered = [];
  const listeners = {};
  const win = { document: { addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); } } };
  vm.runInNewContext(THEME_SRC, { self: win });
  assert.equal(typeof win.ALTheme.wire, "function");
  assert.equal((listeners.DOMContentLoaded || []).length, 1, "waits for the registry");
  win.ALRegions = { register: (spec) => registered.push(spec.name) };
  listeners.DOMContentLoaded[0]();
  listeners.DOMContentLoaded[0]();
  assert.deepEqual(registered, ["theme"], "registered once");
  // a registry already there: registered at load, no listener
  const reg2 = [];
  const l2 = {};
  const w2 = { ALRegions: { register: (spec) => reg2.push(spec.name) },
    document: { addEventListener: (t, fn) => { l2[t] = fn; } } };
  vm.runInNewContext(THEME_SRC, { self: w2 });
  assert.deepEqual(reg2, ["theme"]);
  assert.equal(l2.DOMContentLoaded, undefined);
});

test("the Theme row is in Appearance and tools with the three choices", () => {
  const start = HTML.indexOf('<section id="toolsbox"');
  const end = HTML.indexOf("</section>", start);
  const tools = HTML.slice(start, end);
  const row = tools.indexOf('id="theme-row"');
  assert.ok(row > 0, "the Theme row is in the toolsbox section");
  assert.ok(row < tools.indexOf('id="settingsbox"'), "it is the first row");
  assert.match(tools, /<label for="theme-pick">Theme<\/label>/);
  assert.match(tools, /<select id="theme-pick" aria-describedby="theme-help theme-said">/);
  assert.match(tools, /<p id="theme-help" class="muted small">Follow Windows uses your Windows light or dark setting\.<\/p>/);
  const opts = [...tools.matchAll(/<option value="([a-z]+)">([^<]+)<\/option>/g)].map((m) => [m[1], m[2]]);
  assert.deepEqual(opts, [["dark", "Dark"], ["system", "Follow Windows"], ["light", "Light"]]);
  assert.match(tools, /<span id="theme-said" class="muted"><\/span>/);
  assert.ok(!/id="theme-said"[^>]*aria-live/.test(tools), "no live region");
});

test("theme.css holds the colour scheme per theme and no colour", () => {
  const rules = {};
  for (const m of THEME_CSS.matchAll(/([^{}]+)\{\s*color-scheme:\s*([a-z ]+);\s*\}/g)) {
    rules[m[1].replace(/\/\*[\s\S]*?\*\//g, "").trim()] = m[2].trim();
  }
  assert.deepEqual(rules, { ':root[data-theme="dark"]': "dark",
    ':root[data-theme="light"]': "light", ":root:not([data-theme])": "light dark" });
  assert.doesNotMatch(THEME_CSS, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i);
  assert.match(APP_CSS, /html \{ color-scheme: light dark; \}/, "app.css untouched");
});

/* Resolve a custom property of the root from the kit tokens the way a
   browser does for the three selector shapes the kit uses (:root,
   :root[data-theme="x"], :root:not([data-theme="x"])) inside an optional
   prefers-color-scheme block: specificity first, then source order. */
function resolveToken(css, name, attr, scheme) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules = [];
  const re = /@media\s*\(prefers-color-scheme:\s*(dark|light)\)\s*\{|([^{}@]+)\{([^{}]*)\}|\}/g;
  let media = null;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m[1]) { media = m[1]; continue; }
    if (m[2] === undefined) { media = null; continue; }
    rules.push({ sel: m[2].trim(), body: m[3], media: media, order: rules.length });
  }
  function matches(sel) {
    if (!sel.startsWith(":root")) { return false; }
    let rest = sel.slice(5);
    let spec = 1;
    while (rest) {
      let k = /^:not\(\[data-theme="(\w+)"\]\)/.exec(rest);
      if (k) { if (attr === k[1]) { return false; } spec += 1; rest = rest.slice(k[0].length); continue; }
      k = /^\[data-theme="(\w+)"\]/.exec(rest);
      if (k) { if (attr !== k[1]) { return false; } spec += 1; rest = rest.slice(k[0].length); continue; }
      return false;
    }
    return spec;
  }
  let best = null;
  for (const r of rules) {
    if (r.media && r.media !== scheme) { continue; }
    const spec = matches(r.sel);
    if (!spec) { continue; }
    const d = new RegExp("(?:^|;)\\s*" + name + ":\\s*([^;]+)").exec(r.body);
    if (!d) { continue; }
    if (!best || spec > best.spec || (spec === best.spec && r.order > best.order)) {
      best = { spec: spec, order: r.order, value: d[1].trim() };
    }
  }
  return best ? best.value : null;
}

function rgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return "rgb(" + [(n >> 16) & 255, (n >> 8) & 255, n & 255].join(", ") + ")";
}

test("the page background computes dark under a light browser unless Light is chosen", () => {
  assert.match(APP_CSS, /body \{[^}]*background: var\(--fk-surface\);/);
  const bg = (attr, scheme) => rgb(resolveToken(KIT_CSS, "--fk-surface", attr, scheme));
  // shipped: data-theme="dark", whatever the browser says
  assert.equal(bg("dark", "light"), "rgb(15, 18, 22)");
  assert.equal(bg("dark", "dark"), "rgb(15, 18, 22)");
  // Theme Light
  assert.equal(bg("light", "light"), "rgb(255, 255, 255)");
  assert.equal(bg("light", "dark"), "rgb(255, 255, 255)");
  // Follow Windows (no attribute): the browser decides
  assert.equal(bg(null, "light"), "rgb(255, 255, 255)");
  assert.equal(bg(null, "dark"), "rgb(15, 18, 22)");
  // AshLight's own body text token follows the same selectors
  assert.equal(resolveToken(APP_CSS, "--al-text-body", "dark", "light"), "#c5ccd3");
  assert.equal(resolveToken(APP_CSS, "--al-text-body", "light", "dark"), "#30353c");
});

/* ------------------------------------------------- the desktop client */

function fakeHttp(reply) {
  const seen = [];
  return {
    seen,
    request(opts, cb) {
      seen.push(opts);
      const req = new EventEmitter();
      req.end = () => {
        setImmediate(() => {
          if (reply.error) { req.emit("error", new Error("refused")); return; }
          const res = new EventEmitter();
          res.statusCode = reply.status;
          cb(res);
          for (const c of reply.chunks || []) { res.emit("data", Buffer.from(c)); }
          res.emit("end");
        });
      };
      req.destroy = () => {};
      return req;
    }
  };
}

test("the client's theme source comes only from a known answer", () => {
  assert.deepEqual([...ClientWin.THEME_SOURCES], ["dark", "system", "light"]);
  assert.equal(ClientWin.THEME_PATH, "/api/theme");
  assert.equal(ClientWin.themeSourceOf({ theme: "system" }), "system");
  assert.equal(ClientWin.themeSourceOf({ theme: "light" }), "light");
  for (const bad of [null, undefined, "dark", ["dark"], { theme: "Dark" }, { theme: 1 }, {}]) {
    assert.equal(ClientWin.themeSourceOf(bad), null);
  }
});

test("the client reads /api/theme with the verified token only", async () => {
  const ok = fakeHttp({ status: 200, chunks: ['{"theme": "li', 'ght", "choices": []}'] });
  assert.equal(await ClientWin.makeThemeReader(ok, 8961, () => "tok")(), "light");
  assert.deepEqual(ok.seen[0], { host: "127.0.0.1", port: 8961, path: "/api/theme", method: "GET",
    timeout: 3000, headers: { "X-AL-Token": "tok" } });
  // no verified token: nothing is sent
  const none = fakeHttp({ status: 200, chunks: ['{"theme": "light"}'] });
  assert.equal(await ClientWin.makeThemeReader(none, 8961, () => "")(), null);
  assert.equal(none.seen.length, 0);
  // a refusal, junk, an unknown choice, a huge answer or a socket error: null
  const cases = [{ status: 401, chunks: ['{"theme": "light"}'] }, { status: 200, chunks: ["{nope"] },
    { status: 200, chunks: ['{"theme": "blue"}'] }, { status: 200, chunks: ["x".repeat(5000)] },
    { error: true }];
  for (const c of cases) {
    assert.equal(await ClientWin.makeThemeReader(fakeHttp(c), 8961, () => "tok")(), null);
  }
});

test("the client sets its native theme from the choice on load and on the watch", () => {
  const c = WIN_SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  const sets = c.match(/nativeTheme|\.themeSource\s*=/g) || [];
  assert.deepEqual(sets, ["nativeTheme", ".themeSource ="], "one assignment, in syncTheme");
  assert.match(c, /function syncTheme\(\) \{\s*const nt = opts\.electron\.nativeTheme;[\s\S]*?readTheme\(\)\.then\(\(source\) => \{\s*if \(source && nt\.themeSource !== source\) \{\s*nt\.themeSource = source;/);
  assert.match(c, /const readTheme = makeThemeReader\(http, port, opts\.readToken\);/);
  assert.match(c, /if \(dashboard\) \{ syncTheme\(\); \}/);
  assert.match(c, /if \(r === "ok" && win && !win\.isDestroyed\(\)\) \{ syncTheme\(\); \}/);
  // the window still opens on the kit's dark surface (TD-04A)
  assert.match(c, /backgroundColor: "#0f1216"/);
});
