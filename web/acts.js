/* AshLight dashboard: act times (per-act splits) and zone levels (HUD-ACT).
   UMD: CommonJS for node --test (app/test/acts.test.js), window.ALActs for
   the page. The core computes the splits and sends every sentence in the
   snapshot's `acts` part (server/al/acts.py); this file only formats times
   and fills the table. No timers, no network. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALActs = api;
  }
}(typeof self !== "undefined" ? self : this, function (F) {
  "use strict";

  /* Seconds as m:ss or h:mm:ss, the same form as the zone timer
     (web/fmt.js). */
  var duration = F.duration;

  /* One display row per split. `now` is server time (s); the open split
     counts up to it, a closed one keeps its own end. */
  function splitRows(acts, now) {
    var splits = (acts && acts.splits) || [];
    if (splits.length === 0) { return []; }
    var start = splits[0].started_at;
    return splits.map(function (s) {
      var end = s.ended_at === null || s.ended_at === undefined ? now : s.ended_at;
      var label = s.label || "Act";
      return {
        label: label,
        note: s.partial ? "partial" : "",
        time: duration(end - s.started_at),
        total: duration(end - start),
        current: !!s.current
      };
    });
  }

  /* UX-NEW-CARDS: a partial row says only "(partial)"; the reason is one
     sentence under the table, so a narrow card never wraps the act name
     over four lines. "" when no row is partial. */
  function partialNote(acts) {
    var splits = (acts && acts.splits) || [];
    var any = splits.some(function (s) { return !!s.partial; });
    var t = (acts && acts.partial_text) || "";
    if (!any || !t) { return ""; }
    return t.charAt(0).toUpperCase() + t.slice(1) + ".";
  }

  /* One display row per zone of the current act: name, level, and a note
     ("you are here", "town"). */
  function zoneRows(acts) {
    return ((acts && acts.zones) || []).map(function (z) {
      var notes = [];
      if (z.here) { notes.push("you are here"); }
      if (z.town) { notes.push("town"); }
      return { name: z.name, level: String(z.level), note: notes.join(", "),
        here: !!z.here };
    });
  }

  /* Heading of the zone level part: "Zone levels in Act 2". */
  function zonesTitle(acts) {
    return acts && acts.zones_act ? "Zone levels in " + acts.zones_act : "Zone levels";
  }

  /* The zone level part's message when there is no table to show: the
     data is missing on this computer, lacks the player's act, or the
     player is not in an act. */
  function zonesEmpty(acts) {
    if (!acts) { return ""; }
    // UX-FIRSTRUN: outside a campaign act the missing download does not
    // matter yet, so the player is not told to run a build step.
    if (!acts.levels && acts.current) { return acts.no_levels_text || ""; }
    if (!acts.levels) { return acts.no_zones_text || ""; }
    if (!acts.zones || acts.zones.length === 0) {
      // UTIL-1.0-FIXTURES: in an act the downloaded table lacks (Acts 5-6
      // before the data refresh) the core says so instead.
      return acts.act_levels_text || acts.no_zones_text || "";
    }
    return "";
  }

  function cell(doc, tag, text, cls) {
    var c = doc.createElement(tag);
    if (cls) { c.className = cls; }
    c.textContent = text;
    return c;
  }

  /* Fill the Act times card. full: rebuild every row (new snapshot);
     otherwise only the open split's times move (the 1 s tick). */
  function paint(doc, acts, now, full) {
    var tbody = doc.getElementById("acts-rows");
    if (!tbody) { return; }
    var rows = splitRows(acts, now);
    if (!full) {
      var live = tbody.querySelector("tr[data-current]");
      var last = rows[rows.length - 1];
      if (live && last && last.current) {
        live.children[1].textContent = last.time;
        live.children[2].textContent = last.total;
      }
      return;
    }
    doc.getElementById("acts-table").hidden = rows.length === 0;
    var empty = doc.getElementById("acts-empty");
    empty.hidden = rows.length > 0;
    empty.textContent = (acts && acts.empty_text) || "";
    tbody.textContent = "";
    rows.forEach(function (r) {
      var tr = doc.createElement("tr");
      if (r.current) { tr.setAttribute("data-current", ""); }
      var th = cell(doc, "th", r.label);
      th.setAttribute("scope", "row");
      var notes = [];
      if (r.current) { notes.push("now"); }
      if (r.note) { notes.push(r.note); }
      if (notes.length) {
        th.appendChild(cell(doc, "span", " (" + notes.join(", ") + ")", "muted"));
      }
      tr.appendChild(th);
      tr.appendChild(cell(doc, "td", r.time, "mono"));
      tr.appendChild(cell(doc, "td", r.total, "mono"));
      tbody.appendChild(tr);
    });
    var pnote = doc.getElementById("acts-note");
    if (pnote) {
      pnote.textContent = partialNote(acts);
      pnote.hidden = !pnote.textContent;
    }

    var title = doc.getElementById("zones-title");
    title.textContent = zonesTitle(acts);
    var zones = zoneRows(acts);
    // First run with no data: one heading-free pair of messages, not a bare
    // "Zone levels" heading over a second empty note (design review HA-6).
    title.hidden = rows.length === 0 && zones.length === 0;
    var zbody = doc.getElementById("zones-rows");
    doc.getElementById("zones-table").hidden = zones.length === 0;
    var zempty = doc.getElementById("zones-empty");
    zempty.textContent = zonesEmpty(acts);
    zempty.hidden = zones.length > 0;
    zbody.textContent = "";
    zones.forEach(function (z) {
      var tr = doc.createElement("tr");
      if (z.here) { tr.className = "here"; }
      var th = cell(doc, "th", z.name);
      th.setAttribute("scope", "row");
      if (z.note) { th.appendChild(cell(doc, "span", " (" + z.note + ")", "muted")); }
      tr.appendChild(th);
      tr.appendChild(cell(doc, "td", z.level, "mono"));
      zbody.appendChild(tr);
    });
    var src = doc.getElementById("zones-source");
    src.textContent = (acts && acts.source) || "";
    src.hidden = !(acts && acts.source);
  }

  return { duration: duration, splitRows: splitRows, zoneRows: zoneRows,
    zonesTitle: zonesTitle, zonesEmpty: zonesEmpty, partialNote: partialNote, paint: paint };
}));
