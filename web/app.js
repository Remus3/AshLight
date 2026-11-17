/* AshLight dashboard. Vanilla JS, no framework, no CDN, no inline script.
   The per-start token arrives in the URL fragment (#token=...), is kept in
   sessionStorage and sent as X-AL-Token (fetch) or ?token= (EventSource,
   which cannot set headers). Every text from the log goes in via
   textContent, never innerHTML. */
(function () {
  "use strict";

  var KEY = "al.token";
  var token = readToken();
  var snap = null;
  var offset = 0; // client clock minus server clock, seconds
  var renderedVersion = -1;
  var es = null;
  var ticker = null;

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

  function tick() {
    if (!snap || document.hidden) { return; }
    var now = serverNow();
    $("zone-time").textContent = snap.zone_entered_at ? duration(now - snap.zone_entered_at) : "--:--";
    $("session").textContent = duration(now - snap.session_started_at);
  }

  function kindOf(row) {
    if (row.trade) { return "trade"; }
    if (row.type === "whisper_in") { return "from"; }
    if (row.type === "whisper_out") { return "to"; }
    if (row.type === "death") { return "death"; }
    if (row.type === "level_up") { return "level"; }
    if (row.type === "scene_changed" || row.type === "area_entered") { return "zone"; }
    return "info";
  }

  function renderEvents(rows) {
    var list = $("events");
    var frag = document.createDocumentFragment();
    for (var i = rows.length - 1; i >= 0; i--) {
      var row = rows[i];
      var li = document.createElement("li");
      var k = kindOf(row);
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

  function render(s) {
    snap = s;
    offset = Date.now() / 1000 - s.now;
    if (s.version === renderedVersion) { tick(); return; }
    renderedVersion = s.version;

    $("zone").textContent = s.zone || "-";
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
    if (tl.reading) {
      setPill($("reading"), "running", "[>]", "reading Client.txt");
    } else if (tl.consented) {
      setPill($("reading"), "blocked", "[#]", tl.path ? "Client.txt waiting" : "Client.txt not found");
    } else {
      setPill($("reading"), "idle", "[-]", "not reading Client.txt");
    }
    renderEvents(s.recent_events || []);
    tick();
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
    var err = $("consent-error");
    err.hidden = true;
    api("POST", "/api/consent", { consent: yes }).then(function (res) {
      render(res.state);
    }).catch(function (e) {
      err.textContent = "Could not record your choice: " + e.message;
      err.hidden = false;
    });
  }

  function connect() {
    if (!token) {
      setPill($("link"), "failed", "[x]", "no token - open the link AshLight printed");
      return;
    }
    api("GET", "/api/state").then(render).catch(function () {
      setPill($("link"), "failed", "[x]", "token rejected or core stopped");
    });
    if (es) { es.close(); }
    es = new EventSource("/events?token=" + encodeURIComponent(token));
    es.addEventListener("open", function () { setPill($("link"), "done", "[+]", "live"); });
    es.addEventListener("error", function () { setPill($("link"), "pending", "[ ]", "reconnecting"); });
    es.addEventListener("state", function (m) {
      try { render(JSON.parse(m.data)); } catch (e) { /* ignore a bad frame */ }
    });
  }

  function start() {
    $("consent-yes").addEventListener("click", function () { consent(true); });
    $("consent-no").addEventListener("click", function () { consent(false); });
    document.addEventListener("visibilitychange", tick);
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
