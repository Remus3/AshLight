"use strict";
/* REL-UPDATE-NOTICE-UI (findings F-055, F-077, DEP-16; decisions 0013 and
   0065, ruling Q-21): web/updates.js words the snapshot's update block in
   Settings > About and data, and the web-data box acknowledges the opt-in
   wording that names the update check. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const web = require("./_web.js");

const U = web.load("updates.js");
const TC = web.load("tc.js");
const R = web.load("registry.js");
const PR = web.load("prices.js");
const HTML = web.source("index.html", "ascii");
const HOSTS = TC.LINK_HOSTS;
const URL_OK = "https://" + "github.com" + "/someone/AshLight/releases";

function block(extra) {
  return Object.assign({ installed: "0.4.0", latest: "0.4.0", newer: false, prerelease: false,
    notes: [], releases_url: URL_OK, checked_at: 1795400000, next_at: 1795486400,
    error: null, ack_needed: false, staged: null, click_only: false }, extra || {});
}

/* a tiny DOM: elements by id, created children, attributes, listeners */
function el(tag, id) {
  const n = { tag, id, hidden: false, textContent: "", kids: [], attrs: {}, on: {} };
  n.setAttribute = (k, v) => { n.attrs[k] = String(v); };
  n.getAttribute = (k) => (k in n.attrs ? n.attrs[k] : null);
  n.removeAttribute = (k) => { delete n.attrs[k]; };
  n.appendChild = (c) => { n.kids.push(c); return c; };
  n.addEventListener = (ev, f) => { (n.on[ev] = n.on[ev] || []).push(f); };
  n.fire = (ev) => (n.on[ev] || []).forEach((f) => f({ target: n, preventDefault() {} }));
  Object.defineProperty(n, "textContent", {
    get() { return n._text || ""; },
    set(v) { n._text = String(v); if (v === "") { n.kids = []; } }
  });
  return n;
}

function fakeDoc(ids) {
  const nodes = {};
  ids.forEach((id) => { nodes[id] = el("x", id); });
  return { getElementById: (id) => nodes[id] || null, createElement: (t) => el(t) };
}

const BOX_IDS = ["update-box", "update-version", "update-data", "update-line", "update-ack-row",
  "update-ack", "update-link", "update-link-row", "update-said", "update-notes-box", "update-notes"];

function fakeTabs() {
  const marks = [];
  return { marks, mark(doc, id, word) { marks.push([id, word]); } };
}

function snapOf(update, extraRows, failed) {
  return { update, diag: { failed: failed || 0, checks: [
    { id: "web_data", status: "pass" }, { id: "snapshot", status: "pass", at: 1795300000 }]
    .concat(extraRows || []) } };
}

const tick = () => new Promise((r) => setImmediate(r));

test("no update: the version, the up to date line, no mark, no ack", () => {
  const m = U.model(block(), true, HOSTS);
  assert.equal(m.show, true);
  assert.equal(m.version, "AshLight 0.4.0");
  assert.equal(m.state, "current");
  assert.equal(m.line, U.TEXT.current);
  assert.equal(m.mark, "");
  assert.equal(m.ack, false);
  assert.deepEqual(m.link, { href: URL_OK, text: U.LINK_TEXT });
  // never checked yet
  assert.equal(U.model(block({ checked_at: null }), true, HOSTS).line, U.TEXT.first);
  // no block (an older core): nothing shows
  assert.equal(U.model(null, true, HOSTS).show, false);
});

test("a newer version: one line and the Settings tab mark, never a window", () => {
  const m = U.model(block({ latest: "0.5.0", newer: true }), true, HOSTS);
  assert.equal(m.state, "newer");
  assert.equal(m.line, "AshLight 0.5.0 is out. It installs by itself at a later start.");
  assert.equal(m.mark, "update");
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, staged: "0.5.0" }), true, HOSTS).line,
    "AshLight 0.5.0 is downloaded. It installs at a later start.");
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, click_only: true }), true, HOSTS).line,
    "AshLight 0.5.0 is out. See what changed on GitHub.");
  // paint: the mark goes to the Settings tab; nothing opens
  const doc = fakeDoc(BOX_IDS);
  const tabs = fakeTabs();
  // (no toast or window anywhere: tests/test_glance_rules.py scans the tree)
  U.paint(doc, snapOf(block({ latest: "0.5.0", newer: true })), { hosts: HOSTS, tabs });
  assert.deepEqual(tabs.marks, [["settings", "update"]]);
  assert.equal(doc.getElementById("update-box").hidden, false);
  assert.equal(doc.getElementById("update-line").textContent,
    "AshLight 0.5.0 is out. It installs by itself at a later start.");
  // a failing check keeps web/checks.js's "fix": no mark from here
  const t2 = fakeTabs();
  U.paint(fakeDoc(BOX_IDS), snapOf(block({ latest: "0.5.0", newer: true }), [], 1), { hosts: HOSTS, tabs: t2 });
  assert.deepEqual(t2.marks, []);
  // back to current: the mark is cleared
  const t3 = fakeTabs();
  U.paint(doc, snapOf(block()), { hosts: HOSTS, tabs: t3 });
  assert.deepEqual(t3.marks, [["settings", ""]]);
});

