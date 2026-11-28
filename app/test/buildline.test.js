/* PLAY-TD-15-BUILDLINE (web/buildline.js, F-041): region B prints the four
   build states from snap.play.build, carries the one "Paste a build"
   button only while no build is loaded, and the click shows the tab that
   holds #build-paste with the paste box focused. Never a clipboard read,
   never ALBuildLive, never ALTabs.notify. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const BL = web.load("buildline.js");
const Tabs = web.load("tabs.js");
const R = web.load("regions.js");

const SRC = web.source("buildline.js");
const CSS = web.source("buildline.css");
const HTML = web.source("index.html");

/* A small DOM: ids, parents, children, attributes, hidden, focus, click. */
function makeDoc() {
  const doc = { active: null, byId: {}, all: [] };
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], parentNode: null,
      hidden: false, textContent: "", listeners: {},
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); doc.byId[v] = this; },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) {
        if (k === "id") { this.id = v; return; }
        this.attrs[k] = String(v);
      },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ type: "click" })); },
      focus() { doc.active = this; }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-b [data-slot="b"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.getAttribute(m[1]) !== null) : [];
  };
  // the page bits B touches: region B with its slot and legacy group, the
  // tab buttons and panels, and the paste box inside the Build panel
  const region = elem("section");
  region.id = "play-b";
  region.setAttribute("data-region", "b");
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "b");
  const legacy = region.appendChild(elem("div"));
  legacy.setAttribute("data-legacy", "b-alert");
  Tabs.TABS.forEach((t) => {
    const b = elem("button");
    b.id = "tab-" + t;
    b.querySelector = () => null;
    const p = elem("div");
    p.id = "panel-" + t;
    p.hidden = t !== "play";
    doc[t] = p;
  });
  const wrap = doc.build.appendChild(elem("div"));
  const box = wrap.appendChild(elem("textarea"));
  box.id = "build-paste";
  doc.legacy = legacy;
  doc.region = region;
  return doc;
}

function snapWith(build) { return { play: { build } }; }

const NONE = { state: "none", kit: "pending", glyph: "[ ]", word: "No build", row1: "",
  row2: "Copy a PoB code, press the item key.", can_paste: true };
const FITS = { state: "fits", kit: "done", glyph: "[+]", word: "Build fits",
  row1: "Deadeye, level 52", row2: "Checks use your stat weights.", can_paste: false };
const OLD = { state: "old", kit: "needs-operator", glyph: "[?]", word: "Old build",
  row1: "Deadeye, level 40", row2: "Copy a PoB code, press the item key.", can_paste: false };
const WRONG = { state: "wrong_class", kit: "needs-operator", glyph: "[?]", word: "Wrong class",
  row1: "Titan, level 52", row2: "Copy a PoB code, press the item key.", can_paste: false };

test("a consented snapshot with no build shows [ ] No build and the button", () => {
  BL.reset();
  const doc = makeDoc();
  BL.wire(doc, { tabs: Tabs });
  const m = BL.paint(doc, snapWith(NONE));
  assert.equal(m.state, "none");
  const word = doc.getElementById("bl-word");
  assert.equal(word.textContent, "[ ] No build");
  const button = doc.getElementById("bl-paste");
  assert.equal(button.hidden, false);
  assert.equal(button.textContent, "Paste a build");
  assert.equal(button.getAttribute("type"), "button");
  assert.equal(doc.getElementById("bl-name").hidden, true);
  assert.equal(doc.getElementById("bl-row2").textContent, "Copy a PoB code, press the item key.");
  assert.equal(doc.getElementById("bl").hidden, false);
});

test("the click shows the build tab with #build-paste focused", () => {
  BL.reset();
  const doc = makeDoc();
  BL.wire(doc, { tabs: Tabs });
  BL.paint(doc, snapWith(NONE));
  assert.equal(BL.pasteTab(doc), "build");
  doc.getElementById("bl-paste").click();
  assert.equal(Tabs.current(), "build");
  assert.equal(doc.build.hidden, false);
  assert.equal(doc.play.hidden, true);
  assert.equal(doc.getElementById("tab-build").getAttribute("aria-selected"), "true");
  assert.equal(doc.active, doc.getElementById("build-paste"), "the paste box has focus");
  Tabs.show(doc, "play", false);
});

test("the click still focuses the paste box with no tab helper", () => {
  BL.reset();
  const doc = makeDoc();
  BL.wire(doc, { tabs: null });
  BL.paint(doc, snapWith(NONE));
  doc.getElementById("bl-paste").click();
  assert.equal(doc.active, doc.getElementById("build-paste"));
});

