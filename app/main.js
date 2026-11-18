"use strict";
/* AshLight overlay shell (Electron 45.3.3).

   One frameless, transparent, always-on-top, click-through, non-focusable
   window. It reads the AshLight core's SSE feed and draws only when a
   visible value changes. ToS floor (CLAUDE.md): it never touches the game
   process, never reads game memory, never sends any key or mouse input.
   Global shortcuts: the show/hide toggle, and the item check (TC-EVAL-UI),
   which reads the clipboard once per press (eval_hotkey.js). */

const { app, BrowserWindow, clipboard, globalShortcut, ipcMain, screen, session } = require("electron");
const fs = require("fs");
const http = require("http");
const path = require("path");
const L = require("./shared/layout.js");
const EvalKey = require("./eval_hotkey.js");
const Hotkey = require("./hotkey.js");
const About = require("./about.js");
const OverlayGate = require("./overlay_gate.js");
const Link = require("./client/link.js");
const Launcher = require("./client/launcher.js");
const HotReload = require("./hotreload.js");

const REPO = path.resolve(__dirname, "..");
const TOKEN_FILE = path.join(REPO, "ops", "runtime", "token");
const DISPLAYS_FILE = path.join(REPO, "ops", "runtime", "displays.json");
const PORTS_PY = path.join(REPO, "server", "al", "ports.py");
const LOCAL_CONFIG = path.join(REPO, "config", "local.json");
const OVERLAY_HTML = path.join(__dirname, "overlay", "index.html");
// AUDIT-ELECTRON S6: the overlay is never packaged, so !app.isPackaged
// would leave devTools always on; they open only with an explicit AL_DEV=1.
const DEV_TOOLS = process.env.AL_DEV === "1";
const DEFAULT_TOGGLE = "Alt+Shift+A";
const DEFAULT_EVAL_KEY = "Alt+Shift+E";
const DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way.";

let win = null;
let client = null; // DESKTOP-CLIENT companion window + tray (client mode only)
let gate = null; // overlay visibility (app/overlay_gate.js)
let stopHotReload = null; // HOT-RELOAD: stops the overlay page file watch
let dataCredit = ""; // TC-SNAP-UI: game-data credit, "" without snapshot data
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
// AREA-AUDIT P5-3: a bare key (or a game key like Ctrl+C) from the env or a
// hand-edited / imported config is refused before globalShortcut.register,
// which would otherwise take that key from the game system-wide.
const toggleKey = Hotkey.pick([process.env.AL_OVERLAY_TOGGLE, config.overlay_toggle],
  DEFAULT_TOGGLE, log);
const evalKey = Hotkey.pick([process.env.AL_EVAL_HOTKEY, config.eval_hotkey],
  DEFAULT_EVAL_KEY, log);

// DESKTOP-CLIENT (decision 0041): "--client" (the Start Menu shortcut,
// scripts\run.ps1) runs the companion window, tray and overlay. Started
// from a shortcut there is no AL_SIDECAR_ROOT from run.ps1, so the one
// resolver (server.al.paths) gives it: the profile, and with it the
// single-instance lock, is then the same one a run.ps1 start holds.
const CLIENT_MODE = Link.wantsClient(process.argv);
if (CLIENT_MODE && !process.env.AL_SIDECAR_ROOT) {
  const side = Launcher.resolveSidecar(REPO);
  if (side) { process.env.AL_SIDECAR_ROOT = side; }
}

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
// UX-OVL-RAM (2026-11-17): the network service (the overlay's only network
// use is the SSE feed from 127.0.0.1) runs in the browser process instead of
// its own utility process. Measured: 3 processes -> 2, summed working set
// 245-252 MB -> about 180 MB (decision 0002). The renderer sandbox is
// unchanged. Chromium's feature name carries the "2".
app.commandLine.appendSwitch("enable-features", "NetworkServiceInProcess2");

