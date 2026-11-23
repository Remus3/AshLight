/* AshLight overlay page. Event-driven only: no requestAnimationFrame, no
   polling loop. A repaint happens when an SSE "state" push changes a visible
   string, or when the coarse zone timer's minute text rolls over, the
   item check card leaves, the guide line is due again or a live feed turns
   stale (one setTimeout to the nearest of the four). */
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
  var lastFrame = 0; // Date.now() of the feed's last frame (RUN-FEED-TRUTH)

  function paint() {
    /* RUN-FEED-TRUTH (F-175): no frame, not even the core's "alive" beat,
       for 45 s marks a live feed stale (render_gate.js feedStatus); the
       next frame makes it live again. */
    var was = status;
    status = S.feedStatus(status, lastFrame, Date.now());
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
        } else if (f === "hudShown") {
          /* OVL-PARTS-PAGE: with every part off and no failure word the
             HUD plate is absent (overlay.css [hidden]). */
          nodes.hud.hidden = !model.hudShown;
        } else if (f === "status" || f === "away" || f === "under" || f === "campaign" ||
                   f === "log" || f === "trades" || f === "guide") {
          /* OVL-LINE2-GUIDE: the guide line (rank 5) and the status word
             share line 2, so a change of either repaints both. */
          nodes.hud.setAttribute("data-status", model.status);
          nodes.status.textContent = S.statusText(model);
          nodes.guide.textContent = model.guide;
        } else {
          nodes[f].textContent = model[f];
        }
      }
      shown = model;
    }
    schedule();
    if (status !== was) { reportGate(); }
  }

  /* One timer to the next visible change: the zone timer's minute
     rollover, the item check card leaving (TC-EVAL-UI), or the guide line
     coming back 20 s after a death or level-up (OVL-LINE2-GUIDE): the
     nearest of the three. */
  function schedule() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (!snap) { return; }
    var now = Date.now() / 1000 - offset;
    /* UTIL-MAPRUN-OVL: the row-1 timer's own clock (map time inside a map).
       OVL-PARTS-PAGE: a timer that is off (or quiet in town) wakes nothing;
       only a new snapshot can bring it back, and that paints anyway. */
    var ms = (shown && !shown.timer) ? null : S.msUntilNextChange(S.timerSeconds(snap, now));
    var evalMs = S.msUntilEvalExpires(snap, now);
    if (evalMs !== null && (ms === null || evalMs < ms)) { ms = evalMs; }
    var guideMs = S.msUntilGuideDue(snap, now);
    if (guideMs !== null && (ms === null || guideMs < ms)) { ms = guideMs; }
    var staleMs = S.msUntilStale(status, lastFrame, Date.now());
    if (staleMs !== null && (ms === null || staleMs < ms)) { ms = staleMs; }
    if (ms !== null) { timer = setTimeout(paint, ms); }
  }

  /* Decision 0029 amendment: tell main whether the overlay may show (it
     hides the window while the game may be closed). Sent on change only. */
  var reported = null;
  function reportGate() {
    var want = S.overlayWanted(snap, status);
    if (want !== reported && typeof cfg.reportGate === "function") {
      reported = want;
      cfg.reportGate(want);
    }
  }

  function connect() {
    if (!cfg.token || !cfg.port) {
      status = "offline";
      paint();
      reportGate();
      return; // main reloads this page when the core writes a token
    }
    /* OVL-OVERLAY-FEED (F-177): view=overlay: the core sends only the
       fields the HUD reads (render_gate.js SNAP_FIELDS), and only when one
       of them changed, so dashboard-only state costs no parse or wake-up. */
    var es = new EventSource("http://127.0.0.1:" + cfg.port + "/events?view=overlay&token=" +
                             encodeURIComponent(cfg.token));
    es.addEventListener("open", function () {
      if (status !== "live") { console.info("overlay: feed live"); }
      lastFrame = Date.now();
      status = "live";
      paint();
    });
    /* RUN-FEED-TRUTH: the core's keep-alive; it only proves the feed is
       alive, so it paints only when it ends a stale mark. */
    es.addEventListener("alive", function () {
      lastFrame = Date.now();
      if (status !== "live") { status = "live"; paint(); reportGate(); }
    });
    es.addEventListener("error", function () { status = "offline"; paint(); reportGate(); });
    es.addEventListener("state", function (m) {
      try {
        snap = JSON.parse(m.data);
        lastFrame = Date.now();
        offset = Date.now() / 1000 - snap.now;
        status = "live";
        paint();
        reportGate();
      } catch (e) { /* ignore a bad frame */ }
    });
  }

  function start() {
    ["hud", "zone", "timer", "level", "deaths", "sep", "guide", "status", "trade", "tradeFrom",
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
