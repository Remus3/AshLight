/* AshLight dashboard: the last session card (UTIL-SESSION-SUMMARY). UMD:
   CommonJS for node --test (app/test/summary.test.js), window.ALSummary for
   the page. The core closes a play stretch by itself (20 minutes idle or
   the game closed) and sends every sentence in the snapshot's
   `session_summary` (server/al/summary.py); this file adds only the local
   end time and fills the card with textContent. No timers, no network. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALSummary = api;
  }
}(typeof self !== "undefined" ? self : this, function (F) {
  "use strict";

  /* "14:05" today, "2026-11-16 14:05" for an older card (a saved card
     shows after a restart, so its age is stated; web/fmt.js). */
  var clock = F.clockDated;

  /* card: the snapshot's session_summary (or null). fmt: (ts) -> "14:05". */
  function view(card, fmt) {
    if (!card || !Array.isArray(card.lines)) { return null; }
    var lines = card.lines.filter(function (l) { return typeof l === "string" && l; });
    if (!lines.length) { return null; }
    var ended = "";
    if (typeof card.ended_at === "number" && isFinite(card.ended_at)) {
      var why = typeof card.reason_text === "string" && card.reason_text
        ? " " + card.reason_text : "";
      ended = "Session ended at " + (fmt || clock)(card.ended_at) + why + ".";
    }
    return { lines: lines, ended: ended };
  }

  /* Called on each new snapshot only (not the 1 s tick). */
  function paint(doc, snap, fmt) {
    var v = view(snap ? snap.session_summary : null, fmt);
    var box = doc.getElementById("summarybox");
    if (!box) { return; }
    box.hidden = !v;
    var list = doc.getElementById("summary-lines");
    list.replaceChildren();
    if (v) {
      v.lines.forEach(function (l) {
        var li = doc.createElement("li");
        li.textContent = l;
        list.appendChild(li);
      });
    }
    doc.getElementById("summary-ended").textContent = v ? v.ended : "";
  }

  return { view: view, paint: paint, clock: clock };
}));
