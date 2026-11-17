"use strict";
/* AUDIT-ELECTRON (audit findings S6-S7, docs/audit/2026-11-17-audit.md):
   the overlay is never packaged, so devTools must not follow
   !app.isPackaged (always on); they follow an explicit AL_DEV=1 env. And a
   permission CHECK handler denies every check next to the request handler. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SRC = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");

test("devTools are gated on AL_DEV, not on isPackaged", () => {
  assert.doesNotMatch(SRC, /devTools:\s*!app\.isPackaged/);
  assert.match(SRC, /devTools:\s*DEV_TOOLS\b/);
  assert.match(SRC, /const DEV_TOOLS = process\.env\.AL_DEV === "1";/);
});

test("permission checks and requests are both denied", () => {
  assert.match(SRC, /setPermissionRequestHandler\(\(wc, perm, cb\) => cb\(false\)\)/);
  assert.match(SRC, /setPermissionCheckHandler\(\(\) => false\)/);
});
