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

const T0 = 1000000;
const TRADE = "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%7D";
function ctx(extra) { return Object.assign({ focused: true, now: T0, history: [] }, extra || {}); }

test("the window stays on the local core; only listed https links leave", () => {
  assert.equal(Link.routeFor("http://127.0.0.1:8960/", PORT, false, ctx()), "stay");
  assert.equal(Link.routeFor("http://127.0.0.1:8960/#token=x", PORT, false, ctx()), "stay");
  // the core stays even without focus or ctx (its own navigations)
  assert.equal(Link.routeFor("http://127.0.0.1:8960/", PORT, false), "stay");
  assert.equal(Link.routeFor("http://127.0.0.1:8960/", PORT, true, ctx()), "deny"); // no popups
  assert.equal(Link.routeFor("http://127.0.0.1:8961/", PORT, false, ctx()), "deny");
  assert.equal(Link.routeFor("http://localhost:8960/", PORT, false, ctx()), "deny");
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx()), "external");
  assert.equal(Link.routeFor("https://poe2db.tw/us/Iron_Ring", PORT, false, ctx()), "external");
  assert.equal(Link.routeFor("https://www.pathofexile2.com/passive-skill-tree/A", PORT, true, ctx()),
               "external"); // a subdomain of a listed host
  for (const bad of ["file:///etc/hosts", "javascript:alert(1)", "data:text/html,x",
                     "ms-settings:display", "steam://run/1", "about:blank", "",
                     "http://www.pathofexile.com/trade2/", // http, even to a listed host
                     "https://poe.ninja/", "https://example.org/", // hosts off the list
                     "https://poe2db.tw.evil.example/", "https://www.pathofexile.com:8443/x",
                     // userinfo URLs built from parts (the leak sweep reads
                     // a literal "name@host" as an email address)
                     "https://u:p" + AT + "poe2db.tw/", "http://127.0.0.1:8960" + AT + "evil.example/x"]) {
    assert.equal(Link.routeFor(bad, PORT, false, ctx()), "deny", bad);
    assert.equal(Link.routeFor(bad, PORT, true, ctx()), "deny", bad);
  }
  assert.equal(Link.isCoreUrl("https://127.0.0.1:8960/", PORT), false);
});

test("a link leaves only from the focused companion, at a human rate", () => {
  // no focus, or no ctx at all: denied
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ focused: false })), "deny");
  assert.equal(Link.routeFor(TRADE, PORT, true), "deny");
  // the second link inside 1 s
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ history: [T0 - 999] })), "deny");
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ history: [T0 - 1000] })), "external");
  // the sixth link in a minute
  const five = [T0 - 50000, T0 - 40000, T0 - 30000, T0 - 20000, T0 - 10000];
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ history: five })), "deny");
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ history: five.slice(1) })), "external");
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ now: T0 + 10001, history: five })),
               "external"); // the oldest left the minute
  assert.equal(Link.routeFor(TRADE, PORT, true, ctx({ now: NaN })), "deny");
  // the history keeps the last minute only
  assert.deepEqual(Link.noteOpened([T0 - 70000, T0 - 59000], T0), [T0 - 59000, T0]);
  let h = [];
  let opened = 0;
  for (let t = T0; t < T0 + 60000; t += 1000) {
    if (Link.routeFor(TRADE, PORT, true, ctx({ now: t, history: h })) === "external") {
      opened += 1;
      h = Link.noteOpened(h, t);
    }
  }
  assert.equal(opened, 5);
});

test("the browser gets the parsed href", () => {
  assert.equal(Link.externalHref("https://POE2DB.tw/us/Iron Ring"), "https://poe2db.tw/us/Iron%20Ring");
  assert.equal(Link.externalHref(TRADE), TRADE);
  assert.equal(Link.externalHref("not a url"), "");
  const c = code(WIN_SRC);
  assert.ok(c.includes("const parsed = new URL(url);"));
  assert.ok(c.includes("shell.openExternal(parsed.href)"));
  assert.ok(!c.includes("shell.openExternal(url)"));
  assert.ok(c.includes("focused: focused, now: now, history: opened"));
  assert.ok(c.includes("win.isFocused()"));
});

