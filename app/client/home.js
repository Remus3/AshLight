"use strict";
/* REL-CLIENT-HOME (F-049, DEP-05, decision 0059): the ONE path resolver of
   the Electron client. It mirrors server/al/paths.py install_mode(): an
   installed copy runs from <home>/app/<version>/ with the marker
   <home>/install.json two levels above the payload root, or AL_HOME names
   the home; then the token, local.json and displays.json live in
   <home>/data/ and the cache in <home>/cache/. In a checkout every path is
   the one app/main.js used before (ops/runtime/ and config/ of the repo).
   A home whose path text has a "steamapps" or "Path of Exile 2" component
   is refused by path text only: no registry read, no library file, no
   listing or stat of any game folder (floor audit on F-049).
   Pure path logic and fs reads: this file starts no process (only
   client/launcher.js may, tests/test_overlay_smoke.py). The names below
   are checked against paths.py by tests/test_install_paths.py. */

const path = require("path");

const HOME_ENV = "AL_HOME";
const SIDECAR_ENV = "AL_SIDECAR_ROOT";
const MARKER_NAME = "install.json";
const MARKER_MAX_BYTES = 64 * 1024;
const APP_FOLDER = "app";
const DATA_DIR = "data";
const CACHE_DIR = "cache";
const RUNTIME_FOLDER = "runtime";
const BOOT_NAME = "boot.py";
const REFUSED_COMPONENTS = ["steamapps", "path of exile 2"];

class HomeRefused extends Error {
  constructor(message) {
    super(message);
    this.name = "HomeRefused";
  }
}

/* The reason a home is refused, or null. Path text only (paths.home_refusal):
   the trailing dots and spaces Windows ignores are stripped, case folded. */
function homeRefusal(home) {
  for (const part of String(home).split(/[\\/]+/)) {
    if (REFUSED_COMPONENTS.includes(part.replace(/[. ]+$/, "").toLowerCase())) {
      return "the install home may not lie in a '" + part + "' folder (a Steam " +
        "library or the game's own folder); install AshLight in its own folder";
    }
  }
  return null;
}

function envHome(env) {
  const raw = String((env && env[HOME_ENV]) || "").trim().replace(/^"+|"+$/g, "");
  // path.resolve, never realpath: no file system access before the text check
  return raw ? path.resolve(raw) : null;
}

function isFile(fsMod, p) {
  try { return fsMod.statSync(p).isFile(); } catch (e) { return false; }
}

/* <home> when root is <home>/app/<version> and <home>/install.json is a
   file, else null: one stat of the marker inside the home. */
function markerHome(root, fsMod) {
  const parent = path.dirname(root);
  const home = path.dirname(parent);
  if (parent === root || home === parent) { return null; }
  if (path.basename(parent).toLowerCase() !== APP_FOLDER) { return null; }
  return isFile(fsMod, path.join(home, MARKER_NAME)) ? home : null;
}

/* The marker as an object; {} when missing, too big or unreadable. */
function readMarker(home, fsMod) {
  const file = path.join(home, MARKER_NAME);
  try {
    if (fsMod.statSync(file).size > MARKER_MAX_BYTES) { return {}; }
    const doc = JSON.parse(String(fsMod.readFileSync(file, "utf8")).replace(/^\uFEFF/, ""));
    return doc && typeof doc === "object" && !Array.isArray(doc) ? doc : {};
  } catch (e) {
    return {};
  }
}

/* One plain folder name under <home>/runtime, else null (paths._marker_runtime). */
function runtimeFolder(home, name) {
  if (typeof name !== "string" || !name.replace(/^[. ]+|[. ]+$/g, "") || /[\\/:]/.test(name)) {
    return null;
  }
  return path.join(home, RUNTIME_FOLDER, name);
}

function sidecarCache(env) {
  const raw = String((env && env[SIDECAR_ENV]) || "").trim().replace(/^"+|"+$/g, "");
  return raw ? path.join(path.resolve(raw), "Cache") : null;
}

/* The checkout layout of a repository root: today's constants. */
function checkout(root, env) {
  const dataDir = path.join(root, "ops", "runtime");
  return {
    mode: "checkout", root: root, home: null, dataDir: dataDir,
    tokenFile: path.join(dataDir, "token"),
    localConfig: path.join(root, "config", "local.json"),
    displaysFile: path.join(dataDir, "displays.json"),
    portsPy: path.join(root, "server", "al", "ports.py"),
    cacheDir: sidecarCache(env), pythonDir: null
  };
}

