/* AshLight dashboard: the Theme choice (PLAY-TD-04B-THEME-CHOICE; TD-04,
   F-086; plan 03 section 7).

   The page ships dark for every browser: <html data-theme="dark"> in
   web/index.html, so nothing needs a click (ZERO-CLICK). One optional
   choice in Settings, Appearance and tools, changes it: Dark (the
   default), Follow Windows or Light. The choice is the "theme" key of the
   core's config (GET / POST /api/theme, token-gated like every route) and
   travels with the settings backup (server/al/settingsio.py).

   apply() writes the attribute: "dark" or "light", or no attribute for
   Follow Windows, so the kit's prefers-color-scheme block decides
   (/tokens.css; web/theme.css sets the matching color-scheme). The desktop
   client reads the same choice and sets its native theme
   (app/client/window.js), so Follow Windows follows Windows there too.
   The overlay is always dark and never reads this.

   UMD like web/keptchecks.js: CommonJS for node --test, window.ALTheme in
   the page, registered on ALRegions as a helper (region null) whose wire()
   gets ctx.api. Its tag sits with the Settings scripts, before
   web/slots.js and web/regions.js (the region files' run from slots.js on
   is pinned by app/test/regions.test.js), so it registers on
   DOMContentLoaded when the registry is not there yet; a helper registered
   after ALRegions.start() is wired at once with the same ctx. No timer, no clipboard, no live region of its own: the answer line
   beside the select is plain text the select points at, and a failed
   save is also said in the page's one shared polite line, the header's
   #tab-news, through ALTabs.say (THM-2; a new region would breach the
   6-region cap of tests/test_a11y.py). After a settings
   import (the import's answer line #settings-said changes to words) the
   choice is read again, so an imported theme shows at once. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var api = factory(root, function () {
    return common ? require("./tabs.js") : root.ALTabs;
  });
  if (common) {
    module.exports = api;
  } else {
    root.ALTheme = api;
    var done = false;
    var register = function () {
      if (!done && root.ALRegions && typeof root.ALRegions.register === "function") {
        done = true;
        root.ALRegions.register(api.spec);
      }
    };
    register();
    if (!done && root.document && typeof root.document.addEventListener === "function") {
      root.document.addEventListener("DOMContentLoaded", register);
    }
  }
}(typeof self !== "undefined" ? self : this, function (root, tabs) {
  "use strict";

  var NAME = "theme";
  var CHOICES = ["dark", "system", "light"]; // settingsio.THEMES; "system" = Follow Windows
  var DEFAULT = "dark";
  var PATH = "/api/theme";
  var NOT_SAVED = "Your choice was not saved. Try again.";
  var IDS = { pick: "theme-pick", said: "theme-said", importSaid: "settings-said",
    news: "tab-news" };

  /* THM-2: say a line in the page's shared polite region (ALTabs.say on
     the header's #tab-news, IDS.news); a page without tabs says nothing. */
  function say(doc, text) {
    var t = tabs();
    if (t && typeof t.say === "function") { t.say(doc, text); }
  }

  /* A known choice, else the default. */
  function clean(v) {
    return CHOICES.indexOf(v) >= 0 ? v : DEFAULT;
  }

  /* The data-theme value of a choice: "dark", "light", or null (no
     attribute) for Follow Windows. */
  function attrFor(choice) {
    var c = clean(choice);
    return c === "system" ? null : c;
  }

  /* The choice in a core answer ({"theme": ...}); the default otherwise. */
  function themeOf(answer) {
    return answer && typeof answer === "object" ? clean(answer.theme) : DEFAULT;
  }

  /* Put a choice on the root element; returns the cleaned choice. */
  function apply(doc, choice) {
    var c = clean(choice);
    var el = doc && doc.documentElement;
    if (el) {
      var a = attrFor(c);
      if (a === null) { el.removeAttribute("data-theme"); } else { el.setAttribute("data-theme", a); }
    }
    return c;
  }

  /* Wire the select: read the stored choice once, save a change, read
     again after a settings import. ctx.api(method, path, body) is the
     page's token fetch (web/app.js). */
  function wire(doc, ctx) {
    var call = ctx && typeof ctx.api === "function" ? ctx.api : null;
    if (!doc || !call) { return; }
    var pick = doc.getElementById(IDS.pick);
    var said = doc.getElementById(IDS.said);
    var saved = DEFAULT; // the last choice the core confirmed

    function show(choice) {
      saved = apply(doc, choice);
      if (pick) { pick.value = saved; }
    }

    function read() {
      return Promise.resolve().then(function () { return call("GET", PATH); })
        .then(function (answer) { show(themeOf(answer)); }, function () { /* stays as shown */ });
    }

    read();
    if (pick) {
      pick.addEventListener("change", function () {
        var want = clean(pick.value);
        if (said) { said.textContent = ""; }
        var news = doc.getElementById(IDS.news); // a stale failure of ours goes too
        if (news && news.textContent === NOT_SAVED) { say(doc, ""); }
        apply(doc, want); // at once; the answer confirms it
        return Promise.resolve().then(function () { return call("POST", PATH, { theme: want }); })
          .then(function (answer) { show(themeOf(answer)); }, function () {
            show(saved);
            if (said) { said.textContent = NOT_SAVED; }
            say(doc, NOT_SAVED); // heard as well as shown (THM-2)
          });
      });
    }
    var importSaid = doc.getElementById(IDS.importSaid);
    var view = doc.defaultView || root;
    var Observer = view && typeof view.MutationObserver === "function" ? view.MutationObserver : null;
    if (importSaid && Observer) {
      new Observer(function () {
        if (importSaid.textContent) { read(); }
      }).observe(importSaid, { childList: true, characterData: true, subtree: true });
    }
  }

  var spec = { name: NAME, region: null, wire: wire };

  return { spec: spec, wire: wire, apply: apply, attrFor: attrFor, themeOf: themeOf,
    clean: clean, CHOICES: CHOICES, DEFAULT: DEFAULT, PATH: PATH, NOT_SAVED: NOT_SAVED, IDS: IDS };
}));
