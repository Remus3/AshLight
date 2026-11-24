/* UI-GLANCE: the dashboard tabs (web/tabs.js) and their page markup, and
   the news hook of web/regions.js that tells them about a new item check,
   trade request or build alert (PLAY-LEGACY-OUT-1 and -2). */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const t = web.load("tabs.js");
const regions = web.load("regions.js");

const HTML = web.source("index.html");
const CSS = web.source("app.css");

function el(id) {
  const node = {
    id, attrs: {}, hidden: false, children: [], listeners: {}, focused: false,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    addEventListener(k, f) { this.listeners[k] = f; },
    replaceChildren(...c) { this.children = c; },
    contains(o) { return o === this || this.children.includes(o); },
    focus() { this.focused = true; },
    querySelector() { return this.markNode || null; }
  };
  node.textContent = "";
  return node;
}

function fakeDoc() {
  const ids = { tabs: el("tabs"), "zone-guide": el("zone-guide") };
  t.TABS.forEach((x) => {
    ids["tab-" + x] = el("tab-" + x);
    ids["tab-" + x].markNode = el("mark-" + x);
    ids["panel-" + x] = el("panel-" + x);
  });
  return {
    ids, activeElement: null, focused: false,
    getElementById: (id) => ids[id] || null,
    hasFocus() { return this.focused; }
  };
}

function memStore(init) {
  const m = Object.assign({}, init);
  return { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = v; }, m };
}

test("pick: a stored tab id comes back, anything else gives Play", () => {
  assert.equal(t.pick("build"), "build");
  assert.equal(t.pick(null), "play");
  assert.equal(t.pick("nope"), "play");
  assert.equal(t.pick("constructor"), "play");
  assert.equal(t.PRIMARY, "play");
  assert.equal(t.TABS[0], "play");
});

test("four tabs (PLAY-TD-19B-FOUR-TABS); a stored items maps to build once", () => {
  assert.deepEqual(t.TABS, ["play", "build", "run", "settings"]);
  assert.equal(t.pick("items"), "build");
  const doc = fakeDoc();
  const store = memStore({ [t.STORE_KEY]: "items" });
  t.start(doc, store);
  assert.equal(t.current(), "build");
  assert.equal(doc.ids["panel-build"].hidden, false);
  assert.equal(store.m[t.STORE_KEY], "build", "the old value is replaced at once");
  t.mark(doc, "items", "new"); // a retired id carries no mark
  assert.deepEqual(Object.keys(doc.ids).filter((k) => k.endsWith("-items")), []);
});

test("step: arrows wrap, Home and End jump, other keys do nothing", () => {
  assert.equal(t.step("ArrowRight", "play"), "build");
  assert.equal(t.step("ArrowRight", "build"), "run");
  assert.equal(t.step("ArrowLeft", "play"), "settings");
  assert.equal(t.step("ArrowRight", "settings"), "play");
  assert.equal(t.step("Home", "items"), "play");
  assert.equal(t.step("End", "run"), "settings");
  assert.equal(t.step("Enter", "run"), null);
});

test("shouldSwitch: only when Play is hidden and the player is not working elsewhere", () => {
  assert.equal(t.shouldSwitch({ current: "play", focusTab: null, pageFocused: false }), false);
  assert.equal(t.shouldSwitch({ current: "build", focusTab: "build", pageFocused: false }), true);
  assert.equal(t.shouldSwitch({ current: "build", focusTab: null, pageFocused: true }), true);
  assert.equal(t.shouldSwitch({ current: "build", focusTab: "build", pageFocused: true }), false);
});

test("start restores the remembered tab, a click switches and is remembered", () => {
  const doc = fakeDoc();
  const store = memStore({ [t.STORE_KEY]: "run" });
  t.start(doc, store);
  assert.equal(t.current(), "run");
  assert.equal(doc.ids["panel-run"].hidden, false);
  assert.equal(doc.ids["panel-play"].hidden, true);
  assert.equal(doc.ids["tab-run"].attrs["aria-selected"], "true");
  assert.equal(doc.ids["tab-run"].attrs.tabindex, "0");
  assert.equal(doc.ids["tab-play"].attrs.tabindex, "-1");
  doc.ids["tab-build"].listeners.click();
  assert.equal(t.current(), "build");
  assert.equal(store.m[t.STORE_KEY], "build");
});

