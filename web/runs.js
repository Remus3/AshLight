/* AshLight dashboard: map runs (UTIL-MAPS) and the death recap
   (UTIL-DEATHS). UMD: CommonJS for node --test (app/test/runs.test.js),
   window.ALRuns for the page. The core folds Client.txt and sends every
   sentence in the snapshot's `maps` and `death_recap` parts
   (server/al/runs.py); this file only formats times and fills the cards.
   No timers of its own, no network. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALRuns = api;
  }
}(typeof self !== "undefined" ? self : this, function (F) {
  "use strict";

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer
     (web/fmt.js). */
  var duration = F.duration;

  /* A missing area level reads as a word, never "null" (design DR-1). */
  function levelText(x) { return Number.isInteger(x) ? String(x) : "unknown"; }

  /* Local clock time of an epoch (s), as the Recent list shows it; ""
     when the time is not a number (web/fmt.js). */
  var clock = F.clock;

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

  /* UTIL-MAP-LADDER: display rows of a ladder view (highest level first),
     every number as the core counted it. */
  function ladderRows(lad) {
    return ((lad && lad.levels) || []).map(function (r) {
      return { level: levelText(r.area_level), maps: deathsCount(r.maps),
        deaths: deathsCount(r.deaths), median: r.median_text || "--:--",
        levelups: deathsCount(r.level_ups) };
    });
  }

  function paintLadder(doc, prefix, lad) {
    var wrap = doc.getElementById(prefix);
    if (!wrap) { return; }
    var rows = ladderRows(lad);
    // the empty sentence shows until the first map (design rule 9)
    wrap.hidden = !lad;
    doc.getElementById(prefix + "-table").hidden = rows.length === 0;
    doc.getElementById(prefix + "-text").textContent =
      (lad && (rows.length ? lad.text : lad.empty_text)) || "";
    var tbody = doc.getElementById(prefix + "-rows");
    tbody.textContent = "";
    rows.forEach(function (r) {
      var tr = doc.createElement("tr");
      var th = cell(doc, "th", r.level);
      th.setAttribute("scope", "row");
      tr.appendChild(th);
      [r.maps, r.deaths, r.median, r.levelups].forEach(function (v) {
        tr.appendChild(cell(doc, "td", v, "mono"));
      });
      tbody.appendChild(tr);
    });
  }

  /* full: a new snapshot (rebuild both cards); otherwise the 1 s tick
     moves only the open map's time. */
  function paint(doc, snap, now, full) {
    if (!snap) { return; }
    paintMaps(doc, snap.maps || null, snap.now, now, full);
    if (full) {
      paintDeaths(doc, snap.death_recap || null);
      var maps = snap.maps || {};
      paintLadder(doc, "ladder", maps.ladder || null);
      paintLadder(doc, "ladder-all", maps.ladder_all || null);
    }
  }

  return { duration: duration, levelText: levelText, clock: clock,
    liveTime: liveTime, mapRows: mapRows, mapsSummary: mapsSummary,
    deathLines: deathLines, recapFoot: recapFoot, ladderRows: ladderRows,
    paint: paint };
}));
