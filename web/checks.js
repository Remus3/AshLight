/* AshLight dashboard: the Checks tool (DIAG-SELF, ruling J) and the game
   language notice (LANG-GUARD, ruling K). UMD: CommonJS for node --test
   (app/test/checks.test.js), window.ALChecks for the page. The core makes
   every check, sentence and the redacted report (server/al/diag.py,
   server/al/langguard.py); this file only shows them. The clipboard is
   written only inside the "Copy report" click (decision 0014). No timers. */
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

  var state = { dismissed: undefined, store: null };

  function paintLang(doc, snap) {
    var box = doc.getElementById("langbox");
    if (!box) { return; }
    if (state.dismissed === undefined) { state.dismissed = readDismissed(state.store); }
    var m = langModel(snap && snap.lang, state.dismissed);
    box.hidden = !m.show;
    box.setAttribute("data-key", m.key);
    var text = doc.getElementById("lang-text");
    if (text.textContent !== m.text) { text.textContent = m.text; }
  }

  function paintChecks(doc, snap) {
    var box = doc.getElementById("checksbox");
    if (!box) { return; }
    var m = model(snap && snap.diag);
    var key = JSON.stringify(m);
    if (box.getAttribute("data-key") === key) { return; }
    box.setAttribute("data-key", key);
    doc.getElementById("checks-summary").textContent = m.summary;
    var fold = doc.getElementById("checks");
    // ZERO-CLICK: opens by itself when a check newly needs a fix
    var before = Number(box.getAttribute("data-failed") || "0");
    if (m.failed > 0 && before === 0) {
      fold.open = true;
      // UX-NARROW: the Tools card may sit in the closed narrow fold
      var narrow = doc.getElementById("narrow-tools");
      if (narrow && narrow.contains && narrow.contains(box)) { narrow.open = true; }
    }
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
      list.appendChild(li);
    });
    doc.getElementById("checks-copy").disabled = !m.report;
  }

  function paint(doc, snap) {
    paintLang(doc, snap);
    paintChecks(doc, snap);
  }

  /* `getSnap` returns the latest snapshot; `nav` is navigator (tests pass
     a stub); `store` is localStorage or null. */
  function wire(doc, getSnap, nav, store) {
    state.store = store || null;
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
    var hide = doc.getElementById("lang-dismiss");
    if (hide) {
      hide.addEventListener("click", function () {
        var box = doc.getElementById("langbox");
        state.dismissed = box.getAttribute("data-key") || "";
        writeDismissed(state.store, state.dismissed);
        box.hidden = true;
      });
    }
  }

  return { model: model, langModel: langModel, paint: paint, wire: wire,
           COPIED: COPIED, COPY_FAILED: COPY_FAILED, WAITING: WAITING, MARK: MARK,
           _state: state };
}));
