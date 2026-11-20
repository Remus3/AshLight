/* UTIL-RUN-HISTORY / UTIL-PRICE-WATCH / UX-SETTINGS-IO: exact output of
   the dashboard helpers (web/history.js, web/pricewatch.js,
   web/settingsio.js). The core sends the sentences; these only format. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const h = web.load("history.js");
const pw = web.load("pricewatch.js");
const sio = web.load("settingsio.js");

test("history: delta text and rows", () => {
  assert.equal(h.deltaText(90), "1:30 slower");
  assert.equal(h.deltaText(-45), "0:45 faster");
  assert.equal(h.deltaText(0.4), "same as best");
  assert.equal(h.deltaText(null), "");
  assert.deepEqual(h.bestRows({ best: [
    { key: "G1", label: "Act 1", best_s: 1200, best_text: "20:00", delta_s: 100 },
    { key: "G2", label: "Act 2", best_s: 900, best_text: "15:00", delta_s: null }] }), [
    { label: "Act 1", best: "20:00", delta: "1:40 slower", slower: true },
    { label: "Act 2", best: "15:00", delta: "", slower: false }]);
  assert.deepEqual(h.deathRows({ deaths_by_zone: [{ zone: "Ogham", deaths: 4 },
    { zone: "Grelwood", deaths: 1 }] }), ["Ogham: 4 deaths", "Grelwood: 1 death"]);
  assert.deepEqual(h.bestRows(null), []);
});

test("history: the under-level line left with the old Level tile", () => {
  // PLAY-LEGACY-OUT-1: the strip's sub line carries the under-level words
  assert.equal(h.underlevelText, undefined);
  const ids = [];
  h.paint({ getElementById: (id) => { ids.push(id); return null; } }, { underlevel: { text: "x" } });
  assert.deepEqual(ids, ["historybox"]);
});

test("price watch: model", () => {
  assert.deepEqual(pw.model(null), { text: "", rows: [], canClear: false });
  assert.deepEqual(pw.model({ count: 2, text: "", moved: [
    { text: "A: 1 -> 2 Divine Orb (up 100%)", change_pct: 100 },
    { text: "B: 4 -> 2 Divine Orb (down 50%)", change_pct: -50 }] }), {
    text: "", canClear: true,
    rows: [{ text: "A: 1 -> 2 Divine Orb (up 100%)", up: true },
           { text: "B: 4 -> 2 Divine Orb (down 50%)", up: false }] });
});

test("settings io: import sentences", () => {
  assert.equal(sio.importedText({ applied: ["league"], ignored: [], web_data_offered: false }),
    "Imported 1 setting.");
  assert.equal(sio.importedText({ applied: ["a", "b"], ignored: ["contact"],
    web_data_offered: true }),
  "Imported 2 settings. Skipped 1 setting that AshLight doesn't take from a file." +
    sio.WEB_OFFER);
  assert.equal(sio.importedText({ applied: [] }), "No settings in that file were changed.");
  // FOLLOWUP11: a file with the calc on gets one plain sentence, and the
  // calc is not counted as skipped as well
  assert.equal(sio.importedText({ applied: ["league"], ignored: ["tc_calc"],
    tc_calc_offered: true }), "Imported 1 setting." + sio.CALC_OFFER);
  assert.equal(sio.importedText({ applied: [], ignored: ["contact", "tc_calc"],
    web_data_offered: true, tc_calc_offered: true }),
  "No settings in that file were changed. Skipped 1 setting that AshLight doesn't " +
    "take from a file." + sio.WEB_OFFER + sio.CALC_OFFER);
  assert.equal(sio.importedText({ applied: [], ignored: ["tc_calc"] }),
    "No settings in that file were changed. Skipped 1 setting that AshLight doesn't " +
    "take from a file.");
  assert.match(sio.CALC_OFFER, /^ [^\n]+\.$/);
  assert.equal(sio.refusedText(413, null), sio.TOO_BIG);
  assert.equal(sio.refusedText(400, { error: "Bad." }), "Bad. Nothing changed.");
  assert.equal(sio.refusedText(500, null), sio.FAILED);
});

function fakeFile(text, size) {
  return { size: size === undefined ? text.length : size, text: () => Promise.resolve(text) };
}

test("settings io: import posts parsed JSON with the token; refuses big or bad files", async () => {
  const said = [];
  const calls = [];
  const env = {
    token: "abc",
    tell: (t) => said.push(t),
    fetch: (url, opts) => {
      calls.push([url, opts]);
      return Promise.resolve({ ok: true, status: 200,
        json: () => Promise.resolve({ applied: ["league"], ignored: [], web_data_offered: false }) });
    }
  };
  await sio.runImport(fakeFile('{"kind":"ashlight-settings"}'), env);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/settings-import");
  assert.equal(calls[0][1].headers["X-AL-Token"], "abc");
  assert.equal(said[said.length - 1], "Imported 1 setting.");
  await sio.runImport(fakeFile("x", sio.MAX_BYTES + 1), env);
  assert.equal(said[said.length - 1], sio.TOO_BIG);
  await sio.runImport(fakeFile("not json"), env);
  assert.equal(said[said.length - 1], sio.NOT_JSON);
  await sio.runImport(fakeFile("[1]"), env);
  assert.equal(said[said.length - 1], sio.NOT_JSON);
  assert.equal(calls.length, 1);  // nothing sent for the refused files
});

test("settings io: export saves the download", async () => {
  const saved = [];
  const said = [];
  await sio.runExport({ token: "abc", tell: (t) => said.push(t),
    save: (b, n) => saved.push(n),
    fetch: () => Promise.resolve({ ok: true, blob: () => Promise.resolve("B") }) });
  assert.deepEqual(saved, ["ashlight-settings.json"]);
  assert.equal(said[said.length - 1], sio.SAVED);
  await sio.runExport({ token: "abc", tell: (t) => said.push(t), save: () => {},
    fetch: () => Promise.reject(new Error("down")) });
  assert.equal(said[said.length - 1], sio.OFFLINE);
});
