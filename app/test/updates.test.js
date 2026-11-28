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
  "update-ack", "update-link", "update-link-row", "update-said", "update-notes-box", "update-notes",
  "update-staged", "update-now-row", "update-now", "update-now-said", "update-click-row",
  "update-click-only", "update-click-said", "update-now-note"];

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
  assert.equal(m.line, "AshLight 0.5.0 is out. It downloads while the game is closed, then installs.");
  assert.equal(m.mark, "update");
  // UX-UPDATE-WORDS (review 2026-11-28 P2-7): "later start" made concrete
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, staged: "0.5.0" }), true, HOSTS).line,
    "AshLight 0.5.0 is downloaded. It installs when you next open AshLight, a day after release.");
  // P2-5: a checkout has no Update now, so its click-only line keeps GitHub
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, click_only: true }), true, HOSTS).line,
    "AshLight 0.5.0 is out. See what changed on GitHub.");
  // an installed copy points at the one button that installs it
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, click_only: true }), true, HOSTS, true)
    .line, "AshLight 0.5.0 is out. Click Update now to install it.");
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, click_only: true, staged: "0.5.0" }),
    true, HOSTS, true).line, "AshLight 0.5.0 is downloaded. Click Update now to install it.");
  // paint: the mark goes to the Settings tab; nothing opens
  const doc = fakeDoc(BOX_IDS);
  const tabs = fakeTabs();
  // (no toast or window anywhere: tests/test_glance_rules.py scans the tree)
  U.paint(doc, snapOf(block({ latest: "0.5.0", newer: true })), { hosts: HOSTS, tabs });
  assert.deepEqual(tabs.marks, [["settings", "update"]]);
  assert.equal(doc.getElementById("update-box").hidden, false);
  assert.equal(doc.getElementById("update-line").textContent,
    "AshLight 0.5.0 is out. It downloads while the game is closed, then installs.");
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
  assert.ok(new Set(HOSTS).has("github.com"));
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
  assert.match(s,
    /downloads by itself while the game is closed and installs the next time you open AshLight/);
  assert.doesNotMatch(s, /later start/);
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
    { latest: "10.20.30-rc.1", newer: true, click_only: true },
    { latest: "10.20.30-rc.1", newer: true, click_only: true, staged: "10.20.30-rc.1" },
    { error: "http" }]) {
    const v = U.model(block(extra), true, HOSTS, true);
    assert.ok(v.line.length <= U.LINE_MAX, v.line);
    assert.ok(!/!|Oops|ERROR|HTTP/.test(v.line), v.line);
  }
  assert.ok(U.ACK_LABEL.length <= 24 && U.LINK_TEXT.length <= 47);
  // a malformed version is never shown
  assert.equal(U.model(block({ installed: "<b>1</b>" }), true, HOSTS).show, false);
});

/* UX-UPDATE-WORDS (docs/reviews/ux/2026-11-28.md P2-6, P2-7): the off lines
   name where web data is, and no update line says "a later start". */
test("the off lines name Settings, Reading and web data; no line says a later start", () => {
  assert.equal(U.TEXT.off,
    "Update checks are off while web data is off. Turn it on in Settings, Reading and web data.");
  assert.equal(U.NOW_SAID.off, "Turn on web data in Settings, Reading and web data first.");
  assert.equal(U.TEXT.ack,
    "Web data now also checks daily for a new AshLight and installs it when you next open " +
    "AshLight.");
  for (const t of Object.values(U.TEXT).concat(Object.values(U.NOW_SAID))) {
    assert.doesNotMatch(t, /later start/, t);
  }
  assert.doesNotMatch(HTML, /later start/);
});

/* P3-7: Update now skips the idle gate, so a muted note says AshLight closes
   for a moment, only while the snapshot's game_idle is not true. */
