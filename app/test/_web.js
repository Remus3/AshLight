/* TEST-WEB-SRCPATHS-NODE: the one place the node tests learn where the
   dashboard sources live. A test asks for a file by name:
     load("acts.js")       -> the module (require)
     source("index.html")  -> its text (utf8 unless an encoding is given)
     file("app.css")       -> its absolute path
     dir                   -> the web folder itself
   A name is looked up in web/ first, then in web/panels/ when that folder
   exists, so a source can move into panels/ without touching the tests.
   An unknown name throws an error that carries the name.
   Not a test file: the npm script runs test/**\/*.test.js only. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const SUBDIRS = ["", "panels"];

function create(root) {
  const dir = path.resolve(root);

  function file(name) {
    if (typeof name !== "string" || name === "" || path.isAbsolute(name) ||
        name.split(/[\\/]/).includes("..")) {
      throw new Error("web source name not allowed: " + String(name));
    }
    for (const sub of SUBDIRS) {
      const base = sub ? path.join(dir, sub) : dir;
      if (sub && !fs.existsSync(base)) { continue; }
      const full = path.join(base, name);
      if (fs.existsSync(full) && fs.statSync(full).isFile()) { return full; }
    }
    throw new Error("web source not found: " + name);
  }

  function load(name) { return require(file(name)); }

  function source(name, encoding) {
    return fs.readFileSync(file(name), encoding || "utf8");
  }

  return { dir, file, load, source };
}

module.exports = create(path.join(__dirname, "..", "..", "web"));
module.exports.create = create;
