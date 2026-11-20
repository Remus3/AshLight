/* AshLight dashboard: the new-character tips switch (NEWBIE-HINTS, ruling
   L). UMD: CommonJS for node --test (app/test/util13.test.js),
   window.ALHints for the page. The core picks the tip from Client.txt
   events (server/al/hints.py) and region N shows it as a notice
   (web/notice.js; PLAY-LEGACY-OUT-2 removed the old tip card and its
   painter). This file only wires the Settings click "Show new-character
   tips again". No timers, no network but that click. */
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

  return { wire: wire, FAILED: FAILED };
}));
