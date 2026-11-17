/* AshLight overlay: pure formatting helpers. UMD: CommonJS for node --test,
   window.ALShared for the overlay page. No DOM, no timers. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALShared = Object.assign(root.ALShared || {}, api);
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  /* Coarse zone timer for the HUD: minute resolution, so the overlay
     repaints at most once a minute for it. */
  function minutes(seconds) {
    if (seconds === null || seconds === undefined || !isFinite(seconds) || seconds < 0) {
      return "--";
    }
    var m = Math.floor(seconds / 60);
    if (m < 1) { return "<1m"; }
    if (m < 60) { return m + "m"; }
    return Math.floor(m / 60) + "h" + pad2(m % 60) + "m";
  }

  /* Milliseconds until minutes(seconds) can show a different text. */
  function msUntilNextChange(seconds) {
    if (seconds === null || seconds === undefined || !isFinite(seconds) || seconds < 0) {
      return null;
    }
    var next = (Math.floor(seconds / 60) + 1) * 60;
    return Math.max(250, Math.ceil((next - seconds) * 1000));
  }

  function levelText(level) {
    return (level === null || level === undefined) ? "Lv unknown" : "Lv " + level;
  }

  function deathsText(deaths) {
    var n = Number(deaths) || 0;
    return n === 1 ? "1 death" : n + " deaths";
  }

  /* UX-REVIEW F1: open trade requests as a count for the HUD status slot
     while a card hides the trade card; empty when none are open. */
  function tradeCount(n) {
    var c = Number(n) || 0;
    if (c <= 0) { return ""; }
    return c === 1 ? "1 trade" : c + " trades";
  }

  /* DS-HUD-CLIP: in a hideout the " (HO)" tag (5 chars) is reserved
     before clipping, so the whole line stays within maxLen. */
  function zoneText(zone, inHideout, maxLen) {
    var z = zone ? String(zone) : "No zone yet";
    var tag = inHideout ? " (HO)" : "";
    var max = (maxLen || 28) - tag.length;
    if (z.length > max) { z = z.slice(0, max - 3) + "..."; }
    return z + tag;
  }

  function amount(n) {
    return (n === null || n === undefined) ? "" : String(n);
  }

  /* The trade whisper card (HUD-WHISPER): three short lines from one
     trade request row of the core snapshot. */
  function tradeCard(req, maxLen) {
    if (!req) { return { from: "", item: "", where: "" }; }
    var max = maxLen || 34;
    function clipText(s) {
      s = s ? String(s) : "";
      return s.length > max ? s.slice(0, max - 3) + "..." : s;
    }
    var item = req.item || "item";
    var price = "";
    if (req.kind === "exchange") {
      item = amount(req.want_amount) + " " + item;
      price = "for " + amount(req.price_amount) + " " + (req.price_currency || "");
    } else if (req.price_amount !== null && req.price_amount !== undefined) {
      price = amount(req.price_amount) + " " + (req.price_currency || "");
    } else {
      price = "no price set";
    }
    var where = price.trim();
    /* DS-HUD-CLIP: "tab Sale (3,7)" - tab name, then (left,top). */
    if (req.stash_tab !== undefined && req.stash_tab !== null) {
      where += " | tab " + req.stash_tab;
      if (req.left !== undefined && req.left !== null &&
          req.top !== undefined && req.top !== null) {
        where += " (" + req.left + "," + req.top + ")";
      }
    }
    return { from: clipText("Trade: " + (req.from || "unknown player")), item: clipText(item),
             where: clipText(where) };
  }

  function clip(s, max) {
    s = s ? String(s) : "";
    return s.length > max ? s.slice(0, max - 3) + "..." : s;
  }

  /* TC-EVAL-UI: the item check card. The words come from the core
     (state.py eval_card_text, one template for both surfaces); this only
     clips them to the card's line limit. verdict drives the edge colour,
     never alone (the head starts with the verdict word). */
  function evalCard(ev, maxLen) {
    var max = maxLen || 34;
    var t = (ev && ev.text) || {};
    if (!ev || !t.head) { return { head: "", item: "", line: "", verdict: "" }; }
    return { head: clip(t.head, max), item: clip(t.item, max), line: clip(t.line, max),
             verdict: ev.ok ? String(ev.verdict || "") : "note" };
  }

  /* PRICE-1-UI (decision 0016): the one card the core chose (state.py
     overlay_card: item check, price check, or both from one press). The
     words come from the core; this only clips them to the line limit. */
  function cardText(card, maxLen) {
    var max = maxLen || 34;
    if (!card || !card.head) { return { head: "", line2: "", line3: "", verdict: "" }; }
    return { head: clip(card.head, max), line2: clip(card.line2, max),
             line3: clip(card.line3, max), verdict: String(card.verdict || "") };
  }

  return {
    cardText: cardText,
    evalCard: evalCard,
    tradeCard: tradeCard,
    minutes: minutes,
    msUntilNextChange: msUntilNextChange,
    levelText: levelText,
    deathsText: deathsText,
    tradeCount: tradeCount,
    zoneText: zoneText
  };
}));
