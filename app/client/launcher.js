"use strict";
/* DESKTOP-CLIENT (decision 0041): the companion's only process starts.
   It never starts a process of its own design: it runs the repo's own
   scripts (scripts\run.ps1 converges core + supervisor + overlay, decision
   0010; scripts\stop.ps1 stops them) and the one path resolver
   (python -m server.al.paths) and REL-AUTOSTART-SWITCH's scripts\autostart.ps1
   (decision 0011) and TC-CALC-OPTIN-BUTTON's scripts\calc_setup.ps1
   (decision 0018 opt-in). Nothing here touches the game (ToS floor).
   This is the one app/ file allowed to load child_process
   (tests/test_overlay_smoke.py P4-6).
   OVL-LAUNCH-ENV (F-110, audit S5): a bare name would also be looked up in
   the child's working directory (the repo), so a planted powershell.exe or
   python.exe there would run. PowerShell runs by its absolute System32
   path (psExe) and Python only from an absolute PATH entry (whichAbs, the
   which_abs rule of server/al/exepin.py).
   REL-CLIENT-HOME (F-049): resolveSidecar(), startCore() and stopAll() take
   their script path, cwd, Python command and child environment from the
   one client resolver (app/client/home.js); a bare repository root still
   works (a checkout home).
   REL-UPDATE-LAUNCH (F-077, DEP-11): in an installed copy startCore() first
   runs the installer's own 'apply-staged --if-due' (applyStaged, one hidden
   process when nothing is staged). Exit 10 means the marker moved
   (switched, or rolled back at the third start without a confirm): the
   client is started again from the marker's version (relaunch) and this
   process exits, so the new version's core serves its own web files
   (research 0050 F31). While pending_confirm is true the installer counts
   the start before anything else; after run.ps1 the installer's hidden,
   detached 'confirm --wait' (startConfirm) polls this home's /api/health
   for the marker version. A missing Python or a failing installer never
   blocks the start. A checkout changes nothing. */

const childProcess = require("child_process");
const path = require("path");
const Home = require("./home.js");

const PYTHONS = ["python", "py"];

function isDriveRoot(p) {
  return typeof p === "string" && /^[A-Za-z]:[\\/]/.test(p);
}

/* Absolute path of Windows PowerShell 5.1: %SystemRoot%\System32\
   WindowsPowerShell\v1.0\powershell.exe, SystemRoot used only when it is an
   absolute drive path, else <SystemDrive>\Windows (SystemDrive "X:", else
   C:), as server/al/exepin.py system_dir does. Never a bare name. */
function psExe(env) {
  const e = env || process.env;
  let drive = String(e.SystemDrive || e.SYSTEMDRIVE || "");
  if (!/^[A-Za-z]:$/.test(drive)) { drive = "C:"; }
  let root = e.SystemRoot || e.SYSTEMROOT || "";
  if (!isDriveRoot(root)) { root = drive + "\\Windows"; }
  return path.win32.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
}

function isFile(fsMod, p) {
  try { return fsMod.statSync(p).isFile(); } catch (e) { /* below */ }
  try { return !fsMod.lstatSync(p).isDirectory(); } catch (e) { return false; }
}

/* First match of name (plus each PATHEXT extension on Windows) in an
   ABSOLUTE PATH entry; the current directory, empty, relative and UNC
   entries are skipped. "" when not found. */
function whichAbs(name, env, fsMod) {
  const e = env || process.env;
  const f = fsMod || require("fs");
  const win = process.platform === "win32" || Object.prototype.hasOwnProperty.call(e, "PATHEXT");
  const exts = [""];
  if (win) {
    for (const x of String(e.PATHEXT || ".COM;.EXE;.BAT;.CMD").split(";")) { if (x) { exts.push(x); } }
  }
  const sep = win ? ";" : path.delimiter;
  const raw = e.PATH !== undefined ? e.PATH : (e.Path !== undefined ? e.Path : "");
  for (let entry of String(raw || "").split(sep)) {
    entry = entry.trim().replace(/^"+|"+$/g, "");
    if (!entry || entry.startsWith("\\\\") || entry.startsWith("//")) { continue; }
    const abs = win ? isDriveRoot(entry) : path.isAbsolute(entry);
    if (!abs) { continue; }
    for (const ext of exts) {
      const cand = win ? path.win32.join(entry, name + ext) : path.join(entry, name + ext);
      if (isFile(f, cand)) { return cand; }
    }
  }
  return "";
}

