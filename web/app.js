/* AshLight dashboard. Vanilla JS, no framework, no CDN, no inline script.
   The per-start token arrives in the URL fragment (#token=...), is kept in
   sessionStorage and sent as X-AL-Token (fetch) or ?token= (EventSource,
   which cannot set headers). Every text from the log goes in via
   textContent, never innerHTML.
   TEST-WEB-PANELS-C2 (F-135): this file is the page shell: the token, the
   state feed and its pacer, render / tick / start as loops over the
   registered panels (web/registry.js) and A.host, what the panels share.
   Every card registers itself: the web/panels/ files and the web/*.js
   view modules. Only the four shared shims are named here. */
(function () {
  "use strict";

  var F = window.ALFmt; // web/fmt.js: pad, duration, clock
  var A = window.ALApp; // web/registry.js: the panel loops of render, tick, start
  var KEY = "al.token";
  var token = readToken();
  var snap = null;
  var offset = 0; // client clock minus server clock, seconds
  var renderedVersion = -1;
  var linkLive = false; // the state feed is live right now
  var everLive = false; // ... and was live at least once on this page
  var linkEvent = null; // the feed's last event, for the one bar word

  function $(id) { return document.getElementById(id); }

  function readToken() {
    var t = "";
    var m = /(?:^|[#&])token=([0-9a-fA-F]+)/.exec(location.hash || "");
    if (m) {
      t = m[1];
      try { sessionStorage.setItem(KEY, t); } catch (e) { /* storage off */ }
      try { history.replaceState(null, "", location.pathname); } catch (e) { /* ignore */ }
    } else {
      try { t = sessionStorage.getItem(KEY) || ""; } catch (e) { t = ""; }
    }
    return t;
  }

  var clock = F.clock;

  /* UX-A11Y: write only a changed string. The pills sit in polite live
     regions and are re-set on every state push; rewriting the same words
     would let a screen reader say them again each time. */
  function setText(node, text) {
    if (node.textContent !== text) { node.textContent = text; }
  }

  function setPill(el, state, glyph, word) {
    if (el.getAttribute("data-state") !== state) { el.setAttribute("data-state", state); }
    setText(el.querySelector(".glyph"), glyph);
    setText(el.querySelector(".word"), word);
  }

  function serverNow() { return Date.now() / 1000 - offset; }

  /* While the feed is down the timers stop, so a stale page never looks
     like it is still counting (UI-REVIEW-2). The panels' ticks run in their
     order (web/registry.js); the act clock stops at an idle log's last line
     in web/acts.js (TEST-LIVE-EXIT, decision 0029). */
  function tick() {
    if (!snap || document.hidden || !linkLive) { return; }
    var now = serverNow();
    A.tick(snap, now);
    // TD-09 region hook: every registered Play region's tick (web/regions.js)
    if (window.ALRegions) { window.ALRegions.tick(document, snap, now); }
  }

  /* Links a panel fills on its wire, so the shell reaches a card it does
     not name: evalLink (web/panels/itemcheck.js: price), ratesLink
     (rates.js: getRatesDoc, renderRates, renderPrice, loadRates,
     paintPricesList), webLink (webdata.js: fill, saved, state), readLink
     (consent.js: show, the bar status word) and charLink (web/chars.js:
     view, the picked character's numbers). */
  var evalLink = {};
  var ratesLink = {};
  var webLink = {};
  var readLink = {};
  var charLink = {};

  function viaRates(name, none) {
    return function () {
      var f = ratesLink[name];
      return typeof f === "function" ? f.apply(null, arguments) : none;
    };
  }

  function webState() {
    return typeof webLink.state === "function" ? webLink.state() : { on: false, busy: false, doc: null };
  }

  function webDataSaved(doc) {
    if (typeof webLink.saved === "function") { webLink.saved(doc); }
  }

  /* TEST-WEB-PANELS-A to -C2: what a panel reaches of this page, read on
     its first paint or wire. web/panels/pager.js (el, linkOut, setLine, the
     card pages, the pagers) and feedpace.js (feedLink, pacer) add theirs
     when they load, before this file, so these are merged in. snap is a
     getter; onConnect(fn, late): a first read run by connect() in wire
     order (late: after the rates); onPush(fn): run on every state push;
     repaint(): paint the last push again in full. */
  var own = {
    $: $, api: api, token: token, getSnap: function () { return snap; },
    serverNow: serverNow, webDataSaved: webDataSaved,
    getRatesDoc: viaRates("getRatesDoc", null),
    renderRates: viaRates("renderRates"), renderPrice: viaRates("renderPrice"),
    loadRates: viaRates("loadRates"), webLink: webLink, onConnect: onConnect,
    clock: clock, setText: setText, setPill: setPill, isLive: function () { return linkLive; },
    webState: webState, evalLink: evalLink, ratesLink: ratesLink, readLink: readLink,
    charLink: charLink, render: render, repaint: repaint, onPush: onPush,
    getLink: function () { return { event: linkEvent, everLive: everLive }; }
  };
  A.host = A.host || {};
  Object.keys(own).forEach(function (k) { A.host[k] = own[k]; });

  /* UTIL-MULTICHAR: level, pace, deaths, act times and run history of the
     picked character (web/chars.js); the playing one's without a view. */
  function charView(s) {
    return typeof charLink.view === "function" ? charLink.view(s) : s;
  }

  var pace = null; // pacer(), made in start()
  var pushHooks = []; // host.onPush, in the order the panels wired

  function onPush(fn) {
    if (typeof fn === "function") { pushHooks.push(fn); }
  }

  function render(s) {
    snap = s;
    offset = Date.now() / 1000 - s.now;
    // RUN-PERF-DASH-IDLE: a hidden page paints nothing; one paint on return
    if (pace && !pace.push(s)) { return; }
    // MERGE-SEAMS F5: the restart-overlay note clears on the next state
    // push, before the same-version return (web/panels/restart.js)
    pushHooks.forEach(function (fn) { fn(s); });
    // decision 0029 amendment: say why the overlay is hidden (no live region)
    $("overlay-idle-note").hidden = s.game_idle !== true;
    if (s.version === renderedVersion) { tick(); return; }
    renderedVersion = s.version;
    A.render(s, charView(s));
    // TD-09 region hook: every registered Play region paints after the panels
    if (window.ALRegions) { window.ALRegions.paint(document, s, serverNow()); }
    tick();
  }

  function repaint() {
    if (snap) { renderedVersion = -1; render(snap); }
  }

  /* PLAY-TD-09C-BAR: the one bar status word (web/panels/consent.js) */
  function setLink(event) {
    linkEvent = event;
    linkLive = event === "open";
    if (linkLive) { everLive = true; }
    if (typeof readLink.show === "function") { readLink.show(); }
  }

  function api(method, path, body) {
    var opts = { method: method, headers: { "X-AL-Token": token }, cache: "no-store" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) {
        // the message stays "HTTP <status>"; a JSON answer rides on the
        // error as body (BUILD-SWITCH-COPY: a refusal's reason word)
        var err = new Error("HTTP " + r.status);
        err.status = r.status;
        return r.json().then(function (b) { err.body = b; throw err; },
          function () { throw err; });
      }
      return r.json();
    });
  }

  var connectReads = [];
  var lateReads = [];

  function onConnect(fn, late) {
    if (typeof fn === "function") { (late ? lateReads : connectReads).push(fn); }
  }

  function connect() {
    if (!token) {
      setLink("notoken");
      return;
    }
    // the panels' first reads in wire order, the rates, then the late reads
    // (the version and game-data credit line, web/panels/version.js)
    connectReads.forEach(function (fn) { fn(); });
    A.host.loadRates();
    lateReads.forEach(function (fn) { fn(); });
    api("GET", "/api/state").then(render).catch(function () {
      // a feed that found the core restarted keeps saying so
      if (!linkLive && !(feed && feed.over())) { setLink("error"); }
    });
    if (!feed) { feed = A.host.feedLink(feedHooks()); }
    feed.open();
  }

  /* RUN-FEED-TRUTH: the page's side of feedLink (web/panels/feedpace.js).
     A retry runs the whole connect(), so the panels' first reads come
     again after a core restart that kept its token. */
  var feed = null;

  function feedHooks() {
    return {
      open: function () { return new EventSource("/events?token=" + encodeURIComponent(token)); },
      health: function () {
        return fetch("/api/health", { headers: { "X-AL-Token": token }, cache: "no-store" })
          .then(function (r) { return r.status; });
      },
      link: function (event) {
        setLink(event);
        if (event === "open") { tick(); }
      },
      frame: function (name, m) {
        if (name === "state") {
          try { render(JSON.parse(m.data)); } catch (e) { /* ignore a bad frame */ }
          return;
        }
        /* HOT-RELOAD (decision 0042): a dashboard file changed on disk
           (source checkout only); load the new page. */
        var d = null;
        try { d = JSON.parse(m.data); } catch (e) { d = null; }
        if (d && d.target === "web") { location.reload(); }
      },
      later: function (fn, ms) { return setTimeout(fn, ms); },
      retry: connect,
      everLive: function () { return everLive; }
    };
  }

  function start() {
    // RUN-PERF-DASH-IDLE (F-178): the 1 s ticker and the painters rest
    // while the page is hidden or the game is idle (web/panels/feedpace.js)
    pace = A.host.pacer({
      hidden: function () { return document.hidden; },
      paint: render,
      tick: tick,
      every: function (fn, ms) { return setInterval(fn, ms); },
      stop: function (h) { clearInterval(h); }
    });
    document.addEventListener("visibilitychange", pace.shown);
    // every panel's wire, in its order, before the first push; the last are
    // the 'Tried in game' card (web/checks.js) and the Settings rail
    // (web/panels/consent.js)
    A.start();
    // TD-09 region hook: wire every registered Play region before the first push
    if (window.ALRegions) {
      window.ALRegions.start(document, {
        api: api,
        getSnap: function () { return snap; },
        serverNow: serverNow,
        tabs: window.ALTabs || null
      });
    }
    // The two timers advance once a second while the page shows and the
    // game is not idle; nothing else moves.
    pace.sync();
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