test("arrow keys move and focus the tab; storage that throws is ignored", () => {
  const doc = fakeDoc();
  const bad = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  t.start(doc, bad);
  assert.equal(t.current(), "play");
  let prevented = false;
  doc.ids.tabs.listeners.keydown({ key: "ArrowRight", preventDefault() { prevented = true; } });
  assert.ok(prevented);
  assert.equal(t.current(), "build");
  assert.equal(doc.ids["tab-build"].focused, true);
});

test("notify shows Play when the game has focus, else marks Play new", () => {
  const doc = fakeDoc();
  t.start(doc, memStore({ [t.STORE_KEY]: "build" }));
  doc.focused = true;
  const input = el("x");
  doc.ids["panel-build"].children.push(input);
  doc.activeElement = input;
  assert.equal(t.notify(doc), false);
  assert.equal(t.current(), "build");
  assert.equal(doc.ids["tab-play"].markNode.textContent, "new");
  assert.equal(doc.ids["tab-play"].markNode.hidden, false);
  doc.focused = false;
  assert.equal(t.notify(doc), true);
  assert.equal(t.current(), "play");
  assert.equal(doc.ids["tab-play"].markNode.hidden, true);
});

test("a mark stays while its tab is shown and comes back after", () => {
  const doc = fakeDoc();
  t.start(doc, null);
  t.mark(doc, "settings", "fix");
  assert.equal(doc.ids["tab-settings"].markNode.textContent, "fix");
  t.show(doc, "settings", false);
  assert.equal(doc.ids["tab-settings"].markNode.hidden, true);
  t.show(doc, "play", false);
  assert.equal(doc.ids["tab-settings"].markNode.textContent, "fix");
  t.mark(doc, "settings", "");
  assert.equal(doc.ids["tab-settings"].markNode.hidden, true);
});

test("fill: the one slot (the zone guide in Run); filling it is not news", () => {
  assert.deepEqual(t.SLOTS, ["zone-guide"]);
  const doc = fakeDoc();
  t.start(doc, memStore({ [t.STORE_KEY]: "run" }));
  const node = el("n");
  t.fill(doc, "zone-guide", node);
  assert.equal(doc.ids["zone-guide"].hidden, false);
  assert.equal(t.current(), "run");
  t.fill(doc, "zone-guide", null);
  assert.equal(doc.ids["zone-guide"].hidden, true);
  t.fill(doc, "build-alert", node); // retired slot: ignored
  t.fill(doc, "tabs", node); // not a slot: ignored
  assert.deepEqual(doc.ids.tabs.children, []);
  assert.equal(t.current(), "run");
});