function psArgs(script, extra) {
  return ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
          "-WindowStyle", "Hidden", "-File", script].concat(extra || []);
}

/* The AL sidecar root from server.al.paths, or "" when Python is missing.
   Used only when the client was started without AL_SIDECAR_ROOT (a Start
   Menu shortcut), so the Electron profile and the single-instance lock are
   the same ones scripts\run.ps1 gives the overlay. home is a resolve()
   result of app/client/home.js or a repository root; the command is
   Home.pythonCmd's ("-m" form in a checkout, python looked up in an
   absolute PATH entry; boot.py under the marker's runtime in an install). */
function resolveSidecar(home, exec, env, fsMod) {
  const run = exec || childProcess.execFileSync;
  const h = Home.asHome(home, env);
  const cmd = Home.pythonCmd(h, "server.al.paths", []);
  const exes = cmd.exe ? [cmd.exe] : PYTHONS.map((name) => whichAbs(name, env, fsMod));
  for (const py of exes) {
    if (!py) { continue; }
    try {
      const out = run(py, cmd.args, {
        cwd: h.root, env: Home.childEnv(env), windowsHide: true, timeout: 15000, encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"]
      });
      const doc = JSON.parse(String(out));
      if (doc && typeof doc.sidecar === "string" && doc.sidecar) { return doc.sidecar; }
    } catch (e) { /* next */ }
  }
  return "";
}

/* REL-UPDATE-LAUNCH: the installer's exit code that means "the marker
   moved, start again from it" (server/al/install/switch.py EXIT_SWITCHED). */
const EXIT_SWITCHED = 10;
const INSTALLER_MODULE = "server.al.install";
const APPLY_TIMEOUT_MS = 120000;
const MARKER_MAX_BYTES = 64 * 1024;

/* A home object for startCore: the given resolve() result, else the
   resolve() of a repository / payload root (window.js passes the root
   text, the same root main.js resolved its HOME from), else a checkout. */
function resolvedHome(home, env, fsMod) {
  if (home && typeof home === "object" && typeof home.root === "string") { return home; }
  const root = String(home || "");
  // the marker alone decides here: a bare root stays a checkout even when
  // AL_HOME is set (an installed payload always has the marker at
  // <home>/install.json two levels above it)
  const e = Object.assign({}, env || process.env);
  for (const k of Object.keys(e)) { if (k.toUpperCase() === Home.HOME_ENV) { delete e[k]; } }
  try {
    const h = Home.resolve(path.join(root, "app"), e, fsMod || require("fs"));
    if (h.mode === "installed") { return h; }
  } catch (e) { /* a refused home starts as before: a checkout */ }
  return Home.checkout(root, env);
}

/* <home>/install.json as an object; {} when missing, too big or broken. */
function readMarker(home, fsMod) {
  const f = fsMod || require("fs");
  const file = path.join(home, Home.MARKER_NAME);
  try {
    if (f.statSync(file).size > MARKER_MAX_BYTES) { return {}; }
    const doc = JSON.parse(String(f.readFileSync(file, "utf8")).replace(/^\uFEFF/, ""));
    return doc && typeof doc === "object" && !Array.isArray(doc) ? doc : {};
  } catch (e) {
    return {};
  }
}

/* One plain folder name (no separator or colon, not dots / spaces only), else null. */
function plainName(name) {
  if (typeof name !== "string" || !name.replace(/^[. ]+|[. ]+$/g, "") || /[\\/:]/.test(name)) {
    return null;
  }
  return name;
}

