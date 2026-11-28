// TEST-CDP-ENDPOINT-CI-WAIT (decision 0080): every CDP driver's DevTools
// endpoint poll widens 3x under AL_CI only and stops at once when Chrome
// has failed, as a11y.mjs does since TEST-A11Y-NEWEST-DEVTOOLS. Local
// bounds are 150 x 100 ms for every driver (dash_console.mjs and
// dash_perf.mjs rose from 100 when they began reading DevToolsActivePort,
// TEST-CDP-OS-PORT). Static read of the driver sources.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const DIR = path.join(__dirname, "cdp");
// driver -> its local poll count (100 ms each)
const DRIVERS = { "a11y.mjs": 150, "dash_console.mjs": 150, "dash_perf.mjs": 150,
  "play_fit.mjs": 150 };

for (const [name, local] of Object.entries(DRIVERS)) {
  const src = fs.readFileSync(path.join(DIR, name), "utf8");

  test(`${name}: endpoint poll is ${local} locally, ${local * 3} under AL_CI`, () => {
    assert.match(src, /const CI = process\.env\.AL_CI === "1";/);
    const m = src.match(/const ENDPOINT_POLLS = CI \? (\d+) : (\d+);/);
    assert.ok(m, "ENDPOINT_POLLS bound missing");
    assert.strictEqual(Number(m[2]), local);
    assert.strictEqual(Number(m[1]), local * 3);
    assert.doesNotMatch(src, /i < \d+ && !targets/, "fixed poll bound left");
    assert.match(src, /i < ENDPOINT_POLLS && !targets && chromeExit === null/);
  });

  test(`${name}: a failed Chrome exit stops the poll and is named`, () => {
    assert.match(src,
      /chrome\.on\("exit", \(code, signal\) => \{ if \(signal \|\| code\) \{ chromeExit = signal \|\| code; \} \}\);/);
    assert.match(src, /browser exited: \$\{chromeExit\}/);
  });
}
