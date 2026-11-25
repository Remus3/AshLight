/* PLAY-TD-13-FEED: region T, the feed (web/feed.js). Five one-line rows,
   open trades first (all 5, newest on top) with their own Dismiss, then
   the latest death, level-up and zone change; at most 50 words; "new" for
   60 s; Dismiss all from 2 trades; a keyboard dismiss moves focus to the
   next row's Dismiss or the T heading; the polite trade status says a new
   request once in at most 12 words (moved in from web/trades.js, UX-REVIEW
   F6). A small fake DOM; no browser, no timers, no network. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const F = web.load("feed.js");
const S = web.load("slots.js");

const SRC = web.source("feed.js");
const CSS = web.source("feed.css");

/* ---- fixtures --------------------------------------------------------- */

const NOW = 10000;
const NAME40 = "Firstbuyerwithaverylongaccountnamefirst";
const ITEM40 = "Remember the waypoint beside Clearfell E";

function trade(id, from, item, price, at, where) {
  return { id: id, at: at, from: from, item: item,
           text: from + " wants " + item + " - " + price,
           where: where === undefined ? "tab Sale (" + id + ",7)" : where };
}

/* The core's play.feed for these trades (newest first), as playview.py
   composes it, plus the three events. */
function snapOf(trades, events) {
  const newest = trades.slice().sort((a, b) => b.at - a.at || b.id - a.id);
  return {
    now: NOW,
    trade_requests: trades,
    play: { feed: {
      trades: newest.map((t) => ({ id: t.id, lead: t.text, right: "stale server text",
                                   title: t.text + (t.where ? " (" + t.where + ")" : "") })),
      events: events || { death: null, level: null, zone: null }
    } }
  };
}

const EVENTS = {
  death: { kind: "death", tag: "Death", text: "Ashdemo died in Clearfell", right: "14:01",
           title: "Ashdemo died in Clearfell at level 4", at: NOW - 600 },
  level: { kind: "level", tag: "Level", text: "Ashdemo reached level 4", right: "new, 14:10",
           title: "Ashdemo reached level 4", at: NOW - 30 },
  zone: { kind: "zone", tag: "Zone", text: "Entered Clearfell", right: "14:00",
          title: "Entered Clearfell", at: NOW - 900 }
};

function fiveLong() {
  const out = [];
  for (let i = 1; i <= 5; i++) {
    out.push(trade(i, NAME40.slice(0, 39) + i, ITEM40, (100 + i) + " exalted", NOW - 10 * (6 - i)));
  }
  return out;
}

/* ---- the fake DOM ----------------------------------------------------- */

function fakeDoc() {
  const doc = { activeElement: null, byId: {}, created: 0 };
  function node(tag) {
    doc.created += 1;
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], id: "",
      parentNode: null, attrs: {}, listeners: {}, _text: "", type: "",
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); (this.writes = this.writes || []).push(String(v)); },
      appendChild(c) { return this.insertBefore(c, null); },
      insertBefore(c, ref) {
        if (c.parentNode) { c.parentNode.removeChild(c); }
        const i = ref ? this.children.indexOf(ref) : -1;
        if (i < 0) { this.children.push(c); } else { this.children.splice(i, 0, c); }
        c.parentNode = this;
        return c;
      },
      removeChild(c) {
        this.children = this.children.filter((x) => x !== c);
        c.parentNode = null;
        if (doc.activeElement === c || (doc.activeElement && within(c, doc.activeElement))) {
          doc.activeElement = null;
        }
        return c;
      },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      focus() { doc.activeElement = this; },
      click(detail) {
        (this.listeners.click || []).forEach((fn) => fn({ target: this, detail: detail }));
      }
    };
    return n;
  }
  function within(root, n) {
    for (let p = n; p; p = p.parentNode) { if (p === root) { return true; } }
    return false;
  }
  doc.createElement = node;
  // a text node: no class, no children, its text in data (shownText reads _text)
  doc.createTextNode = (text) => ({
    nodeType: 3, className: "", hidden: false, children: [], parentNode: null, data: String(text),
    get _text() { return this.data; },
    get textContent() { return this.data; }
  });
  doc.getElementById = (id) => doc.byId[id] || null;
  const region = node("section");
  region.id = "play-t";
  const h = node("h2");
  h.id = "play-t-h";
  h.className = "region-h sr-only";
  h.textContent = "Trades and events";
  const slot = node("div");
  slot.className = "slot";
  region.appendChild(h);
  region.appendChild(slot);
  doc.byId = { "play-t": region, "play-t-h": h };
  doc.querySelector = (sel) => (sel === "#play-t > [data-slot=\"t\"]" ? slot : null);
  doc.region = region;
  doc.slot = slot;
  return doc;
}

