"use strict";
/* TC-VIEW / TC-EVAL-UI / GFX-ADVISOR: the dashboard's pure view helpers in
   web/tc.js. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const v = web.load("tc.js");

const BUILD = {
  loaded: true, code: "eNabc",
  build: {
    class_name: "Monk", ascendancy: "Invoker", level: 87, main_skill_index: 1,
    stats: { Life: 2410, EnergyShield: 1830.5, TotalDPS: 123456.78, FireResist: 75,
             Spirit: "not-a-number", SomethingElse: 3 },
    tree: { title: "Endgame", tree_version: "0_3", node_count: 6,
            url: "https://www.pathofexile.com/passive-skill-tree/endgame", jewels: { 40: 3 } },
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
  assert.equal(m.tree.url, "https://www.pathofexile.com/passive-skill-tree/endgame");
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
    { ok: true, offer: "", text: "Loaded: Monk, level 87." });
  assert.match(v.pasteResult(400, { error: "bad base64" }).text, /Your last build stays loaded\.$/);
  assert.match(v.pasteResult(422, {}).text, /^AshLight can't open that link\./);
  assert.equal(v.pasteResult(422, { hosts: ["pobb.in", "pastebin.com"] }).text,
    "AshLight can't open that link. It opens links from pobb.in and pastebin.com only. Or paste the build code instead.");
  assert.equal(v.pasteResult(422, { web_data: false }).text,
    "Build links need web data, which is off. Use the button below to turn it on, or paste the build code instead.");
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
    "Not counted (no weight yet): +N to Example. Add a weight under Stat weights (Items and prices tab) to count them.");
  assert.equal(m.calc, "");
  const err = v.evalView({ ok: false, error: "no build loaded", text: { sentence: "No build loaded yet." } });
  assert.equal(err.word, "Not checked");
  assert.deepEqual(err.comparisons, []);
});

test("eval view: TC-DELTA calc line and the PoB uncounted wording", () => {
  const off = v.evalView({ id: 1, ok: true, verdict: "upgrade", at: 0,
    calc: { source: "weights", notice: "off" },
    text: { sentence: "s", item: "i", comparisons: [], calc: "Scored with your stat weights." } });
  assert.equal(off.calc, "Scored with your stat weights.");
  const pob = v.evalView({ id: 2, ok: true, verdict: "downgrade", at: 0,
    calc: { source: "pob", notice: null }, unweighted: ["Cannot be Example Frozen"],
    text: { sentence: "s", item: "i", comparisons: [],
            calc: "Path of Building: this item in Gloves replaces Old Grip. DPS -36% (from 100 to 64). EHP +12.7% (from 4720 to 5320)." } });
  assert.match(pob.calc, /^Path of Building: this item in Gloves replaces Old Grip. DPS -36%/);
  assert.equal(pob.unweighted, "Not counted (the mod has no number): Cannot be Example Frozen.");
  assert.equal(v.evalView({ id: 3, ok: true, at: 0, text: { calc: 5 } }).calc, "");
});

test("eval view: MATH-WEIGHTS cached Path of Building weights wording", () => {
  const c = v.evalView({ id: 4, ok: true, verdict: "upgrade", at: 0,
    calc: { source: "pob_cached", notice: "off" }, unweighted: ["+# to Example"],
    text: { sentence: "s", item: "i", comparisons: [], calc: "Scored with the stat weights." } });
  assert.equal(c.unweighted,
    "Not counted (Path of Building has not measured these for this build yet): +N to Example.");
  assert.equal(c.calc, "Scored with the stat weights.");
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

/* MATH-POTENTIAL-UI: the score now against the worst and best rolls. */
test("eval view: roll potential line, worst / now / best", () => {
  const base = { id: 5, ok: true, verdict: "upgrade", at: 0,
                 text: { sentence: "s", item: "i", comparisons: [] } };
  const m = v.evalView(Object.assign({}, base,
    { potential: { score: 58.04, worst: 30, best: 84.5, pct: 51.4 } }));
  assert.equal(m.rolls,
    "Rolls: worth 58 points now, 30 at the worst and 84.5 at the best, so 51% of the way up.");
  const top = v.evalView(Object.assign({}, base,
    { potential: { score: 1234.4, worst: 1000, best: 1234.4, pct: 100 } }));
  assert.equal(top.rolls, "Rolls: worth 1,234 points now, the best these rolls can be.");
  assert.equal(v.evalView(base).rolls, "");
  assert.equal(v.evalView(Object.assign({}, base, { potential: null })).rolls, "");
  // no spread: the rolls don't move the score, so nothing to say
  assert.equal(v.evalView(Object.assign({}, base,
    { potential: { score: 10, worst: 10, best: 10, pct: 100 } })).rolls, "");
  for (const bad of [{ score: "5", worst: 1, best: 9, pct: 50 },
                     { score: 5, worst: NaN, best: 9, pct: 50 },
                     { score: 5, worst: 1, best: Infinity, pct: 50 },
                     { score: 5, worst: 9, best: 1, pct: 50 }]) {
    assert.equal(v.evalView(Object.assign({}, base, { potential: bad })).rolls, "",
                 JSON.stringify(bad));
  }
  // a failed check never shows rolls
  assert.equal(v.evalView(Object.assign({}, base, { ok: false,
    potential: { score: 5, worst: 1, best: 9, pct: 50 } })).rolls, "");
  // pct missing or junk is computed from the three numbers
  assert.equal(v.evalView(Object.assign({}, base,
    { potential: { score: 5, worst: 0, best: 10, pct: "x" } })).rolls,
    "Rolls: worth 5 points now, 0 at the worst and 10 at the best, so 50% of the way up.");
});

