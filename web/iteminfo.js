/* AshLight dashboard: the shared item info popover (ITEM-INFO-UI, decision
   0082 part 1, decision 0083 points 1, 5 and 6).

   An item name in the Prices list (your checked items, currency values and
   the week's movers) is a link-like button (button(doc, name): type=button,
   aria-expanded, aria-controls="iteminfo-pop"). One click opens the one
   popover element of index.html, #iteminfo-pop (popover="manual",
   role=dialog, position fixed): it overlays the page beside its button,
   flips above when there is no room below, and never changes a card's
   size. Enter or Space (the button's own click) opens it and moves focus
   to its heading; Escape closes it and gives focus back to the button; Tab
   out closes it (no focus trap); a click anywhere outside it, a tab change,
   a page flip, a page scroll, a window resize or a list re-render closes
   it; one is open at a time.
   attach(root, opts) wires the clicks by event delegation, so the item card
   and the Kindler tab only make their names with button() and call attach.

   Data: the token-gated GET /api/iteminfo?name=... (server/al/plug/iteminfo.py)
   answers from what is already cached on this computer; nothing goes on the
   network when the popover opens, and it works with web data off. A field
   the reply lacks is left out, never guessed; an empty reply shows the name
   and "No saved info for this item yet". The credit lines name only the
   sources that gave a shown field: repoe-fork, poe.ninja (with its age) and
   Path of Building (the "where found" rows, decision 0083 point 1). The
   poe.ninja icon is not shown: it is a web address, and loading it would
   be a request (CSP img-src 'self'). The popover ends with the poe2db line
   and a "More on poe2db" link built from the name; it opens only on the
   player's click, in the browser, through the client's link guard
   (decision 0041; poe2db.tw is in config/link_hosts.json). No poe2db text
   is fetched or copied.

   ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): for a gem the
   reply's "gem" field adds its kind, tags, level, cost, reservation, cast
   time, cooldown and cost multiplier rows, then each stat set's lines as
   the game words them, under "At gem level <n>" (a button made with
   button(doc, name, level) asks for that level, else level 1). The words
   are the repoe-fork export's; a field the reply lacks is left out.

   Text goes in through textContent only; no timer, no clipboard, no live
   region, no storage. UMD like web/prices.js: CommonJS for node
   (tests/test_iteminfo_ui.py drives it there), window.ALItemInfo in the
   page, where it registers
   itself with window.ALApp (web/registry.js) as "iteminfo", order 165. */
