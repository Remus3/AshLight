"use strict";
/* AshLight overlay shell (Electron 45.3.3).

   One frameless, transparent, always-on-top, click-through, non-focusable
   window. It reads the AshLight core's SSE feed and draws only when a
   visible value changes. ToS floor (CLAUDE.md): it never touches the game
   process, never reads game memory, never sends any key or mouse input.
   The only global shortcut is the show/hide toggle. */

const { app, BrowserWindow, globalShortcut, ipcMain, screen, session } = require("electron");
const fs = require("fs");
const path = require("path");
const L = require("./shared/layout.js");

const REPO = path.resolve(__dirname, "..");
const TOKEN_FILE = path.join(REPO, "ops", "runtime", "token");
const DISPLAYS_FILE = path.join(REPO, "ops", "runtime", "displays.json");
const PORTS_PY = path.join(REPO, "server", "al", "ports.py");
const LOCAL_CONFIG = path.join(REPO, "config", "local.json");
const OVERLAY_HTML = path.join(__dirname, "overlay", "index.html");
const DEFAULT_TOGGLE = "Alt+Shift+A";
const DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way.";

let win = null;
let logStream = null;

function log(msg) {
  const line = new Date().toISOString() + " " + msg + "\n";
  if (logStream) { logStream.write(line); } else { process.stderr.write(line); }
}

function openLog() {
  // run.ps1 sets AL_SIDECAR_ROOT from server.al.paths (the one resolver).
  const root = process.env.AL_SIDECAR_ROOT;
  if (!root) { return; }
  try {
    const dir = path.join(root, "Logs");
    fs.mkdirSync(dir, { recursive: true });
    logStream = fs.createWriteStream(path.join(dir, "overlay.log"), { flags: "a" });
  } catch (e) {
    logStream = null;
  }
}

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) { return {}; }
}

/* The core port has ONE source: server/al/ports.py. */
function corePort(cfg) {
  if (process.env.AL_PORT && /^\d+$/.test(process.env.AL_PORT)) { return Number(process.env.AL_PORT); }
  if (Number.isInteger(cfg.port)) { return cfg.port; }
  try {
    const m = /^AL_PORT\s*=\s*(\d+)/m.exec(fs.readFileSync(PORTS_PY, "utf8"));
    if (m) { return Number(m[1]); }
  } catch (e) { /* fall through */ }
  return 0;
}

function readToken() {
  try { return fs.readFileSync(TOKEN_FILE, "ascii").trim(); } catch (e) { return ""; }
}

const config = readJson(LOCAL_CONFIG);
const port = corePort(config);
const toggleKey = process.env.AL_OVERLAY_TOGGLE || config.overlay_toggle || DEFAULT_TOGGLE;

// Sidecar rule: Electron's profile (cache, crash dumps) never lands in the
// user's roaming profile - it goes to the AL sidecar (set by run.ps1 from
// server.al.paths) or, without it, to the repo's gitignored ops/runtime.
const profileDir = process.env.AL_SIDECAR_ROOT
  ? path.join(process.env.AL_SIDECAR_ROOT, "Cache", "overlay-profile")
  : path.join(REPO, "ops", "runtime", "overlay-profile");
app.setPath("userData", profileDir);
app.setPath("sessionData", profileDir);
app.commandLine.appendSwitch("disable-gpu-shader-disk-cache");

// Never contend for the game's GPU queue (decision 0002).
app.disableHardwareAcceleration();
// OVL-BUDGET (2026-11-16): with acceleration off Chromium still starts a
// sandboxed GPU process for software compositing; on the operator's machine a
// WMI-detached start (scripts\al_detach.ps1) failed to launch it
// (error_code=18, then "GPU process isn't usable", exit). Running the
// software compositor in the browser process removes that process: the
// overlay starts, and it is one Electron process fewer (RAM budget).
app.commandLine.appendSwitch("in-process-gpu");

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { /* one overlay only; nothing to focus */ });
  app.whenReady().then(start);
}

/* OVL-POS: the layout is config/local.json "overlay" (edited from the
   dashboard); the math is app/shared/layout.js. */
function currentLayout() {
  return L.normalizeLayout(readJson(LOCAL_CONFIG).overlay);
}

function layoutBounds(layout) {
  return L.computeBounds(layout, screen.getAllDisplays(), screen.getPrimaryDisplay().id);
}

