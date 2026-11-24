/* AshLight dashboard panel: the Last item card (TC-EVAL-UI, the last item
   check from the hotkey press), moved out of web/app.js by
   TEST-WEB-PANELS-C1 (finding F-135; research 0047 R4 (c)).
   PLAY-LEGACY-OUT-2: a new check showing Play is the news hook of
   web/regions.js now (UI-GLANCE ZERO-CLICK); this only fills the card.

   PLAY-TD-19D-ITEMS-GRID: the Last item card's rows, one line each,
   paged with a Full text twin: the check's own rows, then the price rows
   (renderPrice of web/panels/rates.js), then price and points and the
   upgrade search (UX-NEWEST N2: the price words sit together).

   The block moved verbatim: evalShown, EVAL_ROWS, evalRows, paintEvalRows,
   textRow and renderEval, plus the "eval" entry's paint. The one edit: the
   price rows come in through the host's evalLink, which this panel fills
   with price(rows) on its wire, so the rates panel's renderPrice sets them
   as it set evalRows.price before the move. What else the panel shares
   with the page ($, el, setLine, linkPager) is reached through
   window.ALApp.host, which app.js sets before start().

   Paint only: no clipboard, no timer, no request. The upgrade search is a
   link the player opens in their browser (decision 0017).

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "eval", order 20: the name and order
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

  var NAME = "eval";
  var ORDER = 20; // app.js gave "eval" 20 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, el, setLine, linkPager, evalLink;
  var T = null; // web/tc.js: pure view helpers
  var P = null; // web/prices.js: pure view helpers
  var clock = null; // web/fmt.js clock, through the host
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("eval: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; el = host.el; setLine = host.setLine; linkPager = host.linkPager;
    evalLink = host.evalLink;
    T = window.ALTc;
    P = window.ALPrices;
    clock = host.clock;
    bound = true;
  }

  var evalShown = null;

  var EVAL_ROWS = { full: 6, compact: 4 };
  var evalRows = { check: [], price: [], after: [] };

  function paintEvalRows() {
    linkPager("eval-rows", "the item check", EVAL_ROWS, {
      rows: evalRows.check.concat(evalRows.price, evalRows.after),
      text: function (r) { return r.text; }
    });
  }

  function textRow(s) { return { text: s }; }

  function renderEval(ev) {
    var key = ev ? ev.id : null;
    if (key === evalShown) { return; }
    evalShown = key;
    var v = T.evalView(ev, clock);
    $("eval-empty").hidden = !!v;
    $("eval-body").hidden = !v;
    var check = [];
    if (v) {
      var w = $("eval-word");
      w.textContent = v.word;
      w.setAttribute("data-verdict", v.verdict);
      setLine($("eval-item"), v.item);
      $("eval-sentence").textContent = v.sentence;
      $("eval-calc").textContent = v.calc;
      $("eval-calc").hidden = !v.calc;
      if (v.sentence) { check.push(textRow(v.sentence)); }
      if (v.calc) { check.push(textRow(v.calc)); }
      v.notes.forEach(function (n) { check.push(textRow(n)); });
      if (v.rewards) { check.push(textRow(v.rewards)); }
      v.comparisons.forEach(function (c) {
        var slot = c.slot || "Slot";
        // the headline already says the best slot's sentence and calc line;
        // MATH-COMPARE: the other slot's own sentence and Path of Building line
        if (c.slot !== ev.slot && c.sentence) { check.push(textRow(slot + ": " + c.sentence)); }
        if (c.slot !== ev.slot && c.calc) { check.push(textRow(slot + ": " + c.calc)); }
        if (c.stats && c.stats.length) {
          // CL-3: the points in brackets, never run on from the mod text
          c.stats.forEach(function (s) { check.push(textRow(T.statRowText(slot, s))); });
        } else {
          check.push(textRow(slot + ": no stat differences."));
        }
      });
      if (v.unweighted) { check.push(textRow(v.unweighted)); }
      // MATH-POTENTIAL-UI: the core's worst / now / best roll scores
      if (v.rolls) { check.push(textRow(v.rolls)); }
    }
    // TC-CARD-PARTS-WEB: the card parts' notes, read with the verdict
    var notes = document.createDocumentFragment();
    (v ? v.notes : []).forEach(function (n) { notes.appendChild(el("li", "", n)); });
    $("eval-notes").replaceChildren(notes);
    $("eval-notes").hidden = !(v && v.notes.length);
    // UTIL-WAYSTONE-REWARD: the core's reward totals for a waystone
    $("eval-rewards").hidden = !(v && v.rewards);
    $("eval-rewards").textContent = v ? v.rewards : "";
    setLine($("eval-when"), v ? v.when : "");
    var after = [];
    // MATH-VALUE-UI: the item's Note price against its points, from the
    // rates the core already has; nothing when the item has no note price
    var val = v && ev ? P.valueView(ev.value) : null;
    // UX-REGRESSION-SWEEP: with no verdict (no build) there is no points
    // figure to set against the price; the asking price still shows
    if (val && !ev.ok) { val = Object.assign({}, val, { per: "" }); }
    if (val) {
      ["sentence", "per", "stale", "credit"].forEach(function (f) {
        if (val[f]) { after.push(textRow(val[f])); }
      });
    }
    // TC-UPGRADE (decision 0017): the player's click opens the upgrade
    // search in their browser; AshLight never opens or fetches it
    var up = v && ev ? P.upgradeView(ev.upgrade) : null;
    if (up) {
      after.push({ text: up.sentence, link: { href: up.href, label: "Trade site" },
        linkName: up.text.replace(/^Search the official trade site for /, "") });
    }
    evalRows.check = check;
    evalRows.after = after;
    paintEvalRows();
  }

  /* the price rows of web/panels/rates.js renderPrice, set as before */
  function setPrice(rows) {
    evalRows.price = rows;
    paintEvalRows();
  }

  /* The registry entry; getHost is read on the first wire (start(), before
     the first read), when web/app.js has run (it is the last script). The
     wire only binds and fills evalLink, so a price row that lands before
     the first push still reaches the card. */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      paint: function (s) { bind(getHost()); renderEval(s.eval || null); },
      wire: function () { bind(getHost()); evalLink.price = setPrice; }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
