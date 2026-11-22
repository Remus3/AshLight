/* RUN-HISTORY-UNDO (F-191): the Clear run history button in
   web/history.js hides the saved runs and shows "Cleared." with an Undo
   button in place for 10 s; the clear request goes out only when the
   window ends, and an Undo inside it sends nothing. No modal. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const H = web.load("history.js");
const SRC = web.source("history.js");
// the code without its comments (the header names what it never does)
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

function el(tag, id) {
  const node = {
    tagName: tag.toUpperCase(), id: id || "", children: [], attrs: {}, hidden: false,
    disabled: false, checked: false, className: "", type: "", listeners: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    replaceChildren(...cs) { this.children = []; cs.forEach((c) => this.appendChild(c)); },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    fire(t) { (this.listeners[t] || []).forEach((f) => f({ target: this })); }
  };
  Object.defineProperty(node, "textContent", {
    get() { return (this._t || "") + this.children.map((c) => c.textContent).join(""); },
    set(v) { this._t = String(v); this.children = []; }
  });
  return node;
}

function fakeDoc() {
  const nodes = {};
  const d = { activeElement: null };
  function make(tag, id) {
    const n = el(tag, id);
    n.focus = () => { d.activeElement = n; };
    if (id) { nodes[id] = n; }
    return n;
  }
  make("div", "historybox");
  make("p", "history-empty");
  make("div", "history-rows");
  make("input", "history-keep");
  make("button", "history-clear");
  make("p", "history-said");
  d.getElementById = (id) => nodes[id] || null;
  d.createElement = (t) => make(t);
  d.createTextNode = (t) => ({ textContent: t });
  return d;
}

/* Manual timers: set records, run() fires the due callbacks. */
function fakeTimers() {
  let now = 0;
  let next = 1;
  const due = new Map();
  return {
    set(f, ms) { const id = next++; due.set(id, { f, at: now + ms }); return id; },
    clear(id) { due.delete(id); },
    advance(ms) {
      now += ms;
      for (const [id, t] of [...due]) {
        if (t.at <= now) { due.delete(id); t.f(); }
      }
    },
    pending: () => due.size
  };
}

function fakeApi(opts) {
  const calls = [];
  const fn = (method, path, body) => {
    calls.push([method, path, body]);
    if (opts && opts.fail) { return Promise.reject(new Error("HTTP 500")); }
    return Promise.resolve({ run_history: { on: true } });
  };
  fn.calls = calls;
  return fn;
}

const tickle = () => new Promise((r) => setImmediate(r));
const clears = (api) => api.calls.filter((c) => c[2] && c[2].clear === true);
const undoOf = (d) => d.getElementById("history-said").children
  .find((c) => c.tagName === "BUTTON");

function setup(opts) {
  const d = fakeDoc();
  const api = fakeApi(opts);
  const t = fakeTimers();
  H.wire(d, api, t);
  // the data starts shown, as paint() leaves it with saved runs
  d.getElementById("history-rows").hidden = false;
  return { d, api, t };
}

test("history undo: undo inside 10 s sends no clear request", async () => {
  const { d, api, t } = setup();
  d.getElementById("history-clear").fire("click");
  assert.equal(d.getElementById("history-rows").hidden, true, "the data is hidden");
  assert.notEqual(d.getElementById("historybox").getAttribute("data-clearing"), null);
  t.advance(H.UNDO_MS - 1);
  undoOf(d).fire("click");
  t.advance(60000);
  await tickle();
  assert.equal(clears(api).length, 0);
  assert.equal(api.calls.length, 0);
  assert.equal(t.pending(), 0, "the timer is cleared");
  assert.equal(d.getElementById("historybox").getAttribute("data-clearing"), null);
  assert.equal(d.getElementById("history-said").textContent, H.KEPT);
  assert.equal(d.activeElement, d.getElementById("history-clear"), "focus goes back");
});

test("history undo: after 10 s exactly one clear request", async () => {
  const { d, api, t } = setup();
  const clear = d.getElementById("history-clear");
  clear.fire("click");
  clear.fire("click");  // a second click inside the window adds nothing
  t.advance(H.UNDO_MS - 1);
  await tickle();
  assert.equal(clears(api).length, 0, "nothing before the window ends");
  t.advance(1);
  await tickle();
  assert.equal(clears(api).length, 1);
  assert.deepEqual(clears(api)[0], ["POST", "/api/run-history", { clear: true }]);
  t.advance(60000);
  await tickle();
  assert.equal(clears(api).length, 1, "exactly one");
  assert.equal(d.getElementById("history-said").textContent, H.CLEARED);
  assert.equal(undoOf(d), undefined, "the Undo button is gone");
  // a new click after the answer starts a new window
  clear.fire("click");
  assert.ok(undoOf(d));
});

test("history undo: a failed clear shows the data again and says so", async () => {
  const { d, api, t } = setup({ fail: true });
  d.getElementById("history-clear").fire("click");
  t.advance(H.UNDO_MS);
  await tickle();
  await tickle();
  assert.equal(clears(api).length, 1);
  assert.equal(d.getElementById("historybox").getAttribute("data-clearing"), null);
  assert.equal(d.getElementById("history-said").textContent, H.FAILED);
});

test("history undo: no modal; the line is in place and focusable", () => {
  const { d } = setup();
  d.getElementById("history-clear").fire("click");
  const said = d.getElementById("history-said");
  const undo = undoOf(d);
  assert.ok(undo, "the Undo button sits in the said line under the clear button");
  assert.equal(undo.parent, said);
  assert.equal(said.textContent, H.PENDING + " " + H.UNDO);
  assert.equal(undo.type, "button");
  assert.equal(undo.disabled, false);
  assert.equal(undo.getAttribute("tabindex"), null, "a plain button, in the tab order");
  assert.ok(undo.getAttribute("aria-label").startsWith(H.UNDO), "label keeps the visible word");
  assert.equal(d.activeElement, undo, "focus moves to Undo");
  assert.doesNotMatch(CODE, /\b(confirm|alert|prompt)\s*\(/);
  assert.doesNotMatch(CODE, /showModal|<dialog|"dialog"/);
});

test("history undo: paint keeps the data hidden while a clear waits", () => {
  const { d, t } = setup();
  const snap = { run_history: { on: true, text: "On.", best: [
    { key: "G1", label: "Act 1", best_s: 600, delta_s: 0 }], deaths_by_zone: [] } };
  d.getElementById("history-clear").fire("click");
  H.paint(d, snap);
  assert.equal(d.getElementById("history-rows").hidden, true);
  assert.equal(d.getElementById("history-empty").hidden, true);
  assert.equal(t.pending(), 1);
  undoOf(d).fire("click");  // Undo repaints the last snapshot at once
  assert.equal(d.getElementById("history-rows").hidden, false);
});