// Operator order 2026-11-17 (decision 0041): the overlay exists only while
// the AshLight client runs. It is a window of the client's own process, so
// quitting or a crash of the client takes it down too; a start without
// --client exits at once. Only the opt-in overlay smoke (AL_OVERLAY_SMOKE_S,
// a bounded test run) may start the overlay alone, to measure its budget.
const SMOKE_S = Number(process.env.AL_OVERLAY_SMOKE_S || 0);
const OVERLAY_ALONE_TEST = !CLIENT_MODE && SMOKE_S > 0;

if (!CLIENT_MODE && !OVERLAY_ALONE_TEST) {
  process.stderr.write("AshLight: the overlay starts only with the client (--client)\n");
  app.quit();
} else if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  // One process: a second start never makes a second overlay. A second
  // start with --client (the shortcut) opens the companion window here.
  app.on("second-instance", (e, argv) => {
    if (Link.wantsClient(argv)) { openClient(); }
  });
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
let opacityChain = Promise.resolve(null);

/* UX-REAL-OVERLAY: the opacity is page CSS, never BrowserWindow.setOpacity.
   On the real desktop (software compositing, transparent window) the
   window-level alpha left the whole overlay invisible: nothing reached the
   screen. Page opacity multiplies text and plate together, the same maths
   as design 0001 section 5.2. Chained so a quick second change never
   leaves an old rule behind. */
function applyOpacity(value) {
  const css = L.opacityCss(value);
  const wc = win.webContents;
  opacityChain = opacityChain
    .then((old) => (old ? wc.removeInsertedCSS(old).catch(() => null) : null))
    .then(() => wc.insertCSS(css, { cssOrigin: "author" }))
    .catch((e) => { log("opacity not applied: " + e.message); return null; });
}

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
  applyOpacity(layout.opacity);
  win.webContents.setZoomFactor(b.zoom); // the user scale times UX-DPI autoScale
  log("layout " + layout.corner + " display " + layout.display + " scale " + layout.scale +
      " zoom " + b.zoom +
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
      devTools: DEV_TOOLS
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
  gate = OverlayGate.createOverlayGate({
    isVisible: () => !!(win && win.isVisible()),
    showInactive: () => { if (win) { win.showInactive(); } },
    hide: () => { if (win) { win.hide(); } }
  }, log);
  win.once("ready-to-show", () => {
    gate.ready();
    setTimeout(() => { if (gate) { gate.graceOver(); } }, OverlayGate.GRACE_MS);
  });
  win.loadFile(OVERLAY_HTML);
}

/* TC-SNAP-UI: the game-data credit in the About panel and (through
   al:config) the page's About. */
function setCredit(c) {
  dataCredit = c;
  app.setAboutPanelOptions({ applicationName: "AshLight overlay",
                             credits: About.aboutText(DISCLAIMER, dataCredit) });
}

/* On a core restart: re-read the credit, then reload the page (the token
   changed, so the page reloads anyway; one reload, not two). */
function refreshAboutAndReload(getVersion) {
  getVersion().then((doc) => setCredit(About.creditOf(doc)), (e) => {
    log("about: version not read: " + e.message);
  }).then(() => {
    if (win) { win.webContents.reload(); }
    if (client) { client.reload(); }
  });
}

function toggle() {
  if (!win || !gate) { return; }
  gate.toggleUser();
  if (client) { client.refresh(); }
}

/* DESKTOP-CLIENT: "Restart overlay" (tray, or the dashboard's button in
   the client): close the overlay window cleanly and build it again. The
   player's show / hide choice carries over; the gate re-seeds from the
   new page's first report. */
function restartOverlay() {
  const wantsIt = !gate || gate.userWants();
  if (win) {
    const old = win;
    win = null;
    gate = null;
    old.destroy();
  }
  createWindow();
  if (!wantsIt) { gate.toggleUser(); }
  log("overlay restarted");
  if (client) { client.refresh(); }
}

/* The ONE overlay gate hook (decision 0029 amendment 2026-11-17): false
   hides the overlay while the core reports the 0029 idle "game may be
   closed" state, true shows it again on the next fresh log line. Fed by
   the overlay page (al:gate) from the snapshot's game_idle. */
function setOverlayGate(visible) {
  if (gate) { gate.setGate(visible === true); }
}

