/* OVL-KEYS-WEB (F-026, decision 0058): web/hotkeys.js names only the keys
   the desktop client bound, saves the two change-key fields through POST
   /api/hotkeys and shows one Play line while the overlay is switched off.
   Every snapshot here is synthetic. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const hk = web.load("hotkeys.js");

function el(tag, attrs) {
  const node = {
    tagName: tag, children: [], attrs: Object.assign({}, attrs || {}), hidden: false,
    value: "", id: "", className: "", listeners: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, f) { this.listeners[t] = f; }
  };
  Object.defineProperty(node, "textContent", {
    get() { return this._t || ""; },
    set(v) { this._t = String(v); }
  });
  return node;
}

/* A page with the spans of web/index.html (their own words), the two
   fields with their answers, and region C of Play. */
function fakeDoc() {
  const spans = [
    el("span", { "data-hotkey": "eval" }), el("span", { "data-hotkey": "toggle" }),
    el("span", { "data-hotkey": "eval" })];
  spans[0].textContent = "the item check key";
  spans[1].textContent = "the overlay key";
  spans[2].textContent = "the item check key";
  const ids = {};
  ["hotkey-eval", "hotkey-toggle"].forEach((id) => { ids[id] = el("input"); });
  ["hotkey-eval-said", "hotkey-toggle-said", "play-c"].forEach((id) => { ids[id] = el("p"); });
  const doc = {
    ids, spans, activeElement: null,
    getElementById(id) {
      if (ids[id]) { return ids[id]; }
      const made = ids["play-c"].children.find((c) => c.id === id);
      return made || null;
    },
    querySelectorAll(sel) {
      assert.equal(sel, "[data-hotkey]");
      return spans;
    },
    createElement: (t) => el(t)
  };
  return doc;
}

function entry(key, want, registered, fallback) {
  return { key, want, registered, fallback };
}

function snapOf(evalE, toggleE, overlayOn) {
  return { hotkeys: { eval: evalE, toggle: toggleE, overlay_on: overlayOn } };
}

const BOUND = snapOf(entry("Ctrl+Alt+K", "Ctrl+Alt+K", true, false),
  entry("Ctrl+Alt+L", "Ctrl+Alt+L", true, false), true);

test("paint fills every [data-hotkey] with the bound key", () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  assert.deepEqual(doc.spans.map((s) => s.textContent), ["Ctrl+Alt+K", "Ctrl+Alt+L", "Ctrl+Alt+K"]);
  assert.equal(doc.ids["hotkey-eval"].value, "Ctrl+Alt+K");
  assert.equal(doc.ids["hotkey-toggle"].value, "Ctrl+Alt+L");
  assert.equal(doc.ids["hotkey-eval-said"].textContent, "");
});

test("a key that is not bound is never named: the span keeps its own words", () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  // the client is gone (no runtime file): every unknown field is null
  hk.paint(doc, snapOf(entry(null, "Ctrl+Alt+K", null, null),
    entry(null, "Ctrl+Alt+L", null, null), null));
  assert.deepEqual(doc.spans.map((s) => s.textContent),
    ["the item check key", "the overlay key", "the item check key"]);
  // the field still shows the key the player asked for
  assert.equal(doc.ids["hotkey-eval"].value, "Ctrl+Alt+K");
  // no snapshot hotkeys at all (before the core's first tick)
  hk.paint(doc, { hotkeys: null });
  assert.equal(doc.spans[0].textContent, "the item check key");
  assert.equal(hk.shown({}, "eval"), "");
  assert.equal(hk.shown(null, "toggle"), "");
});

test("a fallback shows the alternate and the field says which key was taken", () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, snapOf(entry("Ctrl+Shift+F9", "Ctrl+Alt+K", true, true),
    entry("Ctrl+Alt+L", "Ctrl+Alt+L", true, false), true));
  assert.equal(doc.spans[0].textContent, "Ctrl+Shift+F9");
  assert.equal(doc.ids["hotkey-eval"].value, "Ctrl+Alt+K");
  assert.equal(doc.ids["hotkey-eval-said"].textContent,
    "Another program holds Ctrl+Alt+K, so AshLight uses Ctrl+Shift+F9 instead.");
  assert.equal(doc.ids["hotkey-toggle-said"].textContent, "");
  // a key the client could not bind at all: off, and said so
  hk.paint(doc, snapOf(entry(null, "Ctrl+Alt+K", false, false),
    entry("Ctrl+Alt+L", "Ctrl+Alt+L", true, false), true));
  assert.equal(doc.spans[0].textContent, "the item check key");
  assert.equal(doc.ids["hotkey-eval-said"].textContent,
    "Another program holds Ctrl+Alt+K, so this key is off. Type another key.");
});

test("the field never changes under the player's fingers", () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  doc.ids["hotkey-eval"].value = "Ctrl+Al";
  doc.activeElement = doc.ids["hotkey-eval"];
  hk.paint(doc, BOUND);
  assert.equal(doc.ids["hotkey-eval"].value, "Ctrl+Al");
});

function reply(status, body) {
  return Promise.resolve({ ok: status === 200, status, json: () => Promise.resolve(body) });
}

