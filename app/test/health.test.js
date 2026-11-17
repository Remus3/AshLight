"use strict";
/* MATH-BUILD-HEALTH / MATH-NEXT-LOOK: the build health card (web/health.js).
   The core builds both lists from PoB's numbers; this file only shows them
   and copies a search string only on a click. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const h = require("../../web/health.js");

const WEB = path.join(__dirname, "..", "..", "web");

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
  const none = { loaded: true, health: { loaded: true, has_stats: false,
    message: "This build has no PoB numbers.", warnings: [], values: [] } };
  assert.equal(h.view(none).message, "This build has no PoB numbers.");
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
  const src = fs.readFileSync(path.join(WEB, "health.js"), "ascii");
  const body = src.split("addEventListener(\"click\"");
  assert.equal(body.length, 2, "one click handler");
  assert.equal(src.split("copyText(r.text").length - 1, 1);
  assert.ok(body[1].indexOf("copyText(r.text") >= 0);
  assert.ok(!/setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live/.test(src));
});

test("the page loads the script and has the card without a live region", () => {
  const html = fs.readFileSync(path.join(WEB, "index.html"), "ascii");
  assert.ok(html.indexOf("/web/health.js") > 0);
  const card = html.split("id=\"healthbox\"")[1].split("</section>")[0];
  assert.ok(card.indexOf("aria-live") < 0 && card.indexOf("role=\"status\"") < 0);
  for (const id of ["health-msg", "health-list", "health-values", "next-wrap", "next-list"]) {
    assert.ok(card.indexOf("id=\"" + id + "\"") > 0, id);
  }
});
