"use strict";
/* OVL-LINE2-RULE (plan 03 sections 5.1 and 5.2, TD-17, budget G11): HUD
   line 2 shows one thing by one order, and always fits the plate. Rank 5
   (the zone-guide line) lands with OVL-LINE2-GUIDE. */
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
  // rank 5 is reserved: no guide input is read yet
  assert.deepEqual(gate.hudLine2({ ...BASE, guide: "Find the Sacred Grove" }),
                   { level: "Lv 74", deaths: "3 deaths", status: "" });
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
  for (const f of ["render_gate.js", "format.js"]) {
    const s = fs.readFileSync(path.join(__dirname, "..", "shared", f), "utf8");
    assert.equal((s.match(/setTimeout\s*\(|setInterval\s*\(/g) || []).length, 0, f);
  }
});
