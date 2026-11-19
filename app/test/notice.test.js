/* PLAY-TD-14-NOTICE: region N (web/notice.js). One notice at a time from
   snap.play.notices through ALSlots.noticePick, at most 1 action, a
   "+N more" text count, the head row only in the compact class (kinds 6
   and 7 hidden there), Setup's action shows Settings, the language note's
   Hide reuses the checks.js stored key, one polite live region, no toast,
   no ALTabs.notify, and at most one amber cue (F-159). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const N = require("../../web/notice.js");
const S = require("../../web/slots.js");
const C = require("../../web/checks.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "notice.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "notice.css"), "utf8");

/* ---- notices as server/al/playview.py composes them ---------------------- */

const BROKEN = { kind: 1, state: "failed", glyph: "[x]", word: "Broken", title: "Overlay",
  rows: ["Not running.", "Run the client again."], action: "Open Checks" };
const LANG = { kind: 3, state: "needs-operator", glyph: "[?]", word: "Language",
  title: "Not English", rows: ["AshLight reads only the English game text."],
  action: "Open Checks" };
const SETUP = { kind: 4, state: "pending", glyph: "[ ]", word: "Setup", title: "2 steps left",
  rows: ["Still to set: your build and prices.", "All optional; Settings has the controls."],
  action: "Settings" };
const NOTE = { kind: 5, state: "idle", glyph: "[-]", word: "Note", title: "Game data",
  rows: ["The snapshot is old."], action: "Open Checks" };
const TIP = { kind: 6, state: "idle", glyph: "[-]", word: "Tip", title: "New character",
  rows: ["Press the item key on an item."], action: "" };

function snapOf(notices, extra) {
  return Object.assign({ play: { notices: notices } }, extra || {});
}

/* ---- a small fake DOM ---------------------------------------------------------- */

function el(tag) {
  const n = {
    tagName: tag, children: [], attrs: {}, className: "", parentNode: null, listeners: {},
    open: false, focused: false, clicks: 0,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    addEventListener(t, f) { this.listeners[t] = f; },
    click() { this.clicks += 1; if (this.listeners.click) { this.listeners.click(); } },
    focus() { this.focused = true; }
  };
  Object.defineProperty(n, "textContent", {
    get() { return this._t !== undefined ? this._t : this.children.map((c) => c.textContent).join(""); },
    set(v) { this.children = []; this._t = v === "" ? undefined : String(v); }
  });
  return n;
}

function text(t) { const n = el("#text"); n.textContent = t; return n; }

function fakeDoc(sizeClass, ids) {
  const slot = el("div");
  slot.setAttribute("data-slot", "n");
  const byId = Object.assign({}, ids || {});
  return {
    slot, byId,
    documentElement: {},
    defaultView: { getComputedStyle: () => ({ getPropertyValue: () => " " + sizeClass }) },
    createElement: el,
    createTextNode: text,
    querySelector(sel) { return sel === "[data-slot=\"n\"]" ? slot : null; },
    getElementById(id) { return byId[id] || null; }
  };
}

function walk(n, out) {
  out = out || [];
  out.push(n);
  (n.children || []).forEach((c) => walk(c, out));
  return out;
}

function byClass(root, cls) {
  return walk(root).filter((n) => (" " + n.className + " ").indexOf(" " + cls + " ") >= 0);
}

function fakeTabs() {
  const calls = [];
  return { calls, show(doc, id, focus) { calls.push([id, !!focus]); return id; },
    notify() { calls.push(["notify"]); } };
}

function fresh(sizeClass, ctx, ids) {
  N._reset();
  C._state.dismissed = undefined;
  const doc = fakeDoc(sizeClass, ids);
  N.wire(doc, ctx || { tabs: fakeTabs() });
  return doc;
}

/* ---- the pure model -------------------------------------------------------------- */

test("the spec registers region n and retires the legacy language and tip cards", () => {
  assert.equal(N.spec.name, "notice");
  assert.equal(N.spec.region, "n");
  assert.deepEqual(N.spec.retires, ["n-legacy"]);
  ["wire", "paint", "tick"].forEach((k) => assert.equal(typeof N.spec[k], "function", k));
});

