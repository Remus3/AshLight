/* AshLight dashboard panel: Settings > Reading and web data's first rows,
   the log record line and the bar status word, moved out of web/app.js by
   TEST-WEB-PANELS-C2 (finding F-135; research 0047 R4 (c)).

   The opt-in is region C's setup card (web/setupcard.js); the opt-out,
   the log path and the reading state are in Settings, Reading and web
   data (PLAY-TD-21A-SETTINGS-RAIL), where the bar status word leads. The
   Settings rail (web/rail.js) starts here too: it wires that word's jump.

   The blocks moved verbatim: stopReading, readingView (READING-VIEW),
   ledgerView (LEDGER-VIEW), paintLedger, toggleLedger, showPill and
   showReading, plus the "consent", "reading" entries and the rail's start.
   What the panel shares with the page ($, api, render, setText, setPill,
   the snapshot and the feed's last event) is reached through
   window.ALApp.host, which app.js sets before start(); on its wire it
   fills host.readLink.show, so app.js's setLink repaints the bar word.

   The two clicks post POST /api/consent only, as before: no clipboard, no
   timer, no new request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel, more, entries}; in the page the file
   registers its three entries with window.ALApp (web/registry.js):
   "consent" 70 and "reading" 80, the names and orders app.js gave them
   before the move, and "rail" 310, after every other wire, where app.js
   started the rail right after the panels' wires. The core links this
   file at the panels marker of index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    api.entries(function () { return root.ALApp.host; }).forEach(function (spec) {
      root.ALApp.register(spec);
    });
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "consent";
  var ORDER = 70; // app.js gave "consent" 70 before the move
  var MORE = [["reading", 80], ["rail", 310]];

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, render, setText, setPill, getSnap, getLink;
  var D = null; // web/status.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("consent: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; render = host.render; setText = host.setText;
    setPill = host.setPill; getSnap = host.getSnap; getLink = host.getLink;
    D = window.ALDash;
    bound = true;
  }

  function showPill(id, p) { setPill($(id), p.state, p.glyph, p.word); }

  /* PLAY-TD-09C-BAR: the one bar status word, the worse of the
     Client.txt reading state and the feed state (MERGE-SEAMS F2) */
  function showReading() {
    var snap = getSnap();
    var link = getLink();
    showPill("reading", D.barStatus(snap ? snap.tailer : null, link.event, link.everLive));
  }

  /* "Stop reading Client.txt": the opt-out click. The failure line is not
     a live region; the button points at it (aria-describedby). */
  function stopReading() {
    var said = $("consent-said");
    said.textContent = "";
    api("POST", "/api/consent", { consent: false }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      said.textContent = "Your choice was not saved. Try again.";
      console.warn("consent failed: " + e.message);
    });
  }

  /* READING-VIEW:begin (app/test/rail.test.js runs this function alone;
     keep it self-contained ES5)
     PLAY-TD-21A-SETTINGS-RAIL: the Reading and web data section's first
     rows from the snapshot's tailer block: the reading state in plain
     words, the log file AshLight uses ("" for none) and whether "Stop
     reading Client.txt" shows (only while the player has allowed it). */
  function readingView(tl) {
    tl = tl || {};
    var path = typeof tl.path === "string" ? tl.path.trim() : "";
    var state;
    if (tl.consented !== true) {
      state = "AshLight is not reading Client.txt. The setup card on Play asks first.";
    } else if (tl.reading === true) {
      state = "AshLight is reading Client.txt.";
    } else {
      state = "Allowed, but AshLight is not reading Client.txt now. Checks says why.";
    }
    return { state: state, path: path ? "Log file: " + path : "", stop: tl.consented === true };
  }
  /* READING-VIEW:end */

  /* LEDGER-VIEW:begin (app/test/dashboard.test.js runs this function alone;
     keep it self-contained ES5)
     RUN-LEDGER-CONSENT (decision 0071): the log record's consent line from
     the snapshot's tailer block. Shown only while Client.txt is read; the
     record is on only when the core says ledger === true (the Client.txt
     opt-in alone never turns it on). `send` is what the button posts. */
  function ledgerView(tl) {
    tl = tl || {};
    var shown = tl.consented === true;
    var on = shown && tl.ledger === true;
    var what = " AshLight counts the kinds of log lines it reads and keeps " +
      "their shapes on this computer. Names, chat and item words are blanked " +
      "out. Nothing is sent.";
    if (on) {
      return { shown: true, on: true, send: false, button: "Stop the log record",
               text: "Log record: on." + what + " Stopping it deletes the file." };
    }
    return { shown: shown, on: false, send: true, button: "Allow the log record",
             text: "Log record: off. When on," + what };
  }
  /* LEDGER-VIEW:end */

  var ledgerSend = true;

  function paintLedger(tl) {
    var v = ledgerView(tl);
    ledgerSend = v.send;
    $("ledger-line").hidden = !v.shown;
    setText($("ledger-text"), v.text);
    setText($("ledger-allow"), v.button);
  }

  /* The log record's own Allow / Stop click (decision 0071): posts only the
     ledger flag; the failure line is not a live region. */
  function toggleLedger() {
    var said = $("ledger-said");
    said.textContent = "";
    api("POST", "/api/consent", { ledger: ledgerSend }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      said.textContent = "Your choice was not saved. Try again.";
      console.warn("ledger consent failed: " + e.message);
    });
  }

  function paint(s) {
    var tl = s.tailer || {};
    var rv = readingView(tl);
    setText($("reading-state"), rv.state);
    setText($("reading-path"), rv.path);
    if ($("reading-path").getAttribute("title") !== rv.path) {
      $("reading-path").setAttribute("title", rv.path);
    }
    $("reading-path").hidden = !rv.path;
    if (window.ALLogPath) { window.ALLogPath.paint(document, s); } // SEC-LOG-PATH-FIELD
    $("consent-no").hidden = !rv.stop;
    $("events-empty").textContent = D.emptyText(!!tl.consented);
    paintLedger(tl);
  }

  function wire(host) {
    $("consent-no").addEventListener("click", stopReading);
    if (window.ALLogPath) { window.ALLogPath.wire(document, api, render); }
    $("ledger-allow").addEventListener("click", toggleLedger);
    host.readLink.show = showReading;
  }

  /* PLAY-TD-21A-SETTINGS-RAIL: the Settings rail, the bar status word's
     jump and the data-jump buttons; before the first push, so a failing
     check shows the Checks section (web/rail.js) */
  function startRail() {
    if (window.ALRail) {
      window.ALRail.start(document, { tabs: window.ALTabs || null,
        observe: typeof window.ResizeObserver === "function" ? window.ResizeObserver : null });
    }
  }

  /* The registry entries; getHost is read on the first paint or wire, when
     web/app.js has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      paint: function (s) { bind(getHost()); paint(s); },
      wire: function () { var h = getHost(); bind(h); wire(h); }
    };
  }

  function entries(getHost) {
    return [panel(getHost), {
      name: "reading",
      order: 80,
      paint: function () { bind(getHost()); showReading(); }
    }, {
      name: "rail",
      order: 310,
      wire: function () { startRail(); }
    }];
  }

  return { name: NAME, order: ORDER, panel: panel, more: MORE, entries: entries };
}));