test("only AshLight's own downloads are saved", () => {
  const blob = "blob:http://127.0.0.1:8960/0f0e1d2c-aaaa-bbbb-cccc-111122223333";
  for (const name of ["ashlight.build", "ashlight.filter", "filter-My Filter.filter",
                      "ashlight-settings.json", "report.txt", "ASHLIGHT.BUILD"]) {
    assert.equal(Link.downloadAllowed(blob, name, PORT), true, name);
    assert.equal(Link.downloadAllowed("http://127.0.0.1:8960/api/filter", name, PORT), true, name);
  }
  for (const name of ["x.exe", "ashlight.build.exe", "x.bat", "x.html", "x", ".build", "",
                      "..\\..\\x.ps1"]) {
    assert.equal(Link.downloadAllowed(blob, name, PORT), false, name);
  }
  for (const url of ["blob:http://127.0.0.1:8961/abc", "http://127.0.0.1:8961/x",
                     "https://poe2db.tw/x.json", "blob:https://poe2db.tw/abc",
                     "data:text/plain,x", "file:///etc/x.txt", "", "nonsense"]) {
    assert.equal(Link.downloadAllowed(url, "ashlight.json", PORT), false, url);
  }
  const c = code(WIN_SRC);
  assert.ok(c.includes("Link.downloadAllowed(item.getURL(), item.getFilename(), port)"));
  assert.ok(c.indexOf("item.cancel();") < c.indexOf("item.setSavePath("));
  assert.ok(c.includes('log("client: download refused")'));
  assert.ok(c.includes("Link.isCoreUrl(requestingOrigin, port)"));
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

test("first run with two displays: the companion avoids the overlay's display", () => {
  const primary = { x: 0, y: 0, width: 1920, height: 1080 };
  const second = { x: 1920, y: 0, width: 2560, height: 1440 };
  // createWindow passes the primary first, then every display (a repeat)
  const areas = [primary, primary, second];
  const inside = (b, a) => b.x >= a.x && b.y >= a.y && b.x + b.width <= a.x + a.width &&
    b.y + b.height <= a.y + a.height;
  // overlay on the primary, no saved state -> centred on the second
  const onSecond = Link.windowBounds(null, areas, primary);
  assert.deepEqual(onSecond.bounds, { x: 1920 + 640, y: 290, width: 1280, height: 860 });
  assert.ok(inside(onSecond.bounds, second));
  assert.equal(onSecond.maximized, false);
  // overlay on the second -> the primary
  assert.deepEqual(Link.windowBounds(null, areas, { x: 1920, y: 0, width: 2560, height: 1440 }).bounds,
                   { x: 320, y: 110, width: 1280, height: 860 });
  // one area -> today's centred bounds
  assert.deepEqual(Link.windowBounds(null, [primary], primary).bounds,
                   { x: 320, y: 110, width: 1280, height: 860 });
  // the overlay's display unknown -> today's centred bounds on the primary
  assert.deepEqual(Link.windowBounds(null, areas, null).bounds,
                   { x: 320, y: 110, width: 1280, height: 860 });
  // the largest of the others wins
  const third = { x: -1280, y: 0, width: 1280, height: 1024 };
  assert.ok(inside(Link.windowBounds(null, [primary, third, second], primary).bounds, second));
  // saved visible bounds still win
  const saved = { x: 100, y: 100, width: 1000, height: 700, maximized: true };
  assert.deepEqual(Link.windowBounds(saved, areas, primary),
                   { bounds: { x: 100, y: 100, width: 1000, height: 700 }, maximized: true });
  const c = code(WIN_SRC);
  assert.ok(c.includes("opts.overlayBounds()"));
  assert.ok(c.includes("d.id === ob.displayId"));
  assert.ok(c.includes("Link.windowBounds(readState(), areas, avoid)"));
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
  // OVL-LAUNCH-ENV: never a bare name (it would be looked up in the repo)
  for (const c of calls) {
    assert.ok(path.win32.isAbsolute(c.exe), c.exe);
    assert.match(c.exe, /^[A-Za-z]:\\.*\\System32\\WindowsPowerShell\\v1\.0\\powershell\.exe$/i);
    assert.equal(c.exe, Launcher.psExe());
  }
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

/* REL-CLIENT-HOME (F-049): the launcher takes its script path, cwd, Python
   command and child environment from app/client/home.js. */
test("launcher follows the Home: scripts and cwd under its root, env from childEnv", () => {
  const Home = require("../client/home.js");
  const calls = [];
  const fake = (exe, args, opts) => { calls.push({ exe, args, opts }); return { pid: 7, unref() {} }; };
  const root = path.join(path.parse(__dirname).root, "H", "app", "0.1.1");
  const home = { mode: "installed", root: root, home: path.dirname(path.dirname(root)), pythonDir: null };
  const env = { SystemRoot: "C" + ":" + "\\Windows", AL_HOME: home.home };
  assert.equal(Launcher.startCore(home, 8961, fake, env), 7);
  assert.equal(Launcher.stopAll(home, fake, env), 7);
  assert.equal(calls[0].args[calls[0].args.indexOf("-File") + 1], path.join(root, "scripts", "run.ps1"));
  assert.equal(calls[1].args[calls[1].args.indexOf("-File") + 1], path.join(root, "scripts", "stop.ps1"));
  for (const c of calls) {
    assert.equal(c.opts.cwd, root);
    assert.deepEqual(c.opts.env, Home.childEnv(env));
    assert.notEqual(c.opts.env, env);
  }
  // a bare root is a checkout home: the same paths as before
  calls.length = 0;
  Launcher.startCore("R", 0, fake, env);
  assert.equal(calls[0].opts.cwd, "R");
  assert.equal(calls[0].args[calls[0].args.indexOf("-File") + 1], path.join("R", "scripts", "run.ps1"));
});

test("resolveSidecar: the Home's python command (boot.py and the private runtime in an install)", () => {
  const Home = require("../client/home.js");
  const root = path.join(path.parse(__dirname).root, "H", "app", "0.1.1");
  const py = path.join(path.parse(__dirname).root, "H", "runtime", "python-3.14.10", "python.exe");
  const home = { mode: "installed", root: root, home: path.dirname(path.dirname(root)),
                 pythonDir: path.dirname(py) };
  const seen = [];
  const exec = (exe, args, opts) => { seen.push({ exe, args, opts }); return JSON.stringify({ sidecar: "S" }); };
  assert.equal(Launcher.resolveSidecar(home, exec, { PATH: "" }), "S");
  assert.equal(seen.length, 1);
  assert.equal(seen[0].exe, py);
  assert.deepEqual(seen[0].args, Home.pythonCmd(home, "server.al.paths", []).args);
  assert.deepEqual(seen[0].args, [path.join(root, "boot.py"), "server.al.paths"]);
  assert.equal(seen[0].opts.cwd, root);
  assert.deepEqual(seen[0].opts.env, { PATH: "" });
});

/* A temp folder with a python.exe and a py.exe; PATH and PATHEXT for it. */
function pyDirs(t) {
  const root = fs.mkdtempSync(path.join(require("node:os").tmpdir(), "al-launch-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const bin = path.join(root, "bin");
  const cwd = path.join(root, "repo");
  fs.mkdirSync(bin);
  fs.mkdirSync(cwd);
  for (const n of ["python.exe", "py.exe"]) {
    fs.writeFileSync(path.join(bin, n), "");
    fs.writeFileSync(path.join(cwd, n), "planted");
  }
  return { root, bin, cwd };
}

test("the sidecar comes from server.al.paths, else empty", (t) => {
  const { bin } = pyDirs(t);
  const env = { PATH: bin, PATHEXT: ".COM;.EXE" };
  const seen = [];
  const exec = (py, args) => {
    seen.push(py);
    if (path.basename(py).toLowerCase() === "python.exe") { throw new Error("missing"); }
    assert.deepEqual(args, ["-m", "server.al.paths"]);
    return JSON.stringify({ sidecar: "side-root" });
  };
  assert.equal(Launcher.resolveSidecar("R", exec, env), "side-root");
  assert.deepEqual(seen.map((x) => x.toLowerCase()),
                   [path.join(bin, "python.exe"), path.join(bin, "py.exe")].map((x) => x.toLowerCase()));
  assert.equal(Launcher.resolveSidecar("R", () => { throw new Error("x"); }, env), "");
  assert.equal(Launcher.resolveSidecar("R", () => "{}", env), "");
});

test("OVL-LAUNCH-ENV: Python only from an absolute PATH entry, never the current directory", (t) => {
  const { bin, cwd } = pyDirs(t);
  const saved = process.cwd();
  process.chdir(cwd);
  try {
    checkPythonLookup(saved, bin, cwd);
  } finally {
    process.chdir(saved);
  }
});

function checkPythonLookup(saved, bin, cwd) {
  const seen = [];
  const exec = (py) => { seen.push(py); return JSON.stringify({ sidecar: "s" }); };
  // the current directory, ".", empty, relative and UNC entries are skipped
  // (path.relative is absolute when the temp dir is on another drive: skip it then)
  const rel = path.relative(saved, bin);
  const rels = path.isAbsolute(rel) ? [] : [rel];
  for (const p of ["", ".", ";;", "repo", ...rels, "\\\\server\\share", "//server/share"]) {
    const env = { PATH: p, PATHEXT: ".EXE" };
    assert.equal(Launcher.whichAbs("python", env), "", p);
    assert.equal(Launcher.resolveSidecar(cwd, exec, env), "", p);
  }
  assert.deepEqual(seen, [], "no bare or relative python was ever run");
  // an absolute entry (quoted or not) after a bad one is used
  const env = { PATH: ['.', '"' + bin + '"'].join(";"), PATHEXT: ".EXE" };
  assert.equal(Launcher.whichAbs("python", env).toLowerCase(), path.join(bin, "python.exe").toLowerCase());
  assert.equal(Launcher.resolveSidecar(cwd, exec, env), "s");
  assert.ok(path.isAbsolute(seen[0]) && path.dirname(seen[0]) === bin, seen[0]);
  // a folder named like the tool is not a match
  fs.mkdirSync(path.join(bin, "python3.exe"));
  assert.equal(Launcher.whichAbs("python3", env), "");
}

test("OVL-LAUNCH-ENV: powershell.exe from an absolute SystemRoot, else SystemDrive\\Windows", () => {
  const tail = "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
  // drive paths are built, never written out (tools/leak_sweep.py)
  const at = (d, rest) => d + ":" + "\\" + rest;
  assert.equal(Launcher.psExe({ SystemRoot: at("D", "Win"), SystemDrive: "C:" }), at("D", "Win") + tail);
  for (const bad of ["", "Windows", ".\\Windows", "\\\\host\\share", "D:", "D:Windows"]) {
    assert.equal(Launcher.psExe({ SystemRoot: bad, SystemDrive: "E:" }), at("E", "Windows") + tail, bad);
  }
  assert.equal(Launcher.psExe({ SystemRoot: "rel", SystemDrive: "bad" }), at("C", "Windows") + tail);
  assert.equal(Launcher.psExe({}), at("C", "Windows") + tail);
  // startCore / stopAll pass it to spawn
  const seen = [];
  const fake = (exe) => { seen.push(exe); return { pid: 1, unref() {} }; };
  const env = { SystemRoot: at("F", "WINDOWS") };
  Launcher.startCore("R", 8961, fake, env);
  Launcher.stopAll("R", fake, env);
  assert.deepEqual(seen, [at("F", "WINDOWS") + tail, at("F", "WINDOWS") + tail]);
});

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

/* TC-CALC-OPTIN-BUTTON (decision 0041 amendment 2026-11-20, rulings
   W16-1, W16-2): the calc setup is one fixed script, run hidden. */
test("calc setup: only the fixed scripts/calc_setup.ps1, hidden, by absolute PowerShell, no argument", () => {
  const calls = [];
  const handlers = {};
  const fake = (exe, args, opts) => {
    calls.push({ exe, args, opts });
    return { pid: 51, on(ev, fn) { handlers[ev] = fn; return this; }, unref() { calls.push("unref"); } };
  };
  const done = [];
  assert.equal(Launcher.setupCalc("R", fake, (c) => done.push(c)), 51);
  const run = calls[0];
  assert.equal(run.exe, Launcher.psExe());
  assert.ok(path.win32.isAbsolute(run.exe), run.exe);
  assert.match(run.exe, /\\System32\\WindowsPowerShell\\v1\.0\\powershell\.exe$/i);
  assert.deepEqual(run.args, Launcher.psArgs(path.join("R", "scripts", "calc_setup.ps1")));
  assert.equal(run.args[run.args.length - 1], path.join("R", "scripts", Launcher.CALC_SETUP_PS1));
  assert.equal(run.args.indexOf("-File"), run.args.length - 2, "the script gets no argument");
  assert.ok(run.args.includes("Hidden"));
  assert.deepEqual(run.opts, { cwd: "R", detached: false, windowsHide: true, stdio: "ignore" });
  assert.equal(calls[1], "unref");
  // the outcome is reported once, on exit (an error after exit is ignored)
  handlers.exit(0);
  handlers.error(new Error("late"));
  assert.deepEqual(done, [0]);
  // a start that fails reports null; a throwing spawn returns 0
  const done2 = [];
  Launcher.setupCalc("R", fake, (c) => done2.push(c));
  handlers.error(new Error("ENOENT"));
  assert.deepEqual(done2, [null]);
  const done3 = [];
  assert.equal(Launcher.setupCalc("R", () => { throw new Error("no ps"); }, (c) => done3.push(c)), 0);
  assert.deepEqual(done3, [null]);
  // an absolute SystemRoot is honoured, as for startCore
  const at = "F" + ":" + "\\" + "WINDOWS";
  const seen = [];
  Launcher.setupCalc("R", (exe) => { seen.push(exe); return { pid: 1 }; }, null, { SystemRoot: at });
  assert.deepEqual(seen, [at + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"]);
});

test("calc setup script: no parameter, BelowNormal first, the 0018 opt-in step, never setup.ps1", () => {
  const ps = fs.readFileSync(path.join(__dirname, "..", "..", "scripts", "calc_setup.ps1"), "ascii");
  const body = ps.replace(/<#[\s\S]*?#>/g, "").replace(/^\s*#[^\n]*$/gm, "");
  assert.match(body, /\[CmdletBinding\(\)\]\s*param\(\)/, "no parameter");
  // the first statement after param() lowers the script's own priority
  const after = body.slice(body.indexOf("param()") + "param()".length).trim();
  assert.ok(after.startsWith("try {\n    (Get-Process -Id $PID).PriorityClass = " +
    "[System.Diagnostics.ProcessPriorityClass]::BelowNormal"), after.slice(0, 120));
  // checkout: tools\tc_pin.py setup --opt-in; installed: installer calc --opt-in
  assert.match(body, /Join-Path \$Repo 'tools\\tc_pin\.py'\), 'setup', '--opt-in'/);
  assert.match(body, /'boot\.py'\), 'server\.al\.install', 'calc', '--opt-in'/);
  assert.match(body, /foreach \(\$name in @\('python', 'py'\)\)/);
  assert.match(body, /Join-Path \$AlHome 'runtime'/);
  assert.ok(!/setup\.ps1|npm|Start-Process|Invoke-Expression/i.test(body));
  assert.ok(/^[\x09\x0a\x20-\x7e]*$/.test(ps) && !ps.includes("\r"), "ASCII and LF");
});

test("calc setup: one sender-checked handler in main.js, one run at a time, no child_process there", () => {
  const main = code(MAIN_SRC);
  assert.equal((main.match(/"al:setup-calc"/g) || []).length, 1);
  assert.match(main, /ipcMain\.handle\("al:setup-calc", \(e\) => \{\s*if \(!client \|\| !client\.isCompanion\(e\)\) \{ return null; \}/);
  const fn = main.slice(main.indexOf("function setupCalc()"));
  const body = fn.slice(0, fn.indexOf("\n}\n"));
  assert.match(body, /if \(calcRun\) \{ return calcRun; \}/);
  assert.match(body, /Launcher\.setupCalc\(REPO, undefined, \(code\) => \{/);
  assert.match(body, /settle\(\{ ok: code === 0 \}\);/);
  assert.ok(!/child_process/.test(main));
  // the preload's fifth action passes nothing on
  const pre = code(fs.readFileSync(path.join(__dirname, "..", "client", "preload.js"), "utf8"));
  assert.match(pre, /setupCalc: \(\) => ipcRenderer\.invoke\("al:setup-calc"\)/);
});

test("the companion window is a normal, sandboxed window on its own session", () => {
  const c = code(WIN_SRC);
  for (const needle of ["contextIsolation: true", "nodeIntegration: false", "sandbox: true",
                        "session: clientSession()", 'session.fromPartition(PARTITION)',
                        "setWindowOpenHandler(", 'return { action: "deny" }',
                        '"will-navigate"', '"will-redirect"', "shell.openExternal(parsed.href)",
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
  assert.ok(c.indexOf("resolveSidecar(HOME)") > 0);
  assert.ok(c.indexOf("resolveSidecar(HOME)") < c.indexOf('app.setPath("userData"'));
  assert.ok(c.indexOf("resolveSidecar(HOME)") < c.indexOf("requestSingleInstanceLock()"));
  // REL-CLIENT-HOME: an install never sets AL_SIDECAR_ROOT (its home is the sidecar)
  assert.match(c, /if \(CLIENT_MODE && !process\.env\.AL_SIDECAR_ROOT && HOME\.mode === "checkout"\) \{/);
});

/* OVL-WAKE-COMPANION (decision 0041 amendment 2026-11-19): the companion
   comes back without focus when the log wakes, only on another display. */
const D1 = { x: 0, y: 0, width: 1920, height: 1080 };
const D2 = { x: 1920, y: 0, width: 2560, height: 1440 };

function wakeIn(extra) {
  return Object.assign({ wasIdle: true, fresh: true, hidden: true,
                         bounds: { x: 2200, y: 100, width: 1280, height: 860 },
                         overlayArea: D1, areas: [D1, D2], enabled: true }, extra || {});
}

test("wake: idle to fresh, hidden, wholly on display 2 with the overlay on 1 -> showInactive", () => {
  assert.equal(Link.wakeAction(wakeIn()), "showInactive");
  // Windows' invisible resize border of a window snapped to display 2's edge
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: 1913, y: -7, width: 1294, height: 1447 } })),
               "showInactive");
  // the overlay on display 2, the window on display 1
  assert.equal(Link.wakeAction(wakeIn({ overlayArea: D2,
                                        bounds: { x: 100, y: 100, width: 900, height: 700 } })),
               "showInactive");
});

test("wake: same display, straddling, switch off, not hidden, no wake -> stay", () => {
  // the overlay's (the game's) display: never
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: 100, y: 100, width: 900, height: 700 } })),
               "stay");
  // bounds straddling the two displays
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: 1500, y: 100, width: 1280, height: 860 } })),
               "stay");
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: 1900, y: 100, width: 1280, height: 860 } })),
               "stay");
  // the tray switch is off (or unknown)
  assert.equal(Link.wakeAction(wakeIn({ enabled: false })), "stay");
  assert.equal(Link.wakeAction(wakeIn({ enabled: undefined })), "stay");
  // the window is already shown
  assert.equal(Link.wakeAction(wakeIn({ hidden: false })), "stay");
  // no idle-to-fresh change
  assert.equal(Link.wakeAction(wakeIn({ wasIdle: false })), "stay");
  assert.equal(Link.wakeAction(wakeIn({ fresh: false })), "stay");
  // unknown: no saved bounds, no overlay display, off every display, junk
  assert.equal(Link.wakeAction(wakeIn({ bounds: null })), "stay");
  assert.equal(Link.wakeAction(wakeIn({ overlayArea: null })), "stay");
  assert.equal(Link.wakeAction(wakeIn({ areas: [D1] })), "stay");
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: 9000, y: 0, width: 900, height: 700 } })),
               "stay");
  assert.equal(Link.wakeAction(wakeIn({ bounds: { x: "a", y: 0, width: 900, height: 700 } })),
               "stay");
  assert.equal(Link.wakeAction(null), "stay");
  assert.equal(Link.wakeAction("x"), "stay");
});