function find(n, cls, out) {
  const list = out || [];
  if ((" " + n.className + " ").indexOf(" " + cls + " ") >= 0) { list.push(n); }
  n.children.forEach((c) => find(c, cls, list));
  return list;
}

/* Words a viewer meets: the harness counts innerText, so hidden nodes are
   left out. */
function shownText(n) {
  if (n.hidden) { return ""; }
  return [n._text].concat(n.children.map(shownText)).join(" ");
}

function setup(apiImpl) {
  const doc = fakeDoc();
  const calls = [];
  let snap = null;
  const feed = F.create();
  const ctx = {
    api: (method, p, body) => {
      calls.push({ method: method, path: p, body: body });
      return apiImpl ? apiImpl(body) : Promise.resolve({ ok: true });
    },
    getSnap: () => snap,
    serverNow: () => NOW,
    tabs: null
  };
  feed.wire(doc, ctx);
  return {
    doc: doc, calls: calls, feed: feed,
    paint(s, t) { snap = s; feed.paint(doc, s, t === undefined ? NOW : t, ctx); },
    setSnap(s) { snap = s; },
    rows() { return find(doc.slot, "feed-row").filter((r) => r.parentNode && !r.hidden); },
    btns() { return find(doc.slot, "feed-dismiss"); },
    all() { return find(doc.slot, "feed-all")[0]; },
    status() { return find(doc.slot, "feed-status")[0]; }
  };
}

const flush = () => new Promise((r) => setImmediate(r));

/* ---- words and cuts --------------------------------------------------- */

test("words count like the Play fit harness: tokens with a letter or digit", () => {
  assert.equal(F.words("Trade Quietfox wants Grim Bane - 5 exalted"), 7);
  assert.equal(F.words("new, tab Sale (3,7)"), 4);
  assert.equal(F.words(" - ... "), 0);
  assert.equal(F.words(""), 0);
  assert.equal(F.words(null), 0);
});

test("cutWords keeps n words and ends in ...", () => {
  assert.equal(F.cutWords("Example Amber Amulet", 3), "Example Amber Amulet");
  assert.equal(F.cutWords("Example Unique Quarterstaff of Many Words", 3), "Example Unique Quarterstaff...");
  assert.equal(F.cutWords("Example Amber Amulet", 1), "Example...");
  assert.equal(F.cutWords("Example Amber Amulet", 0), "...");
  assert.equal(F.words(F.cutWords("a b c d e f", 2)), 2);
});

/* ---- trade status (moved from web/trades.js) --------------------------- */

const row = (id, from) => ({ id: id, from: from });

test("status: one new request names the player, several are counted", () => {
  assert.equal(F.newTradeSentence([1], [row(1, "A"), row(2, "Quietfox")]),
    "New trade request from Quietfox.");
  assert.equal(F.newTradeSentence([], [row(4, "")]), "New trade request.");
  assert.equal(F.newTradeSentence([1], [row(1, "A"), row(2, "B"), row(3, "C")]),
    "2 new trade requests.");
  assert.equal(F.newTradeSentence([1], [row(2, "B")]), "New trade request from B.");
});

test("status: nothing on first paint, a shrink or no change", () => {
  assert.equal(F.newTradeSentence(null, [row(1, "A")]), "");
  assert.equal(F.newTradeSentence([1, 2], [row(2, "B")]), "");
  assert.equal(F.newTradeSentence([1, 2], [row(1, "A"), row(2, "B")]), "");
  assert.deepEqual(F.tradeIds([row(3, "A"), row(5, "B")]), [3, 5]);
  assert.deepEqual(F.tradeIds(null), []);
});

