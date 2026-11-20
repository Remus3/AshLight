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
  const src = web.source("health.js", "ascii");
  const body = src.split("addEventListener(\"click\"");
  assert.equal(body.length, 2, "one click handler");
  assert.equal(src.split("copyText(r.text").length - 1, 1);
  assert.ok(body[1].indexOf("copyText(r.text") >= 0);
  assert.ok(!/setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live/.test(src));
});

test("the page loads the script and has the card without a live region", () => {
  const html = web.source("index.html", "ascii");
  assert.ok(html.indexOf("/web/health.js") > 0);
  const card = html.split("id=\"healthbox\"")[1].split("</section>")[0];
  assert.ok(card.indexOf("aria-live") < 0 && card.indexOf("role=\"status\"") < 0);
  for (const id of ["health-msg", "health-list", "health-values", "next-wrap", "next-list"]) {
    assert.ok(card.indexOf("id=\"" + id + "\"") > 0, id);
  }
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

function fakeDoc(ids) {
  function node(tag) {
    const n = { tagName: tag.toUpperCase(), children: [], dataset: {}, attrs: {}, hidden: false,
      textContent: "", className: "",
      appendChild(c) { this.children.push(c); return c; },
      replaceChildren() { this.children = []; },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      addEventListener() {},
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
  const ids = ["healthbox", "health-msg", "health-list", "health-values", "next-wrap", "next-list",
    "next-hint"];
  const doc = fakeDoc(ids);
  h.paint(doc, linkDoc(URL_OK), {});
  const got = anchors(doc.els["next-list"]);
  assert.equal(got.length, 1);
  assert.equal(got[0].href, URL_OK);
  assert.equal(got[0].target, "_blank");
  assert.equal(got[0].rel, "noopener noreferrer");
  assert.equal(got[0].textContent, "Search the official trade site for rare Example Ring (Ring 1)");
  assert.match(got[0].attrs["aria-label"], /\(opens in a new tab\)$/);
  const doc2 = fakeDoc(ids);
  h.paint(doc2, linkDoc("https://evil.example/trade2/search/poe2/Standard?q=1"), {});
  assert.equal(anchors(doc2.els["next-list"]).length, 0);
  assert.equal(doc2.els["next-list"].children.length, 1, "the row itself still shows");
});

test("the trade link rule matches the price card's and nothing fetches it", () => {
  const src = web.source("health.js", "ascii");
  const re = (s) => s.match(/var TRADE_SEARCH = (\/.*\/);/)[1];
  assert.equal(re(src), re(web.source("prices.js", "ascii")));
  assert.ok(!/window\.open|location\s*=|\.click\(\)/.test(src));
});
