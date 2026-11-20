/* TEST-WEB-REGISTRY (F-135): web/registry.js runs the dashboard's panels
   in their order with a try / catch per panel; web/app.js registers one
   entry per paint, tick and wire it used to call in one sequence. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const web = require("./_web.js");
const R = web.load("registry.js");

const HTML = web.source("index.html");
const APP = web.source("app.js");
const SRC = web.source("registry.js");

function quiet() {
  const said = [];
  return { reg: R.create({ warn: (t) => said.push(t) }), said };
}

test("the page build exports one shared registry and a factory", () => {
  for (const k of ["register", "render", "tick", "start", "names", "create"]) {
    assert.equal(typeof R[k], "function", k);
  }
  const a = R.create();
  const b = R.create();
  a.register({ name: "x", order: 1, paint() {} });
  assert.deepEqual(a.names(), ["x"]);
  assert.deepEqual(b.names(), []);
});

test("panels run in order; equal orders keep register order", () => {
  const { reg } = quiet();
  const ran = [];
  const panel = (name, order) => ({
    name, order,
    paint: (s) => ran.push("p:" + name + ":" + s),
    tick: (s, now) => ran.push("t:" + name + ":" + now),
    wire: (ctx) => ran.push("w:" + name + ":" + ctx)
  });
  reg.register(panel("c", 30));
  reg.register(panel("a", 10));
  reg.register(panel("b1", 20));
  reg.register(panel("b2", 20));
  reg.register(panel("neg", -5));
  assert.deepEqual(reg.names(), ["neg", "a", "b1", "b2", "c"]);
  reg.start("ctx");
  reg.render("s");
  reg.tick("s", 7);
  assert.deepEqual(ran, [
    "w:neg:ctx", "w:a:ctx", "w:b1:ctx", "w:b2:ctx", "w:c:ctx",
    "p:neg:s", "p:a:s", "p:b1:s", "p:b2:s", "p:c:s",
    "t:neg:7", "t:a:7", "t:b1:7", "t:b2:7", "t:c:7"]);
});

test("render passes every argument through to each paint", () => {
  const { reg } = quiet();
  const got = [];
  reg.register({ name: "one", order: 1, paint: (...a) => got.push(a) });
  reg.render({ v: 1 }, { level: 3 });
  assert.deepEqual(got, [[{ v: 1 }, { level: 3 }]]);
});

test("a throwing paint is caught, said once, and later panels still paint", () => {
  const { reg, said } = quiet();
  const ran = [];
  reg.register({ name: "first", order: 1, paint: () => ran.push("first") });
  reg.register({ name: "broken", order: 2, paint: () => { throw new Error("boom"); } });
  reg.register({ name: "after", order: 3, paint: () => ran.push("after") });
  reg.render({});
  reg.render({});
  reg.render({});
  assert.deepEqual(ran, ["first", "after", "first", "after", "first", "after"]);
  assert.deepEqual(said, ["panel broken paint failed: boom"]);
});

test("a throwing tick or wire is isolated the same way, per phase", () => {
  const { reg, said } = quiet();
  const ran = [];
  reg.register({
    name: "bad", order: 1,
    tick: () => { throw new Error("t"); },
    wire: () => { throw new TypeError("w"); }
  });
  reg.register({ name: "good", order: 2, tick: () => ran.push("tick"), wire: () => ran.push("wire") });
  reg.start();
  reg.tick();
  reg.tick();
  assert.deepEqual(ran, ["wire", "tick", "tick"]);
  assert.deepEqual(said, ["panel bad wire failed: w", "panel bad tick failed: t"]);
});

test("a new cause is said again; the console gets at most 20 lines a page", () => {
  const { reg, said } = quiet();
  let n = 0;
  reg.register({ name: "noisy", order: 1, paint: () => { n += 1; throw new Error("cause " + n); } });
  for (let i = 0; i < 50; i++) { reg.render(); }
  assert.equal(n, 50);
  assert.equal(said.length, 20);
  assert.equal(said[0], "panel noisy paint failed: cause 1");
  assert.equal(said[19], "panel noisy paint failed: cause 20");
  // a non-Error throw is said by its text
  const q = quiet();
  q.reg.register({ name: "odd", order: 1, paint: () => { throw "plain"; } });
  q.reg.render();
  assert.deepEqual(q.said, ["panel odd paint failed: plain"]);
});

test("a duplicate name is refused and the first panel stays", () => {
  const { reg } = quiet();
  const ran = [];
  reg.register({ name: "zone", order: 1, paint: () => ran.push("one") });
  assert.throws(() => reg.register({ name: "zone", order: 2, paint: () => ran.push("two") }),
    { name: "TypeError", message: /zone is registered twice/ });
  assert.deepEqual(reg.names(), ["zone"]);
  reg.render();
  assert.deepEqual(ran, ["one"]);
});

test("a spec needs a name, a number order and at least one function", () => {
  const { reg } = quiet();
  [null, undefined, "x", {}, { name: "" }, { name: 3, order: 1, paint() {} }].forEach((bad) => {
    assert.throws(() => reg.register(bad), TypeError, JSON.stringify(bad));
  });
  [undefined, "1", NaN, Infinity, null].forEach((order) => {
    assert.throws(() => reg.register({ name: "o", order, paint() {} }), /needs a number order/);
  });
  assert.throws(() => reg.register({ name: "none", order: 1 }), /no paint, tick or wire/);
  assert.throws(() => reg.register({ name: "none", order: 1, paint: "x" }), /no paint, tick or wire/);
  assert.deepEqual(reg.names(), []);
});

test("tick and wire are optional, and so is paint", () => {
  const { reg, said } = quiet();
  const ran = [];
  assert.equal(reg.register({ name: "paintOnly", order: 1, paint: () => ran.push("p") }), "paintOnly");
  reg.register({ name: "tickOnly", order: 2, tick: () => ran.push("t") });
  reg.register({ name: "wireOnly", order: 3, wire: () => ran.push("w") });
  reg.start();
  reg.render();
  reg.tick();
  assert.deepEqual(ran, ["w", "p", "t"]);
  assert.deepEqual(said, []);
});

test("start wires once; a panel registered after start is wired at once", () => {
  const { reg } = quiet();
  const ran = [];
  reg.register({ name: "early", order: 5, wire: (c) => ran.push("early:" + c) });
  reg.start("ctx");
  reg.start("again");
  assert.deepEqual(ran, ["early:ctx"]);
  reg.register({ name: "late", order: 1, wire: (c) => ran.push("late:" + c), paint: () => ran.push("p") });
  assert.deepEqual(ran, ["early:ctx", "late:ctx"]);
  reg.render();
  assert.deepEqual(ran, ["early:ctx", "late:ctx", "p"]);
});

test("a panel registering during a loop runs from the next loop on", () => {
  const { reg } = quiet();
  const ran = [];
  reg.register({
    name: "maker", order: 1,
    paint: () => {
      ran.push("maker");
      if (reg.names().length === 1) { reg.register({ name: "made", order: 0, paint: () => ran.push("made") }); }
    }
  });
  reg.render();
  reg.render();
  assert.deepEqual(ran, ["maker", "made", "maker"]);
});

test("registry.js is the page's second script, pure and ASCII", () => {
  const scripts = [...HTML.matchAll(/<script src="\/web\/([a-z]+)\.js" defer><\/script>/g)].map((m) => m[1]);
  assert.deepEqual(scripts.slice(0, 2), ["fmt", "registry"]);
  assert.ok(scripts.indexOf("registry") < scripts.indexOf("app"));
  assert.doesNotMatch(SRC, /[^\x0a\x20-\x7e]/);
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "setTimeout", "requestAnimationFrame", "fetch(",
    "XMLHttpRequest", "EventSource", "clipboard", "document", "innerHTML", "aria-live"]) {
    assert.ok(!code.includes(bad), bad);
  }
});

/* Run web/app.js against a fake page that never starts, so only its
   registrations happen; the panels land in the shared-registry slot. */