test("ack needed: the line and one OK button; the click posts the wording version once", async () => {
  const m = U.model(block({ ack_needed: true, checked_at: null }), true, HOSTS);
  assert.equal(m.state, "ack");
  assert.equal(m.ack, true);
  assert.equal(m.line, U.TEXT.ack);
  assert.equal(m.mark, "");
  const doc = fakeDoc(BOX_IDS);
  U.paint(doc, snapOf(block({ ack_needed: true })), { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-ack-row").hidden, false);
  const calls = [];
  const saved = [];
  const api = (method, path, body) => { calls.push([method, path, body]); return Promise.resolve({ acked: true }); };
  U.wire(doc, api, () => ({ wording_version: 1 }), (d) => saved.push(d));
  const btn = doc.getElementById("update-ack");
  btn.fire("click");
  btn.fire("click"); // a second click while saving adds nothing
  await tick();
  assert.deepEqual(calls, [["POST", "/api/web-data", { ack: 1 }]]);
  assert.deepEqual(saved, [{ acked: true }]);
  assert.equal(doc.getElementById("update-said").textContent, U.TEXT.acked);
  // no wording version known: nothing is sent
  const d2 = fakeDoc(BOX_IDS);
  const c2 = [];
  U.wire(d2, (m2, p, b) => { c2.push(b); return Promise.resolve({}); }, () => null);
  d2.getElementById("update-ack").fire("click");
  await tick();
  assert.deepEqual(c2, []);
  assert.equal(d2.getElementById("update-said").textContent, U.TEXT.notSaved);
  // the button label in the page is the module's
  assert.match(HTML, new RegExp("<button id=\"update-ack\"[^>]*>" + U.ACK_LABEL + "</button>"));
});

test("web data off: the version plus a releases link; none while the address is empty", () => {
  const m = U.model(block(), false, HOSTS);
  assert.equal(m.state, "off");
  assert.equal(m.line, U.TEXT.off);
  assert.equal(m.version, "AshLight 0.4.0");
  assert.deepEqual(m.link, { href: URL_OK, text: U.LINK_TEXT });
  const none = U.model(block({ releases_url: null }), false, HOSTS);
  assert.equal(none.link, null);
  assert.equal(none.line, U.TEXT.none);
  assert.equal(none.version, "AshLight 0.4.0");
  // the switch is read from the "web_data" Checks row
  assert.equal(U.webDataOn(snapOf(block(), [])), true);
  assert.equal(U.webDataOn({ diag: { checks: [{ id: "web_data", status: "off" }] } }), false);
  assert.equal(U.webDataOn({}), null);
  const doc = fakeDoc(BOX_IDS);
  U.paint(doc, { update: block(), diag: { failed: 0, checks: [{ id: "web_data", status: "off" }] } },
    { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-line").textContent, U.TEXT.off);
  assert.equal(doc.getElementById("update-link-row").hidden, false);
  assert.equal(doc.getElementById("update-link").getAttribute("href"), URL_OK);
  assert.equal(doc.getElementById("update-data").hidden, true); // no snapshot row
});

test("the link is a plain https link on a listed host, opened in the player's own browser", () => {
  assert.ok(HOSTS.includes("github.com"));
  for (const bad of ["http://github.com/a/b/releases", "javascript:alert(1)",
    "https://example.com/a/b/releases", "https://github.com", "", null,
    "https://github.com/a/b/releases?x=\"y\""]) {
    assert.equal(U.releasesLink(bad, HOSTS), null, String(bad));
  }
  assert.equal(U.releasesLink(URL_OK, []), null);
  const a = /<a id="update-link"([^>]*)>([^<]*)<\/a>/.exec(HTML);
  assert.ok(a, "the anchor in index.html");
  assert.match(a[1], /target="_blank"/);
  assert.match(a[1], /rel="noopener noreferrer"/);
  assert.doesNotMatch(a[1], /href=/); // the address comes only from the core
  assert.equal(a[2], U.LINK_TEXT);
  // no host literal of its own (config/link_hosts.json, link_hosts.test.js)
  assert.doesNotMatch(web.source("updates.js"), /https:\/\/[a-z]/i);
});

test("ticking the web-data box sends the wording version", async () => {
  assert.deepEqual(U.ackBody(true, { wording_version: 1 }), { enabled: true, ack: 1 });
  assert.deepEqual(U.ackBody(false, { wording_version: 1 }), { enabled: false });
  assert.deepEqual(U.ackBody(true, {}), { enabled: true });
  assert.deepEqual(U.ackBody(true, { wording_version: "1" }), { enabled: true });
  // the panel itself: GET gives the wording version, the player's tick posts it
  const ids = ["webdata-sentence", "webdata-form", "webdata-on", "webdata-status",
    "webdata-contact-row", "webdata-contact", "webdata-league", "webdata-league-row",
    "webdata-league-note"];
  const doc = fakeDoc(ids);
  const calls = [];
  const reads = [];
  const answers = { "GET /api/web-data": { web_data: false, contact_set: true, wording_version: 1 },
    "POST /api/web-data": { web_data: true, contact_set: true, wording_version: 1, acked: true } };
  const host = {
    $: (id) => doc.getElementById(id),
    api: (method, path, body) => { calls.push([method, path, body]); return Promise.resolve(answers[method + " " + path]); },
    getSnap: () => null, getRatesDoc: () => null, renderRates() {}, renderPrice() {},
    loadRates() {}, webLink: {}, onConnect: (f) => reads.push(f)
  };
  const reg = R.create({ warn: (t) => { throw new Error(t); } });
  reg.host = host;
  const sandbox = { ALApp: reg, ALTc: TC, ALPrices: PR, console };
  sandbox.window = sandbox;
  vm.runInNewContext(web.source("webdata.js"), sandbox, { filename: "webdata.js" });
  reg.start();
  assert.equal(doc.getElementById("webdata-sentence").textContent, TC.WEB_DATA_OPT_IN);
  reads.forEach((f) => f());
  await tick();
  doc.getElementById("webdata-on").checked = true;
  doc.getElementById("webdata-form").fire("change");
  assert.deepEqual(JSON.parse(JSON.stringify(calls[1])),
    ["POST", "/api/web-data", { enabled: true, ack: 1 }]);
  await tick();
  // ticking it off sends no acknowledgement
  doc.getElementById("webdata-on").checked = false;
  doc.getElementById("webdata-form").fire("change");
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2])), ["POST", "/api/web-data", { enabled: false }]);
});

