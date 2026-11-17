/* AshLight dashboard: the new-character tip (NEWBIE-HINTS, ruling L). UMD:
   CommonJS for node --test (app/test/hints.test.js), window.ALHints for
   the page. The core picks the tip from Client.txt events and sends it in
   the snapshot's `hint` part with its end time (server/al/hints.py); this
   file shows it until then and hides it by itself. The one click is "Show
   new-character tips again". No timers of its own, no network but that
   click. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALHints = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var FAILED = "That didn't save. Try again.";

  /* The tip text to show at server time `now`, or "" (none, or ended). */
  function tipText(hint, now) {
    if (!hint || typeof hint.text !== "string" || !hint.text) { return ""; }
    if (isFinite(hint.expires_at) && isFinite(now) && now >= hint.expires_at) {
      return "";
    }
    return hint.text;
  }

  function paint(doc, snap, now) {
    var box = doc.getElementById("hintbox");
    if (!box) { return; }
    var text = tipText(snap && snap.hint, now);
    var p = doc.getElementById("hint-text");
    if (p.textContent !== text) { p.textContent = text; }
    box.hidden = !text;
  }

  function wire(doc, api) {
    var btn = doc.getElementById("hints-reset");
    var said = doc.getElementById("hints-said");
    if (!btn) { return; }
    btn.addEventListener("click", function () {
      said.textContent = "";
      api("POST", "/api/hints", { reset: true }).then(function (r) {
        said.textContent = (r && r.text) || "";
      }, function () { said.textContent = FAILED; });
    });
  }

  return { tipText: tipText, paint: paint, wire: wire, FAILED: FAILED };
}));