function appRegistry() {
  const reg = R.create({ warn() {} });
  const noop = () => {};
  const win = {
    ALApp: reg,
    ALDash: {},
    ALFmt: { duration: noop, clock: noop, pad: noop },
    ALTc: {},
    ALPrices: {}
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

// today's paint sequence (the live regions announce in this order), then
// the wire-only tools and settings
const PANELS = ["build", "eval", "price", "chars", "pace", "consent", "reading",
  "events", "acts", "runs", "summary", "zonenote", "history", "pricewatch", "hints",
  "checks", "zoneguide", "layout", "filter", "weights", "gfx", "restart-overlay", "webdata",
  "settingsio"];

test("app.js registers its panels in today's order", () => {
  const reg = appRegistry();
  assert.deepEqual(reg.names(), PANELS);
});

test("app.js keeps today's tick order: clocks, act split, map time, tip", () => {
  const reg = appRegistry();
  const order = [...APP.matchAll(/A\.register\(\{\s*name: "([a-z-]+)",\s*order: (\d+),([\s\S]*?)\n  \}\);/g)]
    .filter((m) => /\n    tick: function/.test(m[3])).map((m) => m[1]);
  assert.deepEqual(order, ["acts", "runs", "hints"]);
  assert.deepEqual(reg.names().filter((n) => order.includes(n)), order);
});

test("render, tick and start are loops over the registry", () => {
  function body(name) {
    const at = APP.indexOf("  function " + name + "() {") >= 0
      ? APP.indexOf("  function " + name + "() {") : APP.indexOf("  function " + name + "(s) {");
    assert.ok(at >= 0, name);
    return APP.slice(at, APP.indexOf("\n  }\n", at));
  }
  const render = body("render");
  const tick = body("tick");
  const start = body("start");
  assert.match(render, /A\.render\(s, charView\(s\)\);/);
  assert.match(tick, /A\.tick\(snap, now, until\);/);
  assert.match(start, /A\.start\(\);/);
  // no panel is called by name from the three loops any more
  for (const src of [render, tick, start]) {
    for (const name of ["ALActs", "ALRuns", "ALHints", "ALChars", "ALHistory", "ALPriceWatch",
      "ALChecks", "ALZoneGuide", "ALSummary", "ALBuildLive", "ALSettingsIO",
      "renderEval", "renderPrice", "renderEvents", "renderTrades", "renderBuildYou"]) {
      assert.ok(!src.includes(name), name);
    }
  }
  assert.match(APP, /var A = window\.ALApp;/);
});
