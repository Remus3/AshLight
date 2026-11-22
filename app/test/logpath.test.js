/* SEC-LOG-PATH-FIELD (web/logpath.js, F-098): the "Can't find
   Client.txt?" field in Settings, Reading and web data. It shows only
   while the core's Checks row "log" fails; Use posts the existing consent
   API {consent: true, path}; the core's 400 shows as a what-happened and
   what-to-do sentence that also marks the field invalid; the answer line
   sits after the form and is not a live region (page cap). Paths are built at run time: no file here spells
   a drive path (tests/test_sidecar_paths.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const W = require("./_web.js");
const L = W.load("logpath.js");

const HTML = W.source("index.html");
const SRC = W.source("logpath.js");
const APP = W.source("app.js");
const DRIVE = "C" + ":";
const GAME = DRIVE + "\\Program Files\\Games\\PoE2";
const LOG = GAME + "\\logs\\Client.txt";

function snapWith(rows) { return { diag: { checks: rows } }; }

function makeDoc() {
  const byId = {};
  function node(id, extra) {
    const n = Object.assign({ id: id, hidden: false, value: "", textContent: "",
      attrs: {}, listeners: {}, addEventListener(k, fn) { this.listeners[k] = fn; },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      removeAttribute(k) { delete this.attrs[k]; } }, extra || {});
    byId[id] = n;
    return n;
  }
  node("logpath-form", { hidden: true });
  node("logpath-in");
  node("logpath-said");
  return { byId, getElementById(id) { return byId[id] || null; } };
}

function resolved(value) {
  return { then(ok) { ok(value); return this; } };
}

function rejected(err) {
  return { then(ok, bad) { bad(err); return this; } };
}

test("the field shows only while the log check fails", () => {
  assert.equal(L.view(snapWith([{ id: "log", status: "fail" }])).show, true);
  assert.equal(L.view(snapWith([{ id: "log", status: "pass" }])).show, false);
  assert.equal(L.view(snapWith([{ id: "consent", status: "fail" }])).show, false);
  assert.equal(L.view(snapWith([{ id: "log", status: "note" }])).show, false);
  assert.equal(L.view({}).show, false);
  assert.equal(L.view(null).show, false);
  assert.equal(L.view({ diag: null }).show, false);
  assert.equal(L.view({ diag: { checks: "log" } }).show, false);
});

test("paint toggles the form from the snapshot and never touches the typed text", () => {
  const doc = makeDoc();
  doc.byId["logpath-in"].value = GAME;
  L.paint(doc, snapWith([{ id: "log", status: "fail" }]));
  assert.equal(doc.byId["logpath-form"].hidden, false);
  assert.equal(doc.byId["logpath-in"].value, GAME);
  L.paint(doc, snapWith([{ id: "log", status: "pass" }]));
  assert.equal(doc.byId["logpath-form"].hidden, true);
  L.paint({ getElementById() { return null; } }, {}); // no form: no throw
});

test("the payload is the consent API's own shape", () => {
  assert.deepEqual(L.payload("  " + LOG + " "),
    { consent: true, path: LOG });
  assert.deepEqual(L.payload("\"" + GAME + "\""), { consent: true, path: GAME });
  assert.deepEqual(Object.keys(L.payload(DRIVE + "\\Program Files\\x")).sort(), ["consent", "path"]);
  assert.equal(L.payload(""), null);
  assert.equal(L.payload("   "), null);
  assert.equal(L.payload("\"\""), null);
  assert.equal(L.payload(null), null);
  assert.equal(L.payload(DRIVE + "\\Program Files\\" + "a".repeat(L.MAX_PATH)), null);
});

test("Use posts /api/consent once and paints the answer's state", () => {
  L.reset();
  const doc = makeDoc();
  const calls = [];
  const states = [];
  const state = { tailer: { consented: true } };
  L.wire(doc, (m, p, b) => { calls.push([m, p, b]); return resolved({ state }); },
    (s) => states.push(s));
  doc.byId["logpath-in"].value = GAME;
  let prevented = false;
  doc.byId["logpath-form"].listeners.submit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(calls, [["POST", "/api/consent", { consent: true, path: GAME }]]);
  assert.deepEqual(states, [state]);
  assert.equal(doc.byId["logpath-said"].textContent, L.SAVED);
  assert.equal(doc.byId["logpath-in"].value, "");
});

test("an empty field posts nothing", () => {
  L.reset();
  const doc = makeDoc();
  let n = 0;
  assert.equal(L.submit(doc, () => { n += 1; return resolved({}); }), null);
  assert.equal(n, 0);
});

test("a bad path shows the core's 400 words, anything else the retry line", () => {
  L.reset();
  const doc = makeDoc();
  doc.byId["logpath-in"].value = "relative\\path";
  L.submit(doc, () => rejected(new Error("HTTP 400")));
  assert.equal(doc.byId["logpath-said"].textContent, L.BAD_PATH);
  assert.equal(doc.byId["logpath-in"].value, "relative\\path"); // kept for a fix
  assert.equal(doc.byId["logpath-in"].attrs["aria-invalid"], "true");
  L.submit(doc, () => rejected(new Error("HTTP 500")));
  assert.equal(doc.byId["logpath-said"].textContent, L.NOT_SAVED);
  assert.equal(doc.byId["logpath-in"].attrs["aria-invalid"], undefined);
  L.submit(doc, () => rejected(new TypeError("Failed to fetch")));
  assert.equal(doc.byId["logpath-said"].textContent, L.NOT_SAVED);
});

test("one post at a time", () => {
  L.reset();
  const doc = makeDoc();
  doc.byId["logpath-in"].value = GAME;
  let n = 0;
  const pending = { then() { return this; } };
  L.submit(doc, () => { n += 1; return pending; });
  L.submit(doc, () => { n += 1; return pending; });
  assert.equal(n, 1);
  L.reset();
});

test("hiding the form clears a failed answer and keeps a Saved line", () => {
  const doc = makeDoc();
  const fail = snapWith([{ id: "log", status: "fail" }]);
  const pass = snapWith([{ id: "log", status: "pass" }]);
  L.paint(doc, fail);
  doc.byId["logpath-said"].textContent = L.BAD_PATH;
  L.paint(doc, fail); // still shown: the answer stays
  assert.equal(doc.byId["logpath-said"].textContent, L.BAD_PATH);
  L.paint(doc, pass);
  assert.equal(doc.byId["logpath-said"].textContent, "");
  L.paint(doc, fail);
  doc.byId["logpath-said"].textContent = L.SAVED;
  L.paint(doc, pass);
  assert.equal(doc.byId["logpath-said"].textContent, L.SAVED);
});

test("the bad-path line says what happened and what to do, with no HTTP code", () => {
  assert.match(L.BAD_PATH, /^AshLight can't use that path\. Type /);
  assert.match(L.BAD_PATH, /Client\.txt/);
  assert.doesNotMatch(L.BAD_PATH + L.NOT_SAVED + L.SAVED, /HTTP|400|!|core|token/);
});

test("the markup: a labelled field in Reading and web data, hidden, a quiet answer line", () => {
  const sec = HTML.slice(HTML.indexOf("<section id=\"set-reading\""));
  const body = sec.slice(0, sec.indexOf("</section>"));
  const form = body.slice(body.indexOf("<form id=\"logpath-form\""), body.indexOf("</form>"));
  assert.ok(form.length > 0, "the form sits inside #set-reading");
  assert.match(form, /<form id="logpath-form"[^>]*\bhidden\b/);
  assert.match(form, /<label for="logpath-in">Can't find Client\.txt\?/);
  assert.match(form, /<input id="logpath-in" type="text" maxlength="1024"/);
  assert.match(form, /<button id="logpath-use" type="submit"[^>]*>Use<\/button>/);
  assert.doesNotMatch(form, /aria-live|role="status"|role="alert"|id="logpath-said"/);
  const after = body.slice(body.indexOf("</form>"));
  assert.match(after, /^<\/form>\s*<p id="logpath-said" class="row-meta"><\/p>/);
  assert.match(form, /<input id="logpath-in"[^>]*aria-describedby="logpath-note logpath-said"/);
  assert.match(form, /<button id="logpath-use"[^>]*aria-describedby="logpath-said"[^>]*>Use<\/button>/);
  assert.match(HTML, /<script src="\/web\/logpath\.js" defer><\/script>/);
});

test("app.js calls the module from the consent painter and its wire step", () => {
  const start = APP.indexOf("name: \"consent\"");
  const block = APP.slice(start, APP.indexOf("A.register(", start));
  assert.match(block, /window\.ALLogPath\.paint\(document, s\)/);
  assert.match(block, /window\.ALLogPath\.wire\(document, api, render\)/);
});

test("the module reads nothing and starts no timer", () => {
  assert.doesNotMatch(SRC, /setTimeout|setInterval|navigator\.|localStorage|fetch\(/);
});