let appliedLayout = "";

function applyLayout(force) {
  if (!win) { return; }
  const layout = currentLayout();
  const b = layoutBounds(layout);
  const key = JSON.stringify([layout, b]);
  if (!force && key === appliedLayout) { return; }
  appliedLayout = key;
  const rect = { x: b.x, y: b.y, width: b.width, height: b.height };
  // Twice on purpose: moving a window onto a monitor with another DPI
  // re-scales it on arrival, so the second call lands the exact size.
  win.setBounds(rect);
  win.setBounds(rect);
  win.setOpacity(layout.opacity);
  win.webContents.setZoomFactor(layout.scale);
  log("layout " + layout.corner + " display " + layout.display + " scale " + layout.scale +
      " at " + b.x + "," + b.y + " " + b.width + "x" + b.height + " sf " + b.scaleFactor);
}

/* The monitor list for the dashboard's layout editor (read by the core). */
function writeDisplays() {
  const doc = { updated: new Date().toISOString(),
                displays: L.describeDisplays(screen.getAllDisplays(), screen.getPrimaryDisplay().id) };
  try {
    fs.mkdirSync(path.dirname(DISPLAYS_FILE), { recursive: true });
    fs.writeFileSync(DISPLAYS_FILE + ".tmp", JSON.stringify(doc, null, 1) + "\n", "ascii");
    fs.renameSync(DISPLAYS_FILE + ".tmp", DISPLAYS_FILE);
  } catch (e) {
    log("displays.json not written: " + e.message);
  }
}

function onDisplaysChanged() {
  writeDisplays();
  applyLayout(true);
}

function createWindow() {
  const b = layoutBounds(currentLayout());
  win = new BrowserWindow({
    x: b.x, y: b.y, width: b.width, height: b.height,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    hasShadow: false,
    alwaysOnTop: true,
    focusable: false,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    show: false,
    title: "AshLight overlay",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
      devTools: !app.isPackaged
    }
  });
  win.setAlwaysOnTop(true, "screen-saver");
  win.setIgnoreMouseEvents(true);
  win.setMenu(null);
  win.webContents.on("will-navigate", (e) => e.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("console-message", (e) => {
    log("renderer: " + (e.message || ""));
  });
  win.webContents.on("did-finish-load", () => applyLayout(true));
  win.once("ready-to-show", () => win.showInactive());
  win.loadFile(OVERLAY_HTML);
}

function toggle() {
  if (!win) { return; }
  if (win.isVisible()) { win.hide(); } else { win.showInactive(); }
}

function start() {
  openLog();
  app.setAboutPanelOptions({ applicationName: "AshLight overlay", credits: DISCLAIMER });
  // No permission is ever granted to the page (camera, clipboard, ...).
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(false));

  ipcMain.on("al:config", (e) => {
    const url = (e.senderFrame && e.senderFrame.url) || "";
    const ok = url.startsWith("file:") && decodeURIComponent(url).replace(/\\/g, "/")
      .endsWith("/overlay/index.html");
    e.returnValue = ok ? { token: readToken(), port: port } : {};
  });

  writeDisplays();
  createWindow();
  screen.on("display-added", onDisplaysChanged);
  screen.on("display-removed", onDisplaysChanged);
  screen.on("display-metrics-changed", onDisplaysChanged);
  // The dashboard saves the layout into config/local.json; follow it.
  fs.watchFile(LOCAL_CONFIG, { interval: 1000, persistent: false }, () => applyLayout(false));

  // The core writes a fresh token on every start: reload when it changes.
  let lastToken = readToken();
  fs.watchFile(TOKEN_FILE, { interval: 5000, persistent: false }, () => {
    const t = readToken();
    if (t !== lastToken) {
      lastToken = t;
      if (win) { win.webContents.reload(); }
    }
  });

  if (!globalShortcut.register(toggleKey, toggle)) {
    log("toggle shortcut not available: " + toggleKey);
  }
  log("overlay started; port " + port + "; toggle " + toggleKey);

  const smoke = Number(process.env.AL_OVERLAY_SMOKE_S || 0);
  if (smoke > 0) { setTimeout(() => app.quit(), smoke * 1000); }
}

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  fs.unwatchFile(TOKEN_FILE);
  fs.unwatchFile(LOCAL_CONFIG);
});

app.on("window-all-closed", () => app.quit());