test("eval view: UTIL-WAYSTONE word and no uncounted line", () => {
  const text = { sentence: "Tier 15 waystone. Risky for this build: monster critical hits.",
                 item: "Doom Trail", comparisons: [] };
  const risky = v.evalView({ id: 9, ok: false, error: "no gear slot for this item class", at: 0,
    unweighted: ["Monsters have #% increased Critical Hit Chance"], text: text,
    waystone: { tier: 15, risky: [{ id: "monster_crit", label: "monster critical hits" }] } });
  assert.equal(risky.word, "Risky");
  assert.equal(risky.verdict, "risky");
  assert.equal(risky.unweighted, "");
  assert.equal(risky.sentence, text.sentence);
  const calm = v.evalView({ id: 10, ok: false, at: 0, text: text, waystone: { risky: [] } });
  assert.equal(calm.word, "No risky mods");
  assert.equal(calm.rewards, "");
  const paid = v.evalView({ id: 13, ok: false, at: 0, waystone: { risky: [] },
    text: Object.assign({ rewards: "Rewards: +38% item rarity." }, text) });
  assert.equal(paid.rewards, "Rewards: +38% item rarity.");
  assert.equal(v.evalView({ id: 14, ok: true, at: 0, verdict: "upgrade",
    text: Object.assign({ rewards: "Rewards: +1% item rarity." }, text) }).rewards, "");
  const unid = v.evalView({ id: 11, ok: false, at: 0, text: text,
    waystone: { unidentified: true, risky: [] } });
  assert.equal(unid.word, "Unidentified");
  assert.equal(v.evalView({ id: 12, ok: false, at: 0, text: text, waystone: null }).word,
    "Not checked");
});

test("buildFileView summarises the .build download and keeps the core's notes", () => {
  assert.equal(v.buildFileView(null).ready, false);
  assert.equal(v.buildFileView({ loaded: false, build_file: { filename: "x.build" } }).ready, false);
  const f = v.buildFileView({ loaded: true, build_file: {
    filename: "ashlight-Titan-level-90.build", passives: 1, skills: 3, slots: 0,
    notes: ["2 gems left out: no game id in the build.", 7, ""] } });
  assert.equal(f.ready, true);
  assert.equal(f.filename, "ashlight-Titan-level-90.build");
  assert.equal(f.summary, "Holds 1 passive, 3 skills.");
  assert.deepEqual(f.notes, ["2 gems left out: no game id in the build."]);
  const empty = v.buildFileView({ loaded: true, build_file: { filename: "a.build" } });
  assert.equal(empty.summary, "Holds the build's name only.");
  assert.deepEqual(empty.notes, []);
});

