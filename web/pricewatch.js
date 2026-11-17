/* AshLight dashboard: the Price watch card (UTIL-PRICE-WATCH). UMD:
   CommonJS for node --test (app/test/pricewatch.test.js),
   window.ALPriceWatch for the page. The core re-reads the watched items
   from the cached poe.ninja prices on each price book refresh (no new
   request) and sends every sentence in the snapshot's `price_watch`
   part; this file only fills the list. No timers. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALPriceWatch = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CLEARED = "Watched items cleared.";
  var FAILED = "That didn't save. Try again.";

  /* {text, rows: [{text, up}], canClear} for the card. */
  function model(pw) {
    if (!pw) { return { text: "", rows: [], canClear: false }; }
    var rows = (pw.moved || []).map(function (m) {
      return { text: m.text, up: m.change_pct > 0 };
    });
    return { text: pw.text || "", rows: rows, canClear: (pw.count || 0) > 0 };
  }

  function paint(doc, snap) {
    var box = doc.getElementById("watchbox");
    if (!box) { return; }
    var m = model(snap && snap.price_watch);
    var key = JSON.stringify(m);
    if (box.getAttribute("data-key") === key) { return; }
    box.setAttribute("data-key", key);
    var text = doc.getElementById("watch-text");
    text.textContent = m.text;
    text.hidden = !m.text;
    var list = doc.getElementById("watch-moved");
    list.textContent = "";
    m.rows.forEach(function (r) {
      var li = doc.createElement("li");
      li.textContent = r.text;
      li.setAttribute("data-dir", r.up ? "up" : "down");
      list.appendChild(li);
    });
    list.hidden = m.rows.length === 0;
    doc.getElementById("watch-clear").hidden = !m.canClear;
  }

  function wire(doc, api) {
    var btn = doc.getElementById("watch-clear");
    var said = doc.getElementById("watch-said");
    if (!btn) { return; }
    btn.addEventListener("click", function () {
      said.textContent = "";
      api("POST", "/api/price-watch", { clear: true }).then(function () {
        said.textContent = CLEARED;
      }, function () { said.textContent = FAILED; });
    });
  }

  return { model: model, paint: paint, wire: wire, CLEARED: CLEARED, FAILED: FAILED };
}));
