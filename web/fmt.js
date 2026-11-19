/* AshLight dashboard: the shared time formats (TEST-WEB-FMT). pad, the
   m:ss / h:mm:ss duration and the local clock are defined here once; the
   view modules alias them (web/acts.js, web/app.js, web/history.js,
   web/runs.js, web/summary.js, web/strip.js). UMD: CommonJS for node --test
   (app/test/fmt.test.js), window.ALFmt for the page, where it is the first
   script tag. Pure functions: no DOM, no timers, no network. The overlay's
   app/shared/format.js keeps its own pad2 (file-system page, own budget). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALFmt = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* 7 -> "07", 12 -> "12". */
  function pad(n) { return n < 10 ? "0" + n : String(n); }

  function hms(s) {
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
  }

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer; "--:--"
     when unknown, a negative time reads 0:00. */
  function duration(s) {
    if (s === null || s === undefined || !isFinite(s)) { return "--:--"; }
    return hms(Math.max(0, Math.floor(s)));
  }

  /* The size of a time either side of zero (a delta: "1:30" for -90), with
     no unknown form: the caller shows nothing when there is no time. */
  function durationAbs(s) {
    return hms(Math.max(0, Math.floor(Math.abs(s))));
  }

  /* A Date as local "HH:MM". */
  function hm(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }

  /* Local clock time of an epoch (s); "" when the time is not a number. */
  function clock(ts) {
    if (!isFinite(ts)) { return ""; }
    return hm(new Date(ts * 1000));
  }

  /* "14:05" on the day of nowMs (default now), "2026-11-16 14:05" for an
     older time, so a saved card states its age. */
  function clockDated(ts, nowMs) {
    var d = new Date(ts * 1000);
    var now = new Date(typeof nowMs === "number" ? nowMs : Date.now());
    var t = hm(d);
    if (d.toDateString() === now.toDateString()) { return t; }
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + t;
  }

  return { pad: pad, duration: duration, durationAbs: durationAbs, hm: hm,
    clock: clock, clockDated: clockDated };
}));
