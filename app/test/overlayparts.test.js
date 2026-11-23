/* OVL-PARTS-WEB (findings F-118, TD-17): the 'Overlay shows' group in
   web/overlayparts.js. It fills from the layout document, a switch posts
   only {parts: {...}} with every part, a preset sets every switch, the
   zone guide choice posts zone_guide, and the sample button posts
   /api/overlay-sample once and says so in the status line.
   OVL-TD18-CARD-TIME (TD-18): 'Keep a card for' posts card_s (20, 60 or
   200); the dashboard twin of the card is unaffected. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const P = web.load("overlayparts.js");
const SRC = web.source("overlayparts.js");
// the code without its comments (the header names what it never does)
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
const HTML = web.source("index.html");
const APP = web.source("app.js");

const LAYOUT_PARTS = ["zone", "timer", "level", "deaths", "status", "trade", "item",
  "moment", "hint"];

function node(id, tag) {
  return {
    id, tagName: tag, checked: false, value: "", textContent: "", listeners: {},
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    fire(t) { (this.listeners[t] || []).forEach((f) => f({ target: this })); }
  };
}

/* the group's controls as index.html holds them */
function fakeDoc() {
  const ids = {};
  P.PARTS.forEach((p) => { ids["part-" + p] = node("part-" + p, "INPUT"); });
  ["parts-quiet-town"].forEach((i) => { ids[i] = node(i, "INPUT"); });
  ids["parts-zone-guide"] = node("parts-zone-guide", "SELECT");
  ids["parts-card-time"] = node("parts-card-time", "SELECT");
  ["parts-full", "parts-cards", "parts-sample"].forEach((i) => { ids[i] = node(i, "BUTTON"); });
  ids["parts-status"] = node("parts-status", "P");
  return { ids, getElementById: (id) => ids[id] || null };
}

/* web/app.js api() stand-in: records every call; answers by "METHOD path". */
function fakeApi(answers) {
  const calls = [];
  const fn = (method, path, body) => {
    calls.push([method, path, body]);
    const a = (answers || {})[method + " " + path];
    if (a instanceof Error) { return Promise.reject(a); }
    return Promise.resolve(typeof a === "function" ? a(body) : a);
  };
  fn.calls = calls;
  return fn;
}

const tickOver = () => new Promise((r) => setImmediate(r));

function layoutDoc(parts, extra) {
  const all = {};
  LAYOUT_PARTS.forEach((p) => { all[p] = true; });
  return { layout: Object.assign({ display: "primary", corner: "top-right", scale: 1,
    opacity: 0.86, margin: 16, parts: Object.assign(all, parts || {}), quiet_town: false,
    zone_guide: "entry", v: 2 }, extra || {}), corners: [], displays: [] };
}

test("the parts are the core's parts in switch order; the presets cover every part", () => {
  assert.deepEqual(P.PARTS, LAYOUT_PARTS);
  assert.deepEqual(P.ZONE_GUIDE, ["entry", "always", "never"]);
  assert.deepEqual(P.presetParts("full"), Object.fromEntries(LAYOUT_PARTS.map((p) => [p, true])));
  assert.deepEqual(P.presetParts("cards"), { zone: false, timer: false, level: false,
    deaths: false, status: false, trade: true, item: true, moment: true, hint: true });
  assert.equal(P.presetParts("other"), null);
  // a copy: changing it leaves the preset alone
  P.presetParts("full").zone = false;
  assert.equal(P.presetParts("full").zone, true);
});

test("fill sets the switches, the town switch and the zone guide from the layout doc", () => {
  const d = fakeDoc();
  assert.equal(P.fill(d, layoutDoc({ timer: false, hint: false }, { quiet_town: true,
    zone_guide: "always" })), true);
  assert.equal(d.ids["part-zone"].checked, true);
  assert.equal(d.ids["part-timer"].checked, false);
  assert.equal(d.ids["part-hint"].checked, false);
  assert.equal(d.ids["part-item"].checked, true);
  assert.equal(d.ids["parts-quiet-town"].checked, true);
  assert.equal(d.ids["parts-zone-guide"].value, "always");
  // a bare layout works too; a missing part is on, an unknown guide is On entry
  P.fill(d, { parts: { zone: false }, zone_guide: "sometimes" });
  assert.equal(d.ids["part-zone"].checked, false);
  assert.equal(d.ids["part-timer"].checked, true);
  assert.equal(d.ids["parts-quiet-town"].checked, false);
  assert.equal(d.ids["parts-zone-guide"].value, "entry");
  assert.equal(P.fill(d, null), false);
  assert.equal(P.fill(d, "x"), false);
});

