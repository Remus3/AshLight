/* AshLight dashboard: add AshLight's blocks to the player's own loot filter
   (UTIL-FILTER-MERGE, decision 0033). UMD: CommonJS for node --test
   (app/test/filtermerge.test.js), window.ALFilterMerge for the page.
   The player picks their .filter file with the browser's file input; the
   browser reads it and sends the bytes to the core (POST /api/filter-merge,
   token header), which prepends AshLight's Show blocks and answers with the
   combined copy. The browser then saves it as a download. Nothing is
   written into a game folder, the player's own file is never changed, and
   nothing runs without the player picking a file. No timers.
   TC-FILTER-ONE-CONTROL (F-158): this file pick is the card's one primary
   filter control; the plain ashlight.filter download is a small link beside
   it, and the core dates AshLight's section and names its prices' league. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALFilterMerge = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_BYTES = 2 * 1024 * 1024;  /* lootfilter.MAX_MERGE_BYTES */
  var FALLBACK_NAME = "filter-ashlight.filter";
  var TOO_BIG = "That file is over 2 MB, so it is not a loot filter. Pick your own .filter file.";
  var FAILED = "Nothing was saved and your filter was not changed. Try picking it again.";
  var OFFLINE = "Can't reach AshLight - is it running?";

  /* The download name from the core's Content-Disposition header; the core
     already reduced it to letters, digits, space . _ ( ) -. */
  function fileName(disposition) {
    var m = /filename="([A-Za-z0-9 ._()-]+)"/.exec(String(disposition || ""));
    return m ? m[1] : FALLBACK_NAME;
  }

  /* The sentence for a refused merge: the core's own plain words when it
     sent them (it never echoes the file), else a generic retry line. */
  function refusedText(status, body) {
    if (status === 413) { return TOO_BIG; }
    if ((status === 400) && body && typeof body.error === "string" && body.error) {
      return body.error;
    }
    return FAILED;
  }

  function savedText(name) {
    return "Saved " + name + " to your downloads. Your own filter is unchanged. Move the " +
      "new file to the game's filter folder, then pick it in the game's options.";
  }

  /* One merge for the picked file. env: {fetch, token, save(blob, name),
     tell(text)}. Returns a promise; never throws. */
  function run(file, env) {
    if (!file) { return Promise.resolve(); }
    env.tell("");
    if (typeof file.size === "number" && file.size > MAX_BYTES) {
      env.tell(TOO_BIG);
      return Promise.resolve();
    }
    var sent = false;
    return file.arrayBuffer().then(function (buf) {
      sent = true;
      return env.fetch("/api/filter-merge?name=" + encodeURIComponent(file.name || ""), {
        method: "POST",
        headers: { "X-AL-Token": env.token, "Content-Type": "application/octet-stream" },
        body: buf,
        cache: "no-store"
      });
    }).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (b) { return b; }, function () { return null; })
          .then(function (b) { env.tell(refusedText(r.status, b)); });
      }
      var name = fileName(r.headers.get("Content-Disposition"));
      return r.blob().then(function (blob) {
        env.save(blob, name);
        env.tell(savedText(name));
      });
    }).catch(function () {
      env.tell(sent ? OFFLINE : FAILED);
    });
  }

  return { run: run, fileName: fileName, refusedText: refusedText, savedText: savedText,
           MAX_BYTES: MAX_BYTES, TOO_BIG: TOO_BIG, FAILED: FAILED, OFFLINE: OFFLINE };
}));
