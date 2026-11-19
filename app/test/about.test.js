"use strict";
/* TC-SNAP-UI: the game-data credit (decision 0009) in the overlay About
   (app/about.js) and the dashboard footer (web/status.js dataCreditText).
   Shown only when /api/version carries data_credit; the non-affiliation
   line always stays first. */
const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const about = require("../about.js");
const web = require("./_web.js");
const dash = web.load("status.js");

const DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way.";
const CREDIT = "Game data (c) Grinding Gear Games. Item, mod and stat data comes from the " +
  "RePoE fork community export (repoe-fork). Trade search stat ids are " +
  "Grinding Gear Games' trade site data, passed on by repoe-fork. Ids it lacks come from " +
  "Path of Building Community (PoE2, MIT license) when its optional calc files " +
  "are installed. Passive tree data comes from " +
  "Grinding Gear Games' public skill tree export. AshLight downloaded all of it to " +
  "this computer when it was built.";
const WITH = { name: "AshLight", version: "0.1.0", disclaimer: DISCLAIMER,
               data_credit: { attribution: CREDIT + " " + DISCLAIMER, credit: CREDIT } };
const WITHOUT = { name: "AshLight", version: "0.1.0", disclaimer: DISCLAIMER, data_credit: null };

test("overlay About: disclaimer alone without snapshot data", () => {
  assert.equal(about.creditOf(WITHOUT), "");
  assert.equal(about.creditOf(null), "");
  assert.equal(about.creditOf({}), "");
  assert.equal(about.creditOf({ data_credit: { credit: 5 } }), "");
  assert.equal(about.aboutText(DISCLAIMER, ""), DISCLAIMER);
});

test("overlay About: disclaimer first, then the credit, exact text", () => {
  assert.equal(about.creditOf(WITH), CREDIT);
  assert.equal(about.aboutText(DISCLAIMER, about.creditOf(WITH)), DISCLAIMER + "\n\n" + CREDIT);
  assert.equal(about.creditOf({ data_credit: { credit: "x".repeat(2000) } }).length,
               about.MAX_CREDIT_CHARS);
});

test("dashboard footer credit: exact text, empty without snapshot data", () => {
  assert.equal(dash.dataCreditText(WITH), CREDIT);
  assert.equal(dash.dataCreditText(WITHOUT), "");
  assert.equal(dash.dataCreditText(null), "");
  assert.equal(dash.dataCreditText({ data_credit: {} }), "");
});

test("getVersion sends the token and parses the document", async () => {
  let seen = null;
  const srv = http.createServer((req, res) => {
    seen = { path: req.url, method: req.method, token: req.headers["x-al-token"] };
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(WITH));
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  try {
    const get = about.makeGetVersion(http, srv.address().port, () => "tok");
    const doc = await get();
    assert.deepEqual(seen, { path: "/api/version", method: "GET", token: "tok" });
    assert.equal(about.creditOf(doc), CREDIT);
  } finally {
    srv.close();
  }
});

test("getVersion rejects a refused token (no credit shown)", async () => {
  const srv = http.createServer((req, res) => { res.writeHead(401); res.end("no\n"); });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  try {
    const get = about.makeGetVersion(http, srv.address().port, () => "bad");
    await assert.rejects(get(), /HTTP 401/);
  } finally {
    srv.close();
  }
});

test("firstCredit: the credit, or empty on error or timeout", async () => {
  assert.equal(await about.firstCredit(() => Promise.resolve(WITH), 1000), CREDIT);
  assert.equal(await about.firstCredit(() => Promise.resolve(WITHOUT), 1000), "");
  assert.equal(await about.firstCredit(() => Promise.reject(new Error("down")), 1000), "");
  assert.equal(await about.firstCredit(() => new Promise(() => {}), 10), "");
  assert.equal(about.START_WAIT_MS, 1500);
});

test("overlay page keeps the disclaimer and a hidden credit slot", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "overlay", "index.html"), "utf8");
  assert.ok(html.includes('<p class="about">' + DISCLAIMER + "</p>"));
  assert.ok(html.includes('<p id="aboutData" class="about" hidden></p>'));
});
