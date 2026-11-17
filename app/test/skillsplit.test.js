"use strict";
/* MATH-SKILL-SPLIT: damage by skill on the Build card (web/skillsplit.js)
   and MATH-DEF-BREAKDOWN: defence and sustain in Build health
   (web/health.js defView). The core sends PoB's own numbers; these files
   only list them. Fixture values are invented. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const sp = require("../../web/skillsplit.js");
const h = require("../../web/health.js");

const WEB = path.join(__dirname, "..", "..", "web");

function doc(split) { return { loaded: true, skill_split: split }; }

test("rows show name, count, part, DPS and share", () => {
  const v = sp.view(doc({
    skills: [
      { name: "Ice Shot", count: null, part: null, dps: 26519.97, share: 0.7464 },
      { name: "Snipe", count: 2, part: "Full charge", dps: 9002.1, share: 0.2533 },
      { name: "Best Ignite DPS", count: null, part: null, dps: 9.87, share: 0.0003 }],
    ailments: [{ id: "IgniteDPS", label: "Ignite", dps: 9.87 },
      { id: "TotalDotDPS", label: "All damage over time", dps: 9.87 },
      { id: "ImpaleDPS", label: "Impale", dps: 120 }]
  }));
  assert.equal(v.show, true);
  assert.deepEqual(v.rows.map((r) => r.name),
    ["Ice Shot", "2 x Snipe (Full charge)", "Best Ignite DPS"]);
  assert.equal(v.rows[0].text, "26,520 DPS, 75%");
  assert.equal(v.rows[2].text, "9.9 DPS, under 1%");
  assert.equal(v.ailments, "Damage over time, per second: Ignite 9.9. All together: 9.9. " +
    "Impale: 120 per second.");
  const only = sp.view(doc({ skills: [], ailments: [
    { id: "TotalDotDPS", label: "All damage over time", dps: 50 }] }));
  assert.equal(only.ailments, "Damage over time, per second: 50.");
  assert.equal(v.more, "");
});

test("more than the row cap folds into one line", () => {
  const skills = [];
  for (let i = 0; i < sp.MAX_ROWS + 2; i++) {
    skills.push({ name: "S" + i, dps: 100 - i, share: 0.1 });
  }
  const v = sp.view(doc({ skills: skills, ailments: [] }));
  assert.equal(v.rows.length, sp.MAX_ROWS);
  assert.equal(v.more, "2 more skills in Path of Building.");
});

test("nothing to show hides the block; bad rows dropped", () => {
  assert.equal(sp.view(null).show, false);
  assert.equal(sp.view({ loaded: false, skill_split: { skills: [] } }).show, false);
  assert.equal(sp.view(doc({ skills: [], ailments: [] })).show, false);
  const v = sp.view(doc({ skills: [{ name: "", dps: 5, share: 1 },
    { name: "X", dps: Infinity, share: 1 }, { name: "Y", dps: 0, share: 0 }],
    ailments: [{ label: "Bleed", dps: 0 }, { label: "Poison", dps: NaN }] }));
  assert.equal(v.show, false);
});

test("defence rows follow PoB's digits and units; hint only with the calc off", () => {
  const base = { loaded: true, health: { loaded: true, has_stats: true, calc_on: false,
    warnings: [], values: [], defence: [
      { id: "ManaPerSecondCost", label: "Mana cost per second", value: 85.5036, unit: "",
        digits: 1 },
      { id: "Bad", label: "Bad", value: "x", unit: "", digits: 0 }] } };
  const off = h.defView(base);
  assert.deepEqual(off.rows, [{ label: "Mana cost per second", text: "85.5" }]);
  assert.equal(off.hint, h.NO_CALC);
  base.health.calc_on = true;
  base.health.defence.push({ id: "IgniteAvoidChance", label: "Ignite avoid chance",
    value: 30, unit: "%", digits: 0 });
  const on = h.defView(base);
  assert.equal(on.hint, "");
  assert.equal(on.rows[1].text, "30%");
  assert.deepEqual(h.defView(null), { rows: [], hint: "" });
});

test("scripts load, blocks exist, no live region, no timers or network", () => {
  const html = fs.readFileSync(path.join(WEB, "index.html"), "ascii");
  assert.ok(html.indexOf("/web/skillsplit.js") > 0);
  const card = html.split("id=\"buildbox\"")[1].split("</section>")[0];
  for (const id of ["split-wrap", "split-list", "split-more", "split-ailments"]) {
    assert.ok(card.indexOf("id=\"" + id + "\"") > 0, id);
  }
  const health = html.split("id=\"healthbox\"")[1].split("</section>")[0];
  for (const id of ["def-wrap", "def-list", "def-hint"]) {
    assert.ok(health.indexOf("id=\"" + id + "\"") > 0, id);
  }
  const split = html.split("id=\"split-wrap\"")[1].split("</div>")[0];
  assert.ok(split.indexOf("aria-live") < 0);
  const src = fs.readFileSync(path.join(WEB, "skillsplit.js"), "ascii");
  assert.ok(!/setInterval|setTimeout|fetch\(|XMLHttpRequest|aria-live|innerHTML/.test(src));
  assert.ok((html.match(/aria-live/g) || []).length <= 12);
});
