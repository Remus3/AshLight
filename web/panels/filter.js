/* AshLight dashboard panel: the loot filter download and merge on Build
   and items' loot filter page, moved out of web/app.js by
   TEST-WEB-PANELS-C2 (finding F-135; research 0047 R4 (c)).

   UTIL-FILTER (decision 0031) and UTIL-FILTER-MERGE (decision 0033): on
   the player's click or file pick only; the browser saves the result
   where the player picks. AshLight writes no file itself.

   The blocks moved verbatim: downloadFilter and mergeFilter, plus the
   "filter" entry's wire. What the panel shares with the page ($, token,
   setLine) is reached through window.ALApp.host, which app.js sets before
   start(). The merge itself is web/filtermerge.js.

   The same two requests as before (GET /api/filter, and the merge's POST
   through web/filtermerge.js) and the download link's one revoke timer;
   no clipboard, no live region.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "filter", order 210: the name and
   order app.js gave this entry before the move, so the wire order of
   today's page is kept. The core links this file at the panels marker of
   index.html (TEST-WEB-ASSEMBLE). */
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

  var NAME = "filter";
  var ORDER = 210; // app.js gave "filter" 210 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, token, setLine;
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("filter: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; token = host.token; setLine = host.setLine;
    bound = true;
  }

  /* UTIL-FILTER (decision 0031): on the player's click, fetch the snippet
     and hand it to the browser as a download; the player picks where it
     goes. AshLight writes no file itself. */
  function downloadFilter() {
    var said = $("filter-said");
    /* UX-B5-CARDS: no live region (the page keeps its 12); the focused
       button's name carries the answer; most screen readers read it on
       this click (best effort, audit 0004 U22) */
    var btn = $("filter-download");
    var tell = function (text) {
      setLine(said, text);
      setLine($("filter-merge-said"), "");  /* one outcome line for the page */
      btn.setAttribute("aria-label", text ? "Download ashlight.filter (" + text + ")"
        : "Download ashlight.filter");
    };
    tell("");
    fetch("/api/filter", { headers: { "X-AL-Token": token }, cache: "no-store" })
      .then(function (r) {
        if (!r.ok) {
          tell("Can't make the filter. Try again.");
          return null;
        }
        return r.text();
      }).then(function (text) {
        if (text === null) { return; }
        var url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
        var a = document.createElement("a");
        a.href = url;
        a.download = "ashlight.filter";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        tell(text.indexOf("\nShow\n") >= 0
          ? "Sent to your browser's downloads. Move it to the game's filter folder."
          : "Sent to your browser's downloads, but your build has no gear bases, so it " +
            "highlights nothing yet.");
      }).catch(function () {
        tell("Can't reach AshLight - is it running?");
      });
  }

  /* UTIL-FILTER-MERGE (decision 0033): picking a file is the player's act;
     the merged copy goes to the browser's downloads. No live region (the
     page keeps its 12): as for downloadFilter, the focused input's name
     carries the answer (best effort, audit 0004 U22). */
  function mergeFilter() {
    var input = $("filter-merge-file");
    var file = input.files && input.files[0];
    window.ALFilterMerge.run(file, {
      fetch: function (url, opts) { return fetch(url, opts); },
      token: token,
      tell: function (text) {
        setLine($("filter-merge-said"), text);
        if (text) { setLine($("filter-said"), ""); }
        if (text) {
          input.setAttribute("aria-label", "Your loot filter file (" + text + ")");
        } else {
          input.removeAttribute("aria-label");
        }
      },
      save: function (blob, name) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      }
    }).then(function () { input.value = ""; });  /* the same file can be picked again */
  }

  function wire() {
    $("filter-download").addEventListener("click", downloadFilter);
    $("filter-merge-file").addEventListener("change", mergeFilter);
  }

  /* The registry entry; getHost is read on the first wire, when web/app.js
     has run (it is the last script). */
  function panel(getHost) {
    return {
      name: NAME,
      order: ORDER,
      wire: function () { bind(getHost()); wire(); }
    };
  }

  return { name: NAME, order: ORDER, panel: panel };
}));
