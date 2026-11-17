/* AshLight dashboard: pure helpers for the trade request list. UMD:
   CommonJS for node --test (app/test/trades.test.js), window.ALTrades for
   the page. No DOM, no timers, no network.
   UX-REVIEW F6 (2026-11-17): a screen reader hears a new trade request
   once, through the polite #trade-status region; nothing is said on the
   first paint, a dismiss or an expiry. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALTrades = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function tradeIds(rows) {
    return (rows || []).map(function (r) { return r.id; });
  }

  /* prevIds: the ids shown before (null before the first paint).
     rows: the open trade requests now, oldest first. */
  function newTradeSentence(prevIds, rows) {
    if (!prevIds) { return ""; }
    var seen = {};
    prevIds.forEach(function (id) { seen[id] = true; });
    var fresh = (rows || []).filter(function (r) { return !seen[r.id]; });
    if (fresh.length === 0) { return ""; }
    if (fresh.length > 1) { return fresh.length + " new trade requests."; }
    var from = fresh[0].from;
    return from ? "New trade request from " + from + "." : "New trade request.";
  }

  /* Write the polite region (anything with textContent). The same sentence
     twice is cleared first so it is said again; a shrinking set clears the
     old sentence, which no longer matches the list (design review
     2026-11-17 F2). First paint and no change write nothing. */
  function showStatus(el, prevIds, rows) {
    var say = newTradeSentence(prevIds, rows);
    if (say) {
      if (el.textContent === say) { el.textContent = ""; }
      el.textContent = say;
      return;
    }
    if (prevIds && (rows || []).length < prevIds.length && el.textContent !== "") {
      el.textContent = "";
    }
  }

  return { tradeIds: tradeIds, newTradeSentence: newTradeSentence, showStatus: showStatus };
}));