test("status: every sentence is at most 12 words", () => {
  const long = "Secondbuyer_WithALongAccountName";
  const said = [F.newTradeSentence([], [row(1, long)]), F.newTradeSentence([], [row(1, "")]),
                F.newTradeSentence([], [row(1, "A"), row(2, "B"), row(3, "C"), row(4, "D"), row(5, "E")]),
                F.NOT_DISMISSED];
  said.forEach((s) => assert.ok(s && F.words(s) <= 12, s));
});

function fakeRegion(text) {
  const writes = [];
  let value = text;
  return { writes: writes,
           get textContent() { return value; },
           set textContent(v) { value = v; writes.push(v); } };
}

test("showStatus: said once, the same sentence again is cleared first, a shrink clears", () => {
  let el = fakeRegion("");
  F.showStatus(el, [1], [row(1, "A"), row(2, "B")]);
  assert.deepEqual(el.writes, ["New trade request from B."]);
  el = fakeRegion("New trade request.");
  F.showStatus(el, [1], [row(1, ""), row(2, "")]);
  assert.deepEqual(el.writes, ["", "New trade request."]);
  el = fakeRegion("New trade request from B.");
  F.showStatus(el, [1, 2], [row(1, "A")]);
  assert.deepEqual(el.writes, [""]);
  el = fakeRegion("x");
  F.showStatus(el, null, [row(1, "A")]);
  F.showStatus(el, [1], [row(1, "A")]);
  assert.deepEqual(el.writes, []);
});

/* ---- the rows (pure) -------------------------------------------------- */

test("splitLead and splitWhere take the core's template apart", () => {
  assert.deepEqual(F.splitLead("Quietfox wants Grim Bane Ruby Ring - 5 exalted", "Quietfox"),
    { buyer: "Quietfox", verb: "wants", item: "Grim Bane Ruby Ring", price: "- 5 exalted" });
  assert.deepEqual(F.splitLead("Quietfox wants 5 Divine Orb - for 300 exalted", "Quietfox").price,
    "- for 300 exalted");
  assert.deepEqual(F.splitLead("odd text", "Quietfox"),
    { buyer: "", verb: "", item: "odd text", price: "" });
  assert.deepEqual(F.splitWhere("tab Sale (3,7)"), { tab: "tab Sale", pos: "(3,7)" });
  assert.deepEqual(F.splitWhere("tab Sale"), { tab: "tab Sale", pos: "" });
  assert.deepEqual(F.splitWhere(""), { tab: "", pos: "" });
});

test("open trades come first, newest on top, then death, level-up and zone", () => {
  const trades = [trade(1, "Old", "Ring", "5 exalted", NOW - 300),
                  trade(2, "Newer", "Amulet", "9 exalted", NOW - 20)];
  const v = F.view(snapOf(trades, EVENTS), NOW, {}, "");
  assert.deepEqual(v.rows.map((r) => r.kind), ["trade", "trade", "death", "level", "zone"]);
  assert.deepEqual(v.rows.slice(0, 2).map((r) => r.buyer), ["Newer", "Old"]);
  assert.equal(v.head, "Trades 2");
  assert.equal(v.dismissAll, true);
  // the same choice as web/slots.js feedRows
  const f = S.feedRows(trades, EVENTS);
  assert.deepEqual(f.rows.map((r) => r.kind), v.rows.map((r) => r.kind));
});

test("a trade is never evicted by an event: 5 trades fill all 5 rows", () => {
  const v = F.view(snapOf(fiveLong(), EVENTS), NOW, {}, "");
  assert.equal(v.rows.length, 5);
  assert.ok(v.rows.every((r) => r.kind === "trade"));
  assert.deepEqual(v.rows.map((r) => r.id), [5, 4, 3, 2, 1]);
});

test("Dismiss all shows from 2 trades; no trades: the head is Recent", () => {
  const one = F.view(snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 5)], EVENTS), NOW, {}, "");
  assert.equal(one.dismissAll, false);
  assert.equal(one.head, "Trades 1");
  const none = F.view(snapOf([], EVENTS), NOW, {}, "");
  assert.equal(none.head, "Recent");
  assert.equal(none.dismissAll, false);
  assert.deepEqual(none.rows.map((r) => r.tag), ["Death", "Level", "Zone"]);
  const empty = F.view(snapOf([], null), NOW, {}, "");
  assert.equal(empty.rows.length, 0);
  assert.equal(empty.empty, F.EMPTY);
});

