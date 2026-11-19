/* TEST-WEB-SRCPATHS-NODE: the dashboard source helper (app/test/_web.js). */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const web = require("./_web.js");

test("load returns the web module", () => {
  const a = web.load("acts.js");
  assert.equal(typeof a, "object");
  assert.strictEqual(a, require(path.join(web.dir, "acts.js")));
});

test("source returns the file text, utf8 by default", () => {
  const html = web.source("index.html");
  assert.equal(html, fs.readFileSync(path.join(web.dir, "index.html"), "utf8"));
  assert.match(html, /<html/i);
  assert.equal(web.source("index.html", "ascii"),
    fs.readFileSync(path.join(web.dir, "index.html"), "ascii"));
});

test("dir is the repository's web folder", () => {
  assert.equal(web.dir, path.resolve(__dirname, "..", "..", "web"));
  assert.equal(web.file("app.css"), path.join(web.dir, "app.css"));
});

test("a name under panels/ resolves when the folder exists", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "al-web-"));
  try {
    const w = web.create(root);
    assert.throws(() => w.file("card.js"), /card\.js/);
    fs.mkdirSync(path.join(root, "panels"));
    fs.writeFileSync(path.join(root, "panels", "card.js"),
      "module.exports = { panel: 1 };\n");
    fs.writeFileSync(path.join(root, "top.js"), "module.exports = { top: 1 };\n");
    assert.equal(w.file("card.js"), path.join(root, "panels", "card.js"));
    assert.deepEqual(w.load("card.js"), { panel: 1 });
    assert.equal(w.source("card.js"), "module.exports = { panel: 1 };\n");
    assert.deepEqual(w.load("top.js"), { top: 1 });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("web/ wins over panels/ for the same name", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "al-web-"));
  try {
    fs.mkdirSync(path.join(root, "panels"));
    fs.writeFileSync(path.join(root, "x.js"), "a");
    fs.writeFileSync(path.join(root, "panels", "x.js"), "b");
    assert.equal(web.create(root).source("x.js"), "a");
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("an unknown name throws with the name", () => {
  assert.throws(() => web.load("no_such_part.js"), /no_such_part\.js/);
  assert.throws(() => web.source("missing.html"), /missing\.html/);
});

test("a name that leaves the web folder is refused", () => {
  assert.throws(() => web.source("../app/main.js"), /\.\.\/app\/main\.js/);
  assert.throws(() => web.source(path.join(web.dir, "acts.js")), /not allowed/);
  assert.throws(() => web.source(""), /not allowed/);
});