/* TC-CARD-PARTS-WEB: the core's notes, word and tone (state.eval_card_text). */
test("eval view: notes are strings only, at most 4, in the core's order", () => {
  const m = v.evalView({ id: 20, ok: true, verdict: "upgrade", at: 0,
    text: { sentence: "s", item: "i", comparisons: [],
            notes: ["One.", 7, null, "", "  ", { a: 1 }, "Two.", "Three.", "Four.", "Five."] } });
  assert.deepEqual(m.notes, ["One.", "Two.", "Three.", "Four."]);
  assert.deepEqual(v.evalView({ id: 21, ok: true, verdict: "upgrade", at: 0,
    text: { sentence: "s", notes: "not a list" } }).notes, []);
});

test("eval view: the core's word and tone override the local word", () => {
  const m = v.evalView({ id: 22, ok: true, verdict: "upgrade", at: 0,
    text: { sentence: "s", item: "i", comparisons: [], word: "Not checked", tone: "note" } });
  assert.equal(m.word, "Not checked");
  assert.equal(m.verdict, "note");
  assert.equal(m.state, "pending");
  const ws = v.evalView({ id: 23, ok: false, at: 0, waystone: { risky: [] },
    text: { sentence: "s", word: "Risky", tone: "risky" } });
  assert.equal(ws.word, "Risky");
  assert.equal(ws.verdict, "risky");
  assert.equal(ws.state, "blocked");
  // a word alone keeps the local tone; an unknown or empty tone is ignored
  const w = v.evalView({ id: 24, ok: true, verdict: "sidegrade", at: 0,
    text: { sentence: "s", word: "Sidegrade", tone: "glow" } });
  assert.equal(w.verdict, "sidegrade");
  assert.equal(v.evalView({ id: 25, ok: true, verdict: "upgrade", at: 0,
    text: { sentence: "s", tone: "" } }).verdict, "upgrade");
  // a blank or non-string word keeps the local word
  for (const bad of ["", "   ", 5, null]) {
    assert.equal(v.evalView({ id: 26, ok: true, verdict: "downgrade", at: 0,
      text: { sentence: "s", word: bad } }).word, "Downgrade", String(bad));
  }
});

test("eval view: an eval without notes, word or tone renders as before", () => {
  const ev = { id: 27, ok: true, verdict: "upgrade", at: 0, unweighted: [],
               text: { sentence: "Upgrade: 47.5 points more.", item: "Storm Loop", comparisons: [] } };
  const m = v.evalView(ev, () => "14:05");
  assert.deepEqual(m.notes, []);
  assert.equal(m.word, "Upgrade");
  assert.equal(m.verdict, "upgrade");
  assert.equal(m.state, "done");
  assert.equal(m.sentence, "Upgrade: 47.5 points more.");
  assert.equal(m.when, "Checked at 14:05");
});

/* TC-LINK-RECOVER (F-117, decision 0013): two clicks, nothing without the confirm. */
function fakePost(answers) {
  const calls = [];
  const post = (p, body) => {
    calls.push([p, body]);
    const a = answers[p];
    return a instanceof Error ? Promise.reject(a) : Promise.resolve(a);
  };
  return { calls, post };
}

const tick = () => new Promise((r) => setImmediate(r));

test("link recover: the web-data refusal carries the button; others do not", () => {
  const r = v.pasteResult(422, { web_data: false });
  assert.equal(r.ok, false);
  assert.equal(r.offer, "Turn on web data and load this link");
  assert.match(r.offer, /web data/); // the label names the switch (floor audit L3)
  for (const [s, b] of [[422, {}], [422, { hosts: ["pobb.in"] }], [502, {}], [400, {}],
                        [413, {}], [500, null], [200, { loaded: true, build: {} }]]) {
    assert.equal(v.pasteResult(s, b).offer, "", String(s));
  }
});

