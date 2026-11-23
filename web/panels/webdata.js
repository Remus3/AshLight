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

  /* The switch, the contact field (DATA-CONTACT-UI: shown only until a
     contact is set; never prefilled) and the league picker. A partial doc
     (only web_data, from /api/rates) leaves the field and the picker. */
  function fillWebData(doc) {
    var v = P.webDataView(doc);
    var w = doc ? doc.wording_version : null;
    if (typeof w === "number" && w > 0 && Math.floor(w) === w) { wordingSeen = w; }
    webOn = v.on;
    $("webdata-on").checked = v.on;
    if (v.contact.show !== null) { $("webdata-contact-row").hidden = !v.contact.show; }
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
      $("webdata-status").textContent = e && e.message === "HTTP 400"
        ? P.CONTACT_REFUSED : "Not saved. Try again.";
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
    // TC-LINK-RECOVER: Settings shows the one opt-in sentence the confirm shows
    $("webdata-sentence").textContent = T.WEB_DATA_OPT_IN;
    $("webdata-form").addEventListener("change", saveWebData);
    // DATA-CONTACT-UI: Save (or Enter in the contact field) submits the form
    $("webdata-form").addEventListener("submit", function (e) { e.preventDefault(); saveContact(); });
    webLink.fill = fillWebData;
    webLink.saved = webDataSaved;
    webLink.state = function () { return { on: webOn, busy: webBusy, doc: webDoc }; };
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