test("a muted note beside Update now while the game is not idle", () => {
  const busy = "AshLight closes for about a minute to update. Best while the game is closed.";
  assert.equal(U.TEXT.nowBusy, busy);
  const newer = block({ latest: "0.5.0", newer: true });
  assert.equal(U.model(newer, true, HOSTS, true, false).nowNote, busy);
  assert.equal(U.model(newer, true, HOSTS, true).nowNote, busy);
  assert.equal(U.model(newer, true, HOSTS, true, true).nowNote, "");
  // no button, no note
  assert.equal(U.model(block(), true, HOSTS, true, false).nowNote, "");
  assert.equal(U.model(newer, true, HOSTS, false, false).nowNote, "");
  const doc = fakeDoc(BOX_IDS);
  const snap = snapOf(newer, [INSTALL]);
  U.paint(doc, snap, { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-now-note").textContent, busy);
  assert.equal(doc.getElementById("update-now-note").hidden, false);
  snap.game_idle = true;
  U.paint(doc, snap, { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-now-note").textContent, "");
  assert.equal(doc.getElementById("update-now-note").hidden, true);
  assert.match(HTML, /<span id="update-now-note" class="muted"[^>]*hidden><\/span>/);
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

/* REL-AUTOSTART-SETTINGS (folded REL-UPDATE-UI; F-077, DEP-17, decision
   0065): the staged line, 'Update now' and the click-only switch. */
const INSTALL = { id: "install", status: "pass" };

test("installed copy: the staged line and Update now only with a staged or newer version", () => {
  assert.equal(U.installedCopy(snapOf(block(), [INSTALL])), true);
  assert.equal(U.installedCopy(snapOf(block())), false);
  // a checkout: no controls whatever the block says
  const co = U.model(block({ latest: "0.5.0", newer: true, staged: "0.5.0" }), true, HOSTS, false);
  assert.equal(co.now, false);
  assert.equal(co.click, false);
  assert.equal(co.staged, "");
  // installed, up to date, nothing staged: the switch, no button
  const cur = U.model(block(), true, HOSTS, true);
  assert.equal(cur.now, false);
  assert.equal(cur.click, true);
  assert.equal(cur.staged, "");
  // a newer version: the button
  assert.equal(U.model(block({ latest: "0.5.0", newer: true }), true, HOSTS, true).now, true);
  // staged and newest: the main line names it, no second line
  const st = U.model(block({ latest: "0.5.0", newer: true, staged: "0.5.0" }), true, HOSTS, true);
  assert.equal(st.now, true);
  assert.equal(st.staged, "");
  assert.match(st.line, /0\.5\.0 is downloaded/);
  // staged while the newest is another one: one line names the staged one
  const two = U.model(block({ latest: "0.6.0", newer: true, staged: "0.5.0" }), true, HOSTS, true);
  assert.equal(two.staged, "AshLight 0.5.0 is downloaded. Update now installs it.");
  assert.equal(two.now, true);
  const only = U.model(block({ staged: "0.5.0" }), true, HOSTS, true);
  assert.equal(only.staged, "AshLight 0.5.0 is downloaded. Update now installs it.");
  assert.equal(only.now, true);
  // web data off or the wording not acknowledged: no button (the core refuses)
  assert.equal(U.model(block({ latest: "0.5.0", newer: true }), false, HOSTS, true).now, false);
  assert.equal(U.model(block({ latest: "0.5.0", newer: true, ack_needed: true }), true, HOSTS, true).now,
    false);
  // a bad staged version is never shown
  assert.equal(U.model(block({ staged: "<b>" }), true, HOSTS, true).staged, "");
  // paint
  const doc = fakeDoc(BOX_IDS);
  U.paint(doc, snapOf(block({ latest: "0.6.0", newer: true, staged: "0.5.0" }), [INSTALL]),
    { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(doc.getElementById("update-staged").hidden, false);
  assert.equal(doc.getElementById("update-staged").textContent,
    "AshLight 0.5.0 is downloaded. Update now installs it.");
  assert.equal(doc.getElementById("update-now-row").hidden, false);
  assert.equal(doc.getElementById("update-click-row").hidden, false);
  const d2 = fakeDoc(BOX_IDS);
  U.paint(d2, snapOf(block({ latest: "0.6.0", newer: true, staged: "0.5.0" })),
    { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(d2.getElementById("update-staged").hidden, true);
  assert.equal(d2.getElementById("update-now-row").hidden, true);
  assert.equal(d2.getElementById("update-click-row").hidden, true);
});

test("Update now: one POST with the token header and no body; the answer word in plain words", async () => {
  const req = U.nowRequest("t0k");
  assert.deepEqual(req, { method: "POST", cache: "no-store",
    headers: { "X-AL-Token": "t0k", "Content-Type": "application/json" } });
  assert.equal("body" in req, false);
  const doc = fakeDoc(BOX_IDS);
  const calls = [];
  const fetch = (url, opts) => {
    calls.push([url, opts]);
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ started: true, state: "started" }) });
  };
  U.wire(doc, () => Promise.resolve({}), () => null, null, { fetch, token: () => "t0k" });
  const btn = doc.getElementById("update-now");
  btn.fire("click");
  btn.fire("click"); // a second click while it runs adds nothing
  await tick(); await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/update-now");
  assert.equal("body" in calls[0][1], false);
  assert.equal(calls[0][1].headers["X-AL-Token"], "t0k");
  assert.equal(doc.getElementById("update-now-said").textContent, U.NOW_SAID.started);
  for (const w of Object.keys(U.NOW_SAID)) { assert.equal(U.nowSaid({ state: w }), U.NOW_SAID[w]); }
  assert.equal(U.nowSaid({ state: "failed" }), U.TEXT.nowFailed);
  assert.equal(U.nowSaid(null), U.TEXT.nowFailed);
  // a refused request says it did not start
  const d2 = fakeDoc(BOX_IDS);
  U.wire(d2, () => Promise.resolve({}), () => null, null,
    { fetch: () => Promise.resolve({ ok: false, status: 403 }), token: "x" });
  d2.getElementById("update-now").fire("click");
  await tick(); await tick();
  assert.equal(d2.getElementById("update-now-said").textContent, U.TEXT.nowFailed);
  for (const t of Object.values(U.NOW_SAID)) { assert.ok(t.length <= U.LINE_MAX, t); }
  assert.match(HTML, new RegExp("<button id=\"update-now\"[^>]*>" + U.NOW_LABEL + "</button>"));
});

test("the click-only switch: shows the core's state and saves one allow-listed key", async () => {
  assert.equal(U.model(block({ click_only: true }), true, HOSTS, true).clickOnly, true);
  assert.equal(U.model(block(), true, HOSTS, true).clickOnly, false);
  assert.deepEqual(U.clickBody(true),
    { kind: "ashlight-settings", schema: 1, settings: { update_click_only: true } });
  const doc = fakeDoc(BOX_IDS);
  const box = doc.getElementById("update-click-only");
  U.paint(doc, snapOf(block({ click_only: true }), [INSTALL]), { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(box.checked, true);
  assert.equal(doc.getElementById("update-click-said").textContent, U.TEXT.clickOn);
  const calls = [];
  let answer = { applied: ["update_click_only"], ignored: [] };
  U.wire(doc, (m, p, b) => { calls.push([m, p, b]); return Promise.resolve(answer); }, () => null);
  box.checked = false;
  box.fire("change");
  await tick(); await tick();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)),
    [["POST", "/api/settings-import", U.clickBody(false)]]);
  assert.equal(doc.getElementById("update-click-said").textContent, U.TEXT.clickOff);
  // the snapshot has not caught up yet: the player's value stays
  U.paint(doc, snapOf(block({ click_only: true, checked_at: 1795400001 }), [INSTALL]),
    { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(box.checked, false);
  // the core's next pass agrees
  U.paint(doc, snapOf(block({ click_only: false }), [INSTALL]), { hosts: HOSTS, tabs: fakeTabs() });
  assert.equal(box.checked, false);
  assert.equal(box.getAttribute("data-want"), null);
  // not applied: the box goes back and says so
  answer = { applied: [], ignored: ["update_click_only"] };
  box.checked = true;
  box.fire("change");
  await tick(); await tick();
  assert.equal(box.checked, false);
  assert.equal(doc.getElementById("update-click-said").textContent, U.TEXT.notSaved);
  const label = /<label class="check" for="update-click-only"><input\s+id="update-click-only" type="checkbox" aria-describedby="update-click-said"> ([^<]+)<\/label>/.exec(HTML);
  assert.ok(label, "the switch has its label");
  assert.equal(label[1], U.CLICK_LABEL);
  for (const t of [U.TEXT.clickOn, U.TEXT.clickOff]) { assert.ok(t.length <= U.LINE_MAX, t); }
});

test("SAVE-FAIL-SAY: a failed OK ack or click-only save is also said on the polite line", async () => {
  const said = [];
  const tabs = { say(doc, text) { said.push(text); } };
  // the OK ack refused by the core
  const doc = fakeDoc(BOX_IDS);
  U.wire(doc, () => Promise.reject(new Error("x")), () => ({ wording_version: 1 }), null, { tabs });
  doc.getElementById("update-ack").fire("click");
  await tick(); await tick();
  assert.equal(doc.getElementById("update-said").textContent, U.TEXT.notSaved);
  assert.deepEqual(said, [U.TEXT.notSaved]);
  // no wording version known: nothing is sent, the same words are said
  const d2 = fakeDoc(BOX_IDS);
  U.wire(d2, () => Promise.resolve({}), () => null, null, { tabs });
  d2.getElementById("update-ack").fire("click");
  await tick();
  assert.deepEqual(said, [U.TEXT.notSaved, U.TEXT.notSaved]);
  // the click-only switch not applied
  const d3 = fakeDoc(BOX_IDS);
  U.wire(d3, () => Promise.resolve({ applied: [] }), () => null, null, { tabs });
  const box = d3.getElementById("update-click-only");
  box.checked = true;
  box.fire("change");
  await tick(); await tick();
  assert.equal(d3.getElementById("update-click-said").textContent, U.TEXT.notSaved);
  assert.deepEqual(said, [U.TEXT.notSaved, U.TEXT.notSaved, U.TEXT.notSaved]);
  // a save that works says nothing on the polite line (its own line shows it)
  const d4 = fakeDoc(BOX_IDS);
  U.wire(d4, () => Promise.resolve({ acked: true }), () => ({ wording_version: 1 }), null, { tabs });
  d4.getElementById("update-ack").fire("click");
  await tick(); await tick();
  assert.equal(d4.getElementById("update-said").textContent, U.TEXT.acked);
  assert.equal(said.length, 3);
});
