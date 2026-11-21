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

/* TC-CALC-OPTIN-BUTTON (decision 0018 opt-in, decision 0041 amendment
   2026-11-20): the calc row's "Set up the calc" button. */
function calcLi(doc) {
  return doc.ids["checks-list"].children.find((li) =>
    li.children.some((c) => c.children && c.children.some((n) => n.textContent === "Calc component")));
}

function calcButton(doc) {
  const li = calcLi(doc);
  return li ? li.children.find((c) => c.tagName === "button") || null : null;
}

function calcSaid(doc) {
  const li = calcLi(doc);
  const p = li ? li.children.find((c) => c.attrs && c.attrs.role === "status") : null;
  return p ? p.textContent : "";
}

function withCalc(status) {
  return { diag: Object.assign({}, DIAG, { checks: DIAG.checks.map((c) =>
    (c.id === "calc" ? Object.assign({}, c, { status: status }) : c)) }) };
}

test("calc button: only in the client, only while the calc row is off or needs a fix", (t) => {
  t.after(() => { ck._state.client = undefined; ck._state.calc = ""; ck._state.calcRow = null; });
  // a plain browser (no window.alClient): never a button
  ck._state.client = undefined;
  let doc = fakeDoc();
  ck.paint(doc, withCalc("off"));
  assert.equal(calcButton(doc), null);
  // a client without the action: none either
  ck._state.client = { restartOverlay() {} };
  doc = fakeDoc();
  ck.paint(doc, withCalc("off"));
  assert.equal(calcButton(doc), null);
  ck._state.client = { setupCalc: () => new Promise(() => {}) };
  for (const [status, shown] of [["off", true], ["fail", true], ["pass", false],
                                 ["unknown", false], ["note", false]]) {
    doc = fakeDoc();
    ck.paint(doc, withCalc(status));
    const b = calcButton(doc);
    assert.equal(!!b, shown, status);
    if (b) {
      assert.equal(b.textContent, ck.CALC_BUTTON);
      assert.equal(b.textContent, "Set up the calc");
      assert.equal(b.type, "button");
    }
  }
  // no other row ever gets it
  doc = fakeDoc();
  ck.paint(doc, withCalc("off"));
  const withButton = doc.ids["checks-list"].children.filter((li) =>
    li.children.some((c) => c.tagName === "button"));
  assert.equal(withButton.length, 1);
  // the model on its own
  assert.deepEqual(ck.calcModel({ id: "calc", word: "off" }, false, ""), { button: false, said: "" });
  assert.deepEqual(ck.calcModel({ id: "log", word: "off" }, true, ""), { button: false, said: "" });
});

test("calc button: a click runs the client's one action, then pending, then ok or failed", async (t) => {
  t.after(() => { ck._state.client = undefined; ck._state.calc = ""; ck._state.calcRow = null; });
  ck._state.calc = "";
  ck._state.calcRow = null;
  let finish = null;
  const asked = [];
  ck._state.client = { setupCalc: (...a) => { asked.push(a); return new Promise((r) => { finish = r; }); } };
  const doc = fakeDoc();
  ck.paint(doc, withCalc("off"));
  calcButton(doc).listeners.click();
  assert.deepEqual(asked, [[]], "the action takes no argument");
  // pending: the line says it works in the background, no second button
  assert.equal(calcSaid(doc), ck.CALC_PENDING);
  assert.equal(calcButton(doc), null);
  ck.paint(doc, withCalc("off")); // a new snapshot while it runs
  assert.equal(calcSaid(doc), ck.CALC_PENDING);
  assert.equal(calcButton(doc), null);
  finish({ ok: true });
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_OK);
  assert.equal(calcButton(doc), null, "no button after a good setup");
  // the core's row moves on: the line clears and the row speaks for itself
  ck.paint(doc, withCalc("pass"));
  assert.equal(calcSaid(doc), "");
  assert.equal(calcButton(doc), null);

  // a failed setup says so and offers the button again
  ck.paint(doc, withCalc("fail"));
  calcButton(doc).listeners.click();
  assert.equal(calcSaid(doc), ck.CALC_PENDING);
  finish({ ok: false });
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  assert.ok(calcButton(doc));
  // a refused or throwing action reads as failed too
  ck._state.client = { setupCalc: () => Promise.reject(new Error("x")) };
  ck.paint(doc, withCalc("fail"));
  calcButton(doc).listeners.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  ck._state.client = { setupCalc: () => { throw new Error("y"); } };
  ck.paint(doc, withCalc("fail"));
  calcButton(doc).listeners.click();
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  // a stranger answer (null: not the companion) is a failure, never ok
  ck._state.client = { setupCalc: () => Promise.resolve(null) };
  calcButton(doc).listeners.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
});