test("the model shows the first notice of ALSlots.noticePick and counts the rest", () => {
  const q = [BROKEN, LANG, SETUP, NOTE, TIP];
  const m = N.model(snapOf(q), "full", null);
  const pick = S.noticePick(q, "full");
  assert.equal(m.kind, pick.kind);
  assert.equal(m.word, "Broken");
  assert.equal(m.more, pick.more);
  assert.equal(m.more, 4);
  assert.deepEqual(m.rows, BROKEN.rows);
  assert.deepEqual(m.action, { label: "Open Checks", does: "checks" });
  // the queue order from the core does not matter: the lowest kind wins
  assert.equal(N.model(snapOf([TIP, SETUP, LANG]), "full", null).word, "Language");
});

test("compact keeps the head row only and never shows kinds 6 and 7", () => {
  const m = N.model(snapOf([SETUP, TIP]), "compact", null);
  assert.equal(m.word, "Setup");
  assert.deepEqual(m.rows, []);
  assert.equal(m.more, 0, "the tip is not counted where it cannot show");
  const tipOnly = N.model(snapOf([TIP, { kind: 7, word: "Keys", title: "F2" }]), "compact", null);
  assert.equal(tipOnly.empty, true);
  // full shows 2 body rows at most
  assert.equal(N.model(snapOf([SETUP]), "full", null).rows.length, 2);
  // the flow class reads as full
  assert.equal(N.model(snapOf([SETUP]), "flow", null).rows.length, 2);
});

test("empty reads Notices none with no action and no tone", () => {
  for (const snap of [null, {}, { play: null }, { play: { notices: "x" } }, snapOf([])]) {
    const m = N.model(snap, "full", null);
    assert.equal(m.empty, true);
    assert.equal(m.word, "Notices");
    assert.equal(m.title, "none");
    assert.equal(m.action, null);
    assert.equal(m.tone, "");
  }
});

test("at most one action, a known one; the language note's action is Hide", () => {
  assert.deepEqual(N.actionOf(SETUP), { label: "Settings", does: "settings" });
  assert.deepEqual(N.actionOf(LANG), { label: "Hide", does: "hide" });
  assert.equal(N.actionOf(TIP), null);
  assert.equal(N.actionOf({ kind: 2, action: "Do a thing" }), null, "never a dead button");
  assert.equal(N.actionOf({ kind: 1, action: "Open Checks now please" }), null);
  Object.keys(N.ACTIONS).concat([N.HIDE]).forEach((l) => assert.ok(l.length <= 12, l));
});

test("a hidden language note leaves the queue until it begins again", () => {
  const lang = { verdict: "non_english", text: "Your game is not in English.", since: 42 };
  const q = [LANG, SETUP];
  assert.equal(N.model(snapOf(q, { lang }), "full", null).word, "Language");
  assert.equal(N.model(snapOf(q, { lang }), "full", "42").word, "Setup");
  // a new start time: the note is back
  assert.equal(N.model(snapOf(q, { lang: Object.assign({}, lang, { since: 50 }) }), "full", "42")
    .word, "Language");
});

test("one amber cue: only a warn notice has the warn tone", () => {
  assert.equal(N.model(snapOf([LANG]), "full", null).tone, "warn");
  assert.equal(N.model(snapOf([BROKEN]), "full", null).tone, "bad");
  assert.equal(N.model(snapOf([SETUP]), "full", null).tone, "");
  assert.equal(N.model(snapOf([NOTE]), "full", null).tone, "");
  const rules = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  const warn = rules.split("}").filter((r) => /status-warn/.test(r));
  assert.equal(warn.length, 2, "the warn word and its edge, nothing else");
  warn.forEach((r) => assert.match(r, /data-tone="warn"\](\s|\.edge)/));
  assert.match(warn.join("}"), /\.notice-word/);
  assert.match(warn.join("}"), /\.edge \{ border-left-color/);
  // the title, rows, count and button never take a status colour
  rules.split("}").filter((r) => /notice-(title|row|more|act)/.test(r)).forEach((r) => {
    assert.doesNotMatch(r, /status-/, r);
  });
});

/* ---- the DOM -------------------------------------------------------------------- */

