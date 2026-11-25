/* AshLight dashboard: region I, the item card (PLAY-TD-16A-ITEMCARD; plan 03
   TD-16 and section 3.4, F-025, F-151; design 0001 sections 6 and 9).

   The card of the last item-key press stays on Play until the next press
   (the twin of the overlay's timed card). Every row has its fixed place,
   so nothing moves while the card fills (F-059 staged fill and the F-060
   keep-or-vendor sentence arrive as data in the same rows):
   - head: the verdict word with its glyph at 28 px / 700 ("[+] Upgrade",
     "[-] Not an item"), then the item name at 20 px (ellipsis, full text
     in title). The head is the region's one polite, atomic live region.
   - sentence: 2 rows (the reason first).
   - compare: the label ("vs <worn item> (+1 other slot)") and 5 rows.
   - price row: the value (20 px) and its source (14 px, muted).
   - links: at most 2 (Trade search, Upgrade search). They are plain https
     links the player opens in their own browser (decision 0017: a URL
     only, never a trade call).
   - actions: at most 2. "Details" is rendered only once #evalbox sits in
     a tab other than Play (after PLAY-LEGACY-OUT-2) and shows that tab;
     "I wear this" only while snap.play.item.can_wear is set (TC cluster,
     F-070) and posts /api/wear (no clipboard read: the core files the
     last checked item).
   Empty (no press yet): 3 muted rows that teach the press with the bound
   item key (snap.hotkeys.eval.key; with none bound, the words "the item
   check key", never a default the client may not have bound: F-026) and
   say that this check stays here (the F-151 correction; PLAY-FIT-G5-TOTALS
   cut the overlay card time from this card to meet design 0001 G5).
   The links and the actions share one row (at most 2 of each).

   The words come composed from the core (snap.play.item, server/al/
   playcards.py item_view). One exception: the item's own asking price
   (snap.eval.value.price, the Note price of MATH-VALUE) is the price row's
   value when the item carries one, because play.item has no field for it
   yet; "Asking price: 5 exalted" (the amount and currency are data).

   No timer, no network but the player's own "I wear this" click, no
   clipboard, never ALTabs.notify (the legacy path keeps that until
   PLAY-LEGACY-OUT). Registers {name: itemcard, region: i, retires:
   [i-eval]} with web/regions.js. UMD like web/tabs.js: CommonJS for
   node --test, window.ALItemCard in the page. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALItemCard = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NAME = "itemcard";
  var REGION = "i";
  var RETIRES = ["i-eval"];
  var SENTENCE_ROWS = 2;
  var COMPARE_ROWS = 5;
  var MAX_LINKS = 2;
  var ROW_CHARS = 36;         // plan 03 3.4: the item sentence row budget
  var NO_KEY = "the item check key";  // OVL-KEYS-WEB: no bound key, no key named
  var COPY_KEY = "Ctrl+C";    // the game's own item copy (the player presses it)
  var CARD_TIMES = [20, 60, 200];    // TD-18 card time choices; 20 s by default
  var DEFAULT_CARD_S = 20;
  var EVALBOX_ID = "evalbox";
  var DETAILS_LABEL = "Details";
  var WEAR_LABEL = "I wear this";
  var WEAR_PATH = "/api/wear";
  var EMPTY_WORD = "Nothing checked yet";
  var EMPTY_GLYPH = "[ ]";
  var EMPTY_ROWS = 3;
  var STAYS = "The check stays here.";
  var LINK_HINT = " (opens in your browser)";
  // kit state of play.item -> the word's tone (design 0001 section 6:
  // glyph and word carry the verdict, the colour is never alone)
  var TONES = { done: "ok", "needs-operator": "warn" };

  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function str(v) { return typeof v === "string" ? v : ""; }
  function arr(v) { return Array.isArray(v) ? v : []; }

  /* Word-wrap a text into rows of at most `width` characters (a word
     longer than a row stands alone); at most `rows` rows. */
  function wrapRows(text, width, rows) {
    var out = [];
    str(text).split(/\s+/).filter(Boolean).forEach(function (w) {
      var last = out.length - 1;
      if (last >= 0 && out[last].length + 1 + w.length <= width) {
        out[last] += " " + w;
      } else {
        out.push(w);
      }
    });
    return out.slice(0, rows);
  }

  /* The bound item key (snap.hotkeys.eval.key: the core sets it only
     while the client registered it), else "" (none is bound). */
  function itemKey(snap) {
    var hk = isObj(snap) && isObj(snap.hotkeys) ? snap.hotkeys : null;
    var ev = hk && isObj(hk.eval) ? hk.eval : null;
    return ev ? str(ev.key) : "";
  }

  /* The overlay card time in seconds (TD-18: 20, 60 or 200; else 20). */
  function cardTime(snap) {
    var lay = isObj(snap) && isObj(snap.overlay_layout) ? snap.overlay_layout : null;
    var s = lay ? lay.card_s : null;
    return CARD_TIMES.indexOf(s) >= 0 ? s : DEFAULT_CARD_S;
  }

  /* The 3 rows of the empty card: 2 teach the press, 1 says the check
     stays here (F-151; PLAY-FIT-G5-TOTALS cut the overlay card's time from
     this card: Settings names it). */
  function emptyRows(snap) {
    var teach = "Press " + COPY_KEY + " on an item, then " + (itemKey(snap) || NO_KEY) + ".";
    return wrapRows(teach, ROW_CHARS, 2).concat([STAYS]);
  }

  function num(n) {
    return Math.round(n) === n ? String(n) : String(Math.round(n * 100) / 100);
  }

  /* The item's own Note price (snap.eval.value.price), or "" when it has
     none: "Asking price: 5 exalted" / "Buyout price: 2 divine". */
  function askingPrice(snap) {
    var ev = isObj(snap) && isObj(snap.eval) ? snap.eval : null;
    var v = ev && isObj(ev.value) ? ev.value : null;
    var p = v && isObj(v.price) ? v.price : null;
    if (!p || typeof p.amount !== "number" || !isFinite(p.amount) || p.amount <= 0) { return ""; }
    var cur = str(p.name) || str(p.currency);
    if (!cur) { return ""; }
    return (p.kind === "b/o" ? "Buyout price: " : "Asking price: ") + num(p.amount) + " " + cur;
  }

  function safeLinks(links) {
    var out = [];
    arr(links).forEach(function (l) {
      if (out.length >= MAX_LINKS || !isObj(l)) { return; }
      var label = str(l.label), url = str(l.url);
      if (label && url.indexOf("https://") === 0) { out.push({ label: label, url: url }); }
    });
    return out;
  }

  function padList(list, n, blank) {
    var out = list.slice(0, n);
    while (out.length < n) { out.push(blank); }
    return out;
  }

  /* snap -> what I shows, or null before the first snapshot. */
  function model(snap) {
    if (!isObj(snap)) { return null; }
    var play = isObj(snap.play) ? snap.play : null;
    var it = play && isObj(play.item) ? play.item : null;
    if (!it) {
      return { kind: "empty", tone: "neutral", glyph: EMPTY_GLYPH, word: EMPTY_WORD, name: "",
        empty: emptyRows(snap), canWear: false };
    }
    var cmp = isObj(it.compare) ? it.compare : {};
    var rows = arr(cmp.rows).map(function (r) {
      return isObj(r) ? { text: str(r.text), value: str(r.value) } : { text: "", value: "" };
    });
    var price = isObj(it.price) ? it.price : {};
    var asking = askingPrice(snap);
    var sentence = arr(it.sentence).filter(function (s) { return typeof s === "string"; });
    return {
      kind: str(it.kind) || "verdict",
      tone: TONES[it.state] || "neutral",
      glyph: str(it.glyph) || "[-]",
      word: str(it.word) || "Not checked",
      name: str(it.name),
      sentence: padList(sentence, SENTENCE_ROWS, ""),
      full: str(it.full) || sentence.join(" "),
      label: str(cmp.label),
      rows: padList(rows, COMPARE_ROWS, { text: "", value: "" }),
      price: asking ? { value: asking, source: "" }
        : { value: str(price.value), source: str(price.source) },
      links: safeLinks(it.links),
      canWear: it.can_wear === true,
      stage: str(it.stage)
    };
  }

  /* The tab id whose panel holds #evalbox when that is not Play, else null
     (then Details is not rendered: the card it would show is right here). */
  function detailsTab(doc) {
    var n = doc && typeof doc.getElementById === "function" ? doc.getElementById(EVALBOX_ID) : null;
    for (var p = n ? n.parentNode : null; p; p = p.parentNode) {
      var id = typeof p.getAttribute === "function" ? p.getAttribute("id") : p.id;
      if (typeof id === "string" && id.indexOf("panel-") === 0 && id.length > 6) {
        return id.slice(6) === "play" ? null : id.slice(6);
      }
    }
    return null;
  }

  function slotOf(doc) {
    if (!doc || typeof doc.querySelector !== "function") { return null; }
    return doc.querySelector('#play-i [data-slot="i"]');
  }

  function el(doc, tag, cls, id) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (id) { n.id = id; }
    return n;
  }

  function blankNodes() {
    return { doc: null, root: null, head: null, glyph: null, wordText: null, name: null,
      body: null, sent: [], label: null, rows: [], pval: null, psrc: null, links: null,
      acts: null, details: null, wear: null, empty: null, emptyRows: [], pvalText: null,
      linkNodes: [] };
  }

  // the region's nodes, made once by wire() (or the first paint)
  var nodes = blankNodes();
  var wired = { tabs: null, api: null };

  function build(doc) {
    if (nodes.doc === doc && nodes.root) { return nodes; }
    var slot = slotOf(doc);
    if (!slot || typeof doc.createElement !== "function") { return null; }
    var n = blankNodes();
    n.doc = doc;
    // the region's slot is the card itself, with no wrapper of its own
    // (PLAY-FIT-G5-TOTALS: design 0001's visible-element budget)
    n.root = slot;
    if ((" " + slot.className + " ").indexOf(" ic ") < 0) {
      slot.className = slot.className ? slot.className + " ic" : "ic";
    }
    slot.id = "ic";
    n.root.hidden = true;
    // head: the one polite, atomic live region (the verdict and the item)
    n.head = el(doc, "p", "ic-head", "ic-head");
    n.head.setAttribute("role", "status");
    n.head.setAttribute("aria-live", "polite");
    n.head.setAttribute("aria-atomic", "true");
    var word = el(doc, "span", "ic-word", "ic-word");
    n.glyph = el(doc, "span", "glyph");
    n.glyph.setAttribute("aria-hidden", "true");
    n.wordText = doc.createTextNode("");
    word.appendChild(n.glyph);
    word.appendChild(doc.createTextNode(" "));
    word.appendChild(n.wordText);
    n.name = el(doc, "span", "ic-name row-title one-line", "ic-name");
    n.head.appendChild(word);
    n.head.appendChild(n.name);
    n.root.appendChild(n.head);
    // the full card's rows, each in its fixed place
    n.body = el(doc, "div", "ic-body", "ic-body");
    for (var i = 0; i < SENTENCE_ROWS; i++) {
      n.sent.push(n.body.appendChild(el(doc, "p", "ic-row ic-sent row-body one-line")));
    }
    n.label = n.body.appendChild(el(doc, "p", "ic-label row-meta muted one-line", "ic-label"));
    var list = n.body.appendChild(el(doc, "ul", "ic-rows"));
    for (var j = 0; j < COMPARE_ROWS; j++) {
      // one row: its stat text first in reading order (it takes the
      // ellipsis), then its points as a text node kept whole on the right
      // (PLAY-A11Y-COMPARE-ORDER: a screen reader says the stat first)
      var li = list.appendChild(el(doc, "li", "ic-cmp-row row-body"));
      var t = li.appendChild(el(doc, "span", "ic-cmp-text one-line"));
      var v = li.appendChild(doc.createTextNode(""));
      n.rows.push({ li: li, text: t, value: v });
    }
    // the price row is one element: its value as text, then its source
    n.pval = n.body.appendChild(el(doc, "p", "ic-price ic-pval row-title one-line", "ic-pval"));
    n.pvalText = n.pval.appendChild(doc.createTextNode(""));
    n.psrc = n.pval.appendChild(el(doc, "span", "ic-psrc row-meta muted", "ic-psrc"));
    // one row holds the links (at most 2) and then the actions (at most 2)
    n.links = n.body.appendChild(el(doc, "p", "ic-links", "ic-links"));
    n.acts = n.links;
    n.details = n.acts.appendChild(el(doc, "button", "ic-details secondary btn-28", "ic-details"));
    n.details.setAttribute("type", "button");
    n.details.textContent = DETAILS_LABEL;
    n.details.hidden = true;
    n.wear = n.acts.appendChild(el(doc, "button", "ic-wear secondary btn-28", "ic-wear"));
    n.wear.setAttribute("type", "button");
    n.wear.textContent = WEAR_LABEL;
    n.wear.hidden = true;
    n.root.appendChild(n.body);
    // the empty card: 3 muted rows that teach the press
    n.empty = el(doc, "div", "ic-empty", "ic-empty");
    for (var k = 0; k < EMPTY_ROWS; k++) {
      n.emptyRows.push(n.empty.appendChild(el(doc, "p", "ic-row row-body muted one-line")));
    }
    n.root.appendChild(n.empty);
    if (typeof n.details.addEventListener === "function") {
      n.details.addEventListener("click", function () { showDetails(doc, wired.tabs); });
      n.wear.addEventListener("click", function () { wear(wired.api, n.wear); });
    }
    nodes = n;
    return nodes;
  }

  /* Details: show the tab that holds #evalbox (no tab focus). */
  function showDetails(doc, tabs) {
    var id = detailsTab(doc);
    if (id && tabs && typeof tabs.show === "function") { tabs.show(doc, id, false); }
    return id;
  }

  /* I wear this: the player's click files the last checked item as worn
     (POST /api/wear, no body text: the core uses the last check; never a
     clipboard read). The button rests until the next state push. */
  function wear(apiFn, button) {
    if (typeof apiFn !== "function") { return false; }
    if (button) { button.disabled = true; }
    try {
      var p = apiFn("POST", WEAR_PATH, {});
      if (p && typeof p.then === "function") {
        p.then(null, function () { if (button) { button.disabled = false; } });
      }
    } catch (e) {
      if (button) { button.disabled = false; }
      return false;
    }
    return true;
  }

  function setText(n, text) { if (n.textContent !== text) { n.textContent = text; } }
  function setAttr(n, k, v) { if (n.getAttribute(k) !== v) { n.setAttribute(k, v); } }
  function setTitle(n, text) {
    if (text) { setAttr(n, "title", text); } else if (n.getAttribute("title") !== null) {
      n.removeAttribute("title");
    }
  }
  function show(n, on) { if (n.hidden !== !on) { n.hidden = !on; } }

  function paintLinks(n, links) {
    var doc = n.doc;
    var key = links.map(function (l) { return l.label + "\n" + l.url; }).join("\n");
    if (n.links.getAttribute("data-key") === key) { return; }
    n.links.setAttribute("data-key", key);
    // only the links are replaced; the action buttons after them stay
    n.linkNodes.forEach(function (a) { n.links.removeChild(a); });
    n.linkNodes = [];
    links.forEach(function (l) {
      var a = el(doc, "a", "ic-link");
      a.setAttribute("href", l.url);
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
      a.setAttribute("aria-label", l.label + LINK_HINT);
      a.textContent = l.label;
      n.links.insertBefore(a, n.details);
      n.linkNodes.push(a);
    });
  }

  /* Paint I from one snapshot (each state push). Idempotent: a node is
     touched only when its text or attribute changes, so the live head
     speaks only when the verdict or the item changes. */
  function paint(doc, snap) {
    var m = model(snap);
    var n = build(doc);
    if (!n) { return null; }
    if (!m) {
      show(n.root, false);
      return null;
    }
    var empty = m.kind === "empty";
    setAttr(n.root, "data-kind", m.kind);
    setAttr(n.root, "data-tone", m.tone);
    setAttr(n.root, "data-stage", m.stage || "");
    setText(n.glyph, m.glyph);
    setText(n.wordText, m.word);
    setText(n.name, m.name);
    setTitle(n.name, m.name);
    show(n.name, !!m.name);
    show(n.body, !empty);
    show(n.empty, empty);
    if (empty) {
      n.emptyRows.forEach(function (r, i) { setText(r, m.empty[i] || ""); });
      show(n.details, false);
      show(n.wear, false);
      show(n.root, true);
      return m;
    }
    n.sent.forEach(function (r, i) {
      setText(r, m.sentence[i]);
      setTitle(r, m.sentence[i] ? m.full : "");
    });
    setText(n.label, m.label);
    setTitle(n.label, m.label);
    n.rows.forEach(function (r, i) {
      var row = m.rows[i];
      setText(r.text, row.text);
      setTitle(r.li, row.text);
      setText(r.value, row.value);
    });
    setText(n.pvalText, m.price.value);
    setTitle(n.pval, m.price.value);
    setText(n.psrc, m.price.source);
    show(n.psrc, !!m.price.source);
    paintLinks(n, m.links);
    var tab = detailsTab(doc);
    show(n.details, !!tab);
    show(n.wear, m.canWear && typeof wired.api === "function");
    if (!m.canWear) { n.wear.disabled = false; }
    show(n.root, true);
    return m;
  }

  function wire(doc, ctx) {
    wired.tabs = ctx && ctx.tabs ? ctx.tabs : null;
    wired.api = ctx && typeof ctx.api === "function" ? ctx.api : null;
    build(doc);
  }

  /* Tests only: forget the nodes made for an earlier document. */
  function reset() {
    nodes = blankNodes();
    wired.tabs = null;
    wired.api = null;
  }

  var spec = {
    name: NAME,
    region: REGION,
    retires: RETIRES.slice(),
    wire: wire,
    paint: function (doc, snap) { paint(doc, snap); }
  };

  return {
    NAME: NAME, REGION: REGION, RETIRES: RETIRES, NO_KEY: NO_KEY,
    DEFAULT_CARD_S: DEFAULT_CARD_S, DETAILS_LABEL: DETAILS_LABEL, WEAR_LABEL: WEAR_LABEL,
    EMPTY_WORD: EMPTY_WORD, ROW_CHARS: ROW_CHARS,
    model: model, itemKey: itemKey, cardTime: cardTime, emptyRows: emptyRows,
    askingPrice: askingPrice, wrapRows: wrapRows, detailsTab: detailsTab,
    showDetails: showDetails, wear: wear, paint: paint, wire: wire, reset: reset, spec: spec
  };
}));
