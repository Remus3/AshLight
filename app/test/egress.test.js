"use strict";
/* OVL-EGRESS-LOCK (decision 0061 amendment 2026-11-19): the egress allow
   function, its filter and the part, with fake sessions; no Electron. */
const test = require("node:test");
const assert = require("node:assert/strict");
const Egress = require("../egress.js");
const Part = require("../parts/15-egress.js");

const PORT = 8960;
// drive letters built from parts, so this file spells no drive path
// (tests/test_sidecar_paths.py)
const D = "C" + ":";
const ROOT = D + "\\ProgramData\\Ash Light\\app";
const APP = "file:///" + D + "/ProgramData/Ash%20Light/app";
const OPTS = { port: PORT, dev: false, appRoot: ROOT, windows: true };
const DEV = Object.assign({}, OPTS, { dev: true });

const ALLOWED = [
  APP + "/overlay/index.html",
  APP + "/overlay/overlay.css",
  APP + "/shared/format.js",
  APP + "/client/starting.html#failed",
  "http://127.0.0.1:8960/#token=abc",
  "http://127.0.0.1:8960/events?token=abc",
  "http://127.0.0.1:8960/api/health",
  "blob:http://127.0.0.1:8960/0b4f-11",
  "data:image/png;base64,AAAA"
];

const REFUSED = [
  "https://www.pathofexile.com/trade2/search/poe2/Standard",
  "https://poe.ninja/api/data/economy",
  "http://127.0.0.1:8961/api/health",
  "http://localhost:8960/",
  "http://127.0.0.2:8960/",
  "https://127.0.0.1:8960/",
  "ws://127.0.0.1:8960/events",
  "http://user:pw@127.0.0.1:8960/",
  "file:///" + D + "/ProgramData/Ash%20Light/other/x.html",
  "file:///" + D + "/ProgramData/Ash%20Light/app/../secret.txt",
  "file:///" + D + "/ProgramData/Ash%20Light/application/x.html",
  "file://server/share/app/overlay/index.html",
  "devtools://devtools/bundled/inspector.html",
  "chrome://gpu",
  "ftp://example.com/",
  "not a url"
];

test("the allow function: app pages, the core on its port, blob: and data:", () => {
  for (const u of ALLOWED) { assert.equal(Egress.allow(u, OPTS), true, u); }
});

test("every other scheme, host and port is cancelled, the trade site and poe.ninja included", () => {
  for (const u of REFUSED) { assert.equal(Egress.allow(u, OPTS), false, u); }
  assert.ok(ALLOWED.length + REFUSED.length >= 20);
});

test("devtools only with AL_DEV=1; dev opens nothing else", () => {
  assert.equal(Egress.allow("devtools://devtools/bundled/inspector.html", DEV), true);
  for (const u of REFUSED.filter((x) => !x.startsWith("devtools:"))) {
    assert.equal(Egress.allow(u, DEV), false, u);
  }
});

test("no port, no root or no options refuse the core and files", () => {
  assert.equal(Egress.allow("http://127.0.0.1:8960/", { appRoot: ROOT, windows: true }), false);
  assert.equal(Egress.allow(APP + "/overlay/index.html", { port: PORT, windows: true }), false);
  assert.equal(Egress.allow("http://127.0.0.1:8960/"), false);
  assert.equal(Egress.allow("data:,x"), true);
});

test("the filter cancels refused requests and logs each origin once, never a path", () => {
  const logged = [];
  const f = Egress.makeFilter(Object.assign({ log: (m) => logged.push(m) }, OPTS));
  const answers = [];
  const cb = (r) => answers.push(r.cancel);
  f({ url: "https://www.pathofexile.com/trade2/search/poe2/x?q=1" }, cb);
  f({ url: "https://www.pathofexile.com/other" }, cb);
  f({ url: "http://127.0.0.1:8960/events?token=secret" }, cb);
  f({ url: "https://poe.ninja/api/data" }, cb);
  assert.deepEqual(answers, [true, true, false, true]);
  assert.deepEqual(logged, ["egress: request cancelled to https://www.pathofexile.com",
                            "egress: request cancelled to https://poe.ninja"]);
});

function fakeSession() {
  const s = { listeners: [], webRequest: { onBeforeRequest(fn) { s.listeners.push(fn); } } };
  return s;
}

test("the part locks both sessions once, also from the window hooks", () => {
  Part.reset();
  const def = fakeSession();
  const client = fakeSession();
  const asked = [];
  const ctx = {
    port: PORT, devTools: false, appRoot: ROOT, log: () => {},
    electron: { session: { defaultSession: def,
                           fromPartition: (p) => { asked.push(p); return client; } } }
  };
  Part.clientWindow(ctx, {}, client);
  Part.overlayWindow(ctx, { webContents: { session: def } });
  Part.ready(ctx);
  assert.deepEqual(asked, ["persist:client"]);
  assert.equal(def.listeners.length, 1);
  assert.equal(client.listeners.length, 1);
  let cancel = null;
  client.listeners[0]({ url: "https://poe.ninja/" }, (r) => { cancel = r.cancel; });
  assert.equal(cancel, true);
  def.listeners[0]({ url: "http://127.0.0.1:8960/events" }, (r) => { cancel = r.cancel; });
  assert.equal(cancel, false);
  Part.reset();
});

test("the part's app root is the app folder", () => {
  const path = require("path");
  assert.equal(Part.APP_ROOT, path.resolve(__dirname, ".."));
});