test("the page has a tablist with one tab and one panel per id, Play first", () => {
  assert.match(HTML, /<div id="tabs" class="tabs" role="tablist" aria-label="[^"]+">/);
  const tabs = [...HTML.matchAll(/<button id="tab-([a-z]+)"[^>]*role="tab"/g)].map((m) => m[1]);
  assert.deepEqual(tabs, t.TABS);
  const panels = [...HTML.matchAll(/<div id="panel-([a-z]+)"[^>]*role="tabpanel"[^>]*>/g)];
  assert.deepEqual(panels.map((m) => m[1]), t.TABS);
  panels.forEach((m, i) => {
    assert.ok(m[0].includes('aria-labelledby="tab-' + m[1] + '"'), m[0]);
    assert.equal(/ hidden>$/.test(m[0]), i !== 0, m[0]);
  });
  assert.match(HTML, /<script src="\/web\/tabs.js" defer><\/script>/);
  assert.ok(HTML.indexOf("/web/tabs.js") < HTML.indexOf("/web/app.js"));
  // PLAY-TD-19B-FOUR-TABS (TD-19, F-067): exactly four tabs, these names
  const names = [...HTML.matchAll(/role="tab"[^>]*>([^<]+)</g)].map((m) => m[1].trim());
  assert.deepEqual(names, ["Play", "Build and items", "Run", "Settings"]);
  assert.ok(!HTML.includes("panel-items") && !HTML.includes("tab-items"));
  // the hidden bold copies (F-161) follow the names
  names.forEach((n, i) => {
    assert.ok(CSS.includes("#tab-" + t.TABS[i] + '::after { content: "' + n + '"; }'), n);
  });
  assert.doesNotMatch(CSS, /#tab-items/);
});

test("Play holds only the regions; tools and the full cards live in other tabs", () => {
  const play = HTML.slice(HTML.indexOf('id="panel-play"'), HTML.indexOf('id="panel-build"'));
  ["play-g", "play-c", "play-t", "play-n", "play-b", "play-i", "play-u"].forEach((id) => {
    assert.ok(play.includes('id="' + id + '"'), id);
  });
  ["buildbox", "pricesbox", "toolsbox", "actsbox", "weights", "summarybox", "zone-guide",
    "evalbox", "pricebox"].forEach((id) => {
    assert.ok(!play.includes('id="' + id + '"'), id);
  });
  // PLAY-LEGACY-OUT-2: no legacy group is left; the consent, language, tip
  // and Zone tip cards are gone (regions C and N carry them)
  assert.ok(!HTML.includes("data-legacy"));
  ["consent", "consent-yes", "consent-path", "consent-error", "langbox", "lang-dismiss",
    "hintbox", "hint-text", "campaign-hints"].forEach((id) => {
    assert.ok(!HTML.includes('id="' + id + '"'), id);
  });
  // DATA-GUIDE-ONE-BLOCK: the zone tile prints one guide block; the Zone tip
  // markup and style are gone from every web/ file
  const fs = require("node:fs");
  const path = require("node:path");
  (function scan(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const f = path.join(dir, e.name);
      if (e.isDirectory()) { scan(f); continue; }
      assert.ok(!fs.readFileSync(f, "utf8").includes("zone-note"), f);
    }
  })(web.dir);
  // PLAY-TD-21A-SETTINGS-RAIL: the opt-out left the footer for Settings,
  // Reading and web data, where the bar status word leads
  const foot = HTML.slice(HTML.indexOf("<footer"));
  assert.ok(!foot.includes('id="consent-no"'));
  const reading = HTML.slice(HTML.indexOf('<section id="set-reading"'),
    HTML.indexOf("</section>", HTML.indexOf('<section id="set-reading"')));
  assert.ok(reading.includes('id="consent-no"') && reading.includes('aria-describedby="consent-said"'));
  // moved as they were: Last session first in Run, the zone guide in Act
  // times; PLAY-TD-19B-FOUR-TABS: the Items and prices columns, the full
  // last check first, follow the build columns in Build and items
  const run = HTML.slice(HTML.indexOf('id="panel-run"'), HTML.indexOf('id="panel-settings"'));
  assert.match(run, /^id="panel-run"[^>]*>\s*<div class="col">\s*<!--[\s\S]*?-->\s*<section id="summarybox"/);
  const build = HTML.slice(HTML.indexOf('id="panel-build"'), HTML.indexOf('id="panel-run"'));
  // KINDLER-UI-TABS (adjudicator ruling 2026-11-23): the Build sub-tab group
  // comes first (DOM order = Tab order), then the first card cell
  assert.match(build, /^id="panel-build"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)?<div id="kindler-bar"[^>]*role="group"[\s\S]*?<\/div>\s*<div class="col">\s*<section id="buildbox"/);
  assert.match(build, /<\/div>\s*<div class="col">\s*<!--[\s\S]*?-->\s*<section id="evalbox"/);
  // PLAY-TD-19D-ITEMS-GRID (F-056): the price, value and upgrade boxes are
  // rows of the Last item card and the separate price watch card is gone
  ["buildbox", "healthbox", "searchbox", "evalbox", "eval-result", "price-result", "eval-rows",
    "pricesbox", "prices-list", "weightsbox"].forEach((id) => {
    assert.ok(build.includes('id="' + id + '"'), id);
  });
  ["watchbox", "pricebox", "valuebox", "upgradebox", "movers"].forEach((id) => {
    assert.ok(!HTML.includes('id="' + id + '"'), id);
  });
  assert.ok(build.indexOf('id="searchbox"') < build.indexOf('id="evalbox"'));
  // PLAY-LEGACY-OUT-1: the old strip tiles, trade card and build alert slot are gone
  ["zone", "zone-time", "level", "who", "deaths", "levelups", "session", "flags", "underlevel",
    "trades", "trade-list", "trade-clear", "trade-status", "build-alert"].forEach((id) => {
    assert.ok(!HTML.includes('id="' + id + '"'), id);
  });
  ["g-tiles", "t-trades", "b-alert"].forEach((g) => {
    assert.ok(!HTML.includes('data-legacy="' + g + '"'), g);
  });
  assert.ok(!HTML.includes("/web/trades.js") && !HTML.includes("/web/buildlive.js"));
  // the pace line and the zone guide moved, as they were, to Act times;
  // the character picker sits in the Characters card
  const at = HTML.indexOf('id="actsbox"');
  const acts = HTML.slice(at, HTML.indexOf("</section>", at));
  ["pace", "zone-guide"].forEach((id) => {
    assert.ok(acts.includes('id="' + id + '"'), id);
  });
  const ct = HTML.indexOf('id="charsbox"');
  const chars = HTML.slice(ct, HTML.indexOf("</section>", ct));
  ["char-pick-box", "char-pick"].forEach((id) => {
    assert.ok(chars.includes('id="' + id + '"'), id);
  });
});

