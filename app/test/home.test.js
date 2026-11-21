"use strict";
/* REL-CLIENT-HOME (F-049, DEP-05, decision 0059): the client's one path
   resolver (app/client/home.js) mirrors server/al/paths.py install_mode().
   Every case runs against temp folders or a fake fs; nothing starts. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Home = require("../client/home.js");

const APP = path.resolve(__dirname, "..");
const REPO = path.resolve(APP, "..");

function tmp(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "al-home-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

/* <home>/app/<version>/app with the marker at <home>/install.json. */
function layout(root, marker) {
  const home = path.join(root, "AshLight");
  const appDir = path.join(home, "app", "0.1.1", "app");
  fs.mkdirSync(appDir, { recursive: true });
  if (marker !== undefined) {
    fs.writeFileSync(path.join(home, Home.MARKER_NAME), JSON.stringify(marker));
  }
  return { home, appDir, payload: path.dirname(appDir) };
}

test("checkout layout equals the constants main.js used before", () => {
  const h = Home.resolve(APP, {}, fs);
  assert.equal(h.mode, "checkout");
  assert.equal(h.root, REPO);
  assert.equal(h.home, null);
  assert.equal(h.tokenFile, path.join(REPO, "ops", "runtime", "token"));
  assert.equal(h.displaysFile, path.join(REPO, "ops", "runtime", "displays.json"));
  assert.equal(h.portsPy, path.join(REPO, "server", "al", "ports.py"));
  assert.equal(h.localConfig, path.join(REPO, "config", "local.json"));
  assert.equal(h.dataDir, path.join(REPO, "ops", "runtime"));
  assert.equal(h.cacheDir, null);
  assert.equal(Home.profileDir(h, {}), path.join(REPO, "ops", "runtime", "overlay-profile"));
  // AL_SIDECAR_ROOT gives the sidecar's Cache, as run.ps1 sets it
  const side = path.join(os.tmpdir(), "al-side");
  assert.equal(Home.resolve(APP, { AL_SIDECAR_ROOT: side }, fs).cacheDir, path.join(side, "Cache"));
  assert.equal(Home.profileDir(h, { AL_SIDECAR_ROOT: side }), path.join(side, "Cache", "overlay-profile"));
  // a bare root is a checkout home (the launcher's older callers)
  assert.deepEqual(Home.asHome(REPO, {}), h);
});

test("AL_HOME names the home: player state in <home>/data", (t) => {
  const home = path.join(tmp(t), "Home");
  for (const raw of [home, " " + home + " ", '"' + home + '"']) {
    const h = Home.resolve(APP, { AL_HOME: raw }, fs);
    assert.equal(h.mode, "installed");
    assert.equal(h.home, home);
    assert.equal(h.root, REPO, "the code still runs from its own folder");
    assert.equal(h.dataDir, path.join(home, "data"));
    assert.equal(h.tokenFile, path.join(home, "data", "token"));
    assert.equal(h.localConfig, path.join(home, "data", "local.json"));
    assert.equal(h.displaysFile, path.join(home, "data", "displays.json"));
    assert.equal(h.cacheDir, path.join(home, "cache"));
    assert.equal(Home.profileDir(h, {}), path.join(home, "cache", "overlay-profile"));
    assert.equal(h.portsPy, path.join(REPO, "server", "al", "ports.py"));
  }
  // an explicit sidecar root wins for the cache, as in paths.py
  const side = path.join(tmp(t), "sc");
  assert.equal(Home.resolve(APP, { AL_HOME: home, AL_SIDECAR_ROOT: side }, fs).cacheDir,
               path.join(side, "Cache"));
  // an empty AL_HOME is a checkout
  assert.equal(Home.resolve(APP, { AL_HOME: "  " }, fs).mode, "checkout");
});

test("the marker two levels above the payload root makes an install", (t) => {
  const { home, appDir, payload } = layout(tmp(t), { python: "python-3.14.10" });
  const h = Home.resolve(appDir, {}, fs);
  assert.equal(h.mode, "installed");
  assert.equal(h.home, home);
  assert.equal(h.root, payload);
  assert.equal(h.tokenFile, path.join(home, "data", "token"));
  assert.equal(h.localConfig, path.join(home, "data", "local.json"));
  assert.equal(h.portsPy, path.join(payload, "server", "al", "ports.py"));
  assert.equal(h.pythonDir, path.join(home, "runtime", "python-3.14.10"));
  // no marker, or not the app/<version> shape: a checkout
  const bare = layout(tmp(t));
  assert.equal(Home.resolve(bare.appDir, {}, fs).mode, "checkout");
  const oroot = path.join(tmp(t), "h");
  const other = path.join(oroot, "apps", "0.1.1", "app");
  fs.mkdirSync(other, { recursive: true });
  fs.writeFileSync(path.join(oroot, Home.MARKER_NAME), "{}");
  assert.equal(Home.resolve(other, {}, fs).mode, "checkout");
});