test("load reads the layout once and fills; a failed read says so", async () => {
  const d = fakeDoc();
  const api = fakeApi({ "GET /api/overlay-layout": layoutDoc({ deaths: false }) });
  await P.load(d, api);
  assert.deepEqual(api.calls, [["GET", "/api/overlay-layout", undefined]]);
  assert.equal(d.ids["part-deaths"].checked, false);
  assert.equal(d.ids["parts-status"].textContent, "");
  const bad = fakeApi({ "GET /api/overlay-layout": new Error("HTTP 500") });
  await P.load(d, bad);
  assert.equal(d.ids["parts-status"].textContent,
    "Can't load the overlay settings. Is AshLight running?");
});

test("wiring reads nothing; a switch posts only {parts: {...}} with every part", async () => {
  const d = fakeDoc();
  const api = fakeApi({ "POST /api/overlay-layout": (b) => layoutDoc(b.parts) });
  P.wire(d, api);
  assert.deepEqual(api.calls, []);
  P.fill(d, layoutDoc());
  d.ids["part-level"].checked = false;
  d.ids["part-level"].fire("change");
  assert.equal(api.calls.length, 1);
  const [method, path, body] = api.calls[0];
  assert.equal(method, "POST");
  assert.equal(path, "/api/overlay-layout");
  assert.deepEqual(Object.keys(body), ["parts"]);
  assert.deepEqual(body.parts, Object.assign(P.presetParts("full"), { level: false }));
  assert.equal(d.ids["parts-status"].textContent, "Saving...");
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent, "Saved. The overlay follows within a second.");
  assert.equal(d.ids["part-level"].checked, false);
});

test("a preset sets every switch and posts the whole set once", async () => {
  const d = fakeDoc();
  const api = fakeApi({ "POST /api/overlay-layout": (b) => layoutDoc(b.parts) });
  P.wire(d, api);
  P.fill(d, layoutDoc());
  d.ids["parts-cards"].fire("click");
  assert.equal(api.calls.length, 1);
  assert.deepEqual(api.calls[0][2], { parts: P.presetParts("cards") });
  P.PARTS.forEach((p) => {
    assert.equal(d.ids["part-" + p].checked, P.HUD.indexOf(p) < 0, p);
  });
  await tickOver();
  d.ids["parts-full"].fire("click");
  assert.deepEqual(api.calls[1][2], { parts: P.presetParts("full") });
  P.PARTS.forEach((p) => { assert.equal(d.ids["part-" + p].checked, true, p); });
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent, "Saved. The overlay follows within a second.");
});

test("the zone guide choice posts zone_guide; the town switch posts quiet_town", async () => {
  const d = fakeDoc();
  const api = fakeApi({ "POST /api/overlay-layout": (b) => layoutDoc({}, b) });
  P.wire(d, api);
  d.ids["parts-zone-guide"].value = "never";
  d.ids["parts-zone-guide"].fire("change");
  assert.deepEqual(api.calls[0], ["POST", "/api/overlay-layout", { zone_guide: "never" }]);
  await tickOver();
  assert.equal(d.ids["parts-zone-guide"].value, "never");
  d.ids["parts-quiet-town"].checked = true;
  d.ids["parts-quiet-town"].fire("change");
  assert.deepEqual(api.calls[1], ["POST", "/api/overlay-layout", { quiet_town: true }]);
  // a value the core does not know is never sent
  d.ids["parts-zone-guide"].value = "bogus";
  d.ids["parts-zone-guide"].fire("change");
  assert.equal(api.calls.length, 2);
  await tickOver();
});

