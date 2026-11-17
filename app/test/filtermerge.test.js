"use strict";
/* UTIL-FILTER-MERGE (decision 0033): the dashboard half of the merge. */
const test = require("node:test");
const assert = require("node:assert/strict");
const m = require("../../web/filtermerge.js");

function env(reply) {
  const out = { told: [], saved: [], calls: [] };
  out.env = {
    token: "t0k",
    tell: (t) => out.told.push(t),
    save: (blob, name) => out.saved.push([blob, name]),
    fetch: (url, opts) => { out.calls.push([url, opts]); return reply(); }
  };
  return out;
}

function file(name, size, bytes) {
  return { name, size, arrayBuffer: () => Promise.resolve(bytes || new ArrayBuffer(4)) };
}

function response(status, body, disposition) {
  return Promise.resolve({
    ok: status === 200, status,
    headers: { get: (k) => (k === "Content-Disposition" ? disposition : null) },
    json: () => (body === undefined ? Promise.reject(new Error("no json")) : Promise.resolve(body)),
    blob: () => Promise.resolve("BLOB")
  });
}

test("a picked file is posted raw with the token, saved under the core's name", async () => {
  const buf = new ArrayBuffer(8);
  const e = env(() => response(200, undefined, 'attachment; filename="My Filter-ashlight.filter"'));
  await m.run(file("My Filter.filter", 8, buf), e.env);
  assert.equal(e.calls.length, 1);
  const [url, opts] = e.calls[0];
  assert.equal(url, "/api/filter-merge?name=My%20Filter.filter");
  assert.equal(opts.method, "POST");
  assert.equal(opts.body, buf);
  assert.deepEqual(opts.headers, { "X-AL-Token": "t0k", "Content-Type": "application/octet-stream" });
  assert.deepEqual(e.saved, [["BLOB", "My Filter-ashlight.filter"]]);
  assert.equal(e.told.at(-1), m.savedText("My Filter-ashlight.filter"));
  assert.match(e.told.at(-1), /unchanged/);
});

test("over 2 MB is refused in the browser, nothing sent", async () => {
  const e = env(() => { throw new Error("must not fetch"); });
  await m.run(file("big.filter", m.MAX_BYTES + 1), e.env);
  assert.equal(e.calls.length, 0);
  assert.equal(e.told.at(-1), m.TOO_BIG);
});

test("no file picked does nothing", async () => {
  const e = env(() => { throw new Error("must not fetch"); });
  await m.run(null, e.env);
  assert.deepEqual(e.told, []);
});

test("a refusal shows the core's plain words, else a retry line", async () => {
  const words = "That file is not a text file. Pick your own .filter file.";
  let e = env(() => response(400, { error: words, reason: "not_text" }));
  await m.run(file("x.png", 4), e.env);
  assert.equal(e.told.at(-1), words);
  assert.deepEqual(e.saved, []);
  e = env(() => response(500, undefined));
  await m.run(file("x.filter", 4), e.env);
  assert.equal(e.told.at(-1), m.FAILED);
  e = env(() => response(413, { error: "x" }));
  await m.run(file("x.filter", 4), e.env);
  assert.equal(e.told.at(-1), m.TOO_BIG);
});

test("a dead core says so", async () => {
  const e = env(() => Promise.reject(new TypeError("Failed to fetch")));
  await m.run(file("x.filter", 4), e.env);
  assert.equal(e.told.at(-1), m.OFFLINE);
});

test("file name: only the core's safe name, else a fallback", () => {
  assert.equal(m.fileName('attachment; filename="a b-ashlight.filter"'), "a b-ashlight.filter");
  assert.equal(m.fileName('attachment; filename="../x"'), "filter-ashlight.filter");
  assert.equal(m.fileName(null), "filter-ashlight.filter");
});
