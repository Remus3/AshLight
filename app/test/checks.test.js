/* DIAG-SELF / LANG-GUARD: the dashboard helpers in web/checks.js. The core
   sends every check, sentence and the redacted report; these only show
   them, and the clipboard is written only inside the copy click. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const ck = web.load("checks.js");

const DIAG = {
  summary: "1 check needs a fix.", failed: 1, report: "AshLight 1 self-check\n[FIX] X\n",
  checks: [
    { id: "log", label: "Client.txt", status: "pass", detail: "Found.", fix: null },
    { id: "overlay", label: "Overlay", status: "fail", detail: "Not running.",
      fix: "Run scripts\\run.ps1." },
    { id: "calc", label: "Calc component", status: "off", detail: "Off.", fix: null },
    { id: "hotkey", label: "Item check hotkey", status: "unknown", detail: "Later.", fix: null }]
};

function el(tag) {
  const node = {
    tagName: tag, children: [], attrs: {}, hidden: false, open: false, disabled: false,
    textContent: "", className: "", listeners: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, f) { this.listeners[t] = f; }
  };
  Object.defineProperty(node, "textContent", {
    get() { return this._t || ""; },
    set(v) { this._t = String(v); if (v === "") { this.children = []; } }
  });
  return node;
}

function fakeDoc() {
  const ids = {};
  ["langbox", "lang-text", "lang-dismiss", "checksbox", "checks", "checks-summary",
    "checks-list", "checks-copy", "checks-said"].forEach((id) => { ids[id] = el("x"); });
  return {
    ids,
    getElementById: (id) => ids[id] || null,
    createElement: (t) => el(t),
    createTextNode: (t) => ({ textContent: t })
  };
}

test("checks: model maps every status to a glyph and a word", () => {
  const m = ck.model(DIAG);
  assert.equal(m.summary, "1 check needs a fix.");
  assert.deepEqual(m.rows.map((r) => [r.glyph, r.word]), [
    ["[+]", "ok"], ["[#]", "needs a fix"], ["[-]", "off"], ["[ ]", "not known yet"]]);
  assert.equal(m.rows[1].fix, "Run scripts\\run.ps1.");
  assert.deepEqual(ck.model(null), { summary: ck.WAITING, failed: 0, rows: [], report: "" });
});

test("checks: paint opens the fold on a new failure only", () => {
  const doc = fakeDoc();
  ck.paint(doc, { diag: DIAG });
  assert.equal(doc.ids.checks.open, true);
  assert.equal(doc.ids["checks-summary"].textContent, "1 check needs a fix.");
  assert.equal(doc.ids["checks-list"].children.length, 4);
  assert.equal(doc.ids["checks-copy"].disabled, false);
  doc.ids.checks.open = false; // the player closed it
  ck.paint(doc, { diag: Object.assign({}, DIAG, { summary: "same, new text" }) });
  assert.equal(doc.ids.checks.open, false);
  ck.paint(doc, { diag: { summary: "All checks pass.", failed: 0, report: "r", checks: [] } });
  assert.equal(doc.ids.checks.open, false);
});

test("checks: copy writes the core's report only in the click", async () => {
  const doc = fakeDoc();
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null);
  assert.deepEqual(wrote, []);
  doc.ids["checks-copy"].listeners.click();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(wrote, [DIAG.report]);
  assert.equal(doc.ids["checks-said"].textContent, ck.COPIED);
  ck.wire(doc, () => ({ diag: DIAG }), {}, null);
  doc.ids["checks-copy"].listeners.click();
  assert.equal(doc.ids["checks-said"].textContent, ck.COPY_FAILED);
});

test("language notice: shows, hides on click, returns only when it begins again", () => {
  ck._state.dismissed = undefined;
  const doc = fakeDoc();
  const store = { v: {}, getItem(k) { return this.v[k] || null; },
    setItem(k, v) { this.v[k] = v; } };
  ck.wire(doc, () => null, {}, store);
  const lang = { verdict: "non_english", since: 100, text: "Your game seems to use..." };
  ck.paint(doc, { lang });
  assert.equal(doc.ids.langbox.hidden, false);
  assert.equal(doc.ids["lang-text"].textContent, lang.text);
  doc.ids["lang-dismiss"].listeners.click();
  assert.equal(doc.ids.langbox.hidden, true);
  ck.paint(doc, { lang });
  assert.equal(doc.ids.langbox.hidden, true);
  ck.paint(doc, { lang: Object.assign({}, lang, { since: 200 }) });
  assert.equal(doc.ids.langbox.hidden, false);
  ck.paint(doc, { lang: { verdict: "english", text: null } });
  assert.equal(doc.ids.langbox.hidden, true);
  assert.deepEqual(ck.langModel(null, null), { show: false, text: "", key: "" });
});
