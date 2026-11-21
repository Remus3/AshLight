/* RUN-VERDICTS-UI (finding F-062, OPEN-27; decision 0040 amendment
   2026-11-18): the 'Tried in game' card in web/verdicts.js. The model
   lists the open player checks, one click posts a verdict, and the file
   has no timer, no clipboard and sets every text with textContent. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const V = web.load("verdicts.js");
const SRC = web.source("verdicts.js");
// the code without its comments (the header comment names what it never does)
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
const HTML = web.source("index.html");

const CHECKS = [
  ["TC-BUILDFILE-LIVE", "An AshLight-made .build file loaded in game"],
  ["LIVE-SEARCHSTR", "A copied search string pasted into a game search box"],
  ["LIVE-FILTER", "The downloaded AshLight filter snippet imported in game"],
  ["LIVE-FILTER-MERGE", "A merged filter (your filter plus AshLight's blocks) loaded in game"],
  ["OVL-FPS", "One map played with the overlay shown, FPS as usual"]];

/* The GET /api/verdicts document (server/al/verdicts.py view()). */
function doc(verdicts) {
  return {
    schema: 1, results: ["worked", "refused"], max_note: 200, rows: [],
    checks: CHECKS.map(([id, label]) => ({ id, label, verdict: (verdicts || {})[id] || null }))
  };
}