const tick = () => new Promise((r) => setImmediate(r));

test("the change field posts /api/hotkeys and shows the saved key", async () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  const sent = [];
  const view = { eval: entry("Ctrl+Alt+K", "Ctrl+Alt+J", true, false),
    toggle: entry("Ctrl+Alt+L", "Ctrl+Alt+L", true, false), overlay_on: true };
  hk.wire(doc, { token: "t0k", fetch: (url, opts) => { sent.push([url, opts]); return reply(200, { hotkeys: view }); } });
  const input = doc.ids["hotkey-eval"];
  input.listeners.input();
  input.value = " ctrl+alt+j ";
  input.listeners.change();
  await tick(); await tick();
  assert.equal(sent.length, 1);
  assert.equal(sent[0][0], "/api/hotkeys");
  assert.equal(sent[0][1].method, "POST");
  assert.equal(sent[0][1].headers["X-AL-Token"], "t0k");
  assert.deepEqual(JSON.parse(sent[0][1].body), { name: "eval", key: "ctrl+alt+j" });
  const said = doc.ids["hotkey-eval-said"];
  assert.equal(said.textContent, "Saved. AshLight switches to Ctrl+Alt+J by itself.");
  // the answer stands while the client has not re-registered ...
  hk.paint(doc, { hotkeys: view });
  assert.equal(said.textContent, "Saved. AshLight switches to Ctrl+Alt+J by itself.");
  // ... and gives way once it has: the spans show the new key
  hk.paint(doc, snapOf(entry("Ctrl+Alt+J", "Ctrl+Alt+J", true, false), view.toggle, true));
  assert.equal(said.textContent, "");
  assert.equal(doc.spans[0].textContent, "Ctrl+Alt+J");
});

test("a refused key shows the core's sentence and nothing changes", async () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  const refusal = "The item check hotkey needs Ctrl or Alt held with a key, and can't be a key the game uses.";
  hk.wire(doc, { token: "t", fetch: () => reply(400, { error: refusal }) });
  const input = doc.ids["hotkey-eval"];
  input.value = "Ctrl+C";
  input.listeners.change();
  await tick(); await tick();
  const said = doc.ids["hotkey-eval-said"];
  assert.equal(said.textContent, refusal + " Nothing changed.");
  // a state push that changes nothing leaves the answer in place
  hk.paint(doc, BOUND);
  assert.equal(said.textContent, refusal + " Nothing changed.");
  assert.equal(doc.spans[0].textContent, "Ctrl+Alt+K");
  // typing again clears it
  input.listeners.input();
  assert.equal(said.textContent, "");
});

test("save failures and an emptied field", async () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  let calls = 0;
  hk.wire(doc, { token: "t", fetch: () => { calls += 1; return calls === 1 ? reply(500, {}) : Promise.reject(new Error("down")); } });
  const input = doc.ids["hotkey-toggle"];
  const said = doc.ids["hotkey-toggle-said"];
  input.value = "Ctrl+Alt+M";
  input.listeners.change();
  await tick(); await tick();
  assert.equal(said.textContent, hk.FAILED);
  input.listeners.change();
  await tick(); await tick();
  assert.equal(said.textContent, hk.OFFLINE);
  // an emptied field asks nothing and shows the asked key again
  input.value = "  ";
  input.listeners.change();
  await tick();
  assert.equal(calls, 2);
  assert.equal(input.value, "Ctrl+Alt+L");
});

test("the Play line shows only while overlay_on is false", () => {
  hk._reset();
  const doc = fakeDoc();
  hk.paint(doc, BOUND);
  assert.equal(doc.ids["play-c"].children.length, 0);
  const off = snapOf(BOUND.hotkeys.eval, BOUND.hotkeys.toggle, false);
  hk.paint(doc, off);
  const line = doc.ids["play-c"].children[0];
  assert.equal(line.id, "overlay-off-line");
  assert.equal(line.hidden, false);
  assert.equal(line.textContent, "The overlay is switched off. Press Ctrl+Alt+L to show it.");
  hk.paint(doc, BOUND);
  assert.equal(line.hidden, true);
  assert.equal(doc.ids["play-c"].children.length, 1);
  // unknown (no client file) is not "off"
  hk.paint(doc, snapOf(BOUND.hotkeys.eval, BOUND.hotkeys.toggle, null));
  assert.equal(line.hidden, true);
  // off with no bound toggle key names no key
  hk.paint(doc, snapOf(BOUND.hotkeys.eval, entry(null, "Ctrl+Alt+L", false, false), false));
  assert.equal(line.hidden, false);
  assert.equal(line.textContent, hk.OFF_NO_KEY);
  assert.equal(hk.playLine(null), "");
});

test("the page and this view never write a default key", () => {
  const src = web.source("hotkeys.js", "ascii");
  assert.equal(src.includes("Alt+Shift+"), false);
  const html = web.source("index.html", "ascii");
  assert.equal(html.includes("Alt+Shift+"), false);
  assert.ok(html.includes('<script src="/web/hotkeys.js" defer></script>'));
});
