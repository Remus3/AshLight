/* AshLight dashboard: your checked items (UTIL-PRICE-WATCH). UMD:
   CommonJS for node --test (app/test/util9.test.js), window.ALPriceWatch
   for the page. The core re-reads the watched items from the cached
   poe.ninja prices on each price book refresh (no new request) and sends
   every sentence in the snapshot's `price_watch` part; this file only
   words the rows. No timers.

   PLAY-TD-19D-ITEMS-GRID (F-056): the separate Price watch card is gone.
   rows() gives the first rows of the Prices card's list (web/app.js
   paintPricesList: a moved item above the currency values and movers);
   paint() fills the card's "Your checked items" page (the whole sentence
   and the Clear button) and marks the Build and items tab "moved" while a
   checked item moved (web/tabs.js mark: a word beside the tab name, no
   live region). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALPriceWatch = api;
    /* TEST-WEB-PANELS-C2 (F-135): UTIL-PRICE-WATCH registers itself
       (web/registry.js) as "pricewatch", order 160, the name and order
       web/app.js gave it: moved prices of the items the player checked,
       on top of the Prices card list (PLAY-TD-19D-ITEMS-GRID; the list is
       painted again through app.js's ratesLink, web/panels/rates.js). */
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register({
        name: "pricewatch",
        order: 160,
        paint: function (s) {
          var rates = root.ALApp.host.ratesLink;
          if (api.paint(document, s) && typeof rates.paintPricesList === "function") { rates.paintPricesList(); }
        },
        wire: function () { api.wire(document, root.ALApp.host.api); }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CLEARED = "Watched items cleared.";
  var FAILED = "That didn't save. Try again.";
  var MARK = "moved";
  var MOVED_PAGE = "Moved prices are listed first on the card.";
  var TAB = "build";

  /* {text, rows: [{text, up}], canClear} for the card. */
  function model(pw) {
    if (!pw) { return { text: "", rows: [], canClear: false }; }
    var rows = (pw.moved || []).map(function (m) {
      return { text: m.text, up: m.change_pct > 0 };
    });
    return { text: pw.text || "", rows: rows, canClear: (pw.count || 0) > 0 };
  }

  /* The Prices list's first rows: each moved item ("You checked <name>:
     up 30%, from 1 to 1.3 Divine Orb"), else the one sentence that says
     why nothing moved (paused, empty or quiet), else none. */
  function rows(pw) {
    var m = model(pw);
    if (m.rows.length) {
      return m.rows.map(function (r) { return "You checked " + r.text; });
    }
    return m.text ? [m.text] : [];
  }

  function tabs() {
    return typeof self !== "undefined" && self.ALTabs ? self.ALTabs : null;
  }

  /* Fill the page and the tab mark; true when anything changed (then the
     page's list is painted again). */
  function paint(doc, snap) {
    var box = doc.getElementById("pricesbox");
    if (!box) { return false; }
    var m = model(snap && snap.price_watch);
    var key = JSON.stringify(m);
    if (box.getAttribute("data-watch") === key) { return false; }
    box.setAttribute("data-watch", key);
    var text = doc.getElementById("watch-text");
    text.textContent = m.text || (m.rows.length ? MOVED_PAGE : "");
    doc.getElementById("watch-clear").hidden = !m.canClear;
    var t = tabs();
    if (t && typeof t.mark === "function") { t.mark(doc, TAB, m.rows.length ? MARK : ""); }
    return true;
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

  return { model: model, rows: rows, paint: paint, wire: wire, CLEARED: CLEARED,
           FAILED: FAILED, MARK: MARK, MOVED_PAGE: MOVED_PAGE };
}));
