/* TD-09 region hook (web/regions.js, PLAY-TD-09A-REGION-HOOK): the registry
   keeps register order, isolates a throwing region, retires legacy groups
   and marks a region fit; the page pre-links every region file and app.js
   calls the registry from exactly three places. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const R = web.load("regions.js");

const HTML = web.source("index.html");
const APP = web.source("app.js");
const SRC = web.source("regions.js");

const STUB_JS = ["pager", "textspacing", "strip", "context", "setupcard", "feed",
  "notice", "buildline", "itemcard", "keptchecks"];
// every pre-linked region sheet, in <link> order (they stay linked)
const LINKED_CSS = ["strip", "context", "setupcard", "feed", "notice", "buildline",
  "itemcard", "keptchecks"];
// the sheets still empty stubs: one per line, a comment line between each
// pair, so a region package deletes only its own line
const STUB_CSS = [
  "strip",
  // (one stub per line)
  // (one stub per line)
  "setupcard",
  // (one stub per line)
  // (one stub per line)
  // (one stub per line)
  // (one stub per line)
  // (one stub per line)
];

function node(attrs) {
  return {
    attrs: Object.assign({}, attrs), hidden: false,
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    setAttribute(k, v) { this.attrs[k] = String(v); }
  };
}

function fakeDoc(nodes) {
  return {
    nodes,
    querySelectorAll(sel) {
      const m = /^\[([a-z-]+)\]$/.exec(sel);
      assert.ok(m, "only a bare attribute selector is asked: " + sel);
      return nodes.filter((n) => n.getAttribute(m[1]) !== null);
    }
  };
}

function quiet() {
  const said = [];
  return { reg: R.create({ warn: (t) => said.push(t) }), said };
}

test("the page build exports one shared registry and a factory", () => {
  for (const k of ["register", "start", "paint", "tick", "retire", "names", "create"]) {
    assert.equal(typeof R[k], "function", k);
  }
  const a = R.create();
  const b = R.create();
  a.register({ name: "x" });
  assert.deepEqual(a.names(), ["x"]);
  assert.deepEqual(b.names(), []);
});

test("register: a name is needed and used once", () => {
  const { reg } = quiet();
  assert.throws(() => reg.register(null), TypeError);
  assert.throws(() => reg.register({}), TypeError);
  assert.throws(() => reg.register({ name: "" }), TypeError);
  assert.equal(reg.register({ name: "feed", region: "t" }), "feed");
  assert.throws(() => reg.register({ name: "feed" }), /twice/);
  assert.deepEqual(reg.names(), ["feed"]);
});

test("start, paint and tick run in register order with the app context", () => {
  const { reg } = quiet();
  const calls = [];
  ["g", "c", "t"].forEach((r) => {
    reg.register({
      name: "r-" + r, region: r,
      wire: (doc, ctx) => calls.push(["wire", r, doc, ctx]),
      paint: (doc, snap, now, ctx) => calls.push(["paint", r, snap, now, ctx]),
      tick: (doc, snap, now) => calls.push(["tick", r, snap, now])
    });
  });
  reg.register({ name: "helper", region: null }); // nothing to call
  const doc = fakeDoc([]);
  const ctx = { api: () => null, getSnap: () => null, serverNow: () => 5, tabs: null };
  reg.start(doc, ctx);
  reg.start(doc, ctx); // a second start does nothing
  reg.paint(doc, { v: 1 }, 10);
  reg.tick(doc, { v: 1 }, 11);
  assert.deepEqual(calls.map((c) => c[0] + " " + c[1]), [
    "wire g", "wire c", "wire t", "paint g", "paint c", "paint t", "tick g", "tick c", "tick t"]);
  assert.equal(calls[0][2], doc);
  assert.equal(calls[0][3], ctx);
  assert.deepEqual(calls[3].slice(2), [{ v: 1 }, 10, ctx]);
  assert.deepEqual(calls[6].slice(2), [{ v: 1 }, 11]);
});

test("a throwing region is isolated and said once per phase", () => {
  const { reg, said } = quiet();
  const ran = [];
  reg.register({ name: "a", paint: () => ran.push("a"), tick: () => ran.push("ta") });
  reg.register({
    name: "bad",
    wire: () => { throw new Error("wire broke"); },
    paint: () => { throw new Error("paint broke"); },
    tick: () => { throw new Error("tick broke"); }
  });
  reg.register({ name: "c", paint: () => ran.push("c"), tick: () => ran.push("tc"), wire: () => ran.push("wc") });
  reg.start(fakeDoc([]), {});
  for (let i = 0; i < 3; i++) { reg.paint(null, {}, i); reg.tick(null, {}, i); }
  assert.deepEqual(ran, ["wc", "a", "c", "ta", "tc", "a", "c", "ta", "tc", "a", "c", "ta", "tc"]);
  assert.deepEqual(said, ["region bad wire failed: wire broke",
    "region bad paint failed: paint broke", "region bad tick failed: tick broke"]);
});

test("a new cause is said again; the console gets at most 20 lines", () => {
  const { reg, said } = quiet();
  let n = 0;
  reg.register({ name: "flaky", paint: () => { n += 1; throw new Error("cause " + (n > 2 ? n : 1)); } });
  reg.start(fakeDoc([]), {});
  for (let i = 0; i < 40; i++) { reg.paint(null, {}, i); }
  assert.equal(n, 40);
  assert.equal(said.length, 20);
  assert.equal(said[0], "region flaky paint failed: cause 1");
  assert.equal(said[1], "region flaky paint failed: cause 3");
});

test("retire hides a legacy group; a missing group is a no-op", () => {
  const { reg } = quiet();
  const old1 = node({ "data-legacy": "trade-card" });
  const old2 = node({ "data-legacy": "trade-card" });
  const other = node({ "data-legacy": "events" });
  const doc = fakeDoc([old1, old2, other]);
  reg.retire(doc, "trade-card");
  assert.equal(old1.hidden, true);
  assert.equal(old2.hidden, true);
  assert.equal(other.hidden, false);
  reg.retire(doc, "no-such-group");
  reg.retire(doc, "");
  reg.retire(null, "events");
  reg.retire({}, "events");
  assert.equal(other.hidden, false);
});

test("start retires each region's groups; data-fit=yes once all of a region's are gone", () => {
  const { reg } = quiet();
  const feedOld = node({ "data-legacy": "events" });
  const tradesOld = node({ "data-legacy": "trades" });
  const t = node({ "data-region": "t" });
  const c = node({ "data-region": "c" });
  const g = node({ "data-region": "g" });
  const doc = fakeDoc([feedOld, tradesOld, t, c, g]);
  reg.register({ name: "feed", region: "t", retires: ["events", "trades"] });
  reg.register({ name: "context", region: "c", retires: ["guide"] });
  reg.register({ name: "setup", region: "c", retires: ["consent"] });
  reg.start(doc, {});
  assert.equal(feedOld.hidden, true);
  assert.equal(tradesOld.hidden, true);
  // the guide and consent groups are not on this page: retired as a no-op
  assert.equal(t.getAttribute("data-fit"), "yes");
  assert.equal(c.getAttribute("data-fit"), "yes");
  assert.equal(g.getAttribute("data-fit"), null); // no region registered for g
});

test("retire before start hides the group; data-fit is marked only from start", () => {
  const { reg } = quiet();
  const n = node({ "data-region": "n" });
  const tip = node({ "data-legacy": "tip" });
  const doc = fakeDoc([n, tip]);
  reg.register({ name: "notice", region: "n", retires: ["tip"] });
  reg.retire(doc, "tip"); // before start: hidden, but nothing marked yet
  assert.equal(tip.hidden, true);
  assert.equal(n.getAttribute("data-fit"), null);
  reg.register({ name: "notice-2", region: "n", retires: ["lang"] });
  reg.start(doc, {});
  assert.equal(n.getAttribute("data-fit"), "yes");
});

test("a region registered after start is wired and retired at once", () => {
  const { reg } = quiet();
  const old = node({ "data-legacy": "build-alert" });
  const b = node({ "data-region": "b" });
  const doc = fakeDoc([old, b]);
  const ctx = { tabs: null };
  reg.start(doc, ctx);
  let wired = null;
  reg.register({ name: "buildline", region: "b", retires: ["build-alert"], wire: (d, x) => { wired = [d, x]; } });
  assert.deepEqual(wired, [doc, ctx]);
  assert.equal(old.hidden, true);
  assert.equal(b.getAttribute("data-fit"), "yes");
});

test("regions.js sets no timer, asks no network and writes no clipboard", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "fetch(",
    "XMLHttpRequest", "EventSource", "clipboard", "innerHTML", "aria-live"]) {
    assert.ok(!code.includes(bad), bad);
  }
});

test("the page loads slots, regions, the ten region files and app.js last", () => {
  const scripts = [...HTML.matchAll(/<script src="\/web\/([a-z]+)\.js" defer><\/script>/g)].map((m) => m[1]);
  const at = scripts.indexOf("slots");
  assert.ok(at >= 0, "slots.js tag");
  assert.deepEqual(scripts.slice(at), ["slots", "regions"].concat(STUB_JS, ["app"]));
  assert.equal(scripts[scripts.length - 1], "app");
  const sheets = [...HTML.matchAll(/<link rel="stylesheet" href="\/web\/([a-z]+)\.css">/g)].map((m) => m[1]);
  assert.deepEqual(sheets, ["app"].concat(LINKED_CSS));
});

test("each pre-linked file is an empty stub until its package fills it", () => {
  STUB_JS.forEach((name) => {
    const mod = web.load(name + ".js");
    assert.equal(typeof mod, "object", name);
    const src = web.source(name + ".js");
    assert.match(src, /module\.exports = api;/, name);
    assert.doesNotMatch(src, /[^\x0a\x20-\x7e]/, name + " ASCII and LF");
  });
  STUB_CSS.forEach((name) => {
    const css = web.source(name + ".css");
    assert.equal(css.replace(/\/\*[\s\S]*?\*\//g, "").trim(), "", name + " has no rules yet");
    assert.doesNotMatch(css, /[^\x0a\x20-\x7e]/, name + " ASCII and LF");
  });
});

test("app.js reaches the regions only through the three hook calls", () => {
  const calls = [...APP.matchAll(/window\.ALRegions\.([a-z]+)\(/g)].map((m) => m[1]);
  assert.deepEqual(calls, ["tick", "paint", "start"]);
  assert.match(APP, /ALRegions\.start\(document, \{\s*api: api,\s*getSnap: function \(\) \{ return snap; \},\s*serverNow: serverNow,\s*tabs: window\.ALTabs \|\| null\s*\}\)/);
  // render(): the regions paint after the last legacy painter, before tick()
  assert.match(APP, /ALZoneGuide\.paint\(document, s\); \}\n[^\n]*\n\s*if \(window\.ALRegions\) \{ window\.ALRegions\.paint\(document, s, serverNow\(\)\); \}\n\s*tick\(\);/);
  for (const name of ["ALStrip", "ALContext", "ALSetupCard", "ALFeed", "ALNotice", "ALBuildLine",
    "ALItemCard", "ALKeptChecks", "ALPager", "ALTextSpacing"]) {
    assert.ok(!APP.includes(name), "app.js names no region: " + name);
  }
});
