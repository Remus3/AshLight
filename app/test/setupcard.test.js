/* PLAY-TD-12-CONTEXT-SETUP (web/setupcard.js, TD-12, F-069, F-068): region
   C's setup, error and idle modes. A cold profile shows the setup card
   with its 4 step rows and exactly one button.primary (the floor's opt-in
   words); the click posts /api/consent through ctx.api and the card
   leaves; idle shows "Last session" only while game_idle; error names an
   in-app control (Open Checks), never a file or a shell command; each
   mode fits region C's track in the full and compact classes. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../../web/context.js");
const S = require("../../web/slots.js");
const U = require("../../web/setupcard.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "setupcard.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "setupcard.css"), "utf8");
const APPCSS = fs.readFileSync(path.join(WEB, "app.css"), "utf8");
const CTXCSS = fs.readFileSync(path.join(WEB, "context.css"), "utf8");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");

/* A small DOM: ids, attributes, classes, children, hidden, click. */
function makeDoc() {
  const doc = { all: [], byId: {}, focused: null };
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], parentNode: null,
      hidden: false, listeners: {}, _text: "",
      get textContent() {
        return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
      },
      set textContent(v) { this.children = []; this._text = String(v); },
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); doc.byId[v] = this; },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) { if (k === "id") { this.id = v; return; } this.attrs[k] = String(v); },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      replaceChildren() { this.children = []; this._text = ""; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ type: "click" })); },
      focus() { doc.focused = this; }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-c [data-slot="c"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.getAttribute(m[1]) !== null) : [];
  };
  const region = elem("section");
  region.id = "play-c";
  const h = region.appendChild(elem("h2"));
  h.id = "play-c-h";
  h.textContent = "Right now";
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "c");
  doc.setup = region.appendChild(elem("div"));
  doc.setup.setAttribute("data-legacy", "c-setup");
  doc.region = region;
  const checks = elem("details");
  checks.id = "checks";
  checks.open = false;
  const sum = elem("summary");
  sum.id = "checks-summary";
  return doc;
}

function walk(n, out) {
  out = out || [];
  out.push(n);
  n.children.forEach((c) => walk(c, out));
  return out;
}
function visible(n) {
  for (let p = n; p; p = p.parentNode) { if (p.hidden) { return false; } }
  return true;
}
function find(doc, pred) { return walk(doc.region).filter((n) => pred(n) && visible(n)); }
function hasClass(n, cls) { return n.className.split(" ").indexOf(cls) >= 0; }
function byClass(doc, cls) { return find(doc, (n) => hasClass(n, cls)); }
function buttons(doc) { return find(doc, (n) => n.tagName === "BUTTON"); }
function primaries(doc) { return buttons(doc).filter((b) => hasClass(b, "primary")); }
function words(t) { return t.split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w)).length; }
function shownText(doc) { return find(doc, () => true).map((n) => n._text).join(" "); }

/* the line box of each rendered row (px at s = 1, design 0001 section 3) */
function rowPx(n) {
  if (hasClass(n, "su-act")) { return 36; }
  if (hasClass(n, "row-meta")) { return 20; }
  return 22;
}
function contentPx(doc, compact) {
  const pane = byClass(doc, "ctx-pane")[0];
  let px = 26;
  byClass(doc, "su-rows")[0].children.forEach((r) => { px += rowPx(r); });
  const facts = pane.children.filter((n) => hasClass(n, "su-facts"));
  facts.forEach((f) => { if (!(compact && hasClass(f, "su-promise"))) { px += 20; } });
  return px;
}

/* -- fixtures: snapshots as the core sends them (server/al/playcards.py) -- */

function setupBlock(over) {
  const o = Object.assign({ build: false, prices: false, overlay: null, path: "Client.txt" }, over);
  const step = (label, done, yes, no) => ({ kind: "step", text: label + ": " + (done ? yes : no),
    state: done ? "done" : "pending", glyph: done ? "[+]" : "[ ]" });
  return {
    mode: "setup", title: "Set up AshLight", full: "Set up AshLight",
    rows: [
      { kind: "step", text: "Let AshLight read the game's log, read only:", state: "pending",
        glyph: "[ ]", step: "log" },
      o.path ? { kind: "path", text: o.path, full: o.path }
        : { kind: "path", text: "Client.txt not found yet. Start the game once.",
          full: "Client.txt not found yet. Start the game once." },
      { kind: "button", text: "Allow reading Client.txt", action: "consent" },
      step("Your build", o.build, "loaded", "not set, optional"),
      step("Prices", o.prices, "on", "off, optional"),
      Object.assign(step("Overlay", o.overlay === true, "on",
        o.overlay === false ? "off, optional" : "not running, optional"), {})
    ],
    facts: "Read only. AshLight never touches the game."
  };
}