test("the marker inside the home is the only file looked at; no listing", () => {
  const seen = [];
  const fake = {
    statSync(p) { seen.push(p); return { isFile: () => true, size: 2 }; },
    readFileSync() { return "{}"; },
    readdirSync() { throw new Error("no listing"); }
  };
  const appDir = path.join(path.parse(APP).root, "H", "app", "0.2.0", "app");
  const h = Home.resolve(appDir, {}, fake);
  assert.equal(h.mode, "installed");
  assert.ok(seen.length >= 1);
  for (const p of seen) { assert.equal(p, path.join(path.parse(APP).root, "H", Home.MARKER_NAME)); }
});

test("the steamapps and game-folder path shapes are refused, by path text only", (t) => {
  const noFs = new Proxy({}, { get() { return () => { throw new Error("no fs access"); }; } });
  const base = tmp(t);
  const bad = [
    ["Steam", "steamapps", "common", "AshLight"],
    ["SteamApps.", "x"],
    ["Games", "Path of Exile 2", "AshLight"],
    ["Games", "path of exile 2 . ", "AshLight"]
  ];
  for (const parts of bad) {
    const home = path.join(base, ...parts);
    assert.throws(() => Home.resolve(APP, { AL_HOME: home }, noFs),
                  (e) => e instanceof Home.HomeRefused && /install AshLight in its own folder/.test(e.message),
                  home);
    assert.ok(Home.homeRefusal(home));
  }
  for (const parts of [["steamapps2"], ["Path of Exile"], ["my steamapps"]]) {
    assert.equal(Home.homeRefusal(path.join(base, ...parts)), null, parts.join("/"));
  }
  // a marker home in a Steam library is refused too
  const lib = path.join(base, "steamapps", "AshLight");
  fs.mkdirSync(path.join(lib, "app", "0.1.0", "app"), { recursive: true });
  fs.writeFileSync(path.join(lib, Home.MARKER_NAME), "{}");
  assert.throws(() => Home.resolve(path.join(lib, "app", "0.1.0", "app"), {}, fs), Home.HomeRefused);
});

test("refusalNotice shows the refusal sentence once, and nothing for an accepted home", (t) => {
  const base = tmp(t);
  for (const parts of [["Steam", "steamapps", "AshLight"], ["Games", "Path of Exile 2", "AshLight"]]) {
    const home = path.join(base, ...parts);
    let err = null;
    try { Home.resolve(APP, { AL_HOME: home }, fs); } catch (e) { err = e; }
    const calls = [];
    assert.equal(Home.refusalNotice(err, (...args) => { calls.push(args); }), true);
    assert.deepEqual(calls, [[Home.homeRefusal(home)]], "exactly the sentence, once");
    assert.ok(!calls[0][0].includes(base), "no path in the notice");
  }
  // an accepted home throws nothing, so nothing is shown; other errors show nothing
  const calls = [];
  const show = (...args) => { calls.push(args); };
  assert.equal(Home.resolve(APP, { AL_HOME: path.join(base, "Home") }, fs).mode, "installed");
  assert.equal(Home.resolve(APP, {}, fs).mode, "checkout");
  assert.equal(Home.refusalNotice(new Error("disk"), show), false);
  assert.equal(Home.refusalNotice(null, show), false);
  assert.equal(Home.refusalNotice(undefined, show), false);
  assert.deepEqual(calls, []);
  // no show function: nothing thrown
  assert.equal(Home.refusalNotice(new Home.HomeRefused("x"), undefined), false);
});

test("pythonCmd: the -m form in a checkout, boot.py under the marker runtime in an install", (t) => {
  const co = Home.resolve(APP, {}, fs);
  assert.deepEqual(Home.pythonCmd(co, "server.al.paths", []), { exe: null, args: ["-m", "server.al.paths"] });
  assert.deepEqual(Home.pythonCmd(REPO, "server.al", ["--check", 3]),
                   { exe: null, args: ["-m", "server.al", "--check", "3"] });
  const { home, appDir, payload } = layout(tmp(t), { python: "python-3.14.10" });
  const h = Home.resolve(appDir, {}, fs);
  assert.deepEqual(Home.pythonCmd(h, "server.al.paths", []), {
    exe: path.join(home, "runtime", "python-3.14.10", "python.exe"),
    args: [path.join(payload, "boot.py"), "server.al.paths"]
  });
  // a marker naming no usable folder: no exe (the launcher looks one up)
  for (const bad of ["..", "", "a/b", "..\\x", "C:x", 7, null]) {
    const l = layout(tmp(t), { python: bad });
    const hb = Home.resolve(l.appDir, {}, fs);
    assert.equal(hb.pythonDir, null, String(bad));
    assert.equal(Home.pythonCmd(hb, "m", []).exe, null);
  }
  const torn = layout(tmp(t));
  fs.writeFileSync(path.join(torn.home, Home.MARKER_NAME), "{not json");
  assert.equal(Home.resolve(torn.appDir, {}, fs).pythonDir, null);
});

test("childEnv drops nothing yet and returns a copy", () => {
  const env = { A: "1", PATH: "x", AL_HOME: "h" };
  const out = Home.childEnv(env);
  assert.deepEqual(out, env);
  assert.notEqual(out, env);
});
