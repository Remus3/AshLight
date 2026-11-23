/* AshLight dashboard: the version lines and the update line
   (REL-UPDATE-NOTICE-UI; findings F-055, F-077, DEP-16; decisions 0013 and
   0065, ruling Q-21). UMD like web/runs.js: CommonJS for node --test
   (app/test/updates.test.js), window.ALUpdates for the page; web/fmt.js
   gives pad.

   The core makes every fact: the snapshot's `update` block
   (server/al/updates.py view(): installed, latest, newer, notes, the
   releases_url it builds from config/public_repo.json, checked_at, error,
   ack_needed, plus staged and click_only), the "snapshot" Checks row's
   "at" (the game data fetch time) and the "web_data" Checks row (off or
   not). This file only words them in Settings > About and data
   (#update-box):
   - 'AshLight <version>' and 'Game data from <date>' on two lines;
   - one update line: up to date, a newer version (the Settings tab then
     says "update", never a window, never a toast), ready to install, web
     data off, the wording not acknowledged yet, or no answer last time;
   - the releases link: the core's releases_url, a plain https link to a
     host of web/tc.js LINK_HOSTS (config/link_hosts.json), opened only on
     the player's click in their own browser; none while the address is
     empty. This file holds no host literal of its own;
   - the newest 3 versions, each one entry capped at 3 lines of 47
     characters (the target design's Full text rule), inside the same
     rail block, which web/rail.js pages like any other: no fold.
   An opt-in given before the wording that names the update check makes no
   update request until the player acknowledges it once: the one OK
   button posts {ack: <wording version>} to POST /api/web-data (the
   version the core gave in GET /api/web-data). Ticking the Settings box
   sends the same version (web/panels/webdata.js; ackBody() is that rule).
   No timer, no clipboard, no live region, no request but that click. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(common ? require("./fmt.js") : root.ALFmt);
  if (common) {
    module.exports = api;
  } else {
    root.ALUpdates = api;
  }
}(typeof self !== "undefined" ? self : this, function (F) {
  "use strict";

  var TAB = "settings";
  var MARK = "update";
  var FIX = "fix";           // web/checks.js's mark wins over ours
  var LINE_MAX = 94;         // a Settings line: at most 2 lines of 47
  var NOTE_MAX = 141;        // a version entry: at most 3 lines of 47
  var NOTES_MAX = 3;
  var VERSION_RE = /^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[0-9A-Za-z.-]{1,12})?$/;
  var DATE_RE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
  var URL_RE = /^https:\/\/([a-z0-9-]+(?:\.[a-z0-9-]+)+)\/[A-Za-z0-9._\/-]{1,200}$/;

  var LINK_TEXT = "AshLight releases on GitHub";
  var ACK_LABEL = "OK, check for updates";
  var T = {
    current: "AshLight is up to date. It checks once a day.",
    first: "AshLight checks once a day for a new version.",
    off: "Update checks are off while web data is off.",
    none: "This copy doesn't check for updates.",
    ack: "Web data now also checks once a day for a new AshLight and installs it " +
      "at a later start.",
    error: "The last update check got no answer. AshLight tries again tomorrow.",
    acked: "Saved. AshLight checks for updates from now on.",
    notSaved: "Not saved. Try again."
  };

  function str(v) { return typeof v === "string" ? v : ""; }

  function version(v) { return VERSION_RE.test(str(v)) ? v : ""; }

  /* An epoch (s) as a local "YYYY-MM-DD"; "" when it is not a time. */
  function day(ts) {
    if (typeof ts !== "number" || !isFinite(ts) || ts <= 0) { return ""; }
    var d = new Date(ts * 1000);
    return d.getFullYear() + "-" + F.pad(d.getMonth() + 1) + "-" + F.pad(d.getDate());
  }

  function cut(text, max) {
    text = str(text).replace(/\s+/g, " ").trim();
    return text.length > max ? text.slice(0, max - 3).replace(/\s+$/, "") + "..." : text;
  }

  /* The releases link, or null: a plain https URL on a listed host. */
  function releasesLink(url, hosts) {
    var m = URL_RE.exec(str(url));
    if (!m || !Array.isArray(hosts) || hosts.indexOf(m[1]) < 0) { return null; }
    return { href: url, text: LINK_TEXT };
  }

  /* The newest 3 versions as one line each: "<version>, <date>: <text>". */
  function notes(list) {
    if (!Array.isArray(list)) { return []; }
    var out = [];
    for (var i = 0; i < list.length && out.length < NOTES_MAX; i++) {
      var n = list[i] || {};
      var v = cut(n.version, 20);
      var text = cut(n.text, NOTE_MAX);
      if (!v || !text) { continue; }
      var head = v + (DATE_RE.test(str(n.date)) ? ", " + n.date : "") + ": ";
      out.push(cut(head + text, NOTE_MAX));
    }
    return out;
  }

  /* The view of the update block. update: the snapshot's `update` (or
     null); webData: true / false for the web-data switch, null when not
     known yet; hosts: the link host list (web/tc.js LINK_HOSTS).
     -> {show, version, state, line, ack, link, mark, notes} */
  function model(update, webData, hosts) {
    var u = update && typeof update === "object" ? update : null;
    var empty = { show: false, version: "", state: "none", line: "", ack: false,
      link: null, mark: "", notes: [] };
    if (!u || !version(u.installed)) { return empty; }
    var installed = version(u.installed);
    var link = releasesLink(u.releases_url, hosts);
    var latest = version(u.latest);
    var staged = version(u.staged);
    var state;
    var line;
    if (!link && !u.releases_url) {
      state = "none"; line = T.none;
    } else if (webData === false) {
      state = "off"; line = T.off;
    } else if (u.ack_needed === true) {
      state = "ack"; line = T.ack;
    } else if (u.newer === true && latest) {
      if (staged && staged === latest) {
        state = "staged";
        line = "AshLight " + latest + " is downloaded. It installs at a later start.";
      } else if (u.click_only === true) {
        state = "newer";
        line = "AshLight " + latest + " is out. See what changed on GitHub.";
      } else {
        state = "newer";
        line = "AshLight " + latest + " is out. It installs by itself at a later start.";
      }
    } else if (u.error) {
      state = "error"; line = T.error;
    } else if (typeof u.checked_at === "number" && isFinite(u.checked_at)) {
      state = "current"; line = T.current;
    } else {
      state = "first"; line = T.first;
    }
    return {
      show: true,
      version: "AshLight " + installed,
      state: state,
      line: cut(line, LINE_MAX),
      ack: state === "ack",
      link: state === "none" ? null : link,
      mark: state === "newer" || state === "staged" ? MARK : "",
      notes: notes(u.notes)
    };
  }

  /* 'Game data from <date>' from the "snapshot" Checks row, "" without one. */
  function dataLine(snap) {
    var rows = snap && snap.diag && Array.isArray(snap.diag.checks) ? snap.diag.checks : [];
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] && rows[i].id === "snapshot") {
        var d = day(rows[i].at);
        return d ? "Game data from " + d : "";
      }
    }
    return "";
  }

  /* The web-data switch from the "web_data" Checks row: false while it is
     off, true otherwise, null with no row. */
  function webDataOn(snap) {
    var rows = snap && snap.diag && Array.isArray(snap.diag.checks) ? snap.diag.checks : [];
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] && rows[i].id === "web_data") { return rows[i].status !== "off"; }
    }
    return null;
  }

  /* The checks of the page that failed (web/checks.js marks "fix" then). */
  function failed(snap) {
    var n = snap && snap.diag ? snap.diag.failed : 0;
    return typeof n === "number" && n > 0;
  }

  /* The wording version from a GET / POST /api/web-data answer, or null. */
  function wording(doc) {
    var w = doc && doc.wording_version;
    return typeof w === "number" && isFinite(w) && w > 0 && Math.floor(w) === w ? w : null;
  }

  /* The body of the Settings box's change: {enabled}, plus the wording
     version as "ack" when the player ticks it on and the core named one
     (the sentence beside the box names the update check). */
  function ackBody(want, doc) {
    var body = { enabled: want === true };
    var w = wording(doc);
    if (body.enabled && w !== null) { body.ack = w; }
    return body;
  }

  function hostList(opts) {
    if (opts && Array.isArray(opts.hosts)) { return opts.hosts; }
    var tc = typeof self !== "undefined" && self.ALTc ? self.ALTc : null;
    return tc && Array.isArray(tc.LINK_HOSTS) ? tc.LINK_HOSTS : [];
  }

  function tabs(opts) {
    if (opts && opts.tabs) { return opts.tabs; }
    return typeof self !== "undefined" && self.ALTabs ? self.ALTabs : null;
  }

  /* Fill #update-box from a snapshot. opts (tests): {hosts, tabs}.
     Returns the model. The Settings tab mark is set after web/checks.js's
     paint (app.js calls this from the checks entry), and only while no
     check needs a fix, so "fix" always wins. */
  function paint(doc, snap, opts) {
    var box = doc.getElementById("update-box");
    var m = model(snap && snap.update, webDataOn(snap), hostList(opts));
    var data = dataLine(snap);
    var t = tabs(opts);
    if (t && typeof t.mark === "function" && !failed(snap)) { t.mark(doc, TAB, m.mark); }
    if (!box) { return m; }
    var key = JSON.stringify([m, data]);
    if (box.getAttribute("data-key") === key) { return m; }
    box.setAttribute("data-key", key);
    box.hidden = !m.show;
    doc.getElementById("update-version").textContent = m.version;
    var dl = doc.getElementById("update-data");
    dl.textContent = data;
    dl.hidden = !data;
    doc.getElementById("update-line").textContent = m.line;
    doc.getElementById("update-ack-row").hidden = !m.ack;
    var a = doc.getElementById("update-link");
    if (m.link) {
      a.setAttribute("href", m.link.href);
      a.textContent = m.link.text;
    } else {
      a.removeAttribute("href");
    }
    doc.getElementById("update-link-row").hidden = !m.link;
    var list = doc.getElementById("update-notes");
    list.textContent = "";
    m.notes.forEach(function (text) {
      var li = doc.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    doc.getElementById("update-notes-box").hidden = !m.notes.length;
    return m;
  }

  /* The OK click: one POST {ack} with the wording version the core gave
     (getDoc() returns the last GET /api/web-data answer). saved(doc) shows
     the answer in the web data section. */
  function wire(doc, api, getDoc, saved) {
    var btn = doc.getElementById("update-ack");
    var said = doc.getElementById("update-said");
    if (!btn || !said) { return; }
    var busy = false;
    btn.addEventListener("click", function () {
      if (busy) { return; }
      var w = wording(typeof getDoc === "function" ? getDoc() : null);
      if (w === null) { said.textContent = T.notSaved; return; }
      busy = true;
      said.textContent = "";
      Promise.resolve().then(function () {
        return api("POST", "/api/web-data", { ack: w });
      }).then(function (answer) {
        said.textContent = T.acked;
        if (typeof saved === "function") { saved(answer); }
      }, function () {
        said.textContent = T.notSaved;
      }).then(function () { busy = false; });
    });
  }

  return { model: model, paint: paint, wire: wire, ackBody: ackBody, wording: wording,
    dataLine: dataLine, webDataOn: webDataOn, releasesLink: releasesLink, notes: notes,
    day: day, TEXT: T, MARK: MARK, TAB: TAB, LINK_TEXT: LINK_TEXT, ACK_LABEL: ACK_LABEL,
    LINE_MAX: LINE_MAX, NOTE_MAX: NOTE_MAX };
}));