function coldSnap(over) {
  return Object.assign({
    tailer: { consented: false, reading: false, path: "Client.txt" }, game_idle: false,
    zone: null, maps: { count: 0 }, build: { loaded: false },
    play: { map_ok: false, context: { setup: setupBlock() } }
  }, over || {});
}

const IDLE_BLOCK = {
  mode: "idle", title: "Last session", full: "Last session",
  rows: [{ kind: "text", text: "Played: 1:12:05" }, { kind: "text", text: "Level: 4 to 9" },
    { kind: "text", text: "Pace: 4.2 levels an hour" }, { kind: "text", text: "Maps: 0" },
    { kind: "text", text: "Deaths: 1" }, { kind: "text", text: "Price movers: Divine Orb up" }],
  facts: "Ended 14:05 after 20 minutes of quiet"
};

function liveSnap(over) {
  return Object.assign({
    tailer: { consented: true, reading: true, path: "Client.txt" }, game_idle: false,
    zone: "Clearfell", area_id: "G1_2", area_level: 3, maps: { count: 0 }, in_hideout: false,
    session_summary: { lines: ["Played 1:12:05."], ended_at: 1 },
    play: { map_ok: false, context: {} }
  }, over || {});
}

function idleSnap() {
  return liveSnap({ game_idle: true, play: { map_ok: false, context: { idle: IDLE_BLOCK } } });
}

function errorSnap() {
  return {
    tailer: { consented: true, reading: false, path: "Client.txt", last_reset: "missing" },
    game_idle: false, zone: null, maps: { count: 0 }, play: { map_ok: false, context: {} }
  };
}

function fresh() {
  C.reset();
  U.reset();
  assert.equal(U.install(C), true, "the three painters register on ALContext");
  return makeDoc();
}

/* -- tests ------------------------------------------------------------------ */

test("registers as region C, retires the legacy c-setup group and paints 3 modes", () => {
  assert.deepEqual(U.spec.region, "c");
  assert.deepEqual(U.spec.retires, ["c-setup"]);
  assert.equal(U.spec.name, "setupcard");
  assert.deepEqual(U.MODES, ["setup", "error", "idle"]);
  fresh();
  for (const m of U.MODES) { assert.equal(C.hasPainter(m), true, m); }
  assert.equal(U.install(null), false);
  // the page loads setupcard after context (deferred, in document order)
  const ctxAt = HTML.indexOf('<script src="/web/context.js" defer></script>');
  const suAt = HTML.indexOf('<script src="/web/setupcard.js" defer></script>');
  assert.ok(ctxAt > 0 && suAt > ctxAt, "setupcard.js loads after context.js");
  assert.match(HTML, /<link rel="stylesheet" href="\/web\/setupcard\.css">/);
});

test("a cold profile shows the 4 setup rows and exactly one button.primary", () => {
  const doc = fresh();
  const m = C.paint(doc, coldSnap(), 0, {});
  assert.equal(m.mode, "setup");
  assert.equal(byClass(doc, "su-title")[0].textContent, "Set up AshLight");
  const steps = byClass(doc, "su-row").filter((r) => r.getAttribute("data-kind") === "step");
  assert.equal(steps.length, 4, "log, build, prices, overlay");
  assert.equal(byClass(doc, "su-glyph").length, 4, "each step has its state glyph");
  assert.equal(buttons(doc).length, 1, "the opt-in is the one control");
  assert.equal(primaries(doc).length, 1);
  assert.equal(primaries(doc)[0].textContent, "Allow reading Client.txt");
  assert.equal(byClass(doc, "su-path")[0].textContent, "Client.txt");
  assert.equal(byClass(doc, "su-promise").length, 1, "the promise line");
  assert.equal(doc.setup.hidden, true, "the legacy consent card is hidden");
  // the 3 optional rows clear themselves when their data arrives: no control
  const done = coldSnap({ play: { map_ok: false, context: {
    setup: setupBlock({ build: true, prices: true, overlay: true }) } } });
  C.paint(doc, done, 0, {});
  const states = byClass(doc, "su-row").map((r) => r.getAttribute("data-state"));
  assert.deepEqual(states, ["pending", "done", "done", "done"]);
  assert.equal(buttons(doc).length, 1);
  // G5: region C's words, its hidden heading counted
  assert.ok(words(shownText(doc)) + 2 <= 52, "52 words");
});

