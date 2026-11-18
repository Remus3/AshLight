/* UI-GLANCE: the dashboard tabs (web/tabs.js) and their page markup. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const t = require("../../web/tabs.js");

const WEB = path.join(__dirname, "..", "..", "web");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "app.css"), "utf8");

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
  const ids = { tabs: el("tabs"), "zone-guide": el("zone-guide"), "build-alert": el("build-alert") };
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
  assert.equal(t.PRIMARY, "play");
  assert.equal(t.TABS[0], "play");
});

test("step: arrows wrap, Home and End jump, other keys do nothing", () => {
  assert.equal(t.step("ArrowRight", "play"), "run");
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
  const store = memStore({ [t.STORE_KEY]: "items" });
  t.start(doc, store);
  assert.equal(t.current(), "items");
  assert.equal(doc.ids["panel-items"].hidden, false);
  assert.equal(doc.ids["panel-play"].hidden, true);
  assert.equal(doc.ids["tab-items"].attrs["aria-selected"], "true");
  assert.equal(doc.ids["tab-items"].attrs.tabindex, "0");
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
  assert.equal(t.current(), "run");
  assert.equal(doc.ids["tab-run"].focused, true);
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

test("fill: the two Play slots; a build alert shows Play", () => {
  const doc = fakeDoc();
  t.start(doc, memStore({ [t.STORE_KEY]: "run" }));
  const node = el("n");
  t.fill(doc, "zone-guide", node);
  assert.equal(doc.ids["zone-guide"].hidden, false);
  assert.equal(t.current(), "run");
  t.fill(doc, "build-alert", node);
  assert.equal(t.current(), "play");
  t.fill(doc, "build-alert", null);
  assert.equal(doc.ids["build-alert"].hidden, true);
  t.fill(doc, "tabs", node); // not a slot: ignored
  assert.deepEqual(doc.ids.tabs.children, []);
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
});

test("Play holds the glance cards and the two slots; tools live in other tabs", () => {
  const play = HTML.slice(HTML.indexOf('id="panel-play"'), HTML.indexOf('id="panel-run"'));
  ["consent", "zone", "level", "deaths", "session", "zone-guide", "build-alert", "trades",
    "trade-status", "hintbox", "evalbox", "pricebox", "zone-note-box"].forEach((id) => {
    assert.ok(play.includes('id="' + id + '"'), id);
  });
  ["buildbox", "pricesbox", "toolsbox", "actsbox", "weights"].forEach((id) => {
    assert.ok(!play.includes('id="' + id + '"'), id);
  });
});

test("wide windows get the app shell; the page never uses CSS order", () => {
  assert.match(CSS, /@media \(min-width: 900px\) and \(min-height: 560px\)/);
  assert.match(CSS, /@media \(max-width: 520px\)/);
  assert.doesNotMatch(CSS, /(^|[\s;{])order\s*:/m);
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
  assert.equal(doc.ids["tab-news"].textContent, "");
  t.setClock(() => Date.now());
});

test("a build alert node carries its own words, not only the warn edge", () => {
  const before = HTML.slice(HTML.indexOf('id="build-alert"') - 400, HTML.indexOf('id="build-alert"'));
  assert.match(fs.readFileSync(path.join(WEB, "tabs.js"), "utf8"), /must\s+carry its own words/);
  assert.ok(before.includes("ALTabs.fill"), before);
});
