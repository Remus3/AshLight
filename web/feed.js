/* AshLight dashboard: region T, the feed (PLAY-TD-13-FEED; plan 03 sections
   3.4, 3.5, 8 and 9; design 0001 sections 4 and 6). Five one-line rows:
   every open trade request first, newest on top (all 5 server slots), each
   with its own Dismiss; the free rows take the latest death, level-up and
   zone change (web/slots.js feedRows). A trade is never evicted by an
   event. The rows arrive from the log by themselves; Dismiss is optional.

   Registers {name: feed, region: t, retires: [t-trades]} with
   web/regions.js. Rows come from the core's composed play.feed (server/al/
   playview.py), with the raw trade_requests only for each card's time,
   buyer and stash position. The right-hand segment is composed here on
   every tick: "new" for 60 s after arrival (a text change, no motion), the
   stash tab and position, the age in minutes; an event's local time.

   Region T holds at most 50 words (plan 03 3.4, G5). A row set over that
   drops its optional parts by one fixed ladder, the same for every row,
   until it fits: the stash position, the event times, the item name cut to
   3 words, the stash tab, the item cut to 1 word, the trade age, the event
   sentence cut to 3 words, the item name, the price. A cut ends in "...";
   the full sentence stays in the row's title and in Run > Recent.

   One polite live region (trade status) inside the region says a new
   request once ("New trade request from <buyer>."; never on the first
   paint, a dismiss or an expiry) and a failed dismiss. Moved in from
   web/trades.js (which PLAY-LEGACY-OUT-1 deletes); window.ALTrades is
   never called. A dismiss from the keyboard moves focus to the next row's
   Dismiss, else to the T heading (tabindex -1). ALTabs.notify is not
   called here (the legacy path keeps doing that until PLAY-LEGACY-OUT).
   Dismiss posts /api/trade-dismiss through ctx.api; nothing goes to the
   game. No timers of its own, no clipboard.

   UMD like web/tabs.js: CommonJS for node --test (app/test/feed.test.js),
   window.ALFeed in the page. */
