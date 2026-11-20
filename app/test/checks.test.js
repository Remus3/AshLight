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
  ["checksbox", "checks", "checks-summary",
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

test("language notice: region N owns it; the Hide key is read at wire and stored at once", () => {
  // PLAY-LEGACY-OUT-2: the old #langbox card is gone; checks.js keeps only
  // the stored Hide key that web/notice.js reads with langModel
  assert.equal(ck.paintLang, undefined);
  const store = { v: { "al.lang.dismissed": "100" }, getItem(k) { return this.v[k] || null; },
    setItem(k, v) { this.v[k] = v; } };
  const doc = fakeDoc();
  const asked = [];
  const getById = doc.getElementById;
  doc.getElementById = (id) => { asked.push(id); return getById(id); };
  ck.wire(doc, () => null, {}, store);
  assert.equal(ck._state.dismissed, "100");
  const lang = { verdict: "non_english", since: 100, text: "Your game seems to use..." };
  assert.equal(ck.langModel(lang, ck._state.dismissed).show, false);
  ck.paint(doc, { lang });
  assert.ok(!asked.some((id) => /^lang/.test(id)), asked.join(","));
  // a newer notice shows again; region N's Hide stores its key at once
  const later = Object.assign({}, lang, { since: 200 });
  assert.equal(ck.langModel(later, ck._state.dismissed).show, true);
  ck._state.dismissed = "200";
  assert.equal(store.v["al.lang.dismissed"], "200");
  assert.equal(ck.langModel(later, ck._state.dismissed).show, false);
  assert.equal(ck.langModel({ verdict: "english", text: null }, "200").show, false);
  assert.deepEqual(ck.langModel(null, null), { show: false, text: "", key: "" });
  // nothing stored: none hidden; a store that throws is ignored
  ck.wire(doc, () => null, {}, { getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); } });
  assert.equal(ck._state.dismissed, null);
  ck._state.dismissed = "300";
  assert.equal(ck._state.dismissed, "300");
});
