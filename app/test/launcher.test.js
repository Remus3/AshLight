"use strict";
/* REL-UPDATE-LAUNCH (F-077, DEP-11): the client launcher applies a staged
   update before the core starts. app/client/launcher.js applyStaged(),
   relaunch(), startConfirm() and startCore() run against temp install
   folders with fake exec / spawn; nothing starts. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Home = require("../client/home.js");
const Launcher = require("../client/launcher.js");

const ENV = { SystemRoot: "C" + ":" + "\\Windows", PATH: "p", NODE_OPTIONS: "x" };
const RUNTIME_PY = "python-3.14.10";
const RUNTIME_EL = "electron-45.3.3";

function tmp(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "al-launch-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

/* <home>/app/<version>/app, <home>/install.json and the electron.exe of
   the marker's runtime (an empty file: nothing runs it). */
function installed(root, marker) {
  const home = path.join(root, "AshLight Home");
  const doc = Object.assign({ version: "0.2.0", python: RUNTIME_PY, electron: RUNTIME_EL,
                              pending_confirm: false, start_attempts: 0 }, marker || {});
  for (const v of ["0.2.0", "0.3.0"]) {
    fs.mkdirSync(path.join(home, "app", v, "app"), { recursive: true });
  }
  const el = path.join(home, "runtime", RUNTIME_EL);
  fs.mkdirSync(el, { recursive: true });
  fs.writeFileSync(path.join(el, "electron.exe"), "");
  fs.writeFileSync(path.join(home, Home.MARKER_NAME), JSON.stringify(doc));
  const appDir = path.join(home, "app", "0.2.0", "app");
  return { home, appDir, payload: path.dirname(appDir), h: Home.resolve(appDir, {}, fs) };
}

function setMarker(home, patch) {
  const file = path.join(home, Home.MARKER_NAME);
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  fs.writeFileSync(file, JSON.stringify(Object.assign(doc, patch)));
}

/* A recorder: one ordered list of exec / spawn calls. exec answers with
   code (0 returns out, any other code throws as execFileSync does). */
function recorder(code, out, onExec) {
  const calls = [];
  const exec = (exe, args, opts) => {
    calls.push({ kind: "exec", exe, args, opts });
    if (onExec) { onExec(); }
    if (code === 0) { return out || ""; }
    const err = new Error("exit " + code);
    err.status = code;
    err.stdout = out || "";
    throw err;
  };
  const spawn = (exe, args, opts) => {
    calls.push({ kind: "spawn", exe, args, opts });
    return { pid: 100 + calls.length, unref() {}, on() {} };
  };
  return { calls, exec, spawn };
}

function isRunPs1(c) {
  return c.kind === "spawn" && c.args.includes("-File") &&
    /scripts[\\/]run\.ps1$/.test(c.args[c.args.indexOf("-File") + 1]);
}

test("checkout mode: nothing changes, no installer process", () => {
  const r = recorder(0);
  assert.equal(Launcher.applyStaged("R", r.exec, ENV), null);
  assert.equal(Launcher.relaunch("R", r.spawn, ENV), 0);
  assert.equal(Launcher.startConfirm("R", r.spawn, ENV), 0);
  let exited = false;
  const pid = Launcher.startCore("R", 8961, r.spawn, ENV, { exec: r.exec, exit: () => { exited = true; } });
  assert.equal(r.calls.length, 1);
  assert.ok(isRunPs1(r.calls[0]));
  assert.equal(r.calls[0].opts.cwd, "R");
  assert.equal(pid, r.calls.length + 100);
  assert.equal(exited, false);
  // a checkout home object is the same
  const co = Home.resolve(path.resolve(__dirname, ".."), {}, fs);
  assert.equal(co.mode, "checkout");
  assert.equal(Launcher.applyStaged(co, r.exec, ENV), null);
  assert.equal(r.calls.filter((c) => c.kind === "exec").length, 0);
});

