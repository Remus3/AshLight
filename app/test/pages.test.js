"use strict";
/* OVL-APP-SCHEME (decision 0061 amendment 2026-11-21): the app scheme's
   rules (app/pages.js) and its part (app/parts/12-pages.js) with fake
   sessions and a fake protocol; no Electron. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const Pages = require("../pages.js");
const Part = require("../parts/12-pages.js");

const PORT = 8960;
const APP = path.resolve(__dirname, "..");
const ORIGIN = "al-app://app";

function read(file) { return "body of " + file; }

test("the scheme, its one host and the fixed file list", () => {
  assert.equal(Pages.SCHEME, "al-app");
  assert.equal(Pages.ORIGIN, ORIGIN);
  assert.deepEqual(Array.from(Pages.FILES), [
    "overlay/index.html", "overlay/overlay.css", "overlay/overlay.js",
    "shared/format.js", "shared/render_gate.js",
    "client/starting.html", "client/starting.css", "client/starting.js"]);
  assert.ok(Object.isFrozen(Pages.FILES));
  // every listed file exists in the app folder
  for (const f of Pages.FILES) { assert.ok(fs.statSync(path.join(APP, f)).isFile(), f); }
});

test("the handler serves only the listed files; anything else is 404", () => {
  for (const f of Pages.FILES) {
    const r = Pages.respond(ORIGIN + "/" + f, { port: PORT, read });
    assert.equal(r.status, 200, f);
    assert.equal(r.body, "body of " + f);
    assert.equal(r.headers["X-Content-Type-Options"], "nosniff");
    assert.equal(r.headers["Cache-Control"], "no-store");
  }
  assert.match(Pages.respond(ORIGIN + "/overlay/index.html", { port: PORT, read }).headers["Content-Type"],
    /^text\/html/);
  assert.match(Pages.respond(ORIGIN + "/overlay/overlay.css", { port: PORT, read }).headers["Content-Type"],
    /^text\/css/);
  assert.match(Pages.respond(ORIGIN + "/shared/format.js", { port: PORT, read }).headers["Content-Type"],
    /^text\/javascript/);
  // query and fragment do not change the file
  assert.equal(Pages.respond(ORIGIN + "/client/starting.html?reason=x#failed", { port: PORT, read }).status, 200);
  const missing = [
    ORIGIN + "/", ORIGIN, ORIGIN + "/main.js", ORIGIN + "/preload.js", ORIGIN + "/package.json",
    ORIGIN + "/shared/layout.js", ORIGIN + "/overlay/", ORIGIN + "/overlay/index.htm",
    ORIGIN + "/Overlay/index.html", ORIGIN + "//overlay/index.html",
    "al-app://other/overlay/index.html", "al-app://app.evil/overlay/index.html",
    "al-app://app:8960/overlay/index.html", "al-app://user@app/overlay/index.html",
    "file:///overlay/index.html", "http://127.0.0.1:8960/overlay/index.html",
    "https://app/overlay/index.html", "not a url", "", null, undefined
  ];
  for (const u of missing) {
    const r = Pages.respond(u, { port: PORT, read });
    assert.equal(r.status, 404, String(u));
    assert.equal(r.headers["Content-Security-Policy"], undefined);
  }
  // only GET and HEAD; HEAD has no body
  assert.equal(Pages.respond(ORIGIN + "/overlay/index.html", { port: PORT, read, method: "POST" }).status, 404);
  const head = Pages.respond(ORIGIN + "/overlay/index.html", { port: PORT, read, method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(head.body, "");
  // a read failure or no reader is 404, never a throw
  assert.equal(Pages.respond(ORIGIN + "/overlay/index.html",
    { port: PORT, read: () => { throw new Error("gone"); } }).status, 404);
  assert.equal(Pages.respond(ORIGIN + "/overlay/index.html", { port: PORT }).status, 404);
});

test("path traversal is refused", () => {
  const asked = [];
  const spy = (f) => { asked.push(f); return "x"; };
  for (const u of [ORIGIN + "/../main.js", ORIGIN + "/overlay/../main.js",
                   ORIGIN + "/overlay/%2e%2e/main.js", ORIGIN + "/overlay/..%2fmain.js",
                   ORIGIN + "/overlay/..%5cmain.js", ORIGIN + "/overlay\\..\\main.js",
                   ORIGIN + "/%2e%2e/%2e%2e/secret.txt", ORIGIN + "/overlay%2findex.html",
                   ORIGIN + "/overlay/index.html%00", ORIGIN + "/./../../x"]) {
    assert.equal(Pages.resolve(u), null, u);
    assert.equal(Pages.respond(u, { port: PORT, read: spy }).status, 404, u);
  }
  assert.deepEqual(asked, [], "no file is read for a refused path");
  // a dot segment that stays inside the list names the listed file only
  assert.equal(Pages.resolve(ORIGIN + "/client/../overlay/index.html"), "overlay/index.html");
});

test("the CSP header names http://127.0.0.1:<port> exactly; the starting page connects nowhere", () => {
  const csp = Pages.respond(ORIGIN + "/overlay/index.html", { port: PORT, read }).headers["Content-Security-Policy"];
  assert.equal(csp, "default-src 'none'; script-src 'self'; style-src 'self'; " +
    "connect-src http://127.0.0.1:8960; img-src 'none'; base-uri 'none'; form-action 'none'; " +
    "frame-ancestors 'none'");
  assert.ok(!csp.includes("*"), "no port wildcard");
  assert.match(Pages.cspFor(8961, "overlay/index.html"), /connect-src http:\/\/127\.0\.0\.1:8961;/);
  for (const f of ["client/starting.html", "client/starting.js", "client/starting.css"]) {
    assert.match(Pages.respond(ORIGIN + "/" + f, { port: PORT, read }).headers["Content-Security-Policy"],
      /connect-src 'none';/, f);
  }
  // no usable port: no connection at all
  for (const p of [0, -1, 70000, 8960.5, "8960", null, undefined]) {
    assert.match(Pages.cspFor(p, "overlay/index.html"), /connect-src 'none';/, String(p));
  }
});

test("urlFor builds the page URLs; pageKey compares origin and path only", () => {
  assert.equal(Pages.urlFor("overlay/index.html"), ORIGIN + "/overlay/index.html");
  assert.equal(Pages.urlFor("client/starting.html", { hash: "failed" }),
    ORIGIN + "/client/starting.html#failed");
  const u = Pages.urlFor("client/starting.html", { hash: "failed", query: { reason: "Port 8960 is busy." } });
  const p = new URL(u);
  assert.equal(p.searchParams.get("reason"), "Port 8960 is busy.");
  assert.equal(p.hash, "#failed");
  assert.equal(Pages.resolve(u), "client/starting.html");
  assert.throws(() => Pages.urlFor("main.js"));
  assert.equal(Pages.pageKey(ORIGIN + "/overlay/index.html#x"), ORIGIN + "/overlay/index.html");
  assert.equal(Pages.pageKey(ORIGIN + "/overlay/index.html?y=1"), ORIGIN + "/overlay/index.html");
  for (const bad of ["file:///overlay/index.html", "al-app://evil/overlay/index.html",
                     "al-app://app:1/overlay/index.html", "http://127.0.0.1:8960/overlay/index.html",
                     "", "nonsense"]) {
    assert.equal(Pages.pageKey(bad), "", bad);
  }
});

function fakeSession() {
  const s = { handlers: {}, protocol: { handle(scheme, fn) { s.handlers[scheme] = fn; } } };
  return s;
}

class FakeResponse {
  constructor(body, init) { this.body = body; this.status = init.status; this.headers = init.headers; }
}

test("the part: the scheme registered privileged early, served on both sessions once", () => {
  Part.reset();
  const registered = [];
  const def = fakeSession();
  const client = fakeSession();
  const asked = [];
  const logged = [];
  const ctx = {
    port: PORT, log: (m) => logged.push(m), Response: FakeResponse,
    electron: {
      protocol: { registerSchemesAsPrivileged: (list) => registered.push(list) },
      session: { defaultSession: def, fromPartition: (p) => { asked.push(p); return client; } }
    }
  };
  Part.early(ctx);
  assert.deepEqual(registered, [[{ scheme: "al-app", privileges: { standard: true, secure: true } }]]);
  Part.clientWindow(ctx, {}, client); // the companion may load before ready
  Part.ready(ctx);
  Part.overlayWindow(ctx, { webContents: { session: def } });
  assert.deepEqual(asked, ["persist:client"]);
  assert.deepEqual(Object.keys(def.handlers), ["al-app"]);
  assert.deepEqual(Object.keys(client.handlers), ["al-app"]);
  // the real app files, read fresh, with the header CSP
  const r = def.handlers["al-app"]({ url: ORIGIN + "/overlay/index.html", method: "GET" });
  assert.equal(r.status, 200);
  assert.equal(String(r.body), fs.readFileSync(path.join(APP, "overlay", "index.html"), "utf8"));
  assert.match(r.headers["Content-Security-Policy"], /connect-src http:\/\/127\.0\.0\.1:8960;/);
  const s = client.handlers["al-app"]({ url: ORIGIN + "/client/starting.html#failed", method: "GET" });
  assert.equal(s.status, 200);
  assert.match(String(s.body), /id="starting"/);
  // refusals are 404 and logged once, never with the path
  const no = client.handlers["al-app"]({ url: ORIGIN + "/main.js", method: "GET" });
  client.handlers["al-app"]({ url: ORIGIN + "/../package.json", method: "GET" });
  assert.equal(no.status, 404);
  assert.equal(logged.length, 1);
  assert.ok(!logged[0].includes("main.js"));
  // a session without protocol.handle is skipped
  assert.equal(Part.serve(ctx, {}), false);
  assert.equal(Part.serve(ctx, null), false);
  Part.reset();
});

test("the part's app root is the app folder, and it loads after the guards part", () => {
  assert.equal(Part.APP_ROOT, APP);
  const parts = fs.readdirSync(path.join(APP, "parts")).filter((n) => n.endsWith(".js")).sort();
  assert.ok(parts.indexOf("12-pages.js") > parts.indexOf("10-guards.js"));
  assert.ok(parts.indexOf("12-pages.js") < parts.indexOf("15-egress.js"));
});

test("both pages carry no CSP meta (the header has it) and keep relative script paths", () => {
  for (const f of ["overlay/index.html", "client/starting.html"]) {
    const html = fs.readFileSync(path.join(APP, f), "utf8");
    assert.ok(!/http-equiv/i.test(html), f);
    assert.ok(!/(src|href)="(\/|[a-z-]+:)/i.test(html), f + ": no absolute or scheme path");
  }
  const ovl = fs.readFileSync(path.join(APP, "overlay", "index.html"), "utf8");
  for (const ref of ["overlay.css", "../shared/format.js", "../shared/render_gate.js", "overlay.js"]) {
    assert.ok(ovl.includes('"' + ref + '"'), ref);
  }
});
