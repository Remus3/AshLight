"use strict";
/* MATH-BUILD-HEALTH / MATH-NEXT-LOOK: the build health card (web/health.js).
   The core builds both lists from PoB's numbers; this file only shows them
   and copies a search string only on a click. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const h = web.load("health.js");

const DOC = {
  loaded: true,
  health: {
    loaded: true, has_stats: true, source: "PoB", message: null, weakest: null,
    warnings: [
      { id: "attr-str", severity: "high", text: "You don't meet the Strength requirement." },
      { id: "res-cold", severity: "medium", text: "Cold resistance is 71%, below the 75% cap." },
      { id: "weakest", severity: "low", text: "Your weakest element is cold." },
      { id: "junk", severity: "nope", text: "x" },
      { id: "empty", severity: "high", text: "" }],
    values: [
      { id: "Life", label: "Life", value: 2410, unit: "" },
      { id: "EffectiveBlockChance", label: "Block chance", value: 25.25, unit: "%" },
      { id: "Bad", label: "Bad", value: "x", unit: "" }]
  },
  next_look: {
    pob_weights: false,
    slots: [
      { slot: "Ring 1", terms: ["cold res", "maximum life"], line: "cold res, then maximum life",
        text: "\"cold res|maximum life\"", dropped: 0 },
      { slot: "Belt", terms: ["cold res"], line: "cold res", text: "\"cold res\"", dropped: 1 },
      { slot: "", line: "x", text: "y" }]
  }
};

test("view keeps known severities, words them, formats values", () => {
  const v = h.view(DOC);
  assert.equal(v.show, true);
  assert.deepEqual(v.warnings.map((w) => w.word), ["Fix first", "Check", "Note"]);
  assert.deepEqual(v.values, [{ label: "Life", text: "2,410" },
    { label: "Block chance", text: "25.3%" }]);
  assert.equal(v.message, "");
});

test("view says all clear only when PoB has no real warning", () => {
  const doc = { loaded: true, health: { loaded: true, has_stats: true, values: [],
    warnings: [{ id: "weakest", severity: "low", text: "Weakest is cold." }] } };
  assert.equal(h.view(doc).message, h.ALL_CLEAR);
});

test("UX-U25: no saved stats is said once, on the Build card, not in Build health", () => {
  const none = { loaded: true, health: { loaded: true, has_stats: false,
    message: "This build has no PoB numbers.", warnings: [], values: [] } };
  const v = h.view(none);
  assert.equal(v.message, "");
  assert.equal(v.show, false);
  const withNext = Object.assign({}, none, { next_look: { pob_weights: false,
    slots: [{ slot: "Ring 1", line: "Look for", text: "res" }] } });
  assert.equal(h.view(withNext).show, true);
  assert.equal(h.view(withNext).message, "");
  const html = web.source("index.html");
  assert.match(html.split("id=\"buildbox\"")[1].split("</section>")[0], /No stats saved in this build/);
});

test("view hides the card with no build", () => {
  assert.equal(h.view(null).show, false);
  assert.equal(h.view({ loaded: false, health: DOC.health }).show, false);
  assert.equal(h.view({ loaded: true, health: { loaded: false } }).show, false);
});

test("nextView lists valid rows, notes dropped terms, hints without PoB weights", () => {
  const v = h.nextView(DOC);
  assert.equal(v.rows.length, 2);
  assert.equal(v.rows[0].slot, "Ring 1");
  assert.equal(v.rows[1].note, "Shortened to fit the search box: 1 term left out.");
  assert.equal(v.hint, h.NO_WEIGHTS);
  const withW = h.nextView({ loaded: true, next_look: { pob_weights: true, slots: [] } });
  assert.equal(withW.hint, "");
  assert.deepEqual(h.nextView(null), { rows: [], hint: "" });
});

test("the clipboard is written only inside the Copy click handler", () => {
  /* PLAY-TD-19C-BUILD-GRID: the Copy button of a look-for-next row is
     ALSearch.copyButton (web/search.js), whose click handler is the one
     place that writes; this file adds no handler and no clipboard call */
  const src = web.source("health.js", "ascii");
  assert.ok(src.indexOf("addEventListener(") < 0);
  assert.ok(src.indexOf("writeText") < 0 && src.indexOf(".clipboard") < 0);
  assert.equal(src.split("S.copyButton(d, r.text,").length - 1, 1);
  assert.ok(!/setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live/.test(src));
});

