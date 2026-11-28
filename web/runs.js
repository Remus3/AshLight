/* AshLight dashboard: the Maps and Deaths cards of the Run grid (UTIL-MAPS,
   UTIL-DEATHS; PLAY-TD-20A-RUN-GRID, plan 03 section 4, TD-20). UMD:
   CommonJS for node --test (app/test/runs.test.js), window.ALRuns for the
   page. The core folds Client.txt and sends every sentence in the
   snapshot's `maps` and `death_recap` parts (server/al/runs.py); this file
   only formats times and writes the rows. No timers of its own, no
   network.

   Both cards are fixed cells of the Run grid and their lists page at 10
   rows (8 compact) through web/acts.js's pager and page helpers (fill,
   wireCard). Maps: this session's maps, the open one first; pages: the
   summary line, the map ladder of this session and of all saved sessions
   (UTIL-MAP-LADDER), and the maps by name (UTIL-MAP-STATS). Deaths: the death recap, newest first, with the zone
   of most deaths under it. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt, function () {
    return common ? require("./acts.js") : root.ALActs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALRuns = api;
    /* TEST-WEB-PANELS-C2 (F-135): the Maps card registers itself
       (web/registry.js) as "runs", order 120, the name and order web/app.js
       gave it. UTIL-MAPS: the open map's time counts up while the player
       is in it. */
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register({
        name: "runs",
        order: 120,
        paint: function (s) { api.paint(document, s, root.ALApp.host.serverNow(), true); },
        tick: function (s, now) { api.paint(document, s, now, false); }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function (F, actsLib) {
  "use strict";

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer
     (web/fmt.js). */
  var duration = F.duration;

  /* A missing area level reads as a word, never "null" (design DR-1). */
  function levelText(x) { return Number.isInteger(x) ? String(x) : "unknown"; }

  /* Local clock time of an epoch (s), as the Recent list shows it; ""
     when the time is not a number (web/fmt.js). */
  var clock = F.clock;

  /* A count as a bare number ("0" when it is not one). */
  function deathsCount(n) { return String(Number.isInteger(n) ? n : 0); }

  /* "1 death", "2 deaths"; "0 deaths" when the count is not a number. */
  function plural(n, word) {
    var k = Number.isInteger(n) ? n : 0;
    return k + " " + word + (k === 1 ? "" : "s");
  }

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

  /* "Savannah (now): level 66, 5:05, 1 death" */
  function mapText(r) {
    return r.name + (r.note ? " (" + r.note + ")" : "") + ": level " + r.level + ", " +
      r.time + ", " + plural(parseInt(r.deaths, 10), "death");
  }

  /* The summary page: average, maps per hour (UTIL-MAPRUN), deaths in
     maps; each sentence from the core, empty ones skipped. */
  function mapsSummary(maps) {
    if (!maps) { return ""; }
    return [maps.avg_text, maps.rate_text, maps.deaths_text]
      .filter(function (t) { return !!t; }).join(" ");
  }

  /* The death recap lines, newest first, as the core wrote them. */
  function deathLines(recap) {
    return ((recap && recap.recent) || []).map(function (r) { return r.text; });
  }

  /* One death row: the core's sentence in the list (zone and level
     first); the whole text (title, Full text page) adds the local time. */
  function deathText(row) {
    var t = clock(row.at);
    return row.text + (t ? " At " + t + "." : "");
  }

  /* The line under the list: the worst zone, then how many deaths came
     before AshLight started reading (UX-NEW-CARDS). */
  function recapFoot(recap) {
    if (!recap) { return ""; }
    return [recap.worst_text, recap.earlier_text]
      .filter(function (t) { return !!t; }).join(" ");
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

  /* "Level 66: 3 maps, 1 death, median 6:30, 2 level-ups" */
  function ladderText(r) {
    return "Level " + r.level + ": " + plural(parseInt(r.maps, 10), "map") + ", " +
      plural(parseInt(r.deaths, 10), "death") + ", median " + r.median + ", " +
      plural(parseInt(r.levelups, 10), "level-up");
  }

  /* UTIL-MAP-STATS (research 0064 G5): the per-map table, from the saved
     sessions while run history is on, else this session's. Each row is
     the core's sentence plus the local time of its last run (design 0001
     rule 8: a dashboard time is local clock time, dated when older). */
  function byMap(maps) {
    if (!maps) { return null; }
    var all = maps.ladder_all && maps.ladder_all.by_map;
    return all || (maps.ladder && maps.ladder.by_map) || null;
  }

  function byMapText(a, nowMs) {
    var ok = typeof a.last_at === "number" && isFinite(a.last_at);
    var t = ok ? F.clockDated(a.last_at, nowMs) : "";
    return a.text + (t ? ", last run " + t : "");
  }

  function paintByMap(doc, maps, now) {
    var A = actsLib();
    if (!doc.getElementById("bymap")) { return; }
    var st = byMap(maps);
    var areas = (st && st.areas) || [];
    var text = (st && (areas.length ? st.text : st.empty_text)) || "";
    A.showText(doc, "bymap-text", text);
    var t = doc.getElementById("bymap-text");
    if (t) {
      if (text) { t.setAttribute("title", text); } else { t.removeAttribute("title"); }
    }
    var nowMs = typeof now === "number" && isFinite(now) ? now * 1000 : undefined;
    A.fill(doc, "bymap-rows", "maps by name", areas.filter(function (a) {
      return a && typeof a.text === "string" && a.text;
    }).map(function (a) { return { text: byMapText(a, nowMs) }; }));
  }

  function paintMaps(doc, maps, snapNow, now, full) {
    var A = actsLib();
    if (!doc.getElementById("maps-rows")) { return; }
    var rows = mapRows(maps, snapNow, now);
    if (full) { A.wireCard(doc, "mapsbox"); }
    A.fill(doc, "maps-rows", "maps", rows.map(function (r) { return { text: mapText(r) }; }));
    if (!full) { return; }
    A.showText(doc, "maps-empty", rows.length ? "" : (maps && maps.empty_text) || "");
    var sum = mapsSummary(maps);
    // the summary page never stands empty: the empty sentence until a map
    A.showText(doc, "maps-summary", sum || (maps && maps.empty_text) || "");
  }

  /* One ladder page: its sentence (whole in title) above the rows; the
     empty sentence until the first map (design rule 9). */
  function paintLadder(doc, prefix, lad, label) {
    var A = actsLib();
    var wrap = doc.getElementById(prefix);
    if (!wrap) { return; }
    var rows = ladderRows(lad);
    var text = (lad && (rows.length ? lad.text : lad.empty_text)) || "";
    var t = doc.getElementById(prefix + "-text");
    A.showText(doc, prefix + "-text", text);
    if (t) {
      if (text) { t.setAttribute("title", text); } else { t.removeAttribute("title"); }
    }
    A.fill(doc, prefix + "-rows", label, rows.map(function (r) { return { text: ladderText(r) }; }));
  }

  function paintDeaths(doc, recap) {
    var A = actsLib();
    if (!doc.getElementById("deaths-list")) { return; }
    A.wireCard(doc, "deathsbox");
    var recent = (recap && recap.recent) || [];
    A.fill(doc, "deaths-list", "deaths", recent.map(function (row) {
      return { text: deathText(row), line: row.text };
    }));
    A.showText(doc, "deaths-empty", recent.length ? "" : (recap && recap.empty_text) || "");
    var foot = recapFoot(recap);
    A.showText(doc, "deaths-worst", foot);
    var w = doc.getElementById("deaths-worst");
    if (w) {
      if (foot) { w.setAttribute("title", foot); } else { w.removeAttribute("title"); }
    }
  }

  /* full: a new snapshot (rebuild both cards); otherwise the 1 s tick
     moves only the open map's time. */
  function paint(doc, snap, now, full) {
    if (!snap) { return; }
    paintMaps(doc, snap.maps || null, snap.now, now, full);
    if (full) {
      paintDeaths(doc, snap.death_recap || null);
      var maps = snap.maps || {};
      paintLadder(doc, "ladder", maps.ladder || null, "map levels this session");
      paintLadder(doc, "ladder-all", maps.ladder_all || null, "map levels of all saved sessions");
      paintByMap(doc, snap.maps || null, snap.now);
      // the saved sessions page exists only while run history is on
      var open = doc.getElementById("ladder-all-open");
      if (open) {
        open.hidden = !maps.ladder_all;
        // run history went off while its page showed: back to the list
        var box = doc.getElementById("mapsbox");
        if (open.hidden && box && box.getAttribute("data-shown") === "saved") {
          var back = box.querySelector("[data-card-back]");
          if (back) { back.click(); }
        }
      }
    }
  }

  return { duration: duration, levelText: levelText, clock: clock, plural: plural,
    liveTime: liveTime, mapRows: mapRows, mapText: mapText, mapsSummary: mapsSummary,
    deathLines: deathLines, deathText: deathText, recapFoot: recapFoot,
    ladderRows: ladderRows, ladderText: ladderText, byMap: byMap, byMapText: byMapText,
    paint: paint };
}));
