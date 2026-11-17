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

  var FIELDS = ["zone", "timer", "level", "deaths", "sep", "away", "status",
                "tradeFrom", "tradeItem", "tradeWhere", "tradeMore", "anchor"];

  function anchorOf(snap) {
    var c = snap && snap.overlay_layout && snap.overlay_layout.corner;
    return (typeof c === "string" && c.indexOf("bottom") === 0) ? "bottom" : "top";
  }

  /* The visible HUD strings for a state snapshot.
     nowS: the server clock in seconds (client clock minus offset). */
  function hudModel(snap, nowS, status) {
    if (!snap) {
      /* DS-HUD-EMPTY: before the first snapshot the HUD reads "AshLight"
         and the status word; no lone separator. */
      return { zone: "AshLight", timer: "", level: "", deaths: "", sep: "", away: "",
               status: status || "waiting",
               tradeFrom: "", tradeItem: "", tradeWhere: "", tradeMore: "", anchor: "top" };
    }
    var elapsed = snap.zone_entered_at ? nowS - snap.zone_entered_at : null;
    var open = snap.trade_requests || [];
    var card = fmt.tradeCard(open.length ? open[open.length - 1] : null);
    return {
      tradeFrom: card.from,
      tradeItem: card.item,
      tradeWhere: card.where,
      tradeMore: open.length > 1 ? "+" + (open.length - 1) + " more" : "",
      anchor: anchorOf(snap),
      zone: fmt.zoneText(snap.zone, snap.in_hideout),
      timer: fmt.minutes(elapsed),
      level: fmt.levelText(snap.level),
      deaths: fmt.deathsText(snap.deaths),
      sep: "|",
      /* DS-HUD-AFK: the log's AFK / DND state (design 0001 7.2). */
      away: snap.afk ? "AFK" : (snap.dnd ? "DND" : ""),
      status: status || "live"
    };
  }

  /* The word in the HUD status slot: a connection problem first, then
     AFK / DND, else nothing. */
  function statusText(model) {
    if (model.status !== "live") { return model.status; }
    return model.away || "";
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

  return { FIELDS: FIELDS, hudModel: hudModel, shouldRender: shouldRender,
           changedFields: changedFields, statusText: statusText };
}));
