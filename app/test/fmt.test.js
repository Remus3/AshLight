/* TEST-WEB-FMT: web/fmt.js holds pad, duration and clock once; the five
   dashboard views alias it and keep today's forms. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const F = web.load("fmt.js");

function epoch(y, mo, d, h, mi) { return new Date(y, mo - 1, d, h, mi).getTime() / 1000; }

test("pad gives two digits below ten and the plain number above", () => {
  assert.equal(F.pad(0), "00");
  assert.equal(F.pad(7), "07");
  assert.equal(F.pad(10), "10");
  assert.equal(F.pad(123), "123");
});

test("duration: m:ss, h:mm:ss, --:-- when unknown, 0:00 below zero", () => {
  assert.equal(F.duration(0), "0:00");
  assert.equal(F.duration(65.9), "1:05");
  assert.equal(F.duration(3599), "59:59");
  assert.equal(F.duration(3600), "1:00:00");
  assert.equal(F.duration(3725), "1:02:05");
  assert.equal(F.duration(-5), "0:00");
  [null, undefined, NaN, Infinity, -Infinity].forEach((v) => {
    assert.equal(F.duration(v), "--:--", String(v));
  });
});

test("durationAbs: the size either side of zero, no empty or unknown form", () => {
  assert.equal(F.durationAbs(90), "1:30");
  assert.equal(F.durationAbs(-90), "1:30");
  assert.equal(F.durationAbs(-3725.5), "1:02:05");
  assert.equal(F.durationAbs(0.4), "0:00");
  assert.equal(F.durationAbs(null), "0:00");
  assert.notEqual(F.durationAbs(-1), "");
});

test("clock: local HH:MM of an epoch, empty when not a number", () => {
  assert.equal(F.clock(epoch(2026, 11, 16, 9, 5)), "09:05");
  assert.equal(F.clock(epoch(2026, 11, 16, 14, 30)), "14:30");
  assert.equal(F.clock(NaN), "");
  assert.equal(F.clock(undefined), "");
  assert.equal(F.clock(Infinity), "");
  assert.equal(F.hm(new Date(2026, 0, 2, 3, 4)), "03:04");
});

test("clockDated: HH:MM on the same day, the date in front for an older one", () => {
  const now = new Date(2026, 10, 16, 20, 0).getTime();
  assert.equal(F.clockDated(epoch(2026, 11, 16, 14, 5), now), "14:05");
  assert.equal(F.clockDated(epoch(2026, 11, 15, 23, 59), now), "2026-11-15 23:59");
  assert.equal(F.clockDated(epoch(2026, 2, 3, 4, 5), now), "2026-02-03 04:05");
  const today = Date.now() / 1000;
  assert.equal(F.clockDated(today), F.clock(today));
});

test("the five views alias the shared functions and keep their exports", () => {
  const acts = web.load("acts.js");
  const runs = web.load("runs.js");
  const history = web.load("history.js");
  const summary = web.load("summary.js");
  assert.equal(acts.duration, F.duration);
  assert.equal(runs.duration, F.duration);
  assert.equal(runs.clock, F.clock);
  assert.equal(history.duration, F.durationAbs);
  assert.equal(summary.clock, F.clockDated);
  assert.equal(history.deltaText(-90), "1:30 faster");
  assert.equal(history.deltaText(null), "");
  const app = web.source("app.js");
  assert.match(app, /var F = window\.ALFmt;/);
  assert.match(app, /var duration = F\.duration;/);
  assert.match(app, /var clock = F\.clock;/);
});

test("pad is defined once among the five views and fmt.js", () => {
  const re = /function pad2?\(/g;
  assert.equal((web.source("fmt.js").match(re) || []).length, 1);
  ["acts.js", "app.js", "history.js", "runs.js", "summary.js"].forEach((name) => {
    const src = web.source(name);
    assert.equal((src.match(re) || []).length, 0, name);
    assert.doesNotMatch(src, /function (duration|clock)\(/, name);
  });
});

test("no other dashboard file defines a function named pad", () => {
  const fs = require("node:fs");
  fs.readdirSync(web.dir).filter((n) => n.endsWith(".js") && n !== "fmt.js").forEach((name) => {
    assert.doesNotMatch(web.source(name), /function pad\(/, name);
  });
});

test("the strip keeps its duration form through fmt.js", () => {
  const strip = web.load("strip.js");
  assert.equal(strip.duration(3725), F.duration(3725));
  assert.equal(strip.duration(-5), "0:00");
  assert.equal(strip.duration("65"), "--:--");
  assert.equal(strip.duration(null), "--:--");
});

test("fmt.js is the page's first script and stays pure and ASCII", () => {
  const html = web.source("index.html");
  const first = /<script src="\/web\/([a-z]+)\.js" defer><\/script>/.exec(html);
  assert.ok(first);
  assert.equal(first[1], "fmt");
  const src = web.source("fmt.js");
  assert.doesNotMatch(src, /[^\x0a\x20-\x7e]/);
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["setInterval", "setTimeout", "fetch(", "XMLHttpRequest",
    "EventSource", "clipboard", "document", "innerHTML"]) {
    assert.ok(!code.includes(bad), bad);
  }
});
