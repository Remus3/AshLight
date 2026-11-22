"use strict";
/* OVL-LINE2-RULE (plan 03 sections 5.1 and 5.2, TD-17, budget G11): HUD
   line 2 shows one thing by one order, and always fits the plate. Rank 5,
   the zone-guide line, is OVL-LINE2-GUIDE (plan 03 section 5.4). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const fmt = require("../shared/format.js");
const gate = require("../shared/render_gate.js");

const BASE = { level: "Lv 74", deaths: "3 deaths", status: "live", log: "", trades: "",
               under: "", away: "", campaign: "" };

/* [rank, inputs, expected {level, deaths, status}] */
const TABLE = [
  [1, { status: "offline" }, { level: "Lv 74", deaths: "3 deaths", status: "offline" }],
  [1, { status: "connecting", level: "", deaths: "" }, { level: "", deaths: "", status: "connecting" }],
  [1, { log: "waiting for log", trades: "2 trades", under: "3 lv under", away: "AFK",
        campaign: "Boss: cold" }, { level: "Lv 74", deaths: "", status: "waiting for log" }],
  [1, { log: "no Client.txt" }, { level: "Lv 74", deaths: "", status: "no Client.txt" }],
  [1, { log: "log quiet" }, { level: "Lv 74", deaths: "3 deaths", status: "log quiet" }],
  [1, { log: "not reading - see dashboard", level: "", deaths: "" },
      { level: "", deaths: "", status: "not reading - see dashboard" }],
  [2, { trades: "2 trades", under: "3 lv under", away: "AFK", campaign: "Boss: cold" },
      { level: "Lv 74", deaths: "3 deaths", status: "2 trades" }],
  [3, { under: "3 lv under", away: "AFK", campaign: "Boss: cold" },
      { level: "Lv 74", deaths: "3 deaths", status: "3 lv under" }],
  [4, { away: "AFK", campaign: "Boss: cold" }, { level: "Lv 74", deaths: "3 deaths", status: "AFK" }],
  [4, { away: "DND" }, { level: "Lv 74", deaths: "3 deaths", status: "DND" }],
  [6, { campaign: "Boss: cold" }, { level: "Lv 74", deaths: "3 deaths", status: "Boss: cold" }],
  [6, { campaign: "Boots: no speed" }, { level: "Lv 74", deaths: "", status: "Boots: no speed" }],
  [6, { level: "Lv 100", deaths: "999 deaths", campaign: "Boots: no speed" },
      { level: "Lv 100", deaths: "", status: "Boots: no speed" }],
  [7, {}, { level: "Lv 74", deaths: "3 deaths", status: "" }],
  [7, { level: "Lv 100", deaths: "999 deaths" }, { level: "Lv 100", deaths: "999 deaths", status: "" }]
];

test("hudLine2: one order, first match, ranks 1 to 4, 6 and 7", () => {
  for (const [rank, inp, want] of TABLE) {
    assert.deepEqual(gate.hudLine2({ ...BASE, ...inp }), want, "rank " + rank + " " + JSON.stringify(inp));
  }
});

const GUIDE = "Find the Sacred Grove";

test("hudLine2 rank 5: the guide line stands alone and yields to ranks 1 to 4", () => {
  // due: it replaces level and deaths, and beats the campaign word (rank 6)
  assert.deepEqual(gate.hudLine2({ ...BASE, guide: GUIDE }),
                   { level: "", deaths: "", status: "", guide: GUIDE });
  assert.deepEqual(gate.hudLine2({ ...BASE, guide: GUIDE, campaign: "Boss: cold" }),
                   { level: "", deaths: "", status: "", guide: GUIDE });
  // ranks 1 to 4 win at once, and the guide is gone from the line
  const high = [{ status: "offline" }, { log: "waiting for log" }, { trades: "2 trades" },
                { under: "3 lv under" }, { away: "AFK" }];
  for (const h of high) {
    const out = gate.hudLine2({ ...BASE, guide: GUIDE, ...h });
    assert.equal(out.guide, undefined, JSON.stringify(h));
    assert.notEqual(out.status, "", JSON.stringify(h));
  }
  // a short over 34 characters is clipped to the card line limit
  assert.equal(gate.GUIDE_MAX, 34);
  const long = gate.hudLine2({ ...BASE, guide: "z".repeat(40) }).guide;
  assert.equal(long.length, 34);
  assert.ok(long.endsWith("..."));
});

const ALWAYS = { corner: "top-right", zone_guide: "always" };

function gsnap(layout, overlay, extra) {
  return Object.assign({
    zone: "The Grelwood", in_hideout: false, in_town: false, zone_entered_at: 1000,
    level: 74, deaths: 3, now: 1000, trade_requests: [],
    tailer: { consented: true, reading: true, path: "x" },
    overlay_layout: layout,
    overlay: Object.assign({ guide_short: GUIDE, calm_at: null }, overlay || {})
  }, extra || {});
}

