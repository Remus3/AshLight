/* AshLight dashboard: "Can't find Client.txt?" (SEC-LOG-PATH-FIELD, F-098).

   Today's discovery runs first. Only while the core's Checks row "log"
   fails (snapshot diag.checks, id "log", status "fail": no Client.txt
   found, or the configured one is missing) does Settings, Reading and web
   data show one field for the game folder or the Client.txt path. Use (or
   Enter) posts the existing consent API, POST /api/consent {consent: true,
   path}: that one press is the player's own Client.txt opt-in, for that
   one file at that one path. The core checks the path (a local Client.txt
   or the folder holding it) and answers 400 with its own text for a bad
   one; this page turns that answer into its own sentence: what happened
   and what to do (design 0001 P3), no HTTP code.

   Nothing here looks in a folder, a registry key or a config file, and no
   other client's folder is probed (floor audit L3). No timers, no
   clipboard, nothing sent to the game. The answer line (#logpath-said)
   sits after the form, so a Saved line stays when the form hides. It is
   not a live region: the page keeps its cap of plan 03 4.1.3 and Settings
   lines beside their forms stay quiet. The field and Use both point at it
   (aria-describedby), a refused path sets aria-invalid on the field and
   moves focus to it so both are announced (LP-A), and
   a found Client.txt is announced by the bar's polite reading word.

   UMD: CommonJS for node --test (app/test/logpath.test.js),
   window.ALLogPath in the page (web/app.js calls paint from the consent
   painter and wire from its wire step). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALLogPath = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_PATH = 1024; // the core's own cap (logfile.consent_path_ok)
  /* the core's 400 answer (core.record_consent: "path must be a local
     Client.txt or the folder holding it") as what happened and what to do */
  var BAD_PATH = "AshLight can't use that path. Type the full path to Client.txt or to its folder on this PC.";
  var NOT_SAVED = "Not saved. Try again.";
  var SAVED = "Saved. AshLight uses this path for Client.txt.";

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }

  /* The view rule: shown only while the Checks row "log" fails. */
  function view(snap) {
    var d = isObj(snap) && isObj(snap.diag) ? snap.diag : null;
    var rows = d && Array.isArray(d.checks) ? d.checks : [];
    var show = rows.some(function (r) {
      return isObj(r) && r.id === "log" && r.status === "fail";
    });
    return { show: show };
  }

  /* The body Use posts, or null for nothing to send. One pair of
     surrounding double quotes (Windows "Copy as path") is dropped. */
  function payload(text) {
    if (typeof text !== "string") { return null; }
    var p = text.trim();
    if (p.length >= 2 && p.charAt(0) === "\"" && p.charAt(p.length - 1) === "\"") {
      p = p.slice(1, -1).trim();
    }
    if (!p || p.length > MAX_PATH) { return null; }
    return { consent: true, path: p };
  }

  /* The answer words for a failed post: the bad-path sentence for the
     core's 400, else the app's usual retry line. */
  function errorText(err) {
    var msg = err && typeof err.message === "string" ? err.message : "";
    return msg === "HTTP 400" ? BAD_PATH : NOT_SAVED;
  }

  /* aria-invalid on the field only for a path the core refused */
  function invalid(box, on) {
    if (on && typeof box.setAttribute === "function") {
      box.setAttribute("aria-invalid", "true");
    } else if (!on && typeof box.removeAttribute === "function") {
      box.removeAttribute("aria-invalid");
    }
  }

  /* focus is still on the form (the field or Use) or nowhere (the body) */
  function stillHere(doc, box) {
    var a = doc.activeElement;
    return !a || a === box || a === doc.body || a.id === "logpath-use";
  }

  function paint(doc, snap) {
    var form = doc.getElementById("logpath-form");
    if (!form) { return; }
    var show = view(snap).show;
    if (form.hidden === show) {
      form.hidden = !show;
      /* a failed answer goes with the form; a Saved line stays */
      var said = doc.getElementById("logpath-said");
      if (!show && said && said.textContent !== SAVED) { said.textContent = ""; }
    }
  }

  var env = { busy: false };

  /* One post at a time; the answer's state is painted at once. */
  function submit(doc, api, onState) {
    var box = doc.getElementById("logpath-in");
    var said = doc.getElementById("logpath-said");
    if (!box || !said || env.busy || typeof api !== "function") { return null; }
    var body = payload(box.value);
    said.textContent = "";
    invalid(box, false);
    if (!body) { return null; }
    var p = api("POST", "/api/consent", body);
    if (!p || typeof p.then !== "function") { return null; }
    env.busy = true;
    return p.then(function (res) {
      env.busy = false;
      box.value = "";
      said.textContent = SAVED;
      if (isObj(res) && isObj(res.state) && typeof onState === "function") {
        onState(res.state);
      }
    }, function (e) {
      env.busy = false;
      said.textContent = errorText(e);
      var bad = said.textContent === BAD_PATH;
      invalid(box, bad);
      /* LP-A: a refused path moves focus to the field, so a screen reader
         reads its invalid state and the answer it points at
         (aria-describedby); a retry line leaves focus where it is, and so
         does a player who moved on while the post was in flight */
      if (bad && typeof box.focus === "function" && stillHere(doc, box)) { box.focus(); }
    });
  }

  function wire(doc, api, onState) {
    var form = doc.getElementById("logpath-form");
    if (!form) { return false; }
    form.addEventListener("submit", function (ev) {
      if (ev && typeof ev.preventDefault === "function") { ev.preventDefault(); }
      submit(doc, api, onState);
    });
    return true;
  }

  /* Tests only. */
  function reset() { env = { busy: false }; }

  return {
    MAX_PATH: MAX_PATH, BAD_PATH: BAD_PATH, NOT_SAVED: NOT_SAVED, SAVED: SAVED,
    view: view, payload: payload, errorText: errorText, paint: paint,
    submit: submit, wire: wire, reset: reset
  };
}));
