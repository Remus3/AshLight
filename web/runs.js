/* AshLight dashboard: map runs (UTIL-MAPS) and the death recap
   (UTIL-DEATHS). UMD: CommonJS for node --test (app/test/runs.test.js),
   window.ALRuns for the page. The core folds Client.txt and sends every
   sentence in the snapshot's `maps` and `death_recap` parts
   (server/al/runs.py); this file only formats times and fills the cards.
   No timers of its own, no network. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALRuns = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer. */
  function duration(s) {
    if (s === null || s === undefined || !isFinite(s)) { return "--:--"; }
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
  }

  /* A missing area level reads as a word, never "null" (design DR-1). */
  function levelText(x) { return Number.isInteger(x) ? String(x) : "unknown"; }

  function pad2(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }

  /* Local clock time of an epoch (s), as the Recent list shows it. */
  function clock(ts) {
    if (!isFinite(ts)) { return ""; }
    return pad2(new Date(ts * 1000));
  }

  /* The Deaths column holds the bare count under its header, so the
     narrow table never runs the time into the next cell (UX-NEW-CARDS). */
  function deathsCount(n) { return String(Number.isInteger(n) ? n : 0); }

  /* The open map's time: the snapshot's time plus the seconds since it
     was taken, but only while the player is in the map. */
  function liveTime(cur, snapNow, now) {
    if (!cur) { return null; }
    var t = cur.time_s || 0;
    if (cur.inside && isFinite(now) && isFinite(snapNow)) {
      t += Math.max(0, now - snapNow);
    }
    return t;
  }

  /* Display rows for the Maps card: the open map first, then the finished
     ones, newest first. */
  function mapRows(maps, snapNow, now) {
    if (!maps) { return []; }
    var out = [];
    var cur = maps.current;
    if (cur) {
      out.push({ name: cur.name, level: levelText(cur.area_level),
        time: duration(liveTime(cur, snapNow, now)),
        deaths: deathsCount(cur.deaths),
        note: cur.inside ? "now" : "paused",
        current: true });
    }
    (maps.recent || []).forEach(function (m) {
      out.push({ name: m.name, level: levelText(m.area_level),
        time: duration(m.time_s), deaths: deathsCount(m.deaths),
        note: "", current: false });
    });
    return out;
  }

  /* The line under the Maps table: average, maps per hour (UTIL-MAPRUN),
     deaths in maps; each sentence from the core, empty ones skipped. */
  function mapsSummary(maps) {
    if (!maps) { return ""; }
    return [maps.avg_text, maps.rate_text, maps.deaths_text]
      .filter(function (t) { return !!t; }).join(" ");
  }

  function cell(doc, tag, text, cls) {
    var c = doc.createElement(tag);
    if (cls) { c.className = cls; }
    c.textContent = text;
    return c;
  }

  function paintMaps(doc, maps, snapNow, now, full) {
    var tbody = doc.getElementById("maps-rows");
    if (!tbody) { return; }
    var rows = mapRows(maps, snapNow, now);
    if (!full) {
      var live = tbody.querySelector("tr[data-current]");
      if (live && rows.length && rows[0].current) {
        live.children[2].textContent = rows[0].time;
      }
      return;
    }
    doc.getElementById("maps-table").hidden = rows.length === 0;
    var empty = doc.getElementById("maps-empty");
    empty.hidden = rows.length > 0;
    empty.textContent = (maps && maps.empty_text) || "";
    var summary = mapsSummary(maps);
    var sum = doc.getElementById("maps-summary");
    sum.textContent = summary;
    sum.hidden = !summary;
    tbody.textContent = "";
    rows.forEach(function (r) {
      var tr = doc.createElement("tr");
      if (r.current) { tr.setAttribute("data-current", ""); }
      var th = cell(doc, "th", r.name);
      th.setAttribute("scope", "row");
      if (r.note) { th.appendChild(cell(doc, "span", " (" + r.note + ")", "muted")); }
      tr.appendChild(th);
      tr.appendChild(cell(doc, "td", r.level, "mono"));
      tr.appendChild(cell(doc, "td", r.time, "mono"));
      tr.appendChild(cell(doc, "td", r.deaths, "mono"));
      tbody.appendChild(tr);
    });
  }

  /* The death recap lines, newest first, as the core wrote them. */
  function deathLines(recap) {
    return ((recap && recap.recent) || []).map(function (r) { return r.text; });
  }

  /* The line under the list: the worst zone, then how many deaths came
     before AshLight started reading (UX-NEW-CARDS). */
  function recapFoot(recap) {
    if (!recap) { return ""; }
    return [recap.worst_text, recap.earlier_text]
      .filter(function (t) { return !!t; }).join(" ");
  }

  function paintDeaths(doc, recap) {
    var list = doc.getElementById("deaths-list");
    if (!list) { return; }
    var lines = deathLines(recap);
    list.textContent = "";
    ((recap && recap.recent) || []).forEach(function (row) {
      var li = doc.createElement("li");
      var t = clock(row.at);
      if (t) { li.appendChild(cell(doc, "span", t, "time mono")); li.appendChild(doc.createTextNode(" ")); }
      li.appendChild(doc.createTextNode(row.text));
      list.appendChild(li);
    });
    list.hidden = lines.length === 0;
    var empty = doc.getElementById("deaths-empty");
    empty.textContent = (recap && recap.empty_text) || "";
    empty.hidden = lines.length > 0;
    var worst = doc.getElementById("deaths-worst");
    var foot = recapFoot(recap);
    worst.textContent = foot;
    worst.hidden = !foot;
  }

  /* full: a new snapshot (rebuild both cards); otherwise the 1 s tick
     moves only the open map's time. */
  function paint(doc, snap, now, full) {
    if (!snap) { return; }
    paintMaps(doc, snap.maps || null, snap.now, now, full);
    if (full) { paintDeaths(doc, snap.death_recap || null); }
  }

  return { duration: duration, levelText: levelText, clock: clock,
    liveTime: liveTime, mapRows: mapRows, mapsSummary: mapsSummary,
    deathLines: deathLines, recapFoot: recapFoot, paint: paint };
}));
