/* AshLight dashboard: the Settings rail (PLAY-TD-21A-SETTINGS-RAIL; TD-21,
   F-067; docs/plan/03-target-design section 4). Settings is a rail of 6
   section buttons and a pane that shows ONE section at a time:
     1 Checks, 2 Reading and web data, 3 Overlay, 4 Keys,
     5 Appearance and tools, 6 About and data.
   Until PLAY-TD-21B-SETTINGS-ABOUT splits it, sections 4 to 6 share
   today's Tools card (#toolsbox): their three buttons show that one card.

   What this file does:
   - The section switch: a press of a rail button shows its section, marks
     that button aria-current="true" and keeps focus on it. No timer, no
     animation, no network, no clipboard, no live region.
   - The `open` accessor: the Checks section (#checks) gets an `open`
     property, so the code that opened the old Checks fold (web/checks.js
     on a new failure, web/notice.js and web/setupcard.js "Open Checks")
     shows the Checks section by setting open = true, unchanged. Reading
     it says whether Checks is the section on show. ZERO-CLICK: Checks is
     the section shown at load, and a new failure shows it again, unless
     the focus is inside another section (the player is working there).
   - Jump and focus: jump(doc, id) shows Settings, the section holding the
     element, the page of that section holding it, then focuses it. The
     bar status word (#reading, a button since this package) jumps to
     "Stop reading Client.txt" (#consent-no), or to the Reading and web
     data heading while Client.txt is not read: 2 clicks from any tab to
     the opt-out (ToS floor: the word stays the visible reading indicator
     on every tab). A button with data-jump="<id>" jumps the same way.
   - The pager: a section holds at most MAX_PX (448 px at s = 1) of rows
     and text. Its .rail-block children are packed in DOM order into pages
     of at most MAX_PX (a block taller than that is a page alone); Prev /
     Next under the section change the page, only on a press. A block off
     the page carries data-off (app.css folds it to 0 px, out of view and
     out of the focus order); its height is still read from scrollHeight,
     and a size change of a shown block pages the section again
     (ResizeObserver, where there is one). The pressed button is never re-created or disabled; an end
     button says aria-disabled="true" and does nothing.

   UMD like web/tabs.js: CommonJS for node --test (app/test/rail.test.js),
   window.ALRail in the page; web/app.js calls start() once, from its own
   start(), before the first state push. Classes, attributes and text
   only, never an inline style (CSP style-src 'self'). */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALRail = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_PX = 448;
  var CHECKS = "checks";
  // the rail buttons in order: [button id, section id]; 4 to 6 share #toolsbox
  var RAIL = [
    ["rail-checks", "checks"],
    ["rail-reading", "set-reading"],
    ["rail-overlay", "set-overlay"],
    ["rail-keys", "toolsbox"],
    ["rail-tools", "toolsbox"],
    ["rail-about", "toolsbox"]
  ];
  var STOP = "consent-no";
  var READING_HEAD = "reading-title";

  function isFn(v) { return typeof v === "function"; }
  function byId(doc, id) { return doc && isFn(doc.getElementById) ? doc.getElementById(id) : null; }

  /* Pack block heights (px, in DOM order) into pages of at most `max` px:
     a list of pages, each a list of block indexes. A block over `max` is
     a page alone; a zero-height block (hidden, empty) joins the page it
     follows. At least one page, even for no blocks. */
  function pack(heights, max) {
    max = typeof max === "number" && max > 0 ? max : MAX_PX;
    var pages = [[]];
    var used = 0;
    (heights || []).forEach(function (h, i) {
      h = typeof h === "number" && isFinite(h) && h > 0 ? h : 0;
      var cur = pages[pages.length - 1];
      if (cur.length && h > 0 && used + h > max) {
        pages.push([i]);
        used = h;
      } else {
        cur.push(i);
        used += h;
      }
    });
    return pages;
  }

  /* The page of `pages` holding block `index` (0 when none does). */
  function pageOf(pages, index) {
    for (var p = 0; p < pages.length; p++) {
      if (pages[p].indexOf(index) >= 0) { return p; }
    }
    return 0;
  }

  var state = { doc: null, button: RAIL[0][0], tabs: null, pages: {}, index: {},
                bars: {}, observer: null };

  function sectionOf(buttonId) {
    for (var i = 0; i < RAIL.length; i++) {
      if (RAIL[i][0] === buttonId) { return RAIL[i][1]; }
    }
    return null;
  }

  function sectionIds() {
    var out = [];
    RAIL.forEach(function (r) { if (out.indexOf(r[1]) < 0) { out.push(r[1]); } });
    return out;
  }

  function blocks(section) {
    if (!section || !section.children) { return []; }
    return Array.prototype.filter.call(section.children, function (c) {
      return (" " + (c.className || "") + " ").indexOf(" rail-block ") >= 0;
    });
  }

  function setAttr(n, k, on) {
    if (!n) { return; }
    if (on) {
      if (n.getAttribute(k) !== "true") { n.setAttribute(k, "true"); }
    } else if (n.getAttribute(k) !== null) {
      n.removeAttribute(k);
    }
  }

  /* The Prev / Next row under a section, made once per section. */
  function bar(doc, sid) {
    var b = state.bars[sid];
    if (b && b.doc === doc) { return b; }
    var section = byId(doc, sid);
    if (!section || !isFn(doc.createElement)) { return null; }
    var node = doc.createElement("div");
    node.className = "al-pager rail-pager";
    var count = doc.createElement("span");
    count.className = "al-pager-count";
    var prev = doc.createElement("button");
    var next = doc.createElement("button");
    [[prev, "Prev", "Previous page of "], [next, "Next", "Next page of "]].forEach(function (x) {
      x[0].setAttribute("type", "button");
      x[0].className = "al-pager-btn";
      x[0].textContent = x[1];
      var h = byId(doc, section.getAttribute("aria-labelledby"));
      x[0].setAttribute("aria-label", x[2] + (h ? h.textContent : "this section"));
    });
    node.appendChild(count);
    node.appendChild(prev);
    node.appendChild(next);
    section.appendChild(node);
    b = { doc: doc, node: node, count: count, prev: prev, next: next };
    if (isFn(prev.addEventListener)) {
      prev.addEventListener("click", function () { turn(doc, sid, -1); });
      next.addEventListener("click", function () { turn(doc, sid, 1); });
    }
    state.bars[sid] = b;
    return b;
  }

  /* Show page `index[sid]` of a section: data-off on every block off it,
     the count and the end buttons. */
  function paintPage(doc, sid) {
    var section = byId(doc, sid);
    var list = blocks(section);
    var pages = state.pages[sid] || [list.map(function (_, i) { return i; })];
    var p = Math.max(0, Math.min(state.index[sid] || 0, pages.length - 1));
    state.index[sid] = p;
    list.forEach(function (b, i) { setAttr(b, "data-off", pages[p].indexOf(i) < 0); });
    var many = pages.length > 1;
    var br = many ? bar(doc, sid) : state.bars[sid];
    if (!br) { return; }
    br.node.hidden = !many;
    var text = many ? "Page " + (p + 1) + " of " + pages.length : "";
    if (br.count.textContent !== text) { br.count.textContent = text; }
    setAttr(br.prev, "aria-disabled", p === 0);
    setAttr(br.next, "aria-disabled", p >= pages.length - 1);
  }

  /* Measure the blocks of a section and pack them again; the shown page
     is kept (clamped). */
  function repage(doc, sid) {
    var list = blocks(byId(doc, sid));
    state.pages[sid] = pack(list.map(function (b) {
      var o = typeof b.offsetHeight === "number" ? b.offsetHeight : 0;
      var s = typeof b.scrollHeight === "number" ? b.scrollHeight : 0;
      return Math.max(o, s);
    }), MAX_PX);
    paintPage(doc, sid);
  }

  function turn(doc, sid, step) {
    repage(doc, sid);
    var pages = state.pages[sid] || [[]];
    var p = (state.index[sid] || 0) + step;
    if (p < 0 || p >= pages.length) { return; } // an end button does nothing
    state.index[sid] = p;
    paintPage(doc, sid);
  }

  /* Show the section of rail button `buttonId`. Returns the section id. */
  function show(doc, buttonId) {
    var sid = sectionOf(buttonId);
    if (!sid) { return null; }
    state.button = buttonId;
    RAIL.forEach(function (r) {
      var b = byId(doc, r[0]);
      if (!b) { return; }
      if (r[0] === buttonId) {
        if (b.getAttribute("aria-current") !== "true") { b.setAttribute("aria-current", "true"); }
      } else if (b.getAttribute("aria-current") !== null) {
        b.removeAttribute("aria-current");
      }
    });
    sectionIds().forEach(function (id) {
      var s = byId(doc, id);
      if (s) { s.hidden = id !== sid; }
    });
    repage(doc, sid);
    return sid;
  }

  /* The section id on show. */
  function current() { return sectionOf(state.button); }

  /* The section (by id) and the block index holding `el`, or null. */
  function locate(doc, el) {
    var ids = sectionIds();
    for (var i = 0; i < ids.length; i++) {
      var s = byId(doc, ids[i]);
      if (!s || !isFn(s.contains) || !s.contains(el)) { continue; }
      var list = blocks(s);
      for (var j = 0; j < list.length; j++) {
        if (list[j] === el || (isFn(list[j].contains) && list[j].contains(el))) {
          return { sid: ids[i], block: j };
        }
      }
      return { sid: ids[i], block: -1 };
    }
    return null;
  }

  function visible(el) {
    for (var n = el; n; n = n.parentNode) {
      if (n.hidden === true) { return false; }
      if (n.id && n.id.indexOf("panel-") === 0) { return true; }
    }
    return true;
  }

  /* Show Settings, the section and page holding element `id`, and focus
     it; `fallback` (an element id) takes the focus when the element is
     hidden. Returns the element focused, or null. */
  function jump(doc, id, fallback) {
    doc = doc || state.doc;
    var el = byId(doc, id);
    if (!el || el.hidden) { el = fallback ? byId(doc, fallback) : null; }
    if (!el) { return null; }
    var tabs = state.tabs;
    if (tabs && isFn(tabs.show)) { tabs.show(doc, "settings", false); }
    var at = locate(doc, el);
    if (at) {
      var button = state.button;
      if (sectionOf(button) !== at.sid) {
        for (var i = 0; i < RAIL.length; i++) {
          if (RAIL[i][1] === at.sid) { button = RAIL[i][0]; break; }
        }
      }
      show(doc, button);
      if (at.block >= 0) {
        state.index[at.sid] = pageOf(state.pages[at.sid] || [[]], at.block);
        paintPage(doc, at.sid);
      }
    }
    if (!visible(el) && fallback && el.id !== fallback) { return jump(doc, fallback, null); }
    if (isFn(el.focus)) { el.focus(); }
    return el;
  }

  /* The bar status word's press: the opt-out while Client.txt is read,
     else the Reading and web data heading. */
  function toReading(doc) { return jump(doc, STOP, READING_HEAD); }

  /* True while the focus sits inside a shown section other than Checks:
     the player works there, so a new failure does not swap it away (the
     Settings tab still says "fix"; web/checks.js). */
  function holdsFocus(doc) {
    var sid = current();
    if (sid === CHECKS) { return false; }
    var s = byId(doc, sid);
    var a = doc ? doc.activeElement : null;
    return !!(a && s && s.hidden !== true && isFn(s.contains) && s.contains(a));
  }

  /* web/checks.js, web/notice.js and web/setupcard.js set #checks.open;
     true shows the Checks section on its first page (the rows), unless
     the focus is inside another section. */
  function accessor(doc) {
    var el = byId(doc, CHECKS);
    if (!el) { return; }
    var was = el.open === true;
    try {
      Object.defineProperty(el, "open", {
        configurable: true,
        enumerable: true,
        get: function () { return current() === CHECKS && el.hidden !== true; },
        set: function (v) {
          if (!v) { return; } // nothing closes a section; the rail shows another
          if (holdsFocus(doc)) { return; } // never hide what the player works in
          state.index[CHECKS] = 0;
          show(doc, RAIL[0][0]);
        }
      });
    } catch (e) { return; }
    if (was) { el.open = true; }
  }

  /* opts: {tabs: window.ALTabs, observe: a ResizeObserver class or null}.
     Wires the rail, the bar word and the data-jump buttons; shows Checks. */
  function start(doc, opts) {
    var o = opts || {};
    state.doc = doc;
    state.tabs = o.tabs || null;
    state.pages = {};
    state.index = {};
    state.bars = {};
    RAIL.forEach(function (r) {
      var b = byId(doc, r[0]);
      if (b && isFn(b.addEventListener)) {
        b.addEventListener("click", function () { show(doc, r[0]); });
      }
    });
    var word = byId(doc, "reading");
    if (word && isFn(word.addEventListener)) {
      word.addEventListener("click", function () { toReading(doc); });
    }
    var jumps = isFn(doc.querySelectorAll) ? doc.querySelectorAll("[data-jump]") : [];
    Array.prototype.forEach.call(jumps, function (b) {
      b.addEventListener("click", function () { jump(doc, b.getAttribute("data-jump"), null); });
    });
    accessor(doc);
    show(doc, RAIL[0][0]);
    // a block that grows or shrinks (a check row, the report preview, the
    // verdicts list) pages its section again; a block folded by data-off
    // keeps its scrollHeight, so paging again settles at once
    var RO = o.observe;
    if (isFn(RO)) {
      var ro = new RO(function () {
        var sid = current();
        if (sid) { repage(doc, sid); }
      });
      sectionIds().forEach(function (id) {
        blocks(byId(doc, id)).forEach(function (b) { ro.observe(b); });
      });
      state.observer = ro;
    }
    return state;
  }

  return { MAX_PX: MAX_PX, RAIL: RAIL, STOP: STOP, READING_HEAD: READING_HEAD,
    pack: pack, pageOf: pageOf, show: show, current: current, jump: jump,
    toReading: toReading, repage: repage, start: start, _state: state };
}));
