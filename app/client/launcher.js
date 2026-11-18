"use strict";
/* DESKTOP-CLIENT (decision 0041): the companion's only process starts.
   It never starts a process of its own design: it runs the repo's own
   scripts (scripts\run.ps1 converges core + supervisor + overlay, decision
   0010; scripts\stop.ps1 stops them) and the one path resolver
   (python -m server.al.paths). Nothing here touches the game (ToS floor).
   This is the one app/ file allowed to load child_process
   (tests/test_overlay_smoke.py P4-6). */

const childProcess = require("child_process");
const path = require("path");

const PYTHONS = ["python", "py"];

function psArgs(script, extra) {
  return ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
          "-WindowStyle", "Hidden", "-File", script].concat(extra || []);
}

/* The AL sidecar root from server.al.paths, or "" when Python is missing.
   Used only when the client was started without AL_SIDECAR_ROOT (a Start
   Menu shortcut), so the Electron profile and the single-instance lock are
   the same ones scripts\run.ps1 gives the overlay. */
function resolveSidecar(repo, exec) {
  const run = exec || childProcess.execFileSync;
  for (const py of PYTHONS) {
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
function startCore(repo, port, spawn) {
  const run = spawn || childProcess.spawn;
  const extra = ["-NoBrowser"];
  if (Number.isInteger(port) && port > 0) { extra.push("-Port", String(port)); }
  try {
    const child = run("powershell.exe", psArgs(path.join(repo, "scripts", "run.ps1"), extra), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

/* Stop everything (scripts\stop.ps1: core, supervisor, overlay). */
function stopAll(repo, spawn) {
  const run = spawn || childProcess.spawn;
  try {
    const child = run("powershell.exe", psArgs(path.join(repo, "scripts", "stop.ps1")), {
      cwd: repo, detached: false, windowsHide: true, stdio: "ignore"
    });
    if (child && typeof child.unref === "function") { child.unref(); }
    return (child && child.pid) || 0;
  } catch (e) {
    return 0;
  }
}

module.exports = { resolveSidecar, startCore, stopAll, psArgs };
