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

  return {
    evalCard: evalCard,
    tradeCard: tradeCard,
    minutes: minutes,
    msUntilNextChange: msUntilNextChange,
    levelText: levelText,
    deathsText: deathsText,
    zoneText: zoneText
  };
}));