test("link recover: the first click posts nothing and shows the opt-in sentence", async () => {
  const f = fakePost({});
  const rec = v.linkRecover("https://pobb.in/abc", f.post);
  assert.equal(rec.step(), "offer");
  assert.equal(rec.confirm(), null); // no confirm before the sentence is shown
  const shown = rec.open();
  assert.equal(shown.sentence, v.WEB_DATA_OPT_IN);
  assert.equal(shown.confirm, "Turn on web data");
  assert.equal(shown.cancel, "Not now");
  assert.equal(rec.step(), "confirm");
  assert.equal(rec.open(), null);
  await tick();
  assert.deepEqual(f.calls, []);
  rec.cancel();
  assert.equal(rec.step(), "offer");
  await tick();
  assert.deepEqual(f.calls, []);
});

test("link recover: the confirm click posts the opt-in, then the same code once", async () => {
  const f = fakePost({ "/api/web-data": { status: 200, body: { web_data: true } },
                       "/api/build-code": { status: 200,
                         body: { loaded: true, build: { class_name: "Monk", level: 87 } } } });
  const rec = v.linkRecover("https://pobb.in/abc", f.post);
  rec.open();
  const going = rec.confirm();
  assert.equal(rec.confirm(), null); // a second click while busy does nothing
  const out = await going;
  assert.deepEqual(f.calls, [["/api/web-data", { enabled: true }],
                             ["/api/build-code", { code: "https://pobb.in/abc" }]]);
  assert.equal(out.saved, true);
  assert.deepEqual(out.web, { web_data: true });
  assert.deepEqual(out.result, { ok: true, offer: "", text: "Loaded: Monk, level 87." });
  assert.equal(rec.step(), "done");
  assert.equal(rec.confirm(), null);
  assert.equal(rec.open(), null);
  await tick();
  assert.equal(f.calls.length, 2);
});

test("link recover: a refused load after the opt-in is not offered again", async () => {
  const f = fakePost({ "/api/web-data": { status: 200, body: { web_data: true } },
                       "/api/build-code": { status: 422, body: { web_data: false } } });
  const rec = v.linkRecover("https://pobb.in/abc", f.post);
  rec.open();
  const out = await rec.confirm();
  assert.equal(out.result.offer, "");
  assert.equal(out.result.ok, false);
  assert.equal(f.calls.length, 2);
});

test("link recover: no code is posted unless the opt-in is saved", async () => {
  for (const ans of [{ status: 500, body: null }, { status: 200, body: { web_data: false } },
                     new Error("offline")]) {
    const f = fakePost({ "/api/web-data": ans });
    const rec = v.linkRecover("https://pobb.in/abc", f.post);
    rec.open();
    const out = await rec.confirm();
    assert.equal(out.saved, false);
    assert.equal(out.web, null);
    assert.match(out.result.text, /^Web data is still off/);
    assert.ok(!/HTTP|token|core|!/.test(out.result.text));
    assert.deepEqual(f.calls, [["/api/web-data", { enabled: true }]]);
    assert.equal(rec.step(), "confirm"); // the player may confirm again
  }
});

test("link recover: the opt-in sentence is one constant, and index.html holds it", () => {
  const html = web.source("index.html", "ascii");
  const m = /<p id="webdata-sentence"[^>]*>([\s\S]*?)<\/p>/.exec(html);
  assert.ok(m, "Settings sentence #webdata-sentence");
  assert.equal(m[1].replace(/\s+/g, " ").trim(), v.WEB_DATA_OPT_IN);
  // the button labels in the page are the controller's labels
  for (const [id, label] of [["link-offer", v.LINK_OFFER], ["link-yes", v.LINK_CONFIRM],
                             ["link-no", v.LINK_CANCEL]]) {
    const b = new RegExp("<button id=\"" + id + "\"[^>]*>([^<]*)</button>").exec(html);
    assert.ok(b, id);
    assert.equal(b[1].trim(), label);
  }
  // the notes list sits inside #eval-body, read with the verdict
  const body = /<div id="eval-body"[^>]*>([\s\S]*?)<\/div>/.exec(html);
  assert.ok(body && /<ul id="eval-notes"/.test(body[1]));
});
