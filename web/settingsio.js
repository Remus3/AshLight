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
   until they set it up. No timers. */
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
  var TOO_BIG = "That file is over 16 KB, so it isn't an AshLight settings file. Nothing changed.";
  var NOT_JSON = "That file isn't an AshLight settings file. Nothing changed.";
  var FAILED = "Nothing changed. Try again.";
  var OFFLINE = "Can't reach AshLight - is it running?";
  var SAVED = "Downloaded " + FILE_NAME + ". It holds AshLight's settings " +
    "only: no contact, password or file paths.";
  var WEB_OFFER = " The file had web data on. It stays off here until you tick " +
    "\"Use web data\" under Prices and web data.";
  /* FOLLOWUP11: the dashboard has no switch for the calc (it is set up
     with setup.ps1 -TcCalc, decision 0018), so the sentence names that
     step instead of a tick box. TC-CALC-OPTIN: that one run installs the
     calc and turns it on (no second edit of the config). */
  var CALC_OFFER = " The file had the optional Path of Building calc on. It stays " +
    "off here. To use it, run scripts\\setup.ps1 -TcCalc. That one step installs " +
    "the calc and turns it on.";

  /* The sentence after an import, from the core's report. */
  function importedText(report) {
    report = report || {};
    var n = (report.applied || []).length;
    var text = n === 0 ? "No settings in that file were changed."
      : "Imported " + n + (n === 1 ? " setting." : " settings.");
    var ignored = report.ignored || [];
    /* the calc gets its own sentence, so it isn't counted as skipped too */
    if (report.tc_calc_offered) {
      ignored = ignored.filter(function (k) { return k !== "tc_calc"; });
    }
    if (ignored.length) {
      text += " Skipped " + ignored.length + (ignored.length === 1 ? " setting" : " settings") +
        " that AshLight doesn't take from a file.";
    }
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

  /* One export. env: {fetch, token, save(blob, name), tell(text)}. */
  function runExport(env) {
    env.tell("");
    return env.fetch("/api/settings-export", {
      headers: { "X-AL-Token": env.token }, cache: "no-store"
    }).then(function (r) {
      if (!r.ok) { env.tell(FAILED); return null; }
      return r.blob().then(function (blob) {
        env.save(blob, FILE_NAME);
        env.tell(SAVED);
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
    var e = { fetch: env.fetch, token: env.token, save: env.save,
      tell: function (text) {
        said.textContent = text;
        [btn, input].forEach(function (el) {
          if (text && el === doc.activeElement) {
            el.setAttribute("aria-label", (el === btn ? "Download settings" :
              "Import a settings file") + " (" + text + ")");
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
    refusedText: refusedText, wire: wire, MAX_BYTES: MAX_BYTES, TOO_BIG: TOO_BIG,
    NOT_JSON: NOT_JSON, FAILED: FAILED, OFFLINE: OFFLINE, SAVED: SAVED,
    WEB_OFFER: WEB_OFFER, CALC_OFFER: CALC_OFFER };
}));
