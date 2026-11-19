/* UX-REGRESSION-SWEEP (AREA-UX b10): one message per cause, no
   contradiction between cards. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const tc = web.load("tc.js");
const hist = web.load("history.js");

test("a not-checked item (no build) has no 'not counted' note", () => {
  const m = tc.evalView({ ok: false, error: "no build loaded", unweighted: ["Cannot be Frozen"],
    text: { sentence: "No build loaded yet.", item: "Grim Clutch" } });
  assert.equal(m.word, "Not checked");
  assert.equal(m.unweighted, "");
  const ok = tc.evalView({ ok: true, verdict: "upgrade", unweighted: ["Cannot be Frozen"],
    text: { sentence: "Upgrade.", item: "Grim Clutch" } });
  assert.match(ok.unweighted, /^Not counted \(no weight yet\): Cannot be Frozen\./);
});

test("run history: this run's own best act says 'best so far', not 'not yet'", () => {
  const rows = hist.bestRows({ best: [
    { key: "G1", label: "Act 1", best_s: 600, best_text: "10:00", delta_s: null, this_run: true },
    { key: "G2", label: "Act 2", best_s: 900, best_text: "15:00", delta_s: null },
    { key: "G3", label: "Act 3", best_s: 700, best_text: "11:40", delta_s: 90 }] });
  assert.deepEqual(rows.map((r) => r.delta), ["best so far", "", "1:30 slower"]);
});
