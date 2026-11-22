/* DIAG-SELF / LANG-GUARD: the dashboard helpers in web/checks.js. The core
   sends every check, sentence and the redacted report; these only show
   them, and the clipboard is written only inside the copy click.
   RUN-REPORT-ROUTE (folded into RUN-VERDICTS-UI): the report is built on
   the click by GET /api/report into a read-only preview, and Copy report
   writes exactly the previewed text, synchronously inside its click. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const ck = web.load("checks.js");

const DIAG = {
  summary: "1 check needs a fix.", failed: 1,
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
  ["checksbox", "checks", "checks-summary", "checks-list", "checks-copy", "checks-said",
    "checks-preview", "checks-preview-box"].forEach((id) => { ids[id] = el("x"); });
  ids["checks-preview-box"].hidden = true;
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
  assert.deepEqual(ck.model(null), { summary: ck.WAITING, failed: 0, rows: [] });
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
  ck.paint(doc, { diag: { summary: "All checks pass.", failed: 0, checks: [] } });
  assert.equal(doc.ids.checks.open, false);
});

/* app.js api() stand-in: GET /api/report answers `text` (or fails). */
function reportApi(text, calls) {
  return (method, path, body) => {
    calls.push([method, path, body]);
    if (text === null) { return Promise.reject(new Error("HTTP 500")); }
    return Promise.resolve({ report: text });
  };
}

const REPORT = "AshLight 0.1.0 (abc) self-check, 2026-11-21 10:00 UTC\n[FIX] Overlay: Not running.\n";
const tickle = () => new Promise((r) => setImmediate(r));

test("checks: the copy button waits only for the first checks", () => {
  const doc = fakeDoc();
  ck.paint(doc, { diag: DIAG });
  assert.equal(doc.ids["checks-copy"].disabled, false, "the route builds it, not the snapshot");
  const empty = fakeDoc();
  ck.paint(empty, { diag: { summary: "x", failed: 0, checks: [] } });
  assert.equal(empty.ids["checks-copy"].disabled, true);
});

test("checks: opening the fold builds the preview; a fold that opens by itself builds nothing", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, reportApi(REPORT, calls));
  assert.deepEqual(calls, [], "nothing is built at wire time");
  ck.paint(doc, { diag: DIAG }); // a failure opens the fold by itself
  assert.equal(doc.ids.checks.open, true);
  assert.deepEqual(calls, [], "no click, no build");
  doc.ids.checks.open = false;
  doc.ids["checks-summary"].listeners.click(); // the player opens it
  assert.deepEqual(calls, [["GET", "/api/report", undefined]]);
  assert.equal(doc.ids["checks-said"].textContent, ck.BUILDING);
  await tickle();
  assert.equal(doc.ids["checks-preview"].value, REPORT);
  assert.equal(doc.ids["checks-preview-box"].hidden, false);
  assert.equal(doc.ids["checks-said"].textContent, ck.READY);
  // closing it builds nothing
  doc.ids.checks.open = true;
  doc.ids["checks-summary"].listeners.click();
  assert.equal(calls.length, 1);
  assert.deepEqual(wrote, [], "building the preview never writes the clipboard");
});

test("checks: preview equals the copied text byte for byte", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, reportApi(REPORT, calls));
  doc.ids["checks-summary"].listeners.click();
  await tickle();
  doc.ids["checks-copy"].listeners.click();
  assert.equal(wrote.length, 1);
  assert.equal(wrote[0], doc.ids["checks-preview"].value);
  assert.equal(Buffer.compare(Buffer.from(wrote[0], "utf8"), Buffer.from(REPORT, "utf8")), 0);
  // RUN-QUIET-FEED: the snapshot carries no report of its own
  assert.equal("report" in DIAG, false);
  await tickle();
  assert.equal(doc.ids["checks-said"].textContent, ck.COPIED);
  assert.equal(calls.length, 1, "the copy click builds nothing");
});