test("rank 5 under zone_guide always: the short replaces level and deaths", () => {
  const m = gate.hudModel(gsnap(ALWAYS), 1005, "live");
  assert.equal(m.guide, GUIDE);
  assert.equal(m.level, "");
  assert.equal(m.deaths, "");
  assert.equal(m.sep, "");
  assert.equal(gate.statusText(m), "");
  assert.equal(m.hudShown, true);
  assert.ok(gate.FIELDS.includes("guide"));
  // the campaign word (rank 6) waits behind it; AFK (rank 4) beats it
  const camp = gate.hudModel(gsnap(ALWAYS, {}, { campaign: { word: "Boss: cold" } }), 1005, "live");
  assert.equal(camp.guide, GUIDE);
  assert.equal(gate.statusText(camp), "");
  const afk = gate.hudModel(gsnap(ALWAYS, {}, { afk: true }), 1005, "live");
  assert.equal(afk.guide, "");
  assert.equal(afk.level, "Lv 74");
  assert.equal(gate.statusText(afk), "AFK");
  const off = gate.hudModel(gsnap(ALWAYS), 1005, "offline");
  assert.equal(off.guide, "");
  assert.equal(gate.statusText(off), "offline");
});

test("a death or level-up brings level and deaths back for 20 s", () => {
  // calm_at = the death time + 20 s (server/al/overlayview.py CALM_S)
  const s = gsnap(ALWAYS, { calm_at: 1020 }, { deaths: 4 });
  const quiet = gate.hudModel(s, 1005, "live");
  assert.equal(quiet.guide, "");
  assert.equal(quiet.level, "Lv 74");
  assert.equal(quiet.deaths, "4 deaths");
  // the one extra wake-up: when the guide is due again
  assert.equal(gate.msUntilGuideDue(s, 1005), 15000);
  assert.equal(gate.msUntilGuideDue(s, 1019.95), 250);
  const back = gate.hudModel(s, 1020, "live");
  assert.equal(back.guide, GUIDE);
  assert.equal(back.level, "");
  assert.equal(gate.msUntilGuideDue(s, 1020), null);
  assert.ok(gate.shouldRender(quiet, back));
  assert.deepEqual(gate.changedFields(quiet, back).sort(),
                   ["deaths", "guide", "level", "sep"]);
  // no calm time: no wake-up
  assert.equal(gate.msUntilGuideDue(gsnap(ALWAYS), 1005), null);
});

test("under entry / never (or no layout) rank 5 never fires", () => {
  for (const zg of ["entry", "never", undefined, "sometimes"]) {
    const lay = { corner: "top-right" };
    if (zg !== undefined) { lay.zone_guide = zg; }
    const m = gate.hudModel(gsnap(lay), 1005, "live");
    assert.equal(m.guide, "", String(zg));
    assert.equal(m.level, "Lv 74", String(zg));
    assert.equal(m.deaths, "3 deaths", String(zg));
    assert.equal(gate.msUntilGuideDue(gsnap(lay, { calm_at: 1020 }), 1005), null, String(zg));
  }
  assert.equal(gate.hudModel(gsnap(null), 1005, "live").guide, "");
  // no short (an unguided zone, a map), a town or the hideout: no guide line
  assert.equal(gate.hudModel(gsnap(ALWAYS, { guide_short: "" }), 1005, "live").guide, "");
  assert.equal(gate.hudModel(gsnap(ALWAYS, {}, { in_town: true }), 1005, "live").guide, "");
  assert.equal(gate.hudModel(gsnap(ALWAYS, {}, { in_hideout: true }), 1005, "live").guide, "");
  assert.equal(gate.hudModel(gsnap(ALWAYS, {}, { overlay: null }), 1005, "live").guide, "");
  assert.equal(gate.hudModel(gsnap(ALWAYS, {}, { tailer: { consented: false } }), 1005,
                             "live").guide, "");
  assert.equal(gate.hudModel(null, 0).guide, "");
});

test("the zone card comes first: no guide line while it holds the slot", () => {
  const zone = { kind: "zone", head: GUIDE, line2: "Next: The Red Vale", line3: "Fits Lv 74",
                 verdict: "", expires_at: 1012 };
  const s = gsnap(ALWAYS, {}, { card: zone });
  const during = gate.hudModel(s, 1005, "live");
  assert.equal(during.evalHead, GUIDE);
  assert.equal(during.guide, "");
  assert.equal(during.level, "Lv 74");
  const after = gate.hudModel(s, 1012, "live");
  assert.equal(after.evalHead, "");
  assert.equal(after.guide, GUIDE);
  // a press card does not hide the guide line
  const press = gate.hudModel(gsnap(ALWAYS, {}, { card: { kind: "eval", head: "Keep",
    line2: "Ring", line3: "", verdict: "note", expires_at: 1020 } }), 1005, "live");
  assert.equal(press.evalHead, "Keep");
  assert.equal(press.guide, GUIDE);
});