test("the page loads the script and has the card without a live region", () => {
  const html = web.source("index.html", "ascii");
  assert.ok(html.indexOf("/web/health.js") > 0);
  const card = html.split("id=\"healthbox\"")[1].split("</section>")[0];
  assert.ok(card.indexOf("aria-live") < 0 && card.indexOf("role=\"status\"") < 0);
  for (const id of ["health-msg", "health-list", "next-wrap", "next-list", "def-wrap", "def-list",
    "def-hint", "build-gear", "build-skills", "build-notes"]) {
    assert.ok(card.indexOf("id=\"" + id + "\"") > 0, id);
  }
  /* PLAY-TD-19C-BUILD-GRID: a card of the grid, always shown, with the
     pages of plan 03 section 4 (gear, gems, notes) and Numbers */
  assert.match(html, /<section id="healthbox" class="card health grid-card"[^>]*>/);
  assert.doesNotMatch(card.split(">")[0], /hidden/);
  for (const page of ["main", "numbers", "gear", "gems", "notes"]) {
    assert.match(card, new RegExp("class=\"card-page\" data-page=\"" + page + "\""), page);
  }
  for (const page of ["numbers", "gear", "gems", "notes"]) {
    assert.match(card, new RegExp("data-card-open=\"" + page + "\""), page);
  }
  assert.ok(card.indexOf("<details") < 0, "no fold can grow the card");
});

const PAINT_IDS = ["healthbox", "health-msg", "health-list", "next-wrap", "next-title", "next-list",
  "next-hint", "def-hint", "def-list"];

test("PLAY-TD-19C-BUILD-GRID: the top 3 health rows on the card, the rest on Numbers", () => {
  const many = { loaded: true, health: { loaded: true, has_stats: true, values: DOC.health.values,
    warnings: [1, 2, 3, 4, 5].map((i) => ({ id: "w" + i, severity: "medium", text: "Warning " + i })),
    defence: [{ label: "Stun threshold", value: 512, unit: "", digits: 0 }] } };
  const doc = fakeDoc(PAINT_IDS);
  h.paint(doc, many, {});
  const top = doc.els["health-list"].children;
  assert.equal(top.length, h.TOP);
  assert.equal(top[0].attrs.title, "Check: Warning 1");
  assert.match(top[0].className, /one-line/);
  assert.deepEqual(h.numberRows(many), ["Check: Warning 4", "Check: Warning 5", "Life: 2,410",
    "Block chance: 25.3%", "Stun threshold: 512"]);
  const nums = doc.els["def-list"].children[0];
  assert.deepEqual(nums.children[0].children.map((li) => li.textContent), h.numberRows(many));
  assert.equal(doc.els.healthbox.hidden, false);
});

test("PLAY-TD-19C-BUILD-GRID: no build still shows the card, saying so in one row", () => {
  const doc = fakeDoc(PAINT_IDS);
  h.paint(doc, null, {});
  assert.equal(doc.els.healthbox.hidden, false);
  assert.equal(doc.els["health-msg"].textContent, h.EMPTY);
  assert.equal(doc.els["health-list"].hidden, true);
  assert.equal(doc.els["next-wrap"].hidden, true);
  const nums = doc.els["def-list"].children[0].children[0];
  assert.deepEqual(nums.children.map((li) => li.textContent), [h.EMPTY]);
});

test("PLAY-TD-19C-BUILD-GRID: a build with no PoB numbers says why the card is empty", () => {
  const none = { loaded: true, health: { loaded: true, has_stats: false, warnings: [], values: [] } };
  const doc = fakeDoc(PAINT_IDS);
  h.paint(doc, none, {});
  assert.equal(doc.els["health-msg"].textContent, h.NO_HEALTH);
  assert.ok(h.NO_HEALTH.indexOf("copy") < 0, "the fix is said once, on the Build card (UX-U25)");
});

test("PLAY-TD-19C-BUILD-GRID: look for next pages 4 rows (2 compact) with Copy and Trade", () => {
  const slots = Array.from({ length: 6 }, (_, i) => ({ slot: "Slot " + i, line: "life",
    text: "\"life " + i + "\"", base: "Base " + i, url: URL_OK }));
  const doc = fakeDoc(PAINT_IDS);
  h.paint(doc, { loaded: true, health: DOC.health, next_look: { pob_weights: true, slots } }, {});
  assert.deepEqual(h.NEXT_SIZE, { full: 4, compact: 2 });
  const host = doc.els["next-list"].children[0];
  const list = host.children[0];
  assert.equal(list.children.length, 4);
  const row = list.children[0];
  assert.equal(row.className, "al-row-ctl");
  assert.equal(row.children[0].attrs.title, "Slot 0: life - \"life 0\"");
  assert.equal(row.children[1].textContent, "Copy");
  assert.equal(row.children[1].attrs["aria-label"], "Copy Slot 0 search string");
  assert.equal(row.children[2].tagName, "A");
  assert.equal(row.children[2].textContent, "Trade");
  assert.equal(host.children[1].children[0].textContent, "1-4 of 6");
});