test("one polite live region in the slot, repainted only on a text change", () => {
  const doc = fresh("full");
  assert.equal(doc.slot.children.length, 1);
  const box = doc.slot.children[0];
  assert.equal(box.getAttribute("aria-live"), "polite");
  assert.equal(box.textContent, "Noticesnone");
  N.paint(doc, snapOf([SETUP]));
  const head = box.children[0];
  N.paint(doc, snapOf([SETUP]));
  assert.equal(box.children[0], head, "same text, same nodes");
  assert.equal(doc.slot.children.length, 1);
  assert.equal(walk(doc.slot).filter((n) => n.getAttribute && n.getAttribute("aria-live")).length, 1);
});

test("full: head row with glyph, word, title, +N more and 1 button, then 2 rows", () => {
  const doc = fresh("full");
  N.paint(doc, snapOf([SETUP, NOTE, TIP]));
  const box = doc.slot.children[0];
  assert.equal(box.getAttribute("data-kind"), "4");
  const head = box.children[0];
  assert.equal(byClass(head, "notice-word")[0].textContent, "[ ] Setup");
  assert.equal(byClass(head, "glyph")[0].getAttribute("aria-hidden"), "true");
  assert.equal(byClass(head, "notice-title")[0].textContent, "2 steps left");
  assert.equal(byClass(head, "notice-more")[0].textContent, "+2 more");
  const buttons = walk(box).filter((n) => n.tagName === "button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].textContent, "Settings");
  assert.equal(byClass(box, "notice-row").length, 2);
});

test("compact: the head row only", () => {
  const doc = fresh("compact");
  N.paint(doc, snapOf([SETUP, TIP]));
  const box = doc.slot.children[0];
  assert.equal(box.children.length, 1);
  assert.equal(byClass(box, "notice-row").length, 0);
  assert.equal(byClass(box, "notice-more").length, 0);
});

test("Setup: N steps left shows Settings; Open Checks opens the Checks fold", () => {
  const tabs = fakeTabs();
  const fold = el("details");
  const summary = el("summary");
  const doc = fresh("full", { tabs }, { checks: fold, "checks-summary": summary });
  N.paint(doc, snapOf([SETUP]));
  walk(doc.slot).find((n) => n.tagName === "button").click();
  assert.deepEqual(tabs.calls, [["settings", true]]);
  N.paint(doc, snapOf([NOTE]));
  walk(doc.slot).find((n) => n.tagName === "button").click();
  assert.deepEqual(tabs.calls[1], ["settings", false]);
  assert.equal(fold.open, true);
  assert.equal(summary.focused, true);
  assert.ok(!tabs.calls.some((c) => c[0] === "notify"), "never ALTabs.notify");
});

test("Hide goes through the checks.js handler and the note leaves", () => {
  const legacy = el("button");
  const doc = fresh("full", { tabs: fakeTabs() }, { "lang-dismiss": legacy });
  const lang = { verdict: "non_english", text: "Your game is not in English.", since: 7 };
  // the checks.js handler: reads #langbox data-key, stores it (its helpers)
  legacy.addEventListener("click", () => { C._state.dismissed = "7"; });
  N.paint(doc, snapOf([LANG, SETUP], { lang }));
  assert.equal(doc.slot.children[0].getAttribute("data-kind"), "3");
  const hide = walk(doc.slot).find((n) => n.tagName === "button");
  assert.equal(hide.textContent, "Hide");
  hide.click();
  assert.equal(legacy.clicks, 1);
  assert.equal(doc.slot.children[0].getAttribute("data-kind"), "4", "Setup shows next");
});

test("tick repaints only when the size class changed", () => {
  const doc = fresh("full");
  N.paint(doc, snapOf([SETUP]));
  assert.equal(byClass(doc.slot, "notice-row").length, 2);
  N.tick(doc);
  assert.equal(byClass(doc.slot, "notice-row").length, 2);
  doc.defaultView = { getComputedStyle: () => ({ getPropertyValue: () => "compact" }) };
  N.tick(doc);
  assert.equal(byClass(doc.slot, "notice-row").length, 0);
});

test("no timer, toast, sound, network, clipboard or ALTabs.notify; ASCII and LF", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  assert.doesNotMatch(code, /setTimeout|setInterval|Notification|Audio\(|fetch\(|XMLHttpRequest|clipboard|\.notify\(/);
  assert.doesNotMatch(SRC + CSS, /[^\x0a\x20-\x7e]/);
  assert.doesNotMatch(CSS.replace(/\/\*[\s\S]*?\*\//g, ""), /animation|transition/);
  assert.match(SRC, /module\.exports = api;/);
});