test("no setup block: the same words, the path and the one button", () => {
  const doc = fresh();
  const snap = coldSnap({ tailer: { consented: false, reading: false, path: "" },
    play: { map_ok: false, context: null } });
  C.paint(doc, snap, 0, {});
  assert.equal(byClass(doc, "su-title")[0].textContent, "Set up AshLight");
  assert.equal(byClass(doc, "su-path")[0].textContent,
    "Client.txt not found yet. Start the game once.");
  assert.equal(primaries(doc).length, 1);
  // a long path keeps its end
  const long = "Games\\".repeat(13) + "logs\\Client.txt";
  C.paint(doc, coldSnap({ tailer: { consented: false, reading: false, path: long },
    play: { map_ok: false, context: null } }), 0, {});
  const p = byClass(doc, "su-path")[0];
  assert.ok(p.textContent.endsWith("Client.txt") && p.textContent.length <= 52);
  assert.equal(p.getAttribute("title"), long);
});

test("the opt-in posts /api/consent through ctx.api, then the feed is live and the card leaves", async () => {
  const doc = fresh();
  const calls = [];
  const after = liveSnap({ zone: null, tailer: { consented: true, reading: true, path: "Client.txt" } });
  const ctx = {
    api: (method, url, body) => { calls.push([method, url, body]); return Promise.resolve({ state: after }); },
    serverNow: () => 5, tabs: null
  };
  C.paint(doc, coldSnap(), 0, ctx);
  primaries(doc)[0].click();
  primaries(doc)[0].click(); // a second click while the first is in flight does nothing
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(calls, [["POST", "/api/consent", { consent: true }]]);
  assert.equal(primaries(doc).length, 0, "the setup card left");
  assert.equal(byClass(doc, "su-title").length, 0);
  assert.equal(doc.focused, doc.getElementById("play-c-h"), "focus lands on the region heading");
  assert.equal(S.contextMode(after), "none");
});

test("a refused opt-in says so beside the button and keeps the card", async () => {
  const doc = fresh();
  const ctx = { api: () => Promise.reject(new Error("HTTP 500")) };
  C.paint(doc, coldSnap(), 0, ctx);
  primaries(doc)[0].click();
  await new Promise((r) => setImmediate(r));
  const said = byClass(doc, "su-said")[0];
  assert.equal(said.textContent, U.NOT_SAVED);
  assert.equal(said.getAttribute("role"), "status");
  assert.equal(primaries(doc).length, 1);
});

test("idle shows Last session only while game_idle", () => {
  const doc = fresh();
  let m = C.paint(doc, idleSnap(), 0, {});
  assert.equal(m.mode, "idle");
  assert.equal(byClass(doc, "su-title")[0].textContent, "Last session");
  assert.equal(byClass(doc, "su-row").length, 6);
  assert.equal(byClass(doc, "su-facts")[0].textContent, IDLE_BLOCK.facts);
  assert.equal(buttons(doc).length, 0);
  // the same summary with the game running: not idle, no Last session
  m = C.paint(doc, liveSnap({ zone_guide: null }), 0, {});
  assert.notEqual(m.mode, "idle");
  assert.ok(!/Last session/.test(shownText(doc)), "Last session leaves with game_idle");
  // idle with no block still says something
  const bare = liveSnap({ game_idle: true });
  C.paint(doc, bare, 0, {});
  assert.equal(byClass(doc, "su-title")[0].textContent, "Last session");
  assert.equal(byClass(doc, "su-row").length, 1);
});

