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

  var FIELDS = ["zone", "timer", "level", "deaths", "status"];

  /* The visible HUD strings for a state snapshot.
     nowS: the server clock in seconds (client clock minus offset). */
  function hudModel(snap, nowS, status) {
    if (!snap) {
      return { zone: "", timer: "", level: "", deaths: "", status: status || "waiting" };
    }
    var elapsed = snap.zone_entered_at ? nowS - snap.zone_entered_at : null;
    return {
      zone: fmt.zoneText(snap.zone, snap.in_hideout),
      timer: fmt.minutes(elapsed),
      level: fmt.levelText(snap.level),
      deaths: fmt.deathsText(snap.deaths),
      status: status || "live"
    };
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
           changedFields: changedFields };
}));
