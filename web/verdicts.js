/* AshLight dashboard: the 'Tried in game' card of the Checks tool
   (RUN-VERDICTS-UI; finding F-062, OPEN-27; decision 0040 amendment
   2026-11-18). UMD: CommonJS for node --test (app/test/verdicts.test.js),
   window.ALVerdicts for the page.

   Some checks only the player can make in game (a .build file loads, a
   search string works, the filter imports, the overlay keeps its FPS).
   The card lists them from GET /api/verdicts (server/al/plug/verdicts.py);
   each open check (not tried yet, or refused) carries Worked and Refused
   buttons and its own optional note field, and one click posts the
   verdict (POST /api/verdicts) with that row's note. A check that worked
   is closed and shows no buttons.
   VERDICTS-UI-A11Y (design review V-1 to V-3): every verdict click ends
   with focus on the said line (#verdicts-said, tabindex -1), so a screen
   reader reads Saved or the failure; while a post runs the buttons are
   aria-disabled (never disabled, which would drop the focus) and clicks
   are ignored; each open row has its own note, so a note can only go
   with the check it sits under. The core keeps the record (ops/runtime/verdicts.json);
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
  var NOTE_LABEL = "Note for this check, optional";
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
  var state = { doc: null, api: null, nodes: null, data: null, busy: false, buttons: [],
                notes: {} };

  function make(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text) { n.textContent = text; }
    return n;
  }

  function build(doc, mount) {
    var intro = make(doc, "p", "muted small", INTRO);
    var list = make(doc, "ul", "checks-list");
    list.id = "verdicts-list";
    // not a live region: the dashboard keeps at most 9 (test_a11y); focus
    // moves here after every verdict click (V-1), so it is read out
    var said = make(doc, "p", "muted");
    said.id = "verdicts-said";
    said.setAttribute("tabindex", "-1");
    mount.appendChild(intro);
    mount.appendChild(list);
    mount.appendChild(said);
    return { mount: mount, list: list, said: said };
  }

  function button(doc, text, row, result) {
    var b = make(doc, "button", "", text);
    b.type = "button";
    b.setAttribute("data-check", row.id);
    b.setAttribute("data-result", result);
    b.setAttribute("aria-describedby", "verdicts-label-" + row.id);
    b.setAttribute("aria-disabled", state.busy ? "true" : "false");
    b.addEventListener("click", function () { send(row.id, result, b); });
    state.buttons.push(b);
    return b;
  }

  /* V-3: one note field per open row, labelled for that row. */
  function noteField(doc, row, maxNote) {
    var wrap = make(doc, "p", "check-detail");
    var id = "verdicts-note-" + row.id;
    var label = make(doc, "label", "row-meta", NOTE_LABEL);
    label.setAttribute("for", id);
    var note = make(doc, "textarea", "paste-box");
    note.id = id;
    note.setAttribute("rows", "1");
    note.setAttribute("maxlength", String(maxNote));
    note.setAttribute("autocomplete", "off");
    wrap.appendChild(label);
    wrap.appendChild(note);
    return { wrap: wrap, note: note };
  }

  function paint() {
    var n = state.nodes;
    if (!n) { return; }
    var doc = state.doc;
    var m = model(state.data);
    n.mount.hidden = m.rows.length === 0;
    // a rebuild keeps what the player typed in the rows still open
    var kept = state.notes;
    state.notes = {};
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
        var f = noteField(doc, r, m.maxNote);
        f.note.value = kept[r.id] ? kept[r.id].value : "";
        state.notes[r.id] = f.note;
        li.appendChild(f.wrap);
        var row = make(doc, "p", "settings-controls");
        row.appendChild(button(doc, WORKED, r, "worked"));
        row.appendChild(button(doc, REFUSED, r, "refused"));
        li.appendChild(row);
      }
      n.list.appendChild(li);
    });
    if (m.allDone && !n.said.textContent) { n.said.textContent = ALL_DONE; }
  }

  /* While a click's post runs every verdict button waits (one at a time).
     V-2: aria-disabled, never disabled, so the focused button keeps the
     focus; send() ignores clicks while busy. */
  function setBusy(on) {
    state.busy = on;
    state.buttons.forEach(function (b) { b.setAttribute("aria-disabled", on ? "true" : "false"); });
  }

  /* V-1: the said line takes the focus after a verdict click, unless the
     player has since moved it somewhere else on the page. */
  function sayFocus(clicked) {
    var n = state.nodes;
    var doc = state.doc;
    if (!n || typeof n.said.focus !== "function") { return; }
    var a = doc ? doc.activeElement : null;
    if (!clicked || !a || a === clicked || a === doc.body) { n.said.focus(); }
  }

  /* One click: post the verdict with that row's note, then repaint from
     the core's answer. A refused note is said, never cut or sent; the
     focus goes to that note field, which then points at the said line. */
  function send(id, result, clicked) {
    var n = state.nodes;
    if (!n || state.busy || typeof state.api !== "function") { return; }
    var m = model(state.data);
    var field = state.notes[id] || null;
    var note = cleanNote(field ? field.value : "", m.maxNote);
    if (note === null) {
      n.said.textContent = NOTE_BAD;
      field.setAttribute("aria-invalid", "true");
      field.setAttribute("aria-describedby", "verdicts-said");
      if (typeof field.focus === "function") { field.focus(); }
      return;
    }
    if (field && field.getAttribute("aria-invalid") === "true") {
      field.setAttribute("aria-invalid", "false");
    }
    n.said.textContent = "";
    setBusy(true);
    var p;
    try { p = state.api("POST", PATH, body(id, result, note)); } catch (e) { p = Promise.reject(e); }
    return Promise.resolve(p).then(function (res) {
      state.busy = false;
      if (res && res.verdicts) { state.data = res.verdicts; }
      if (state.notes[id]) { state.notes[id].value = ""; }
      paint();
      n.said.textContent = SAVED[result];
      sayFocus(clicked);
    }, function () {
      setBusy(false);
      n.said.textContent = SAVE_FAILED;
      sayFocus(clicked);
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
    state.notes = {};
    state.buttons = [];
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