function el(tag) {
  const node = {
    tagName: tag.toUpperCase(), children: [], attrs: {}, hidden: false, disabled: false,
    className: "", listeners: {}, value: "", id: "",
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
  const mount = el("div");
  mount.hidden = true;
  const d = {
    mount, activeElement: null,
    getElementById: (id) => (id === "verdicts" ? mount : null),
    createElement: (t) => {
      const n = el(t);
      n.focus = () => { d.activeElement = n; };
      return n;
    },
    createTextNode: (t) => ({ textContent: t })
  };
  return d;
}

function find(node, pred, out) {
  out = out || [];
  if (pred(node)) { out.push(node); }
  (node.children || []).forEach((c) => find(c, pred, out));
  return out;
}

const byId = (d, id) => find(d.mount, (n) => n.id === id)[0] || null;
const buttons = (d) => find(d.mount, (n) => n.tagName === "BUTTON");
const rowsOf = (d) => byId(d, "verdicts-list").children;

/* app.js api() stand-in: records every call; GET answers `state`, POST
   adds the verdict and answers the core's {verdict, verdicts}. */
function fakeApi(state, opts) {
  const calls = [];
  const fn = (method, path, body) => {
    calls.push([method, path, body]);
    if (opts && opts.fail && method === "POST") { return Promise.reject(new Error("HTTP 400")); }
    if (method === "GET") { return Promise.resolve(doc(state)); }
    state[body.check] = { check: body.check, result: body.result, note: body.note || "", at: 1 };
    return Promise.resolve({ verdict: state[body.check], verdicts: doc(state) });
  };
  fn.calls = calls;
  return fn;
}

const tickle = () => new Promise((r) => setImmediate(r));

test("verdicts: model lists the open checks, one click posts a verdict", async () => {
  // the model on its own: untried and refused are open, worked is closed
  const m = V.model(doc({}));
  assert.equal(m.rows.length, 5);
  assert.equal(m.open, 5);
  assert.deepEqual(m.rows.map((r) => r.word), Array(5).fill("not tried yet"));
  const m2 = V.model(doc({
    "TC-BUILDFILE-LIVE": { result: "worked", note: "" },
    "LIVE-FILTER": { result: "refused", note: "import said bad line" } }));
  assert.equal(m2.open, 4);
  assert.deepEqual(m2.rows.map((r) => [r.id, r.open, r.word]).slice(0, 3), [
    ["TC-BUILDFILE-LIVE", false, "worked"], ["LIVE-SEARCHSTR", true, "not tried yet"],
    ["LIVE-FILTER", true, "refused"]]);
  assert.equal(m2.rows[2].note, "import said bad line");
  assert.deepEqual(V.model(null), { rows: [], open: 0, allDone: false, maxNote: 200 });

  // the card: one GET at wire, a heading in the markup, two named buttons per open row
  const d = fakeDoc();
  const api = fakeApi({ "OVL-FPS": { check: "OVL-FPS", result: "worked", note: "", at: 1 } });
  await V.wire(d, api);
  assert.deepEqual(api.calls, [["GET", "/api/verdicts", undefined]]);
  assert.equal(d.mount.hidden, false);
  assert.equal(rowsOf(d).length, 5);
  assert.equal(buttons(d).length, 8, "four open rows, Worked and Refused each");
  for (const b of buttons(d)) {
    assert.ok(b.textContent === V.WORKED || b.textContent === V.REFUSED);
    assert.equal(b.type, "button");
    const label = byId(d, b.getAttribute("aria-describedby"));
    assert.ok(label && label.textContent, "each button points at its check's name");
  }
  const closed = rowsOf(d)[4];
  assert.equal(find(closed, (n) => n.tagName === "BUTTON").length, 0, "a worked check is closed");

  // one click: Worked on the first check posts it, with that row's note
  byId(d, "verdicts-note-TC-BUILDFILE-LIVE").value = "  loaded fine  ";
  const first = buttons(d).find((b) => b.getAttribute("data-check") === "TC-BUILDFILE-LIVE" &&
    b.getAttribute("data-result") === "worked");
  first.focus();
  first.listeners.click();
  assert.deepEqual(api.calls[1], ["POST", "/api/verdicts",
    { check: "TC-BUILDFILE-LIVE", result: "worked", note: "loaded fine" }]);
  assert.ok(buttons(d).every((b) => b.getAttribute("aria-disabled") === "true" && !b.disabled),
    "one post at a time");
  first.listeners.click(); // a second click while it posts does nothing
  assert.equal(api.calls.length, 2);
  await tickle();
  assert.equal(api.calls.length, 2, "no read after the post: the answer repaints");
  assert.equal(buttons(d).length, 6);
  assert.equal(byId(d, "verdicts-note-TC-BUILDFILE-LIVE"), null, "a closed check has no note field");
  assert.equal(byId(d, "verdicts-said").textContent, V.SAVED.worked);
  assert.equal(d.activeElement, byId(d, "verdicts-said"), "focus never drops to the body");

  // Refused without a note posts no note; the row stays open with its word
  buttons(d).find((b) => b.getAttribute("data-check") === "LIVE-FILTER" &&
    b.getAttribute("data-result") === "refused").listeners.click();
  assert.deepEqual(api.calls[2][2], { check: "LIVE-FILTER", result: "refused" });
  await tickle();
  const lf = rowsOf(d).find((li) => li.getAttribute("data-check") === "LIVE-FILTER");
  assert.ok(find(lf, (n) => n.textContent === "refused").length);
  assert.equal(find(lf, (n) => n.tagName === "BUTTON").length, 2);

  // a note the core would refuse is said, never cut and never sent
  const noteOf = (b) => byId(d, "verdicts-note-" + b.getAttribute("data-check"));
  noteOf(buttons(d)[0]).value = "x".repeat(201);
  buttons(d)[0].listeners.click();
  assert.equal(api.calls.length, 3);
  assert.equal(byId(d, "verdicts-said").textContent, V.NOTE_BAD);
  noteOf(buttons(d)[0]).value = "caf\u00e9";
  buttons(d)[0].listeners.click();
  assert.equal(api.calls.length, 3);
  assert.equal(V.cleanNote(" ok ", 200), "ok");
  assert.equal(V.cleanNote("tab\there", 200), null);

  // all worked: the card says so and has no buttons
  for (const [id] of CHECKS) {
    const b = buttons(d).find((x) => x.getAttribute("data-check") === id &&
      x.getAttribute("data-result") === "worked");
    if (b) { byId(d, "verdicts-note-" + id).value = ""; b.listeners.click(); await tickle(); }
  }
  assert.equal(buttons(d).length, 0);
  assert.equal(rowsOf(d).length, 5, "closed checks stay listed");
  assert.ok(V.model(doc(Object.fromEntries(CHECKS.map(([id]) =>
    [id, { result: "worked" }])))).allDone);
});

test("verdicts: a failed post or read says so", async () => {
  const d = fakeDoc();
  const api = fakeApi({}, { fail: true });
  await V.wire(d, api);
  buttons(d)[0].listeners.click();
  await tickle();
  assert.equal(byId(d, "verdicts-said").textContent, V.SAVE_FAILED);
  assert.ok(buttons(d).every((b) => b.getAttribute("aria-disabled") === "false"),
    "the buttons come back");
  const d2 = fakeDoc();
  await V.wire(d2, () => Promise.reject(new Error("HTTP 500")));
  assert.equal(d2.mount.hidden, false);
  assert.equal(byId(d2, "verdicts-said").textContent, V.LOAD_FAILED);
  // no mount, no api: nothing at all
  assert.equal(await V.wire({ getElementById: () => null }, fakeApi({})), false);
});

/* VERDICTS-UI-A11Y: the RUN-VERDICTS-UI design review, V-1 to V-3. */
const btn = (d, id, result) => buttons(d).find((b) => b.getAttribute("data-check") === id &&
  b.getAttribute("data-result") === result);

test("verdicts V-1: a Refused click is read out: focus moves to the said line", async () => {
  const d = fakeDoc();
  await V.wire(d, fakeApi({}));
  const refused = btn(d, "LIVE-FILTER", "refused");
  refused.focus();
  refused.listeners.click();
  await tickle();
  // the row stays open (its buttons are rebuilt), yet the focus moves on
  assert.ok(btn(d, "LIVE-FILTER", "refused"), "a refused check stays open");
  assert.equal(byId(d, "verdicts-said").textContent, V.SAVED.refused);
  assert.equal(d.activeElement, byId(d, "verdicts-said"));
  assert.equal(byId(d, "verdicts-said").getAttribute("tabindex"), "-1");
  // a failed post is read out the same way
  const d2 = fakeDoc();
  await V.wire(d2, fakeApi({}, { fail: true }));
  const w = btn(d2, "OVL-FPS", "worked");
  w.focus();
  w.listeners.click();
  await tickle();
  assert.equal(byId(d2, "verdicts-said").textContent, V.SAVE_FAILED);
  assert.equal(d2.activeElement, byId(d2, "verdicts-said"));
  // focus the player moved elsewhere during the post is left alone
  const d3 = fakeDoc();
  await V.wire(d3, fakeApi({}));
  btn(d3, "OVL-FPS", "refused").focus();
  btn(d3, "OVL-FPS", "refused").listeners.click();
  const elsewhere = byId(d3, "verdicts-note-LIVE-FILTER");
  elsewhere.focus();
  await tickle();
  assert.equal(d3.activeElement, elsewhere);
});

test("verdicts V-2: the busy state keeps the focus (aria-disabled, never disabled)", async () => {
  const d = fakeDoc();
  let answer = null;
  const api = (method) => (method === "GET" ? Promise.resolve(doc({})) :
    new Promise((r) => { answer = r; }));
  await V.wire(d, api);
  const b = btn(d, "LIVE-SEARCHSTR", "worked");
  b.focus();
  b.listeners.click();
  for (const x of buttons(d)) {
    assert.equal(x.disabled, false, "a disabled button would drop the focus");
    assert.equal(x.getAttribute("aria-disabled"), "true");
  }
  assert.equal(d.activeElement, b, "focus stays on the pressed button while it posts");
  answer({ verdicts: doc({ "LIVE-SEARCHSTR": { result: "worked", note: "" } }) });
  await tickle();
  assert.ok(buttons(d).every((x) => x.getAttribute("aria-disabled") === "false"));
  assert.equal(d.activeElement, byId(d, "verdicts-said"));
  // the source never sets .disabled on a verdict button
  assert.ok(!/\.disabled\s*=/.test(CODE));
});

test("verdicts V-3: each open check has its own note field, sent only with that check", async () => {
  const d = fakeDoc();
  const api = fakeApi({});
  await V.wire(d, api);
  const notes = find(d.mount, (n) => n.tagName === "TEXTAREA");
  assert.equal(notes.length, 5, "one note field per open check");
  for (const n of notes) {
    const id = n.id.replace("verdicts-note-", "");
    const label = find(d.mount, (x) => x.tagName === "LABEL" && x.getAttribute("for") === n.id);
    assert.equal(label.length, 1);
    assert.equal(label[0].textContent, V.NOTE_LABEL);
    assert.equal(label[0].textContent, "Note for this check, optional");
    const li = rowsOf(d).find((r) => r.getAttribute("data-check") === id);
    assert.ok(find(li, (x) => x === n).length, "the field sits in its own check's row");
    assert.equal(n.getAttribute("maxlength"), "200");
  }
  // a note typed under one check never goes with another
  byId(d, "verdicts-note-LIVE-FILTER").value = "bad line 12";
  byId(d, "verdicts-note-OVL-FPS").value = "steady";
  btn(d, "TC-BUILDFILE-LIVE", "worked").listeners.click();
  assert.deepEqual(api.calls[1][2], { check: "TC-BUILDFILE-LIVE", result: "worked" });
  await tickle();
  // the rebuild keeps what was typed in the rows still open
  assert.equal(byId(d, "verdicts-note-LIVE-FILTER").value, "bad line 12");
  assert.equal(byId(d, "verdicts-note-OVL-FPS").value, "steady");
  btn(d, "LIVE-FILTER", "refused").listeners.click();
  assert.deepEqual(api.calls[2][2], { check: "LIVE-FILTER", result: "refused", note: "bad line 12" });
  await tickle();
  assert.equal(byId(d, "verdicts-note-LIVE-FILTER").value, "", "a sent note is cleared");
  assert.equal(byId(d, "verdicts-note-OVL-FPS").value, "steady");
  // a refused note focuses its own field, which points at the said line
  const bad = byId(d, "verdicts-note-OVL-FPS");
  bad.value = "tab\there";
  btn(d, "OVL-FPS", "worked").listeners.click();
  assert.equal(api.calls.length, 3);
  assert.equal(d.activeElement, bad);
  assert.equal(bad.getAttribute("aria-invalid"), "true");
  assert.equal(bad.getAttribute("aria-describedby"), "verdicts-said");
  assert.ok(!/goes with your next click/.test(SRC));
});

test("verdicts: no timer, no clipboard, text set with textContent", () => {
  assert.ok(!/setTimeout|setInterval|requestAnimationFrame/.test(CODE), "no timer");
  assert.ok(!/clipboard|execCommand/.test(CODE), "no clipboard");
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write/.test(CODE));
  assert.ok(/\.textContent = /.test(CODE));
  assert.ok(!/\bdialog\b|showModal|alert\(|confirm\(|prompt\(/.test(CODE), "no modal");
  assert.ok(!/localStorage|sessionStorage/.test(CODE));
  // the only requests are the card's own route
  const paths = CODE.match(/"\/api\/[a-z-]+"/g) || [];
  assert.deepEqual([...new Set(paths)], ['"/api/verdicts"']);
  assert.ok(!/fetch\(|XMLHttpRequest|EventSource/.test(CODE));
  // ASCII only
  assert.ok(/^[\x09\x0a\x20-\x7e]*$/.test(SRC));
});

test("verdicts: the page holds one mount with a heading, after the checks list", () => {
  const list = HTML.indexOf('id="checks-list"');
  const mount = HTML.indexOf('id="verdicts"');
  assert.ok(list > 0 && mount > list, "the mount follows #checks-list");
  assert.ok(mount < HTML.indexOf('id="checks-copy"'), "inside the Checks group");
  assert.match(HTML, /<div id="verdicts" class="tool verdicts" role="group" aria-labelledby="verdicts-title" hidden>\s*<h4 id="verdicts-title" class="sub-h">Tried in game<\/h4>/);
  assert.equal(HTML.split('src="/web/verdicts.js"').length - 1, 1);
  assert.ok(HTML.indexOf("/web/verdicts.js") < HTML.indexOf("/web/app.js"));
  const app = web.source("app.js");
  assert.equal(app.split("ALVerdicts.wire(document, api)").length - 1, 1);
});
