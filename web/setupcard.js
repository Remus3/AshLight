/* AshLight dashboard: region C, the setup, error and idle modes
   (PLAY-TD-12-CONTEXT-SETUP; plan 03 TD-12, F-069, F-068; sections 3.4,
   3.5 and 3.6).

   web/context.js owns region C and picks its one mode (web/slots.js
   contextMode, first match). This file paints three of them through
   ALContext.mode(name, painter) and retires the legacy c-setup group (the
   old consent card and the old Last session card):

   - setup (F-069): no opt-in yet. The title "Set up AshLight", the ask
     row, the log path (14 px, its end kept when cut), ONE button row
     with the floor's opt-in words "Allow reading Client.txt" (the only
     button.primary of the app, 36 px), then 3 step rows (your build,
     prices, overlay) with a state glyph and word only and no control,
     and the promise line (dropped in the compact class). Rows come
     composed from the core (snap.play.context.setup,
     server/al/playcards.py setup_block); a missing block falls back to
     the same words here. The click posts /api/consent {consent: true}
     through ctx.api exactly as the legacy card did: explicit, revocable
     with "Stop reading Client.txt", and the bar's reading indicator is
     not touched. Web data stays off until ticked in Settings (decision
     0013); the prices row only says so.
   - error: reading is not possible. What is wrong (2 rows), what
     AshLight does and what the player can do (3 rows), and one in-app
     control, "Open Checks" (Settings > Checks); the nopath kind names the
     typed game folder field and its button "Type the folder" jumps there
     (#logpath-in through ALRail.jump, UX-NOPATH-TYPE-FOLDER). Never a file to edit or
     a shell command. The lost kind has no button: Checks comes from the
     AshLight that is not answering, so its last row says to quit from
     the tray and reopen it, and the page reconnects by itself
     (UX-LOST-MODE-NO-DEADEND, 136 px).
   - idle: game_idle (decision 0029). "Last session" from the core's
     block (6 label: value rows and an "Ended ..." facts row); shown only
     while the snapshot says game_idle, because contextMode picks idle
     only then.

   Line boxes (s = 1): title 26, body rows 22, the path row 20, a button
   row 36, facts 20, no gaps: setup 190 px (170 compact), error 172, idle
   178, inside C's 206 px (190 compact) of content box.

   No timers, no clipboard, nothing sent to the game. ALTabs.notify is not
   called (the legacy path keeps doing that until PLAY-LEGACY-OUT).
   Registers {name: setupcard, region: c, retires: [c-setup]} with
   web/regions.js. UMD like web/context.js: CommonJS for node --test
   (app/test/setupcard.test.js, which calls install(ALContext) itself),
   window.ALSetupCard in the page (installed on load). */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(root);
  if (common) {
    module.exports = api;
  } else {
    root.ALSetupCard = api;
    api.install(root.ALContext || null);
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (ROOT) {
  "use strict";

  var NAME = "setupcard";
  var REGION = "c";
  var RETIRES = ["c-setup"];
  var MODES = ["setup", "error", "idle"];

  /* the floor's opt-in words (CLAUDE.md, decision 0003): unchanged */
  var CONSENT_BUTTON = "Allow reading Client.txt";
  var SETUP_TITLE = "Set up AshLight";
  var SETUP_ASK = "AshLight follows your game through its log file.";
  var SETUP_NO_PATH = "Client.txt not found yet. Start the game once.";
  var SETUP_PROMISE = "Read only. Play in Windowed Fullscreen.";
  var NOT_SAVED = "Not saved. Try again.";
  var CHECKS_BUTTON = "Open Checks";
  /* nopath: the typed game folder field (#logpath-in, Settings > Reading
     and web data) is the fix for a moved install (UX-NOPATH-TYPE-FOLDER) */
  var FOLDER_BUTTON = "Type the folder";
  var FOLDER_FIELD = "logpath-in";
  var FOLDER_ELSE = "reading-title";
  var IDLE_TITLE = "Last session";
  var IDLE_EMPTY = "The game may be closed. Nothing to sum up yet.";
  var PATH_CAP = 52;
  var ELLIPSIS = "...";

  /* error mode: two rows say what is wrong, three what AshLight does and
     what to do; the fix is always an in-app control */
  var ERRORS = {
    missing: {
      title: "Can't read Client.txt",
      rows: ["The game's log is missing or can't be opened.",
             "Zone, level and deaths wait until it is back.",
             "AshLight keeps checking for it by itself.",
             "Start the game once so it writes the log.",
             "Open Checks to see the path AshLight uses."]
    },
    nopath: {
      title: "Client.txt not found",
      rows: ["AshLight has not found the game's log yet.",
             "Zone, level and deaths wait until it is found.",
             "AshLight keeps checking for it by itself.",
             "Start the game once so it writes the log.",
             "Or type the game folder in Settings."],
      button: { text: FOLDER_BUTTON, action: "logpath" }
    },
    lost: {
      title: "AshLight is not answering",
      rows: ["This page lost its link to AshLight.",
             "The numbers on screen are from before.",
             "AshLight restarts itself if it stopped.",
             "This page connects again by itself.",
             "If it stays, quit from the tray and reopen it."],
      // Checks is filled by the same AshLight that is not answering, so a
      // button there would open a stale list (UX-LOST-MODE-NO-DEADEND)
      noButton: true
    }
  };

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function isFn(v) { return typeof v === "function"; }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* A path keeps its end (the file name) when it is cut. */
  function clipLeft(text, cap) {
    return text.length <= cap ? text : ELLIPSIS + text.slice(text.length - (cap - ELLIPSIS.length));
  }

  function row(kind, text, extra) {
    var r = { kind: kind, text: text, full: text };
    if (extra) { Object.keys(extra).forEach(function (k) { r[k] = extra[k]; }); }
    return r;
  }

  /* ---- the views (pure) --------------------------------------------------- */

  /* The setup view from the core's block; the same words when it is
     missing. Exactly one button row, always the opt-in. */
  function setupView(snap, block) {
    var b = isObj(block) ? block : null;
    var rows = [];
    var button = false;
    (b && Array.isArray(b.rows) ? b.rows : []).forEach(function (r) {
      if (!isObj(r) || !str(r.text)) { return; }
      var kind = str(r.kind) || "text";
      if (kind === "button") {
        if (button) { return; }
        button = true;
        rows.push(row("button", CONSENT_BUTTON, { action: "consent" }));
        return;
      }
      rows.push(row(kind, r.text, {
        full: str(r.full) || r.text, glyph: str(r.glyph), state: str(r.state),
        step: str(r.step)
      }));
    });
    if (!b || !rows.length) {
      var tl = isObj(snap) && isObj(snap.tailer) ? snap.tailer : {};
      var path = str(tl.path).trim();
      rows = [row("step", SETUP_ASK, { glyph: "[ ]", state: "pending", step: "log" }),
              path ? row("path", clipLeft(path, PATH_CAP), { full: path })
                : row("path", SETUP_NO_PATH)];
      button = false;
    }
    if (!button) {
      var at = 0;
      while (at < rows.length && rows[at].kind !== "path") { at++; }
      rows.splice(at < rows.length ? at + 1 : rows.length, 0,
        row("button", CONSENT_BUTTON, { action: "consent" }));
    }
    return { mode: "setup", title: (b && str(b.title)) || SETUP_TITLE,
             full: (b && str(b.full)) || (b && str(b.title)) || SETUP_TITLE,
             rows: rows, facts: (b && str(b.facts)) || SETUP_PROMISE, factsDrop: true };
  }

  /* Which error: AshLight lost, no log found, or the log went missing. */
  function errorKind(snap) {
    if (!isObj(snap) || snap.offline === true) { return "lost"; }
    var tl = isObj(snap.tailer) ? snap.tailer : {};
    return str(tl.path) ? "missing" : "nopath";
  }

  function errorView(snap) {
    var kind = errorKind(snap);
    var e = ERRORS[kind];
    var rows = e.rows.map(function (t) { return row("text", t); });
    if (!e.noButton) {
      var b = e.button || { text: CHECKS_BUTTON, action: "checks" };
      rows.push(row("button", b.text, { action: b.action }));
    }
    return { mode: "error", kind: kind, title: e.title, full: e.title, rows: rows,
             facts: "", factsDrop: false };
  }

  /* Last session: the core's block; one plain row while it has none. */
  function idleView(snap, block) {
    var b = isObj(block) ? block : null;
    var rows = (b && Array.isArray(b.rows) ? b.rows : []).filter(function (r) {
      return isObj(r) && str(r.text);
    }).map(function (r) { return row("text", r.text, { full: str(r.full) || r.text }); });
    if (!rows.length) { rows = [row("text", IDLE_EMPTY)]; }
    return { mode: "idle", title: (b && str(b.title)) || IDLE_TITLE,
             full: (b && str(b.full)) || IDLE_TITLE, rows: rows.slice(0, 6),
             facts: b ? str(b.facts) : "", factsDrop: false };
  }

  function view(mode, snap, block) {
    if (mode === "setup") { return setupView(snap, block); }
    if (mode === "error") { return errorView(snap); }
    if (mode === "idle") { return idleView(snap, block); }
    return null;
  }

  /* ---- the DOM -------------------------------------------------------------- */

  var env = { ctx: null, doc: null, busy: false };

  function el(doc, tag, cls) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    return n;
  }

  function clear(n) {
    if (isFn(n.replaceChildren)) {
      n.replaceChildren();
    } else {
      while (n.children && n.children.length) { n.removeChild(n.children[0]); }
      n.textContent = "";
    }
  }

  function regionsApi() { return ROOT && ROOT.ALRegions ? ROOT.ALRegions : null; }
  function contextApi() { return env.context || (ROOT && ROOT.ALContext) || null; }

  function focusHeading(doc) {
    var h = doc && isFn(doc.getElementById) ? doc.getElementById("play-c-h") : null;
    if (h && isFn(h.focus)) {
      h.setAttribute("tabindex", "-1");
      h.focus();
    }
  }

  /* The opt-in: one POST through the page's own api, as the legacy card
     did. The answer's state is painted at once so the card leaves; the
     next push repaints everything else. */
  function consent(doc, ctx, said) {
    var c = ctx || env.ctx || {};
    if (env.busy || !isFn(c.api)) { return null; }
    env.busy = true;
    said.textContent = "";
    var p = c.api("POST", "/api/consent", { consent: true });
    if (!p || !isFn(p.then)) { env.busy = false; return null; }
    return p.then(function (res) {
      env.busy = false;
      var state = isObj(res) && isObj(res.state) ? res.state : null;
      if (!state) { return; }
      var now = isFn(c.serverNow) ? c.serverNow() : Date.now() / 1000;
      var reg = regionsApi();
      var cx = contextApi();
      if (reg && isFn(reg.paint)) {
        reg.paint(doc, state, now);
      } else if (cx && isFn(cx.paint)) {
        cx.paint(doc, state, now, c);
      }
      focusHeading(doc);
    }, function () {
      env.busy = false;
      said.textContent = NOT_SAVED;
    });
  }

  /* Open Checks: Settings, the Checks fold open, focus on its summary
     (the same path as region N's "Open Checks"). */
  function openChecks(doc, ctx) {
    var c = ctx || env.ctx || {};
    var tabs = c.tabs || (ROOT && ROOT.ALTabs) || null;
    if (!tabs || !isFn(tabs.show)) { return false; }
    tabs.show(doc, "settings", false);
    var fold = isFn(doc.getElementById) ? doc.getElementById("checks") : null;
    if (fold) { fold.open = true; }
    var sum = isFn(doc.getElementById) ? doc.getElementById("checks-summary") : null;
    if (sum && isFn(sum.focus)) { sum.focus(); }
    return true;
  }

  /* Type the folder: the rail's jump opens Settings > Reading and web data
     at the field (its heading while the field is hidden); a page with no
     rail opens Settings on Checks, as before. */
  function openFolder(doc, ctx) {
    var c = ctx || env.ctx || {};
    var rail = c.rail || (ROOT && ROOT.ALRail) || null;
    if (rail && isFn(rail.jump)) { return !!rail.jump(doc, FOLDER_FIELD, FOLDER_ELSE); }
    return openChecks(doc, c);
  }

  /* A button row: the consent button keeps a row (.su-act) for its said
     word beside it; any other button is the row itself (PLAY-FIT-G5-TOTALS:
     no wrapper around a lone button). */
  function buttonRow(doc, r, ctx) {
    var btn = el(doc, "button", (r.action === "consent" ? "primary" : "secondary") + " su-btn");
    btn.setAttribute("type", "button");
    btn.setAttribute("data-action", r.action);
    btn.textContent = r.text;
    if (r.action !== "consent") {
      btn.addEventListener("click", function () {
        if (r.action === "logpath") { openFolder(doc, ctx); } else { openChecks(doc, ctx); }
      });
      return btn;
    }
    var wrap = el(doc, "div", "su-act");
    wrap.appendChild(btn);
    var said = el(doc, "span", "su-said row-meta");
    said.setAttribute("role", "status");
    wrap.appendChild(said);
    btn.addEventListener("click", function () { consent(doc, ctx, said); });
    return wrap;
  }

  function textRow(doc, r) {
    var n;
    if (r.kind === "path") {
      n = el(doc, "p", "su-path row-meta muted one-line");
      n.textContent = r.text;
    } else {
      n = el(doc, "p", "su-row row-body one-line");
      if (r.glyph) {
        var g = el(doc, "span", "su-glyph");
        g.setAttribute("aria-hidden", "true");
        g.textContent = r.glyph + " ";
        n.appendChild(g);
        n.appendChild(doc.createTextNode(r.text));
      } else {
        n.textContent = r.text;
      }
      if (r.state) { n.setAttribute("data-state", r.state); }
    }
    n.setAttribute("title", r.full || r.text);
    return n;
  }

  /* Fill a pane from a view; rebuilt only when the view changes, so a
     focused button and its said text stay between pushes. */
  function render(doc, pane, v, ctx) {
    var key = JSON.stringify([v.mode, v.title, v.full, v.rows, v.facts]);
    if (pane.getAttribute("data-key") === key) { return false; }
    clear(pane);
    var h = el(doc, "h3", "ctx-title su-title row-title one-line");
    h.textContent = v.title;
    h.setAttribute("title", v.full || v.title);
    pane.appendChild(h);
    // the rows sit in the pane itself, after the title (no list wrapper)
    v.rows.forEach(function (r) {
      var n = r.kind === "button" ? buttonRow(doc, r, ctx) : textRow(doc, r);
      n.setAttribute("data-kind", r.kind);
      pane.appendChild(n);
    });
    if (v.facts) {
      var f = el(doc, "p", "su-facts row-meta muted one-line" + (v.factsDrop ? " su-promise" : ""));
      f.textContent = v.facts;
      f.setAttribute("title", v.facts);
      pane.appendChild(f);
    }
    pane.setAttribute("data-key", key);
    return true;
  }

  function painter(mode) {
    return function (doc, pane, snap, now, ctx, block) {
      var v = view(mode, snap, block);
      if (v) { render(doc, pane, v, ctx || env.ctx); }
    };
  }

  /* Register the three painters on ALContext (web/context.js). */
  function install(context) {
    if (!context || !isFn(context.mode)) { return false; }
    env.context = context;
    return MODES.every(function (m) { return context.mode(m, painter(m)); });
  }

  function wire(doc, ctx) {
    env.doc = doc;
    env.ctx = ctx || null;
  }

  /* Tests only. */
  function reset() { env = { ctx: null, doc: null, busy: false }; }

  var spec = { name: NAME, region: REGION, retires: RETIRES.slice(), wire: wire };

  return {
    NAME: NAME, REGION: REGION, RETIRES: RETIRES, MODES: MODES,
    CONSENT_BUTTON: CONSENT_BUTTON, CHECKS_BUTTON: CHECKS_BUTTON, NOT_SAVED: NOT_SAVED,
    FOLDER_BUTTON: FOLDER_BUTTON,
    ERRORS: ERRORS, IDLE_TITLE: IDLE_TITLE,
    view: view, errorKind: errorKind, render: render, install: install,
    consent: consent, openChecks: openChecks, openFolder: openFolder, wire: wire, reset: reset, spec: spec
  };
}));