test("a failed save says so; only the newest save's answer fills the form", async () => {
  const d = fakeDoc();
  const failing = fakeApi({ "POST /api/overlay-layout": new Error("HTTP 400") });
  P.wire(d, failing);
  d.ids["part-zone"].fire("change");
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent, "Not saved. Try again.");
  // two quick saves: the first answer (stale) is not painted
  const pending = [];
  const slow = (method, path, body) => new Promise((resolve) => { pending.push([body, resolve]); });
  const d2 = fakeDoc();
  P.wire(d2, slow);
  P.fill(d2, layoutDoc());
  d2.ids["part-zone"].checked = false;
  d2.ids["part-zone"].fire("change");
  d2.ids["part-zone"].checked = true;
  d2.ids["part-zone"].fire("change");
  pending[1][1](layoutDoc({ zone: true }));
  await tickOver();
  pending[0][1](layoutDoc({ zone: false }));
  await tickOver();
  assert.equal(d2.ids["part-zone"].checked, true);
  assert.equal(d2.ids["parts-status"].textContent, "Saved. The overlay follows within a second.");
});

test("the sample button posts /api/overlay-sample once and says so", async () => {
  const d = fakeDoc();
  const api = fakeApi({ "POST /api/overlay-sample": { card: { kind: "sample" } } });
  P.wire(d, api);
  P.fill(d, layoutDoc());
  d.ids["parts-sample"].fire("click");
  d.ids["parts-sample"].fire("click"); // a second click while it runs is ignored
  assert.deepEqual(api.calls, [["POST", "/api/overlay-sample", {}]]);
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent, "Sample card on the overlay for 10 s.");
  // with Item check card off the overlay hides the sample: the line says so
  d.ids["part-item"].checked = false;
  d.ids["parts-sample"].fire("click");
  assert.equal(api.calls.length, 2);
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent,
    "Sample card hidden: Item check card is off. Turn it on to see the card.");
  const bad = fakeApi({ "POST /api/overlay-sample": new Error("HTTP 500") });
  P.wire(d, bad);
  d.ids["parts-sample"].fire("click");
  await tickOver();
  assert.equal(d.ids["parts-status"].textContent, "Sample card not shown. Try again.");
});

test("the page holds one labelled group with every switch, and loads the file before app.js", () => {
  const i = HTML.indexOf('<div id="overlay-parts"');
  assert.ok(i > 0);
  assert.equal(HTML.split('id="overlay-parts"').length, 2);
  const group = HTML.slice(i, HTML.indexOf('<p id="parts-status"', i));
  assert.match(group, /role="group" aria-labelledby="parts-title"/);
  assert.match(group, /<h4 id="parts-title" class="sub-h">Overlay shows<\/h4>/);
  P.PARTS.forEach((p) => {
    assert.ok(group.includes('<label class="check" for="part-' + p + '"><input id="part-' + p +
      '" type="checkbox">'), p);
  });
  for (const id of ["parts-quiet-town", "parts-zone-guide", "parts-full", "parts-cards",
    "parts-sample"]) {
    assert.ok(group.includes('id="' + id + '"'), id);
  }
  assert.ok(group.includes(">Show a sample card for 10 s</button>"));
  assert.ok(group.includes("Hide the zone line in town and hideout"));
  assert.ok(group.includes("Zone guide on the overlay"));
  assert.ok(/<option value="entry">On entry<\/option>/.test(group));
  // the status line is a plain line, not a live region
  assert.ok(HTML.includes('<p id="parts-status" class="muted"></p>'));
  // beside the layout form (outside it, so its change never saves the layout)
  const form = HTML.slice(HTML.indexOf('<form id="layout-form"'), HTML.indexOf("</form>",
    HTML.indexOf('<form id="layout-form"')));
  assert.ok(!form.includes("overlay-parts"));
  assert.ok(HTML.indexOf("</form>", HTML.indexOf('<form id="layout-form"')) < i);
  assert.ok(HTML.indexOf("/web/overlayparts.js") > 0);
  assert.ok(HTML.indexOf("/web/overlayparts.js") < HTML.indexOf("/web/app.js"));
  // app.js wires it once and reads it on connect
  assert.equal(APP.split("window.ALOverlayParts.wire(document, api)").length, 2);
  assert.equal(APP.split("window.ALOverlayParts.load(document, api)").length, 2);
});

