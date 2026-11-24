"use strict";
/* REL-AUTOSTART-SETTINGS (F-073; decision 0011, ruling Q-08): the 'Start
   with Windows' row of Settings > Appearance and tools (web/autostart.js).
   It shows the client's recorded choice and passes the click on through
   the preload's fixed actions; a plain browser gets a disabled box and
   'Set this in the AshLight app'. Fake client and timers: nothing runs. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");

const A = web.load("autostart.js");
const HTML = web.source("index.html", "ascii");

function el(id) {
  const n = { id, checked: false, disabled: false, textContent: "", attrs: {}, on: {} };
  n.addEventListener = (ev, f) => { (n.on[ev] = n.on[ev] || []).push(f); };
  n.fire = (ev) => (n.on[ev] || []).forEach((f) => f({ target: n }));
  return n;
}

function fakeDoc() {
  const nodes = { "autostart-on": el("autostart-on"), "autostart-said": el("autostart-said") };
  return { getElementById: (id) => nodes[id] || null };
}

function fakeClient(enabled) {
  const calls = [];
  const c = {
    calls,
    rec: enabled,
    autostartOn() { calls.push("on"); },
    autostartOff() { calls.push("off"); },
    autostartState() { calls.push("state"); return Promise.resolve({ enabled: c.rec }); }
  };
  return c;
}

function fakeTimers() {
  const due = [];
  return { due, set(fn, ms) { due.push([ms, fn]); }, runAll() { due.splice(0).forEach(([, f]) => f()); } };
}

const tick = () => new Promise((r) => setImmediate(r));

test("model: client absent, present on / off, and the plain-browser wording", () => {
  for (const c of [null, undefined, {}, { autostartOn() {}, autostartOff() {} }]) {
    const m = A.model(c, { enabled: true }, null);
    assert.deepEqual(m, { client: false, disabled: true, checked: false, line: A.TEXT.browser });
  }
  assert.equal(A.TEXT.browser, "Set this in the AshLight app.");
  const c = fakeClient(false);
  assert.deepEqual(A.model(c, { enabled: true }, null),
    { client: true, disabled: false, checked: true, line: A.TEXT.on });
  assert.deepEqual(A.model(c, { enabled: false }, null),
    { client: true, disabled: false, checked: false, line: A.TEXT.off });
  // not read yet, a failed read, and a click still saving
  assert.equal(A.model(c, null, null).disabled, true);
  assert.equal(A.model(c, null, null).line, A.TEXT.reading);
  assert.equal(A.model(c, "failed", null).line, A.TEXT.unknown);
  const saving = A.model(c, { enabled: false }, true);
  assert.deepEqual(saving, { client: true, disabled: true, checked: true, line: A.TEXT.saving });
  // a click that matches the record is done
  assert.equal(A.model(c, { enabled: true }, true).line, A.TEXT.on);
  // the client's action names never take an argument (ruling Q-08)
  assert.doesNotMatch(web.source("autostart.js"), /autostart(On|Off|State)\([^)]/);
});

test("a plain browser: the box stays disabled and nothing is asked", async () => {
  const doc = fakeDoc();
  A.wire(doc, null, fakeTimers());
  await tick();
  assert.equal(doc.getElementById("autostart-on").disabled, true);
  assert.equal(doc.getElementById("autostart-on").checked, false);
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.browser);
});

test("the client: one read at wire time shows the recorded choice by itself", async () => {
  for (const on of [true, false]) {
    const doc = fakeDoc();
    const c = fakeClient(on);
    A.wire(doc, c, fakeTimers());
    assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.reading);
    await tick();
    assert.deepEqual(c.calls, ["state"]);
    assert.equal(doc.getElementById("autostart-on").checked, on);
    assert.equal(doc.getElementById("autostart-on").disabled, false);
    assert.equal(doc.getElementById("autostart-said").textContent, on ? A.TEXT.on : A.TEXT.off);
  }
});

test("a click passes on, then the row follows the record once the script ran", async () => {
  const doc = fakeDoc();
  const c = fakeClient(false);
  const t = fakeTimers();
  A.wire(doc, c, t);
  await tick();
  const box = doc.getElementById("autostart-on");
  box.checked = true;
  box.fire("change");
  assert.deepEqual(c.calls, ["state", "on"]);
  assert.equal(box.disabled, true);
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.saving);
  assert.deepEqual(t.due.map(([ms]) => ms), A.RECHECK_MS);
  box.fire("change"); // a second change while saving sends nothing
  assert.deepEqual(c.calls, ["state", "on"]);
  c.rec = true; // the script recorded the choice
  t.due.shift()[1]();
  await tick();
  assert.equal(box.checked, true);
  assert.equal(box.disabled, false);
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.on);
  t.runAll(); // the later checks see nothing pending: no read
  await tick();
  assert.deepEqual(c.calls, ["state", "on", "state"]);
  // and back off
  box.checked = false;
  box.fire("change");
  assert.equal(c.calls[c.calls.length - 1], "off");
});

test("a click the record never follows: the box goes back and says not saved", async () => {
  const doc = fakeDoc();
  const c = fakeClient(false);
  const t = fakeTimers();
  A.wire(doc, c, t);
  await tick();
  const box = doc.getElementById("autostart-on");
  box.checked = true;
  box.fire("change");
  for (let i = 0; i < A.RECHECK_MS.length; i++) {
    t.due.shift()[1]();
    await tick();
  }
  assert.equal(box.checked, false);
  assert.equal(box.disabled, false);
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.notSaved);
});

test("a failed read: disabled with a plain line, no click passes on", async () => {
  const doc = fakeDoc();
  const c = fakeClient(false);
  c.autostartState = () => Promise.reject(new Error("x"));
  A.wire(doc, c, fakeTimers());
  await tick();
  assert.equal(doc.getElementById("autostart-on").disabled, true);
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.unknown);
  doc.getElementById("autostart-on").fire("change");
  assert.deepEqual(c.calls, []);
});

test("the page: one 32 px row with a label in Appearance and tools, the script before app.js", () => {
  const tools = HTML.indexOf('<section id="toolsbox"');
  const end = HTML.indexOf("</section>", tools);
  const row = HTML.indexOf('<p id="autostart-row" class="set-row">');
  assert.ok(tools > 0 && row > tools && row < end, "the row sits in section 5");
  assert.equal(HTML.split('id="autostart-row"').length, 2);
  const rowHtml = HTML.slice(row, HTML.indexOf("</p>", row));
  assert.match(rowHtml, /<label class="check" for="autostart-on"><input\s+id="autostart-on" type="checkbox" disabled aria-describedby="autostart-said"> Start with Windows<\/label>/);
  assert.match(rowHtml, /<span id="autostart-said" class="muted">Set this in the AshLight app\.<\/span>/);
  assert.equal(A.LABEL, "Start with Windows");
  assert.doesNotMatch(rowHtml, /aria-live|role="status"/);
  const s = HTML.indexOf("/web/autostart.js");
  assert.ok(s > 0 && s < HTML.indexOf("/web/app.js"));
  for (const t of Object.values(A.TEXT)) { assert.ok(t.length <= 94, t); }
});

test("SAVE-FAIL-SAY: a failed save is also said in the header's polite #tab-news", async () => {
  // the record never follows the click
  const doc = fakeDoc();
  const news = el("tab-news");
  const get = doc.getElementById;
  doc.getElementById = (id) => (id === "tab-news" ? news : get(id));
  const c = fakeClient(false);
  const t = fakeTimers();
  A.wire(doc, c, t);
  await tick();
  const box = doc.getElementById("autostart-on");
  box.checked = true;
  box.fire("change");
  assert.equal(news.textContent, "", "saving says nothing");
  for (let i = 0; i < A.RECHECK_MS.length; i++) {
    t.due.shift()[1]();
    await tick();
  }
  assert.equal(doc.getElementById("autostart-said").textContent, A.TEXT.notSaved);
  assert.equal(news.textContent, A.TEXT.notSaved);
  // the client's action throws
  const d2 = fakeDoc();
  const n2 = el("tab-news");
  const g2 = d2.getElementById;
  d2.getElementById = (id) => (id === "tab-news" ? n2 : g2(id));
  const c2 = fakeClient(false);
  c2.autostartOn = () => { throw new Error("x"); };
  A.wire(d2, c2, fakeTimers());
  await tick();
  d2.getElementById("autostart-on").checked = true;
  d2.getElementById("autostart-on").fire("change");
  assert.equal(d2.getElementById("autostart-said").textContent, A.TEXT.notSaved);
  assert.equal(n2.textContent, A.TEXT.notSaved);
  // a save that the record follows says nothing on the polite line
  const d3 = fakeDoc();
  const n3 = el("tab-news");
  const g3 = d3.getElementById;
  d3.getElementById = (id) => (id === "tab-news" ? n3 : g3(id));
  const c3 = fakeClient(false);
  const t3 = fakeTimers();
  A.wire(d3, c3, t3);
  await tick();
  d3.getElementById("autostart-on").checked = true;
  d3.getElementById("autostart-on").fire("change");
  c3.rec = true;
  t3.due.shift()[1]();
  await tick();
  assert.equal(d3.getElementById("autostart-said").textContent, A.TEXT.on);
  assert.equal(n3.textContent, "");
});