test("for 60 s the right segment starts with new, then the age in minutes", () => {
  const t = trade(1, "A", "Ring", "1 exalted", NOW - 59, "tab Sale (1,2)");
  let r = F.view(snapOf([t]), NOW, {}, "").rows[0];
  assert.equal(r.right, "new, tab Sale (1,2)");
  r = F.view(snapOf([t]), NOW + 1, {}, "").rows[0];
  assert.equal(r.right, "tab Sale (1,2), 1m");
  r = F.view(snapOf([t]), NOW + 200, {}, "").rows[0];
  assert.equal(r.right, "tab Sale (1,2), 4m");
  // an event: "new, 14:10" from its own time, the server's stale "new" dropped
  const ev = F.view(snapOf([], EVENTS), NOW, {}, "").rows;
  assert.equal(ev[1].right, "new, 14:10");
  assert.equal(F.view(snapOf([], EVENTS), NOW + 60, {}, "").rows[1].right, "14:10");
  assert.equal(ev[0].right, "14:01");
});

test("the row sentence keeps its template: the buyer leads, new never enters it", () => {
  const t = trade(1, "Quietfox", "Grim Bane Ruby Ring", "5 exalted", NOW - 1);
  const r = F.view(snapOf([t]), NOW, {}, "").rows[0];
  assert.equal([r.buyer, r.verb, r.item, r.price].join(" "),
    "Quietfox wants Grim Bane Ruby Ring - 5 exalted");
  assert.equal(r.tag, "", "a trade row carries no tag (design 0001 ruling 2026-11-24)");
  assert.ok(r.title.indexOf("Grim Bane Ruby Ring - 5 exalted") > 0);
});

test("5 open trades with 40-character names fit the 50-word cap with a status line", () => {
  const status = "New trade request from " + NAME40 + ".";
  const v = F.view(snapOf(fiveLong()), NOW, {}, status);
  assert.ok(v.words <= F.WORD_CAP, "words " + v.words);
  assert.equal(v.rows.length, 5);
  v.rows.forEach((r) => {
    assert.ok(r.buyer && r.price, "buyer and price stay");
    assert.ok(/\.\.\.$/.test(r.item), "the item takes the cut: " + r.item);
    assert.ok(r.title.indexOf(ITEM40) > 0, "the full sentence stays in the title");
  });
  // the burst state: 5 short trades, all on screen
  const burst = [trade(1, "Firstbuyer", "Grim Bane Ruby Ring", "5 exalted", NOW - 900),
    trade(2, "Secondbuyer_WithALongAccountName", "Example Unique Quarterstaff of Many Words",
          "40 exalted", NOW - 800),
    trade(3, "Thirdbuyer", "Example Amber Amulet", "12 exalted", NOW - 30),
    trade(4, "Fourthbuyer", "Example Leather Boots", "3 exalted", NOW - 20),
    trade(5, "Fifthbuyer", "Example Iron Ring", "1 exalted", NOW - 10)];
  const b = F.view(snapOf(burst), NOW, {}, "3 new trade requests.");
  assert.ok(b.words <= F.WORD_CAP, "burst words " + b.words);
  assert.equal(b.rows.length, 5);
});

test("the worst rows still fit: unknown buyers, no price set, every step of the ladder", () => {
  const worst = [1, 2, 3, 4, 5].map((i) => ({
    id: i, at: NOW - 600 * i, from: "Unknown player", where: "tab Long Sale Tab Name (1,1)",
    text: "Unknown player wants 25 Greater Orb of Augmentation and Regal - no price set" }));
  const v = F.view(snapOf(worst), NOW, {}, "New trade request from Unknown player.");
  assert.ok(v.words <= F.WORD_CAP, "words " + v.words);
  assert.ok(v.level <= F.LADDER_TOP);
});

