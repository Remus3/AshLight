/* AshLight dashboard: the 'Tried in game' card of the Checks tool
   (RUN-VERDICTS-UI; finding F-062, OPEN-27; decision 0040 amendment
   2026-11-18). UMD: CommonJS for node --test (app/test/verdicts.test.js),
   window.ALVerdicts for the page.

   Some checks only the player can make in game (a .build file loads, a
   search string works, the filter imports, the overlay keeps its FPS).
   The card lists them from GET /api/verdicts (server/al/plug/verdicts.py);
   each open check (not tried yet, or refused) carries Worked and Refused
   buttons, and one click posts the verdict (POST /api/verdicts) with the
   optional note typed above the list. A check that worked is closed and
   shows no buttons. The core keeps the record (ops/runtime/verdicts.json);
   nothing is sent to the game or anywhere else. No timers, no clipboard,
   no modal; every text is set with textContent. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALVerdicts = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var PATH = "/api/verdicts";
  var INTRO = "Some things only you can check in the game. After you try one, " +
    "press Worked or Refused. Nothing is sent anywhere.";
  var NOTE_LABEL = "Note, optional (goes with your next click)";
  var WORKED = "Worked";
  var REFUSED = "Refused";
  var STATUS = { open: "not tried yet", worked: "worked", refused: "refused" };
  var ALL_DONE = "Every in-game check worked. Thank you.";
  var SAVED = { worked: "Saved: worked.", refused: "Saved: refused." };
  var SAVE_FAILED = "That didn't save. Try again.";
  var LOAD_FAILED = "Couldn't load the in-game checks. Reload the page to try again.";
  var MAX_NOTE = 200;
  var NOTE_BAD = "The note can use plain letters, digits and punctuation, up to " +
    MAX_NOTE + " characters.";
  // design 0001 section 6: kit state glyph and word, never colour alone
  var MARK = {
    open: { glyph: "[ ]", state: "pending" },
    worked: { glyph: "[+]", state: "done" },
    refused: { glyph: "[#]", state: "blocked" }
  };

  /* {rows: [{id, label, status, word, glyph, state, note, open}], open,
     allDone, maxNote} from the GET /api/verdicts document. A row is open
     until its newest verdict is "worked". */
  function model(doc) {
    var checks = doc && Array.isArray(doc.checks) ? doc.checks : [];
    var maxNote = doc && typeof doc.max_note === "number" && doc.max_note > 0 ?
      doc.max_note : MAX_NOTE;
    var rows = [];
    checks.forEach(function (c) {
      if (!c || typeof c.id !== "string" || !c.id) { return; }
      var v = c.verdict && typeof c.verdict === "object" ? c.verdict : null;
      var status = v && v.result === "worked" ? "worked" :
        (v && v.result === "refused" ? "refused" : "open");
      var m = MARK[status];
      rows.push({ id: c.id, label: typeof c.label === "string" ? c.label : c.id,
                  status: status, word: STATUS[status], glyph: m.glyph, state: m.state,
                  note: v && typeof v.note === "string" ? v.note : "",
                  open: status !== "worked" });
    });
    var open = rows.filter(function (r) { return r.open; }).length;
    return { rows: rows, open: open, allDone: rows.length > 0 && open === 0,
             maxNote: maxNote };
  }

  /* The trimmed note, or null when the core would refuse it (printable
     ASCII only, at most max characters; never cut). */
  function cleanNote(text, max) {
    var note = String(text == null ? "" : text).trim();
    if (note.length > (max || MAX_NOTE)) { return null; }
    for (var i = 0; i < note.length; i++) {
      var code = note.charCodeAt(i);
      if (code < 0x20 || code > 0x7e) { return null; }
    }
    return note;
  }

  /* The POST body for one click. */
  function body(id, result, note) {
    var out = { check: id, result: result };
    if (note) { out.note = note; }
    return out;
  }

  // the card's fixed nodes, made once per wire; the list is rebuilt
  var state = { doc: null, api: null, nodes: null, data: null, busy: false, buttons: [] };

  function make(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text) { n.textContent = text; }
    return n;
  }

  function build(doc, mount) {
    var intro = make(doc, "p", "muted small", INTRO);
    var label = make(doc, "label", "row-meta", NOTE_LABEL);
    label.setAttribute("for", "verdicts-note");
    var note = make(doc, "textarea", "paste-box");
    note.id = "verdicts-note";
    note.setAttribute("rows", "2");
    note.setAttribute("maxlength", String(MAX_NOTE));
    note.setAttribute("autocomplete", "off");
    var list = make(doc, "ul", "checks-list");
    list.id = "verdicts-list";
    // not a live region: the dashboard keeps at most 9 (test_a11y); focus
    // moves here when a click removes the focused button
    var said = make(doc, "p", "muted");
    said.id = "verdicts-said";
    said.setAttribute("tabindex", "-1");
    mount.appendChild(intro);
    mount.appendChild(label);
    mount.appendChild(note);
    mount.appendChild(list);
    mount.appendChild(said);
    return { mount: mount, note: note, list: list, said: said };
  }

  function button(doc, text, row, result) {
    var b = make(doc, "button", "", text);
    b.type = "button";
    b.setAttribute("data-check", row.id);
    b.setAttribute("data-result", result);
    b.setAttribute("aria-describedby", "verdicts-label-" + row.id);
    b.addEventListener("click", function () { send(row.id, result); });
    state.buttons.push(b);
    return b;
  }

  function paint() {
    var n = state.nodes;
    if (!n) { return; }
    var doc = state.doc;
    var m = model(state.data);
    n.mount.hidden = m.rows.length === 0;
    n.note.setAttribute("maxlength", String(m.maxNote));
    n.list.textContent = "";
    state.buttons = [];
    m.rows.forEach(function (r) {
      var li = doc.createElement("li");
      li.setAttribute("data-state", r.state);
      li.setAttribute("data-check", r.id);
      var head = make(doc, "p", "check-line");
      var g = make(doc, "span", "glyph", r.glyph);
      g.setAttribute("aria-hidden", "true");
      var name = make(doc, "strong", "", r.label);
      name.id = "verdicts-label-" + r.id;
      var word = make(doc, "span", "check-word", r.word);
      head.appendChild(g);
      head.appendChild(doc.createTextNode(" "));
      head.appendChild(name);
      head.appendChild(doc.createTextNode(" "));
      head.appendChild(word);
      li.appendChild(head);
      if (r.note) {
        li.appendChild(make(doc, "p", "check-detail muted", "Your note: " + r.note));
      }
      if (r.open) {
        var row = make(doc, "p", "settings-controls");
        row.appendChild(button(doc, WORKED, r, "worked"));
        row.appendChild(button(doc, REFUSED, r, "refused"));
        li.appendChild(row);
      }
      n.list.appendChild(li);
    });
    if (m.allDone && !n.said.textContent) { n.said.textContent = ALL_DONE; }
  }

  /* While a click's post runs every verdict button waits (one at a time). */
  function setBusy(on) {
    state.busy = on;
    state.buttons.forEach(function (b) { b.disabled = on; });
  }

  /* One click: post the verdict with the typed note, then repaint from the
     core's answer. A refused note is said, never cut or sent. */
  function send(id, result) {
    var n = state.nodes;
    if (!n || state.busy || typeof state.api !== "function") { return; }
    var m = model(state.data);
    var note = cleanNote(n.note.value, m.maxNote);
    if (note === null) {
      n.said.textContent = NOTE_BAD;
      return;
    }
    n.said.textContent = "";
    setBusy(true);
    var p;
    try { p = state.api("POST", PATH, body(id, result, note)); } catch (e) { p = Promise.reject(e); }
    return Promise.resolve(p).then(function (res) {
      var doc = state.doc;
      var hadFocus = doc && doc.activeElement && doc.activeElement.getAttribute &&
        doc.activeElement.getAttribute("data-check") === id;
      state.busy = false;
      if (res && res.verdicts) { state.data = res.verdicts; }
      n.note.value = "";
      paint();
      n.said.textContent = SAVED[result];
      if (hadFocus && typeof n.said.focus === "function") { n.said.focus(); }
    }, function () {
      setBusy(false);
      n.said.textContent = SAVE_FAILED;
    });
  }

  /* `api(method, path, body)` -> promise of the JSON reply (app.js api()).
     One read of the open checks at wire time; then only the player's
     clicks. Returns the read's promise (tests wait on it). */
  function wire(doc, api) {
    var mount = doc && doc.getElementById("verdicts");
    state.doc = doc;
    state.api = api;
    state.data = null;
    state.busy = false;
    state.nodes = null;
    if (!mount || typeof api !== "function") { return Promise.resolve(false); }
    state.nodes = build(doc, mount);
    var p;
    try { p = api("GET", PATH); } catch (e) { p = Promise.reject(e); }
    return Promise.resolve(p).then(function (res) {
      state.data = res || null;
      paint();
      return true;
    }, function () {
      mount.hidden = false;
      state.nodes.said.textContent = LOAD_FAILED;
      return false;
    });
  }

  return { model: model, cleanNote: cleanNote, body: body, wire: wire, send: send,
           PATH: PATH, INTRO: INTRO, NOTE_LABEL: NOTE_LABEL, WORKED: WORKED,
           REFUSED: REFUSED, STATUS: STATUS, ALL_DONE: ALL_DONE, SAVED: SAVED,
           SAVE_FAILED: SAVE_FAILED, LOAD_FAILED: LOAD_FAILED, NOTE_BAD: NOTE_BAD,
           _state: state };
}));