/* DESKTOP-CLIENT: the companion window (app/client/window.js), built on
   first use only, so an overlay-only start never loads a second renderer. */
function openClient() {
  if (!app.isReady()) { return; }
  if (!client) {
    const electron = require("electron");
    client = require("./client/window.js").createClient({
      electron: electron, http: http, repo: REPO, port: port, readToken: readToken,
      runtimeDir: path.dirname(TOKEN_FILE), log: log, devTools: DEV_TOOLS,
      toggleOverlay: toggle, overlayVisible: () => !gate || gate.userWants(),
      restartOverlay: restartOverlay
    });
  }
  client.open();
}

function start() {
  openLog();
  app.setAboutPanelOptions({ applicationName: "AshLight overlay", credits: DISCLAIMER });
  // No permission is ever granted to the page (camera, clipboard, ...).
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(false));
  // AUDIT-ELECTRON S7: permission checks (navigator.permissions, ...) too.
  session.defaultSession.setPermissionCheckHandler(() => false);

  ipcMain.on("al:config", (e) => {
    const url = (e.senderFrame && e.senderFrame.url) || "";
    const ok = url.startsWith("file:") && decodeURIComponent(url).replace(/\\/g, "/")
      .endsWith("/overlay/index.html");
    e.returnValue = ok ? { token: readToken(), port: port, credit: dataCredit } : {};
  });
  ipcMain.on("al:gate", (e, visible) => {
    if (!win || e.sender !== win.webContents) { return; } // the overlay page only
    setOverlayGate(visible === true);
  });
  // DESKTOP-CLIENT: the dashboard's "Restart overlay", from the companion
  // window's main frame on the local core only (app/client/preload.js).
  ipcMain.on("al:restart-overlay", (e) => {
    if (client && client.isCompanion(e)) { restartOverlay(); }
  });

  writeDisplays();
  // DESKTOP-CLIENT: the companion window first, so the shortcut shows
  // something at once (it starts the core itself when needed).
  if (CLIENT_MODE) { openClient(); }
  // TC-SNAP-UI: the credit is read before the page loads (at most
  // About.START_WAIT_MS), so the window never reloads just to show it.
  const getVersion = About.makeGetVersion(http, port, readToken);
  About.firstCredit(getVersion, About.START_WAIT_MS).then((c) => {
    setCredit(c);
    createWindow();
  });
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
      refreshAboutAndReload(getVersion);
    }
  });

  // HOT-RELOAD (decision 0042): in a source checkout, an edit of the
  // overlay page's own files reloads the page (stat poll here, none in it).
  if (HotReload.devEnabled(REPO, process.env, () => readJson(LOCAL_CONFIG), fs.existsSync)) {
    const files = HotReload.pageFiles([path.join(__dirname, "overlay"),
                                       path.join(__dirname, "shared")], fs.readdirSync);
    stopHotReload = HotReload.watch(files, () => {
      log("hot reload: overlay page files changed; reloading the page");
      if (win) { win.webContents.reload(); }
    });
  }

  if (!globalShortcut.register(toggleKey, toggle)) {
    log("toggle shortcut not available: " + toggleKey);
  }
  // TC-EVAL-UI: one clipboard read per press, posted to the core.
  const onEval = EvalKey.createEvalHotkey({
    readText: () => clipboard.readText(),
    post: EvalKey.makePost(http, port, readToken),
    log: log
  });
  if (!globalShortcut.register(evalKey, onEval)) {
    log("item check shortcut not available: " + evalKey);
  }
  log("overlay started; port " + port + "; toggle " + toggleKey + "; item check " + evalKey);

  if (SMOKE_S > 0) { setTimeout(() => app.quit(), SMOKE_S * 1000); }
}

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  if (client) { client.dispose(); }
  fs.unwatchFile(TOKEN_FILE);
  fs.unwatchFile(LOCAL_CONFIG);
  if (stopHotReload) { stopHotReload(); }
});

// With the tray up (client mode) closing windows does not quit; the tray's
// Close / Stop items do.
app.on("window-all-closed", () => {
  if (client && client.hasTray()) { return; }
  app.quit();
});
