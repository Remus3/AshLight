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
   TC-CALC-OPTIN-BUTTON (decision 0018 opt-in, decision 0041 amendment
   2026-11-20): inside the desktop client only (window.alClient.setupCalc,
   app/client/preload.js) the calc row carries a "Set up the calc" button
   while that row is off or needs a fix; a click runs the client's fixed
   setup script and the row says it is working, then done or not done. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALChecks = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var COPIED = "Report copied. Paste it where you ask for help.";
  var COPY_FAILED = "Couldn't copy the report. Try again.";
  var WAITING = "Checking AshLight...";
  var DISMISS_KEY = "al.lang.dismissed";
  // TC-CALC-OPTIN-BUTTON: the calc row's button and its three lines
  var CALC_BUTTON = "Set up the calc";
  var CALC_PENDING = "Setting up the calc. This runs in the background and can take a few minutes.";
  var CALC_OK = "Calc set up. This row updates by itself.";
  var CALC_FAILED = "Calc setup didn't finish. Try again.";
  // design 0001 section 6: kit state glyph and word, never colour alone
  var MARK = {
    pass: { glyph: "[+]", word: "ok", state: "done" },
    fail: { glyph: "[#]", word: "needs a fix", state: "blocked" },
    note: { glyph: "[-]", word: "note", state: "idle" },
    unknown: { glyph: "[ ]", word: "not known yet", state: "pending" },
    off: { glyph: "[-]", word: "off", state: "idle" }
  };

  /* {summary, failed, rows: [{id, glyph, word, state, label, detail, fix}],
     report} for the Checks tool. */
  function model(d) {
    if (!d || !Array.isArray(d.checks)) {
      return { summary: WAITING, failed: 0, rows: [], report: "" };
    }
    var rows = d.checks.map(function (c) {
      var m = MARK[c.status] || MARK.unknown;
      return { id: c.id, glyph: m.glyph, word: m.word, state: m.state,
               label: c.label || "", detail: c.detail || "", fix: c.fix || "" };
    });
    return { summary: d.summary || "", failed: d.failed || 0, rows: rows,
             report: typeof d.report === "string" ? d.report : "" };
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
  var state = { store: null, client: undefined, calc: "", calcRow: null, doc: null, snap: null };
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

  function startCalc() {
    var c = calcClient();
    if (!c || state.calc === "pending") { return; }
    state.calc = "pending";
    repaint();
    var done = function (r) {
      state.calc = r && r.ok === true ? "ok" : "failed";
      repaint();
    };
    var p = null;
    try { p = c.setupCalc(); } catch (e) { p = null; }
    if (p && typeof p.then === "function") {
      p.then(done, function () { done(null); });
    } else {
      done(null);
    }
  }

  function repaint() {
    if (state.doc) { paintChecks(state.doc, state.snap); }
  }

  function addCalc(doc, li, r, inClient) {
    var cm = calcModel(r, inClient, state.calc);
    if (cm.said) {
      var said = doc.createElement("p");
      said.className = "check-detail";
      said.setAttribute("role", "status");
      said.textContent = cm.said;
      li.appendChild(said);
    }
    if (cm.button) {
      var b = doc.createElement("button");
      b.type = "button";
      b.id = "checks-calc-setup";
      b.textContent = CALC_BUTTON;
      b.addEventListener("click", startCalc);
      li.appendChild(b);
    }
  }

  function paintChecks(doc, snap) {
    state.doc = doc;
    state.snap = snap;
    var box = doc.getElementById("checksbox");
    if (!box) { return; }
    var m = model(snap && snap.diag);
    var client = calcClient();
    // a finished setup's line clears once the core's calc row changes
    var calcRow = "";
    m.rows.forEach(function (r) { if (r.id === "calc") { calcRow = r.word; } });
    if (state.calcRow !== null && calcRow !== state.calcRow &&
        (state.calc === "ok" || state.calc === "failed")) {
      state.calc = "";
    }
    state.calcRow = calcRow;
    var key = JSON.stringify([m, !!client, state.calc]);
    if (box.getAttribute("data-key") === key) { return; }
    box.setAttribute("data-key", key);
    doc.getElementById("checks-summary").textContent = m.summary;
    var fold = doc.getElementById("checks");
    // ZERO-CLICK: opens by itself when a check newly needs a fix
    var before = Number(box.getAttribute("data-failed") || "0");
    if (m.failed > 0 && before === 0) {
      fold.open = true;
    }
    // UI-GLANCE: the Settings tab says "fix" while a check needs one (it
    // never switches tabs by itself; Play stays in front during play)
    var tabs = typeof self !== "undefined" && self.ALTabs ? self.ALTabs : null;
    if (tabs) { tabs.mark(doc, "settings", m.failed > 0 ? "fix" : ""); }
    box.setAttribute("data-failed", String(m.failed));
    var list = doc.getElementById("checks-list");
    list.textContent = "";
    m.rows.forEach(function (r) {
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
      addCalc(doc, li, r, !!client);
      list.appendChild(li);
    });
    doc.getElementById("checks-copy").disabled = !m.report;
  }

  function paint(doc, snap) {
    paintChecks(doc, snap);
  }

  /* `getSnap` returns the latest snapshot; `nav` is navigator (tests pass
     a stub); `store` is localStorage or null. */
  function wire(doc, getSnap, nav, store) {
    state.store = store || null;
    held.wired = false;
    state.dismissed = readDismissed(state.store);
    held.wired = true;
    var copy = doc.getElementById("checks-copy");
    var said = doc.getElementById("checks-said");
    if (copy) {
      copy.addEventListener("click", function () {
        var snap = getSnap();
        var text = model(snap && snap.diag).report;
        said.textContent = "";
        var fail = function () { said.textContent = COPY_FAILED; };
        if (text && nav && nav.clipboard && nav.clipboard.writeText) {
          nav.clipboard.writeText(text).then(function () { said.textContent = COPIED; }, fail);
        } else {
          fail();
        }
      });
    }
  }

  return { model: model, langModel: langModel, calcModel: calcModel, paint: paint, wire: wire,
           COPIED: COPIED, COPY_FAILED: COPY_FAILED, WAITING: WAITING, MARK: MARK,
           CALC_BUTTON: CALC_BUTTON, CALC_PENDING: CALC_PENDING, CALC_OK: CALC_OK,
           CALC_FAILED: CALC_FAILED, _state: state };
}));
