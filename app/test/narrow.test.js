/* UX-NARROW: the narrow side-window order plan (web/narrow.js). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const n = require("../../web/narrow.js");

const PAGE = ["consent", "glance", "summarybox", "trades", "trade-status", "evalbox",
  "actsbox", "mapsbox", "deathsbox", "historybox", "events", "buildbox", "healthbox",
  "searchbox", "pricesbox", "watchbox", "toolsbox"];

test("narrow puts live play first and folds the tool cards at the end", () => {
  const p = n.plan(PAGE);
  assert.deepEqual(p.live, ["consent", "glance", "summarybox", "trades", "trade-status",
    "actsbox", "mapsbox", "deathsbox", "evalbox", "events"]);
  assert.deepEqual(p.tools, ["buildbox", "healthbox", "searchbox", "pricesbox", "watchbox",
    "historybox", "toolsbox"]);
  assert.deepEqual(p.rest, []);
});

test("an unknown card stays visible with the live cards, never folded", () => {
  const p = n.plan(["glance", "charpick", "buildbox"]);
  assert.deepEqual(p.rest, ["charpick"]);
  assert.deepEqual(p.tools, ["buildbox"]);
});

test("every card key the plan names exists in the page, and the script loads", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "..", "web", "index.html"), "utf8");
  const main = html.split("<main>")[1].split("</main>")[0];
  n.LIVE.concat(n.TOOLS).forEach((k) => {
    if (k === "glance") { assert.match(main, /<section class="stats"/); return; }
    if (k === "events") { assert.match(main, /<section class="card events"/); return; }
    assert.ok(main.includes("id=\"" + k + "\""), k);
  });
  assert.match(html, /<script src="\/web\/narrow.js" defer><\/script>/);
  assert.equal(n.NARROW_PX, 520);
  const css = fs.readFileSync(path.join(__dirname, "..", "..", "web", "app.css"), "utf8");
  assert.match(css, /@media \(max-width: 520px\)/);
  assert.doesNotMatch(css, /(^|[\s;{])order\s*:/m);
});
