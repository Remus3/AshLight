/* AshLight overlay page. Event-driven only: no requestAnimationFrame, no
   polling loop. A repaint happens when an SSE "state" push changes a visible
   string, or when the coarse zone timer's minute text rolls over or the
   item check card leaves (one setTimeout to the nearer of the two). */
(function () {
  "use strict";

  var S = window.ALShared;
  var cfg = window.al || { token: "", port: 0, credit: "" };
  var snap = null;
  var offset = 0;
  var shown = null;
  var status = "connecting";
  var timer = null;
  var nodes = {};

  function paint() {
    var model = S.hudModel(snap, Date.now() / 1000 - offset, status);
    if (S.shouldRender(shown, model)) {
      var changed = S.changedFields(shown, model);
      for (var i = 0; i < changed.length; i++) {
        var f = changed[i];
        if (f === "anchor") {
          document.body.setAttribute("data-anchor", model.anchor);
        } else if (f === "tradeItem") {
          nodes.tradeItem.textContent = model.tradeItem;
          nodes.trade.hidden = !model.tradeItem;
        } else if (f === "evalHead") {
          nodes.evalHead.textContent = model.evalHead;
          nodes.evalCard.hidden = !model.evalHead;
        } else if (f === "evalVerdict") {
          nodes.evalCard.setAttribute("data-verdict", model.evalVerdict);
        } else if (f === "status" || f === "away" || f === "under" || f === "campaign" ||
                   f === "log" || f === "trades") {
          nodes.hud.setAttribute("data-status", model.status);
          nodes.status.textContent = S.statusText(model);
        } else {
          nodes[f].textContent = model[f];
        }
      }
      shown = model;
    }
    schedule();
  }

  /* One timer to the next visible change: the zone timer's minute
     rollover, or the item check card leaving (TC-EVAL-UI). */
  function schedule() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (!snap) { return; }
    var now = Date.now() / 1000 - offset;
    /* UTIL-MAPRUN-OVL: the row-1 timer's own clock (map time inside a map) */
    var ms = S.msUntilNextChange(S.timerSeconds(snap, now));
    var evalMs = S.msUntilEvalExpires(snap, now);
    if (evalMs !== null && (ms === null || evalMs < ms)) { ms = evalMs; }
    if (ms !== null) { timer = setTimeout(paint, ms); }
  }

  function connect() {
    if (!cfg.token || !cfg.port) {
      status = "offline";
      paint();
      return; // main reloads this page when the core writes a token
    }
    var es = new EventSource("http://127.0.0.1:" + cfg.port + "/events?token=" +
                             encodeURIComponent(cfg.token));
    es.addEventListener("open", function () {
      if (status !== "live") { console.info("overlay: feed live"); }
      status = "live";
      paint();
    });
    es.addEventListener("error", function () { status = "offline"; paint(); });
    es.addEventListener("state", function (m) {
      try {
        snap = JSON.parse(m.data);
        offset = Date.now() / 1000 - snap.now;
        status = "live";
        paint();
      } catch (e) { /* ignore a bad frame */ }
    });
  }

  function start() {
    ["hud", "zone", "timer", "level", "deaths", "sep", "status", "trade", "tradeFrom",
     "tradeItem", "tradeWhere", "tradeMore", "evalCard", "evalHead", "evalItem",
     "evalLine"].forEach(function (id) {
      nodes[id] = document.getElementById(id);
    });
    // TC-SNAP-UI: the game-data credit joins the About only with snapshot data.
    var about = document.getElementById("aboutData");
    about.textContent = cfg.credit || "";
    about.hidden = !cfg.credit;
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
