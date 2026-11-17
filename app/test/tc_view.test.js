"use strict";
/* TC-VIEW / TC-EVAL-UI / GFX-ADVISOR: the dashboard's pure view helpers in
   web/tc.js. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const v = require("../../web/tc.js");

const BUILD = {
  loaded: true, code: "eNabc",
  build: {
    class_name: "Monk", ascendancy: "Invoker", level: 87, main_skill_index: 1,
    stats: { Life: 2410, EnergyShield: 1830.5, TotalDPS: 123456.78, FireResist: 75,
             Spirit: "not-a-number", SomethingElse: 3 },
    tree: { title: "Endgame", tree_version: "0_3", node_count: 6,
            url: "https://example.org/tree/endgame", jewels: { 40: 3 } },
    gear: { "Gloves": { rarity: "RARE", name: "Doom Grip", base: "Example Gloves", text: "Rarity: RARE\nDoom Grip" },
            "Weapon 1": { rarity: "UNIQUE", name: "Example Unique", base: "Example Quarterstaff", text: "" } },
    skills: [{ enabled: true, slot: "Weapon 1", label: "Main",
               gems: [{ name: "Example Strike", level: 19, quality: 20, enabled: true },
                      { name: "Example Support", level: 1, quality: 0, enabled: false }] },
             { enabled: false, slot: null, label: null,
               gems: [{ name: "Example Aura", level: 15, quality: 0, enabled: true }] }],
    notes: "  Some notes  "
  }
};

test("build view: header, live level, key stats in order", () => {
  const m = v.buildView(BUILD, { level: 64, zone: "Clearfell" });
  assert.equal(m.title, "Monk - Invoker");
  assert.equal(m.levelLine, "Planned at level 87.");
  assert.equal(m.you, "You are level 64 in Clearfell.");
  assert.deepEqual(m.stats, [
    { label: "Life", value: "2,410" }, { label: "Energy shield", value: "1,831" },
    { label: "Total DPS", value: "123,457" }, { label: "Fire resistance", value: "75%" }]);
  assert.equal(m.notes, "Some notes");
  assert.equal(m.code, "eNabc");
  assert.equal(v.buildView(BUILD, null).you, "");
  assert.equal(v.buildView(BUILD, { level: null, zone: "Clearfell" }).you, "You are in Clearfell.");
});

test("build view: gear in slot order, links only for uniques", () => {
  const m = v.buildView(BUILD, null);
  assert.deepEqual(m.gear.map((g) => g.slot), ["Weapon 1", "Gloves"]);
  assert.equal(m.gear[0].name, "Example Unique");
  assert.equal(m.gear[0].rarity, "Unique");
  assert.deepEqual(m.gear[0].links.map((l) => l.href),
    ["https://poe2db.tw/us/Example_Unique", "https://www.poe2wiki.net/wiki/Example_Unique"]);
  assert.deepEqual(m.gear[1].links, []);
  assert.equal(m.gear[1].base, "Example Gloves");
});

test("build view: skills, gems and tree summary", () => {
  const m = v.buildView(BUILD, null);
  assert.equal(m.skills[0].label, "Main");
  assert.equal(m.skills[0].main, true);
  assert.equal(m.skills[0].gems[0].detail, "level 19, 20% quality");
  assert.equal(m.skills[0].gems[1].detail, "level 1, off");
  assert.equal(m.skills[1].label, "Example Aura");
  assert.deepEqual(m.skills[0].gems[0].links.map((l) => l.label), ["poe2db"]);
  assert.equal(m.skills[1].enabled, false);
  assert.equal(m.tree.line, "Endgame: 6 points allocated (tree 0_3)");
  assert.equal(m.tree.url, "https://example.org/tree/endgame");
});

test("build view: empty and hostile values", () => {
  const e = v.buildView({ loaded: false, build: null }, null);
  assert.equal(e.loaded, false);
  assert.match(e.empty, /^No build yet\./);
  const odd = v.buildView({ loaded: true, build: { class_name: null, level: null,
    tree: { node_count: 1, url: "javascript:alert(1)" }, gear: {}, skills: [], stats: {} } }, null);
  assert.equal(odd.title, "Class unknown");
  assert.equal(odd.levelLine, "Planned at level unknown.");
  assert.equal(odd.tree.url, "");
  assert.equal(odd.tree.line, "Passive tree: 1 point allocated");
  assert.ok(!/undefined|null|NaN/.test(JSON.stringify(odd)));
});

test("paste answers are plain and say what to do", () => {
  assert.deepEqual(v.pasteResult(200, { loaded: true, build: { class_name: "Monk", level: 87 } }),
    { ok: true, text: "Loaded: Monk, level 87." });
  assert.match(v.pasteResult(400, { error: "bad base64" }).text, /Your last build stays loaded\.$/);
  assert.match(v.pasteResult(422, {}).text, /^AshLight can't open that link\./);
  assert.equal(v.pasteResult(422, { hosts: ["pobb.in", "pastebin.com"] }).text,
    "AshLight can't open that link. It opens links from pobb.in and pastebin.com only. Or paste the build code instead.");
  assert.equal(v.pasteResult(422, { web_data: false }).text,
    "Build links need web data, which is off. Turn it on under Prices and web data, or paste the build code instead.");
  assert.match(v.pasteResult(502, {}).text, /^The build link isn't loading\./);
  assert.equal(v.pasteResult(500, null).text, "Not loaded. Try again.");
  for (const s of [400, 413, 422, 500, 502]) {
    assert.ok(!/HTTP|token|core|!/.test(v.pasteResult(s, {}).text));
  }
});

test("eval view uses the core's words; empty is null", () => {
  assert.equal(v.evalView(null), null);
  const ev = { id: 3, ok: true, verdict: "upgrade", at: 0, unweighted: ["+# to Example"],
               text: { sentence: "Upgrade: 47.5 points more than your Ring 1 (Weak Loop).",
                       item: "Storm Loop", comparisons: [{ slot: "Ring 1", sentence: "s", stats: [] }] } };
  const m = v.evalView(ev, () => "14:05");
  assert.equal(m.word, "Upgrade");
  assert.equal(m.state, "done");
  assert.equal(m.when, "Checked at 14:05");
  assert.equal(m.comparisons.length, 1);
  assert.equal(m.unweighted,
    "Not counted (no weight yet): +N to Example. Add a weight under Stat weights to count them.");
  const err = v.evalView({ ok: false, error: "no build loaded", text: { sentence: "No build loaded yet." } });
  assert.equal(err.word, "Not checked");
  assert.deepEqual(err.comparisons, []);
});

test("weights: rows sorted; the PUT document drops blanks", () => {
  assert.deepEqual(v.weightRows({ weights: { b: 1, "+#% to A": 2 } }),
    [{ key: "+#% to A", label: "+N% to A", weight: 2 }, { key: "b", label: "b", weight: 1 }]);
  assert.equal(v.toKey(" +N% to Fire Resistance "), "+#% to Fire Resistance");
  assert.equal(v.toKey("Adds N to N Cold Damage"), "Adds # to # Cold Damage");
  assert.equal(v.toKey("Nearby Enemies"), "Nearby Enemies");
  assert.deepEqual(v.weightRows(null), []);
  assert.deepEqual(v.weightsDoc([{ key: " +# to maximum Life ", value: "1.5" }, { key: "x", value: "" },
                                 { key: "", value: "3" }], "2", "abc"),
    { weights: { "+# to maximum Life": 1.5 }, sidegrade: { abs: 2, pct: 5 } });
});

test("graphics view: hardware lines, advice, failure text", () => {
  const doc = { ok: true, hardware: { cpu: { name: "Example CPU", cores: 6, threads: 12 },
                ram_gb: 16, gpu: { name: "Example GPU", vram_gb: 8 },
                display: { width: 1920, height: 1080, refresh_hz: 144 } },
                advice: { tier_text: "Balanced", settings: [{ setting: "Display Mode",
                  value: "Windowed Fullscreen", why: "x" }], warnings: [] } };
  const m = v.gfxView(doc);
  assert.deepEqual(m.hardware, [
    { label: "Processor", value: "Example CPU (6 cores, 12 threads)" },
    { label: "Graphics card", value: "Example GPU (8 GB)" },
    { label: "Memory", value: "16 GB" },
    { label: "Screen", value: "1920x1080 at 144 Hz" }]);
  assert.equal(m.settings[0].value, "Windowed Fullscreen");
  const bad = v.gfxView({ ok: false, error: "AshLight could not read this computer's hardware.",
                          hardware: null, advice: { settings: [] } });
  assert.equal(bad.error, "AshLight could not read this computer's hardware. These are safe middle settings.");
  assert.deepEqual(bad.hardware, []);
});