test("installed mode: applyStaged runs before startCore; a no-op costs one hidden process", (t) => {
  const l = installed(tmp(t));
  const r = recorder(0, "apply-staged: nothing staged\n");
  const lines = [];
  Launcher.startCore(l.h, 8960, r.spawn, ENV, { exec: r.exec, fs: fs, log: (m) => lines.push(m),
                                                exit: () => assert.fail("no exit on a no-op") });
  assert.equal(r.calls.length, 2);
  const [apply, run] = r.calls;
  assert.equal(apply.kind, "exec");
  assert.equal(apply.exe, path.join(l.home, "runtime", RUNTIME_PY, "python.exe"));
  assert.deepEqual(apply.args, [path.join(l.payload, "boot.py"), "server.al.install",
                                "apply-staged", "--if-due", "--home", l.home]);
  assert.equal(apply.opts.windowsHide, true);
  assert.equal(apply.opts.cwd, l.payload);
  assert.deepEqual(apply.opts.env, Home.childEnv(ENV));
  assert.ok(apply.opts.timeout > 0);
  assert.ok(isRunPs1(run));
  assert.equal(run.opts.cwd, l.payload);
  // nothing pending: no confirm helper
  assert.ok(!r.calls.some((c) => c.args.includes("confirm")));
  assert.deepEqual(lines, ["update: apply-staged: nothing staged"]);
});

test("the payload root text (window.js's opts.repo) resolves to the install", (t) => {
  const l = installed(tmp(t));
  const r = recorder(0);
  Launcher.startCore(l.payload, 0, r.spawn, ENV, { exec: r.exec, fs: fs, log: () => {} });
  assert.equal(r.calls[0].kind, "exec");
  assert.ok(isRunPs1(r.calls[1]));
});

test("after a switch the client starts from the marker's version and this process exits", (t) => {
  const l = installed(tmp(t));
  const r = recorder(Launcher.EXIT_SWITCHED, "apply-staged: switched 0.2.0 to 0.3.0\n",
                     () => setMarker(l.home, { version: "0.3.0", previous: "0.2.0",
                                               pending_confirm: true }));
  let exits = 0;
  const lines = [];
  const pid = Launcher.startCore(l.h, 8960, r.spawn, ENV,
                                 { exec: r.exec, fs: fs, exit: () => { exits += 1; }, log: (m) => lines.push(m) });
  assert.equal(pid, 0);
  assert.equal(exits, 1);
  assert.equal(r.calls.length, 2);
  const re = r.calls[1];
  assert.equal(re.kind, "spawn");
  assert.equal(re.exe, path.join(l.home, "runtime", RUNTIME_EL, "electron.exe"));
  const newApp = path.join(l.home, "app", "0.3.0", "app");
  assert.deepEqual(re.args, [newApp, "--client"]);
  assert.equal(re.opts.cwd, newApp);
  assert.equal(re.opts.detached, true);
  assert.equal(re.opts.windowsHide, true);
  assert.deepEqual(re.opts.env, Home.childEnv(ENV));
  // the old version's run.ps1 never starts: the new core serves its own pages
  assert.ok(!r.calls.some(isRunPs1));
  assert.deepEqual(lines, ["update: apply-staged: switched 0.2.0 to 0.3.0"]);
});

test("a switch whose new runtime is missing goes on with this start", (t) => {
  const l = installed(tmp(t));
  const r = recorder(Launcher.EXIT_SWITCHED, "",
                     () => setMarker(l.home, { version: "0.3.0", electron: "electron-99.0.0" }));
  let exits = 0;
  Launcher.startCore(l.h, 0, r.spawn, ENV, { exec: r.exec, fs: fs, exit: () => { exits += 1; }, log: () => {} });
  assert.equal(exits, 0);
  assert.ok(r.calls.some(isRunPs1));
  // a marker naming a path instead of a folder is refused
  setMarker(l.home, { version: "..\\x", electron: RUNTIME_EL });
  assert.equal(Launcher.relaunch(l.h, r.spawn, ENV, fs), 0);
});