test("wide windows get the app shell; the page never uses CSS order", () => {
  assert.match(CSS, /@media \(min-width: 900px\) and \(min-height: 560px\)/);
  assert.match(CSS, /@media \(max-width: 520px\)/);
  assert.doesNotMatch(CSS, /(^|[\s;{])order\s*:/m);
});

test("Play is 7 regions with no panel tab stop; the shown tab keeps its regions", () => {
  // PLAY-TD-09B-SKELETON (F-096): the tab is the stop, not the panel or a column
  const open = HTML.match(/<div id="panel-play"[^>]*>/)[0];
  assert.doesNotMatch(open, /tabindex/);
  assert.doesNotMatch(HTML, /class="play-(main|side)"/);
  const play = HTML.slice(HTML.indexOf('id="panel-play"'), HTML.indexOf('id="panel-build"'));
  const regions = [...play.matchAll(/<section id="play-([a-z])" class="region" data-region="([a-z])"/g)];
  assert.deepEqual(regions.map((m) => m[1]), ["g", "c", "t", "n", "b", "i", "u"]);
  regions.forEach((m) => assert.equal(m[1], m[2]));
  // each region is its heading and one slot, nothing else
  const sections = play.split('<section id="play-').slice(1);
  assert.equal(sections.length, 7);
  sections.forEach((sec) => {
    const body = sec.slice(0, sec.indexOf("</section>"));
    assert.equal((body.match(/<(div|section|p|ul) /g) || []).length, 1, body);
    assert.match(body, /<div class="slot" data-slot="[a-z]"><\/div>/);
  });
});

test("modifier keys pass through the tab row (Alt+Left stays browser Back)", () => {
  const doc = fakeDoc();
  t.start(doc, null);
  let prevented = false;
  doc.ids.tabs.listeners.keydown({ key: "ArrowLeft", altKey: true, preventDefault() { prevented = true; } });
  doc.ids.tabs.listeners.keydown({ key: "Home", ctrlKey: true, preventDefault() { prevented = true; } });
  assert.equal(prevented, false);
  assert.equal(t.current(), "play");
});

test("grace: a recent click in the shown tab holds it; the header line says the news", () => {
  const doc = fakeDoc();
  const handlers = {};
  doc.addEventListener = (k, f) => { handlers[k] = f; };
  doc.ids["tab-news"] = el("tab-news");
  let now = 1000;
  t.setClock(() => now);
  t.start(doc, memStore({ [t.STORE_KEY]: "build" }));
  doc.focused = true;
  const text = el("txt");
  doc.ids["panel-build"].children.push(text);
  handlers.pointerdown({ target: text });
  assert.equal(t.shouldSwitch({ current: "build", focusTab: null, pageFocused: true, recent: true }), false);
  assert.equal(t.notify(doc, "trade request"), false);
  assert.equal(doc.ids["tab-news"].textContent, "New on Play: trade request.");
  // the same news twice is cleared and written again, so it is said again
  const writes = [];
  let cur = doc.ids["tab-news"].textContent;
  Object.defineProperty(doc.ids["tab-news"], "textContent", {
    get() { return cur; }, set(v) { writes.push(v); cur = v; }, configurable: true });
  t.notify(doc, "trade request");
  assert.deepEqual(writes, ["", "New on Play: trade request."]);
  now += t.GRACE_MS + 1;
  assert.equal(t.notify(doc, "item check"), true);
  assert.equal(t.current(), "play");
  assert.equal(doc.ids["tab-news"].textContent, "Showing Play. Item check.");
  t.setClock(() => Date.now());
});

/* ---- PLAY-TD-22B-TAB-FOCUS (TD-22, F-096, design G-13) ------------------ */

function graceDoc(storedTab) {
  const doc = fakeDoc();
  const handlers = {};
  doc.addEventListener = (k, f) => { handlers[k] = f; };
  doc.ids["tab-news"] = el("tab-news");
  t.TABS.forEach((x) => doc.ids.tabs.children.push(doc.ids["tab-" + x]));
  const writes = [];
  let cur = "";
  Object.defineProperty(doc.ids["tab-news"], "textContent", {
    get() { return cur; }, set(v) { writes.push(v); cur = v; }, configurable: true });
  t.start(doc, memStore({ [t.STORE_KEY]: storedTab }));
  return { doc, handlers, writes };
}

test("the automatic return never fires within 10 s of a key press in the tab row", () => {
  let now = 5000;
  t.setClock(() => now);
  const { doc, handlers } = graceDoc("play");
  doc.focused = true;
  // the player arrows from Play to Run in the tab row
  handlers.keydown({ target: doc.ids["tab-play"] });
  doc.ids.tabs.listeners.keydown({ key: "ArrowRight", preventDefault() {} });
  doc.ids.tabs.listeners.keydown({ key: "ArrowRight", preventDefault() {} });
  assert.equal(t.current(), "run");
  doc.activeElement = doc.ids["tab-run"];
  doc.ids["tab-run"].focused = false;
  [0, 1, 5000, t.GRACE_MS - 1].forEach((d) => {
    now = 5000 + d;
    assert.equal(t.notify(doc, "trade request"), false, "at +" + d + " ms");
    assert.equal(t.current(), "run");
    assert.equal(doc.ids["tab-run"].focused, false, "focus stays where the player is");
  });
  // the game took focus right after the key press: still held by the grace
  doc.focused = false;
  now = 5000 + t.GRACE_MS - 1;
  assert.equal(t.notify(doc, "item check"), false);
  assert.equal(t.current(), "run");
  assert.equal(doc.ids["tab-play"].focused, false);
  t.setClock(() => Date.now());
});

test("after the grace, focus on the tab row moves to the Play tab, said once", () => {
  let now = 1000;
  t.setClock(() => now);
  const { doc, handlers, writes } = graceDoc("build");
  doc.focused = true;
  handlers.keydown({ target: doc.ids["tab-build"] });
  doc.activeElement = doc.ids["tab-build"];
  now += t.GRACE_MS + 1;
  writes.length = 0;
  assert.equal(t.notify(doc, "trade request"), true);
  assert.equal(t.current(), "play");
  assert.equal(doc.ids["tab-play"].focused, true, "focus follows to the Play tab");
  assert.equal(doc.ids["tab-play"].attrs.tabindex, "0");
  assert.equal(doc.ids["tab-news"].textContent, "Showing Play. Trade request.");
  assert.equal(writes.filter((w) => w.startsWith("Showing Play")).length, 1, writes.join("|"));
  // Play is shown now: more news writes nothing more
  writes.length = 0;
  assert.equal(t.notify(doc, "build alert"), false);
  assert.deepEqual(writes, []);
  t.setClock(() => Date.now());
});

test("a focus inside a panel is never moved by the automatic return", () => {
  let now = 1000;
  t.setClock(() => now);
  const { doc } = graceDoc("settings");
  const field = el("field");
  field.focus = () => { throw new Error("a panel focus is not moved"); };
  doc.ids["panel-settings"].children.push(field);
  doc.activeElement = field;
  now += t.GRACE_MS + 1;
  // the page has focus and the player sits in the panel: Play only gets its word
  doc.focused = true;
  assert.equal(t.notify(doc, "trade request"), false);
  assert.equal(t.current(), "settings");
  assert.equal(doc.ids["tab-play"].markNode.textContent, "new");
  // the game has focus: Play shows, but no element is focused
  doc.focused = false;
  assert.equal(t.notify(doc, "item check"), true);
  assert.equal(t.current(), "play");
  t.TABS.forEach((x) => assert.equal(doc.ids["tab-" + x].focused, false, x));
  assert.equal(doc.ids["tab-news"].textContent, "Showing Play. Item check.");
  t.setClock(() => Date.now());
});

test("a return with no focus anywhere moves none; empty news still says Showing Play", () => {
  let now = 1000;
  t.setClock(() => now);
  const { doc } = graceDoc("run");
  doc.focused = false;
  now += t.GRACE_MS + 1;
  assert.equal(t.notify(doc, ""), true);
  t.TABS.forEach((x) => assert.equal(doc.ids["tab-" + x].focused, false, x));
  assert.equal(doc.ids["tab-news"].textContent, "Showing Play.");
  t.setClock(() => Date.now());
});

test("a filled slot node carries its own words, not only an edge", () => {
  const at = HTML.indexOf('<div id="zone-guide"');
  const before = HTML.slice(at - 400, at);
  assert.match(web.source("tabs.js"), /must\s+carry its own words/);
  assert.ok(before.includes("ALTabs.fill"), before);
});

/* ---- the news hook (web/regions.js, PLAY-LEGACY-OUT-1) ------------------ */

test("news: a new trade id or new build alert words, never on the first push", () => {
  const seen = regions.seen;
  const news = regions.news;
  assert.deepEqual(seen({}), { check: "", trades: [], alert: "" });
  assert.deepEqual(seen(null), { check: "", trades: [], alert: "" });
  assert.deepEqual(seen({ trade_requests: [{ id: 3, from: "A" }, null, { id: "x" }],
    build_alert: { kind: "stale", text: "Old build." } }),
  { check: "", trades: ["3", "x"], alert: "Old build." });
  assert.equal(seen({ build_alert: { text: 5 } }).alert, "");
  const one = seen({ trade_requests: [{ id: 1 }] });
  const two = seen({ trade_requests: [{ id: 1 }, { id: 2 }] });
  assert.equal(news(null, two), "", "the first push is the baseline");
  assert.equal(news(one, two), "trade request");
  assert.equal(news(two, one), "", "a dismiss or an expiry is no news");
  assert.equal(news(two, two), "");
  const alertA = seen({ trade_requests: [{ id: 1 }], build_alert: { text: "Old build." } });
  const alertB = seen({ trade_requests: [{ id: 1 }], build_alert: { text: "Wrong class." } });
  assert.equal(news(one, alertA), "build alert");
  assert.equal(news(alertA, alertA), "");
  assert.equal(news(alertA, alertB), "build alert");
  assert.equal(news(alertA, one), "", "a cleared alert is no news");
  const both = seen({ trade_requests: [{ id: 1 }, { id: 9 }], build_alert: { text: "Old build." } });
  assert.equal(news(one, both), "trade request and build alert");
});

test("news: a new item check (PLAY-LEGACY-OUT-2 moved it from app.js to the hook)", () => {
  const seen = regions.seen;
  const news = regions.news;
  assert.equal(seen({ eval: { id: 7 } }).check, "7");
  assert.equal(seen({ eval: { id: "a1" } }).check, "a1");
  assert.equal(seen({ eval: { id: null } }).check, "");
  assert.equal(seen({ eval: "x" }).check, "");
  const none = seen({});
  const a = seen({ eval: { id: "a" } });
  const b = seen({ eval: { id: "b" } });
  assert.equal(news(null, a), "", "a check already there at the first push is the baseline");
  assert.equal(news(none, a), "item check");
  assert.equal(news(a, a), "", "the same check pushed again is no news");
  assert.equal(news(a, b), "item check");
  assert.equal(news(a, none), "", "a cleared check is no news");
  const all = seen({ eval: { id: "c" }, trade_requests: [{ id: 2 }], build_alert: { text: "Old." } });
  assert.equal(news(none, all), "item check, trade request and build alert");
  const two = seen({ eval: { id: "c" }, trade_requests: [{ id: 2 }] });
  assert.equal(news(none, two), "item check and trade request");
});

test("the hook shows Play for a new item check after the first push", () => {
  const reg = regions.create({ warn: () => {} });
  const told = [];
  const doc = { querySelectorAll: () => [] };
  reg.start(doc, { tabs: { notify: (d, what) => told.push(what) } });
  reg.paint(doc, { eval: { id: 1 } }, 0);
  assert.deepEqual(told, [], "baseline");
  reg.paint(doc, { eval: { id: 1 } }, 0);
  assert.deepEqual(told, []);
  reg.paint(doc, { eval: { id: 2 } }, 0);
  assert.deepEqual(told, ["item check"]);
});

test("the hook tells the tabs once per push, after the painters", () => {
  const reg = regions.create({ warn: () => {} });
  const order = [];
  const told = [];
  reg.register({ name: "feed", region: "t", paint: () => order.push("paint") });
  const doc = { querySelectorAll: () => [] };
  reg.start(doc, { tabs: { notify: (d, what) => { order.push("notify"); told.push([d, what]); } } });
  reg.paint(doc, { trade_requests: [{ id: 1 }] }, 0);
  assert.deepEqual(told, [], "baseline");
  reg.paint(doc, { trade_requests: [{ id: 1 }, { id: 2 }] }, 0);
  assert.deepEqual(told, [[doc, "trade request"]]);
  assert.deepEqual(order, ["paint", "paint", "notify"]);
  reg.paint(doc, { trade_requests: [{ id: 2 }], build_alert: { text: "Old build." } }, 0);
  assert.deepEqual(told[1], [doc, "build alert"]);
  assert.equal(told.length, 2);
  // no tabs helper on the page: nothing to tell, nothing thrown
  const bare = regions.create({ warn: () => { throw new Error("no warn expected"); } });
  bare.start(doc, { tabs: null });
  bare.paint(doc, {}, 0);
  bare.paint(doc, { trade_requests: [{ id: 1 }] }, 0);
});

test("the hook marks Play new while another tab is in use, else shows Play", () => {
  const doc = fakeDoc();
  doc.ids["tab-news"] = el("tab-news");
  doc.querySelectorAll = () => [];
  t.setClock(() => 1000);
  t.start(doc, memStore({ [t.STORE_KEY]: "build" }));
  doc.focused = true;
  const input = el("i");
  doc.ids["panel-build"].children.push(input);
  doc.activeElement = input;
  const reg = regions.create({ warn: () => {} });
  reg.start(doc, { tabs: t });
  reg.paint(doc, { trade_requests: [] }, 0);
  reg.paint(doc, { trade_requests: [{ id: 7, from: "Bo" }] }, 0);
  assert.equal(t.current(), "build");
  assert.equal(doc.ids["tab-news"].textContent, "New on Play: trade request.");
  doc.focused = false;
  reg.paint(doc, { trade_requests: [{ id: 7 }], build_alert: { text: "Old build." } }, 0);
  assert.equal(t.current(), "play");
  t.setClock(() => Date.now());
});

test("no other dashboard file tells the tabs about checks, trades or build alerts", () => {
  const app = web.source("app.js");
  assert.doesNotMatch(app, /\.notify\(/);
  assert.doesNotMatch(app, /notify\(document, "trade request"\)|notify\(document, "build alert"\)/);
  assert.doesNotMatch(app, /ALTrades|ALBuildLive|renderTrades|dismissTrade/);
  assert.match(web.source("regions.js"), /tabs\.notify\(doc, what\)/);
});
