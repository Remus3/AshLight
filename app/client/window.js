"use strict";
/* DESKTOP-CLIENT (decision 0041): the AshLight companion window and tray.

   A normal framed, resizable window (NOT the overlay: not always-on-top,
   focusable, in the taskbar) that shows the dashboard from the local core.
   The per-start token goes in the URL fragment of a window without a URL
   bar (app/client/link.js). It has its own session partition, so the
   overlay's deny-everything session is untouched; this one allows only the
   clipboard write the dashboard's Copy buttons make on the player's click
   (decision 0014), only for the core's origin. Links leave for the default
   browser (https to config/link_hosts.json only, on a click in the focused
   window, rate limited); the window never navigates off 127.0.0.1.

   Created only in client mode (electron app --client, the Start Menu
   shortcut); the overlay-only start (scripts\run.ps1) never builds it, so
   the overlay's process and RAM budget (decision 0002) is unchanged.
   The window has the standard Windows title bar (minimize, maximize /
   restore, X). X closes the window to the tray: its renderer is freed, the
   overlay, tray and core keep running, and the first close of a run says
   so in a tray note; tray "Quit AshLight" closes everything (decision
   0041).

   OVL-MAIN-PARTS (decision 0053): opts.onWindow(win, ses), when given, is
   called once per created companion window (main.js runs the parts'
   clientWindow hook from it); opts.overlayBounds() gives the overlay's
   current bounds to the parts that place this window. The returned object
   has window() and tray() getters for the parts.

   OVL-WAKE-COMPANION (decision 0041 amendment 2026-11-19): wake() is asked
   by the wake part (app/parts/40-wake.js) when the log goes from idle to a
   fresh line. A companion in the tray or minimised comes back with
   showInactive() (never focus()), only when Link.wakeAction says its saved
   bounds lie wholly on a display other than the overlay's. The tray
   checkbox "Open AshLight when the game wakes" switches it (client-prefs.json
   in the runtime dir, default on).

   REL-AUTOSTART-SWITCH (decision 0011, ruling Q-08): the tray checkbox
   "Start with Windows" shows the recorded choice (<runtime>\autostart.json,
   default off) and a click runs scripts\autostart.ps1 -Enable / -Disable
   hidden through the launcher; the menu is rebuilt when the script exits.
   The same three fixed, argument-free actions reach the dashboard through
   the preload (al:autostart-on, al:autostart-off, al:autostart-state); the
   handlers are registered here and answer only isCompanion() senders. */

const fs = require("fs");
const path = require("path");
const Link = require("./link.js");
const Brand = require("../brand/index.js"); // BRAND-ICON (design 0005)
const Launcher = require("./launcher.js");
const TrayMenu = require("./tray_menu.js");

const PARTITION = "persist:client";
const STARTING_HTML = path.join(__dirname, "starting.html");
const PRELOAD = path.join(__dirname, "preload.js");
const STATE_FILE = "client-window.json";
const CORE_WAIT_MS = 30000;
const CORE_STEP_MS = 500;
const SAVE_DELAY_MS = 500;
const ALLOWED_PERMISSION = "clipboard-sanitized-write";