test("the page never renders the long guide line", () => {
  // the snapshot's dashboard form (zone_guide.line, 120 characters) is never read
  const long = "x".repeat(120);
  const m = gate.hudModel(gsnap(ALWAYS, { guide_short: "" },
    { zone_guide: { kind: "campaign", short: "", line: long } }), 1005, "live");
  assert.equal(m.guide, "");
  for (const k of gate.FIELDS) { assert.ok(m[k] !== long, k); }
  const gateSrc = fs.readFileSync(path.join(__dirname, "..", "shared", "render_gate.js"), "utf8");
  const page = fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.js"), "utf8");
  for (const src of [gateSrc, page]) {
    assert.ok(!/zone_guide\s*\.\s*line|zone_guide\s*\[/.test(src));
    assert.ok(!/snap\.zone_guide/.test(src));
  }
  // the page writes the model's guide into the one guide node
  assert.match(page, /nodes\.guide\.textContent = model\.guide;/);
  const html = fs.readFileSync(path.join(__dirname, "..", "overlay", "index.html"), "utf8");
  assert.match(html, /<span id="deaths"><\/span>\s*<span id="guide" class="guide"><\/span>/);
});

test("hudLine2: level text + status word at most 26 characters, else the deaths text drops", () => {
  assert.equal(gate.LINE2_MAX, 26);
  // "Lv 74  3 deaths" is 15: an 11-character word fits (26), a 12-character one does not
  assert.equal(fmt.line2Length("Lv 74", "3 deaths", "x".repeat(11)), 26);
  assert.equal(gate.hudLine2({ ...BASE, campaign: "x".repeat(11) }).deaths, "3 deaths");
  assert.equal(gate.hudLine2({ ...BASE, campaign: "x".repeat(12) }).deaths, "");
  // every shown pair stays within the rule for the vocabulary words
  const words = ["offline", "connecting", "waiting for log", "no Client.txt", "log quiet",
                 "9 trades", "3 lv under", "AFK", "DND", "Boss: cold", "Boots: no speed",
                 "Cold res 32%"];
  for (const level of ["Lv 1", "Lv 74", "Lv 100", "Lv unknown"]) {
    for (const deaths of ["0 deaths", "1 death", "999 deaths"]) {
      for (const w of words) {
        const inp = w === "offline" || w === "connecting"
          ? { ...BASE, level, deaths, status: w } : { ...BASE, level, deaths, campaign: w };
        const out = gate.hudLine2(inp);
        assert.equal(out.status, w);
        assert.equal(out.level, level);
        assert.ok(fmt.line2Length(out.level, out.deaths, out.status) <= 26,
                  [out.level, out.deaths, out.status].join(" / "));
      }
    }
  }
});

test("hudLine2: a word over 20 characters stands alone, at most 27", () => {
  assert.equal(gate.WORD_BESIDE_MAX, 20);
  assert.equal(gate.WORD_ALONE_MAX, 27);
  assert.deepEqual(gate.hudLine2({ ...BASE, campaign: "x".repeat(20) }),
                   { level: "Lv 74", deaths: "", status: "x".repeat(20) });
  // design review L2-1: "Lv unknown" + a 20-character word is 30: the word stands alone
  assert.deepEqual(gate.hudLine2({ ...BASE, level: "Lv unknown", campaign: "x".repeat(20) }),
                   { level: "", deaths: "", status: "x".repeat(20) });
  assert.deepEqual(gate.hudLine2({ ...BASE, level: "Lv unknown", campaign: "x".repeat(16) }),
                   { level: "Lv unknown", deaths: "", status: "x".repeat(16) });
  assert.deepEqual(gate.hudLine2({ ...BASE, log: "not reading - see dashboard" }),
                   { level: "", deaths: "", status: "not reading - see dashboard" });
  const long = gate.hudLine2({ ...BASE, status: "y".repeat(40) });
  assert.equal(long.level, "");
  assert.equal(long.deaths, "");
  assert.equal(long.status.length, 27);
  assert.ok(long.status.endsWith("..."));
  // statusText prints the same word the rule picked
  assert.equal(gate.statusText({ ...BASE, status: "y".repeat(40) }), long.status);
});

test("hudLine2 is pure: the input is not changed", () => {
  const inp = { ...BASE, campaign: "Boots: no speed" };
  const copy = { ...inp };
  gate.hudLine2(inp);
  assert.deepEqual(inp, copy);
  assert.deepEqual(gate.hudLine2(null), { level: "", deaths: "", status: "" });
});

test("no timer added: overlay.js keeps one setTimeout call site", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "overlay", "overlay.js"), "utf8");
  assert.equal((src.match(/setTimeout\s*\(/g) || []).length, 1);
  // OVL-LINE2-GUIDE: the guide wake-up folds into schedule()'s one timer
  const sched = src.slice(src.indexOf("function schedule()"), src.indexOf("function reportGate()"));
  assert.match(sched, /var guideMs = S\.msUntilGuideDue\(snap, now\);/);
  assert.match(sched, /if \(guideMs !== null && \(ms === null \|\| guideMs < ms\)\) \{ ms = guideMs; \}/);
  for (const f of ["render_gate.js", "format.js"]) {
    const s = fs.readFileSync(path.join(__dirname, "..", "shared", f), "utf8");
    assert.equal((s.match(/setTimeout\s*\(|setInterval\s*\(/g) || []).length, 0, f);
  }
});