(function (root, factory) {
  "use strict";
  var common = typeof module === "object" && module.exports;
  var slots = common ? require("./slots.js") : root.ALSlots;
  var api = factory(slots);
  if (common) {
    module.exports = api;
  } else {
    root.ALFeed = api;
    if (root.ALRegions && typeof root.ALRegions.register === "function") {
      root.ALRegions.register(api.spec);
    }
  }
}(typeof self !== "undefined" ? self : this, function (S) {
  "use strict";

  var WORD_CAP = 50;      // G5: region T
  var NEW_S = 60;         // the word "new" this long after arrival
  var ROWS = 5;
  var ELLIPSIS = "...";
  var EMPTY = "Nothing yet. Trades and events show here.";
  var NOT_DISMISSED = "Not dismissed. Try again.";
  // a trade row has no tag (PLAY-FIT-G5-TOTALS, design 0001 ruling 2026-11-24:
  // the head "Trades N", the verb, the price and Dismiss already say it)
  var TAGS = { death: "Death", level: "Level", zone: "Zone" };
  var LADDER_TOP = 9;

  function isObj(v) { return v !== null && typeof v === "object"; }
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function str(v) { return typeof v === "string" ? v : ""; }

  /* Words as the Play fit harness counts them (app/test/cdp/play_fit.mjs):
     whitespace-separated tokens that hold a letter or a digit. */
  function words(text) {
    return str(text).split(/\s+/).filter(function (w) { return /[A-Za-z0-9]/.test(w); }).length;
  }

  /* text cut to its first n tokens and "..." (n 0: "..." alone); unchanged
     when it already fits. */
  function cutWords(text, n) {
    var t = str(text).trim();
    if (words(t) <= n) { return t; }
    var toks = t.split(/\s+/);
    var kept = [];
    var count = 0;
    for (var i = 0; i < toks.length && count < n; i++) {
      kept.push(toks[i]);
      if (/[A-Za-z0-9]/.test(toks[i])) { count += 1; }
    }
    return kept.length ? kept.join(" ") + ELLIPSIS : ELLIPSIS;
  }

  /* ---- trade status (moved in from web/trades.js, UX-REVIEW F6) ------- */

  function tradeIds(rows) {
    return (rows || []).map(function (r) { return r.id; });
  }

  /* prevIds: the ids shown before (null before the first paint). rows: the
     open trade requests now. */
  function newTradeSentence(prevIds, rows) {
    if (!prevIds) { return ""; }
    var seen = {};
    prevIds.forEach(function (id) { seen[id] = true; });
    var fresh = (rows || []).filter(function (r) { return !seen[r.id]; });
    if (fresh.length === 0) { return ""; }
    if (fresh.length > 1) { return fresh.length + " new trade requests."; }
    var from = fresh[0].from;
    return from ? "New trade request from " + from + "." : "New trade request.";
  }

  /* Write the polite region (anything with textContent). The same sentence
     twice is cleared first so it is said again; a shrinking set clears the
     old sentence, which no longer matches the list (design review
     2026-11-17 F2). First paint and no change write nothing. Returns true
     when it wrote. */
  function showStatus(el, prevIds, rows) {
    var say = newTradeSentence(prevIds, rows);
    if (say) {
      if (el.textContent === say) { el.textContent = ""; }
      el.textContent = say;
      return true;
    }
    if (prevIds && (rows || []).length < prevIds.length && el.textContent !== "") {
      el.textContent = "";
      return true;
    }
    return false;
  }

  /* ---- the rows (pure) ------------------------------------------------- */

  /* "<buyer> wants <item> - <price>" (state.py _trade_text) split into its
     parts; a lead that does not start with the buyer stays whole. */
  function splitLead(lead, from) {
    var t = str(lead);
    var who = str(from);
    var head = who + " wants ";
    if (!who || t.indexOf(head) !== 0) {
      return { buyer: "", verb: "", item: t, price: "" };
    }
    var rest = t.slice(head.length);
    var cut = rest.lastIndexOf(" - ");
    return cut < 0 ? { buyer: who, verb: "wants", item: rest, price: "" }
      : { buyer: who, verb: "wants", item: rest.slice(0, cut), price: "- " + rest.slice(cut + 3) };
  }

  /* "tab Sale (3,7)" -> {tab: "tab Sale", pos: "(3,7)"} */
  function splitWhere(where) {
    var w = str(where).trim();
    var m = /^(.*\S)\s+(\(\d+,\d+\))$/.exec(w);
    return m ? { tab: m[1], pos: m[2] } : { tab: w, pos: "" };
  }

  function joinRight(parts) {
    return parts.filter(function (p) { return !!p; }).join(", ");
  }

  /* The trade and event models of one paint. snap: the state snapshot;
     now: server seconds; hide: ids dismissed but still in the snapshot. */
  function model(snap, now, hide) {
    var s = isObj(snap) ? snap : {};
    var gone = isObj(hide) ? hide : {};
    var raw = Array.isArray(s.trade_requests) ? s.trade_requests.filter(isObj) : [];
    var byId = {};
    raw.forEach(function (r) { byId[r.id] = r; });
    var play = isObj(s.play) && isObj(s.play.feed) ? s.play.feed : null;
    var list;
    if (play && Array.isArray(play.trades)) {
      // play.feed.trades is newest first; feedRows takes oldest first
      list = play.trades.filter(isObj).slice().reverse().map(function (t) {
        var r = byId[t.id] || {};
        return { id: t.id, at: r.at, from: str(r.from), lead: str(t.lead) || str(r.text),
                 where: str(r.where), title: str(t.title) || str(t.lead) };
      });
    } else {
      list = raw.map(function (r) {
        return { id: r.id, at: r.at, from: str(r.from), lead: str(r.text),
                 where: str(r.where), title: str(r.text) };
      });
    }
    list = list.filter(function (t) { return !gone[t.id]; });
    var feed = S.feedRows(list, play && isObj(play.events) ? play.events : {});
    var t = isNum(now) ? now : null;
    var rows = feed.rows.map(function (row) {
      var it = row.item;
      var age = t !== null && isNum(it.at) ? t - it.at : null;
      var fresh = age !== null && age < NEW_S;
      if (row.kind === "trade") {
        var p = splitLead(it.lead, it.from);
        var w = splitWhere(it.where);
        return { kind: "trade", key: "t" + it.id, id: it.id, tag: "",
                 from: it.from, buyer: p.buyer, verb: p.verb, item: p.item, price: p.price,
                 isNew: fresh, tab: w.tab, pos: w.pos,
                 age: age !== null && age >= NEW_S ? Math.floor(age / 60) + "m" : "",
                 title: it.title + (it.where ? " (" + it.where + ")" : "") };
      }
      return { kind: row.kind, key: "e" + row.kind, tag: str(it.tag) || TAGS[row.kind] || "",
               text: str(it.text), isNew: fresh,
               time: str(it.right).replace(/^new(, )?/, ""), title: str(it.title) || str(it.text) };
    });
    return { head: feed.head, dismissAll: feed.dismissAll, trades: feed.trades, rows: rows,
             open: list };
  }

  /* One row's shown texts at ladder level L (0 = whole). */
  function rowAt(r, L) {
    if (r.kind === "trade") {
      var item = r.item;
      if (L >= 8) { item = cutWords(item, 0); } else if (L >= 5) { item = cutWords(item, 1); }
      else if (L >= 3) { item = cutWords(item, 3); }
      var tab = L >= 4 ? "" : r.tab;
      var pos = L >= 1 ? "" : r.pos;
      var where = tab ? (pos ? tab + " " + pos : tab) : "";
      return { kind: r.kind, key: r.key, id: r.id, tag: r.tag, buyer: r.buyer, verb: r.verb,
               item: item, price: L >= 9 ? "" : r.price,
               right: joinRight([r.isNew ? "new" : "", where, L >= 6 ? "" : r.age]),
               title: r.title, from: r.from };
    }
    return { kind: r.kind, key: r.key, tag: r.tag,
             text: L >= 7 ? cutWords(r.text, 3) : r.text,
             right: joinRight([r.isNew ? "new" : "", L >= 2 ? "" : r.time]), title: r.title };
  }

  function rowWords(r) {
    if (r.kind === "trade") {
      return words(r.tag) + words(r.buyer) + words(r.verb) + words(r.item) + words(r.price) +
        words(r.right) + 1; // its Dismiss
    }
    return words(r.tag) + words(r.text) + words(r.right);
  }

  /* The rows at the first ladder level whose region words fit the budget
     (the words of the head, Dismiss all and the trade status already
     taken off). Returns {level, words, rows}. */
  function compose(rows, budget) {
    var list = Array.isArray(rows) ? rows : [];
    var out = null;
    for (var L = 0; L <= LADDER_TOP; L++) {
      var shown = list.map(function (r) { return rowAt(r, L); });
      var n = shown.reduce(function (a, r) { return a + rowWords(r); }, 0);
      out = { level: L, words: n, rows: shown };
      if (n <= budget) { break; }
    }
    return out;
  }

  /* The whole region view: head, Dismiss all, the composed rows, under the
     50-word cap with `status` (the live region's text) counted. */
  function view(snap, now, hide, status) {
    var m = model(snap, now, hide);
    var fixed = words(m.head) + (m.dismissAll ? 2 : 0) + words(status);
    var c = compose(m.rows, WORD_CAP - fixed);
    return { head: m.head, dismissAll: m.dismissAll, trades: m.trades, open: m.open,
             rows: c.rows, level: c.level,
             words: fixed + (m.rows.length ? c.words : words(EMPTY)),
             empty: m.rows.length === 0 ? EMPTY : "" };
  }

  /* ---- the DOM --------------------------------------------------------- */

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function setText(n, text) {
    if (n.textContent !== text) { n.textContent = text; }
  }

  function setAttr(n, k, v) {
    if (v === null) {
      if (n.getAttribute(k) !== null) { n.removeAttribute(k); }
    } else if (n.getAttribute(k) !== v) {
      n.setAttribute(k, v);
    }
  }

  function setHidden(n, h) {
    if (n.hidden !== h) { n.hidden = h; }
  }

  function create() {
    var ui = null;       // the region's nodes once wired
    var ctx = {};
    var shownIds = null; // trade ids on screen; null until the first paint
    var hide = {};       // dismissed ids the snapshot still holds
    var rowNodes = {};   // key -> row node
    var pendingFocus = null; // {gone: [ids], next: id or null}
    var order = [];      // trade ids in shown order

    function wire(doc, c) {
      ctx = c || {};
      var region = doc.getElementById("play-t");
      var slot = doc.querySelector("#play-t > [data-slot=\"t\"]");
      if (!region || !slot) { return; }
      var h = doc.getElementById("play-t-h");
      // the slot is the feed box itself (PLAY-FIT-G5-TOTALS: no wrapper)
      var box = slot;
      if ((" " + box.className + " ").indexOf(" feed ") < 0) {
        box.className = box.className ? box.className + " feed" : "feed";
      }
      var head = el(doc, "div", "feed-head");
      if (!h) { h = el(doc, "h2"); h.id = "play-t-h"; }
      h.className = "region-h feed-h";
      h.setAttribute("tabindex", "-1");
      head.appendChild(h); // the T heading becomes the visible head line
      var status = el(doc, "p", "feed-status");
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      head.appendChild(status);
      var all = el(doc, "button", "secondary btn-24 feed-all", "Dismiss all");
      all.type = "button";
      all.setAttribute("aria-label", "Dismiss all trade requests");
      all.hidden = true;
      all.addEventListener("click", function (ev) { dismiss(doc, null, keyboard(ev)); });
      head.appendChild(all);
      var list = el(doc, "ol", "feed-rows");
      var empty = el(doc, "p", "feed-empty row-body muted", EMPTY);
      empty.hidden = true;
      box.appendChild(head);
      box.appendChild(list);
      box.appendChild(empty);
      ui = { doc: doc, region: region, h: h, status: status, all: all, list: list, empty: empty };
    }

    /* A click from Enter or Space has no pointer detail. */
    function keyboard(ev) { return !!ev && ev.detail === 0; }

    function now() {
      return typeof ctx.serverNow === "function" ? ctx.serverNow() : Date.now() / 1000;
    }

    function snapNow() {
      return typeof ctx.getSnap === "function" ? ctx.getSnap() : null;
    }

    function dismiss(doc, id, byKey) {
      if (!ui || typeof ctx.api !== "function") { return; }
      var ids = id === null ? order.slice() : [id];
      var next = null;
      if (id !== null) {
        var i = order.indexOf(id);
        next = i >= 0 && i + 1 < order.length ? order[i + 1] : null;
      }
      pendingFocus = byKey ? { gone: ids, next: next } : null;
      setAttr(ui.status, "data-shown", null);
      setText(ui.status, "");
      ctx.api("POST", "/api/trade-dismiss", id === null ? { all: true } : { id: id })
        .then(function () {
          ids.forEach(function (x) { hide[x] = true; });
          var s = snapNow();
          if (s) { render(doc, s, now()); }
        })
        .catch(function (e) {
          pendingFocus = null;
          ui.status.textContent = "";
          ui.status.textContent = NOT_DISMISSED;
          setAttr(ui.status, "data-shown", "yes");
          if (typeof console !== "undefined" && console && console.warn) {
            console.warn("dismiss failed: " + (e && e.message ? e.message : e));
          }
          var s = snapNow();
          if (s) { render(doc, s, now()); }
        });
    }

    function tradeNode(doc, r) {
      var li = el(doc, "li", "feed-row feed-trade edge edge-accent");
      // flat (PLAY-FIT-G5-TOTALS): the row's parts sit in the row itself;
      // the verb leads the item span ("wants Grim Bane Ruby Ring")
      var parts = {
        buyer: el(doc, "span", "feed-buyer"),
        item: el(doc, "span", "feed-item"),
        price: el(doc, "span", "feed-price"),
        right: el(doc, "span", "feed-right"),
        btn: el(doc, "button", "secondary btn-24 feed-dismiss", "Dismiss")
      };
      parts.btn.type = "button";
      parts.btn.addEventListener("click", function (ev) { dismiss(doc, r.id, keyboard(ev)); });
      li.appendChild(parts.buyer);
      li.appendChild(parts.item);
      li.appendChild(parts.price);
      li.appendChild(parts.right);
      li.appendChild(parts.btn);
      li.feedParts = parts;
      return li;
    }

    function eventNode(doc, r) {
      var li = el(doc, "li", "feed-row feed-event feed-" + r.kind);
      var parts = {
        tag: el(doc, "span", "feed-tag"),
        text: el(doc, "span", "feed-text"),
        right: el(doc, "span", "feed-right")
      };
      li.appendChild(parts.tag);
      li.appendChild(parts.text);
      li.appendChild(parts.right);
      li.feedParts = parts;
      return li;
    }

    function fill(li, r) {
      var p = li.feedParts;
      if (p.tag) { setText(p.tag, r.tag); }
      setText(p.right, r.right);
      setHidden(p.right, !r.right);
      setAttr(li, "title", r.title || null);
      if (r.kind === "trade") {
        setText(p.buyer, r.buyer);
        setHidden(p.buyer, !r.buyer);
        setText(p.item, [r.verb, r.item].filter(Boolean).join(" "));
        setText(p.price, r.price);
        setHidden(p.price, !r.price);
        setAttr(p.btn, "aria-label", "Dismiss trade request from " + (r.from || "unknown player"));
      } else {
        setText(p.text, r.text);
      }
    }

    /* Keep each row node by key, so a focused Dismiss survives a repaint;
       nodes move only when the order changes. */
    function place(list, nodes) {
      for (var i = 0; i < nodes.length; i++) {
        var at = list.children[i];
        if (at !== nodes[i]) { list.insertBefore(nodes[i], at || null); }
      }
      while (list.children.length > nodes.length) {
        list.removeChild(list.children[list.children.length - 1]);
      }
    }

    function render(doc, snap, t) {
      if (!ui || !isObj(snap)) { return; }
      var live = Array.isArray(snap.trade_requests) ? snap.trade_requests : [];
      var still = {};
      live.forEach(function (r) { if (isObj(r)) { still[r.id] = true; } });
      Object.keys(hide).forEach(function (k) { if (!still[k]) { delete hide[k]; } });
      var m = model(snap, t, hide);
      var prev = shownIds;
      shownIds = tradeIds(m.open);
      /* a shown "Not dismissed" goes once the open list changes */
      if (ui.status.getAttribute("data-shown") === "yes" &&
          (prev || []).join(",") !== shownIds.join(",")) {
        setAttr(ui.status, "data-shown", null);
        setText(ui.status, "");
      }
      /* design 0001 section 6: rows look frozen while the log is idle
         (decision 0029 game_idle) or AshLight is lost (state.offline) */
      setAttr(ui.region, "data-stale",
        snap.game_idle === true || snap.offline === true ? "yes" : null);
      if (showStatus(ui.status, prev, m.open)) { setAttr(ui.status, "data-shown", null); }
      var v = view(snap, t, hide, ui.status.textContent);
      setText(ui.h, v.head);
      setHidden(ui.all, !v.dismissAll);
      setHidden(ui.empty, !v.empty);
      var keep = {};
      var nodes = v.rows.map(function (r) {
        var li = rowNodes[r.key];
        if (!li) { li = r.kind === "trade" ? tradeNode(doc, r) : eventNode(doc, r); }
        rowNodes[r.key] = li;
        keep[r.key] = true;
        fill(li, r);
        return li;
      });
      Object.keys(rowNodes).forEach(function (k) { if (!keep[k]) { delete rowNodes[k]; } });
      place(ui.list, nodes);
      order = v.rows.filter(function (r) { return r.kind === "trade"; })
        .map(function (r) { return r.id; });
      moveFocus();
    }

    /* After a keyboard dismiss: once its row is gone, focus the next row's
       Dismiss, else the T heading. Never moves focus on any other change. */
    function moveFocus() {
      var f = pendingFocus;
      if (!f) { return; }
      var left = f.gone.some(function (id) { return order.indexOf(id) >= 0; });
      if (left) { return; }
      pendingFocus = null;
      var li = f.next !== null ? rowNodes["t" + f.next] : null;
      if (li && order.indexOf(f.next) >= 0) {
        li.feedParts.btn.focus();
      } else {
        ui.h.focus();
      }
    }

    function paint(doc, snap, t) { render(doc, snap, t); }
    function tick(doc, snap, t) { render(doc, snap, t); }

    return {
      wire: wire, paint: paint, tick: tick,
      spec: { name: "feed", region: "t", retires: ["t-trades"],
              wire: wire, paint: paint, tick: tick }
    };
  }

  var main = create();

  return {
    WORD_CAP: WORD_CAP, NEW_S: NEW_S, ROWS: ROWS, EMPTY: EMPTY, NOT_DISMISSED: NOT_DISMISSED,
    LADDER_TOP: LADDER_TOP,
    words: words, cutWords: cutWords, tradeIds: tradeIds, newTradeSentence: newTradeSentence,
    showStatus: showStatus, splitLead: splitLead, splitWhere: splitWhere, model: model,
    compose: compose, view: view, create: create, spec: main.spec
  };
}));
