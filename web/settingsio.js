/* AshLight dashboard: settings export / import (UX-SETTINGS-IO, research
   0028 ruling E). UMD: CommonJS for node --test (app/test/settingsio.test.js),
   window.ALSettingsIO for the page.
   Export: on the player's click the core's GET /api/settings-export
   (token header) comes back as a download the browser saves; it holds
   AshLight's own settings only, never the contact, a token, a cookie or a
   file path. Import: the player picks that file with the browser's file
   input; the browser reads it (size-capped) and posts its JSON to the
   core, which applies allowed keys only. Web data is never turned on by
   an import: the player is told to tick the switch themselves. Nor is
   the optional calc (tc_calc_offered): the player is told it stays off
   until they set it up. TC-WEIGHTS-DELTA-EXPORT: schema 2 files also
   carry the player's stat weight changes (weights_applied in the
   report). No timers.
   PLAY-F-186B-PLAYER-NOTES-UI (decision 0074 item 8): the player's zone
   notes join the backup only while "Include my zone notes"
   (#settings-notes) is ticked (GET /api/settings-export?notes=1); an
   import adds notes for new zones and never replaces a note this computer
   already has (notes_added, notes_kept, notes_full in the report). The
   tests of the notes parts are in app/test/playernote.test.js. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALSettingsIO = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_BYTES = 16 * 1024;  /* settingsio.MAX_BYTES */
  var FILE_NAME = "ashlight-settings.json";
  /* RUN-NO-DEAD-ENDS (research 0042 F3): the export is the "settings
     backup", never a "settings file" (that name belongs to no file the
     player edits). */
  var TOO_BIG = "That file is over 16 KB, so it isn't an AshLight settings backup. Nothing changed.";
  var NOT_JSON = "That file isn't an AshLight settings backup. Nothing changed.";
  var FAILED = "Nothing changed. Try again.";
  var OFFLINE = "Can't reach AshLight - is it running?";
  var SAVED = "Downloaded your settings backup, " + FILE_NAME + ". It holds " +
    "AshLight's settings only: no contact, password or file paths.";
  var SAVED_NOTES = "Downloaded your settings backup, " + FILE_NAME + ". It holds " +
    "AshLight's settings and your zone notes: no contact, password or file paths.";
  /* design review D-1: an import replaces this computer's weight changes */
  var WEIGHTS_NOTE = " They replace the stat weights you had here.";
  var WEB_OFFER = " The file had web data on. It stays off here until you tick " +
    "\"Use web data\" under Settings, Reading and web data.";
  /* FOLLOWUP11: the dashboard has no tick box for the calc (decision
     0018). TC-CALC-OPTIN: one run installs the calc and turns it on (no
     second edit of the config). RUN-NO-DEAD-ENDS (research 0042 R4): the
     sentence names the Checks row's button (TC-CALC-OPTIN-BUTTON), never a
     script. */
  var CALC_OFFER = " The file had the optional Path of Building calc on. It stays " +
    "off here. To use it, press \"Set up the calc\" under Settings, Checks in " +
    "the AshLight window. That one step installs the calc and turns it on.";

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  /* The export sentence's tail when some notes did not fit the 16 KB
     backup (the newest ones are in it). */
  function leftOutText(n) {
    return n > 0 ? " " + plural(n, "older note", "older notes") +
      " didn't fit in the backup and stayed only on this computer." : "";
  }

  /* The notes sentences after an import ("" when the file had none). */
  function notesText(report) {
    if (typeof report.notes_added !== "number") { return ""; }
    var added = report.notes_added, kept = report.notes_kept || 0, full = report.notes_full || 0;
    var text = added ? " Added " + plural(added, "zone note", "zone notes") + "." : "";
    if (kept) {
      text += " Kept " + plural(kept, "note", "notes") + " you already had here for the " +
        "same zone; the backup's version wasn't used.";
    }
    if (full) {
      text += " Left out " + plural(full, "note", "notes") + ": AshLight keeps at most " +
        "300 notes for 12 characters.";
    }
    if (report.notes_failed) { text += " Some notes weren't saved. Import the backup again."; }
    if (!text) { text = " Your zone notes were already here."; }
    return text;
  }

  /* The sentence after an import, from the core's report. */
  function importedText(report) {
    report = report || {};
    var n = (report.applied || []).length;
    var w = report.weights_applied === true;
    var text;
    if (n === 0) {
      text = w ? "Imported your stat weights." : "No settings in that file were changed.";
    } else {
      text = "Imported " + n + (n === 1 ? " setting" : " settings") +
        (w ? " and your stat weights." : ".");
    }
    if (w) { text += WEIGHTS_NOTE; }
    var ignored = report.ignored || [];
    /* the calc gets its own sentence, so it isn't counted as skipped too */
    if (report.tc_calc_offered) {
      ignored = ignored.filter(function (k) { return k !== "tc_calc"; });
    }
    if (ignored.length) {
      text += " Skipped " + ignored.length + (ignored.length === 1 ? " setting" : " settings") +
        " that AshLight doesn't take from a file.";
    }
    text += notesText(report);
    if (report.web_data_offered) { text += WEB_OFFER; }
    if (report.tc_calc_offered) { text += CALC_OFFER; }
    return text;
  }

  function refusedText(status, body) {
    if (status === 413) { return TOO_BIG; }
    if (status === 400 && body && typeof body.error === "string" && body.error) {
      return body.error + " Nothing changed.";
    }
    return FAILED;
  }

  /* One import of the picked file. env: {fetch, token, tell(text)}.
     Returns a promise; never throws. */
  function runImport(file, env) {
    if (!file) { return Promise.resolve(); }
    env.tell("");
    if (typeof file.size === "number" && file.size > MAX_BYTES) {
      env.tell(TOO_BIG);
      return Promise.resolve();
    }
    var sent = false;
    return file.text().then(function (text) {
      var doc;
      try { doc = JSON.parse(text); } catch (e) { doc = null; }
      if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
        env.tell(NOT_JSON);
        return null;
      }
      sent = true;
      return env.fetch("/api/settings-import", {
        method: "POST",
        headers: { "X-AL-Token": env.token, "Content-Type": "application/json" },
        body: JSON.stringify(doc),
        cache: "no-store"
      }).then(function (r) {
        return r.json().then(function (b) { return b; }, function () { return null; })
          .then(function (b) {
            env.tell(r.ok ? importedText(b) : refusedText(r.status, b));
          });
      });
    }).catch(function () {
      env.tell(sent ? OFFLINE : FAILED);
    });
  }

  /* The export URL: the notes block only when the player ticked it. */
  function exportUrl(notes) {
    return notes === true ? "/api/settings-export?notes=1" : "/api/settings-export";
  }

  /* One export. env: {fetch, token, save(blob, name), tell(text),
     notes() optional: true while "Include my zone notes" is ticked}. */
  function runExport(env) {
    env.tell("");
    var notes = typeof env.notes === "function" && env.notes() === true;
    return env.fetch(exportUrl(notes), {
      headers: { "X-AL-Token": env.token }, cache: "no-store"
    }).then(function (r) {
      if (!r.ok) { env.tell(FAILED); return null; }
      return r.blob().then(function (blob) {
        env.save(blob, FILE_NAME);
        if (!notes) { env.tell(SAVED); return null; }
        var read = typeof blob.text === "function" ? blob.text() : Promise.resolve("");
        return read.then(function (t) {
          var left = 0;
          try { left = JSON.parse(t).notes_left_out; } catch (e) { left = 0; }
          env.tell(SAVED_NOTES + leftOutText(typeof left === "number" ? left : 0));
        }, function () { env.tell(SAVED_NOTES); });
      });
    }).catch(function () { env.tell(OFFLINE); });
  }

  function wire(doc, env) {
    var btn = doc.getElementById("settings-export");
    var input = doc.getElementById("settings-import-file");
    var said = doc.getElementById("settings-said");
    if (!btn || !input) { return; }
    /* No live region (the page keeps its 12): as for the loot filter
       merge, the focused control's name carries the answer too. */
    var notesBox = doc.getElementById("settings-notes");
    var e = { fetch: env.fetch, token: env.token, save: env.save,
      notes: function () { return !!(notesBox && notesBox.checked); },
      tell: function (text) {
        said.textContent = text;
        [btn, input].forEach(function (el) {
          if (text && el === doc.activeElement) {
            el.setAttribute("aria-label", (el === btn ? "Download settings backup" :
              "Import a settings backup") + " (" + text + ")");
          } else {
            el.removeAttribute("aria-label");
          }
        });
      } };
    btn.addEventListener("click", function () { runExport(e); });
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      runImport(file, e).then(function () { input.value = ""; });
    });
  }

  return { runImport: runImport, runExport: runExport, importedText: importedText,
    refusedText: refusedText, wire: wire, exportUrl: exportUrl, notesText: notesText,
    leftOutText: leftOutText, SAVED_NOTES: SAVED_NOTES, MAX_BYTES: MAX_BYTES, TOO_BIG: TOO_BIG,
    NOT_JSON: NOT_JSON, FAILED: FAILED, OFFLINE: OFFLINE, SAVED: SAVED,
    WEB_OFFER: WEB_OFFER, CALC_OFFER: CALC_OFFER, WEIGHTS_NOTE: WEIGHTS_NOTE };
}));
