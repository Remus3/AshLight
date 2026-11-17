/* AshLight overlay page. Event-driven only: no requestAnimationFrame, no
   polling loop. A repaint happens when an SSE "state" push changes a visible
   string, or when the coarse zone timer's minute text rolls over (one
   setTimeout to that boundary). */
(function () {
  "use strict";

  var S = window.ALShared;
  var cfg = window.al || { token: "", port: 0 };
  var snap = null;
  var offset = 0;
  var shown = null;
  var status = "waiting";
  var timer = null;
  var nodes = {};

  function paint() {
    var model = S.hudModel(snap, Date.now() / 1000 - offset, status);
    if (S.shouldRender(shown, model)) {
      var changed = S.changedFields(shown, model);
      for (var i = 0; i < changed.length; i++) {
        var f = changed[i];
        if (f === "status") {
          nodes.hud.setAttribute("data-status", model.status);
          nodes.status.textContent = model.status === "live" ? "" : model.status;
        } else {
          nodes[f].textContent = model[f];
        }
      }
      shown = model;
    }
    schedule();
  }

  function schedule() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (!snap || !snap.zone_entered_at) { return; }
    var ms = S.msUntilNextChange(Date.now() / 1000 - offset - snap.zone_entered_at);
    if (ms !== null) { timer = setTimeout(paint, ms); }
  }

  function connect() {
    if (!cfg.token || !cfg.port) {
      status = "core not running";
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
    ["hud", "zone", "timer", "level", "deaths", "status"].forEach(function (id) {
      nodes[id] = document.getElementById(id);
    });
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