test("the ladder drops optional parts in its fixed order, short rows stay whole", () => {
  const t = trade(1, "Quietfox", "Grim Bane Ruby Ring", "5 exalted", NOW - 120, "tab Sale (3,7)");
  const whole = F.view(snapOf([t]), NOW, {}, "");
  assert.equal(whole.level, 0);
  assert.equal(whole.rows[0].right, "tab Sale (3,7), 2m");
  const model = [{ kind: "trade", key: "t1", id: 1, tag: "Trade", buyer: "Quietfox", verb: "wants",
    item: "Grim Bane Ruby Ring", price: "- 5 exalted", isNew: false, tab: "tab Sale",
    pos: "(3,7)", age: "2m", title: "x", from: "Quietfox" }];
  const at = (budget) => F.compose(model, budget);
  assert.equal(at(14).level, 0); // Trade Quietfox wants 4 + 2 + 4 + Dismiss
  let c = at(13);
  assert.deepEqual([c.level, c.rows[0].right], [1, "tab Sale, 2m"]);
  c = at(12);
  assert.deepEqual([c.level, c.rows[0].item], [3, "Grim Bane Ruby..."]);
  c = at(10);
  assert.deepEqual([c.level, c.rows[0].right], [4, "2m"]);
  c = at(8);
  assert.deepEqual([c.level, c.rows[0].item], [5, "Grim..."]);
  c = at(7);
  assert.deepEqual([c.level, c.rows[0].right], [6, ""]);
  c = at(6);
  assert.deepEqual([c.level, c.rows[0].item, c.rows[0].price], [8, "...", "- 5 exalted"]);
  const top = at(-1); // a budget nothing meets: the last step
  assert.equal(top.level, F.LADDER_TOP);
  assert.equal(top.rows[0].item, "...");
  assert.equal(top.rows[0].price, "");
  assert.equal(top.rows[0].buyer, "Quietfox");
  // events: the time goes at step 2, the sentence is cut at step 7
  const ev = [{ kind: "zone", key: "ezone", tag: "Zone", text: "Entered The Grelwood Forest Camp",
                isNew: true, time: "14:00", title: "x" }];
  assert.deepEqual(F.compose(ev, 99).rows[0].right, "new, 14:00");
  assert.deepEqual(F.compose(ev, 7).rows[0].right, "new");
  assert.deepEqual(F.compose(ev, 5).rows[0].text, "Entered The Grelwood...");
});

test("dismissed rows leave at once; an unknown play block falls back to the raw cards", () => {
  const trades = [trade(1, "A", "Ring", "1 exalted", NOW - 5), trade(2, "B", "Belt", "2 exalted", NOW - 4)];
  const v = F.view(snapOf(trades), NOW, { 2: true }, "");
  assert.deepEqual(v.rows.map((r) => r.id), [1]);
  const raw = F.view({ trade_requests: trades }, NOW, {}, "");
  assert.deepEqual(raw.rows.map((r) => r.buyer), ["B", "A"]);
});

/* ---- the DOM ---------------------------------------------------------- */

test("wire: the T heading becomes the head line, one polite status inside the region", () => {
  const ui = setup();
  const h = ui.doc.byId["play-t-h"];
  assert.equal(h.getAttribute("tabindex"), "-1");
  assert.ok(h.className.indexOf("sr-only") < 0);
  assert.ok(find(ui.doc.slot, "feed-head")[0].children.indexOf(h) >= 0);
  const st = ui.status();
  assert.equal(st.getAttribute("role"), "status");
  assert.equal(st.getAttribute("aria-live"), "polite");
  assert.equal(find(ui.doc.region, "feed-status").length, 1);
  assert.equal(ui.all().hidden, true);
});

test("paint: every open trade has a row with its own Dismiss; Dismiss all from 2", () => {
  const ui = setup();
  ui.paint(snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 5)], EVENTS));
  assert.equal(ui.rows().length, 4);
  assert.equal(ui.btns().length, 1);
  assert.equal(ui.all().hidden, true);
  assert.equal(ui.doc.byId["play-t-h"].textContent, "Trades 1");
  ui.paint(snapOf(fiveLong(), EVENTS));
  assert.equal(ui.rows().length, 5);
  assert.equal(ui.btns().length, 5);
  assert.equal(ui.all().hidden, false);
  assert.equal(ui.doc.byId["play-t-h"].textContent, "Trades 5");
  ui.btns().forEach((b) => assert.ok(/^Dismiss trade request from \S+/.test(b.getAttribute("aria-label"))));
  const rows = ui.rows();
  assert.ok(rows.every((r) => r.className.indexOf("edge-accent") >= 0));
  assert.ok(F.words(shownText(ui.doc.region)) <= F.WORD_CAP);
});

