/* AshLight dashboard panel: the version line (footer and Settings > About
   and data) and the game-data credits, moved out of web/app.js by
   TEST-WEB-PANELS-C2 (finding F-135; research 0047 R4 (c)).

   TC-SNAP-UI: the full game-data credits in Settings > About and data
   (PLAY-TD-21B-SETTINGS-ABOUT moved them out of the footer), read on
   every connect, so a snapshot made by the build shows up without a
   click. RUN-BUILD-STAMP-UI: the same read fills the footer's version
   line and the About and data version, so a core restart on a new build
   shows it.

   The blocks moved verbatim: versionText (BUILD-STAMP) and loadDataCredit.
   The panel's wire hands loadDataCredit to app.js's connect() as a late
   read (host.onConnect(fn, true)), which runs it right after the rates,
   where connect() called it before the move: the same GET /api/version,
   in the same place. What the panel shares with the page ($, api) is
   reached through window.ALApp.host, which app.js sets before start().

   No clipboard, no timer, no new request, no live region.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel, versionText, footerParts}; in the page the file
   registers itself with window.ALApp (web/registry.js) as "version",
   order 270, after the other settings panels (it only queues its read).
   The core links this file at the panels marker of index.html
   (TEST-WEB-ASSEMBLE). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALApp.register(api.panel(function () { return root.ALApp.host; }));
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "version";
  var ORDER = 270;

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api;
  var D = null; // web/status.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("version: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api;
    D = window.ALDash;
    bound = true;
  }

  /* BUILD-STAMP:begin (app/test/about.test.js runs this function alone and
     holds it to app/about.js versionLine; keep it self-contained ES5)
     RUN-BUILD-STAMP-UI (F-027, decision 0082 part 2): the version line
     from the core's build string '<x.y.z>[+<12 hex>][.dev]':
     "Version 0.1.0, build 0123456789ab", ", dev" while hot reload is on;
     "" for anything else. */
  function versionText(doc) {
    var raw = doc && (typeof doc.build === "string" ? doc.build : doc.version);
    if (typeof raw !== "string" || raw.length > 100) { return ""; }
    var plus = raw.indexOf("+");
    var ver = plus < 0 ? raw : raw.slice(0, plus);
    if (!/^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/.test(ver)) { return ""; }
    var meta = plus < 0 ? [] : raw.slice(plus + 1).split(".");
    var commit = "";
    var dev = false;
    for (var i = 0; i < meta.length; i++) {
      if (meta[i] === "dev" && !dev) { dev = true; continue; }
      if (/^[0-9a-f]{12}$/.test(meta[i]) && !commit && !dev) { commit = meta[i]; continue; }
      return "";
    }
    return "Version " + ver + (commit ? ", build " + commit : "") + (dev ? ", dev" : "");
  }

  /* WEB-PLAY-FOOT-ONE-ROW: the footer's short form of the same line, so
     the footer stays one row at 1024 px: the build cut to its first 7 hex,
     set apart in a fixed-width face (web/app.css .foot-hash); the full
     12-hex line stays in Settings > About and data. {head, hash, tail},
     hash "" when the line names no build; null when versionText says
     nothing. */
  function footerParts(doc) {
    var text = versionText(doc);
    if (!text) { return null; }
    var m = /^(Version [^,]+, build )([0-9a-f]{12})(.*)$/.exec(text);
    if (!m) { return { head: text, hash: "", tail: "" }; }
    return { head: m[1], hash: m[2].slice(0, 7), tail: m[3] };
  }
  /* BUILD-STAMP:end */

  /* the footer line from footerParts: text nodes only, no markup */
  function fillFooter(line, parts) {
    while (line.firstChild) { line.removeChild(line.firstChild); }
    line.appendChild(document.createTextNode(parts.head));
    if (parts.hash) {
      var hash = document.createElement("span");
      hash.className = "foot-hash";
      hash.textContent = parts.hash;
      line.appendChild(hash);
    }
    if (parts.tail) { line.appendChild(document.createTextNode(parts.tail)); }
  }

  function loadDataCredit() {
    api("GET", "/api/version").then(function (doc) {
      var text = D.dataCreditText(doc);
      var p = $("data-credit");
      p.textContent = text;
      p.hidden = !text;
      $("credits").hidden = !text; // the About and data group around it
      var ver = versionText(doc);
      if (ver) {
        fillFooter($("build-line"), footerParts(doc));
        $("build-line").hidden = false;
        $("about-version").textContent = ver;
      }
    }).catch(function () { /* keep the last line; the next connect retries */ });
  }

  /* The registry entry; getHost is read on the first wire, when web/app.js
     has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () {
        var host = getHost();
        bind(host);
        host.onConnect(loadDataCredit, true);
      }
    };
  }

  return { name: NAME, order: ORDER, panel: panel, versionText: versionText,
           footerParts: footerParts };
}));
