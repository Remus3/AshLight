/* AshLight dashboard: the state feed's link and the page pacer, moved out
   of web/app.js by TEST-WEB-PANELS-C2 (finding F-135; adjudicator ruling,
   wave 40: the shell's 300-line budget). The FEED-PACE block moved
   verbatim: feedLink (RUN-FEED-TRUTH, F-175) and pacer (RUN-PERF-DASH-IDLE,
   F-178). app/test/dashboard.test.js runs the block alone.

   Not a card: the file registers no panel. It adds feedLink and pacer to
   window.ALApp.host when it loads (before web/app.js, which merges its own
   members into the same object), and web/app.js calls them through
   A.host from connect() and start(). No DOM, no request of its own: the
   EventSource, the health read and the timers are the page's, passed in.

   UMD like web/fmt.js: CommonJS for node --test exports {feedLink, pacer,
   FEED_RETRY_MS}. The core links this file at the panels marker of
   index.html (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    var host = root.ALApp.host = root.ALApp.host || {};
    host.feedLink = api.feedLink;
    host.pacer = api.pacer;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* FEED-PACE:begin (app/test/dashboard.test.js runs this block alone;
     keep it self-contained ES5)
     RUN-FEED-TRUTH (F-175): the state feed says what really happened.
     When the EventSource is closed for good (readyState 2: the core
     answered with something other than a stream), the page asks
     /api/health once. A 401 after a live feed means the core restarted
     with a new token: the bar says so and the page stops trying (the
     client window reloads itself with the new token). A 401 before any
     live feed is a wrong link. Anything else (an error, no answer) opens
     the feed again FEED_RETRY_MS later, so it retries every 3 s. A feed
     that is only reconnecting (readyState 0) is left to the browser,
     which retries on the core's "retry: 3000".
     o: open() -> a new EventSource; health() -> a promise of the HTTP
     status (0 or a rejection when nothing answered); link(event) with
     "open" | "error" | "restarted" | "notoken"; frame(name, m) for each
     named message; later(fn, ms); everLive() -> bool; retry() (optional,
     else open()) is what a retry runs. */
  var FEED_RETRY_MS = 3000;

  function feedLink(o) {
    var es = null;
    var asking = false;
    var waiting = false;
    var over = false;

    function onError(src) {
      if (src !== es || over) { return; }
      o.link("error");
      if (es.readyState !== 2 || asking || waiting) { return; }
      asking = true;
      var settle = function (code) {
        asking = false;
        if (over) { return; }
        if (code === 401) {
          over = true;
          o.link(o.everLive() ? "restarted" : "notoken");
          return;
        }
        waiting = true;
        o.later(function () {
          waiting = false;
          if (typeof o.retry === "function") { o.retry(); } else { open(); }
        }, FEED_RETRY_MS);
      };
      var p;
      try { p = o.health(); } catch (e) { p = null; }
      if (!p || typeof p.then !== "function") { settle(0); return; }
      p.then(settle, function () { settle(0); });
    }

    function open() {
      if (over) { return null; }
      if (es) { es.close(); }
      var src = o.open();
      es = src;
      src.addEventListener("open", function () { if (src === es) { o.link("open"); } });
      src.addEventListener("error", function () { onError(src); });
      // the state frames and the HOT-RELOAD notice (decision 0042)
      es.addEventListener("state", function (m) { if (src === es) { o.frame("state", m); } });
      es.addEventListener("reload", function (m) { if (src === es) { o.frame("reload", m); } });
      return src;
    }

    return { open: open, over: function () { return over; } };
  }

  /* RUN-PERF-DASH-IDLE (F-178): the page rests while nobody can see it
     and while the game is idle. push(s) is the state push: false while
     the page is hidden (the newest snapshot is held and painted once when
     the page shows again, through shown()); true when the caller paints.
     The 1 s ticker runs only while the page shows and the game is not
     idle (snapshot game_idle, decision 0029): a fresh log line clears
     game_idle and the next push starts it again.
     o: hidden() -> bool; paint(s); tick(); every(fn, ms) -> handle;
     stop(handle). */
  function pacer(o) {
    var held = null;
    var idle = false;
    var ticker = null;

    function sync() {
      var on = !idle && !o.hidden();
      if (on && ticker === null) {
        ticker = o.every(o.tick, 1000);
      } else if (!on && ticker !== null) {
        o.stop(ticker);
        ticker = null;
      }
    }

    function push(s) {
      idle = !!(s && s.game_idle === true);
      sync();
      if (o.hidden()) { held = s; return false; }
      held = null;
      return true;
    }

    function shown() {
      sync();
      if (o.hidden()) { return; }
      if (held) {
        var s = held;
        held = null;
        o.paint(s);
      } else {
        o.tick();
      }
    }

    return { push: push, shown: shown, sync: sync,
      ticking: function () { return ticker !== null; },
      held: function () { return held !== null; } };
  }
  /* FEED-PACE:end */

  return { feedLink: feedLink, pacer: pacer, FEED_RETRY_MS: FEED_RETRY_MS };
}));