test("a long item name: buyer and verb stay whole, only the item truncates (PLAY-FEED-VERB-CLIP)", () => {
  const ui = setup();
  const LONG = "Grim Bane Ruby Ring of the Everlasting Ember and the Quiet Fox of Clearfell";
  ui.paint(snapOf([trade(1, "Quietfox", LONG, "5 exalted", NOW - 5)]));
  const row = ui.rows()[0];
  const buyer = find(row, "feed-buyer")[0];
  const item = find(row, "feed-item")[0];
  const i = row.children.indexOf(buyer);
  const verb = row.children[i + 1];
  // the verb is a bare text node right after the buyer: not inside the
  // item span (the one part that takes the ellipsis) and no element
  assert.equal(verb.nodeType, 3);
  assert.equal(verb.data, "wants");
  assert.equal(row.children[i + 2], item);
  assert.equal(buyer.textContent, "Quietfox");
  assert.ok(item.textContent.indexOf("wants") < 0, "the item span never holds the verb");
  assert.equal(item.getAttribute("title"), LONG, "the item's full name is its title");
  // a trade row stays 6 elements (design 0001): li, buyer, item, price, right, Dismiss
  const elements = (n) => (n.nodeType === 3 ? 0 : 1 + n.children.reduce((a, c) => a + elements(c), 0));
  assert.equal(elements(row), 6);
  // a word ladder cut shortens only the item; buyer and verb stay, the title keeps it all
  const five = fiveLong().map((t) => Object.assign({}, t, { item: LONG,
    text: t.from + " wants " + LONG + " - 1 exalted" }));
  ui.paint(snapOf(five, EVENTS));
  ui.rows().forEach((r) => {
    const b = find(r, "feed-buyer")[0];
    const it = find(r, "feed-item")[0];
    assert.equal(r.children[r.children.indexOf(b) + 1].data, "wants");
    assert.ok(/^Firstbuyer/.test(b.textContent) && b.textContent.indexOf("...") < 0);
    assert.equal(it.getAttribute("title"), LONG);
  });
  // CSS: the item takes the ellipsis and gives way first; the buyer shrinks
  // last; the verb (the row's own text) is set at the title size
  const body = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  assert.ok(/\.feed-item \{ flex: 0 1000 auto; min-width: 3em; \}/.test(body));
  assert.ok(/\.feed-trade \.feed-buyer \{ flex: 0 0\.001 auto; \}/.test(body));
  assert.ok(/\.feed-trade \{[^}]*font-size: var\(--al-fs-title\)/.test(body));
  assert.ok(!/feed-verb/.test(body), "no verb element to clip");
});

test("status: a new request is said once in at most 12 words, never on first paint", () => {
  const ui = setup();
  const one = [trade(1, "A", "Ring", "1 exalted", NOW - 5)];
  ui.paint(snapOf(one));
  assert.equal(ui.status().textContent, "");
  ui.paint(snapOf(one));
  assert.equal(ui.status().textContent, "");
  ui.paint(snapOf(one.concat([trade(2, "Quietfox", "Belt", "2 exalted", NOW - 1)])));
  assert.equal(ui.status().textContent, "New trade request from Quietfox.");
  assert.ok(F.words(ui.status().textContent) <= 12);
  const writes = ui.status().writes.length;
  ui.paint(snapOf(one.concat([trade(2, "Quietfox", "Belt", "2 exalted", NOW - 1)])), NOW + 1);
  assert.equal(ui.status().writes.length, writes, "a tick says nothing again");
});

