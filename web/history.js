/* AshLight dashboard: the under-level line in the Act times card
   (UTIL-UNDERLEVEL) and the Run history card (UTIL-RUN-HISTORY, decision
   0036). UMD: CommonJS for node --test (app/test/history.test.js),
   window.ALHistory for the page. The core sends every sentence in the
   snapshot (`underlevel`, `run_history`); this file only formats times and
   fills the card. No timers, no network except the player's own clicks
   (switch, clear). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALHistory = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CLEARED = "Run history cleared.";
  var FAILED = "That didn't save. Try again.";

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  function duration(s) {
    s = Math.max(0, Math.floor(Math.abs(s)));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
  }

  /* "+1:30 slower", "0:45 faster", "same as best", or "" with no time yet. */
  function deltaText(d) {
    if (d === null || d === undefined || !isFinite(d)) { return ""; }
    if (Math.abs(d) < 1) { return "same as best"; }
    return d > 0 ? duration(d) + " slower" : duration(d) + " faster";
  }

  function underlevelText(snap) {
    var u = snap && snap.underlevel;
    return u && typeof u.text === "string" ? u.text : "";
  }

  /* Display rows of the best-times table. */
  function bestRows(h) {
    return ((h && h.best) || []).map(function (b) {
      return { label: b.label || b.key, best: b.best_text || duration(b.best_s),
        delta: deltaText(b.delta_s), slower: typeof b.delta_s === "number" && b.delta_s >= 1 };
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
    var ul = doc.getElementById("underlevel");
    if (ul) {
      var t = underlevelText(snap);
      setText(ul, t);
      ul.hidden = !t;
    }
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

  return { duration: duration, deltaText: deltaText, underlevelText: underlevelText,
    bestRows: bestRows, deathRows: deathRows, paint: paint, wire: wire,
    CLEARED: CLEARED, FAILED: FAILED };
}));