test("checks: clipboard only inside the click", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  let inClick = false;
  const nav = { clipboard: { writeText: (t) => {
    assert.ok(inClick, "writeText outside the click");
    wrote.push(t);
    return Promise.resolve();
  } } };
  const click = (id) => { inClick = true; try { doc.ids[id].listeners.click(); } finally { inClick = false; } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, reportApi(REPORT, calls));
  // no preview yet (the fold opened by itself): this click builds it and
  // copies nothing, not even once the build answers
  click("checks-copy");
  assert.deepEqual(calls, [["GET", "/api/report", undefined]]);
  await tickle();
  await tickle();
  assert.deepEqual(wrote, [], "never written after a wait");
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_AGAIN);
  // the next click copies, synchronously inside it
  click("checks-copy");
  assert.deepEqual(wrote, [REPORT]);
  // a failed build says so and copies nothing
  const bad = fakeDoc();
  const none = [];
  ck.wire(bad, () => ({ diag: DIAG }), nav, null, reportApi(null, none));
  inClick = true;
  bad.ids["checks-copy"].listeners.click();
  inClick = false;
  await tickle();
  assert.equal(bad.ids["checks-said"].textContent, ck.BUILD_FAILED);
  assert.equal(bad.ids["checks-preview-box"].hidden, true);
  assert.deepEqual(wrote, [REPORT]);
  // no clipboard: the copy says it failed
  const plain = fakeDoc();
  ck.wire(plain, () => ({ diag: DIAG }), {}, null, reportApi(REPORT, []));
  plain.ids["checks-summary"].listeners.click();
  await tickle();
  plain.ids["checks-copy"].listeners.click();
  assert.equal(plain.ids["checks-said"].textContent, ck.COPY_FAILED);
  // the source writes the clipboard in one place, never after a then
  const src = web.source("checks.js");
  assert.equal(src.split("clipboard.writeText(").length - 1, 1);
  assert.ok(!/\.then\(function \(res\) \{[^}]*writeText/.test(src));
  assert.ok(!/setTimeout|setInterval/.test(src));
});

/* VERDICTS-UI-A11Y: the RUN-VERDICTS-UI design review, V-4 to V-6. */
test("checks V-4: after an auto-opened fold the Copy click says the report is below", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, reportApi(REPORT, calls));
  ck.paint(doc, { diag: DIAG }); // the fold opens by itself: no preview yet
  assert.equal(doc.ids.checks.open, true);
  doc.ids["checks-copy"].listeners.click();
  await tickle();
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_AGAIN);
  assert.equal(ck.READY_AGAIN, "The report is below. Press Copy report again to copy it.");
  assert.notEqual(ck.READY_AGAIN, ck.READY);
  assert.deepEqual(wrote, []);
  doc.ids["checks-copy"].listeners.click();
  assert.deepEqual(wrote, [REPORT]);
  // opening the fold by hand keeps the plain line
  const d2 = fakeDoc();
  ck.wire(d2, () => ({ diag: DIAG }), nav, null, reportApi(REPORT, []));
  d2.ids["checks-summary"].listeners.click();
  await tickle();
  assert.equal(d2.ids["checks-said"].textContent, ck.READY);
});

test("checks V-5: a preview older than the checks' states is made again before a copy", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  let text = REPORT;
  const api = (method, path) => { calls.push([method, path]); return Promise.resolve({ report: text }); };
  let inClick = false;
  const nav = { clipboard: { writeText: (t) => {
    assert.ok(inClick, "writeText outside the click");
    wrote.push(t);
    return Promise.resolve();
  } } };
  const click = (id) => { inClick = true; try { doc.ids[id].listeners.click(); } finally { inClick = false; } };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, api);
  ck.paint(doc, { diag: DIAG });
  doc.ids.checks.open = false; // the player closed it, then opens it again
  click("checks-summary");
  await tickle();
  assert.equal(calls.length, 1);
  // new wording only (the minutes age): the preview is still current
  ck.paint(doc, { diag: Object.assign({}, DIAG, { summary: "same states, new words" }) });
  click("checks-copy");
  assert.deepEqual(wrote, [REPORT]);
  assert.equal(calls.length, 1);
  // a check changes its state while the fold is open
  const fixed = Object.assign({}, DIAG, { failed: 0, summary: "All checks pass.",
    checks: DIAG.checks.map((c) => (c.id === "overlay" ? Object.assign({}, c, { status: "pass" }) : c)) });
  text = "AshLight 0.1.0 (abc) self-check, 2026-11-21 10:05 UTC\n[OK] Overlay\n";
  ck.paint(doc, { diag: fixed });
  click("checks-copy"); // remakes the preview, copies nothing
  assert.equal(calls.length, 2);
  assert.deepEqual(wrote, [REPORT]);
  await tickle();
  assert.equal(doc.ids["checks-preview"].value, text);
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_CHANGED);
  assert.match(ck.READY_CHANGED, /Press Copy report again to copy it\.$/);
  click("checks-copy"); // the next click copies the new preview, synchronously
  assert.deepEqual(wrote, [REPORT, text]);
  assert.equal(calls.length, 2);
});