test("a repaint keeps each row node, so a focused Dismiss keeps its focus", () => {
  const ui = setup();
  const two = [trade(1, "A", "Ring", "1 exalted", NOW - 5), trade(2, "B", "Belt", "2 exalted", NOW - 4)];
  ui.paint(snapOf(two));
  const b = ui.btns()[1];
  b.focus();
  ui.paint(snapOf(two), NOW + 70); // "new" goes, the age shows
  assert.equal(ui.doc.activeElement, b);
  ui.paint(snapOf(two.concat([trade(3, "C", "Cap", "3 exalted", NOW + 71)])), NOW + 72);
  assert.equal(ui.doc.activeElement, b, "a new trade on top never moves focus");
});

test("a keyboard dismiss moves focus to the next row's Dismiss", async () => {
  const ui = setup();
  const three = [trade(1, "A", "Ring", "1 exalted", NOW - 30), trade(2, "B", "Belt", "2 exalted", NOW - 20),
                 trade(3, "C", "Cap", "3 exalted", NOW - 10)];
  ui.paint(snapOf(three));
  // shown newest first: C, B, A; dismiss B (the middle) by Enter
  const btnB = find(ui.rows()[1], "feed-dismiss")[0];
  btnB.focus();
  btnB.click(0);
  assert.deepEqual(ui.calls[0], { method: "POST", path: "/api/trade-dismiss", body: { id: 2 } });
  await flush();
  assert.equal(ui.rows().length, 2, "the row leaves before the next push");
  const btnA = find(ui.rows()[1], "feed-dismiss")[0];
  assert.equal(ui.doc.activeElement, btnA);
  // the push that drops it says nothing and moves nothing
  ui.paint(snapOf([three[0], three[2]]));
  assert.equal(ui.doc.activeElement, btnA);
  assert.equal(ui.status().textContent, "");
});

test("a keyboard dismiss of the last row, or Dismiss all, focuses the T heading", async () => {
  let ui = setup();
  const two = [trade(1, "A", "Ring", "1 exalted", NOW - 30), trade(2, "B", "Belt", "2 exalted", NOW - 20)];
  ui.paint(snapOf(two));
  find(ui.rows()[1], "feed-dismiss")[0].click(0);
  await flush();
  assert.equal(ui.doc.activeElement, ui.doc.byId["play-t-h"]);
  ui = setup();
  ui.paint(snapOf(two, EVENTS));
  ui.all().click(0);
  assert.deepEqual(ui.calls[0].body, { all: true });
  await flush();
  assert.equal(ui.btns().filter((b) => b.parentNode && b.parentNode.parentNode).length, 0);
  assert.equal(ui.doc.activeElement, ui.doc.byId["play-t-h"]);
  assert.equal(ui.all().hidden, true);
  assert.equal(ui.doc.byId["play-t-h"].textContent, "Recent");
});

test("a pointer dismiss moves no focus", async () => {
  const ui = setup();
  ui.paint(snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 30), trade(2, "B", "Belt", "2 exalted", NOW - 20)]));
  find(ui.rows()[0], "feed-dismiss")[0].click(1);
  await flush();
  assert.equal(ui.doc.activeElement, null);
  assert.equal(ui.rows().length, 1);
});

test("a failed dismiss keeps the row and says so in the head line", async () => {
  const ui = setup(() => Promise.reject(new Error("HTTP 500")));
  const warn = console.warn;
  console.warn = () => {};
  try {
    ui.paint(snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 30)]));
    find(ui.rows()[0], "feed-dismiss")[0].click(0);
    await flush();
  } finally {
    console.warn = warn;
  }
  assert.equal(ui.rows().length, 1);
  assert.equal(ui.status().textContent, F.NOT_DISMISSED);
  assert.equal(ui.status().getAttribute("data-shown"), "yes");
  assert.equal(ui.doc.activeElement, null);
  // a tick with the same open list keeps it
  ui.paint(snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 30)]), NOW + 1);
  assert.equal(ui.status().textContent, F.NOT_DISMISSED);
});

