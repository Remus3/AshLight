/* AshLight dashboard: the Run history card (UTIL-RUN-HISTORY, decision
   0036). UMD: CommonJS for node --test (app/test/history.test.js),
   window.ALHistory for the page. The core sends every sentence in the
   snapshot (`run_history`); this file only formats times and fills the
   card. The under-level words are the strip's sub line (web/strip.js)
   since PLAY-LEGACY-OUT-1. No timers, no network except the player's own
   clicks (switch, clear). */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALHistory = api;
  }
}(typeof self !== "undefined" ? self : this, function (F) {
  "use strict";

  var CLEARED = "Run history cleared.";
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

  function cell(doc, tag, text, cls) {
    var c = doc.createElement(tag);
    if (cls) { c.className = cls; }
    c.textContent = text;
    return c;
  }

  function setText(el, text) {
    if (el && el.textContent !== text) { el.textContent = text; }
  }

  function paint(doc, snap) {
    var box = doc.getElementById("historybox");
    if (!box) { return; }
    var h = (snap && snap.run_history) || null;
    box.hidden = !h;
    if (!h) { return; }
    setText(doc.getElementById("history-on"), h.text || "");
    var keep = doc.getElementById("history-keep");
    if (keep && doc.activeElement !== keep) { keep.checked = !!h.on; }
    var rows = bestRows(h);
    var key = JSON.stringify(rows) + "|" + JSON.stringify(deathRows(h));
    if (box.getAttribute("data-key") === key) { return; }
    box.setAttribute("data-key", key);
    var empty = doc.getElementById("history-empty");
    setText(empty, h.empty_text || "");
    empty.hidden = !h.empty_text;
    doc.getElementById("history-table").hidden = rows.length === 0;
    var tbody = doc.getElementById("history-rows");
    tbody.textContent = "";
    rows.forEach(function (r) {
      var tr = doc.createElement("tr");
      var th = cell(doc, "th", r.label);
      th.setAttribute("scope", "row");
      tr.appendChild(th);
      tr.appendChild(cell(doc, "td", r.best, "mono"));
      tr.appendChild(cell(doc, "td", r.delta || "not yet", "mono" + (r.slower ? " slower" : "")));
      tbody.appendChild(tr);
    });
    var deaths = deathRows(h);
    var dtitle = doc.getElementById("history-deaths-title");
    if (dtitle) { dtitle.hidden = !h.on; }
    var dempty = doc.getElementById("history-deaths-empty");
    setText(dempty, h.deaths_empty_text || "");
    dempty.hidden = !h.deaths_empty_text;
    var list = doc.getElementById("history-deaths");
    list.textContent = "";
    deaths.forEach(function (d) { list.appendChild(cell(doc, "li", d)); });
    list.hidden = deaths.length === 0;
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
    bestRows: bestRows, deathRows: deathRows, paint: paint, wire: wire,
    CLEARED: CLEARED, FAILED: FAILED };
}));