function createClient(opts) {
  const { BrowserWindow, Menu, Tray, nativeImage, session, shell, screen, app,
          ipcMain } = opts.electron;
  const http = opts.http;
  const log = opts.log || (() => {});
  const port = opts.port;
  const stateFile = path.join(opts.runtimeDir, STATE_FILE);
  const healthy = Link.makeHealthCheck(http, port, opts.readToken);
  let win = null;
  let tray = null;
  let saveTimer = null;
  let starting = null;
  let ses = null;
  let shownToken = "";
  let closedNoteShown = false;
  let opened = []; // times of the links opened in the last minute (rate limit)
  let prefs = null; // client-prefs.json, read on first use
  let autostartBusy = false; // scripts\autostart.ps1 is running

  function iconImage() {
    return Brand.trayImage(nativeImage);
  }

  function clientSession() {
    if (ses) { return ses; }
    ses = session.fromPartition(PARTITION);
    ses.setPermissionRequestHandler((wc, perm, cb, details) => {
      const from = (details && details.requestingUrl) || (wc && wc.getURL()) || "";
      cb(perm === ALLOWED_PERMISSION && Link.isCoreUrl(from, port));
    });
    ses.setPermissionCheckHandler((wc, perm, requestingOrigin) =>
      perm === ALLOWED_PERMISSION && Link.isCoreUrl(requestingOrigin, port));
    // Downloads (the .build file, the loot filter, a settings export) go to
    // the user's Downloads folder, as the dashboard's own words say. Only
    // AshLight's own: from the core origin, a .build, .filter, .json or .txt
    // name (OVL-LINKS-DOWNLOADS); anything else is cancelled.
    ses.on("will-download", (e, item) => {
      if (!Link.downloadAllowed(item.getURL(), item.getFilename(), port)) {
        item.cancel();
        log("client: download refused");
        return;
      }
      const name = Link.safeFileName(item.getFilename()) || "ashlight-download";
      const dir = app.getPath("downloads");
      const ext = path.extname(name);
      const stem = name.slice(0, name.length - ext.length);
      let target = path.join(dir, name);
      for (let i = 1; fs.existsSync(target) && i < 100; i++) {
        target = path.join(dir, stem + " (" + i + ")" + ext);
      }
      item.setSavePath(target);
      log("client: download saved as " + path.basename(target));
    });
    return ses;
  }

  function readState() {
    try { return JSON.parse(fs.readFileSync(stateFile, "ascii")); } catch (e) { return null; }
  }

  function saveState() {
    if (!win || win.isDestroyed()) { return; }
    const doc = Link.stateDoc(win.isMaximized() ? win.getNormalBounds() : win.getBounds(),
                              win.isMaximized());
    try {
      fs.mkdirSync(path.dirname(stateFile), { recursive: true });
      fs.writeFileSync(stateFile + ".tmp", JSON.stringify(doc) + "\n", "ascii");
      fs.renameSync(stateFile + ".tmp", stateFile);
    } catch (e) {
      log("client: window state not saved: " + e.message);
    }
  }

  function saveSoon() {
    if (saveTimer) { clearTimeout(saveTimer); }
    saveTimer = setTimeout(() => { saveTimer = null; saveState(); }, SAVE_DELAY_MS);
  }

  /* A link leaves only on the player's click in the focused companion,
     to a listed https host, at most 1 a second and 5 a minute. */
  function route(e, url, isPopup) {
    const now = Date.now();
    const focused = !!(win && !win.isDestroyed() && win.isFocused());
    const r = Link.routeFor(url, port, isPopup, { focused: focused, now: now, history: opened });
    if (r === "stay") { return; }
    if (e && e.preventDefault) { e.preventDefault(); }
    if (r === "external") {
      opened = Link.noteOpened(opened, now);
      const parsed = new URL(url);
      shell.openExternal(parsed.href).catch((err) => log("client: link not opened: " + err.message));
    } else {
      log("client: navigation refused");
    }
  }

  function showDashboard() {
    if (!win || win.isDestroyed()) { return; }
    const token = opts.readToken();
    const url = Link.dashboardUrl(port, token);
    shownToken = url ? token : "";
    if (url) { win.loadURL(url); } else { win.loadFile(STARTING_HTML, { hash: "failed" }); }
  }

  /* Load the dashboard once the core answers; start it (scripts\run.ps1)
     when it does not. One start attempt per window open. */
  function connect() {
    if (starting) { return starting; }
    starting = healthy().then((ok) => {
      if (ok) { return true; }
      const pid = Launcher.startCore(opts.repo, port);
      log("client: core not answering; scripts\\run.ps1 started (pid " + pid + ")");
      return Link.waitFor(healthy, CORE_WAIT_MS, CORE_STEP_MS);
    }).then((ok) => {
      starting = null;
      if (!win || win.isDestroyed()) { return; }
      if (ok) {
        showDashboard();
      } else {
        log("client: core did not answer within " + CORE_WAIT_MS / 1000 + " s");
        win.loadFile(STARTING_HTML, { hash: "failed" });
      }
    });
    return starting;
  }

  /* inactive: the wake path. The window shows without taking focus and at
     its saved normal size (maximize() would activate it). */
  function createWindow(inactive) {
    const displays = [screen.getPrimaryDisplay()].concat(screen.getAllDisplays());
    const areas = displays.map((d) => d.workArea);
    // OVL-SECOND-DISPLAY: Electron's display list only; the overlay's
    // display (opts.overlayBounds().displayId) is the one to avoid.
    let avoid = null;
    try {
      const ob = typeof opts.overlayBounds === "function" ? opts.overlayBounds() : null;
      const od = ob ? screen.getAllDisplays().find((d) => d.id === ob.displayId) : null;
      avoid = od ? od.workArea : null;
    } catch (e) {
      avoid = null;
    }
    const placed = Link.windowBounds(readState(), areas, avoid);
    win = new BrowserWindow({
      x: placed.bounds.x, y: placed.bounds.y,
      width: placed.bounds.width, height: placed.bounds.height,
      minWidth: Link.MIN_SIZE.width, minHeight: Link.MIN_SIZE.height,
      show: false,
      title: "AshLight",
      icon: iconImage(),
      backgroundColor: "#0f1216", // kit dark surface (TD-04)
      autoHideMenuBar: true,
      frame: true, // the standard Windows title bar: minimize, maximize, X
      webPreferences: {
        session: clientSession(), // the PARTITION session, never the overlay's
        preload: PRELOAD, // fixed argument-free actions only (ruling Q-08)
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        spellcheck: false,
        devTools: opts.devTools === true
      }
    });
    win.setMenu(null);
    win.webContents.on("will-navigate", (e) => route(e, e.url, false));
    win.webContents.on("will-redirect", (e) => route(e, e.url, false));
    win.webContents.setWindowOpenHandler((details) => {
      route(null, details.url, true);
      return { action: "deny" };
    });
    win.webContents.on("did-finish-load", () => {
      const shown = win.webContents.getURL();
      log("client: " + (Link.isCoreUrl(shown, port) ? "dashboard" : "starting page") + " shown");
    });
    win.on("page-title-updated", (e) => e.preventDefault()); // always "AshLight"
    win.on("resize", saveSoon);
    win.on("move", saveSoon);
    win.on("close", saveState);
    win.on("closed", () => {
      if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
      win = null;
      refresh();
      noteClosedToTray();
    });
    for (const ev of ["minimize", "restore", "show", "hide"]) { win.on(ev, refresh); }
    win.once("ready-to-show", () => {
      if (inactive === true) { win.showInactive(); return; }
      if (placed.maximized) { win.maximize(); }
      win.show();
    });
    if (typeof opts.onWindow === "function") { opts.onWindow(win, clientSession()); }
    win.loadFile(STARTING_HTML);
    connect();
  }

  function companionShown() {
    return !!(win && !win.isDestroyed() && win.isVisible() && !win.isMinimized());
  }

  /* Tray "Minimize / Restore AshLight". */
  function toggleCompanion() {
    if (companionShown()) { win.minimize(); } else { open(); }
  }

  /* Tray "Quit AshLight": everything stops (scripts\stop.ps1: core,
     supervisor, this client and so its overlay). */
  function quit() {
    Launcher.stopAll(opts.repo);
    app.quit();
  }

  function currentPrefs() {
    if (!prefs) { prefs = Link.loadPrefs(opts.runtimeDir); }
    return prefs;
  }

  /* Tray "Open AshLight when the game wakes": flip and keep the switch. */
  function toggleWake() {
    prefs = { wake: !currentPrefs().wake };
    try {
      Link.savePrefs(opts.runtimeDir, prefs);
    } catch (e) {
      log("client: preferences not saved: " + e.message);
    }
    refresh();
  }

  /* The recorded "Start with Windows" choice (autostart.json). */
  function currentAutostart() {
    return Launcher.readAutostart(opts.runtimeDir);
  }

  /* Run scripts\autostart.ps1 -Enable / -Disable hidden; one run at a
     time; the tray checkbox follows the record once the script exits. */
  function setAutostart(on) {
    if (autostartBusy) { return 0; }
    autostartBusy = true;
    const pid = Launcher.setAutostart(opts.repo, on === true, undefined, (code) => {
      autostartBusy = false;
      log("client: autostart " + (on === true ? "-Enable" : "-Disable") + " exited (" + code + ")");
      refresh();
    });
    log("client: scripts\\autostart.ps1 " + (on === true ? "-Enable" : "-Disable") +
        " started (pid " + pid + ")");
    return pid;
  }

  /* Tray "Start with Windows": flip the recorded choice. */
  function toggleAutostart() {
    return setAutostart(!currentAutostart());
  }

  function trayMenu() {
    return Menu.buildFromTemplate(TrayMenu.trayTemplate(
      { overlayOn: opts.overlayVisible(), companionShown: companionShown(),
        wakeOn: currentPrefs().wake, autostartOn: currentAutostart() },
      { toggleCompanion: toggleCompanion, toggleOverlay: () => opts.toggleOverlay(),
        toggleWake: toggleWake, toggleAutostart: toggleAutostart,
        restart: () => opts.restartOverlay(), quit: quit }));
  }

  /* X closed the window: say once per run that AshLight is still here. */
  function noteClosedToTray() {
    if (closedNoteShown || !tray) { return; }
    closedNoteShown = true;
    try {
      tray.displayBalloon({ title: "AshLight", content: TrayMenu.CLOSED_NOTE,
                            iconType: "info", noSound: true });
    } catch (e) { /* notes off: the tooltip says the same */ }
  }

  function ensureTray() {
    if (tray) { return; }
    tray = new Tray(iconImage());
    tray.setToolTip(TrayMenu.TOOLTIP);
    tray.setContextMenu(trayMenu());
    tray.on("click", open); // left-click restores the companion
  }

  /* Is this IPC sender the companion window's main frame on the core? */
  function isCompanion(e) {
    return !!(win && !win.isDestroyed() && e && e.sender === win.webContents &&
      e.senderFrame && e.senderFrame === win.webContents.mainFrame &&
      Link.isCoreUrl(e.senderFrame.url, port));
  }

  /* Show the window (create it when closed) and the tray.
     REL-AUTOSTART-TRAY (decision 0041 amendment 2026-11-18): the FIRST
     open of a --client --tray start (the opt-in logon task) builds the
     tray and connects the core (starting it through the launcher when it
     does not answer) but creates no window and takes no focus; the overlay
     follows the log as always (decision 0029). Any later open (a tray
     click, the Start Menu shortcut's --client start) shows the window. */
  let firstOpen = true;
  function open() {
    ensureTray();
    const trayOnly = firstOpen &&
      Link.wantsTray(Array.isArray(opts.argv) ? opts.argv : process.argv);
    firstOpen = false;
    if (trayOnly) {
      log("client: tray-only start (logon); no window until asked");
      connect();
      return;
    }
    if (win && !win.isDestroyed()) {
      if (win.isMinimized()) { win.restore(); }
      win.show();
      win.focus();
      return;
    }
    createWindow();
  }

  /* The overlay's display rect (its layout's displayId), or null. */
  function overlayArea() {
    try {
      const ob = typeof opts.overlayBounds === "function" ? opts.overlayBounds() : null;
      const od = ob ? screen.getAllDisplays().find((d) => d.id === ob.displayId) : null;
      return od ? od.bounds : null;
    } catch (e) {
      return null;
    }
  }

  /* The log woke (w: {wasIdle, fresh}, from the wake part): bring a hidden
     companion back without focus, only on a display that is not the
     overlay's. Returns the action taken ("showInactive" or "stay"). */
  function wake(w) {
    const hidden = !companionShown();
    const action = Link.wakeAction({
      wasIdle: !!(w && w.wasIdle === true), fresh: !!(w && w.fresh === true),
      hidden: hidden, bounds: readState(), overlayArea: overlayArea(),
      areas: screen.getAllDisplays().map((d) => d.bounds), enabled: currentPrefs().wake === true
    });
    if (action !== "showInactive") { return "stay"; }
    ensureTray();
    if (win && !win.isDestroyed()) {
      win.showInactive(); // restores a minimised window without activating it
    } else {
      createWindow(true);
    }
    log("client: companion shown again (the game woke)");
    return action;
  }

  /* The core restarted with a new token: show the dashboard again. */
  function reload() {
    if (win && !win.isDestroyed() && !starting && opts.readToken() !== shownToken) {
      showDashboard();
    }
  }

  /* The overlay was shown or hidden: keep the tray checkbox true. */
  function refresh() {
    if (tray) { tray.setContextMenu(trayMenu()); }
  }

  /* The preload's autostart actions (ruling Q-08): fixed channels, no
     data read from the message, honoured only from the companion window's
     main frame on the local core. */
  if (ipcMain) {
    ipcMain.on("al:autostart-on", (e) => { if (isCompanion(e)) { setAutostart(true); } });
    ipcMain.on("al:autostart-off", (e) => { if (isCompanion(e)) { setAutostart(false); } });
    ipcMain.handle("al:autostart-state", (e) =>
      (isCompanion(e) ? { enabled: currentAutostart() } : null));
  }

  function hasTray() { return tray !== null; }

  function dispose() {
    if (tray) { tray.destroy(); tray = null; }
  }

  return { open, reload, refresh, hasTray, dispose, isCompanion, toggleCompanion, quit,
           wake, toggleWake, toggleAutostart, setAutostart, window: () => win,
           tray: () => tray };
}

module.exports = { createClient, PARTITION, STATE_FILE };