test("the opt-in sentence names the daily update check and the automatic apply", () => {
  const s = TC.WEB_DATA_OPT_IN;
  assert.match(s, /checks GitHub once a day for a new AshLight/);
  assert.match(s, /downloads by itself and installs at a later start/);
  assert.match(s, /three things only/);
});

test("game data from <date>, the newest 3 versions, and no string over the design caps", () => {
  const snap = snapOf(block());
  const d = U.day(1795300000);
  assert.match(d, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(U.dataLine(snap), "Game data from " + d);
  assert.equal(U.dataLine({ diag: { checks: [{ id: "snapshot", status: "off" }] } }), "");
  const long = "Word ".repeat(200);
  const notes = [1, 2, 3, 4].map((i) => ({ version: "0." + i + ".0", date: "2026-11-0" + i, text: long }));
  const m = U.model(block({ notes }), true, HOSTS);
  assert.equal(m.notes.length, 3);
  assert.match(m.notes[0], /^0\.1\.0, 2026-11-01: Word/);
  for (const n of m.notes) { assert.ok(n.length <= U.NOTE_MAX, n); }
  const doc = fakeDoc(BOX_IDS);
  U.paint(doc, snapOf(block({ notes })), { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-notes").kids.length, 3);
  assert.equal(doc.getElementById("update-notes-box").hidden, false);
  assert.equal(doc.getElementById("update-data").textContent, "Game data from " + d);
  // every fixed line and every built line fits two Settings lines of 47
  for (const t of Object.values(U.TEXT)) { assert.ok(t.length <= U.LINE_MAX, t); }
  for (const extra of [{ latest: "10.20.30-rc.1", newer: true },
    { latest: "10.20.30-rc.1", newer: true, staged: "10.20.30-rc.1" },
    { latest: "10.20.30-rc.1", newer: true, click_only: true }, { error: "http" }]) {
    const v = U.model(block(extra), true, HOSTS);
    assert.ok(v.line.length <= U.LINE_MAX, v.line);
    assert.ok(!/!|Oops|ERROR|HTTP/.test(v.line), v.line);
  }
  assert.ok(U.ACK_LABEL.length <= 24 && U.LINK_TEXT.length <= 47);
  // a malformed version is never shown
  assert.equal(U.model(block({ installed: "<b>1</b>" }), true, HOSTS).show, false);
});

test("the page holds one update container in About and data, and loads updates.js", () => {
  const about = HTML.indexOf('<section id="set-about"');
  const box = HTML.indexOf('<div id="update-box" class="rail-block"');
  assert.ok(about > 0 && box > about);
  assert.equal(HTML.split('id="update-box"').length, 2);
  assert.ok(HTML.indexOf("/web/updates.js") > HTML.indexOf("/web/checks.js"));
  assert.ok(HTML.indexOf("/web/updates.js") < HTML.indexOf("/web/app.js"));
  const boxHtml = HTML.slice(box, HTML.indexOf("</section>", box));
  assert.doesNotMatch(boxHtml, /aria-live|role="status"|<details/);
});
