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
   handlers are registered here and answer only isCompanion() senders.

   RUN-START-REASON-CLIENT (F-091): when the core did not answer, the
   starting page shows the one line of <runtime>\start-error.json (the
   core's "fix" sentence for a port it could not bind) when that record is
   from this start attempt (startErrorLine): printable ASCII, at most
   REASON_MAX characters, never a path or a script name; it reaches the
   page as a query value and is shown as text only.

   RUN-SECOND-LINE-CLIENT (F-127, decision 0005 amendment 2026-11-18): the
   client is the last line when the core and its supervisor are both down.
   A timer in this (main) process, never in the overlay page, runs the
   same hello health check every WATCH_MS (30 s); after WATCH_FAILS (4)
   failed checks in a row it runs scripts\run.ps1 once through the
   launcher, at most once per WATCH_GAP_MS (15 min), counting the start
   connect() makes. run.ps1 is idempotent per component (decision 0010),
   so it starts only the missing core and supervisor, never a second
   client (decision 0041). When the supervisor gave up (keepalive.json
   "gave-up", Launcher.readGiveUp) its reason is shown in words
   (giveUpLine: fixed text, a number and a reason word, never a path) on
   the failed page when the core left no start-error line; an open
   companion follows the watch's start through the starting page to the
   dashboard or that failed page. No tray note: nothing pops up by itself
   (design 0001 section 7.1).

   OVL-APP-SCHEME (decision 0061 amendment 2026-11-21): the starting page
   loads from the app scheme (app/pages.js, served on this window's session
   by app/parts/12-pages.js from the clientWindow hook, which runs before
   the first load), with a header CSP that lets it connect nowhere; never
   from file://. */

const fs = require("fs");
const path = require("path");
const Link = require("./link.js");
const Brand = require("../brand/index.js"); // BRAND-ICON (design 0005)
const Launcher = require("./launcher.js");
const TrayMenu = require("./tray_menu.js");
const Pages = require("../pages.js");

const PARTITION = "persist:client";
const STARTING_PAGE = Pages.STARTING_PAGE; // client/starting.html on the app scheme
const PRELOAD = path.join(__dirname, "preload.js");
const STATE_FILE = "client-window.json";
const CORE_WAIT_MS = 30000;
const CORE_STEP_MS = 500;
const SAVE_DELAY_MS = 500;
const ALLOWED_PERMISSION = "clipboard-sanitized-write";
const START_ERROR_FILE = "start-error.json";
const START_ERROR_MAX = 4096;
const REASON_MAX = 300;
const REASON_SLACK_MS = 60000; // a record up to 1 min before the attempt counts
const NO_PATH = /[A-Za-z]:[\/]|\\|\.(ps1|psm1|py|pyw|exe|bat|cmd|js)\b/i;

/* The core's one-line reason for a failed start, or "": the "fix" of
   <runtimeDir>/start-error.json when the file is small, its "at" (UNIX
   seconds) is no older than sinceMs minus REASON_SLACK_MS, and the line is
   printable ASCII without a path or a script name. Never throws. */
function startErrorLine(runtimeDir, sinceMs, fsi) {
  const f = fsi || fs;
  try {
    const file = path.join(runtimeDir, START_ERROR_FILE);
    const st = f.statSync(file);
    if (!st.isFile() || st.size > START_ERROR_MAX) { return ""; }
    const doc = JSON.parse(f.readFileSync(file, "utf8"));
    if (!doc || typeof doc !== "object" || typeof doc.fix !== "string") { return ""; }
    if (typeof doc.at !== "number" || !isFinite(doc.at)) { return ""; }
    if (typeof sinceMs === "number" && doc.at * 1000 < sinceMs - REASON_SLACK_MS) { return ""; }
    const line = doc.fix.trim();
    if (!line || line.length > REASON_MAX || !/^[\x20-\x7e]+$/.test(line)) { return ""; }
    return NO_PATH.test(line) ? "" : line;
  } catch (e) {
    return "";
  }
}

/* The page options of the failed page: #failed, plus the reason line
   as the one query value when there is one (startingUrl builds the URL). */
function failedPage(line) {
  return line ? { hash: "failed", query: { reason: line } } : { hash: "failed" };
}

/* The starting page's app scheme URL, with failedPage's options or none. */
function startingUrl(options) {
  return Pages.urlFor(STARTING_PAGE, options);
}

/* RUN-SECOND-LINE-CLIENT: the core watch. */
const WATCH_MS = 30000;
const WATCH_FAILS = 4;
const WATCH_GAP_MS = 15 * 60 * 1000;
// the words of server/al/plug/supervisor.py REASON_WORDS
const GIVE_UP_WORDS = {
  "hung": "it had stopped answering",
  "crash": "it had closed unexpectedly",
  "start-crash": "it closed while starting",
  "start-timeout": "it did not finish starting"
};

/* The supervisor's give-up record (Launcher.readGiveUp) as one sentence,
   or "" for none. Built only from fixed words, the restart count and a
   known reason word; printable ASCII without a path, as startErrorLine. */
function giveUpLine(rec) {
  if (!rec || typeof rec !== "object") { return ""; }
  const n = rec.restarts;
  const count = Number.isInteger(n) && n >= 1 && n <= 1000
    ? " after " + n + (n === 1 ? " try" : " tries") : "";
  const why = Object.prototype.hasOwnProperty.call(GIVE_UP_WORDS, rec.reason)
    ? " (" + GIVE_UP_WORDS[rec.reason] + ")" : "";
  const line = "AshLight stopped restarting its core" + count + why + ".";
  return line.length <= REASON_MAX && /^[\x20-\x7e]+$/.test(line) && !NO_PATH.test(line) ? line : "";
}

/* The watch's state machine, one tick per health check. o: {check (a
   promise of true / false), start (runs scripts\run.ps1), now, fails,
   gapMs}. tick() resolves "ok", "fail" (the streak is short), "start"
   (fails failed checks in a row and no start in the last gapMs: start()
   ran once) or "held" (a start is due but one ran inside gapMs; the
   streak keeps counting, so the first failed check after the hold
   starts). noteStart(t) records a start made elsewhere (connect()). */
function makeWatch(o) {
  const clock = typeof o.now === "function" ? o.now : Date.now;
  const fails = Number.isInteger(o.fails) && o.fails > 0 ? o.fails : WATCH_FAILS;
  const gapMs = typeof o.gapMs === "number" && o.gapMs >= 0 ? o.gapMs : WATCH_GAP_MS;
  let streak = 0;
  let lastStart = null;
  function noteStart(t) {
    lastStart = typeof t === "number" ? t : clock();
    streak = 0;
  }
  function tick() {
    return Promise.resolve().then(o.check).then((ok) => ok === true, () => false).then((ok) => {
      if (ok) { streak = 0; return "ok"; }
      streak += 1;
      if (streak < fails) { return "fail"; }
      const t = clock();
      if (lastStart !== null && t - lastStart < gapMs) { return "held"; }
      noteStart(t);
      o.start();
      return "start";
    });
  }
  return { tick, noteStart, streak: () => streak };
}

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
  let watchTimer = null; // RUN-SECOND-LINE-CLIENT: the next health check

  /* RUN-SECOND-LINE-CLIENT: 4 failed checks in a row run scripts\run.ps1
     once (at most once per 15 minutes). An open companion follows the
     start as connect() does: the starting page, then the dashboard, or the
     failed page with the supervisor's give-up reason. No tray note (design
     0001 section 7.1: nothing pops up by itself). */
  const watch = makeWatch({
    check: healthy,
    start: () => {
      const since = Date.now();
      const reason = giveUpNow();
      const pid = Launcher.startCore(opts.repo, port);
      log("client: core down for " + WATCH_FAILS + " checks; scripts\\run.ps1 started (pid " +
          pid + ")" + (reason ? "; supervisor gave up: " + reason : ""));
      followStart(since);
    }
  });

  function watchStep() {
    watchTimer = null;
    const busy = starting !== null; // connect() is waiting on its own start
    (busy ? Promise.resolve("busy") : watch.tick()).catch(() => "fail").then(() => {
      if (watchTimer === null && watching) { scheduleWatch(); }
    });
  }

  let watching = false;
  function scheduleWatch() {
    watchTimer = setTimeout(watchStep, WATCH_MS);
    if (watchTimer && typeof watchTimer.unref === "function") { watchTimer.unref(); }
  }

  function startWatch() {
    if (watching) { return; }
    watching = true;
    scheduleWatch();
  }

  function stopWatch() {
    watching = false;
    if (watchTimer) { clearTimeout(watchTimer); watchTimer = null; }
  }

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

  /* The supervisor's give-up sentence, or "". */
  function giveUpNow() {
    return giveUpLine(Launcher.readGiveUp(opts.runtimeDir));
  }

  /* The failed page, with the core's reason when this attempt left one,
     else the supervisor's give-up reason when it gave up. */
  function showFailed(sinceMs) {
    if (!win || win.isDestroyed()) { return; }
    let line = startErrorLine(opts.runtimeDir, sinceMs);
    if (line) {
      log("client: start error: " + line);
    } else {
      line = giveUpNow();
      if (line) { log("client: supervisor gave up: " + line); }
    }
    win.loadURL(startingUrl(failedPage(line)));
  }

  function showDashboard(sinceMs) {
    if (!win || win.isDestroyed()) { return; }
    const token = opts.readToken();
    const url = Link.dashboardUrl(port, token);
    shownToken = url ? token : "";
    if (url) { win.loadURL(url); } else { showFailed(sinceMs); }
  }

  /* Load the dashboard once the core answers; start it (scripts\run.ps1)
     when it does not. One start attempt per window open. */
  function connect() {
    if (starting) { return starting; }
    const since = Date.now();
    starting = healthy().then((ok) => {
      if (ok) { return true; }
      const pid = Launcher.startCore(opts.repo, port);
      watch.noteStart(); // counts toward the watch's one start per 15 minutes
      log("client: core not answering; scripts\\run.ps1 started (pid " + pid + ")");
      return Link.waitFor(healthy, CORE_WAIT_MS, CORE_STEP_MS);
    }).then((ok) => settle(ok, since));
    return starting;
  }

  /* The end of a start attempt: the dashboard, or the failed page. */
  function settle(ok, since) {
    starting = null;
    if (!win || win.isDestroyed()) { return; }
    if (ok) {
      showDashboard(since);
    } else {
      log("client: core did not answer within " + CORE_WAIT_MS / 1000 + " s");
      showFailed(since);
    }
  }

  /* RUN-SECOND-LINE-CLIENT: the watch started the core; an open window
     waits for it on the starting page (a closed one has nothing to show). */
  function followStart(since) {
    if (starting || !win || win.isDestroyed()) { return; }
    win.loadURL(startingUrl());
    starting = Link.waitFor(healthy, CORE_WAIT_MS, CORE_STEP_MS).then((ok) => settle(ok, since));
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
    win.loadURL(startingUrl());
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
    startWatch(); // RUN-SECOND-LINE-CLIENT: from the client's first open
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
    stopWatch();
    if (tray) { tray.destroy(); tray = null; }
  }

  return { open, reload, refresh, hasTray, dispose, isCompanion, toggleCompanion, quit,
           wake, toggleWake, toggleAutostart, setAutostart, window: () => win,
           tray: () => tray };
}

module.exports = { createClient, startErrorLine, failedPage, startingUrl, PARTITION, STATE_FILE,
                   START_ERROR_FILE, REASON_MAX, giveUpLine, makeWatch, WATCH_MS, WATCH_FAILS,
                   WATCH_GAP_MS };
