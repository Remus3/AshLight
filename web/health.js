/* AshLight dashboard: build health and "look for next" (MATH-BUILD-HEALTH,
   MATH-NEXT-LOOK, MATH-DEF-BREAKDOWN, decision 0004). UMD: CommonJS for node --test
   (app/test/health.test.js), window.ALHealth for the page. The core builds
   both from Path of Building's own numbers (server/al/theorycraft/
   health.py) and sends them in GET /api/build as `health` and `next_look`;
   this file only lists them. Each "look for next" row has a Copy button
   that writes its search string to the clipboard inside that click only
   (decision 0014, via ALSearch.copyButton). TC-UPGRADE-PER-SLOT: a row also
   links to the official trade site's search for that slot when the core
   sent a trade2 search URL (built offline, decision 0017); the player's
   click opens it in their browser, AshLight never opens or fetches it.
   No live region, no timers, no network.

   PLAY-TD-19C-BUILD-GRID (TD-19, plan 03 section 4): this is the Health and
   next card of the Build and items grid. Its first page holds the top 3
   health rows and the "look for next" rows (a pager, ALSearch.rowPager);
   its Numbers page lists the plain values, Path of Building's defence and
   sustain rows and any warning past the top 3 (a pager). The card always
   shows; with no build it says so in one row. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALHealth = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* the word shown before each warning, so severity never rests on colour */
  var SEVERITY = { high: "Fix first", medium: "Check", low: "Note" };
  var ALL_CLEAR = "No resistance, attribute or Spirit problems in Path of Building's numbers.";
  var NO_STATS = "This build has no Path of Building numbers. Open it in Path of Building, " +
    "then copy its code again.";
  // UX-B9-CARDS: name the optional calc, not "build calc"
  var NO_WEIGHTS = "More stats show here for each slot once you check items. This " +
    "needs the optional Path of Building calc, which is off by default.";
  // MATH-DEF-BREAKDOWN: the calc-only rows (CalcDefence / CalcPerform)
  var NO_CALC = "Ailment and stun avoidance, flask and charm numbers show here once the " +
    "optional Path of Building calc is on. It is off by default.";
  var COPIED = "Copied - paste it into the search box in game";

  /* TC-UPGRADE-PER-SLOT: the same rule as ALPrices.tradeLink (web/prices.js):
     only a trade2 search page on the official site, else "". */
  var TRADE_SEARCH = /^https:\/\/www\.pathofexile\.com\/trade2\/search\/poe2\/[^\s?#\/]+\?q=[^\s&#]+$/;

  function str(v) { return typeof v === "string" ? v : ""; }

  function tradeLink(u) {
    return (typeof u === "string" && u.length <= 4096 && TRADE_SEARCH.test(u)) ? u : "";
  }

  /* row -> {href, text, label} for its trade-search link, or null */
  function rowLink(r) {
    var href = tradeLink(r.url);
    var base = str(r.base).trim();
    if (!href || !base) { return null; }
    var text = "Search the official trade site for rare " + base + " (" + r.slot + ")";
    return { href: href, text: text, label: text + " (opens in a new tab)" };
  }
  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function fmt(n) {
    var r = Math.round(n * 10) / 10;
    return r.toLocaleString("en-US");
  }

  /* doc: the GET /api/build answer (or null) -> the health view. */
  function view(doc) {
    var h = doc && doc.health && typeof doc.health === "object" ? doc.health : null;
    if (!doc || !doc.loaded || !h || !h.loaded) {
      return { show: false, message: "", warnings: [], values: [] };
    }
    var warnings = (Array.isArray(h.warnings) ? h.warnings : []).filter(function (w) {
      return w && str(w.text) && SEVERITY[w.severity];
    }).map(function (w) {
      return { id: str(w.id), severity: w.severity, word: SEVERITY[w.severity], text: w.text };
    });
    var values = (Array.isArray(h.values) ? h.values : []).filter(function (v) {
      return v && str(v.label) && isNum(v.value);
    }).map(function (v) {
      return { label: v.label, text: fmt(v.value) + str(v.unit) };
    });
    /* UX-U25: with no saved stats the Build card already says so (Key
       stats); this card says nothing and shows only for Look for next rows */
    if (h.has_stats === false && !warnings.length && !values.length) {
      return { show: nextView(doc).rows.length > 0 || defView(doc).rows.length > 0,
        message: "", warnings: [], values: [] };
    }
    var message = str(h.message);
    if (!message && h.has_stats &&
        !warnings.some(function (w) { return w.severity !== "low"; })) {
      message = ALL_CLEAR;
    }
    if (!message && !warnings.length && !values.length) { message = NO_STATS; }
    return { show: true, message: message, warnings: warnings, values: values };
  }

  function fmtDigits(n, digits) {
    var d = isNum(digits) && digits >= 0 && digits <= 3 ? digits : 1;
    return n.toLocaleString("en-US", { maximumFractionDigits: d });
  }

  /* doc -> {rows: [{label, text}], hint} for "defence and sustain"
     (MATH-DEF-BREAKDOWN): PoB's values as it exports them. */
  function defView(doc) {
    var h = doc && doc.loaded && doc.health && typeof doc.health === "object" &&
      doc.health.loaded ? doc.health : null;
    if (!h) { return { rows: [], hint: "" }; }
    var rows = (Array.isArray(h.defence) ? h.defence : []).filter(function (r) {
      return r && str(r.label) && isNum(r.value);
    }).map(function (r) {
      return { label: r.label, text: fmtDigits(r.value, r.digits) + str(r.unit) };
    });
    // AREA-AUDIT P7-5: no "once the calc is on" while it is on and pending
    var hint = h.calc_on === false && h.calc_pending !== true &&
      (rows.length || h.has_stats) ? NO_CALC : "";
    return { rows: rows, hint: hint };
  }

  /* doc -> {rows: [{slot, line, text, note, link}], hint} for "look for
     next"; link is null without a valid trade2 search URL. */
  function nextView(doc) {
    var n = doc && doc.loaded && doc.next_look && typeof doc.next_look === "object"
      ? doc.next_look : null;
    if (!n) { return { rows: [], hint: "" }; }
    var rows = (Array.isArray(n.slots) ? n.slots : []).filter(function (r) {
      return r && str(r.slot) && str(r.line) && str(r.text);
    }).map(function (r) {
      var dropped = isNum(r.dropped) && r.dropped > 0 ? r.dropped : 0;
      return { slot: r.slot, line: r.line, text: r.text,
        note: dropped ? "Shortened to fit the search box: " + dropped +
          (dropped === 1 ? " term" : " terms") + " left out." : "",
        link: rowLink(r) };
    });
    return { rows: rows, hint: n.pob_weights ? "" : NO_WEIGHTS };
  }

  var EMPTY = "No build yet. Load one on the Build card.";
  // UX-U25: the Build card says how to add saved stats; this card only says
  // why it is empty, so a fixed card never shows a blank page
  var NO_HEALTH = "Health shows once the build has Path of Building numbers.";
  var TOP = 3; // health rows on the card's first page (plan 03 section 4)
  // look for next: control rows of 24 px under 3 health rows and the
  // heading (66 + 22 + 4 x 24 + 28 = 212 of 220; compact 2: 164 of 176)
  var NEXT_SIZE = { full: 4, compact: 2 };
  // Numbers: one hint row above the pager (22 + 9 x 22 + 28 = 248)
  var NUM_SIZE = { full: 9, compact: 7 };

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }

  function searchLib() {
    if (typeof window !== "undefined" && window.ALSearch) { return window.ALSearch; }
    return typeof require === "function" ? require("./search.js") : null;
  }

  /* doc -> the rows of the Numbers page: warnings past the top 3, the
     plain values, then the defence and sustain rows; strings only. */
  function numberRows(doc) {
    var v = view(doc);
    var out = v.warnings.slice(TOP).map(function (w) { return w.word + ": " + w.text; });
    v.values.forEach(function (x) { out.push(x.label + ": " + x.text); });
    defView(doc).rows.forEach(function (x) { out.push(x.label + ": " + x.text); });
    return out;
  }

  /* one look-for-next row's whole text (title and the Full text page) */
  function nextText(r) {
    return r.slot + ": " + r.line + " - " + r.text + (r.note ? " " + r.note : "");
  }

  function oneLine(n, text) {
    n.textContent = text;
    if (text) { n.setAttribute("title", text); } else if (n.removeAttribute) { n.removeAttribute("title"); }
    n.hidden = !text;
  }

  var card = { doc: null, next: null, nums: null, loaded: false };

  function pagers(doc, nav) {
    if (card.doc === doc && card.next) { return card; }
    var S = searchLib();
    var klass = function () { return S.sizeClass(doc); };
    card.doc = doc;
    card.next = S.rowPager(doc, {
      label: "look for next", size: NEXT_SIZE, sizeClass: klass, text: nextText,
      parts: function (r) {
        return [{ text: r.slot + ": ", cls: "al-row-lbl" }, { text: r.text, cls: "al-row-txt" }];
      },
      controls: function (d, r, list) {
        var out = [S.copyButton(d, r.text, "Copy " + r.slot + " search string", null, list, nav)];
        if (r.link) {
          // decision 0017: the player's click opens it; nothing is fetched
          var a = el(d, "a", "out", "Trade");
          a.href = r.link.href;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.setAttribute("title", r.link.text);
          a.setAttribute("aria-label", r.link.label);
          out.push(a);
        }
        return out;
      }
    });
    card.nums = S.rowPager(doc, {
      label: "numbers", size: NUM_SIZE, sizeClass: klass,
      empty: function () { return card.loaded ? "No numbers saved in this build." : EMPTY; }
    });
    var nextSlot = doc.getElementById("next-list");
    var numSlot = doc.getElementById("def-list");
    if (nextSlot) { nextSlot.replaceChildren(card.next.node); }
    if (numSlot) { numSlot.replaceChildren(card.nums.node); }
    return card;
  }

  var lastSig = null;

  function paint(doc, buildDoc, nav) {
    var box = doc.getElementById("healthbox");
    if (!box) { return; }
    var v = view(buildDoc);
    var nv = nextView(buildDoc);
    var dv = defView(buildDoc);
    var sig = JSON.stringify([v, nv, dv, !!(buildDoc && buildDoc.loaded)]);
    if (sig === lastSig && card.doc === doc) { return; }
    lastSig = sig;
    box.hidden = false;
    card.loaded = !!(buildDoc && buildDoc.loaded);
    var c = pagers(doc, nav);
    var msg = doc.getElementById("health-msg");
    var said = !card.loaded ? EMPTY : v.message ||
      (!v.warnings.length && !nv.rows.length ? NO_HEALTH : "");
    oneLine(msg, said);
    var list = doc.getElementById("health-list");
    list.replaceChildren();
    var top = v.warnings.slice(0, TOP);
    list.hidden = !top.length;
    top.forEach(function (w) {
      var li = el(doc, "li", "health-row one-line");
      li.dataset.severity = w.severity;
      li.setAttribute("title", w.word + ": " + w.text);
      li.appendChild(el(doc, "strong", "health-word", w.word + ": "));
      li.appendChild(doc.createTextNode(w.text));
      list.appendChild(li);
    });
    var wrap = doc.getElementById("next-wrap");
    if (wrap) { wrap.hidden = !nv.rows.length && !nv.hint; }
    var hint = doc.getElementById("next-hint");
    if (hint) { oneLine(hint, nv.hint ? "- " + nv.hint : ""); }
    var head = doc.getElementById("next-title");
    if (head) {
      if (nv.hint) { head.setAttribute("title", "Look for next - " + nv.hint); } else if (head.removeAttribute) {
        head.removeAttribute("title");
      }
    }
    c.next.set(nv.rows);
    var dh = doc.getElementById("def-hint");
    if (dh) { oneLine(dh, dv.hint); }
    c.nums.set(numberRows(buildDoc));
  }

  return { view: view, nextView: nextView, defView: defView, numberRows: numberRows, paint: paint,
    tradeLink: tradeLink, EMPTY: EMPTY, NO_HEALTH: NO_HEALTH, TOP: TOP, NEXT_SIZE: NEXT_SIZE, NUM_SIZE: NUM_SIZE,
    SEVERITY: SEVERITY,
    ALL_CLEAR: ALL_CLEAR, NO_CALC: NO_CALC, NO_STATS: NO_STATS, NO_WEIGHTS: NO_WEIGHTS, COPIED: COPIED };
}));