/* Run 'installer apply-staged --if-due --home <home>' hidden and wait for
   it. Returns {code, line}: code is the installer's exit code (null when
   it could not run or timed out; the start goes on), line its last output
   line ("" when none). A checkout, or an install whose marker names no
   usable Python, runs nothing and returns null. */
function applyStaged(home, exec, env, ifDue) {
  const h = Home.asHome(home, env);
  if (h.mode !== "installed" || !h.home) { return null; }
  const args = ifDue === false ? ["apply-staged", "--home", h.home]
    : ["apply-staged", "--if-due", "--home", h.home];
  const cmd = Home.pythonCmd(h, INSTALLER_MODULE, args);
  if (!cmd.exe) { return null; }
  const run = exec || childProcess.execFileSync;
  let code = 0;
  let out = "";
  try {
    out = run(cmd.exe, cmd.args, {
      cwd: h.root, env: Home.childEnv(env), windowsHide: true, timeout: APPLY_TIMEOUT_MS,
      encoding: "utf8", stdio: ["ignore", "pipe", "ignore"]
    });
  } catch (e) {
    code = e && Number.isInteger(e.status) ? e.status : null;
    out = (e && e.stdout) || "";
  }
  const lines = String(out || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  return { code: code, line: lines.length ? lines[lines.length - 1] : "" };
}

/* Start the client again from the marker's version:
   <home>/runtime/<electron>/electron.exe "<home>/app/<version>/app" --client,
   detached and hidden, as the Start Menu shortcut does
   (server/al/install/shell.py). Returns the child pid, or 0 when the marker
   names no usable version / runtime or the start failed (the caller then
   goes on in this process). */
function relaunch(home, spawn, env, fsMod) {
  const f = fsMod || require("fs");
  const h = Home.asHome(home, env);
  if (h.mode !== "installed" || !h.home) { return 0; }
  const marker = readMarker(h.home, f);
  const version = plainName(marker.version);
  const electron = plainName(marker.electron);
  if (!version || !electron) { return 0; }
  const exe = path.join(h.home, Home.RUNTIME_FOLDER, electron, "electron.exe");
  const appDir = path.join(h.home, Home.APP_FOLDER, version, "app");
  if (!isFile(f, exe)) { return 0; }
  const run = spawn || childProcess.spawn;
  try {
    const child = run(exe, [appDir, "--client"], {
      cwd: appDir, env: Home.childEnv(env), detached: true, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.on === "function") { child.on("error", () => {}); }
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* Start 'installer confirm --wait --home <home>' hidden and detached
   (pythonw): it polls this home's own /api/health until the marker's
   version answers, then clears pending_confirm. Only while the marker's
   pending_confirm is true. Returns the child pid or 0. */
function startConfirm(home, spawn, env, fsMod) {
  const h = Home.asHome(home, env);
  if (h.mode !== "installed" || !h.home) { return 0; }
  if (readMarker(h.home, fsMod).pending_confirm !== true) { return 0; }
  const cmd = Home.pythonCmd(h, INSTALLER_MODULE, ["confirm", "--wait", "--home", h.home],
                             { windowless: true });
  if (!cmd.exe) { return 0; }
  const run = spawn || childProcess.spawn;
  try {
    const child = run(cmd.exe, cmd.args, {
      cwd: h.root, env: Home.childEnv(env), detached: true, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.on === "function") { child.on("error", () => {}); }
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* This process ends after a relaunch: Electron's app.exit when running in
   Electron (the single-instance lock is freed for the new client), else
   process.exit. */
function exitNow() {
  let app = null;
  try { app = require("electron").app; } catch (e) { app = null; }
  if (app && typeof app.exit === "function") { app.exit(0); } else { process.exit(0); }
}

/* Start scripts\run.ps1 -NoBrowser hidden. Not detached: a detached
   powershell got no console and exited at once without running; run.ps1
   detaches the core and supervisor itself (WMI). It converges to one
   core, one supervisor and (this process already being the overlay) no
   second overlay. Returns the child pid or 0.
   REL-UPDATE-LAUNCH: in an installed copy applyStaged runs first; on exit
   10 the client is relaunched from the marker and this process exits
   (0 is returned when exit is injected); after run.ps1 startConfirm runs.
   opts (tests): {exec, fs, exit, log}; log gets the installer's one line
   that names the version. */
function startCore(home, port, spawn, env, opts) {
  const o = opts || {};
  const run = spawn || childProcess.spawn;
  const h = resolvedHome(home, env, o.fs);
  const root = h.root;
  const say = typeof o.log === "function" ? o.log
    : (m) => { try { process.stderr.write("AshLight: " + m + "\n"); } catch (e) { /* none */ } };
  if (h.mode === "installed") {
    const res = applyStaged(h, o.exec, env);
    if (res && res.line) { say("update: " + res.line); }
    if (res && res.code === EXIT_SWITCHED && relaunch(h, run, env, o.fs)) {
      (typeof o.exit === "function" ? o.exit : exitNow)();
      return 0;
    }
  }
  const extra = ["-NoBrowser"];
  if (Number.isInteger(port) && port > 0) { extra.push("-Port", String(port)); }
  let pid = 0;
  try {
    const child = run(psExe(env), psArgs(path.join(root, "scripts", "run.ps1"), extra), {
      cwd: root, env: Home.childEnv(env), detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    pid = (child && child.pid) || 0;
  } catch (e) {
    pid = 0;
  }
  if (h.mode === "installed") { startConfirm(h, run, env, o.fs); }
  return pid;
}

/* Stop everything (scripts\stop.ps1: core, supervisor, overlay). */
function stopAll(home, spawn, env) {
  const run = spawn || childProcess.spawn;
  const root = Home.asHome(home, env).root;
  try {
    const child = run(psExe(env), psArgs(path.join(root, "scripts", "stop.ps1")), {
      cwd: root, env: Home.childEnv(env), detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* REL-UPDATE-APPLY-NOW (F-077, decision 0065): one 'Update now' click
   finishes the update. After the click's staging run the core writes
   <data>/apply_now.request ({"version"}; server/al/core.py _ask_apply).
   takeApplyRequest() reads it (at most 4 KB) and always removes it, so a
   request is acted on once; it returns the version when it is a plain
   SemVer text, else null. Never throws. */
const APPLY_REQUEST_FILE = "apply_now.request";
const APPLY_REQUEST_MAX_BYTES = 4096;
const STOP_FILE = "stop.request";
const CORE_ALIVE_FILE = "core.alive";
const STOP_WAIT_MS = 20000;  // stop.ps1's clean-exit wait is 15 s
const STOP_STEP_MS = 500;
const VERSION_RE = /^[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}(-[0-9A-Za-z.-]{1,40})?$/;

function takeApplyRequest(runtimeDir, fsMod) {
  const f = fsMod || require("fs");
  const file = path.join(String(runtimeDir || ""), APPLY_REQUEST_FILE);
  let doc = null;
  try {
    const st = f.statSync(file);
    if (st.isFile() && st.size <= APPLY_REQUEST_MAX_BYTES) {
      const text = String(f.readFileSync(file, "utf8"));
      doc = JSON.parse(text.charCodeAt(0) === 0xfeff ? text.slice(1) : text); // a BOM is dropped
    }
  } catch (e) {
    doc = null;
  }
  try { f.unlinkSync(file); } catch (e) { /* missing: nothing to take */ }
  const v = doc && typeof doc === "object" && !Array.isArray(doc) ? doc.version : null;
  return typeof v === "string" && VERSION_RE.test(v) ? v : null;
}

/* Stop the core through stop.request, wait until it is gone, apply the
   staged version at once and start again. In an installed copy only:
   1. write <data>/stop.request (the user-stop file scripts\stop.ps1 writes:
      the core exits cleanly and the supervisor exits too, so nothing
      restarts the old core during the switch);
   2. wait (at most STOP_WAIT_MS) until o.check() (the hello health check)
      says the core is down and core.alive is gone;
   3. run 'installer apply-staged --home <home>' (no --if-due: the click
      skips the 24 h hold, switch.apply's "Update now" case);
   4. exit 10 and a relaunch from the marker's version: this process exits
      ("switched"); anything else: startCore() as at a normal start
      (run.ps1 removes stop.request), "restarted", or "busy" when the core
      never went away (apply is then not run; the release still applies at
      the next client start). A checkout does nothing ("checkout").
   o (tests): {check, exec, spawn, fs, env, exit, log, sleep, now, waitMs,
   stepMs}. Resolves one fixed word; never rejects. */
function applyNow(home, port, opts) {
  const o = opts || {};
  const f = o.fs || require("fs");
  const env = o.env;
  const h = resolvedHome(home, env, f);
  const say = typeof o.log === "function" ? o.log : () => {};
  if (h.mode !== "installed" || !h.home) { return Promise.resolve("checkout"); }
  const restart = (word) => {
    startCore(h, port, o.spawn, env, { exec: o.exec, fs: f, exit: o.exit, log: o.log });
    return word;
  };
  try {
    f.mkdirSync(h.dataDir, { recursive: true });
    f.writeFileSync(path.join(h.dataDir, STOP_FILE), "update\n");
  } catch (e) {
    say("update: stop request not written; the update applies at the next start");
    return Promise.resolve("failed");
  }
  const check = typeof o.check === "function" ? o.check : () => Promise.resolve(false);
  const clock = typeof o.now === "function" ? o.now : Date.now;
  const pause = typeof o.sleep === "function" ? o.sleep
    : (ms) => new Promise((r) => setTimeout(r, ms));
  const waitMs = typeof o.waitMs === "number" ? o.waitMs : STOP_WAIT_MS;
  const stepMs = typeof o.stepMs === "number" ? o.stepMs : STOP_STEP_MS;
  const end = clock() + waitMs;
  const aliveFile = path.join(h.dataDir, CORE_ALIVE_FILE);
  function gone() {
    return Promise.resolve().then(check).then((up) => up === true, () => false)
      .then((up) => !up && !isFile(f, aliveFile));
  }
  function round() {
    return gone().then((down) => {
      if (down) { return true; }
      if (clock() >= end) { return false; }
      return Promise.resolve(pause(stepMs)).then(round);
    });
  }
  return round().then((down) => {
    if (!down) {
      say("update: the core did not stop; the update applies at the next start");
      return restart("busy");
    }
    const res = applyStaged(h, o.exec, env, false);
    if (res && res.line) { say("update: " + res.line); }
    if (res && res.code === EXIT_SWITCHED && relaunch(h, o.spawn, env, f)) {
      (typeof o.exit === "function" ? o.exit : exitNow)();
      return "switched";
    }
    return restart("restarted");
  }).catch(() => "failed");
}

/* REL-AUTOSTART-SWITCH (decision 0011, ruling Q-08): tray "Start with
   Windows". Runs scripts\autostart.ps1 -Enable or -Disable hidden, with no
   other script argument; the script registers or removes the logon task and
   records the choice in <runtime>\autostart.json. done(code), when given,
   is called once the script exits (code null when it could not start).
   Returns the child pid or 0. */
function setAutostart(repo, on, spawn, done, env) {
  const run = spawn || childProcess.spawn;
  const flag = on === true ? "-Enable" : "-Disable";
  const finish = typeof done === "function" ? done : () => {};
  try {
    const child = run(psExe(env), psArgs(path.join(repo, "scripts", "autostart.ps1"), [flag]), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.on === "function") {
      let called = false;
      const once = (code) => { if (!called) { called = true; finish(code); } };
      child.on("exit", (code) => once(code));
      child.on("error", () => once(null));
    }
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    finish(null);
    return 0;
  }
}

/* TC-CALC-OPTIN-BUTTON (decision 0041 amendment 2026-11-20, rulings Q-08,
   W16-1, W16-2): the Checks "Set up the calc" button. Runs the fixed
   scripts\calc_setup.ps1 hidden, with no script argument, by the absolute
   System32 PowerShell (psExe); not detached, as startCore. The script sets
   its own priority to BelowNormal first and runs the decision 0018 opt-in
   (tools/tc_pin.py setup --opt-in in a checkout, installer calc --opt-in
   in an installed copy; never setup.ps1). done(code), when given, is
   called once the script exits (code null when it could not start).
   Returns the child pid or 0. */
const CALC_SETUP_PS1 = "calc_setup.ps1";

function setupCalc(repo, spawn, done, env) {
  const run = spawn || childProcess.spawn;
  const finish = typeof done === "function" ? done : () => {};
  try {
    const child = run(psExe(env), psArgs(path.join(repo, "scripts", CALC_SETUP_PS1)), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.on === "function") {
      let called = false;
      const once = (code) => { if (!called) { called = true; finish(code); } };
      child.on("exit", (code) => once(code));
      child.on("error", () => once(null));
    }
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    finish(null);
    return 0;
  }
}

/* The recorded autostart choice: true only when AshLight's own
   <runtime>\autostart.json (written by scripts\autostart.ps1) says
   "enabled": true. A missing or broken file reads as off (the default). */
const AUTOSTART_FILE = "autostart.json";

function readAutostart(home, fsMod) {
  const f = fsMod || require("fs");
  try {
    const doc = JSON.parse(String(f.readFileSync(path.join(home, AUTOSTART_FILE), "utf8"))
      .replace(/^\uFEFF/, ""));
    return !!(doc && doc.enabled === true);
  } catch (e) {
    return false;
  }
}

/* RUN-SECOND-LINE-CLIENT (F-127): the supervisor's give-up record. The
   keepalive supervisor (server/al/keepalive.py) writes <runtime>\
   keepalive.json; "status": "gave-up" means it hit its restart cap and
   exited, so nothing restarts the core until the next scripts\run.ps1.
   Returns null unless the file is small, valid JSON and says gave-up;
   else {restarts, reason}: restarts a whole number 1-1000 (else 0) and
   reason one of KEEPALIVE_REASONS from last_restart (else ""). Only these
   two values leave the file: no pid, port or path. Never throws. */
const KEEPALIVE_FILE = "keepalive.json";
const KEEPALIVE_MAX_BYTES = 64 * 1024;
const KEEPALIVE_REASONS = ["hung", "crash", "start-crash", "start-timeout"];

function readGiveUp(runtimeDir, fsMod) {
  const f = fsMod || require("fs");
  try {
    const file = path.join(String(runtimeDir || ""), KEEPALIVE_FILE);
    const st = f.statSync(file);
    if (!st.isFile() || st.size > KEEPALIVE_MAX_BYTES) { return null; }
    const doc = JSON.parse(String(f.readFileSync(file, "utf8")).replace(/^\uFEFF/, ""));
    if (!doc || typeof doc !== "object" || Array.isArray(doc) || doc.status !== "gave-up") {
      return null;
    }
    const n = doc.restarts;
    const restarts = Number.isInteger(n) && n >= 1 && n <= 1000 ? n : 0;
    const last = doc.last_restart;
    const reason = last && typeof last === "object" && KEEPALIVE_REASONS.includes(last.reason)
      ? last.reason : "";
    return { restarts: restarts, reason: reason };
  } catch (e) {
    return null;
  }
}

module.exports = { resolveSidecar, startCore, stopAll, psArgs, psExe, whichAbs, setAutostart,
                   readAutostart, AUTOSTART_FILE, setupCalc, CALC_SETUP_PS1,
                   applyStaged, relaunch, startConfirm, EXIT_SWITCHED,
                   applyNow, takeApplyRequest, APPLY_REQUEST_FILE,
                   readGiveUp, KEEPALIVE_FILE, KEEPALIVE_REASONS };