test("the four states print their words, the button only with no build", () => {
  BL.reset();
  const doc = makeDoc();
  BL.wire(doc, { tabs: Tabs });
  const cases = [[FITS, "[+] Build fits", "neutral"], [OLD, "[?] Old build", "warn"],
    [WRONG, "[?] Wrong class", "warn"], [NONE, "[ ] No build", "neutral"]];
  for (const [b, text, tone] of cases) {
    BL.paint(doc, snapWith(b));
    assert.equal(doc.getElementById("bl-word").textContent, text);
    assert.equal(doc.getElementById("bl").getAttribute("data-state"), b.state);
    assert.equal(doc.getElementById("bl").getAttribute("data-tone"), tone);
    assert.equal(doc.getElementById("bl-paste").hidden, b.state !== "none", b.state);
    const name = doc.getElementById("bl-name");
    assert.equal(name.textContent, b.row1);
    assert.equal(name.getAttribute("title"), b.row1);
    assert.equal(name.hidden, !b.row1);
    assert.equal(doc.getElementById("bl-row2").textContent, b.row2);
  }
  // the kit word stale is never used
  assert.doesNotMatch(SRC, /["']stale["']/);
});

test("the model reads snap.play.build only and falls back to the table", () => {
  assert.equal(BL.model({}), null);
  assert.equal(BL.model({ build: { loaded: true }, build_alert: { kind: "level" } }), null);
  assert.equal(BL.model({ play: { build: "x" } }), null);
  const m = BL.model(snapWith({ state: "bogus" }));
  assert.equal(m.state, "none");
  assert.equal(m.word, "No build");
  assert.equal(m.glyph, "[ ]");
  assert.equal(m.canPaste, false, "the button follows the core's can_paste");
  assert.equal(BL.model(snapWith({ state: "old" })).word, "Old build");
});

test("a snapshot with no play block hides the line; paint is idempotent", () => {
  BL.reset();
  const doc = makeDoc();
  BL.wire(doc, { tabs: Tabs });
  BL.paint(doc, snapWith(FITS));
  const root = doc.getElementById("bl");
  assert.equal(root.hidden, false);
  const before = doc.slot.children.length;
  BL.paint(doc, snapWith(FITS));
  BL.paint(doc, {});
  assert.equal(root.hidden, true);
  assert.equal(doc.slot.children.length, before, "the nodes are made once");
});

test("it registers as region b and retires the b-alert group", () => {
  assert.equal(BL.spec.name, "buildline");
  assert.equal(BL.spec.region, "b");
  assert.deepEqual(BL.spec.retires, ["b-alert"]);
  BL.reset();
  const doc = makeDoc();
  const reg = R.create({ warn: () => {} });
  reg.register(BL.spec);
  reg.start(doc, { api: () => null, getSnap: () => null, serverNow: () => 0, tabs: Tabs });
  assert.equal(doc.legacy.hidden, true);
  assert.equal(doc.region.getAttribute("data-fit"), "yes");
  reg.paint(doc, snapWith(NONE), 0);
  assert.equal(doc.getElementById("bl-word").textContent, "[ ] No build");
});

test("the floor: no clipboard, no ALBuildLive, no notify, no timer, no network", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of [/clipboard/i, /ALBuildLive/, /\.notify\(/, /setInterval|setTimeout/,
    /fetch\(|XMLHttpRequest|EventSource/, /innerHTML/, /aria-live/]) {
    assert.doesNotMatch(code, bad, String(bad));
  }
  assert.match(SRC, /module\.exports = api;/);
  assert.doesNotMatch(SRC + CSS, /[^\x0a\x20-\x7e]/, "ASCII and LF");
});

test("the page holds the paste box inside the Build panel and pre-links the file", () => {
  const panel = HTML.indexOf('id="panel-build"');
  const next = HTML.indexOf('id="panel-run"');
  const box = HTML.indexOf('id="build-paste"');
  assert.ok(panel > 0 && box > panel && box < next, "#build-paste is in panel-build");
  assert.match(HTML, /<script src="\/web\/buildline\.js" defer><\/script>/);
  assert.match(HTML, /<link rel="stylesheet" href="\/web\/buildline\.css">/);
});

/* ACTIVE-BUILD-PICK (decision 0096): one switch between the pasted build
   and a Kindler plan, composed by the core (play.build.switch). */
test("the switch shows the core's words and posts the player's click", async () => {
  BL.reset();
  const doc = makeDoc();
  const calls = [];
  BL.wire(doc, { tabs: Tabs, api: (m, p, b) => { calls.push([m, p, b]); return Promise.resolve({}); } });
  const kin = Object.assign({}, FITS, { row1: "Kindler: Plan, level 21",
    row2: "Kindler plan (generated)", switch: { label: "Use pasted build", use: "pasted", id: null } });
  BL.paint(doc, snapWith(kin));
  const swap = doc.getElementById("bl-swap");
  assert.equal(swap.hidden, false);
  assert.equal(swap.textContent, "Use pasted build");
  assert.equal(swap.getAttribute("type"), "button");
  assert.equal(doc.getElementById("bl-paste").hidden, true, "one button only");
  swap.click();
  await Promise.resolve();
  assert.deepEqual(calls, [["POST", "/api/build-source", { use: "pasted" }]]);
  const pasted = Object.assign({}, FITS, { row2: "Pasted build",
    switch: { label: "Use Kindler plan", use: "kindler", id: "k1" } });
  BL.paint(doc, snapWith(pasted));
  assert.equal(swap.textContent, "Use Kindler plan");
  swap.click();
  assert.deepEqual(calls[1], ["POST", "/api/build-source", { use: "kindler", id: "k1" }]);
  BL.paint(doc, snapWith(FITS));
  assert.equal(swap.hidden, true, "nothing to switch to: no button");
});

test("a failed switch is said on the polite line, never thrown", async () => {
  BL.reset();
  const doc = makeDoc();
  const said = [];
  const tabs = { say: (d, t) => said.push(t) };
  BL.wire(doc, { tabs, api: () => Promise.reject(new Error("HTTP 400")) });
  BL.paint(doc, snapWith(Object.assign({}, FITS,
    { switch: { label: "Use Kindler plan", use: "kindler", id: "k1" } })));
  await BL.useSource({ use: "kindler", id: "k1" });
  assert.deepEqual(said, ["The build didn't switch. Try again."]);
  assert.equal(BL.model(snapWith({ state: "fits", switch: { label: "", use: "pasted" } })).switchTo,
    null, "no words, no switch");
});

/* BUILD-SWITCH-COPY: a refusal says why from the answer's fixed reason
   word; anything else keeps the general line. */
test("a refused switch says why from the reason word", async () => {
  BL.reset();
  const doc = makeDoc();
  const said = [];
  const tabs = { say: (d, t) => said.push(t) };
  function refuse(body) {
    const e = new Error("HTTP 400");
    e.status = 400;
    e.body = body;
    return () => Promise.reject(e);
  }
  const why = "Play a character first.";
  BL.wire(doc, { tabs, api: refuse({ error: why, reason: "no_character" }) });
  await BL.useSource({ use: "pasted" });
  BL.wire(doc, { tabs, api: refuse({ error: "cache\\some\\file.json", reason: "elsewhere" }) });
  await BL.useSource({ use: "pasted" });
  BL.wire(doc, { tabs, api: refuse({ reason: "no_result" }) });
  await BL.useSource({ use: "pasted" });
  BL.wire(doc, { tabs, api: refuse({ error: "x".repeat(121), reason: "bad" }) });
  await BL.useSource({ use: "pasted" });
  assert.deepEqual(said, [
    "The build didn't switch. " + why,
    "The build didn't switch. Try again.",
    "The build didn't switch. Try again.",
    "The build didn't switch. Try again."]);
  assert.deepEqual(BL.REASONS, ["bad", "no_character", "no_result"]);
});

/* BUILD-SWITCH-COPY: the switch hiding while focused hands focus on, to
   the paste button that takes its place, else the region heading. */
test("a switch that hides with focus hands focus on", () => {
  BL.reset();
  const doc = makeDoc();
  Object.defineProperty(doc, "activeElement", { get() { return doc.active; } });
  const heading = doc.createElement("h2");
  heading.id = "play-b-h";
  doc.region.appendChild(heading);
  BL.wire(doc, { tabs: null, api: () => Promise.resolve({}) });
  const sw = Object.assign({}, FITS, { switch: { label: "Use pasted build", use: "pasted" } });
  BL.paint(doc, snapWith(sw));
  const swap = doc.getElementById("bl-swap");
  swap.focus();
  BL.paint(doc, snapWith(FITS));
  assert.equal(swap.hidden, true);
  assert.equal(doc.active, heading, "no paste button: the region heading");
  assert.equal(heading.getAttribute("tabindex"), "-1");
  // no build left: the paste button takes the switch's place
  BL.paint(doc, snapWith(sw));
  swap.focus();
  BL.paint(doc, snapWith(NONE));
  assert.equal(doc.active, doc.getElementById("bl-paste"));
  // the label only changes: focus stays on the switch
  BL.paint(doc, snapWith(sw));
  swap.focus();
  BL.paint(doc, snapWith(Object.assign({}, FITS,
    { switch: { label: "Use Kindler plan", use: "kindler", id: "k1" } })));
  assert.equal(doc.active, swap);
  // focus elsewhere: left alone
  const other = doc.createElement("button");
  other.focus();
  BL.paint(doc, snapWith(FITS));
  assert.equal(doc.active, other);
  // the snapshot loses play.build: the heading, never the hidden paste button
  BL.paint(doc, snapWith(sw));
  swap.focus();
  BL.paint(doc, {});
  assert.equal(doc.active, heading);
});
