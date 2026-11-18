"use strict";
/* BRAND-ICON: app/brand/index.js points at real icon files of the right
   size, and trayImage builds the 1x / 2x representations. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const Brand = require("../brand/index.js");

function pngSize(file) {
  const b = fs.readFileSync(file);
  assert.equal(b.subarray(1, 4).toString("latin1"), "PNG", file);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

test("tray and large icon PNGs have their sizes", () => {
  assert.deepEqual(pngSize(Brand.TRAY_16), [16, 16]);
  assert.deepEqual(pngSize(Brand.TRAY_32), [32, 32]);
  assert.deepEqual(pngSize(Brand.ICON_256), [256, 256]);
});

test("icon.ico holds the seven sizes", () => {
  const b = fs.readFileSync(Brand.ICO);
  assert.equal(b.readUInt16LE(2), 1);
  const n = b.readUInt16LE(4);
  const sizes = [];
  for (let i = 0; i < n; i++) { sizes.push(b[6 + 16 * i] || 256); }
  assert.deepEqual(sizes, [16, 24, 32, 48, 64, 128, 256]);
});

test("trayImage adds a 1x and a 2x representation", () => {
  const reps = [];
  const fake = { createEmpty: () => ({ addRepresentation: (r) => reps.push(r) }) };
  Brand.trayImage(fake);
  assert.deepEqual(reps.map((r) => r.scaleFactor), [1, 2]);
  assert.ok(reps.every((r) => Buffer.isBuffer(r.buffer) && r.buffer.length > 0));
});
