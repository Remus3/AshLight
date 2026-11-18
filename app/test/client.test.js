"use strict";
/* DESKTOP-CLIENT (decision 0041): the companion window's rules
   (app/client/link.js), its brand icon (app/brand/index.js), its
   launcher (app/client/launcher.js, run with fakes) and the window's
   security wiring (app/client/window.js, read as text). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const Link = require("../client/link.js");
const Launcher = require("../client/launcher.js");

const TOKEN = "ab".repeat(24);
const AT = String.fromCharCode(64);
const PORT = 8960;
const WIN_SRC = fs.readFileSync(path.join(__dirname, "..", "client", "window.js"), "utf8");
const MAIN_SRC = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");

test("dashboard URL carries the token in the fragment only", () => {
  const url = Link.dashboardUrl(PORT, TOKEN);
  assert.equal(url, "http://127.0.0.1:8960/#token=" + TOKEN);
  const u = new URL(url);
  assert.equal(u.search, "");
  assert.equal(u.hash, "#token=" + TOKEN);
  assert.equal(Link.dashboardUrl(PORT, ""), "");
  assert.equal(Link.dashboardUrl(PORT, "not-hex&x=1"), "");
  assert.equal(Link.dashboardUrl(0, TOKEN), "");
  assert.equal(Link.dashboardUrl("8960", TOKEN), "");
});

test("the window stays on the local core; only http(s) links leave", () => {
  assert.equal(Link.routeFor("http://127.0.0.1:8960/", PORT, false), "stay");
  assert.equal(Link.routeFor("http://127.0.0.1:8960/#token=x", PORT, false), "stay");
  assert.equal(Link.routeFor("http://127.0.0.1:8960/", PORT, true), "deny"); // no popups
  assert.equal(Link.routeFor("http://127.0.0.1:8961/", PORT, false), "external");
  assert.equal(Link.routeFor("http://localhost:8960/", PORT, false), "external");
  assert.equal(Link.routeFor("https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%7D",
                             PORT, true), "external");
  assert.equal(Link.routeFor("https://poe.ninja/", PORT, false), "external");
  for (const bad of ["file:///etc/hosts", "javascript:alert(1)", "data:text/html,x",
                     "ms-settings:display", "steam://run/1", "about:blank", "",
                     // userinfo URLs built from parts (the leak sweep reads
                     // a literal "name@host" as an email address)
                     "https://u:p" + AT + "example.com/", "http://127.0.0.1:8960" + AT + "evil.example/x"]) {
    assert.notEqual(Link.routeFor(bad, PORT, false), "stay", bad);
    if (!/^https?:/.test(bad) || bad.includes("@")) {
      assert.equal(Link.routeFor(bad, PORT, false), "deny", bad);
    }
  }
  assert.equal(Link.isCoreUrl("https://127.0.0.1:8960/", PORT), false);
});

test("--client is read from the command line", () => {
  assert.equal(Link.wantsClient(["electron.exe", "app", "--client"]), true);
  assert.equal(Link.wantsClient(["electron.exe", "app", "--CLIENT"]), true);
  assert.equal(Link.wantsClient(["electron.exe", "app"]), false);
  assert.equal(Link.wantsClient(null), false);
});

test("saved bounds are kept only while a display shows them", () => {
  const areas = [{ x: 0, y: 0, width: 1920, height: 1040 }, { x: 1920, y: 0, width: 1920, height: 1040 }];
  const saved = { x: 2000, y: 100, width: 1000, height: 700, maximized: true };
  assert.deepEqual(Link.windowBounds(saved, areas),
                   { bounds: { x: 2000, y: 100, width: 1000, height: 700 }, maximized: true });
  // the second monitor was unplugged: back to the default on the primary
  const one = Link.windowBounds(saved, [areas[0]]);
  assert.deepEqual(one.bounds, { x: 320, y: 90, width: 1280, height: 860 });
  assert.equal(one.maximized, false);
  // junk or too small
  for (const junk of [null, "x", {}, { x: 0, y: 0, width: 100, height: 100 },
                      { x: "a", y: 0, width: 900, height: 700 }]) {
    assert.deepEqual(Link.windowBounds(junk, areas).bounds, { x: 320, y: 90, width: 1280, height: 860 });
  }
  // a small screen caps the default size
  assert.deepEqual(Link.windowBounds(null, [{ x: 0, y: 0, width: 1024, height: 700 }]).bounds,
                   { x: 0, y: 0, width: 1024, height: 700 });
  assert.deepEqual(Link.stateDoc({ x: 1, y: 2, width: 3, height: 4 }, 1),
                   { x: 1, y: 2, width: 3, height: 4, maximized: false });
});

test("download names are reduced to a safe base name", () => {
  assert.equal(Link.safeFileName("ashlight.filter"), "ashlight.filter");
  assert.equal(Link.safeFileName("..\\..\\Windows\\evil.exe"), "evil.exe");
  assert.equal(Link.safeFileName("a/b/c:d?.build"), "c_d_.build");
  assert.equal(Link.safeFileName("..."), "");
  assert.equal(Link.safeFileName(""), "");
  assert.ok(Link.safeFileName("x".repeat(400)).length <= 120);
});

test("waitFor polls until the core answers or the time is up", async () => {
  let t = 0;
  let calls = 0;
  const ok = await Link.waitFor(() => { calls += 1; return calls >= 3; }, 10000, 500,
                                (ms) => { t += ms; return Promise.resolve(); }, () => t);
  assert.equal(ok, true);
  assert.equal(calls, 3);
  t = 0;
  const no = await Link.waitFor(() => Promise.reject(new Error("down")), 2000, 500,
                                (ms) => { t += ms; return Promise.resolve(); }, () => t);
  assert.equal(no, false);
  assert.equal(t, 2000);
});

test("health check sends the token header and reads 200 as up", async () => {
  let seen = null;
  const srv = http.createServer((req, res) => {
    seen = req.headers["x-al-token"];
    res.statusCode = seen === TOKEN ? 200 : 401;
    res.end("{}");
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const port = srv.address().port;
  try {
    assert.equal(await Link.makeHealthCheck(http, port, () => TOKEN)(), true);
    assert.equal(seen, TOKEN);
    assert.equal(await Link.makeHealthCheck(http, port, () => "cd".repeat(24))(), false);
    assert.equal(await Link.makeHealthCheck(http, port, () => "")(), false);
  } finally {
    srv.close();
  }
  assert.equal(await Link.makeHealthCheck(http, port, () => TOKEN)(), false); // closed
});

test("the window and tray use the brand icon files", () => {
  assert.match(WIN_SRC, /require\("\.\.\/brand\/index\.js"\)/);
  assert.match(WIN_SRC, /return Brand\.trayImage\(nativeImage\);/);
});

test("launcher runs the repo's own scripts, hidden, never detached", () => {
  const calls = [];
  const fake = (exe, args, opts) => { calls.push({ exe, args, opts }); return { pid: 42, unref() {} }; };
  assert.equal(Launcher.startCore("R", 8961, fake), 42);
  assert.equal(Launcher.stopAll("R", fake), 42);
  const [run, stop] = calls;
  assert.equal(run.exe, "powershell.exe");
  assert.ok(run.args.includes("-File"));
  assert.match(run.args[run.args.indexOf("-File") + 1], /scripts[\\/]run\.ps1$/);
  assert.deepEqual(run.args.slice(-3), ["-NoBrowser", "-Port", "8961"]);
  assert.match(stop.args[stop.args.indexOf("-File") + 1], /scripts[\\/]stop\.ps1$/);
  for (const c of calls) {
    assert.equal(c.opts.windowsHide, true);
    assert.equal(c.opts.detached, false);
    assert.equal(c.opts.stdio, "ignore");
    assert.ok(c.args.includes("Hidden"));
  }
  assert.equal(Launcher.startCore("R", 0, () => { throw new Error("no ps"); }), 0);
});

test("the sidecar comes from server.al.paths, else empty", () => {
  const seen = [];
  const exec = (py, args) => {
    seen.push(py);
    if (py === "python") { throw new Error("missing"); }
    assert.deepEqual(args, ["-m", "server.al.paths"]);
    return JSON.stringify({ sidecar: "side-root" });
  };
  assert.equal(Launcher.resolveSidecar("R", exec), "side-root");
  assert.deepEqual(seen, ["python", "py"]);
  assert.equal(Launcher.resolveSidecar("R", () => { throw new Error("x"); }), "");
  assert.equal(Launcher.resolveSidecar("R", () => "{}"), "");
});

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

test("the companion window is a normal, sandboxed window on its own session", () => {
  const c = code(WIN_SRC);
  for (const needle of ["contextIsolation: true", "nodeIntegration: false", "sandbox: true",
                        "session: clientSession()", 'session.fromPartition(PARTITION)',
                        "setWindowOpenHandler(", 'return { action: "deny" }',
                        '"will-navigate"', '"will-redirect"', "shell.openExternal(url)",
                        "Link.routeFor(", "setPermissionRequestHandler(",
                        "setPermissionCheckHandler(", "minWidth"]) {
    assert.ok(c.includes(needle), needle);
  }
  for (const banned of ["alwaysOnTop", "transparent", "setIgnoreMouseEvents", "focusable: false",
                        "skipTaskbar", "frame: false", "nodeIntegration: true", "webviewTag",
                        "loadURL(e.url", "clipboard.read", "defaultSession"]) {
    assert.ok(!c.includes(banned), banned);
  }
  assert.equal((c.match(/new BrowserWindow\(/g) || []).length, 1);
  // the only permission ever granted is the click-time clipboard write
  assert.match(c, /const ALLOWED_PERMISSION = "clipboard-sanitized-write";/);
  assert.equal((c.match(/cb\(/g) || []).length, 1);
});

test("main.js opens the client only in client mode, after ready", () => {
  const c = code(MAIN_SRC);
  assert.match(c, /const CLIENT_MODE = Link\.wantsClient\(process\.argv\);/);
  assert.match(c, /if \(CLIENT_MODE\) \{ openClient\(\); \}/);
  assert.match(c, /if \(Link\.wantsClient\(argv\)\) \{ openClient\(\); \}/);
  // the window module is loaded lazily, never at an overlay-only start
  assert.ok(!/^const .*require\("\.\/client\/window\.js"\)/m.test(c));
  assert.ok(c.indexOf("resolveSidecar(REPO)") < c.indexOf('app.setPath("userData"'));
  assert.ok(c.indexOf("resolveSidecar(REPO)") < c.indexOf("requestSingleInstanceLock()"));
});
