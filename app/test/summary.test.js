"use strict";
/* UTIL-SESSION-SUMMARY: the last session card (web/summary.js). The core
   sends every sentence (server/al/summary.py); this only adds the end time.
   PLAY-TD-20B-RUN-CARDS: the card is a Run grid card whose page is the
   run history (web/history.js). PLAY-TD-21C-HISTORY-MOVE: the keep / clear
   switch sits in Settings > About and data, not on the card, and no jump
   row points at it. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const s = web.load("summary.js");
const h = web.load("history.js");

const CARD = { id: 2, reason: "idle", reason_text: "after 20 minutes with no game activity",
  ended_at: 1700000000, lines: ["Played 1:00:00 and reached level 70.", "Maps: 2.",
  "Deaths: 1."] };

test("summary view: the core's lines and the end sentence", () => {
  const v = s.view(CARD, () => "14:05");
  assert.deepEqual(v.lines, CARD.lines);
  assert.equal(v.ended, "Session ended at 14:05 after 20 minutes with no game activity.");
  const closed = s.view(Object.assign({}, CARD, { reason_text: "when the game closed" }),
                        () => "9:30");
  assert.equal(closed.ended, "Session ended at 9:30 when the game closed.");
  assert.equal(s.view(Object.assign({}, CARD, { reason_text: "" }), () => "9:30").ended,
               "Session ended at 9:30.");
  assert.equal(s.view(Object.assign({}, CARD, { ended_at: "x" }), () => "9:30").ended, "");
});

test("summary clock: time today, date and time for an older card", () => {
  const ts = new Date(2026, 10, 16, 9, 5).getTime() / 1000;
  assert.equal(s.clock(ts, new Date(2026, 10, 16, 23, 0).getTime()), "09:05");
  assert.equal(s.clock(ts, new Date(2026, 10, 17, 8, 0).getTime()), "2026-11-16 09:05");
});

test("summary view: null for no card; junk lines dropped", () => {
  assert.equal(s.view(null), null);
  assert.equal(s.view({ lines: [] }), null);
  assert.equal(s.view({ lines: "x" }), null);
  const v = s.view({ lines: ["Maps: 1.", 5, null, ""], ended_at: 1 }, () => "0:00");
  assert.deepEqual(v.lines, ["Maps: 1."]);
});

/* ---- a small fake DOM: enough for the card pages and the pagers -------- */
function matches(n, sel) {
  let m;
  if ((m = /^\[([\w-]+)="([^"]*)"\]$/.exec(sel))) { return n.attrs[m[1]] === m[2]; }
  if ((m = /^\[([\w-]+)\]$/.exec(sel))) { return m[1] in n.attrs; }
  if (sel.charAt(0) === ".") { return n.className.split(/\s+/).includes(sel.slice(1)); }
  return n.tagName === sel.toUpperCase();
}

function fakeDoc(size) {
  const doc = { activeElement: null, els: {} };
  doc.createElement = (tag) => ({
    tagName: tag.toUpperCase(), className: "", hidden: false, children: [], parentNode: null,
    attrs: {}, listeners: {}, _text: "", value: "", checked: false,
    get firstChild() { return this.children[0] || null; },
    get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
    set textContent(v) { this.children = []; this._text = String(v); },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.els[v] = this; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    hasAttribute(k) { return k in this.attrs; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
    contains(x) { return x === this || this.walk().includes(x); },
    walk(out) {
      out = out || [];
      this.children.forEach((c) => { out.push(c); if (c.walk) { c.walk(out); } });
      return out;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) { return this.walk().filter((c) => matches(c, sel)); },
    focus() { doc.activeElement = this; }
  });
  doc.getElementById = (id) => doc.els[id] || null;
  doc.defaultView = { getComputedStyle: () => ({ getPropertyValue: () => size || "full" }) };
  return doc;
}

function mk(doc, tag, attrs, kids) {
  const n = doc.createElement(tag);
  Object.keys(attrs || {}).forEach((k) => {
    if (k === "class") { n.className = attrs[k]; } else if (k === "hidden") { n.hidden = !!attrs[k]; } else {
      n.setAttribute(k, attrs[k]);
    }
  });
  (kids || []).forEach((k) => n.appendChild(k));
  return n;
}

/* The Last session card as web/index.html builds it: the summary home
   page and the Run history page; the keep / clear switch in the About and
   data section of Settings. */
function summaryCard(size) {
  const d = fakeDoc(size);
  const page = (name, label, kids, id) => mk(d, "div", Object.assign({ class: "card-page",
    "data-page": name, "data-label": label, hidden: name !== "main" }, id ? { id } : {}), kids);
  const head = mk(d, "h2", {});
  head.textContent = "Last session";
  mk(d, "section", { id: "summarybox", class: "card session grid-card", "data-home": "main" }, [
    mk(d, "div", { class: "card-head" }, [head, mk(d, "span", { class: "card-sub", "data-card-sub": "" }),
      mk(d, "button", { class: "card-back", "data-card-back": "", hidden: true })]),
    page("main", "", [mk(d, "p", { id: "summary-empty" }),
      mk(d, "div", { id: "summary-lines", hidden: true }), mk(d, "p", { id: "summary-ended", hidden: true }),
      mk(d, "div", { class: "card-foot" }, [mk(d, "button", { "data-card-open": "history", id: "open-history" })])]),
    page("history", "Run history", [mk(d, "p", { id: "history-empty", hidden: true }),
      mk(d, "div", { id: "history-rows", hidden: true })], "historybox")
  ]);
  mk(d, "section", { id: "set-about", class: "card rail-section", hidden: true }, [
    mk(d, "div", { class: "rail-block" }, [mk(d, "p", { id: "history-on" }),
      mk(d, "input", { id: "history-keep" }), mk(d, "button", { id: "history-clear" }),
      mk(d, "p", { id: "history-said" })])]);
  return d;
}

const listOf = (d, id) => d.getElementById(id).children[0].children[0]; // host > ul
const texts = (ul) => ul.children.map((li) => li.textContent);

test("summary paint: the lines page in the card; with no card it says when it fills", () => {
  const d = summaryCard();
  s.paint(d, { session_summary: CARD }, () => "14:05");
  assert.equal(d.getElementById("summarybox").hidden, false);
  assert.deepEqual(texts(listOf(d, "summary-lines")), CARD.lines);
  assert.equal(d.getElementById("summary-lines").hidden, false);
  assert.equal(d.getElementById("summary-empty").hidden, true);
  const ended = d.getElementById("summary-ended");
  assert.equal(ended.hidden, false);
  assert.equal(ended.textContent, "Session ended at 14:05 after 20 minutes with no game activity.");
  // no card: the card stays, its sentence says when it fills
  s.paint(d, { session_summary: null }, () => "14:05");
  assert.equal(d.getElementById("summarybox").hidden, false);
  assert.equal(d.getElementById("summary-lines").hidden, true);
  assert.equal(d.getElementById("summary-empty").hidden, false);
  assert.equal(ended.hidden, true);
  assert.equal(ended.textContent, "");
});

test("summary paint: lines page at 7 (5 compact); the pages open on a press only", () => {
  const lines = [];
  for (let i = 0; i < 9; i += 1) { lines.push("Line " + i + "."); }
  ["full", "compact"].forEach((size) => {
    const d = summaryCard(size);
    s.paint(d, { session_summary: Object.assign({}, CARD, { lines }) }, () => "14:05");
    assert.equal(listOf(d, "summary-lines").children.length, size === "full" ? 7 : 5, size);
  });
  assert.deepEqual(s.ROWS, { full: 7, compact: 5 });
  const d = summaryCard();
  s.paint(d, { session_summary: CARD }, () => "14:05");
  const box = d.getElementById("summarybox");
  const shown = () => box.querySelectorAll(".card-page").filter((p) => !p.hidden)
    .map((p) => p.getAttribute("data-page"));
  assert.deepEqual(shown(), ["main"]);
  s.paint(d, { session_summary: CARD }, () => "14:05");
  assert.deepEqual(shown(), ["main"]);
  d.getElementById("open-history").click();
  assert.deepEqual(shown(), ["history"]);
  assert.equal(box.querySelector("[data-card-sub]").textContent, "Run history");
  // a new snapshot leaves the page the player opened
  s.paint(d, { session_summary: null }, () => "14:05");
  assert.deepEqual(shown(), ["history"]);
  box.querySelector("[data-card-back]").click();
  assert.deepEqual(shown(), ["main"]);
  assert.equal(box.querySelectorAll("[data-card-open]").length, 1, "Run history is the one page");
});

const HIST = { on: true, runs: 3, text: "Run history is on.", empty_text: "", deaths_empty_text: "",
  best: [{ key: "G1", label: "Act 1", best_s: 1200, best_text: "20:00", delta_s: 100 },
    { key: "G2", label: "Act 2", best_s: 900, best_text: "15:00", delta_s: null },
    { key: "G3", label: "Act 3", best_s: 800, best_text: "13:20", delta_s: null, this_run: true }],
  deaths_by_zone: [{ zone: "Ogham", deaths: 4 }, { zone: "Grelwood", deaths: 1 }] };

test("run history page: best times, then the zones of most deaths, one line each", () => {
  assert.deepEqual(h.listRows(HIST).map((r) => r.text), [
    "Act 1: best 20:00, this run 1:40 slower",
    "Act 2: best 15:00, not reached this run",
    "Act 3: best so far 13:20 (this run)",
    "Most deaths: Ogham, 4 deaths",
    "Most deaths: Grelwood, 1 death"]);
  assert.equal(h.emptyText(HIST), "");
  // no death yet: the core's sentence closes the list
  const calm = Object.assign({}, HIST, { deaths_by_zone: [],
    deaths_empty_text: "No deaths in your saved runs." });
  assert.equal(h.listRows(calm).slice(-1)[0].text, "No deaths in your saved runs.");
  // nothing saved yet: the empty sentence in place of the list
  const none = Object.assign({}, HIST, { best: [], deaths_by_zone: [],
    empty_text: "No finished acts saved yet." });
  assert.deepEqual(h.listRows(none), []);
  assert.equal(h.emptyText(none), "No finished acts saved yet.");
  // off: it says so, says where the switch is, and lists nothing
  // (PLAY-TD-21C-HISTORY-MOVE: the switch left the card)
  const off = { on: false, best: [], deaths_by_zone: [], text: "Run history is off. Nothing is saved." };
  assert.deepEqual(h.listRows(off), []);
  assert.equal(h.OFF_WHERE, "Turn it on in Settings > About and data.");
  assert.equal(h.emptyText(off), "Run history is off. Nothing is saved. " + h.OFF_WHERE);
  assert.equal(h.emptyText({ on: false }), "");
  assert.equal(h.emptyText(null), "");
});

test("run history paint: the card's list page and the switch in Settings", () => {
  const d = summaryCard();
  h.paint(d, { run_history: HIST });
  assert.equal(texts(listOf(d, "history-rows")).length, 5);
  assert.equal(d.getElementById("history-rows").hidden, false);
  assert.equal(d.getElementById("history-empty").hidden, true);
  assert.equal(d.getElementById("history-on").textContent, "Run history is on.");
  assert.equal(d.getElementById("history-keep").checked, true);
  h.paint(d, { run_history: { on: false, best: [], deaths_by_zone: [], text: "Run history is off." } });
  assert.equal(d.getElementById("history-rows").hidden, true);
  assert.equal(d.getElementById("history-empty").textContent, "Run history is off. " + h.OFF_WHERE);
  assert.equal(d.getElementById("history-empty").hidden, false);
  // the Settings line beside the switch keeps the core's sentence alone
  assert.equal(d.getElementById("history-on").textContent, "Run history is off.");
  assert.equal(d.getElementById("history-keep").checked, false);
  // 9 rows a page (8 compact)
  const many = Object.assign({}, HIST, { best: [], deaths_by_zone: [] });
  for (let i = 0; i < 12; i += 1) {
    many.best.push({ key: "K" + i, label: "Act " + i, best_s: 60, best_text: "1:00", delta_s: null });
  }
  ["full", "compact"].forEach((size) => {
    const c = summaryCard(size);
    h.paint(c, { run_history: many });
    assert.equal(listOf(c, "history-rows").children.length, size === "full" ? 9 : 8, size);
  });
  assert.deepEqual(h.ROWS, { full: 9, compact: 8 });
});

test("the Last session card in the markup: a grid card with its Run history page", () => {
  const html = web.source("index.html");
  const at = html.indexOf('id="summarybox"');
  const box = html.slice(at, html.indexOf("</section>", at));
  assert.match(box, /^id="summarybox" class="card session grid-card"[^>]*data-home="main">/);
  assert.ok(box.includes('data-card-open="history"') && box.includes('data-page="history"'));
  assert.ok(!box.includes('data-card-open="keep"') && !box.includes('data-page="keep"'), "no keep page");
  ["summary-lines", "history-rows"].forEach((id) => {
    assert.ok(box.includes('id="' + id + '" class="pager-slot"'), id);
  });
  assert.ok(box.includes('id="historybox"'));
  ["history-keep", "history-clear", "history-said", "history-on"].forEach((id) => {
    assert.ok(!box.includes('id="' + id + '"'), id + " left the card");
  });
  assert.ok(!/<table|<details/.test(box));
  assert.ok(!/^id="summarybox"[^>]* hidden/.test(box), "the card always shows");
});

test("PLAY-TD-21C-HISTORY-MOVE: keep / clear sit in Settings > About and data, no jump row", () => {
  const html = web.source("index.html");
  const at = html.indexOf('<section id="set-about"');
  const about = html.slice(at, html.indexOf("</section>", at));
  ["history-on", "history-keep", "history-clear", "history-said"].forEach((id) => {
    assert.equal(html.split('id="' + id + '"').length, 2, id + " once on the page");
    assert.ok(about.includes('id="' + id + '"'), id + " in About and data");
  });
  assert.match(about, /<label class="check" for="history-keep"><input id="history-keep" type="checkbox">/);
  assert.match(about, /<button id="history-clear" type="button" class="secondary">Clear run history<\/button>/);
  assert.ok(!html.includes('data-jump="history-keep"'), "the jump row is gone");
  assert.ok(!html.includes('id="about-history"'));
  // the switch comes before the version line, which stays last
  assert.ok(about.indexOf('id="about-version"') > about.indexOf('id="history-said"'));
});
