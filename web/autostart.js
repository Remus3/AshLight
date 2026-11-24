/* AshLight dashboard: the 'Start with Windows' row of Settings > Appearance
   and tools (REL-AUTOSTART-SETTINGS; F-073; decision 0011, ruling Q-08).
   UMD like web/checks.js: CommonJS for node --test
   (app/test/autostart_row.test.js), window.ALAutostart for the page.

   The same switch as the tray's "Start with Windows" checkbox
   (REL-AUTOSTART-SWITCH): the desktop client's preload hands the page three
   fixed, argument-free actions (window.alClient.autostartOn, autostartOff
   and autostartState, a promise of {enabled}); the client runs its own
   scripts\autostart.ps1 and records the choice. This file only shows the
   recorded choice and passes the player's click on. In a plain browser
   there is no client: the box is disabled and the row says to set it in
   the AshLight app. Autostart is off by default (decision 0011).

   ZERO-CLICK: one read of the record at wire time; after a click the row
   reads the record again a few times (RECHECK_MS, bounded), so it follows
   the recorded state by itself once the script has run. No clipboard, no
   live region (the box points at its answer line), no request to the
   core. SAVE-FAIL-SAY (design finding AS-1): a save that fails ("Not
   saved") is also said in the page's one shared polite line, the header's
   #tab-news, through ALTabs.say (design 0001 N6; a region of its own would
   breach the 6-region cap of tests/test_a11y.py). */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(function () {
    return common ? require("./tabs.js") : root.ALTabs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALAutostart = api;
  }
}(typeof self !== "undefined" ? self : this, function (tabs) {
  "use strict";

  var LABEL = "Start with Windows";
  var RECHECK_MS = [1500, 4000, 10000];
  var T = {
    browser: "Set this in the AshLight app.",
    reading: "Reading your choice.",
    on: "AshLight starts in the tray when you sign in to Windows.",
    off: "AshLight starts only when you open it.",
    saving: "Saving your choice.",
    notSaved: "Not saved. Try again.",
    unknown: "AshLight couldn't read this choice. Try again later."
  };

  /* The client's three actions, or null (a plain browser, an older
     client). */
  function clientOf(c) {
    return c && typeof c.autostartOn === "function" && typeof c.autostartOff === "function" &&
      typeof c.autostartState === "function" ? c : null;
  }

  /* The row. client: window.alClient (or null); rec: the recorded state
     ({enabled}), null while not read yet, "failed" when the read failed;
     want: the value the last click asked for, or null.
     -> {client, disabled, checked, line} */
  function model(client, rec, want) {
    if (!clientOf(client)) {
      return { client: false, disabled: true, checked: false, line: T.browser };
    }
    if (rec === "failed") {
      return { client: true, disabled: true, checked: false, line: T.unknown };
    }
    var known = rec && typeof rec === "object" && typeof rec.enabled === "boolean";
    if (!known) {
      return { client: true, disabled: true, checked: false, line: T.reading };
    }
    if (typeof want === "boolean" && want !== rec.enabled) {
      return { client: true, disabled: true, checked: want, line: T.saving };
    }
    return { client: true, disabled: false, checked: rec.enabled === true,
      line: rec.enabled === true ? T.on : T.off };
  }

  /* Say a line in the header's polite #tab-news (ALTabs.say); a page
     without tabs says nothing. */
  function say(doc, text) {
    var t = tabs();
    if (t && typeof t.say === "function") { t.say(doc, text); }
  }

  /* The visible "Not saved" line, said on the polite line as well. */
  function notSaved(doc) {
    doc.getElementById("autostart-said").textContent = T.notSaved;
    say(doc, T.notSaved);
  }

  /* Show a model in #autostart-row. */
  function paint(doc, m) {
    var box = doc.getElementById("autostart-on");
    var said = doc.getElementById("autostart-said");
    if (!box || !said) { return m; }
    box.checked = m.checked === true;
    box.disabled = m.disabled === true;
    said.textContent = m.line;
    return m;
  }

  /* Read the record once, then follow the player's clicks. client:
     window.alClient; timers (tests): {set(fn, ms)}. Returns a small handle
     for tests: {state()}. */
  function wire(doc, client, timers) {
    var c = clientOf(client);
    var held = { rec: null, want: null, gen: 0 };
    var set = timers && typeof timers.set === "function" ? timers.set
      : function (fn, ms) { return setTimeout(fn, ms); };
    function show() { return paint(doc, model(c, held.rec, held.want)); }
    show();
    var box = doc.getElementById("autostart-on");
    if (!c || !box) { return { state: function () { return held; } }; }

    /* one read of the record; a stale answer (an older click's) is dropped */
    function read(gen, last) {
      var p;
      try { p = Promise.resolve(c.autostartState()); } catch (e) { p = Promise.reject(e); }
      return p.then(function (r) {
        if (gen !== held.gen) { return; }
        if (r && typeof r.enabled === "boolean") {
          held.rec = { enabled: r.enabled };
          if (held.want === r.enabled) { held.want = null; }
        } else if (held.rec === null) {
          held.rec = "failed";
        }
        if (last && held.want !== null) {
          // the script did not change the record: say so, keep the record
          held.want = null;
          show();
          notSaved(doc);
          return;
        }
        show();
      }, function () {
        if (gen !== held.gen) { return; }
        if (held.rec === null) { held.rec = "failed"; }
        if (last) { held.want = null; }
        show();
      });
    }

    box.addEventListener("change", function () {
      if (!held.rec || held.rec === "failed" || held.want !== null) { show(); return; }
      var want = box.checked === true;
      if (want === held.rec.enabled) { show(); return; }
      held.want = want;
      held.gen += 1;
      var gen = held.gen;
      try {
        if (want) { c.autostartOn(); } else { c.autostartOff(); }
      } catch (e) {
        held.want = null;
        show();
        notSaved(doc);
        return;
      }
      show();
      RECHECK_MS.forEach(function (ms, i) {
        set(function () {
          if (gen === held.gen && held.want !== null) { read(gen, i === RECHECK_MS.length - 1); }
        }, ms);
      });
    });
    read(held.gen, false);
    return { state: function () { return held; } };
  }

  return { model: model, paint: paint, wire: wire, TEXT: T, LABEL: LABEL,
    RECHECK_MS: RECHECK_MS };
}));