test("checks W-1: a Copy click that builds the preview moves the focus to the said line", async () => {
  const setup = (text) => {
    const doc = fakeDoc();
    doc.activeElement = null;
    Object.values(doc.ids).forEach((n) => { n.focus = () => { doc.activeElement = n; }; });
    const nav = { clipboard: { writeText: () => Promise.resolve() } };
    ck.wire(doc, () => ({ diag: DIAG }), nav, null, reportApi(text, []));
    return doc;
  };
  // V-4 path: no preview yet
  let doc = setup(REPORT);
  doc.ids["checks-copy"].focus();
  doc.ids["checks-copy"].listeners.click();
  assert.equal(doc.activeElement, doc.ids["checks-copy"], "focus stays while it builds");
  await tickle();
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_AGAIN);
  assert.equal(doc.activeElement, doc.ids["checks-said"]);
  // V-5 path: a check changed state since the preview was made
  doc.ids["checks-copy"].focus();
  ck.paint(doc, { diag: Object.assign({}, DIAG, {
    checks: DIAG.checks.map((c) => (c.id === "hotkey" ? Object.assign({}, c, { status: "pass" }) : c)) }) });
  doc.ids["checks-copy"].listeners.click();
  await tickle();
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_CHANGED);
  assert.equal(doc.activeElement, doc.ids["checks-said"]);
  // focus moved elsewhere during the build is left alone
  doc = setup(REPORT);
  doc.ids["checks-copy"].focus();
  doc.ids["checks-copy"].listeners.click();
  doc.ids["checks-summary"].focus();
  await tickle();
  assert.equal(doc.activeElement, doc.ids["checks-summary"]);
  // a failed build moves nothing
  doc = setup(null);
  doc.ids["checks-copy"].focus();
  doc.ids["checks-copy"].listeners.click();
  await tickle();
  assert.equal(doc.ids["checks-said"].textContent, ck.BUILD_FAILED);
  assert.equal(doc.activeElement, doc.ids["checks-copy"]);
  // the said line can take the focus
  assert.match(web.source("index.html"), /<p id="checks-said" class="muted" tabindex="-1"><\/p>/);
});

