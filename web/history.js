/* AshLight dashboard: the run history (UTIL-RUN-HISTORY, decision 0036).
   UMD: CommonJS for node --test (app/test/util9.test.js), window.ALHistory
   for the page. The core sends every sentence in the snapshot
   (`run_history`); this file only formats times and fills the pages. The
   under-level words are the strip's sub line (web/strip.js) since
   PLAY-LEGACY-OUT-1. No timers, no network except the player's own clicks
   (switch, clear).

   PLAY-TD-20B-RUN-CARDS (plan 03 section 4): the run history is two pages
   of the Run grid's Last session card. "Run history" (#historybox): your
   best time per act and the zones of most deaths across the saved runs
   (20 runs a character), one line a row, paged at 9 (8 compact) through
   web/acts.js's pager; with run history off it says so. "Keep or clear":
   the on / off sentence, the keep switch and the clear button, here until
   PLAY-TD-21B-SETTINGS-ABOUT moves them to Settings. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt, function () {
    return common ? require("./acts.js") : root.ALActs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALHistory = api;
  }
}(typeof self !== "undefined" ? self : this, function (F, actsLib) {
  "use strict";

  var CLEARED = "Run history cleared.";
  /* rows a page: 9 x 22 + pager 24 = 222 of the 244 px under the title at
     1280x760 (compact 8 x 22 + 24 = 200 of 204 at 1024x700) */
  var ROWS = { full: 9, compact: 8 };
  var FAILED = "That didn't save. Try again.";

  /* The size of a time either side of zero, no unknown form (web/fmt.js). */
  var duration = F.durationAbs;

  /* "+1:30 slower", "0:45 faster", "same as best", or "" with no time yet. */
  function deltaText(d) {
    if (d === null || d === undefined || !isFinite(d)) { return ""; }
    if (Math.abs(d) < 1) { return "same as best"; }
    return d > 0 ? duration(d) + " slower" : duration(d) + " faster";
  }

  /* Display rows of the best-times table. */
  function bestRows(h) {
    return ((h && h.best) || []).map(function (b) {
      return { label: b.label || b.key, best: b.best_text || duration(b.best_s),
        // UX-REGRESSION-SWEEP: the best time is this run's own act
        delta: b.this_run ? "best so far" : deltaText(b.delta_s), slower: typeof b.delta_s === "number" && b.delta_s >= 1 };
    });
  }

  function deathRows(h) {
    return ((h && h.deaths_by_zone) || []).map(function (d) {
      return d.zone + ": " + d.deaths + (d.deaths === 1 ? " death" : " deaths");
    });
  }

  /* One line of the Run history page per best act time: "Act 1: best
     20:00, this run 1:40 slower"; this run's own best reads "best so far". */
  function bestLine(r) {
    if (r.delta === "best so far") { return r.label + ": best so far " + r.best + " (this run)"; }
    return r.label + ": best " + r.best + (r.delta ? ", this run " + r.delta : ", not reached this run");
  }

  /* Every row of the Run history page: the best act times, then the zones
     of most deaths ("Most deaths: Ogham, 4 deaths"); with best times and no
     death, the core's no-deaths sentence closes the list. */
  function listRows(h) {
    if (!h || !h.on) { return []; }
    var rows = bestRows(h).map(function (r) { return { text: bestLine(r) }; });
    ((h.deaths_by_zone) || []).forEach(function (d) {
      rows.push({ text: "Most deaths: " + d.zone + ", " + d.deaths +
        (d.deaths === 1 ? " death" : " deaths") });
    });
    if (rows.length && !(h.deaths_by_zone || []).length && h.deaths_empty_text) {
      rows.push({ text: h.deaths_empty_text });
    }
    return rows;
  }

  /* The sentence in place of the best times: run history off, or on with
     no finished act saved yet ("" when there are best times). */
  function emptyText(h) {
    if (!h) { return ""; }
    if (!h.on) { return h.text || ""; }
    return bestRows(h).length ? "" : h.empty_text || "";
  }

  function setText(el, text) {
    if (el && el.textContent !== text) { el.textContent = text; }
  }

  function paint(doc, snap) {
    var box = doc.getElementById("historybox");
    if (!box) { return; }
    var h = (snap && snap.run_history) || null;
    setText(doc.getElementById("history-on"), h ? h.text || "" : "");
    var keep = doc.getElementById("history-keep");
    if (h && keep && doc.activeElement !== keep) { keep.checked = !!h.on; }
    var A = actsLib();
    A.fill(doc, "history-rows", "run history", listRows(h), ROWS);
    A.showText(doc, "history-empty", emptyText(h));
  }

  /* The switch and the clear button. api(method, path, body) -> promise
     of the JSON reply (app.js api()). */
  function wire(doc, api) {
    var keep = doc.getElementById("history-keep");
    var clear = doc.getElementById("history-clear");
    var said = doc.getElementById("history-said");
    if (!keep || !clear) { return; }
    function tell(text) { setText(said, text); }
    keep.addEventListener("change", function () {
      tell("");
      api("POST", "/api/run-history", { enabled: keep.checked }).catch(function () {
        keep.checked = !keep.checked;
        tell(FAILED);
      });
    });
    clear.addEventListener("click", function () {
      tell("");
      api("POST", "/api/run-history", { clear: true }).then(function () {
        tell(CLEARED);
      }, function () { tell(FAILED); });
    });
  }

  return { duration: duration, deltaText: deltaText,
    bestRows: bestRows, deathRows: deathRows, bestLine: bestLine, listRows: listRows,
    emptyText: emptyText, paint: paint, wire: wire, ROWS: ROWS,
    CLEARED: CLEARED, FAILED: FAILED };
}));
