/* AshLight dashboard: the Last session card (UTIL-SESSION-SUMMARY). UMD:
   CommonJS for node --test (app/test/summary.test.js), window.ALSummary for
   the page. The core closes a play stretch by itself (20 minutes idle or
   the game closed) and sends every sentence in the snapshot's
   `session_summary` (server/al/summary.py); this file adds only the local
   end time and fills the card with textContent. No timers, no network.

   PLAY-TD-20B-RUN-CARDS (plan 03 section 4, TD-20): the card is a fixed
   cell of the Run grid and always shows. Its home page is the summary: one
   line a sentence, paged at 7 (5 compact) through web/acts.js's pager
   (the whole sentence in title and on the Full text page), with the end
   sentence under them; until the first summary the card says when it
   fills. Its pages are the run history (web/history.js) and the keep /
   clear switch; web/acts.js's wireCard switches them on a press only. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt, function () {
    return common ? require("./acts.js") : root.ALActs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALSummary = api;
  }
}(typeof self !== "undefined" ? self : this, function (F, actsLib) {
  "use strict";

  /* "14:05" today, "2026-11-16 14:05" for an older card (a saved card
     shows after a restart, so its age is stated; web/fmt.js). */
  var clock = F.clockDated;

  /* Summary lines a page: 7 x 22 + pager 24 + the end sentence (two
     lines, 40) + the page buttons 24 = 242 of the 244 px under the title
     at 1280x760 (compact 5 x 22 + 88 = 198 of 204 at 1024x700). */
  var ROWS = { full: 7, compact: 5 };

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
    var box = doc.getElementById("summarybox");
    if (!box) { return; }
    var A = actsLib();
    var v = view(snap ? snap.session_summary : null, fmt);
    A.wireCard(doc, "summarybox");
    A.fill(doc, "summary-lines", "last session", v ? v.lines.map(function (l) {
      return { text: l };
    }) : [], ROWS);
    var empty = doc.getElementById("summary-empty");
    if (empty) { empty.hidden = !!v; }
    A.showText(doc, "summary-ended", v ? v.ended : "");
  }

  return { view: view, paint: paint, clock: clock, ROWS: ROWS };
}));