test("error names Open Checks, never a file to edit or a shell command", () => {
  const doc = fresh();
  const shown = [];
  const ctx = { tabs: { show: (d, id, focus) => shown.push([id, focus]) } };
  const checks = doc.getElementById("checks");
  const m = C.paint(doc, errorSnap(), 0, ctx);
  assert.equal(m.mode, "error");
  assert.equal(byClass(doc, "su-title")[0].textContent, "Can't read Client.txt");
  assert.equal(byClass(doc, "su-row").length, 5, "2 rows wrong, 3 rows doing / to do");
  assert.equal(buttons(doc).length, 1);
  assert.equal(primaries(doc).length, 0, "the one filled button is the opt-in only");
  const btn = buttons(doc)[0];
  assert.equal(btn.textContent, "Open Checks");
  btn.click();
  assert.deepEqual(shown, [["settings", false]]);
  assert.equal(checks.open, true);
  assert.equal(doc.focused, doc.getElementById("checks-summary"));
  for (const kind of Object.keys(U.ERRORS)) {
    const e = U.ERRORS[kind];
    const text = [e.title].concat(e.rows).join(" ");
    assert.doesNotMatch(text, /\.(ps1|json|py|cmd|bat|exe)\b|\\|\/|python|powershell|local\.json/i, kind);
    assert.equal(e.rows.length, 5, kind);
    e.rows.forEach((r) => assert.ok(r.length <= 52, r));
    assert.ok(e.title.length <= 38, e.title);
    assert.ok(words(text) + 2 + 2 <= 52, kind + ": 52 words with the button and heading");
  }
  assert.equal(U.errorKind(null), "lost");
  assert.equal(U.errorKind({ offline: true }), "lost");
  assert.equal(U.errorKind({ tailer: { consented: true, reading: false, path: "" } }), "nopath");
});

test("region C fits its track in setup, error and idle modes (full and compact)", () => {
  for (const cls of ["full", "compact"]) {
    for (const mode of ["setup", "error", "idle"]) {
      const lay = S.layout({ mode }, cls);
      assert.ok(lay.regions.c.slack >= 2, `${mode} ${cls}: slack ${lay.regions.c.slack}`);
    }
  }
  // the rendered rows match the line arithmetic of web/slots.js
  const inner = { full: 228 - 2 - 20, compact: 212 - 2 - 20 }; // context.css pads 10
  for (const [snap, want] of [[coldSnap(), { full: 190, compact: 170 }],
    [errorSnap(), { full: 172, compact: 172 }], [idleSnap(), { full: 178, compact: 178 }]]) {
    const doc = fresh();
    C.paint(doc, snap, 0, {});
    for (const cls of ["full", "compact"]) {
      const px = contentPx(doc, cls === "compact");
      assert.equal(px, want[cls], `${S.contextMode(snap)} ${cls}`);
      assert.ok(inner[cls] - px >= 2, `${S.contextMode(snap)} ${cls}: slack`);
    }
  }
  assert.equal(S.trackSet("full").setupPromise, true);
  assert.equal(S.trackSet("compact").setupPromise, false);
  assert.match(CSS, /min-height: 2\.25rem;/, "the button row is 36 px");
  assert.match(CSS, /gap: 0;/);
  assert.match(CTXCSS, /--region-pad: var\(--al-space-2\);/);
  // the compact class drops the promise line exactly where app.css's
  // track tokens switch to compact
  const css = (t) => [...t.matchAll(/@media \(min-width: ([\d.]+em)\) and \(min-height: ([\d.]+em)\)/g)]
    .map((x) => x[1] + "/" + x[2]);
  const ours = css(CSS);
  const theirs = css(APPCSS.slice(APPCSS.indexOf("compact or full per scale step")));
  assert.equal(ours.length, 8);
  assert.deepEqual(ours, theirs.slice(0, ours.length));
  const hides = [...CSS.matchAll(/\.su-promise \{ display: (none|block); \}/g)].map((x) => x[1]);
  assert.deepEqual(hides, ["none", "block", "none", "block", "none", "block", "none", "block"]);
});

test("setupcard.js: no timer, clipboard, game input, innerHTML or notify; ASCII and LF", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "fetch(",
    "XMLHttpRequest", "EventSource", "clipboard", "readText", "innerHTML", "notify", "web_data"]) {
    assert.ok(!code.includes(bad), bad);
  }
  assert.match(code, /c\.api\("POST", "\/api\/consent", \{ consent: true \}\)/);
  assert.match(code, /"Allow reading Client\.txt"/, "the floor's opt-in words");
  for (const [name, text] of [["setupcard.js", SRC], ["setupcard.css", CSS]]) {
    assert.doesNotMatch(text, /[^\x0a\x20-\x7e]/, name + " ASCII and LF");
  }
});
