/* AshLight dashboard panel: the Prices card and the last price check
   (DATA-NINJA-UI / PRICE-1-UI, decision 0016), moved out of web/app.js
   by TEST-WEB-PANELS-C1 (finding F-135; research 0047 R4 (c)). poe.ninja
   currency values and the last price check. Rates are polled from the
   local core every few minutes (the core itself asks poe.ninja at most
   once an hour); no refresh button.

   The block moved verbatim: RATES_POLL_MS, ratesDoc, ratesAgain,
   priceShown, PRICE_ROWS, rateRows, trendRows, paintPricesList,
   renderRates, renderMovers, loadRates, pollRates and renderPrice, plus
   the "price" entry's paint and the poll timer start() set. The edits:
   the page's snap, the feed's live flag and the web data state are read
   through the host's getSnap(), isLive() and webState(); renderPrice
   hands its rows to the Last item card through the host's evalLink
   (web/panels/itemcheck.js fills it). On its wire this panel fills the
   host's ratesLink, so app.js's connect() and Price watch paint, and the
   web data panel (host getRatesDoc, renderRates, renderPrice, loadRates),
   reach these functions as before the move.

   The same one request as before (GET /api/rates, on connect, on the
   poll and on a refresh the core just started); the trade and poe.ninja
   links open only on the player's click (decision 0017). No clipboard.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "price", order 40: the name and order
   app.js gave this entry before the move, so the paint order of today's
   page is kept. The core links this file at the panels marker of
   index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALApp.register(api.panel(function () { return root.ALApp.host; }));
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "price";
  var ORDER = 40; // app.js gave "price" 40 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, setPill, getSnap, isLive, linkPager, webLink, webState, evalLink, ratesLink;
  var P = null; // web/prices.js: pure view helpers
  var clock = null; // web/fmt.js clock, through the host
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("price: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; setPill = host.setPill; getSnap = host.getSnap;
    isLive = host.isLive; linkPager = host.linkPager; webLink = host.webLink;
    webState = host.webState; evalLink = host.evalLink; ratesLink = host.ratesLink;
    P = window.ALPrices;
    clock = host.clock;
    bound = true;
  }

  var RATES_POLL_MS = 5 * 60 * 1000;
  var ratesDoc = null;
  var ratesAgain = null;
  var priceShown = null;

  function textRow(s) { return { text: s }; }

  /* PLAY-TD-19D-ITEMS-GRID (F-056): the Prices card is one list that
     pages: your checked items first (web/pricewatch.js rows), then the
     currency values (top 6), then the week's movers (3) worded as a
     trend. All of it is the cached poe.ninja book; nothing new is asked. */
  var PRICE_ROWS = { full: 7, compact: 4 };
  var rateRows = [];
  var trendRows = [];

  /* ITEM-INFO-UI (decision 0082 part 1): each row is {text, item}; the
     item's name in the row is a button that opens the shared item info
     popover (web/iteminfo.js), plain text while that file is absent. */
  function itemParts(r) {
    var I = window.ALItemInfo;
    return I ? I.parts(document, r.text, r.item) : [{ text: r.text }];
  }

  function paintPricesList() {
    var snap = getSnap();
    var pw = window.ALPriceWatch;
    var watch = pw ? pw.items(snap ? snap.price_watch : null) : [];
    linkPager("prices-list", "prices", PRICE_ROWS, {
      rows: watch.concat(rateRows, trendRows),
      text: function (r) { return r.text; },
      parts: itemParts
    });
    // a re-render that took the open popover's button away closes it
    if (window.ALItemInfo) { window.ALItemInfo.sync(); }
  }

  function renderRates() {
    var v = P.ratesView(ratesDoc, webState().doc);
    setPill($("rates-pill"), v.pill.state, v.pill.glyph, v.pill.word);
    // PLAY-TD-21A-SETTINGS-RAIL: the same state beside the web data switch
    setPill($("book-state"), v.pill.state, v.pill.glyph, v.pill.word);
    $("rates-credit").textContent = v.credit;
    $("rates-unit").textContent = v.rows.length
      ? ", in " + v.primary + (v.leagueLine ? ", " + v.leagueLine : "") : "";
    $("rates-credit-line").setAttribute("title", $("rates-credit-line").textContent);
    $("rates-attrib").textContent = v.attribution;
    rateRows = v.rows.map(function (r) {
      return { text: r.name + ": " + r.value + (r.per ? " (" + r.per + ")" : ""), item: r.name };
    });
    renderMovers();
  }

  /* UTIL-MOVERS: the week's biggest moves from the same /api/rates doc */
  function renderMovers() {
    trendRows = P.trendList(ratesDoc);
    paintPricesList();
  }

  function loadRates() {
    if (ratesAgain) { clearTimeout(ratesAgain); ratesAgain = null; }
    api("GET", "/api/rates").then(function (doc) {
      ratesDoc = doc;
      var web = webState();
      if (typeof doc.web_data === "boolean" && !web.busy && doc.web_data !== web.on &&
          typeof webLink.fill === "function") {
        webLink.fill({ web_data: doc.web_data });
      }
      renderRates();
      var snap = getSnap();
      renderPrice(snap ? snap.price : null, true);
      // a refresh the core just started finishes in a few seconds
      if (doc.refreshing) { ratesAgain = setTimeout(loadRates, 3000); }
    }).catch(function () {
      setPill($("rates-pill"), "failed", "[x]", "can't load currency values - is AshLight running?");
      setPill($("book-state"), "failed", "[x]", "can't load currency values - is AshLight running?");
    });
  }

  function pollRates() {
    if (!document.hidden && isLive()) { loadRates(); }
  }

  function renderPrice(pr, force) {
    var v = P.priceView(pr, ratesDoc, clock);
    var key = v ? v.key : "";
    if (key === priceShown && !force) { return; }
    priceShown = key;
    $("price-body").hidden = !v;
    var rows = [];
    if (v) {
      setPill($("price-badge"), v.badge.state, v.badge.glyph, v.badge.word);
      $("price-sentence").textContent = v.sentence;
      if (v.sentence) { rows.push(textRow(v.sentence)); }
      // PRICE-TRADE-LINK (decision 0017): the player's click opens the trade
      // search in their browser; AshLight never opens or fetches it
      if (v.link) {
        rows.push({ text: v.link.text, link: { href: v.link.href, label: "Trade site" },
          linkName: v.item || "this item" });
      }
      // DATA-PRICE-NINJA-LINK: the poe.ninja category page, opened only by
      // the player's click in their browser; AshLight requests nothing
      if (v.ninjaLink) {
        rows.push({ text: v.ninjaLink.text,
          link: { href: v.ninjaLink.href, label: "poe.ninja", aria: v.ninjaLink.label },
          linkName: v.item || "this item" });
      }
      v.rows.forEach(function (r) {
        rows.push(textRow(r.text + (r.about ? " (" + r.about + ")" : "")));
      });
    }
    if (typeof evalLink.price === "function") { evalLink.price(rows); }
  }

  function wire() {
    ratesLink.getRatesDoc = function () { return ratesDoc; };
    ratesLink.renderRates = renderRates;
    ratesLink.renderPrice = renderPrice;
    ratesLink.loadRates = loadRates;
    ratesLink.paintPricesList = paintPricesList;
    setInterval(pollRates, RATES_POLL_MS);
  }

  /* The registry entry; getHost is read on the first wire (start(), before
     the first read), when web/app.js has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      paint: function (s) { bind(getHost()); renderPrice(s.price || null, false); },
      wire: function () { bind(getHost()); wire(); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
