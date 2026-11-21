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
   which_abs rule of server/al/exepin.py). */

const childProcess = require("child_process");
const path = require("path");

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
   the same ones scripts\run.ps1 gives the overlay. */
function resolveSidecar(repo, exec, env, fsMod) {
  const run = exec || childProcess.execFileSync;
  for (const name of PYTHONS) {
    const py = whichAbs(name, env, fsMod);
    if (!py) { continue; }
    try {
      const out = run(py, ["-m", "server.al.paths"], {
        cwd: repo, windowsHide: true, timeout: 15000, encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"]
      });
      const doc = JSON.parse(String(out));
      if (doc && typeof doc.sidecar === "string" && doc.sidecar) { return doc.sidecar; }
    } catch (e) { /* next */ }
  }
  return "";
}

/* Start scripts\run.ps1 -NoBrowser hidden. Not detached: a detached
   powershell got no console and exited at once without running; run.ps1
   detaches the core and supervisor itself (WMI). It converges to one
   core, one supervisor and (this process already being the overlay) no
   second overlay. Returns the child pid or 0. */
function startCore(repo, port, spawn, env) {
  const run = spawn || childProcess.spawn;
  const extra = ["-NoBrowser"];
  if (Number.isInteger(port) && port > 0) { extra.push("-Port", String(port)); }
  try {
    const child = run(psExe(env), psArgs(path.join(repo, "scripts", "run.ps1"), extra), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* Stop everything (scripts\stop.ps1: core, supervisor, overlay). */
function stopAll(repo, spawn, env) {
  const run = spawn || childProcess.spawn;
  try {
    const child = run(psExe(env), psArgs(path.join(repo, "scripts", "stop.ps1")), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* REL-AUTOSTART-SWITCH (decision 0011, ruling Q-08): tray "Start with
   Windows". Runs scripts\autostart.ps1 -Enable or -Disable hidden, with no
   other script argument; the script registers or removes the logon task and
   records the choice in <runtime>\autostart.json. done(code), when given,
   is called once the script exits (code null when it could not start).
   Returns the child pid or 0. */
function setAutostart(repo, on, spawn, done) {
  const run = spawn || childProcess.spawn;
  const flag = on === true ? "-Enable" : "-Disable";
  const finish = typeof done === "function" ? done : () => {};
  try {
    const child = run("powershell.exe", psArgs(path.join(repo, "scripts", "autostart.ps1"), [flag]), {
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

module.exports = { resolveSidecar, startCore, stopAll, psArgs, psExe, whichAbs, setAutostart,
                   readAutostart, AUTOSTART_FILE, setupCalc, CALC_SETUP_PS1 };