(function (root, factory) {
  "use strict";
  var api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALItemInfo = api;
    if (root.ALApp && typeof root.ALApp.register === "function") {
      root.ALApp.register({
        name: api.NAME,
        order: api.ORDER,
        paint: function () { api.sync(); },
        wire: function () { api.attach(document, { api: root.ALApp.host.api }); }
      });
    }
  }
}(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  var NAME = "iteminfo";
  var ORDER = 165; // after Price watch (160), which paints the Prices list
  var POP_ID = "iteminfo-pop";
  var CLS = "iteminfo-name";
  var PATH = "/api/iteminfo?name=";
  var POE2DB = "https://poe2db.tw/us/";
  var GAP = 4;    // px between the button and the popover
  var EDGE = 8;   // px the popover keeps from the window edge

  var EMPTY = "No saved info for this item yet";
  var FAILED = "AshLight can't read item info right now. Try again in a moment.";
  var MORE_LINE = "Drops, vendor and disenchant: see poe2db (community site)";
  var MORE_TEXT = "More on poe2db";
  var WHERE_TITLE = "Where found";
  var GONE = "No longer obtainable";
  var CREDITS = {
    "repoe-fork": "Item data: RePoE fork export. Game data (c) Grinding Gear Games",
    "path-of-building": "Path of Building (MIT), community-written, may be out of date",
    flavour: "Flavour text: poe.ninja"
  };
  var STATES = { legacy: "Legacy", unreleased: "Unreleased", unique_only: "Unique only" };
  var GEM_KINDS = { active: "Skill gem", support: "Support gem", spirit: "Spirit gem" };
  var COSTS = { Mana: "Mana", Life: "Life", Ward: "Ward", ManaPerMinute: "Mana a minute",
                LifePerMinute: "Life a minute", WardPerMinute: "Ward a minute" };
  var LEVEL_MAX = 40;

  function prices() {
    if (root && root.ALPrices) { return root.ALPrices; }
    if (typeof module === "object" && module.exports && typeof require === "function") {
      return require("./prices.js");
    }
    return null;
  }

  function str(v) { return typeof v === "string" ? v.trim() : ""; }
  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function num(n) {
    var P = prices();
    return P ? P.num(n) : String(n);
  }

  function ageText(s) {
    var P = prices();
    return P ? P.ageText(s) : "";
  }

  /* The poe2db page of a name (the same form as web/tc.js links()). */
  function poe2dbHref(name) {
    var n = str(name);
    return n ? POE2DB + encodeURIComponent(n.replace(/ /g, "_")) : "";
  }

  function stateWords(s) {
    var v = str(s);
    if (!v) { return ""; }
    if (STATES[v]) { return STATES[v]; }
    var w = v.replace(/_+/g, " ");
    return w.charAt(0).toUpperCase() + w.slice(1);
  }

  function trend(c) {
    if (!isNum(c)) { return ""; }
    if (Math.abs(c) < 0.5) { return "no change"; }
    return (c > 0 ? "up " : "down ") + num(Math.abs(c)) + "%";
  }

  function marketRows(m) {
    var rows = [];
    if (!m || typeof m !== "object" || !isNum(m.value)) { return rows; }
    var unit = str(m.unit);
    var price = "";
    if (isNum(m.divine)) {
      price = num(m.divine) + " Divine Orb";
      if (unit && unit !== "Divine Orb") { price += " (" + num(m.value) + " " + unit + ")"; }
    } else if (unit) {
      price = num(m.value) + " " + unit;
    }
    if (price) { rows.push({ label: "Price", value: price }); }
    var t = trend(m.change_7d);
    if (t) { rows.push({ label: "7-day trend", value: t }); }
    if (typeof m.listings === "number" && isFinite(m.listings)) {
      rows.push({ label: "Listings", value: num(m.listings) + (m.few ? " (few listings)" : "") });
    } else if (isNum(m.volume)) {
      rows.push({ label: "Volume", value: num(m.volume) });
    }
    return rows;
  }

  function marketCredit(m) {
    var c = str(m && m.credit) || "Prices: poe.ninja";
    var league = str(m && m.league);
    var age = ageText(m && m.age_s);
    return c + (league ? ", " + league : "") + (age ? ", updated " + age : "");
  }

  function whereView(w) {
    if (!w || typeof w !== "object") { return null; }
    var rows = [];
    (Array.isArray(w.drops) ? w.drops : []).forEach(function (d) {
      var boss = str(d && d.boss);
      if (!boss) { return; }
      var zone = str(d.zone);
      rows.push("Drops from " + boss + (zone ? " in " + zone + (d.map === true ? " (a map)" : "") : ""));
    });
    if (w.no_longer_obtainable === true) { rows.push(GONE); }
    return rows.length ? { title: WHERE_TITLE, rows: rows } : null;
  }

  function secs(v) { return num(Math.round(v * 100) / 100) + " s"; }

  /* A gem's rows and stat-line sections ({rows, sets}); an unknown cost
     type or field is left out. */
  function gemView(g) {
    var rows = [];
    var sets = [];
    if (!g || typeof g !== "object") { return { rows: rows, sets: sets }; }
    function add(label, value) { if (value) { rows.push({ label: label, value: value }); } }
    add("Gem", GEM_KINDS[str(g.kind)] || "");
    var tags = (Array.isArray(g.tags) ? g.tags : []).map(str).filter(Boolean);
    add("Tags", tags.join(", "));
    var many = isNum(g.max_level) && g.max_level > 1;
    if (many && isNum(g.level)) { add("Gem level", num(g.level)); }
    var costs = (Array.isArray(g.costs) ? g.costs : []).filter(function (c) {
      return c && COSTS[c.type] && isNum(c.amount);
    }).map(function (c) { return num(c.amount) + " " + COSTS[c.type]; });
    add("Cost", costs.join(", "));
    if (isNum(g.spirit) && g.spirit > 0) { add("Reservation", num(g.spirit) + " Spirit"); }
    if (isNum(g.cast_time_s)) { add("Cast time", secs(g.cast_time_s)); }
    if (isNum(g.cooldown_s) && g.cooldown_s > 0) { add("Cooldown", secs(g.cooldown_s)); }
    if (isNum(g.cost_multiplier) && g.cost_multiplier > 0) {
      add("Cost multiplier", num(g.cost_multiplier) + "%");
    }
    var level = many && isNum(g.level) ? "At gem level " + num(g.level) : "Effect";
    var list = Array.isArray(g.sets) ? g.sets : [];
    list.forEach(function (st, i) {
      if (!st || typeof st !== "object") { return; }
      var lines = [];
      if (isNum(st.damage_pct)) { lines.push("Attack damage: " + num(st.damage_pct) + "% of base"); }
      if (isNum(st.crit_pct)) { lines.push("Critical hit chance: " + num(st.crit_pct) + "%"); }
      (Array.isArray(st.lines) ? st.lines : []).forEach(function (t) {
        if (str(t)) { lines.push(str(t)); }
      });
      if (!lines.length) { return; }
      // more than one set: each heading names its set (its label, else "Set <n>")
      var label = list.length > 1 ? (str(st.label) || "Set " + (i + 1)) : "";
      sets.push({ title: level + (label ? ": " + label : ""), rows: lines });
    });
    return { rows: rows, sets: sets };
  }

  /* The popover's words for one /api/iteminfo reply {name, fields,
     sources}: {name, empty, rows [{label, value}], texts [{cls, text}],
     where {title, rows} | null, credits [text], more {line, text, href,
     label}}. Field order of decision 0083 point 1; a field with no value
     is left out. */
  function view(reply, asked) {
    var r = reply && typeof reply === "object" ? reply : {};
    var f = r.fields && typeof r.fields === "object" ? r.fields : {};
    var sources = Array.isArray(r.sources) ? r.sources : [];
    var name = str(r.name) || str(asked);
    var rows = [];
    var texts = [];
    var credits = [];
    var fromRepoe = false;

    function row(label, value) {
      if (!value) { return; }
      rows.push({ label: label, value: value });
      fromRepoe = true;
    }

    row("Item class", str(f.item_class));
    row("Rarity", str(f.rarity));
    var gem = gemView(f.gem);
    gem.rows.forEach(function (g) { row(g.label, g.value); });
    var market = marketRows(f.market);
    market.forEach(function (m) { rows.push(m); });
    var stack = typeof f.stack_size === "number" && isFinite(f.stack_size) && f.stack_size > 1
      ? f.stack_size : 0;
    var turns = str(f.full_stack_turns_into);
    if (stack && turns) {
      row("Full stack", num(stack) + " become 1 " + turns);
    } else if (stack) {
      row("Stack size", num(stack));
    }
    [["description", "iteminfo-desc"], ["directions", "iteminfo-dir"]].forEach(function (p) {
      var t = str(f[p[0]]);
      if (t) { texts.push({ cls: p[1], text: t }); fromRepoe = true; }
    });
    var flavour = str(f.flavour);
    if (flavour) { texts.push({ cls: "iteminfo-flavour", text: flavour }); }
    row("Release state", stateWords(f.release_state));
    var where = whereView(f.where_found);
    if (gem.sets.length) { fromRepoe = true; }

    if (fromRepoe && sources.indexOf("repoe-fork") >= 0) { credits.push(CREDITS["repoe-fork"]); }
    // the market block carries its own credit: shown prices are always credited
    if (market.length) {
      credits.push(marketCredit(f.market));
    } else if (flavour && sources.indexOf("poe.ninja") >= 0) {
      credits.push(CREDITS.flavour);
    }
    if (where && sources.indexOf("path-of-building") >= 0) {
      credits.push(CREDITS["path-of-building"]);
    }
    var href = poe2dbHref(name);
    return {
      name: name,
      empty: !rows.length && !texts.length && !where && !gem.sets.length,
      rows: rows, texts: texts, gem: gem.sets, where: where, credits: credits,
      more: href ? { line: MORE_LINE, text: MORE_TEXT, href: href,
                     label: MORE_TEXT + " about " + name + " (opens in a new tab)" } : null
    };
  }

  /* Where the popover goes: below the button, flipped above when it does
     not fit below and does fit above; kept EDGE px inside the window.
     btn {top, bottom, left}, size {width, height}, win {width, height}. */
  function place(btn, size, win) {
    var top = btn.bottom + GAP;
    if (top + size.height > win.height - EDGE && btn.top - GAP - size.height >= EDGE) {
      top = btn.top - GAP - size.height;
    }
    top = Math.max(EDGE, Math.min(top, win.height - size.height - EDGE));
    var left = Math.max(EDGE, Math.min(btn.left, win.width - size.width - EDGE));
    return { top: Math.round(top), left: Math.round(left) };
  }

  /* An item name as a link-like button that opens the popover; level (a
     gem level, 1 to LEVEL_MAX) asks for a gem's lines at that level. */
  function button(doc, name, level) {
    var b = doc.createElement("button");
    b.type = "button";
    b.className = "link " + CLS;
    b.textContent = name;
    b.setAttribute("data-item", name);
    b.setAttribute("aria-expanded", "false");
    b.setAttribute("aria-controls", POP_ID);
    b.setAttribute("aria-haspopup", "dialog");
    if (isNum(level) && level >= 1 && level <= LEVEL_MAX && level === Math.floor(level)) {
      b.setAttribute("data-level", String(level));
    }
    return b;
  }

  /* A list row's parts for web/search.js rowPager: the row text with the
     first appearance of item as its button ([{text}, {node}, {text}]);
     the whole text when the item is empty or not in it. */
  function parts(doc, text, item) {
    var t = typeof text === "string" ? text : "";
    var name = typeof item === "string" ? item : "";
    var at = name ? t.indexOf(name) : -1;
    if (at < 0) { return [{ text: t }]; }
    var out = [];
    if (at > 0) { out.push({ text: t.slice(0, at) }); }
    out.push({ node: button(doc, name) });
    if (at + name.length < t.length) { out.push({ text: t.slice(at + name.length) }); }
    return out;
  }

  /* ---- the one popover per page */
  var ctl = null;       // {doc, pop, api, opener, seq, roots}
  var lastEvent = null; // a click handled once, however many roots see it

  function el(doc, tag, cls, text) {
    var n = doc.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function nameButton(target) {
    var n = target;
    while (n && n.nodeType === 1) {
      if (n.classList && n.classList.contains(CLS)) { return n; }
      n = n.parentNode;
    }
    return null;
  }

  function isOpen() { return !!(ctl && ctl.opener); }

  function show(pop) {
    if (typeof pop.showPopover === "function") {
      try { pop.showPopover(); } catch (e) { /* already open */ }
    } else {
      pop.hidden = false;
    }
  }

  function hide(pop) {
    if (typeof pop.hidePopover === "function") {
      try { pop.hidePopover(); } catch (e) { /* already closed */ }
    } else {
      pop.hidden = true;
    }
  }

  function position() {
    if (!isOpen()) { return; }
    var win = ctl.doc.defaultView || root;
    var b = ctl.opener.getBoundingClientRect();
    var p = ctl.pop.getBoundingClientRect();
    var at = place(b, { width: p.width, height: p.height },
                   { width: win.innerWidth, height: win.innerHeight });
    ctl.pop.style.top = at.top + "px";
    ctl.pop.style.left = at.left + "px";
  }

  function fill(v, failed) {
    var doc = ctl.doc;
    doc.getElementById("iteminfo-title").textContent = v.name;
    var body = doc.getElementById("iteminfo-body");
    body.replaceChildren();
    if (failed) {
      body.appendChild(el(doc, "p", "iteminfo-note", FAILED));
    } else if (v.empty) {
      body.appendChild(el(doc, "p", "iteminfo-note", EMPTY));
    }
    if (v.rows.length) {
      var dl = el(doc, "dl", "iteminfo-rows");
      v.rows.forEach(function (r) {
        dl.appendChild(el(doc, "dt", null, r.label));
        dl.appendChild(el(doc, "dd", null, r.value));
      });
      body.appendChild(dl);
    }
    v.texts.forEach(function (t) { body.appendChild(el(doc, "p", t.cls, t.text)); });
    (v.gem || []).forEach(function (st) {
      body.appendChild(el(doc, "h3", "iteminfo-sub", st.title));
      var gl = el(doc, "ul", "iteminfo-where iteminfo-gem");
      st.rows.forEach(function (t) { gl.appendChild(el(doc, "li", null, t)); });
      body.appendChild(gl);
    });
    if (v.where) {
      body.appendChild(el(doc, "h3", "iteminfo-sub", v.where.title));
      var ul = el(doc, "ul", "iteminfo-where");
      v.where.rows.forEach(function (t) { ul.appendChild(el(doc, "li", null, t)); });
      body.appendChild(ul);
    }
    v.credits.forEach(function (c) { body.appendChild(el(doc, "p", "iteminfo-credit", c)); });
    var more = doc.getElementById("iteminfo-more");
    var link = doc.getElementById("iteminfo-poe2db");
    more.hidden = link.hidden = !v.more;
    if (v.more) {
      more.textContent = v.more.line;
      link.textContent = v.more.text;
      link.href = v.more.href;
      link.setAttribute("aria-label", v.more.label);
    }
    position();
  }

  function close(returnFocus) {
    if (!isOpen()) { return; }
    var opener = ctl.opener;
    ctl.opener = null;
    ctl.seq += 1; // a reply still on its way paints nothing
    opener.setAttribute("aria-expanded", "false");
    hide(ctl.pop);
    if (returnFocus && opener.isConnected !== false && typeof opener.focus === "function") {
      opener.focus();
    }
  }

  function open(btn) {
    if (!ctl) { return; }
    if (ctl.opener) { close(false); }
    var name = btn.getAttribute("data-item") || btn.textContent || "";
    ctl.opener = btn;
    btn.setAttribute("aria-expanded", "true");
    var seq = ++ctl.seq;
    var v = view(null, name);
    show(ctl.pop);
    fill({ name: v.name, empty: false, rows: [], texts: [], gem: [], where: null, credits: [],
           more: v.more }, false);
    ctl.doc.getElementById("iteminfo-title").focus();
    if (typeof ctl.api !== "function") { return; }
    var lvl = btn.getAttribute("data-level") || "";
    var tail = /^[1-9][0-9]?$/.test(lvl) ? "&level=" + lvl : "";
    ctl.api("GET", PATH + encodeURIComponent(name) + tail).then(function (reply) {
      if (seq === ctl.seq) { fill(view(reply, name), false); }
    }, function () {
      if (seq === ctl.seq) { fill(view(null, name), true); }
    });
  }

  function onClick(e) {
    if (e === lastEvent) { return; }
    lastEvent = e;
    var b = nameButton(e.target);
    if (b) {
      if (ctl.opener === b) { close(false); } else { open(b); }
      return;
    }
    if (isOpen() && !ctl.pop.contains(e.target)) { close(false); }
  }

  function onKey(e) {
    if (isOpen() && (e.key === "Escape" || e.key === "Esc")) {
      e.preventDefault();
      close(true);
    }
  }

  function onFocusOut(e) {
    if (!isOpen()) { return; }
    var to = e.relatedTarget;
    if (to && ctl.pop.contains(to)) { return; }
    if (to === ctl.opener) { return; }
    // the window lost focus (a link opened the browser): stay open
    if (!to && ctl.doc.hasFocus && !ctl.doc.hasFocus()) { return; }
    close(false);
  }

  /* Wire the popover once per page, and the clicks of root (the document,
     or a card that makes its names with button()). opts.api: the page's
     token api(method, path) -> Promise. */
  function attach(rootNode, opts) {
    var doc = rootNode && (rootNode.ownerDocument || rootNode);
    if (!doc || typeof doc.getElementById !== "function") { return false; }
    var pop = doc.getElementById(POP_ID);
    if (!pop) { return false; }
    if (!ctl || ctl.doc !== doc) {
      ctl = { doc: doc, pop: pop, api: null, opener: null, seq: 0, roots: [] };
      if (typeof pop.showPopover !== "function") { pop.hidden = true; }
      doc.addEventListener("click", onClick);
      doc.addEventListener("keydown", onKey);
      pop.addEventListener("focusout", onFocusOut);
      // a page scroll moves the button away from the fixed popover: close
      doc.addEventListener("scroll", function (e) {
        if (isOpen() && !ctl.pop.contains(e.target)) { close(false); }
      }, true);
      var win = doc.defaultView;
      if (win && typeof win.addEventListener === "function") {
        win.addEventListener("resize", function () { close(false); });
      }
    }
    if (opts && typeof opts.api === "function") { ctl.api = opts.api; }
    if (rootNode !== doc && ctl.roots.indexOf(rootNode) < 0) {
      ctl.roots.push(rootNode);
      rootNode.addEventListener("click", onClick);
    }
    return true;
  }

  /* After a list re-render: an opener that left the page closes the
     popover (no focus to give back). */
  function sync() {
    if (isOpen() && (ctl.opener.isConnected === false || !ctl.doc.contains(ctl.opener))) {
      close(false);
    }
  }

  return { NAME: NAME, ORDER: ORDER, POP_ID: POP_ID, CLS: CLS, PATH: PATH,
           EMPTY: EMPTY, FAILED: FAILED, MORE_LINE: MORE_LINE, MORE_TEXT: MORE_TEXT,
           WHERE_TITLE: WHERE_TITLE, GONE: GONE, CREDITS: CREDITS,
           GEM_KINDS: GEM_KINDS, COSTS: COSTS, LEVEL_MAX: LEVEL_MAX,
           view: view, gemView: gemView, place: place, poe2dbHref: poe2dbHref, button: button, parts: parts,
           attach: attach, sync: sync, close: close, isOpen: isOpen };
}));
