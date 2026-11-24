/* AshLight dashboard: pure view helpers for currency values (DATA-NINJA-UI)
   and the price check result (PRICE-1-UI), decision 0016. UMD: CommonJS for
   node --test (app/test/prices.test.js), window.ALPrices for the page. No
   DOM, no timers, no network. Price check sentences come from the core
   (server/al/text/price.py price_card_text); these helpers add only numbers
   converted with poe.ninja rates and the plain state words. */
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

  var TOP_RATES = 6; // PLAY-TD-19D-ITEMS-GRID: the Prices card shows the top 6
  var TREND_ROWS = 3; // and the week's 3 biggest moves

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

  /* ---- the one web-data opt-in (decision 0013), GET / POST /api/web-data.
     DATA-CONTACT-UI (F-018): `blocked` is the core's reason no poe.ninja
     request runs ("web data off", "contact not set", "release build" or
     null; /api/web-data and /api/rates both carry it). While prices are
     blocked the words name the one step instead of a promise. */
  var NO_CONTACT = "contact not set";
  var RELEASE = "release build";
  var STEP_CONTACT = "add your contact for poe.ninja";
  var RELEASE_TEXT = "This version of AshLight does not ask poe.ninja for prices.";

  function blockedOf(doc) {
    var b = doc && typeof doc.blocked === "string" ? doc.blocked : "";
    return b === NO_CONTACT || b === RELEASE ? b : "";
  }

  /* The contact field (write-only: never prefilled, the value is never
     echoed; the core answers only contact_set). Shown only while the doc
     says no contact is set; a doc without contact_set leaves it as it is
     (show null). DATA-CONTACT-DEFAULT: contact_set is the typed contact
     only; with none, requests carry the project's issues page, so the
     field is an optional per-install override. */
  function contactView(doc) {
    var known = !!doc && typeof doc.contact_set === "boolean";
    return {
      show: known ? doc.contact_set !== true : null,
      label: "Your contact for poe.ninja",
      note: "Optional. An email address or a name. poe.ninja asks who runs an app. " +
            "AshLight sends your contact if you add one, else its project issues page when this copy has one. " +
            "Stored only on this computer."
    };
  }

  function webDataView(doc) {
    var on = !!(doc && doc.web_data === true);
    var blocked = on ? blockedOf(doc) : "";
    var status;
    if (!on) {
      status = "Web data is off. AshLight asks nothing from the internet.";
    } else if (blocked === NO_CONTACT) {
      status = "Web data is on. This copy has no default contact, so prices need one more step: " + STEP_CONTACT + " below.";
    } else if (blocked === RELEASE) {
      status = "Web data is on. " + RELEASE_TEXT;
    } else {
      status = "Web data is on. Prices come from poe.ninja about once an hour.";
    }
    return { on: on, blocked: blocked, status: status, contact: contactView(doc) };
  }

  /* After a saved switch; `doc` is the POST answer (its blocked reason). */
  function savedText(on, doc) {
    if (!on) { return "Saved. Web data is off. AshLight asks nothing from the internet now."; }
    var blocked = blockedOf(doc);
    if (blocked === NO_CONTACT) {
      return "Saved. Web data is on. Prices start once you " + STEP_CONTACT + " below.";
    }
    if (blocked === RELEASE) { return "Saved. Web data is on. " + RELEASE_TEXT; }
    return "Saved. Web data is on. Currency values arrive within a minute.";
  }

  /* The answer to a contact Save; `doc` is the POST answer. */
  var CONTACT_REFUSED = "AshLight can't use that contact. Use up to 120 plain " +
                        "characters, without brackets or a backslash.";

  function contactSavedText(doc) {
    if (!doc || doc.contact_set !== true) { return "Not saved. Try again."; }
    if (doc.web_data !== true) {
      return "Contact saved on this computer. Turn on web data to get poe.ninja prices.";
    }
    if (blockedOf(doc) === RELEASE) { return "Contact saved on this computer. " + RELEASE_TEXT; }
    return "Contact saved on this computer. Currency values arrive within a minute.";
  }

  /* ---- DATA-LEAGUE-PICKER-UI (F-141): the league picker from the GET
     /api/web-data doc: "league" (the setting or null), "league_auto" (the
     current league's name or null), "prices_from" (the league prices come
     from: a solo league maps to its trade league) and "leagues" (the
     cached names, newest first). The first option is the automatic one
     (value "", the key removed); with no pick the league follows
     poe.ninja's current one. Shown only while a list is cached. */
  function textOf(v) { return typeof v === "string" && v.trim() ? v.trim() : ""; }

  function leagueView(doc) {
    var names = doc && Array.isArray(doc.leagues) ? doc.leagues.filter(textOf) : [];
    var setting = textOf(doc && doc.league);
    var auto = textOf(doc && doc.league_auto);
    var from = textOf(doc && doc.prices_from);
    var options = [{ value: "", text: auto ? "Automatic (" + auto + ")"
                                           : "Automatic (poe.ninja's current league)" }];
    names.forEach(function (n) { options.push({ value: n, text: n }); });
    // a league set by hand that the list lacks stays the shown choice
    if (setting && names.indexOf(setting) < 0) { options.push({ value: setting, text: setting }); }
    var mapped = !!(setting && from && from !== setting);
    return {
      show: names.length > 0, label: "League for prices", options: options,
      selected: setting,
      from: mapped ? "Prices from " + from + ": poe.ninja has no prices for " + setting + "." : ""
    };
  }

  function leagueSavedText(doc) {
    var setting = textOf(doc && doc.league);
    if (!setting) { return "Saved. Prices follow poe.ninja's current league."; }
    var from = textOf(doc && doc.prices_from);
    var source = from && from !== setting ? from : setting;
    return "Saved. Prices come from " + source + " after the next price update.";
  }

  var LEAGUE_REFUSED = "AshLight can't price that league. Pick one from the list, " +
                       "or the automatic league.";

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
    var from = age ? " (from " + age + ")" : "";
    var blocked = doc.web_data ? blockedOf(doc) : "";
    if (has) {
      if (!doc.web_data) {
        return pill("idle", "[-]", "not updating - web data is off" + from);
      }
      // DATA-CONTACT-UI: opted in but blocked, like "waiting for Client.txt"
      if (blocked === NO_CONTACT) { return pill("blocked", "[#]", "not updating - " + STEP_CONTACT + from); }
      if (blocked === RELEASE) { return pill("idle", "[-]", "not updating in this version" + from); }
      if (doc.stale) { return pill("blocked", "[#]", "old values" + (age ? " - from " + age : "")); }
      return pill("done", "[+]", age ? "updated " + age : "updated");
    }
    if (!doc.web_data) { return pill("idle", "[-]", "web data is off - no currency values"); }
    if (blocked === NO_CONTACT) { return pill("blocked", "[#]", "one step left: " + STEP_CONTACT); }
    if (blocked === RELEASE) { return pill("idle", "[-]", "no currency values in this version"); }
    if (doc.refreshing) { return pill("running", "[>]", "getting currency values from poe.ninja..."); }
    if (doc.last_error) {
      var mins = Math.ceil((Number(doc.next_refresh_in_s) || 0) / 60);
      return pill("blocked", "[#]", "can't reach poe.ninja - " +
        (mins > 0 ? "trying again in " + mins + " min" : "trying again soon"));
    }
    return pill("pending", "[ ]", "currency values arrive within a minute");
  }

  /* The rates panel: top currencies (by traded volume, else value) in the
     primary unit, the state word, league and the credit.
     DATA-LEAGUE-PICKER-UI: `web` (optional, the GET /api/web-data doc)
     names the league line: "league <rates league>", or, when a solo
     league is mapped, "league <setting>, prices from <trade league>". */
  function leagueLine(league, web) {
    var setting = textOf(web && web.league);
    var from = textOf(web && web.prices_from);
    if (setting && from && from !== setting) { return "league " + setting + ", prices from " + from; }
    return league ? "league " + league : "";
  }

  function ratesView(doc, web) {
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
    var league = (doc && typeof doc.league === "string") ? doc.league : "";
    return { pill: ratesPill(doc, ids.length > 0), rows: rows, primary: unit,
             league: league, leagueLine: leagueLine(league, web),
             credit: (doc && doc.credit) || "Prices: poe.ninja",
             attribution: (doc && doc.attribution) || "" };
  }

  /* ---- UTIL-MOVERS: the week's biggest price changes from the cached
     poe.ninja overviews (/api/rates `movers`; no extra request). Shown only
     while web data is on. */
  function moverRow(r) {
    var ch = typeof r.change === "number" && isFinite(r.change) ? r.change : 0;
    // under 0.5% is no trend, as the core's price card says (state.ninja_text)
    var change = Math.abs(ch) < 0.5 ? "no change"
      : (ch > 0 ? "up " : "down ") + num(Math.abs(ch)) + "%";
    var unit = typeof r.unit === "string" && r.unit ? " " + r.unit : "";
    var value = typeof r.value === "number" && isFinite(r.value) ? num(r.value) + unit : "";
    var name = typeof r.name === "string" && r.name ? r.name : "Unnamed item";
    return { name: name, change: change, value: value };
  }

  function moversView(doc) {
    var on = !!(doc && doc.web_data === true);
    var m = doc && doc.movers && typeof doc.movers === "object" ? doc.movers : {};
    var up = Array.isArray(m.up) ? m.up.map(moverRow) : [];
    var down = Array.isArray(m.down) ? m.down.map(moverRow) : [];
    var blocked = on ? blockedOf(doc) : "";
    var empty = "";
    if (on && !up.length && !down.length) {
      empty = blocked === NO_CONTACT
        ? "No price changes to show yet. They appear once you " + STEP_CONTACT + "."
        : blocked === RELEASE
          ? "No price changes to show. " + RELEASE_TEXT
          : "No price changes to show yet. They appear after the next hourly price update.";
    }
    return { show: on, up: up, down: down, empty: empty };
  }

  /* PLAY-TD-19D-ITEMS-GRID (F-056): the week's 3 biggest moves of either
     direction, each worded as a trend in one line ("X is rising: up 61%
     this week (0.35 Divine Orb)"); the empty sentence while web data is on
     and there is none; nothing while web data is off. */
  function trendRows(doc) {
    return trendList(doc).map(function (r) { return r.text; });
  }

  /* ITEM-INFO-UI: the same rows as {text, item}: item is the mover's name
     (the Prices list makes it the item info button), "" for the empty
     sentence and an unnamed mover. */
  function trendList(doc) {
    var m = moversView(doc);
    if (!m.show) { return []; }
    if (m.empty) { return [{ text: m.empty, item: "" }]; }
    var all = m.up.map(function (r, i) { return { r: r, raw: doc.movers.up[i] }; })
      .concat(m.down.map(function (r, i) { return { r: r, raw: doc.movers.down[i] }; }));
    var size = function (x) {
      var c = x.raw && typeof x.raw.change === "number" && isFinite(x.raw.change) ? x.raw.change : 0;
      return Math.abs(c);
    };
    all.sort(function (a, b) { return size(b) - size(a); });
    return all.slice(0, TREND_ROWS).map(function (x) {
      var r = x.r;
      var word = r.change === "no change" ? " has not moved" :
        (r.change.indexOf("up ") === 0 ? " is rising: " : " is falling: ") + r.change + " this week";
      return { text: r.name + word + (r.value ? " (" + r.value + ")" : ""),
               item: x.raw && typeof x.raw.name === "string" && x.raw.name ? r.name : "" };
    });
  }

  /* ---- PRICE-1-UI: the snapshot's price (decision 0016 contract). */
  var PRICE_BADGE = {
    // PRICE-TRADE-LINK (decision 0017): the trade search link is ready
    link: pill("done", "[+]", "link ready"),
    searching: pill("running", "[>]", "searching"),
    waiting: pill("pending", "[ ]", "waiting"),
    done: pill("done", "[+]", "priced"),
    off: pill("idle", "[-]", "web data off"),
    // off because no contact for poe.ninja is set yet (DATA-CONTACT-UI: the
    // player types it in the web data form, Settings > Reading and web
    // data; the core keeps it only on this computer); idle like "web data
    // off": a setting the player has not made yet, not a failed check
    // (design review PRICE-1-COPY F3)
    contact: pill("idle", "[-]", "no contact"),
    error: pill("failed", "[x]", "not priced"),
    // the player can fix these themselves: warn, not red (review N5)
    retry: pill("blocked", "[#]", "can't price")
  };

  /* PRICE-TRADE-LINK (decision 0017): the card's url only when it is a
     trade2 search page on the official site (the core builds it offline and
     never opens it; the player's click opens it in their browser), else "". */
  var TRADE_SEARCH = /^https:\/\/www\.pathofexile\.com\/trade2\/search\/poe2\/[^\s?#\/]+\?q=[^\s&#]+$/;

  function tradeLink(u) {
    return (typeof u === "string" && u.length <= 4096 && TRADE_SEARCH.test(u)) ? u : "";
  }

  /* DATA-PRICE-NINJA-LINK (decision 0016 amendment 2026-11-23): the card's
     ninja_url only when it is a poe.ninja PoE2 economy category page (the
     core picks it from a table of page forms read from poe.ninja; the app
     requests nothing, the player's click opens it), else "". */
  var NINJA_PAGE = /^https:\/\/poe\.ninja\/poe2\/economy\/[a-z0-9]+(?:-[a-z0-9]+)*\/[a-z0-9]+(?:-[a-z0-9]+)*$/;

  function ninjaLink(u) {
    return (typeof u === "string" && u.length <= 200 && NINJA_PAGE.test(u)) ? u : "";
  }

  function priceView(price, rates, clock) {
    if (!price || !price.text) { return null; }
    var t = price.text;
    var href = price.status === "link" ? tradeLink(price.url) : "";
    var ninja = price.status === "link" ? ninjaLink(price.ninja_url) : "";
    var name = t.item || "this item";
    var listings = Array.isArray(price.listings) ? price.listings : [];
    var rows = (t.rows || []).map(function (text, i) {
      var l = listings[i] || {};
      return { text: text, about: aboutText(rates, l.amount, l.currency) };
    });
    return {
      key: String(price.id), status: price.status,
      badge: (price.status === "error" &&
              (price.error === "not an item" || price.error === "no league" ||
               price.error === "no base type"))
        ? PRICE_BADGE.retry
        : (price.status === "off" && price.error === "contact not set")
          ? PRICE_BADGE.contact
          : (PRICE_BADGE[price.status] || PRICE_BADGE.error),
      item: t.item || "", sentence: t.sentence || "", rows: rows,
      link: href ? { href: href, text: "Search the official trade site for " + name,
                     label: "Search the official trade site for " + name +
                            " (opens in a new tab)" } : null,
      ninjaLink: ninja ? { href: ninja, text: "Compare prices of items like " + name + " on poe.ninja",
                           label: "Compare prices of items like " + name + " on poe.ninja" +
                                  " (opens in a new tab)" } : null,
      when: typeof price.at === "number" && clock ? "Checked at " + clock(price.at) : ""
    };
  }

  /* TC-UPGRADE (decision 0017 item 3): the item check's `upgrade` doc (slot,
     base, source equipped | item, url) -> the upgrade-search link view, or
     null when there is no valid trade2 search URL. Same link rules as the
     price link: the core builds it offline, the player's click opens it. */
  function upgradeView(up) {
    if (!up || typeof up !== "object") { return null; }
    var href = tradeLink(up.url);
    var base = typeof up.base === "string" ? up.base.trim() : "";
    var slot = typeof up.slot === "string" ? up.slot.trim() : "";
    if (!href || !base || !slot) { return null; }
    var where = up.source === "item"
      ? "Your build has nothing in " + slot + ", so this uses the checked item's base, " +
        base + ". "
      : "Your build wears " + base + " in " + slot + ", so this finds rare items of that base. ";
    return {
      href: href,
      sentence: where + "It matches base type and rarity only, not stats.",
      // the slot keeps it apart from the price link on the same card (UP-3)
      text: "Search the official trade site for rare " + base + " (" + slot + ")",
      label: "Search the official trade site for rare " + base + " (" + slot +
             ") (opens in a new tab)"
    };
  }

  /* MATH-VALUE-UI: the item check's `value` doc (MATH-VALUE: the item's own
     Note price in poe.ninja's primary currency, points per primary unit,
     the rates' stale flag and credit) -> the card's words, or null when
     the item has no note price. Nothing is fetched: the core computed it
     from the cached rates. */
  function currencyName(id, name) {
    return (typeof name === "string" && name && name !== id) ? name : nameOf(id, null);
  }

  function valueView(v) {
    if (!v || typeof v !== "object" || !v.price || typeof v.price !== "object") { return null; }
    var p = v.price;
    if (typeof p.amount !== "number" || !isFinite(p.amount) || p.amount <= 0 ||
        typeof p.currency !== "string" || !p.currency) { return null; }
    var cur = currencyName(p.currency, p.name);
    var listed = (p.kind === "b/o" ? "Buyout price: " : "Asking price: ") +
                 num(p.amount) + " " + cur;
    var primary = (typeof v.primary === "string" && v.primary)
      ? currencyName(v.primary, v.primary_name) : "";
    var rated = !!primary && typeof v.price_primary === "number" && isFinite(v.price_primary);
    var sentence;
    if (!primary) {
      // RUN-NO-DEAD-ENDS (research 0042 F12): name the switch and its place
      sentence = listed + ". No currency values are saved yet, so AshLight can't " +
                 "compare the item's price with its points. They come by themselves " +
                 "while \"Use web data\" is ticked under Settings, Reading and web data.";
    } else if (!rated) {
      sentence = listed + ". There is no saved value for " + cur + " yet, so AshLight " +
                 "can't compare the item's price with its points.";
    } else if (p.currency === v.primary) {
      sentence = listed + ".";
    } else {
      sentence = listed + ", about " + num(v.price_primary) + " " + primary + ".";
    }
    var spp = v.score_per_primary;
    var per = rated && typeof spp === "number" && isFinite(spp)
      ? (num(spp) === "1" || num(spp) === "-1" ? num(spp) + " point" : num(spp) + " points") +
        " per " + primary + "."
      : "";
    return {
      sentence: sentence, per: per,
      stale: rated && v.stale ? "These currency values may be out of date." : "",
      credit: rated ? ((typeof v.credit === "string" && v.credit) || "Prices: poe.ninja") : ""
    };
  }

  return { num: num, ageText: ageText, webDataView: webDataView, savedText: savedText,
           contactView: contactView, contactSavedText: contactSavedText,
           CONTACT_REFUSED: CONTACT_REFUSED, leagueView: leagueView,
           leagueSavedText: leagueSavedText, LEAGUE_REFUSED: LEAGUE_REFUSED,
           ratesPill: ratesPill, ratesView: ratesView, convert: convert, aboutText: aboutText,
           tradeAbout: tradeAbout, priceView: priceView, trendRows: trendRows, trendList: trendList,
           tradeLink: tradeLink, ninjaLink: ninjaLink, upgradeView: upgradeView, moversView: moversView,
           valueView: valueView };
}));