/* resolve(appDir, env, fs) -> {mode, root, home, dataDir, tokenFile,
   localConfig, displaysFile, portsPy, cacheDir, pythonDir}. appDir is the
   app/ folder (main.js's __dirname); root is the folder above it (the repo,
   or the payload root <home>/app/<version>). cacheDir is the sidecar's
   Cache when AL_SIDECAR_ROOT is set (it wins, as in paths.py), else
   <home>/cache in an install, else null (the sidecar is not known yet).
   Throws HomeRefused for a home in a Steam library or the game's folder. */
function resolve(appDir, env, fsMod) {
  const e = env || process.env;
  const f = fsMod || require("fs");
  const root = path.resolve(appDir, "..");
  const home = envHome(e) || markerHome(root, f);
  if (!home) { return checkout(root, e); }
  const reason = homeRefusal(home);
  if (reason) { throw new HomeRefused(reason); }
  const dataDir = path.join(home, DATA_DIR);
  return {
    mode: "installed", root: root, home: home, dataDir: dataDir,
    tokenFile: path.join(dataDir, "token"),
    localConfig: path.join(dataDir, "local.json"),
    displaysFile: path.join(dataDir, "displays.json"),
    portsPy: path.join(root, "server", "al", "ports.py"),
    cacheDir: sidecarCache(e) || path.join(home, CACHE_DIR),
    pythonDir: runtimeFolder(home, readMarker(home, f).python)
  };
}

/* A home object from a resolve() result or a bare repository root (the
   launcher's older callers pass the root text: a checkout). */
function asHome(home, env) {
  if (home && typeof home === "object" && typeof home.root === "string") { return home; }
  return checkout(String(home || ""), env);
}

/* The Electron profile folder: <sidecar>/Cache/overlay-profile when
   AL_SIDECAR_ROOT is set (run.ps1, or the client's own sidecar read),
   else <home>/cache/overlay-profile in an install, else the checkout's
   ops/runtime/overlay-profile (paths.all_runtime_paths overlay_profile). */
function profileDir(home, env) {
  const h = asHome(home, env);
  const side = sidecarCache(env || process.env);
  if (side) { return path.join(side, "overlay-profile"); }
  if (h.mode === "installed") { return path.join(h.home, CACHE_DIR, "overlay-profile"); }
  return path.join(h.dataDir, "overlay-profile");
}

/* The command for a Python child (paths.python_cmd): {exe, args}. A
   checkout keeps the "-m" form and exe null (the launcher looks python up
   in an absolute PATH entry); an install prefers the marker's private
   runtime (REL-RUNTIME-SCRIPTS, decision 0063): <runtime>/python.exe, or
   pythonw.exe when opts.windowless, running <root>/boot.py, because the
   embeddable runtime's ._pth ignores the current folder; exe null when the
   marker names no usable python folder. No stat of the runtime folder. */
function pythonCmd(home, module, args, opts) {
  const h = asHome(home);
  const tail = [String(module)].concat((args || []).map(String));
  if (h.mode !== "installed") { return { exe: null, args: ["-m"].concat(tail) }; }
  const name = opts && opts.windowless ? "pythonw.exe" : "python.exe";
  return {
    exe: h.pythonDir ? path.join(h.pythonDir, name) : null,
    args: [path.join(h.root, BOOT_NAME)].concat(tail)
  };
}

/* The variables no child of the client gets (OVL-LAUNCH-ENV, F-110): either
   one turns electron.exe into a Node script host before any app code runs,
   and run.ps1 starts the client again on a re-run. Matched in any case, as
   Windows matches environment names. scripts/run.ps1 drops the same two
   ($clientUnset). */
const DROPPED_ENV = ["ELECTRON_RUN_AS_NODE", "NODE_OPTIONS"];

/* The environment a child gets: a copy of env without DROPPED_ENV. The one
   place the launcher's child environment is narrowed. */
function childEnv(env) {
  const src = env || process.env;
  const drop = DROPPED_ENV.map((n) => n.toUpperCase());
  const out = {};
  for (const key of Object.keys(src)) {
    if (!drop.includes(String(key).toUpperCase())) { out[key] = src[key]; }
  }
  return out;
}

module.exports = {
  resolve, asHome, checkout, profileDir, pythonCmd, childEnv, homeRefusal, HomeRefused,
  HOME_ENV, SIDECAR_ENV, MARKER_NAME, MARKER_MAX_BYTES, APP_FOLDER, DATA_DIR, CACHE_DIR,
  RUNTIME_FOLDER, BOOT_NAME, REFUSED_COMPONENTS, DROPPED_ENV
};