/* TC-UPGRADE-PER-SLOT: each "look for next" row may link to the official
   trade site's search for its slot (built offline by the core, decision
   0017); the player's click opens it. */
const URL_OK = "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%22query%22%3A1%7D";

function linkDoc(url, base) {
  return { loaded: true, health: DOC.health, next_look: { pob_weights: true, slots: [
    { slot: "Ring 1", terms: ["cold res"], line: "cold resistance", text: "\"cold res\"",
      dropped: 0, base: base === undefined ? "Example Ring" : base, url: url }] } };
}

/* a small fake DOM: enough for web/health.js and the pagers of
   web/search.js and web/pager.js (no browser, no timers) */
function fakeDoc(ids) {
  function node(tag) {
    const n = { tagName: tag.toUpperCase(), children: [], dataset: {}, attrs: {}, hidden: false,
      className: "", parentNode: null, listeners: {}, _text: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
      replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
      querySelector() { return null; },
      querySelectorAll() { return []; } };
    return n;
  }
  const els = {};
  ids.forEach((id) => { els[id] = node("div"); });
  return { els, getElementById: (id) => els[id] || null, createElement: node,
    createTextNode: (t) => ({ tagName: "#text", textContent: t, children: [] }) };
}

function anchors(n, out) {
  out = out || [];
  if (n.tagName === "A") { out.push(n); }
  (n.children || []).forEach((c) => anchors(c, out));
  return out;
}

test("nextView links a row only for an https trade2 search url and a base", () => {
  const link = h.nextView(linkDoc(URL_OK)).rows[0].link;
  assert.deepEqual(link, { href: URL_OK,
    text: "Search the official trade site for rare Example Ring (Ring 1)",
    label: "Search the official trade site for rare Example Ring (Ring 1) (opens in a new tab)" });
  for (const bad of [undefined, null, "", "http://www.pathofexile.com/trade2/search/poe2/Standard?q=1",
    "https://evil.example/trade2/search/poe2/Standard?q=1",
    "https://www.pathofexile.com/trade2/search/poe2/Standard?q=1&x=2",
    "javascript:alert(1)", "https://www.pathofexile.com/trade2/search/poe2/Standard?q=" + "a".repeat(5000)]) {
    assert.equal(h.nextView(linkDoc(bad)).rows[0].link, null, String(bad).slice(0, 60));
  }
  assert.equal(h.nextView(linkDoc(URL_OK, null)).rows[0].link, null);
  assert.equal(h.nextView(DOC).rows[0].link, null);
  assert.equal(h.tradeLink(URL_OK), URL_OK);
});

test("paint renders the trade link as a new-tab anchor, and none for a bad url", () => {
  const ids = PAINT_IDS;
  const doc = fakeDoc(ids);
  h.paint(doc, linkDoc(URL_OK), {});
  const got = anchors(doc.els["next-list"]);
  assert.equal(got.length, 1);
  assert.equal(got[0].href, URL_OK);
  assert.equal(got[0].target, "_blank");
  assert.equal(got[0].rel, "noopener noreferrer");
  assert.equal(got[0].textContent, "Trade");
  assert.equal(got[0].attrs.title, "Search the official trade site for rare Example Ring (Ring 1)");
  assert.match(got[0].attrs["aria-label"], /^Search the official trade site .*\(opens in a new tab\)$/);
  const doc2 = fakeDoc(ids);
  h.paint(doc2, linkDoc("https://evil.example/trade2/search/poe2/Standard?q=1"), {});
  assert.equal(anchors(doc2.els["next-list"]).length, 0);
  assert.equal(doc2.els["next-list"].children[0].children[0].children.length, 1,
    "the row itself still shows");
});

test("the trade link rule matches the price card's and nothing fetches it", () => {
  const src = web.source("health.js", "ascii");
  const re = (s) => s.match(/var TRADE_SEARCH = (\/.*\/);/)[1];
  assert.equal(re(src), re(web.source("prices.js", "ascii")));
  assert.ok(!/window\.open|location\s*=|\.click\(\)/.test(src));
});