test("the Not dismissed line goes when the open list changes or on the next Dismiss", async () => {
  let fail = true;
  const ui = setup(() => (fail ? Promise.reject(new Error("HTTP 500")) : Promise.resolve({})));
  const warn = console.warn;
  console.warn = () => {};
  const one = [trade(1, "A", "Ring", "1 exalted", NOW - 30)];
  try {
    ui.paint(snapOf(one));
    find(ui.rows()[0], "feed-dismiss")[0].click(1);
    await flush();
    assert.equal(ui.status().textContent, F.NOT_DISMISSED);
    // the card expires: the open list changes
    ui.paint(snapOf([]));
    assert.equal(ui.status().textContent, "");
    assert.equal(ui.status().getAttribute("data-shown"), null);
    // fails again, then the next Dismiss click clears it at once
    ui.paint(snapOf(one));
    find(ui.rows()[0], "feed-dismiss")[0].click(1);
    await flush();
    assert.equal(ui.status().getAttribute("data-shown"), "yes");
    fail = false;
    find(ui.rows()[0], "feed-dismiss")[0].click(1);
    assert.equal(ui.status().textContent, "");
    assert.equal(ui.status().getAttribute("data-shown"), null);
  } finally {
    console.warn = warn;
  }
});

test("rows look frozen while the log is idle or AshLight is lost", () => {
  const ui = setup();
  const s = snapOf([trade(1, "A", "Ring", "1 exalted", NOW - 30)]);
  ui.paint(s);
  assert.equal(ui.doc.region.getAttribute("data-stale"), null);
  ui.paint(Object.assign({}, s, { game_idle: true }));
  assert.equal(ui.doc.region.getAttribute("data-stale"), "yes");
  ui.paint(Object.assign({}, s, { offline: true }));
  assert.equal(ui.doc.region.getAttribute("data-stale"), "yes");
  ui.paint(s);
  assert.equal(ui.doc.region.getAttribute("data-stale"), null);
  assert.ok(/#play-t\[data-stale="yes"\] \.feed-row/.test(CSS));
  assert.ok(!/data-fresh/.test(CSS));
});

test("an empty feed shows one muted line", () => {
  const ui = setup();
  ui.paint(snapOf([], null));
  assert.equal(ui.rows().length, 0);
  const empty = find(ui.doc.slot, "feed-empty")[0];
  assert.equal(empty.hidden, false);
  assert.equal(empty.textContent, F.EMPTY);
  assert.equal(F.EMPTY, "Nothing yet. Trades and events show here.");
  assert.equal(ui.doc.byId["play-t-h"].textContent, "Recent");
});

/* ---- the seams -------------------------------------------------------- */

test("registers as region t, retires t-trades, and leaves the legacy helpers alone", () => {
  assert.equal(F.spec.name, "feed");
  assert.equal(F.spec.region, "t");
  assert.deepEqual(F.spec.retires, ["t-trades"]);
  ["wire", "paint", "tick"].forEach((k) => assert.equal(typeof F.spec[k], "function"));
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.ok(!/ALTrades/.test(code), "never calls window.ALTrades");
  assert.ok(!/\.notify\(/.test(code), "does not call ALTabs.notify");
  assert.ok(/"\/api\/trade-dismiss"/.test(code) && /ctx\.api\(/.test(code));
  assert.ok(!/setInterval|setTimeout|clipboard|fetch\(/.test(code), "no timers, clipboard or own fetch");
  assert.ok(/^[\x00-\x7f]*$/.test(SRC) && SRC.indexOf("\r") < 0);
  // registered with a fresh region registry it wires and retires its group
  const R = web.load("regions.js").create({ warn: () => {} });
  R.register(F.create().spec);
  assert.deepEqual(R.names(), ["feed"]);
});

test("feed.css: nothing moves, rows are 32 px, the head 26 px", () => {
  const body = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  assert.ok(!/animation|transition/.test(body));
  assert.ok(/\.feed-row \{[^}]*min-height: 2rem/.test(body));
  assert.ok(/\.feed-head \{[^}]*min-height: var\(--al-lh-title\)/.test(body));
  assert.ok(/^[\x00-\x7f]*$/.test(CSS) && CSS.indexOf("\r") < 0);
  // 2 + 6 + 6 + 26 + 5 x 32 = 200 of the 204 track
  assert.equal(2 + 12 + 26 + F.ROWS * 32, 200);
  assert.equal(F.ROWS, S.FEED_SLOTS);
});
