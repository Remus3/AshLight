/* AshLight dashboard. Vanilla JS, no framework, no CDN, no inline script.
   The per-start token arrives in the URL fragment (#token=...), is kept in
   sessionStorage and sent as X-AL-Token (fetch) or ?token= (EventSource,
   which cannot set headers). Every text from the log goes in via
   textContent, never innerHTML. */
(function () {
  "use strict";

  var D = window.ALDash; // web/status.js: pure view helpers
  var KEY = "al.token";
  var token = readToken();
  var snap = null;
  var offset = 0; // client clock minus server clock, seconds
  var renderedVersion = -1;
  var es = null;
  var ticker = null;
  var linkLive = false; // the state feed is live right now
  var everLive = false; // ... and was live at least once on this page

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

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  function duration(s) {
    if (s === null || s === undefined || !isFinite(s)) { return "--:--"; }
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
  }

  function clock(ts) {
    var d = new Date(ts * 1000);
    return pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function setPill(el, state, glyph, word) {
    el.setAttribute("data-state", state);
    el.querySelector(".glyph").textContent = glyph;
    el.querySelector(".word").textContent = word;
  }

  function serverNow() { return Date.now() / 1000 - offset; }

  /* While the feed is down the timers stop, so a stale page never looks
     like it is still counting (UI-REVIEW-2). */
  function tick() {
    if (!snap || document.hidden || !linkLive) { return; }
    var now = serverNow();
    $("zone-time").textContent = snap.zone_entered_at ? duration(now - snap.zone_entered_at) : "--:--";
    // Before the Client.txt opt-in there is no play session to time.
    $("session").textContent = snap.tailer && snap.tailer.consented
      ? duration(now - snap.session_started_at) : "--:--";
  }

  function renderEvents(rows) {
    var list = $("events");
    var frag = document.createDocumentFragment();
    for (var i = rows.length - 1; i >= 0; i--) {
      var row = rows[i];
      var li = document.createElement("li");
      var k = D.kindOf(row);
      if (row.whisper) { li.className = "whisper"; }
      if (row.trade) { li.className += " trade"; }
      if (row.type === "death") { li.className = "death"; }
      var t = document.createElement("span");
      t.className = "time mono";
      t.textContent = clock(row.at);
      var kd = document.createElement("span");
      kd.className = "kind";
      kd.textContent = k;
      var tx = document.createElement("span");
      tx.className = "text";
      tx.textContent = row.text;
      li.appendChild(t);
      li.appendChild(kd);
      li.appendChild(tx);
      frag.appendChild(li);
    }
    list.replaceChildren(frag);
    $("events-empty").hidden = rows.length > 0;
  }

  var renderedTrades = "";

  function renderTrades(rows) {
    var key = JSON.stringify(rows.map(function (r) { return r.id; }));
    if (key === renderedTrades) { return; }
    renderedTrades = key;
    var frag = document.createDocumentFragment();
    for (var i = rows.length - 1; i >= 0; i--) {
      var t = rows[i];
      var line = D.tradeLine(t);
      var li = document.createElement("li");
      var tm = document.createElement("span");
      tm.className = "time mono";
      tm.textContent = clock(t.at);
      var what = document.createElement("span");
      what.className = "what";
      what.textContent = line.what;
      var where = document.createElement("span");
      where.className = "where";
      where.textContent = line.where;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = "Dismiss";
      btn.setAttribute("aria-label", "Dismiss trade request from " + (t.from || "unknown player"));
      btn.addEventListener("click", dismissTrade.bind(null, t.id));
      li.appendChild(tm);
      li.appendChild(what);
      li.appendChild(where);
      li.appendChild(btn);
      frag.appendChild(li);
    }
    $("trade-list").replaceChildren(frag);
    $("trades").hidden = rows.length === 0;
  }

  /* Dashboard-only: dismissing never sends anything to the game. */
  function dismissTrade(id) {
    $("trade-status").textContent = "";
    api("POST", "/api/trade-dismiss", id === null ? { all: true } : { id: id })
      .then(function (res) { render(res.state); })
      .catch(function (e) {
        $("trade-status").textContent = "Not dismissed. Try again.";
        console.warn("dismiss failed: " + e.message);
      });
  }

  /* OVL-POS: overlay layout editor. Saved to config/local.json by the core;
     the overlay follows the file. */
  var layoutBusy = false;

  function option(value, text) {
    var o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    return o;
  }

  function fillLayout(doc) {
    var l = doc.layout;
    var corner = $("layout-corner");
    if (!corner.options.length) {
      doc.corners.forEach(function (c) { corner.appendChild(option(c, D.cornerLabel(c))); });
    }
    var disp = $("layout-display");
    disp.replaceChildren(option("primary", "Primary"));
    (doc.displays || []).forEach(function (d) {
      disp.appendChild(option(String(d.index), "Monitor " + (d.index + 1) +
        (d.primary ? " (primary)" : "") +
        (d.width ? " - " + d.width + "x" + d.height : "") +
        (d.scale_factor && d.scale_factor !== 1
          ? " @" + Math.round(d.scale_factor * 100) + "%" : "")));
    });
    var known = (doc.displays || []).some(function (d) { return d.index === l.display; });
    if (l.display !== "primary" && !known) {
      disp.appendChild(option(String(l.display),
        "Monitor " + (l.display + 1) + " (not connected - primary used)"));
    }
    disp.value = String(l.display);
    corner.value = l.corner;
    $("layout-scale").value = String(l.scale);
    $("layout-opacity").value = String(l.opacity);
    $("layout-margin").value = String(l.margin);
    $("layout-scale-out").textContent = Math.round(l.scale * 100) + "%";
    $("layout-opacity-out").textContent = Math.round(l.opacity * 100) + "%";
  }

  function readLayoutForm() {
    var d = $("layout-display").value;
    return {
      display: d === "primary" ? "primary" : parseInt(d, 10),
      corner: $("layout-corner").value,
      scale: parseFloat($("layout-scale").value),
      opacity: parseFloat($("layout-opacity").value),
      margin: parseInt($("layout-margin").value, 10) || 0
    };
  }

  function saveLayout() {
    if (layoutBusy) { return; }
    layoutBusy = true;
    $("layout-status").textContent = "Saving...";
    api("POST", "/api/overlay-layout", readLayoutForm()).then(function (doc) {
      fillLayout(doc);
      $("layout-status").textContent = "Saved. The overlay moves within a second.";
    }).catch(function (e) {
      $("layout-status").textContent = "Not saved. Try again.";
      console.warn("layout save failed: " + e.message);
    }).then(function () { layoutBusy = false; });
  }

  function loadLayout() {
    api("GET", "/api/overlay-layout").then(fillLayout).catch(function () {
      $("layout-status").textContent = "Can't load the overlay settings. Is AshLight running?";
    });
  }

  function render(s) {
    snap = s;
    offset = Date.now() / 1000 - s.now;
    if (s.version === renderedVersion) { tick(); return; }
    renderedVersion = s.version;

    $("zone").textContent = s.zone || "No zone yet";
    $("hideout").hidden = !s.in_hideout;
    $("level").textContent = s.level === null ? "-" : String(s.level);
    $("who").textContent = s.character
      ? s.character + (s["class"] ? " (" + s["class"] + ")" : "")
      : "character unknown";
    $("deaths").textContent = String(s.deaths);
    $("levelups").textContent = s.level_ups + (s.level_ups === 1 ? " level-up" : " level-ups");
    var flags = [];
    if (s.afk) { flags.push("AFK"); }
    if (s.dnd) { flags.push("DND"); }
    $("flags").textContent = flags.length ? flags.join(" / ") : "\u00a0";

    var tl = s.tailer || {};
    $("consent").hidden = !!tl.consented;
    $("consent-no").hidden = !tl.consented;
    $("consent-path").textContent = tl.path || "Client.txt (not found yet - start the game once)";
    $("events-empty").textContent = D.emptyText(!!tl.consented);
    showReading();
    renderEvents(s.recent_events || []);
    renderTrades(s.trade_requests || []);
    tick();
  }

  function showPill(id, p) { setPill($(id), p.state, p.glyph, p.word); }

  function showReading() {
    showPill("reading", D.readingView(snap ? snap.tailer : null, linkLive));
  }

  function setLink(event) {
    linkLive = event === "open";
    if (linkLive) { everLive = true; }
    showPill("link", D.linkView(event, everLive));
    showReading();
  }

  function api(method, path, body) {
    var opts = { method: method, headers: { "X-AL-Token": token }, cache: "no-store" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    });
  }

  function consent(yes) {
    var err = $("consent-error"); // a polite live region; empty hides nothing
    err.textContent = "";
    api("POST", "/api/consent", { consent: yes }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      err.textContent = "Your choice was not saved. Try again.";
      console.warn("consent failed: " + e.message);
    });
  }

  function connect() {
    if (!token) {
      setLink("notoken");
      return;
    }
    loadLayout();
    api("GET", "/api/state").then(render).catch(function () {
      if (!linkLive) { setLink("error"); }
    });
    if (es) { es.close(); }
    es = new EventSource("/events?token=" + encodeURIComponent(token));
    es.addEventListener("open", function () { setLink("open"); tick(); });
    es.addEventListener("error", function () { setLink("error"); });
    es.addEventListener("state", function (m) {
      try { render(JSON.parse(m.data)); } catch (e) { /* ignore a bad frame */ }
    });
  }

  function start() {
    $("consent-yes").addEventListener("click", function () { consent(true); });
    $("consent-no").addEventListener("click", function () { consent(false); });
    document.addEventListener("visibilitychange", tick);
    $("trade-clear").addEventListener("click", function () { dismissTrade(null); });
    $("layout-form").addEventListener("change", saveLayout);
    $("layout-form").addEventListener("submit", function (e) { e.preventDefault(); });
    ["layout-scale", "layout-opacity"].forEach(function (id) {
      $(id).addEventListener("input", function () {
        $(id + "-out").textContent = Math.round(parseFloat($(id).value) * 100) + "%";
      });
    });
    // The two timers advance once a second; nothing else moves.
    ticker = setInterval(tick, 1000);
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
