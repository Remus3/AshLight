/* AshLight dashboard: the region registry (TD-09 hook, PLAY-TD-09A-REGION-HOOK;
   research 0047 R4, the seam move). Every Play region file registers itself
   here, so a later region package edits only its own file: web/index.html
   already loads it and web/app.js calls this registry from three places
   (start, render, tick), never the region by name.

   UMD like web/tabs.js: CommonJS for node --test, window.ALRegions in the
   page. Loaded after web/slots.js and before the region files; web/app.js
   loads last. Deferred scripts run in document order before
   DOMContentLoaded, so every region has registered before start().

   No timers, no network, no clipboard, no live region: the registry only
   calls the regions' own functions, hides retired legacy groups and runs
   the one news hook below.

   The news hook (PLAY-LEGACY-OUT-1, UI-GLANCE ZERO-CLICK): after the
   painters of each state push, two consecutive snapshots are compared. A
   trade request id that was not open before, or a build alert whose words
   changed to new non-empty words, is news for Play: ctx.tabs.notify(doc,
   what) shows Play by itself or marks it "new" (web/tabs.js decides). The
   first snapshot only sets the baseline; a dismiss, an expiry or a cleared
   alert is no news. The region files never call notify themselves.

   Exports (one shared registry; create() makes a fresh one for tests):
   - register(spec): spec = {name, region, retires, paint, tick, wire}.
     name: a unique non-empty string. region: the region letter of
     web/slots.js (g, c, t, n, b, i, u) or null for a helper. retires: the
     data-legacy ids this region replaces. paint(doc, snap, now, ctx),
     tick(doc, snap, now, ctx), wire(doc, ctx): each optional. A region
     registered after start() is wired and its groups retired at once.
   - start(doc, ctx): wires every region in register order, then retires
     their legacy groups. ctx = {api, getSnap, serverNow, tabs}; ctx.tabs
     may be null (no web/tabs.js), so a region checks it before use.
   - paint(doc, snap, now): every painter in register order (each state
     push). tick(doc, snap, now): every ticker in register order (once a
     second). One region that throws is caught and said once on the
     console per cause (at most 20 lines); the regions after it still run.
   - retire(doc, legacyId): hides every [data-legacy=legacyId] node; a
     no-op when there is none. A region node ([data-region=<letter>]) gets
     data-fit=yes once every legacy group of its regions is retired.
   - seen(snap) -> {trades: [open trade ids], alert: build alert words};
     news(before, after) -> the news words for Play ("trade request",
     "build alert", both joined by " and ", or "" for none); pure, for the
     hook and its tests. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALRegions = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SAY_CAP = 20; // console lines a page, so a broken region cannot flood it

  function isFn(v) { return typeof v === "function"; }
  function isName(v) { return typeof v === "string" && v.length > 0; }

  /* What the news hook compares in one snapshot: the open trade request
     ids (snap.trade_requests) and the build alert's words
     (snap.build_alert.text, decision 0045). */
  function seen(snap) {
    var rows = snap && Array.isArray(snap.trade_requests) ? snap.trade_requests : [];
    var trades = [];
    rows.forEach(function (r) {
      if (r && (typeof r.id === "string" || typeof r.id === "number")) { trades.push(String(r.id)); }
    });
    var a = snap && snap.build_alert;
    var alert = a && typeof a === "object" && isName(a.text) ? a.text : "";
    return { trades: trades, alert: alert };
  }

  /* The news between two consecutive snapshots' seen() values; "" when
     there is no earlier one (the first push is the baseline). */
  function news(before, after) {
    if (!before || !after) { return ""; }
    var open = {};
    before.trades.forEach(function (id) { open[id] = true; });
    var out = [];
    if (after.trades.some(function (id) { return !open[id]; })) { out.push("trade request"); }
    if (after.alert && after.alert !== before.alert) { out.push("build alert"); }
    return out.join(" and ");
  }

  function defaultWarn(text) {
    if (typeof console !== "undefined" && console && isFn(console.warn)) { console.warn(text); }
  }

  function create(opts) {
    var warn = opts && isFn(opts.warn) ? opts.warn : defaultWarn;
    var specs = [];      // in register order
    var retired = {};    // legacy id -> true
    var said = {};       // "name phase cause" -> true: each failure is said once
    var saidCount = 0;
    var started = false;
    var startDoc = null;
    var startCtx = null;
    var lastSeen = null; // seen() of the last painted snapshot
    var HOOK = { name: "news" };

    function clean(spec) {
      if (!spec || typeof spec !== "object" || !isName(spec.name)) {
        throw new TypeError("ALRegions.register: a spec needs a name");
      }
      specs.forEach(function (s) {
        if (s.name === spec.name) {
          throw new TypeError("ALRegions.register: " + spec.name + " is registered twice");
        }
      });
      var retires = Array.isArray(spec.retires) ? spec.retires.filter(isName) : [];
      return {
        name: spec.name,
        region: isName(spec.region) ? spec.region : null,
        retires: retires,
        paint: isFn(spec.paint) ? spec.paint : null,
        tick: isFn(spec.tick) ? spec.tick : null,
        wire: isFn(spec.wire) ? spec.wire : null
      };
    }

    /* Run one region function; a throw is caught, said once per region,
       phase and cause (at most SAY_CAP lines a page), and the caller goes
       on with the next region. */
    function guard(s, phase, fn, args) {
      try {
        fn.apply(null, args);
        return true;
      } catch (e) {
        var msg = e && e.message ? e.message : String(e);
        var key = s.name + " " + phase + " " + msg;
        if (!said[key] && saidCount < SAY_CAP) {
          said[key] = true;
          saidCount += 1;
          warn("region " + s.name + " " + phase + " failed: " + msg);
        }
        return false;
      }
    }

    function nodesWith(doc, attr, value) {
      var out = [];
      if (!doc || !isFn(doc.querySelectorAll)) { return out; }
      var list = doc.querySelectorAll("[" + attr + "]") || [];
      for (var i = 0; i < list.length; i++) {
        var n = list[i];
        if (n && isFn(n.getAttribute) && n.getAttribute(attr) === value) { out.push(n); }
      }
      return out;
    }

    /* data-fit=yes on each region node whose regions' legacy groups are
       all retired (a region with none fits once it has started). */
    function markFit(doc) {
      if (!started) { return; }
      var regions = {};
      specs.forEach(function (s) {
        if (!s.region) { return; }
        var ok = s.retires.every(function (id) { return retired[id] === true; });
        regions[s.region] = (regions[s.region] !== false) && ok;
      });
      Object.keys(regions).forEach(function (r) {
        if (!regions[r]) { return; }
        nodesWith(doc, "data-region", r).forEach(function (n) {
          if (n.getAttribute("data-fit") !== "yes") { n.setAttribute("data-fit", "yes"); }
        });
      });
    }

    function hide(doc, legacyId) {
      if (!isName(legacyId)) { return; }
      nodesWith(doc, "data-legacy", legacyId).forEach(function (n) {
        if (n.hidden !== true) { n.hidden = true; }
      });
      retired[legacyId] = true;
    }

    function startOne(s) {
      if (s.wire) { guard(s, "wire", s.wire, [startDoc, startCtx]); }
      s.retires.forEach(function (id) { hide(startDoc, id); });
    }

    function register(spec) {
      var s = clean(spec);
      specs.push(s);
      if (started) {
        startOne(s);
        markFit(startDoc);
      }
      return s.name;
    }

    function start(doc, ctx) {
      if (started) { return; }
      started = true;
      startDoc = doc;
      startCtx = ctx || {};
      specs.slice().forEach(startOne);
      markFit(doc);
    }

    function each(phase, doc, snap, now) {
      specs.slice().forEach(function (s) {
        if (s[phase]) { guard(s, phase, s[phase], [doc, snap, now, startCtx]); }
      });
    }

    /* The news hook: one notify per push at most, after the painters. */
    function tellNews(doc, snap) {
      var now = seen(snap);
      var what = news(lastSeen, now);
      lastSeen = now;
      var tabs = startCtx && startCtx.tabs;
      if (what && tabs && isFn(tabs.notify)) { tabs.notify(doc, what); }
    }

    function paint(doc, snap, now) {
      each("paint", doc, snap, now);
      guard(HOOK, "paint", tellNews, [doc, snap]);
    }
    function tick(doc, snap, now) { each("tick", doc, snap, now); }

    function retire(doc, legacyId) {
      hide(doc, legacyId);
      markFit(doc);
    }

    function names() { return specs.map(function (s) { return s.name; }); }

    return {
      register: register, start: start, paint: paint, tick: tick,
      retire: retire, names: names
    };
  }

  var api = create();
  api.create = create;
  api.seen = seen;
  api.news = news;
  return api;
}));
