"use strict";
/* UTIL-SEARCHSTR: the search string card (web/search.js). The core builds
   every string; this lists them and copies only on a click. Fixture values
   are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const s = require("../../web/search.js");

const DOC = { loaded: true, search_strings: [
  { id: "resists", label: "Resistances you still need", why: "Finds gear.",
    text: "\"cold res|chaos res\"", terms: 2, dropped: 0 },
  { id: "bases", label: "Your gear bases", why: "", text: "\"a|b\"", terms: 2, dropped: 3 },
  { id: "junk", label: 5, text: "" }] };

test("view lists strings with text only and says what was left out", () => {
  const rows = s.view(DOC);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].label, "Resistances you still need");
  assert.equal(rows[0].note, "");
  assert.equal(rows[1].note, "Shortened to fit the search box: 3 terms left out.");
  assert.deepEqual(s.view(null), []);
  assert.deepEqual(s.view({ loaded: false, search_strings: DOC.search_strings }), []);
  assert.deepEqual(s.view({ loaded: true, search_strings: "x" }), []);
});

test("copy writes only through the clipboard API it is handed", async () => {
  const wrote = [];
  const nav = { clipboard: { writeText: (t) => { wrote.push(t); return Promise.resolve(); } } };
  await new Promise((done) => s.copy("\"x\"", nav, done, () => assert.fail("no fallback")));
  assert.deepEqual(wrote, ["\"x\""]);
  let fell = false;
  s.copy("y", {}, () => assert.fail("no clipboard"), () => { fell = true; });
  assert.ok(fell);
});

test("the clipboard is written only inside a click handler", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "..", "web", "search.js"), "ascii");
  const calls = src.split("copy(r.text").length - 1;
  assert.equal(calls, 1);
  const at = src.indexOf("copy(r.text");
  assert.ok(src.lastIndexOf("addEventListener(\"click\"", at) > src.lastIndexOf("function paint", at));
  assert.equal(src.split("writeText(").length - 1, 1);
});