test("no timer, no clipboard, no live region, text only through textContent", () => {
  for (const bad of ["setTimeout", "setInterval", "clipboard", "innerHTML", "aria-live",
    "localStorage", "fetch(", "XMLHttpRequest"]) {
    assert.ok(!CODE.includes(bad), bad);
  }
  assert.ok(/^[\x00-\x7f]*$/.test(SRC) && !SRC.includes("\r"));
});

test("OVL-TD18-CARD-TIME: fill shows the card time; an unknown value shows 20", () => {
  assert.deepEqual(P.CARD_S, [20, 60, 200]);
  const d = fakeDoc();
  P.fill(d, layoutDoc({}, { card_s: 60 }));
  assert.equal(d.ids["parts-card-time"].value, "60");
  P.fill(d, layoutDoc({}, { card_s: 200 }));
  assert.equal(d.ids["parts-card-time"].value, "200");
  for (const bad of [7, "60", true, null, undefined, 60.5]) {
    P.fill(d, { parts: {}, card_s: bad });
    assert.equal(d.ids["parts-card-time"].value, "20", String(bad));
  }
});

test("OVL-TD18-CARD-TIME: the control posts only {card_s: n}; an unknown value is never sent",
  async () => {
    const d = fakeDoc();
    const api = fakeApi({ "POST /api/overlay-layout": (b) => layoutDoc({}, b) });
    P.wire(d, api);
    assert.deepEqual(api.calls, []);
    for (const v of ["60", "200", "20"]) {
      d.ids["parts-card-time"].value = v;
      d.ids["parts-card-time"].fire("change");
      await tickOver();
    }
    assert.deepEqual(api.calls.map((c) => c[2]), [{ card_s: 60 }, { card_s: 200 },
      { card_s: 20 }]);
    api.calls.forEach((c) => { assert.deepEqual(c.slice(0, 2), ["POST", "/api/overlay-layout"]); });
    assert.equal(d.ids["parts-card-time"].value, "20");
    assert.equal(d.ids["parts-status"].textContent, "Saved. The overlay follows within a second.");
    for (const bad of ["30", "", "60s", "6e1", "bogus"]) {
      d.ids["parts-card-time"].value = bad;
      d.ids["parts-card-time"].fire("change");
    }
    assert.equal(api.calls.length, 3);
  });

test("OVL-TD18-CARD-TIME: one labelled select in the group; the dashboard twin is unaffected",
  () => {
    const i = HTML.indexOf('<div id="overlay-parts"');
    const group = HTML.slice(i, HTML.indexOf('<p id="parts-status"', i));
    assert.equal(HTML.split('id="parts-card-time"').length, 2);
    assert.ok(group.includes('<label for="parts-card-time">Keep a card for</label>'));
    assert.ok(group.includes('<select id="parts-card-time" aria-describedby="parts-card-time-note">'));
    const sel = group.slice(group.indexOf('<select id="parts-card-time"'),
      group.indexOf("</select>", group.indexOf('<select id="parts-card-time"')));
    assert.deepEqual([...sel.matchAll(/<option value="(\d+)">/g)].map((m) => Number(m[1])),
      P.CARD_S);
    assert.ok(/<option value="20">20 seconds<\/option>/.test(sel)); // first is the default
    assert.ok(group.includes('<p id="parts-card-time-note" class="muted">'));
    // the dashboard's own item check and price rows (the card's twin) are
    // not touched by the control: no card id, no expiry in this file
    for (const bad of ["eval-result", "price-result", "evalbox", "expires_at"]) {
      assert.ok(!CODE.includes(bad), bad);
    }
    assert.equal(HTML.split('<div id="eval-result"').length, 2);
    assert.equal(HTML.split('<div id="price-result"').length, 2);
  });