test("checks V-6: the preview is 6 rows, full width, inside the Checks fold", () => {
  const html = web.source("index.html");
  assert.match(html, /<textarea id="checks-preview" class="code-out" readonly rows="6" spellcheck="false"><\/textarea>/);
  const css = web.source("app.css");
  assert.match(css, /\.code-out \{ width: 100%;/);
  assert.match(css, /\.paste-box \{ width: 100%;/);
  // a tab's column scrolls on its own, so the open fold never pushes the page
  assert.match(css, /\.panel-grid > \.col \{ max-height: 100%; overflow-y: auto;/);
  const fold = html.indexOf('<details id="checks">');
  const end = html.indexOf("</details>", fold);
  const box = html.indexOf('id="checks-preview-box"');
  assert.ok(fold > 0 && box > fold && box < end);
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
function focusDoc() {
  const doc = fakeDoc();
  doc.activeElement = null;
  const make = doc.createElement;
  doc.createElement = (t) => {
    const node = make(t);
    node.focus = () => { doc.activeElement = node; };
    return node;
  };
  return doc;
}

function calcLi(doc) {
  return doc.ids["checks-list"].children.find((li) =>
    li.children.some((c) => c.children && c.children.some((n) => n.textContent === "Calc component")));
}

function calcButtonNode(doc) {
  const li = calcLi(doc);
  return li ? li.children.find((c) => c.tagName === "button") || null : null;
}

function calcButton(doc) { // the button when it shows, else null
  const b = calcButtonNode(doc);
  return b && !b.hidden ? b : null;
}

function calcStatus(doc) {
  const li = calcLi(doc);
  return li ? li.children.find((c) => c.attrs && c.attrs.role === "status") || null : null;
}

function calcSaid(doc) {
  const p = calcStatus(doc);
  return p ? p.textContent : "";
}

function withCalc(status, summary) {
  const diag = Object.assign({}, DIAG, { checks: DIAG.checks.map((c) =>
    (c.id === "calc" ? Object.assign({}, c, { status: status }) : c)) });
  if (summary) { diag.summary = summary; }
  return { diag: diag };
}

function resetCalc() {
  ck._state.client = undefined;
  ck._state.calc = "";
  ck._state.calcRow = null;
  ck._state.calcNodes = null;
}

test("calc button: only in the client, only while the calc row is off or needs a fix", (t) => {
  resetCalc();
  t.after(resetCalc);
  // a plain browser (no window.alClient): never a button, no region
  let doc = focusDoc();
  ck.paint(doc, withCalc("off"));
  assert.equal(calcButtonNode(doc), null);
  assert.equal(calcStatus(doc), null);
  // a client without the action: none either
  ck._state.client = { restartOverlay() {} };
  doc = focusDoc();
  ck.paint(doc, withCalc("off"));
  assert.equal(calcButtonNode(doc), null);
  ck._state.client = { setupCalc: () => new Promise(() => {}) };
  for (const [status, shown] of [["off", true], ["fail", true], ["pass", false],
                                 ["unknown", false], ["note", false]]) {
    doc = focusDoc();
    ck.paint(doc, withCalc(status));
    const b = calcButton(doc);
    assert.equal(!!b, shown, status);
    if (b) {
      assert.equal(b.textContent, ck.CALC_BUTTON);
      assert.equal(b.textContent, "Set up the calc");
      assert.equal(b.type, "button");
      assert.equal(b.getAttribute("aria-disabled"), "false");
    }
  }
  // no other row ever gets it
  doc = focusDoc();
  ck.paint(doc, withCalc("off"));
  const withButton = doc.ids["checks-list"].children.filter((li) =>
    li.children.some((c) => c.tagName === "button"));
  assert.equal(withButton.length, 1);
  // the model on its own
  assert.deepEqual(ck.calcModel({ id: "calc", word: "off" }, false, ""), { button: false, said: "" });
  assert.deepEqual(ck.calcModel({ id: "log", word: "off" }, true, ""), { button: false, said: "" });
});

test("calc row: one persistent, empty polite live region, kept across rebuilds", (t) => {
  resetCalc();
  t.after(resetCalc);
  ck._state.client = { setupCalc: () => new Promise(() => {}) };
  const doc = focusDoc();
  ck.paint(doc, withCalc("off"));
  const region = calcStatus(doc);
  assert.ok(region);
  assert.equal(region.id, "checks-calc-status");
  assert.equal(region.attrs["aria-live"], "polite");
  assert.equal(region.attrs.tabindex, "-1");
  assert.equal(region.textContent, "", "empty until a click");
  const button = calcButtonNode(doc);
  // a new snapshot rebuilds the list: the same two nodes come back
  ck.paint(doc, withCalc("off", "new words"));
  assert.equal(calcStatus(doc), region);
  assert.equal(calcButtonNode(doc), button);
});

test("calc button: a click runs the client's one action, then pending, then ok or failed", async (t) => {
  resetCalc();
  t.after(resetCalc);
  let finish = null;
  const asked = [];
  ck._state.client = { setupCalc: (...a) => { asked.push(a); return new Promise((r) => { finish = r; }); } };
  const doc = focusDoc();
  ck.paint(doc, withCalc("off"));
  const region = calcStatus(doc);
  const button = calcButton(doc);
  button.focus();
  button.listeners.click();
  assert.deepEqual(asked, [[]], "the action takes no argument");
  // pending: the region speaks, the focused button stays in place, aria-disabled
  assert.equal(calcStatus(doc), region);
  assert.equal(region.textContent, ck.CALC_PENDING);
  assert.equal(calcButton(doc), button);
  assert.equal(button.getAttribute("aria-disabled"), "true");
  assert.equal(doc.activeElement, button, "focus stays on the button");
  button.listeners.click(); // a second click while it runs does nothing
  assert.equal(asked.length, 1);
  ck.paint(doc, withCalc("off", "a new snapshot"));
  assert.equal(region.textContent, ck.CALC_PENDING);
  assert.equal(calcButton(doc), button);
  assert.equal(doc.activeElement, button, "a rebuild keeps the focus on the button");
  finish({ ok: true });
  await new Promise((r) => setImmediate(r));
  assert.equal(region.textContent, ck.CALC_OK);
  assert.equal(calcButton(doc), null, "no button after a good setup");
  assert.equal(doc.activeElement, region, "focus moves to the status line, never to body");
  // the core's row moves on: the line clears and the row speaks for itself
  ck.paint(doc, withCalc("pass"));
  assert.equal(calcSaid(doc), "");
  assert.equal(calcButton(doc), null);

  // a failed setup says so and offers the button again, focus kept on it
  ck.paint(doc, withCalc("fail"));
  calcButton(doc).focus();
  calcButton(doc).listeners.click();
  assert.equal(calcSaid(doc), ck.CALC_PENDING);
  finish({ ok: false });
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  assert.equal(calcButton(doc), button);
  assert.equal(button.getAttribute("aria-disabled"), "false");
  assert.equal(doc.activeElement, button);
  // a refused or throwing action reads as failed too
  ck._state.client = { setupCalc: () => Promise.reject(new Error("x")) };
  calcButton(doc).listeners.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  ck._state.client = { setupCalc: () => { throw new Error("y"); } };
  calcButton(doc).listeners.click();
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  // a stranger answer (null: not the companion) is a failure, never ok
  ck._state.client = { setupCalc: () => Promise.resolve(null) };
  calcButton(doc).listeners.click();
  await new Promise((r) => setImmediate(r));
  assert.equal(calcSaid(doc), ck.CALC_FAILED);
  // the copy says play goes on and where to look on a failure
  assert.match(ck.CALC_PENDING, /You can keep playing\.$/);
  assert.match(ck.CALC_FAILED, /calc_setup\.log in the Logs folder\.$/);
  assert.equal(ck.CALC_OK, "Calc set up. This row will change to ok soon.");
});

/* RUN-QUIET-FEED (F-093): age rows carry an absolute "at" and the AGO mark;
   the page writes the age in, stepped at 5 minutes. */
test("checks: ages step at 5 minutes", () => {
  assert.equal(ck.AGE_STEP_S, 300);
  assert.equal(ck.ageText(0), "just now");
  assert.equal(ck.ageText(89), "just now");
  assert.equal(ck.ageText(90), "under 5 min ago");
  assert.equal(ck.ageText(299), "under 5 min ago");
  assert.equal(ck.ageText(300), "5 min ago");
  assert.equal(ck.ageText(599), "5 min ago");
  assert.equal(ck.ageText(600), "10 min ago");
  assert.equal(ck.ageText(89 * 60), "85 min ago");
  assert.equal(ck.ageText(3 * 3600 + 5), "3 h ago");
  assert.equal(ck.ageText(3 * 86400), "3 days ago");
  assert.equal(ck.ageText(-5), "just now");
  assert.equal(ck.ageText(NaN), "just now");
  const T = 1795200000;
  const d = { summary: "All checks pass.", failed: 0, checks: [
    { id: "last_line", label: "Last log line", status: "pass", detail: ck.AGO + ".",
      fix: null, at: T - 30 },
    { id: "prices", label: "Price book", status: "pass", detail: "Updated " + ck.AGO + ".",
      fix: null, at: T - 600 },
    { id: "port", label: "Dashboard address", status: "pass", detail: "127.0.0.1:8960",
      fix: null }] };
  const at = (now) => ck.model(d, now).rows.map((r) => r.detail);
  assert.deepEqual(at(T), ["Just now.", "Updated 10 min ago.", "127.0.0.1:8960"]);
  // the same 5-minute step: the same model, so the list is not rebuilt
  assert.deepEqual(ck.model(d, T + 60), ck.model(d, T + 239));
  assert.deepEqual(at(T + 300), ["5 min ago.", "Updated 15 min ago.", "127.0.0.1:8960"]);
  // paint takes the snapshot's own clock and rebuilds only on a new step
  const doc = fakeDoc();
  ck.paint(doc, { diag: d, now: T + 60 });
  const key = doc.ids.checksbox.getAttribute("data-key");
  ck.paint(doc, { diag: d, now: T + 200 });
  assert.equal(doc.ids.checksbox.getAttribute("data-key"), key);
  ck.paint(doc, { diag: d, now: T + 300 });
  assert.notEqual(doc.ids.checksbox.getAttribute("data-key"), key);
  const detail = doc.ids["checks-list"].children[1].children[1].textContent;
  assert.equal(detail, "Updated 15 min ago.");
  // no "at": the AGO mark is never written in (shown as sent)
  assert.equal(ck.model({ checks: [{ id: "x", status: "note", detail: "a " + ck.AGO }] }, T)
    .rows[0].detail, "a " + ck.AGO);
});

/* RUN-REPORT-FIELDS (finding F-109): the preview's one checkbox, the
   player's explicit second choice that adds AshLight's own log lines. */
test("checks: the second choice is off by default", async () => {
  const doc = fakeDoc();
  const calls = [];
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  const api = (method, path) => {
    calls.push([method, path]);
    return Promise.resolve({ report: path.indexOf("tails=1") >= 0 ? REPORT + "Log tails: x\n" : REPORT });
  };
  ck.wire(doc, () => ({ diag: DIAG }), nav, null, api);
  const box = ck._report.tailsBox;
  assert.ok(box, "the checkbox is made at wire time");
  assert.equal(box.type, "checkbox");
  assert.equal(box.id, "checks-tails");
  assert.equal(box.checked, false, "off by default");
  // it sits inside the preview box, with its own label text
  const holder = doc.ids["checks-preview-box"].children[0];
  assert.ok(holder && holder.children[0].children[0] === box);
  assert.equal(holder.children[0].children[1].textContent, " " + ck.TAILS_LABEL);
  // the fold's opening click asks for the report without the log lines
  doc.ids["checks-summary"].listeners.click();
  assert.deepEqual(calls, [["GET", ck.REPORT_PATH]]);
  await tickle();
  doc.ids["checks-copy"].listeners.click();
  assert.deepEqual(wrote, [REPORT]);
  // ticking it makes the preview again with the log lines; nothing is copied
  box.checked = true;
  box.listeners.change();
  assert.deepEqual(calls[1], ["GET", ck.REPORT_PATH + ck.TAILS_QUERY]);
  await tickle();
  await tickle();
  assert.equal(doc.ids["checks-preview"].value, REPORT + "Log tails: x\n");
  assert.equal(doc.ids["checks-said"].textContent, ck.READY_TAILS);
  assert.equal(wrote.length, 1, "a change never writes the clipboard");
  doc.ids["checks-copy"].listeners.click();
  assert.deepEqual(wrote, [REPORT, REPORT + "Log tails: x\n"]);
  // a preview made with the other choice is made again before any copy
  box.checked = false;
  doc.ids["checks-copy"].listeners.click();
  assert.deepEqual(calls[2], ["GET", ck.REPORT_PATH]);
  assert.equal(wrote.length, 2);
  await tickle();
  await tickle();
  assert.equal(doc.ids["checks-preview"].value, REPORT);
  // a new page starts unticked again (never stored)
  const again = fakeDoc();
  ck.wire(again, () => ({ diag: DIAG }), nav, null, api);
  assert.equal(ck._report.tailsBox.checked, false);
});
