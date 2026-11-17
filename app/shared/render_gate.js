/* AshLight overlay: the "should we repaint?" gate. The HUD repaints only
   when one of its visible strings changes; everything else (other state
   fields, heartbeats, duplicate pushes) costs no frame. UMD like format.js. */
(function (root, factory) {
  "use strict";
  var fmt = (typeof module === "object" && module.exports)
    ? require("./format.js")
    : root.ALShared;
  var api = factory(fmt);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALShared = Object.assign(root.ALShared || {}, api);
  }
}(typeof self !== "undefined" ? self : this, function (fmt) {
  "use strict";

  var FIELDS = ["zone", "timer", "level", "deaths", "sep", "away", "log", "status", "trades",
                "tradeFrom", "tradeItem", "tradeWhere", "tradeMore", "anchor",
                "evalHead", "evalItem", "evalLine", "evalVerdict"];

  /* TC-EVAL-UI: the item check card shows from the hotkey press until the
     core's expires_at (state.py EVAL_CARD_S), then leaves by itself. While
     it shows it takes the one card slot (design 0001 section 10: at most
     one card), so the trade card waits; trades stay on the dashboard. */
  /* PRICE-1-UI (decision 0016): a core that sends "card" has already
     chosen the one card (item check, price check, or both from one press);
     it shows until its expires_at. An older core without the field keeps
     the item check path. */
  function slotPart(snap) {
    if (!snap) { return null; }
    if (Object.prototype.hasOwnProperty.call(snap, "card")) {
      var c = snap.card;
      return c && c.head ? { expires: c.expires_at, text: fmt.cardText(c) } : null;
    }
    var ev = snap.eval;
    if (!ev || !ev.text || !ev.text.head) { return null; }
    var e = fmt.evalCard(ev);
    return { expires: ev.expires_at,
             text: { head: e.head, line2: e.item, line3: e.line, verdict: e.verdict } };
  }

  function freshSlot(snap, nowS) {
    var p = slotPart(snap);
    return (p && typeof p.expires === "number" && nowS < p.expires) ? p : null;
  }

  function withEval(model, snap, nowS) {
    var p = freshSlot(snap, nowS);
    var card = p ? p.text : { head: "", line2: "", line3: "", verdict: "" };
    model.evalHead = card.head;
    model.evalItem = card.line2;
    model.evalLine = card.line3;
    model.evalVerdict = card.verdict;
    /* UX-REVIEW F1: while the card holds the slot, open trade requests
       still show as a count in the status slot, never invisible. */
    var n = (snap && snap.trade_requests) ? snap.trade_requests.length : 0;
    model.trades = card.head ? fmt.tradeCount(n) : "";
    if (card.head) {
      model.tradeFrom = model.tradeItem = model.tradeWhere = model.tradeMore = "";
    }
    return model;
  }

  /* Milliseconds until the card in the slot leaves, or null. */
  function msUntilEvalExpires(snap, nowS) {
    var p = freshSlot(snap, nowS);
    if (!p) { return null; }
    return Math.max(250, Math.ceil((p.expires - nowS) * 1000));
  }

  function hudModel(snap, nowS, status) {
    return withEval(baseModel(snap, nowS, status), snap, nowS);
  }

  function anchorOf(snap) {
    var c = snap && snap.overlay_layout && snap.overlay_layout.corner;
    return (typeof c === "string" && c.indexOf("bottom") === 0) ? "bottom" : "top";
  }

  /* The visible HUD strings for a state snapshot.
     nowS: the server clock in seconds (client clock minus offset). */
  function baseModel(snap, nowS, status) {
    if (!snap) {
      /* DS-HUD-EMPTY: before the first snapshot the HUD reads "AshLight"
         and the status word; no lone separator. */
      return { zone: "AshLight", timer: "", level: "", deaths: "", sep: "", away: "",
               log: "", status: status || "connecting",
               tradeFrom: "", tradeItem: "", tradeWhere: "", tradeMore: "", anchor: "top" };
    }
    var elapsed = snap.zone_entered_at ? nowS - snap.zone_entered_at : null;
    var open = snap.trade_requests || [];
    var card = fmt.tradeCard(open.length ? open[open.length - 1] : null);
    /* UI-REVIEW-2 (design 0001 7.2): say when Client.txt is not being read.
       Not opted in: no numbers at all (they would be made up). Opted in but
       the file is missing or quiet: keep what is known and say so. A core
       without the tailer field counts as reading. */
    var tl = snap.tailer;
    if (tl && !tl.consented) {
      return { zone: "AshLight", timer: "", level: "", deaths: "", sep: "", away: "",
               log: "not reading - see dashboard", status: status || "live",
               tradeFrom: card.from, tradeItem: card.item, tradeWhere: card.where,
               tradeMore: open.length > 1 ? "+" + (open.length - 1) + " more" : "",
               anchor: anchorOf(snap) };
    }
    return {
      tradeFrom: card.from,
      tradeItem: card.item,
      tradeWhere: card.where,
      tradeMore: open.length > 1 ? "+" + (open.length - 1) + " more" : "",
      anchor: anchorOf(snap),
      zone: fmt.zoneText(snap.zone, snap.in_hideout),
      timer: snap.zone ? fmt.minutes(elapsed) : "",
      level: fmt.levelText(snap.level),
      deaths: fmt.deathsText(snap.deaths),
      sep: "|",
      /* DS-HUD-AFK: the log's AFK / DND state (design 0001 7.2). */
      away: snap.afk ? "AFK" : (snap.dnd ? "DND" : ""),
      /* UX-COPY: a known file that is quiet is not missing. Telegraphic so
         it fits after "Lv 100 | 99 deaths" in the 258 px plate (design
         review F1: "waiting for Client.txt" clipped). */
      log: (tl && !tl.reading) ? (tl.path ? "waiting for log" : "no Client.txt") : "",
      status: status || "live"
    };
  }

  /* The word in the HUD status slot: a connection problem first, then the
     Client.txt state, then the open trade count while a card hides the
     trade card, then AFK / DND, else nothing. */
  function statusText(model) {
    if (model.status !== "live") { return model.status; }
    return model.log || model.trades || model.away || "";
  }

  function shouldRender(prev, next) {
    if (!prev) { return true; }
    for (var i = 0; i < FIELDS.length; i++) {
      if (prev[FIELDS[i]] !== next[FIELDS[i]]) { return true; }
    }
    return false;
  }

  /* Field names whose text changed (the page touches only those nodes). */
  function changedFields(prev, next) {
    var out = [];
    for (var i = 0; i < FIELDS.length; i++) {
      if (!prev || prev[FIELDS[i]] !== next[FIELDS[i]]) { out.push(FIELDS[i]); }
    }
    return out;
  }

  return { FIELDS: FIELDS, hudModel: hudModel, msUntilEvalExpires: msUntilEvalExpires,
           shouldRender: shouldRender,
           changedFields: changedFields, statusText: statusText };
}));
