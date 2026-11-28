/* AshLight dashboard panel: the web data setting (DATA-NINJA-UI / PRICE-1-UI,
   decision 0016), moved out of web/app.js by TEST-WEB-PANELS-B (finding
   F-135; research 0047 R4 (c)). The one web_data opt-in of decision 0013
   stays the player's switch: it is saved only on the player's change of
   it, and nothing here turns it on. The contact field (DATA-CONTACT-UI)
   saves on the player's Save and the league picker (DATA-LEAGUE-PICKER-UI)
   on a pick. The first read (GET /api/web-data) runs from connect()
   through the host's onConnect, as before the move.

   The block moved verbatim: webOn, webBusy, webDoc, fillWebData,
   loadWebData, webDataSaved, saveContact, saveLeague and saveWebData,
   plus the "webdata" entry's wire. The edits: the page's snap and the
   rates doc are read through the host's getSnap() and getRatesDoc(). The
   rates (Prices card) stay in web/app.js; on its wire this panel fills the
   host's webLink with fill, saved and state, so app.js's rates follow the
   switch and the loaded build's link offer reaches webDataSaved.

   Changes and clicks only: no clipboard, no new timer, no new request.

   UMD like web/fmt.js: CommonJS for node --test (app/test/panels.test.js)
   exports {name, order, panel}; in the page the file registers itself with
   window.ALApp (web/registry.js) as "webdata", order 250: the name and order
   app.js gave this entry before the move, so the wire order of today's
   page is kept. The core links this file at the panels marker of
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

  var NAME = "webdata";
  var ORDER = 250; // app.js gave "webdata" 250 before the move

  /* the page's shared helpers (window.ALApp.host, set by web/app.js) */
  var $, api, getSnap, getRatesDoc, renderRates, renderPrice, loadRates, webLink, onConnect;
  var T = null; // web/tc.js: pure view helpers
  var P = null; // web/prices.js: pure view helpers
  var bound = false;

  function bind(host) {
    if (bound) { return; }
    if (!host || typeof host.$ !== "function") {
      throw new TypeError("webdata: no page host (web/app.js sets ALApp.host)");
    }
    $ = host.$; api = host.api; getSnap = host.getSnap; getRatesDoc = host.getRatesDoc;
    renderRates = host.renderRates; renderPrice = host.renderPrice;
    loadRates = host.loadRates; webLink = host.webLink; onConnect = host.onConnect;
    T = window.ALTc;
    P = window.ALPrices;
    bound = true;
  }

  var webOn = false;
  var webBusy = false;

  var webDoc = null; // DATA-LEAGUE-PICKER-UI: the last full GET / POST /api/web-data answer
  // REL-UPDATE-NOTICE-UI: the opt-in wording version of the last answer that named one
  var wordingSeen = null;
  // UX-WEBDATA-SENTENCE-TRUE: the opt-in sentence of the last answer that held one
  var sentenceSeen = "";
  var NO_SENTENCE = "Can't load what web data does. Open AshLight again from the tray.";

  /* The switch, the contact field (DATA-CONTACT-UI: never prefilled;
     DATA-CONTACT-CLEAR: it stays once a contact is set, with Clear and
     the saved note) and the league picker. A partial doc (only web_data,
     from /api/rates) leaves the field and the picker. */
  function fillWebData(doc) {
    var v = P.webDataView(doc);
    var w = doc ? doc.wording_version : null;
    if (typeof w === "number" && w > 0 && Math.floor(w) === w) { wordingSeen = w; }
    // UX-WEBDATA-SENTENCE-TRUE: the core's opt-in sentence for this copy
    var said = T.optInSentence(doc);
    if (said) {
      sentenceSeen = said;
      $("webdata-sentence").textContent = said;
    }
    webOn = v.on;
    $("webdata-on").checked = v.on;
    // never ticked on blind: with no sentence read the switch can only go off
    $("webdata-on").disabled = !sentenceSeen && !v.on;
    if (v.contact.show !== null) {
      $("webdata-contact-row").hidden = !v.contact.show;
      // a page fixture that lacks the Clear button or the note leaves them
      var clr = $("webdata-contact-clear");
      var note = $("webdata-contact-note");
      if (clr) { clr.hidden = !v.contact.clear; }
      if (note) { note.textContent = v.contact.note; }
      // UX-46-P3 (P3-2): a release build shows no field, label or Save
      ["webdata-contact-label", "webdata-contact", "webdata-contact-save"].forEach(function (id) {
        var n = $(id);
        if (n) { n.hidden = !v.contact.input; }
      });
    }
    if (doc && Array.isArray(doc.leagues)) {
      webDoc = doc;
      var lv = P.leagueView(doc);
      var sel = $("webdata-league");
      sel.textContent = "";
      lv.options.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o.value;
        opt.textContent = o.text;
        sel.appendChild(opt);
      });
      sel.value = lv.selected;
      $("webdata-league-note").textContent = lv.from;
      $("webdata-league-row").hidden = !lv.show;
      if (getRatesDoc()) { renderRates(); }
    }
    return v;
  }

  function loadWebData() {
    api("GET", "/api/web-data").then(function (doc) {
      $("webdata-status").textContent = fillWebData(doc).status;
      renderPrice(getSnap() ? getSnap().price : null, true);
    }).catch(function () {
      $("webdata-status").textContent = "Can't load the web data setting. Is AshLight running?";
      // UX-WEBDATA-SENTENCE-TRUE: no list was read, so none is shown and
      // the switch cannot be ticked on beside an empty line
      if (!sentenceSeen) {
        $("webdata-sentence").textContent = NO_SENTENCE;
        if (!webOn) { $("webdata-on").disabled = true; }
      }
    });
  }

  /* After a saved web-data choice (the Settings switch or the
     TC-LINK-RECOVER confirm): the switch, its status and the prices. */
  function webDataSaved(doc) {
    fillWebData(doc);
    $("webdata-status").textContent = P.savedText(webOn, doc);
    renderPrice(getSnap() ? getSnap().price : null, true);
    loadRates();
  }

  /* DATA-CONTACT-CLEAR (design DCC-1): a failed contact Save or Clear is
     written in #webdata-status (not a live region) and said once on the
     header's polite #tab-news through ALTabs.say, as web/autostart.js and
     web/panels/weights.js do; a page without tabs says only the line. */
  var NOT_SAVED = "Not saved. Try again.";
  var NOT_CLEARED = "Not cleared. Try again.";

  function failed(text) {
    $("webdata-status").textContent = text;
    var t = window.ALTabs;
    if (t && typeof t.say === "function" && typeof document !== "undefined") {
      t.say(document, text);
    }
  }

  /* DATA-CONTACT-UI: the Save click (the form's submit). The value goes
     only to POST /api/web-data {contact}; the answer says contact_set,
     never the value. The field is cleared after a save; a refused value
     stays so the player can fix it. */
  function saveContact() {
    var box = $("webdata-contact");
    var value = box.value.trim();
    if (webBusy) { return; }
    if (!value) {
      $("webdata-status").textContent = "Type a contact first, then click Save.";
      return;
    }
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    api("POST", "/api/web-data", { contact: value }).then(function (doc) {
      box.value = "";
      fillWebData(doc);
      $("webdata-status").textContent = P.contactSavedText(doc);
      renderPrice(getSnap() ? getSnap().price : null, true);
      loadRates();
    }).catch(function (e) {
      if (e && e.message === "HTTP 400") {
        $("webdata-status").textContent = P.CONTACT_REFUSED;
      } else {
        failed(NOT_SAVED);
      }
    }).then(function () { webBusy = false; });
  }

  /* DATA-CONTACT-CLEAR (finding DCD-3): the Clear click posts only
     {contact: ""}; the core removes the key and answers contact_set false,
     never a value. Clear hides itself on success, so focus moves to the
     field (the player may type a new one). */
  function clearContact() {
    if (webBusy) { return; }
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    api("POST", "/api/web-data", { contact: "" }).then(function (doc) {
      var box = $("webdata-contact");
      box.value = "";
      fillWebData(doc);
      var said = P.contactClearedText(doc);
      if (said === NOT_CLEARED) { failed(said); } else { $("webdata-status").textContent = said; }
      var clr = $("webdata-contact-clear");
      if (!clr || clr.hidden) {
        // UX-46-P3: with no field (release build) focus goes to the switch;
        // box.hidden is that signal (set by fillWebData from contactView.input)
        var row = $("webdata-contact-row");
        ((row && row.hidden) || box.hidden ? $("webdata-on") : box).focus();
      }
      renderPrice(getSnap() ? getSnap().price : null, true);
      loadRates();
    }).catch(function () {
      failed(NOT_CLEARED);
    }).then(function () { webBusy = false; });
  }

  /* DATA-LEAGUE-PICKER-UI: a pick saves at once (POST /api/web-data
     {league}; "" follows poe.ninja's current league again). Makes no
     request to poe.ninja: the next due price update uses it. */
  function saveLeague() {
    var sel = $("webdata-league");
    if (webBusy) { return; }
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    api("POST", "/api/web-data", { league: sel.value }).then(function (doc) {
      fillWebData(doc);
      $("webdata-status").textContent = P.leagueSavedText(doc);
    }).catch(function (e) {
      sel.value = P.leagueView(webDoc).selected; // back to what is really saved
      $("webdata-status").textContent = e && e.message === "HTTP 400"
        ? P.LEAGUE_REFUSED : "Not saved. Try again.";
    }).then(function () { webBusy = false; });
  }

  /* The form's change event: the switch saves at once, a league pick
     saves at once, typing in the contact field waits for Save. */
  function saveWebData(e) {
    var target = e && e.target;
    if (target && target.id === "webdata-league") { saveLeague(); return; }
    if (target && target.id === "webdata-contact") { return; }
    if (webBusy) { return; }
    var want = $("webdata-on").checked;
    webBusy = true;
    $("webdata-status").textContent = "Saving...";
    // REL-UPDATE-NOTICE-UI (ruling Q-21): ticking the box on beside the
    // sentence that names the update check acknowledges that wording: the
    // wording version the core gave (GET /api/web-data) goes along as "ack"
    var body = { enabled: want };
    if (want && wordingSeen !== null) { body.ack = wordingSeen; }
    api("POST", "/api/web-data", body).then(function (doc) {
      webDataSaved(doc);
    }).catch(function () {
      $("webdata-on").checked = webOn; // back to what is really saved
      $("webdata-status").textContent = "Not saved. Try again.";
    }).then(function () { webBusy = false; });
  }

  function wire() {
    // TC-LINK-RECOVER / UX-WEBDATA-SENTENCE-TRUE: Settings shows the core's
    // opt-in sentence (fillWebData, from the first GET); the confirm shows
    // the same text through webLink.state().sentence; until it is read the
    // switch cannot be ticked on
    $("webdata-on").disabled = true;
    $("webdata-form").addEventListener("change", saveWebData);
    // DATA-CONTACT-UI: Save (or Enter in the contact field) submits the form
    $("webdata-form").addEventListener("submit", function (e) { e.preventDefault(); saveContact(); });
    // DATA-CONTACT-CLEAR: Clear is a plain button (never submits the form);
    // its click is read on the form, like the change event above
    $("webdata-form").addEventListener("click", function (e) {
      if (e && e.target && e.target.id === "webdata-contact-clear") { clearContact(); }
    });
    webLink.fill = fillWebData;
    webLink.saved = webDataSaved;
    webLink.state = function () {
      return { on: webOn, busy: webBusy, doc: webDoc, sentence: sentenceSeen };
    };
    // UX-WEBDATA-SENTENCE-TRUE: the build link offer's one read of the
    // setting when no sentence was read yet (the same GET as loadWebData)
    webLink.read = function () {
      return api("GET", "/api/web-data").then(function (doc) {
        $("webdata-status").textContent = fillWebData(doc).status;
        return doc;
      });
    };
    onConnect(loadWebData);
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
