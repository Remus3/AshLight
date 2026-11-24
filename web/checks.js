/* AshLight dashboard: the Checks tool (DIAG-SELF, ruling J) and the stored
   Hide of the game language notice (LANG-GUARD, ruling K). UMD: CommonJS
   for node --test (app/test/checks.test.js), window.ALChecks for the page.
   The core makes every check, sentence and the redacted report
   (server/al/diag.py, server/al/langguard.py); this file only shows them.
   Region N (web/notice.js) owns the language note itself since
   PLAY-LEGACY-OUT-2 removed the old card: its Hide sets _state.dismissed,
   and this file reads the stored key at wire time and stores a changed
   key on the next paint (key al.lang.dismissed). The clipboard is written
   only inside the "Copy report" click (decision 0014). No timers.
   RUN-REPORT-ROUTE (finding F-109, folded into RUN-VERDICTS-UI): the
   report is built on the player's click by GET /api/report
   (server/al/plug/report.py) and shown first in a read-only preview
   (#checks-preview). The press of the Checks rail button that shows the
   section builds it, so the preview costs no extra click; "Copy report"
   then writes exactly the previewed text, synchronously inside its own
   click. When no preview is there yet (Checks showed by itself, at load
   or on a failure, or the build failed), that click builds and shows it
   and the next one copies; the clipboard is never written after a wait.
   No upload, ever.
   PLAY-TD-21A-SETTINGS-RAIL (TD-21): Checks is section 1 of the Settings
   rail (web/rail.js), no longer a fold. #checks.open is rail.js's
   accessor, so setting it shows the section. The rows page instead of
   folding: ROWS_PAGE (12) a page, Prev / Next only on a press (#checks-
   pager; the pressed button is never re-created or disabled, an end one
   says aria-disabled="true" and does nothing); a new failure shows the
   page holding the first failing row. Every row stays in #checks-list;
   a row off the shown page carries the hidden attribute, so it is out of
   view and out of the accessibility tree, and a page turn only moves
   that attribute (no rebuild).
   VERDICTS-UI-A11Y (design review V-4, V-5): a Copy click that built the
   missing preview says it is below and asks for Copy report again; a
   preview made before a check changed its state is made again by the
   next Copy click (which then copies nothing), so the copy is never an
   older report than the checks on show.
   TC-CALC-OPTIN-BUTTON (decision 0018 opt-in, decision 0041 amendment
   2026-11-20): inside the desktop client only (window.alClient.setupCalc,
   app/client/preload.js) the calc row carries a "Set up the calc" button
   while that row is off or needs a fix; a click runs the client's fixed
   setup script and the row says it is working, then done or not done.
   RUN-QUIET-FEED (findings F-093, F-109): the snapshot holds no report
   text and no age words; age rows carry an absolute "at" and this file
   writes the age in, stepped at 5 minutes (ageText).
   RUN-REPORT-FIELDS (finding F-109, research 0051 R6): the preview holds
   one checkbox (#checks-tails, made here, off on every page load and never
   stored). Ticking it is the player's explicit second choice: the preview
   is made again with GET /api/report?tails=1, which adds the last lines of
   AshLight's own logs through the core's redactor. A Copy click whose
   preview was made with the other choice makes it again and copies
   nothing, so the copy always matches the box on show. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALChecks = api;
    /* TEST-WEB-PANELS-C2 (F-135): the Checks tool registers itself
       (web/registry.js) under the names and orders web/app.js gave it.
       "checks" 180: DIAG-SELF / LANG-GUARD, the core's checks and language
       notice; REL-UPDATE-NOTICE-UI: the version lines and the update line
       (web/updates.js) paint right after the checks, so the Settings tab's
       "fix" mark wins over "update"; the OK click acknowledges the wording.
       "verdicts" 300: RUN-VERDICTS-UI, the 'Tried in game' card (one read,
       then clicks only), wired after every other card, where app.js wired
       it right after the panels' wires. */
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register({
        name: "checks",
        order: 180,
        paint: function (s) {
          api.paint(document, s);
          if (root.ALUpdates) { root.ALUpdates.paint(document, s); }
        },
        wire: function () {
          var host = root.ALApp.host;
          if (root.ALUpdates) {
            // REL-AUTOSTART-SETTINGS: 'Update now' posts with no body, so it
            // gets the page's fetch and token instead of api()
            root.ALUpdates.wire(document, host.api, function () { return host.webState().doc; },
              host.webDataSaved, { fetch: function (url, opts) { return fetch(url, opts); }, token: host.token });
          }
          var store = null;
          try { store = root.localStorage; } catch (e) { store = null; }
          // RUN-REPORT-ROUTE: api builds the report on the click (GET /api/report)
          api.wire(document, function () { return host.getSnap(); }, navigator, store, host.api);
        }
      });
      root.ALApp.register({
        name: "verdicts",
        order: 300,
        wire: function () {
          if (root.ALVerdicts) { root.ALVerdicts.wire(document, root.ALApp.host.api); }
        }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var COPIED = "Report copied. Paste it where you ask for help.";
  var COPY_FAILED = "Couldn't copy the report. Try again.";
  // RUN-REPORT-ROUTE: the preview's own lines
  var REPORT_PATH = "/api/report";
  var BUILDING = "Making the report...";
  var READY = "This is the report. Press Copy report to copy it.";
  // V-4: after a Copy click that had to build the preview first
  var READY_AGAIN = "The report is below. Press Copy report again to copy it.";
  // V-5: after a Copy click that found the preview older than the checks
  var READY_CHANGED = "The checks changed. The new report is below. " +
    "Press Copy report again to copy it.";
  var BUILD_FAILED = "Couldn't make the report. Try again.";
  // RUN-REPORT-FIELDS: the preview's second choice (off by default)
  var TAILS_QUERY = "?tails=1";
  var TAILS_LABEL = "Also add the last lines of AshLight's own logs. " +
    "Paths, names and addresses are masked.";
  var READY_TAILS = "The report changed with your choice. The new report is below. " +
    "Press Copy report to copy it.";
  var WAITING = "Checking AshLight...";
  // PLAY-TD-21A-SETTINGS-RAIL: rows a page, and the rail button whose
  // press shows the section (and builds the preview)
  var ROWS_PAGE = 12;
  var OPENER = "rail-checks";
  var DISMISS_KEY = "al.lang.dismissed";
  // TC-CALC-OPTIN-BUTTON: the calc row's button and its three lines
  var CALC_BUTTON = "Set up the calc";
  var CALC_PENDING = "Setting up the calc. This runs in the background and can take a few " +
    "minutes. You can keep playing.";
  var CALC_OK = "Calc set up. This row will change to ok soon.";
  var CALC_FAILED = "Calc setup didn't finish. Try again. If it keeps failing, see " +
    "calc_setup.log in the Logs folder.";
  // design 0001 section 6: kit state glyph and word, never colour alone
  var MARK = {
    pass: { glyph: "[+]", word: "ok", state: "done" },
    fail: { glyph: "[#]", word: "needs a fix", state: "blocked" },
    note: { glyph: "[-]", word: "note", state: "idle" },
    unknown: { glyph: "[ ]", word: "not known yet", state: "pending" },
    off: { glyph: "[-]", word: "off", state: "idle" }
  };

  /* RUN-QUIET-FEED (F-093): a row with an age carries its absolute time in
     "at" (epoch s) and AGO where the age goes in its detail
     (server/al/diag.py); the snapshot holds no age text, so an idle minute
     pushes nothing. The age is written in here, stepped at 5 minutes, so
     the list is rebuilt at most once per step. */
  var AGO = "{ago}";
  var AGE_STEP_S = 300;

  /* The age words for `s` seconds: "just now" under 90 s (as the report
     says it), "under 5 min ago" up to 5 minutes, then whole 5-minute steps
     (rounded down) below 90 minutes, then hours, then days (from 2 days).
     Coarser than the price ages of web/prices.js on purpose: this list is
     repainted only when a snapshot comes (design review RQF-1, RQF-2). A
     rebuild keeps the calc button's focus (addCalc); the rows hold no
     other focusable control (RQF-3). */
  function ageText(s) {
    s = typeof s === "number" && isFinite(s) ? Math.max(0, s) : 0;
    if (s < 90) { return "just now"; }
    if (s < AGE_STEP_S) { return "under 5 min ago"; }
    if (s < 5400) { return Math.floor(s / AGE_STEP_S) * 5 + " min ago"; }
    // hours and days round as the report's words do (server/al/diag.py _ago)
    if (s < 2 * 86400) { return Math.round(s / 3600) + " h ago"; }
    return Math.round(s / 86400) + " days ago";
  }

  /* The row's detail with its age written in at `now` (epoch s); a row
     with no "at" or no AGO is shown as sent. */
  function ageDetail(c, now) {
    var detail = typeof c.detail === "string" ? c.detail : "";
    if (typeof c.at !== "number" || !isFinite(c.at) || detail.indexOf(AGO) < 0) {
      return detail;
    }
    var ago = ageText(now - c.at);
    if (detail.indexOf(AGO) === 0) {
      detail = ago.charAt(0).toUpperCase() + ago.slice(1) + detail.slice(AGO.length);
    }
    return detail.split(AGO).join(ago);
  }

  /* {summary, failed, rows: [{id, glyph, word, state, label, detail, fix}]}
     for the Checks tool; `now` (epoch s, the snapshot's own clock) writes
     the ages in. */
  function model(d, now) {
    if (!d || !Array.isArray(d.checks)) {
      return { summary: WAITING, failed: 0, rows: [] };
    }
    if (typeof now !== "number" || !isFinite(now)) { now = Date.now() / 1000; }
    var rows = d.checks.map(function (c) {
      var m = MARK[c.status] || MARK.unknown;
      return { id: c.id, glyph: m.glyph, word: m.word, state: m.state,
               label: c.label || "", detail: ageDetail(c, now), fix: c.fix || "" };
    });
    return { summary: d.summary || "", failed: d.failed || 0, rows: rows };
  }

  function readDismissed(store) {
    try { return store ? store.getItem(DISMISS_KEY) : null; } catch (e) { return null; }
  }

  function writeDismissed(store, value) {
    try { if (store) { store.setItem(DISMISS_KEY, value); } } catch (e) { /* page only */ }
  }

  /* The language notice: {show, text, key}. key = when this notice began,
     so a hidden notice comes back only after it cleared and began again. */
  function langModel(lang, dismissed) {
    if (!lang || lang.verdict !== "non_english" || !lang.text) {
      return { show: false, text: "", key: "" };
    }
    var key = String(lang.since == null ? "" : lang.since);
    return { show: dismissed !== key, text: lang.text, key: key };
  }

  /* state.dismissed: the hidden notice's key; undefined until wire()
     reads the store, null for none. Region N's Hide sets it, and once
     wired a new key is stored at once, so a hidden note stays hidden after
     a reload until it clears and begins again. */
  var held = { dismissed: undefined, wired: false };
  var state = { store: null, client: undefined, calc: "", calcRow: null, calcNodes: null,
                page: 0, rows: [], rowNodes: [], inClient: false };
  Object.defineProperty(state, "dismissed", {
    enumerable: true,
    get: function () { return held.dismissed; },
    set: function (v) {
      var changed = v !== held.dismissed;
      held.dismissed = v;
      if (held.wired && changed && typeof v === "string") { writeDismissed(state.store, v); }
    }
  });

  /* TC-CALC-OPTIN-BUTTON: the client's argument-free action, or null in a
     plain browser. state.client stands in for window.alClient in tests. */
  function calcClient() {
    var c = state.client;
    if (c === undefined) {
      c = typeof window !== "undefined" && window ? window.alClient : null;
    }
    return c && typeof c.setupCalc === "function" ? c : null;
  }

  /* What the calc row adds: {button, said}. The button shows only in the
     client, only while the row is off or needs a fix, never while a setup
     runs or after one finished well; said is the setup's own line ("" before
     the first click). */
  function calcModel(row, inClient, calc) {
    var out = { button: false, said: "" };
    if (!row || row.id !== "calc" || !inClient) { return out; }
    if (calc === "pending") {
      out.said = CALC_PENDING;
      return out;
    }
    out.said = calc === "ok" ? CALC_OK : (calc === "failed" ? CALC_FAILED : "");
    out.button = calc !== "ok" &&
      (row.word === MARK.off.word || row.word === MARK.fail.word);
    return out;
  }

  /* The calc row's two nodes, made once per page and moved into each
     rebuilt list: one polite live region (id checks-calc-status, empty
     until a click; tabindex -1 so focus can land on it) and the button.
     A setup's state changes update them in place (syncCalc), never by a
     rebuild, so the button keeps focus while the setup runs. */
  function calcNodes(doc) {
    var n = state.calcNodes;
    if (n && n.doc === doc) { return n; }
    var status = doc.createElement("p");
    status.id = "checks-calc-status";
    status.className = "check-detail";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("tabindex", "-1");
    var b = doc.createElement("button");
    b.type = "button";
    b.id = "checks-calc-setup";
    b.textContent = CALC_BUTTON;
    b.addEventListener("click", startCalc);
    n = { doc: doc, status: status, button: b, row: null };
    state.calcNodes = n;
    return n;
  }

  /* The live region's text and the button's state from state.calc. While a
     setup runs the button stays in place, aria-disabled; when a finished
     setup hides the focused button, focus moves to the region. */
  function syncCalc() {
    var n = state.calcNodes;
    if (!n || !n.row) { return; }
    var cm = calcModel(n.row, true, state.calc);
    var pending = state.calc === "pending";
    var hadFocus = n.doc.activeElement === n.button;
    if (n.status.textContent !== cm.said) { n.status.textContent = cm.said; }
    n.button.hidden = !(cm.button || pending);
    n.button.setAttribute("aria-disabled", pending ? "true" : "false");
    if (hadFocus && n.button.hidden && typeof n.status.focus === "function") {
      n.status.focus();
    }
  }

  function startCalc() {
    var c = calcClient();
    if (!c || state.calc === "pending") { return; }
    state.calc = "pending";
    syncCalc();
    var done = function (r) {
      state.calc = r && r.ok === true ? "ok" : "failed";
      syncCalc();
    };
    var p = null;
    try { p = c.setupCalc(); } catch (e) { p = null; }
    if (p && typeof p.then === "function") {
      p.then(done, function () { done(null); });
    } else {
      done(null);
    }
  }

  function addCalc(doc, li, r, inClient) {
    if (!inClient || r.id !== "calc") { return; }
    var n = calcNodes(doc);
    var hadFocus = doc.activeElement === n.button;
    n.row = r;
    li.appendChild(n.status);
    li.appendChild(n.button);
    syncCalc();
    if (hadFocus && !n.button.hidden && typeof n.button.focus === "function") {
      n.button.focus(); // a new snapshot rebuilt the list under the focus
    }
  }

  /* One page of `rows`: {rows, index, pages, label, hasPrev, hasNext};
     index clamped; label "1-12 of 16" ("" when one page holds them all). */
  function rowsPage(rows, index) {
    rows = Array.isArray(rows) ? rows : [];
    var pages = Math.max(1, Math.ceil(rows.length / ROWS_PAGE));
    var i = Math.max(0, Math.min(typeof index === "number" ? index : 0, pages - 1));
    var from = i * ROWS_PAGE;
    var to = Math.min(rows.length, from + ROWS_PAGE);
    return { rows: rows.slice(from, to), index: i, pages: pages,
             label: pages > 1 ? (from + 1) + "-" + to + " of " + rows.length : "",
             hasPrev: i > 0, hasNext: i < pages - 1 };
  }

  function setEnd(b, on) {
    if (!b) { return; }
    if (on) { b.removeAttribute("aria-disabled"); } else { b.setAttribute("aria-disabled", "true"); }
  }

  /* Every row in #checks-list, then the shown page. */
  function renderRows(doc) {
    var list = doc.getElementById("checks-list");
    list.textContent = "";
    state.rowNodes = state.rows.map(function (r) {
      var li = doc.createElement("li");
      li.setAttribute("data-state", r.state);
      var head = doc.createElement("p");
      head.className = "check-line";
      var g = doc.createElement("span");
      g.className = "glyph";
      g.setAttribute("aria-hidden", "true");
      g.textContent = r.glyph;
      var name = doc.createElement("strong");
      name.textContent = r.label;
      var word = doc.createElement("span");
      word.className = "check-word";
      word.textContent = r.word;
      head.appendChild(g);
      head.appendChild(doc.createTextNode(" "));
      head.appendChild(name);
      head.appendChild(doc.createTextNode(" "));
      head.appendChild(word);
      li.appendChild(head);
      var detail = doc.createElement("p");
      detail.className = "check-detail muted";
      detail.textContent = r.detail;
      li.appendChild(detail);
      if (r.fix) {
        var fix = doc.createElement("p");
        fix.className = "check-fix";
        fix.textContent = "Fix: " + r.fix;
        li.appendChild(fix);
      }
      addCalc(doc, li, r, state.inClient);
      list.appendChild(li);
      return li;
    });
    return showPage(doc);
  }

  /* The shown page: rows off it carry hidden (out of view and out of the
     accessibility tree, still in the list), and the pager under them. */
  function showPage(doc) {
    var p = rowsPage(state.rows, state.page);
    state.page = p.index;
    var from = p.index * ROWS_PAGE;
    var to = from + p.rows.length;
    state.rowNodes.forEach(function (li, i) {
      var off = i < from || i >= to;
      if (li.hidden !== off) { li.hidden = off; }
    });
    var bar = doc.getElementById("checks-pager");
    if (bar) { bar.hidden = p.pages < 2; }
    var count = doc.getElementById("checks-count");
    if (count && count.textContent !== p.label) { count.textContent = p.label; }
    setEnd(doc.getElementById("checks-prev"), p.hasPrev);
    setEnd(doc.getElementById("checks-next"), p.hasNext);
    return p;
  }

  /* Prev / Next: the only way the rows page changes; an end does nothing. */
  function turnRows(doc, step) {
    var p = rowsPage(state.rows, state.page);
    var next = p.index + step;
    if (next < 0 || next >= p.pages) { return p; }
    state.page = next;
    return showPage(doc);
  }

  function paintChecks(doc, snap) {
    var box = doc.getElementById("checksbox");
    if (!box) { return; }
    var m = model(snap && snap.diag, snap && snap.now);
    var client = calcClient();
    // a finished setup's line clears once the core's calc row changes
    var calcRow = "";
    m.rows.forEach(function (r) { if (r.id === "calc") { calcRow = r.word; } });
    if (state.calcRow !== null && calcRow !== state.calcRow &&
        (state.calc === "ok" || state.calc === "failed")) {
      state.calc = "";
    }
    state.calcRow = calcRow;
    // V-5: the checks' states (not their wording, whose ages step every
    // 5 minutes); a change makes an open preview stale
    var states = JSON.stringify(m.rows.map(function (r) { return [r.id, r.word]; }));
    if (states !== report.states) {
      report.states = states;
      report.checksGen += 1;
    }
    var key = JSON.stringify([m, !!client]);
    if (box.getAttribute("data-key") === key) {
      syncCalc(); // a cleared setup line, with no rebuild
      return;
    }
    box.setAttribute("data-key", key);
    doc.getElementById("checks-summary").textContent = m.summary;
    var fold = doc.getElementById("checks");
    // ZERO-CLICK: shows by itself when a check newly needs a fix, on the
    // page holding the first failing row
    var before = Number(box.getAttribute("data-failed") || "0");
    var newFail = m.failed > 0 && before === 0;
    // UI-GLANCE: the Settings tab says "fix" while a check needs one (it
    // never switches tabs by itself; Play stays in front during play)
    var tabs = typeof self !== "undefined" && self.ALTabs ? self.ALTabs : null;
    if (tabs) { tabs.mark(doc, "settings", m.failed > 0 ? "fix" : ""); }
    box.setAttribute("data-failed", String(m.failed));
    state.rows = m.rows;
    state.inClient = !!client;
    if (newFail) {
      for (var i = 0; i < m.rows.length; i++) {
        if (m.rows[i].word === MARK.fail.word) { state.page = Math.floor(i / ROWS_PAGE); break; }
      }
    }
    renderRows(doc);
    if (newFail && fold) { fold.open = true; }
    // RUN-REPORT-ROUTE: the core builds the report on the click; the
    // button waits only for the first checks (RUN-QUIET-FEED: the
    // snapshot carries no report)
    doc.getElementById("checks-copy").disabled = !m.rows.length;
  }

  function paint(doc, snap) {
    paintChecks(doc, snap);
  }

  /* RUN-REPORT-ROUTE: the preview. report.text is the text on show ("" for
     none), report.gen counts builds so a late answer of an older build
     never overwrites a newer one. V-5: report.checksGen moves when a
     check's state changes (report.states), report.builtGen is the
     checksGen the preview on show was asked at (-1 for none). */
  var report = { text: "", gen: 0, states: "", checksGen: 0, builtGen: -1,
                 tails: false, builtTails: false, tailsBox: null };

  /* RUN-REPORT-FIELDS: true while the player ticked the second choice. */
  function tailsOn() {
    var b = report.tailsBox;
    return !!(b && b.checked === true);
  }

  /* The one checkbox, made once per page inside the preview box (after
     the text area); unticked on every load, never stored. `onChange`
     runs on the player's change. Returns the input or null. */
  function addTails(doc, onChange) {
    var box = doc.getElementById("checks-preview-box");
    if (!box) { return null; }
    var input = doc.getElementById("checks-tails");
    if (!input) {
      var p = doc.createElement("p");
      p.className = "row-meta small";
      var label = doc.createElement("label");
      input = doc.createElement("input");
      input.type = "checkbox";
      input.id = "checks-tails";
      input.checked = false;
      label.appendChild(input);
      label.appendChild(doc.createTextNode(" " + TAILS_LABEL));
      p.appendChild(label);
      box.appendChild(p);
    }
    input.checked = false;
    input.addEventListener("change", onChange);
    return input;
  }

  function showPreview(doc, text) {
    var pre = doc.getElementById("checks-preview");
    var box = doc.getElementById("checks-preview-box");
    report.text = text;
    if (pre) { pre.value = text; }
    if (box) { box.hidden = !text; }
  }

  /* GET /api/report, then the preview; `ready` is the line said when it
     shows (READY by default). Resolves to true when it shows. */
  function buildReport(doc, api, said, ready) {
    if (typeof api !== "function") {
      said.textContent = BUILD_FAILED;
      return Promise.resolve(false);
    }
    var gen = ++report.gen;
    var asked = report.checksGen;
    var tails = tailsOn();
    said.textContent = BUILDING;
    var p;
    try {
      p = api("GET", tails ? REPORT_PATH + TAILS_QUERY : REPORT_PATH);
    } catch (e) { p = Promise.reject(e); }
    return Promise.resolve(p).then(function (res) {
      if (gen !== report.gen) { return false; }
      var text = res && typeof res.report === "string" ? res.report : "";
      showPreview(doc, text);
      report.builtGen = text ? asked : -1;
      report.builtTails = tails;
      said.textContent = text ? (ready || READY) : BUILD_FAILED;
      return !!text;
    }, function () {
      if (gen !== report.gen) { return false; }
      said.textContent = BUILD_FAILED;
      return false;
    });
  }

  /* `getSnap` returns the latest snapshot; `nav` is navigator (tests pass
     a stub); `store` is localStorage or null; `api` is app.js api(method,
     path) -> promise of the JSON reply (RUN-REPORT-ROUTE). */
  function wire(doc, getSnap, nav, store, api) {
    state.store = store || null;
    held.wired = false;
    state.dismissed = readDismissed(state.store);
    held.wired = true;
    report.text = "";
    report.gen = 0;
    report.builtGen = -1;
    report.builtTails = false;
    var copy = doc.getElementById("checks-copy");
    var said = doc.getElementById("checks-said");
    var fold = doc.getElementById("checks");
    var opener = doc.getElementById(OPENER);
    // the player's press that shows the Checks section builds the preview
    // (Checks shown by itself, at load or on a failure, builds nothing);
    // this listener runs before web/rail.js shows the section
    if (opener && fold) {
      opener.addEventListener("click", function () {
        if (!fold.open) { buildReport(doc, api, said); }
      });
    }
    state.page = 0;
    var prev = doc.getElementById("checks-prev");
    var next = doc.getElementById("checks-next");
    if (prev) { prev.addEventListener("click", function () { turnRows(doc, -1); }); }
    if (next) { next.addEventListener("click", function () { turnRows(doc, 1); }); }
    /* W-1: #checks-said is not a live region, so a Copy click that had to
       (re)build the preview moves the focus there once the preview shows,
       unless the player has since moved it somewhere else. */
    var rebuild = function (ready) {
      buildReport(doc, api, said, ready).then(function (ok) {
        if (!ok || typeof said.focus !== "function") { return; }
        var a = doc.activeElement;
        if (!a || a === copy || a === doc.body) { said.focus(); }
      });
    };
    // RUN-REPORT-FIELDS: the player's change of the second choice makes
    // the preview again with (or without) the log lines
    report.tailsBox = addTails(doc, function () { rebuild(READY_TAILS); });
    if (copy) {
      copy.addEventListener("click", function () {
        var text = report.text;
        if (!text) { // no preview yet: this click builds it, the next copies
          rebuild(READY_AGAIN);
          return;
        }
        if (report.builtGen !== report.checksGen) { // V-5: a check moved since
          rebuild(READY_CHANGED);
          return;
        }
        if (report.builtTails !== tailsOn()) { // made with the other choice
          rebuild(READY_TAILS);
          return;
        }
        said.textContent = "";
        var fail = function () { said.textContent = COPY_FAILED; };
        var p = null;
        if (nav && nav.clipboard && nav.clipboard.writeText) {
          // synchronous inside the click: the previewed text, byte for byte
          try { p = nav.clipboard.writeText(text); } catch (e) { p = null; }
        }
        if (p && typeof p.then === "function") {
          p.then(function () { said.textContent = COPIED; }, fail);
        } else {
          fail();
        }
      });
    }
  }

  return { model: model, langModel: langModel, calcModel: calcModel, paint: paint, wire: wire,
           ageText: ageText, AGO: AGO, AGE_STEP_S: AGE_STEP_S,
           COPIED: COPIED, COPY_FAILED: COPY_FAILED, WAITING: WAITING, MARK: MARK,
           REPORT_PATH: REPORT_PATH, BUILDING: BUILDING, READY: READY,
           READY_AGAIN: READY_AGAIN, READY_CHANGED: READY_CHANGED,
           BUILD_FAILED: BUILD_FAILED, _report: report,
           TAILS_QUERY: TAILS_QUERY, TAILS_LABEL: TAILS_LABEL, READY_TAILS: READY_TAILS,
           CALC_BUTTON: CALC_BUTTON, CALC_PENDING: CALC_PENDING, CALC_OK: CALC_OK,
           CALC_FAILED: CALC_FAILED, _state: state,
           ROWS_PAGE: ROWS_PAGE, OPENER: OPENER, rowsPage: rowsPage };
}));