test("while pending_confirm is true each start bumps the attempt first; confirm starts after startCore", (t) => {
  const l = installed(tmp(t), { version: "0.3.0", previous: "0.2.0", pending_confirm: true });
  const r = recorder(0, "apply-staged: start 1 of 0.3.0 counted\n");
  Launcher.startCore(l.h, 8960, r.spawn, ENV, { exec: r.exec, fs: fs, log: () => {},
                                                exit: () => assert.fail("no exit") });
  assert.deepEqual(r.calls.map((c) => c.kind), ["exec", "spawn", "spawn"]);
  // the installer (which bumps start_attempts while pending) runs first
  assert.ok(r.calls[0].args.includes("apply-staged"));
  assert.ok(isRunPs1(r.calls[1]));
  const confirm = r.calls[2];
  assert.equal(confirm.exe, path.join(l.home, "runtime", RUNTIME_PY, "pythonw.exe"));
  assert.deepEqual(confirm.args, [path.join(l.payload, "boot.py"), "server.al.install",
                                  "confirm", "--wait", "--home", l.home]);
  assert.equal(confirm.opts.detached, true);
  assert.equal(confirm.opts.windowsHide, true);
  assert.equal(confirm.opts.stdio, "ignore");
  assert.deepEqual(confirm.opts.env, Home.childEnv(ENV));
});

test("a missing python or a failing installer never blocks the start", (t) => {
  // the marker names no python runtime: no installer process at all
  const l = installed(tmp(t), { python: "", pending_confirm: true });
  assert.equal(l.h.pythonDir, null);
  const r = recorder(0);
  Launcher.startCore(l.h, 0, r.spawn, ENV, { exec: r.exec, fs: fs, log: () => {} });
  assert.equal(r.calls.length, 1);
  assert.ok(isRunPs1(r.calls[0]));
  // an installer that fails, is busy, or cannot run at all (ENOENT, timeout)
  const l2 = installed(tmp(t));
  for (const code of [1, 2, 3, null]) {
    const f = recorder(code === null ? 1 : code);
    const exec = code === null
      ? (exe, args, opts) => { f.calls.push({ kind: "exec", exe, args, opts }); throw new Error("ENOENT"); }
      : f.exec;
    let exited = false;
    const pid = Launcher.startCore(l2.h, 0, f.spawn, ENV,
                                   { exec: exec, fs: fs, exit: () => { exited = true; }, log: () => {} });
    assert.equal(exited, false);
    assert.ok(f.calls.some(isRunPs1), "run.ps1 starts after installer code " + code);
    assert.ok(pid > 0);
  }
  assert.deepEqual(Launcher.applyStaged(l2.h, () => { throw new Error("ENOENT"); }, ENV),
                   { code: null, line: "" });
  // a confirm helper that cannot start is ignored
  setMarker(l2.home, { pending_confirm: true });
  assert.equal(Launcher.startConfirm(l2.h, () => { throw new Error("no pythonw"); }, ENV, fs), 0);
});

/* REL-UPDATE-APPLY-NOW: one 'Update now' click finishes the update. The
   core writes <data>/apply_now.request after the click's staging run; the
   client takes it, stops the core through stop.request, waits for it to be
   gone and runs apply-staged (no --if-due), then relaunches or restarts. */
function applyOpts(r, events, extra) {
  return Object.assign({
    exec: r.exec, spawn: r.spawn, fs: fs, env: ENV, log: () => {},
    exit: () => events.push("exit"), sleep: () => Promise.resolve(), waitMs: 1000, stepMs: 1
  }, extra || {});
}

