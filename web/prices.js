/* AshLight dashboard: pure view helpers for currency values (DATA-NINJA-UI)
   and the price check result (PRICE-1-UI), decision 0016. UMD: CommonJS for
   node --test (app/test/prices.test.js), window.ALPrices for the page. No
   DOM, no timers, no network. Price check sentences come from the core
   (state.py price_card_text); these helpers add only numbers converted with
   poe.ninja rates and the plain state words. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALPrices = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var TOP_RATES = 8;

  function pill(state, glyph, word) { return { state: state, glyph: glyph, word: word }; }

  /* A value for display: commas from 100 up, then fewer decimals as the
     number grows; under 1, three significant digits. */
  function num(n) {
    if (typeof n !== "number" || !isFinite(n)) { return ""; }
    var a = Math.abs(n);
    var t;
    if (a >= 100) {
      t = String(Math.round(a)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    } else if (a >= 10) {
      t = String(Math.round(a * 10) / 10);
    } else if (a >= 1) {
      t = String(Math.round(a * 100) / 100);
    } else if (a === 0) {
      t = "0";
    } else {
      t = String(Number(a.toPrecision(3)));
    }
    return (n < 0 ? "-" : "") + t;
  }

  function ageText(s) {
    if (typeof s !== "number" || !isFinite(s) || s < 0) { return ""; }
    if (s < 60) { return "just now"; }
    if (s < 3600) { return Math.floor(s / 60) + " min ago"; }
    if (s < 86400) { return Math.floor(s / 3600) + " h ago"; }
    var d = Math.floor(s / 86400);
    return d + (d === 1 ? " day ago" : " days ago");
  }

  /* ---- the one web-data opt-in (decision 0013), GET / POST /api/web-data */
  function webDataView(doc) {
    var on = !!(doc && doc.web_data === true);
    return { on: on, status: on
      ? "Web data is on. Currency values come from poe.ninja about once an hour. " +
        "The trade site is asked only when you check an item."
      : "Web data is off. AshLight asks nothing from the internet." };
  }

  function savedText(on) {
    return on ? "Saved. Web data is on. Currency values arrive within a minute."
              : "Saved. Web data is off. AshLight asks nothing from the internet now.";
  }

  /* ---- poe.ninja rates (GET /api/rates) */
  function rateList(doc) {
    return (doc && doc.rates && typeof doc.rates === "object") ? doc.rates : {};
  }

  function nameOf(id, entry) {
    if (entry && typeof entry.name === "string" && entry.name) { return entry.name; }
    var s = String(id).replace(/[-_]+/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  /* The rate entry for a currency word from a whisper or a listing
     ("exalted", "Exalted Orb", "annulment"), or null. */
  function findRate(doc, currency) {
    var rates = rateList(doc);
    if (typeof currency !== "string" || !currency.trim()) { return null; }
    var c = currency.trim().toLowerCase();
    var ids = Object.keys(rates);
    for (var i = 0; i < ids.length; i++) {
      var id = ids[i];
      var e = rates[id] || {};
      var n = typeof e.name === "string" ? e.name.toLowerCase() : "";
      if (id.toLowerCase() === c || n === c || n === c + " orb" || n === "orb of " + c) {
        return { id: id, entry: e };
      }
    }
    return null;
  }

  function primaryName(doc) {
    if (!doc || typeof doc.primary !== "string" || !doc.primary) { return ""; }
    return nameOf(doc.primary, rateList(doc)[doc.primary]);
  }

  /* An amount of a currency in poe.ninja's primary unit, or null when that
     cannot be said honestly (no rate, no primary, already the primary). */
  function convert(doc, amount, currency) {
    if (typeof amount !== "number" || !isFinite(amount)) { return null; }
    var unit = primaryName(doc);
    var hit = findRate(doc, currency);
    if (!unit || !hit || hit.id === doc.primary) { return null; }
    var v = hit.entry.value;
    if (typeof v !== "number" || !isFinite(v) || v <= 0) { return null; }
    return amount * v;
  }

  function aboutText(doc, amount, currency) {
    var v = convert(doc, amount, currency);
    return v === null ? "" : "about " + num(v) + " " + primaryName(doc);
  }

  function rateTitle(doc) {
    var age = ageText(doc && doc.age_s);
    return "poe.ninja rate" + (age ? ", updated " + age : "");
  }

  /* The asked price of a trade request row, in the primary unit. */
  function tradeAbout(row, doc) {
    var text = row ? aboutText(doc, row.price_amount, row.price_currency) : "";
    return { text: text, title: text ? rateTitle(doc) : "" };
  }

  function ratesPill(doc, has) {
    if (!doc) { return pill("pending", "[ ]", "currency values not loaded yet"); }
    var age = ageText(doc.age_s);
    if (has) {
      if (!doc.web_data) {
        return pill("idle", "[-]", "not updating - web data is off" + (age ? " (from " + age + ")" : ""));
      }
      if (doc.stale) { return pill("blocked", "[#]", "old values" + (age ? " - from " + age : "")); }
      return pill("done", "[+]", age ? "updated " + age : "updated");
    }
    if (!doc.web_data) { return pill("idle", "[-]", "web data is off - no currency values"); }
    if (doc.refreshing) { return pill("running", "[>]", "getting currency values from poe.ninja..."); }
    if (doc.last_error) {
      var mins = Math.ceil((Number(doc.next_refresh_in_s) || 0) / 60);
      return pill("blocked", "[#]", "can't reach poe.ninja - " +
        (mins > 0 ? "trying again in " + mins + " min" : "trying again soon"));
    }
    return pill("pending", "[ ]", "currency values arrive within a minute");
  }

  /* The rates panel: top currencies (by traded volume, else value) in the
     primary unit, the state word, league and the credit. */
  function ratesView(doc) {
    var rates = rateList(doc);
    var unit = primaryName(doc);
    var ids = Object.keys(rates).filter(function (id) {
      var v = rates[id] && rates[id].value;
      return id !== (doc && doc.primary) && typeof v === "number" && isFinite(v) && v > 0;
    });
    ids.sort(function (a, b) {
      var x = rates[a], y = rates[b];
      return ((y.volume || 0) - (x.volume || 0)) || (y.value - x.value) || (a < b ? -1 : 1);
    });
    var rows = ids.slice(0, TOP_RATES).map(function (id) {
      var v = rates[id].value;
      var u = unit || "(unit unknown)";
      return { name: nameOf(id, rates[id]), value: num(v) + " " + u,
               per: v < 1 && unit ? num(1 / v) + " per " + unit : "" };
    });
    return { pill: ratesPill(doc, ids.length > 0), rows: rows, primary: unit,
             league: (doc && typeof doc.league === "string") ? doc.league : "",
             credit: (doc && doc.credit) || "Prices: poe.ninja",
             attribution: (doc && doc.attribution) || "" };
  }

  /* ---- PRICE-1-UI: the snapshot's price (decision 0016 contract). */
  var PRICE_BADGE = {
    searching: pill("running", "[>]", "searching"),
    waiting: pill("pending", "[ ]", "waiting"),
    done: pill("done", "[+]", "priced"),
    off: pill("idle", "[-]", "web data off"),
    error: pill("failed", "[x]", "not priced"),
    // the player can fix these themselves: warn, not red (review N5)
    retry: pill("blocked", "[#]", "can't price")
  };

  function priceView(price, rates, clock) {
    if (!price || !price.text) { return null; }
    var t = price.text;
    var listings = Array.isArray(price.listings) ? price.listings : [];
    var rows = (t.rows || []).map(function (text, i) {
      var l = listings[i] || {};
      return { text: text, about: aboutText(rates, l.amount, l.currency) };
    });
    return {
      key: String(price.id), status: price.status,
      badge: (price.status === "error" &&
              (price.error === "not an item" || price.error === "no league"))
        ? PRICE_BADGE.retry : (PRICE_BADGE[price.status] || PRICE_BADGE.error),
      item: t.item || "", sentence: t.sentence || "", rows: rows,
      when: typeof price.at === "number" && clock ? "Checked at " + clock(price.at) : ""
    };
  }

  function priceEmpty(webOn) {
    return webOn
      ? "Nothing priced yet. Check an item with Alt+Shift+E and its prices from the " +
        "official trade site show here."
      : "Prices need web data, which is off. Turn it on under Prices and web data.";
  }

  return { num: num, ageText: ageText, webDataView: webDataView, savedText: savedText,
           ratesView: ratesView, convert: convert, aboutText: aboutText,
           tradeAbout: tradeAbout, priceView: priceView, priceEmpty: priceEmpty };
}));
