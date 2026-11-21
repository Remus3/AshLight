"use strict";
/* REL-RUNTIME-SCRIPTS (F-047, DEP-06, decision 0063): the client launcher
   prefers the installed copy's private runtimes and gives its children a
   scrubbed environment. app/client/home.js pythonCmd() and childEnv() only;
   every case runs against temp folders, nothing starts. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Home = require("../client/home.js");
const Launcher = require("../client/launcher.js");

function tmp(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "al-homert-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

/* <home>/app/<version>/app with the marker at <home>/install.json. */
function installed(root, marker) {
  const home = path.join(root, "AshLight Home");
  const appDir = path.join(home, "app", "0.2.0", "app");
  fs.mkdirSync(appDir, { recursive: true });
  fs.writeFileSync(path.join(home, Home.MARKER_NAME), JSON.stringify(marker));
  return { home, appDir, payload: path.dirname(appDir) };
}

test("pythonCmd installed form: the marker's runtime runs <payload>/boot.py <module>", (t) => {
  const l = installed(tmp(t), { python: "python-3.14.10", electron: "electron-41.0.0" });
  const h = Home.resolve(l.appDir, {}, fs);
  assert.equal(h.mode, "installed");
  const rt = path.join(l.home, "runtime", "python-3.14.10");
  assert.deepEqual(Home.pythonCmd(h, "server.al.paths", []), {
    exe: path.join(rt, "python.exe"),
    args: [path.join(l.payload, "boot.py"), "server.al.paths"]
  });
  assert.deepEqual(Home.pythonCmd(h, "server.al", ["--port", 8961], { windowless: true }), {
    exe: path.join(rt, "pythonw.exe"),
    args: [path.join(l.payload, "boot.py"), "server.al", "--port", "8961"]
  });
  // never the -m form in an install (the embeddable ._pth ignores the cwd)
  assert.ok(!Home.pythonCmd(h, "server.al.paths", []).args.includes("-m"));
  // AL_HOME names the home just as the marker does
  const viaEnv = Home.resolve(l.appDir, { AL_HOME: l.home }, fs);
  assert.equal(Home.pythonCmd(viaEnv, "m", []).exe, path.join(rt, "python.exe"));
  // a checkout keeps the -m form, windowless or not
  const co = Home.resolve(path.resolve(__dirname, ".."), {}, fs);
  assert.deepEqual(Home.pythonCmd(co, "m", ["a"], { windowless: true }),
                   { exe: null, args: ["-m", "m", "a"] });
});

test("resolveSidecar runs the private runtime, never a PATH python, in an install", (t) => {
  const l = installed(tmp(t), { python: "python-3.14.10" });
  const h = Home.resolve(l.appDir, {}, fs);
  const seen = [];
  const exec = (exe, args, opts) => { seen.push({ exe, args, opts }); return JSON.stringify({ sidecar: "S" }); };
  const env = { PATH: "py-dir", ELECTRON_RUN_AS_NODE: "1", NODE_OPTIONS: "--inspect" };
  assert.equal(Launcher.resolveSidecar(h, exec, env), "S");
  assert.equal(seen.length, 1);
  assert.equal(seen[0].exe, path.join(l.home, "runtime", "python-3.14.10", "python.exe"));
  assert.deepEqual(seen[0].opts.env, { PATH: "py-dir" });
});

test("childEnv drops ELECTRON_RUN_AS_NODE and NODE_OPTIONS in any case, keeps the rest", () => {
  assert.deepEqual(Home.DROPPED_ENV, ["ELECTRON_RUN_AS_NODE", "NODE_OPTIONS"]);
  const env = {
    PATH: "x", AL_HOME: "h", AL_SIDECAR_ROOT: "s", SystemRoot: "w",
    ELECTRON_RUN_AS_NODE: "1", NODE_OPTIONS: "--require evil.js",
    electron_run_as_node: "1", Node_Options: "--inspect"
  };
  const out = Home.childEnv(env);
  assert.deepEqual(out, { PATH: "x", AL_HOME: "h", AL_SIDECAR_ROOT: "s", SystemRoot: "w" });
  // a copy: the caller's object is not changed
  assert.notEqual(out, env);
  assert.equal(env.NODE_OPTIONS, "--require evil.js");
  out.PATH = "y";
  assert.equal(env.PATH, "x");
});

test("childEnv defaults to process.env and still drops the two names", () => {
  const before = process.env.NODE_OPTIONS;
  process.env.NODE_OPTIONS = "--inspect";
  try {
    const out = Home.childEnv();
    assert.ok(!Object.keys(out).some((k) => k.toUpperCase() === "NODE_OPTIONS"));
    assert.ok(Object.keys(out).length > 0);
  } finally {
    if (before === undefined) { delete process.env.NODE_OPTIONS; } else { process.env.NODE_OPTIONS = before; }
  }
});

test("the launcher's PowerShell children get the scrubbed environment", () => {
  const calls = [];
  const fake = (exe, args, opts) => { calls.push({ exe, args, opts }); return { pid: 9, unref() {} }; };
  const env = { SystemRoot: "C" + ":" + "\\Windows", PATH: "p", ELECTRON_RUN_AS_NODE: "1", NODE_OPTIONS: "x" };
  assert.equal(Launcher.startCore("R", 0, fake, env), 9);
  assert.equal(Launcher.stopAll("R", fake, env), 9);
  for (const c of calls) {
    assert.deepEqual(c.opts.env, { SystemRoot: "C" + ":" + "\\Windows", PATH: "p" });
  }
});