test("applyNow: stop.request first, apply-staged only once the core is gone, then relaunch", async (t) => {
  const l = installed(tmp(t));
  fs.mkdirSync(l.h.dataDir, { recursive: true });
  const stopFile = path.join(l.h.dataDir, "stop.request");
  const events = [];
  let up = 2; // the core answers twice more after the stop request
  const r = recorder(Launcher.EXIT_SWITCHED, "apply-staged: switched 0.2.0 to 0.3.0\n", () => {
    events.push("apply:" + fs.existsSync(stopFile));
    setMarker(l.home, { version: "0.3.0", previous: "0.2.0", pending_confirm: true });
  });
  const check = () => {
    events.push("check:" + fs.existsSync(stopFile));
    up -= 1;
    return Promise.resolve(up >= 0);
  };
  const word = await Launcher.applyNow(l.h, 8960, applyOpts(r, events, { check: check }));
  assert.equal(word, "switched");
  assert.deepEqual(events, ["check:true", "check:true", "check:true", "apply:true", "exit"]);
  const apply = r.calls[0];
  assert.equal(apply.kind, "exec");
  assert.deepEqual(apply.args, [path.join(l.payload, "boot.py"), "server.al.install",
                                "apply-staged", "--home", l.home]);
  assert.equal(apply.opts.windowsHide, true);
  // relaunched from the new version; the old run.ps1 never starts
  assert.equal(r.calls[1].kind, "spawn");
  assert.equal(r.calls[1].args[0], path.join(l.home, "app", "0.3.0", "app"));
  assert.ok(!r.calls.some(isRunPs1));
});

test("applyNow: nothing switched (busy or failed) restarts the core through run.ps1", async (t) => {
  const l = installed(tmp(t));
  for (const code of [0, 2, 3]) {
    const events = [];
    const r = recorder(code, "apply-staged: a core of this home runs; not switched\n");
    const word = await Launcher.applyNow(l.h, 8960, applyOpts(r, events, {
      check: () => Promise.resolve(false)
    }));
    assert.equal(word, "restarted");
    assert.ok(!r.calls[0].args.includes("--if-due"));
    assert.ok(r.calls.some(isRunPs1), "run.ps1 after code " + code);
    assert.ok(!events.includes("exit"));
  }
});

test("applyNow: a core that never goes away still ends in a restart, never a hang", async (t) => {
  const l = installed(tmp(t));
  const events = [];
  const r = recorder(3, "");
  let clock = 0;
  const word = await Launcher.applyNow(l.h, 0, applyOpts(r, events, {
    check: () => Promise.resolve(true), now: () => clock,
    sleep: () => { clock += 500; return Promise.resolve(); }
  }));
  assert.equal(word, "busy");
  assert.ok(r.calls.some(isRunPs1));
  assert.ok(!events.includes("exit"));
});

test("applyNow: a checkout does nothing", async (t) => {
  const r = recorder(0);
  const events = [];
  const word = await Launcher.applyNow("R", 8961, applyOpts(r, events, {
    check: () => { events.push("check"); return Promise.resolve(false); }
  }));
  assert.equal(word, "checkout");
  assert.deepEqual(r.calls, []);
  assert.deepEqual(events, []);
});

test("takeApplyRequest: a valid request is taken once; anything else is dropped", (t) => {
  const dir = tmp(t);
  const file = path.join(dir, Launcher.APPLY_REQUEST_FILE);
  assert.equal(Launcher.APPLY_REQUEST_FILE, "apply_now.request");
  assert.equal(Launcher.takeApplyRequest(dir, fs), null);
  fs.writeFileSync(file, JSON.stringify({ version: "0.3.0" }));
  assert.equal(Launcher.takeApplyRequest(dir, fs), "0.3.0");
  assert.equal(fs.existsSync(file), false);
  assert.equal(Launcher.takeApplyRequest(dir, fs), null);
  for (const bad of ["{", "[]", JSON.stringify({ version: "..\\x" }), JSON.stringify({}),
                     JSON.stringify({ version: "x".repeat(5000) })]) {
    fs.writeFileSync(file, bad);
    assert.equal(Launcher.takeApplyRequest(dir, fs), null, bad.slice(0, 20));
    assert.equal(fs.existsSync(file), false);
  }
});

test("child_process stays in launcher.js only", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "client", "launcher.js"), "utf8");
  assert.match(src, /require\("child_process"\)/);
  for (const name of ["window.js", "home.js"]) {
    const other = fs.readFileSync(path.join(__dirname, "..", "client", name), "utf8");
    assert.ok(!/require\("child_process"\)/.test(other), name);
  }
});