test("wake part: only a false -> true gate change asks the client, once", () => {
  const Wake = require("../parts/40-wake.js");
  const calls = [];
  const client = { wake: (w) => { calls.push(w); return "showInactive"; } };
  const ctx = { getClient: () => client, log: () => {} };
  Wake.gate(ctx, true); // first value: no change seen yet
  Wake.gate(ctx, true);
  assert.deepEqual(calls, []);
  Wake.gate(ctx, false); // the log went idle
  Wake.gate(ctx, false);
  assert.deepEqual(calls, []);
  Wake.gate(ctx, true); // a fresh line
  assert.deepEqual(calls, [{ wasIdle: true, fresh: true }]);
  Wake.gate(ctx, true);
  assert.equal(calls.length, 1);
  // an overlay-only start has no client: nothing happens, nothing throws
  const bare = { getClient: () => null };
  Wake.gate(bare, false);
  Wake.gate(bare, true);
  Wake.gate(null, true);
  assert.equal(calls.length, 1);
});

test("wake in the window: showInactive only, never focus, saved state and overlay display", () => {
  const c = code(WIN_SRC);
  const body = c.slice(c.indexOf("function wake(w)"), c.indexOf("function reload()"));
  assert.ok(body.length > 0);
  assert.ok(body.includes("Link.wakeAction("));
  assert.ok(body.includes("bounds: readState()"));
  assert.ok(body.includes("overlayArea: overlayArea()"));
  assert.ok(body.includes("win.showInactive()"));
  assert.ok(body.includes("createWindow(true)"));
  for (const banned of ["focus(", ".show()", ".restore()", ".maximize()", "moveTop", "setAlwaysOnTop"]) {
    assert.ok(!body.includes(banned), banned);
  }
  assert.ok(c.includes("if (inactive === true) { win.showInactive(); return; }"));
  assert.ok(c.includes("opts.overlayBounds()"));
  // the part reads no game process or window and sends nothing
  const part = code(fs.readFileSync(path.join(__dirname, "..", "parts", "40-wake.js"), "utf8"));
  for (const banned of ["process", "exec", "globalShortcut", "require("]) {
    assert.ok(!part.includes(banned), banned);
  }
});
