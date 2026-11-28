/* UTIL-MAPS / UTIL-DEATHS: exact output of the dashboard map run and death
   recap helpers (web/runs.js). The core sends the sentences; these only
   format. PLAY-TD-20A-RUN-GRID (TD-20): the Maps and Deaths cards are
   fixed cells of the Run grid; their lists page at 10 rows (8 compact)
   and the summary and map ladders are pages of the Maps card. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const r = web.load("runs.js");

const MAPS = {
  count: 2, done: 1,
  current: { name: "Savannah", area_level: 66, time_s: 300, deaths: 0, inside: true },
  recent: [{ name: "Crypt", area_level: 65, time_s: 390, deaths: 1 }],
  avg_s: 390, avg_text: "Average map: 6:30 over 1 finished map.",
  deaths_text: "1 death in maps.",
  empty_text: "No maps yet. Map times start by themselves when you open a map."
};

test("duration matches the zone timer form", () => {
  assert.equal(r.duration(0), "0:00");
  assert.equal(r.duration(390), "6:30");
  assert.equal(r.duration(3725), "1:02:05");
  assert.equal(r.duration(null), "--:--");
});

test("liveTime counts up only while the player is in the map", () => {
  assert.equal(r.liveTime(MAPS.current, 1000, 1010), 310);
  assert.equal(r.liveTime(Object.assign({}, MAPS.current, { inside: false }), 1000, 1010), 300);
  assert.equal(r.liveTime(null, 1000, 1010), null);
});

test("mapRows: open map first, then finished maps", () => {
  assert.deepEqual(r.mapRows(MAPS, 1000, 1005), [
    { name: "Savannah", level: "66", time: "5:05", deaths: "0",
      note: "now", current: true },
    { name: "Crypt", level: "65", time: "6:30", deaths: "1",
      note: "", current: false }
  ]);
  const out = Object.assign({}, MAPS, {
    current: Object.assign({}, MAPS.current, { inside: false }) });
  assert.equal(r.mapRows(out, 1000, 1005)[0].note, "paused");
  const nolevel = { current: null, recent: [{ name: "Crypt", area_level: null, time_s: 60, deaths: 0 }] };
  assert.equal(r.mapRows(nolevel, 0, 0)[0].level, "unknown");
  assert.equal(r.levelText(undefined), "unknown");
  assert.equal(r.levelText(65), "65");
  assert.deepEqual(r.mapRows(null, 0, 0), []);
});

test("deathLines prints the core's sentences in order", () => {
  const recap = { recent: [
    { text: "Died in Crypt (area level 65), 0:05 into the zone." },
    { text: "Died in Savannah (area level 66) at level 72." }
  ], worst_text: "", empty_text: "No deaths this session." };
  assert.deepEqual(r.deathLines(recap), [
    "Died in Crypt (area level 65), 0:05 into the zone.",
    "Died in Savannah (area level 66) at level 72."
  ]);
  assert.deepEqual(r.deathLines(null), []);
});

test("recapFoot joins the worst zone and the deaths before reading (UX-NEW-CARDS)", () => {
  assert.equal(r.recapFoot(null), "");
  assert.equal(r.recapFoot({ worst_text: "", earlier_text: "" }), "");
  assert.equal(r.recapFoot({ worst_text: "Most deaths: Crypt (2).", earlier_text: "" }),
    "Most deaths: Crypt (2).");
  assert.equal(r.recapFoot({ worst_text: "Most deaths: Crypt (2).",
    earlier_text: "1 death came before AshLight started reading." }),
    "Most deaths: Crypt (2). 1 death came before AshLight started reading.");
});

test("mapsSummary adds maps per hour between average and deaths (UTIL-MAPRUN)", () => {
  assert.equal(r.mapsSummary(null), "");
  assert.equal(r.mapsSummary(MAPS), "Average map: 6:30 over 1 finished map. 1 death in maps.");
  const rate = Object.assign({}, MAPS, { rate_text: "4.0 maps per hour since the first map." });
  assert.equal(r.mapsSummary(rate),
    "Average map: 6:30 over 1 finished map. 4.0 maps per hour since the first map. 1 death in maps.");
});

/* ---- a small fake DOM: enough for the card pages and the pagers -------- */
function matches(n, sel) {
  let m;
  if ((m = /^\[([\w-]+)="([^"]*)"\]$/.exec(sel))) { return n.attrs[m[1]] === m[2]; }
  if ((m = /^\[([\w-]+)\]$/.exec(sel))) { return m[1] in n.attrs; }
  if (sel.charAt(0) === ".") { return n.className.split(/\s+/).includes(sel.slice(1)); }
  return n.tagName === sel.toUpperCase();
}

function fakeDoc(size) {
  const doc = { activeElement: null, els: {} };
  doc.createElement = (tag) => {
    const n = {
      tagName: tag.toUpperCase(), className: "", hidden: false, children: [], parentNode: null,
      attrs: {}, listeners: {}, _text: "", value: "",
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); },
      set textContent(v) { this.children = []; this._text = String(v); },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
      replaceChildren(...kids) { this.children = []; this._text = ""; kids.forEach((k) => this.appendChild(k)); },
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") { doc.els[v] = this; } },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      hasAttribute(k) { return k in this.attrs; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
      contains(x) { return x === this || this.walk().includes(x); },
      walk(out) {
        out = out || [];
        this.children.forEach((c) => { out.push(c); if (c.walk) { c.walk(out); } });
        return out;
      },
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
      querySelectorAll(sel) { return this.walk().filter((c) => matches(c, sel)); },
      focus() { doc.activeElement = this; }
    };
    return n;
  };
  doc.getElementById = (id) => doc.els[id] || null;
  doc.defaultView = { getComputedStyle: () => ({ getPropertyValue: () => size || "full" }) };
  return doc;
}

/* el("div", {id, class, ...attrs}, children) */
function mk(doc, tag, attrs, kids) {
  const n = doc.createElement(tag);
  Object.keys(attrs || {}).forEach((k) => {
    if (k === "class") { n.className = attrs[k]; } else if (k === "hidden") { n.hidden = !!attrs[k]; } else {
      n.setAttribute(k, attrs[k]);
    }
  });
  (kids || []).forEach((k) => n.appendChild(k));
  return n;
}

/* The Maps and Deaths cards as web/index.html builds them. */
function runCards(size) {
  const d = fakeDoc(size);
  const page = (name, label, kids, id) => mk(d, "div", Object.assign({ class: "card-page", "data-page": name,
    "data-label": label, hidden: name !== "main" }, id ? { id } : {}), kids);
  const head = (title) => mk(d, "div", { class: "card-head" }, [
    (() => { const h = mk(d, "h2", {}); h.textContent = title; return h; })(),
    mk(d, "span", { class: "card-sub", "data-card-sub": "" }),
    mk(d, "button", { class: "card-back", "data-card-back": "", hidden: true })]);
  mk(d, "section", { id: "mapsbox", class: "card grid-card", "data-home": "main" }, [
    head("Maps"),
    page("main", "", [mk(d, "p", { id: "maps-empty" }), mk(d, "div", { id: "maps-rows", hidden: true }),
      mk(d, "div", { class: "card-foot" }, [
        mk(d, "button", { "data-card-open": "summary", id: "open-summary" }),
        mk(d, "button", { "data-card-open": "ladder", id: "open-ladder" }),
        mk(d, "button", { "data-card-open": "saved", id: "ladder-all-open", hidden: true })])]),
    page("summary", "Map summary", [mk(d, "p", { id: "maps-summary" })]),
    page("ladder", "By map level, this session", [mk(d, "p", { id: "ladder-text" }),
      mk(d, "div", { id: "ladder-rows" })], "ladder"),
    page("saved", "By map level, all saved sessions", [mk(d, "p", { id: "ladder-all-text" }),
      mk(d, "div", { id: "ladder-all-rows" })], "ladder-all"),
    page("bymap", "By map name", [mk(d, "p", { id: "bymap-text" }),
      mk(d, "div", { id: "bymap-rows" })], "bymap")
  ]);
  mk(d, "section", { id: "deathsbox", class: "card grid-card", "data-home": "main" }, [
    head("Deaths"),
    page("main", "", [mk(d, "p", { id: "deaths-empty" }), mk(d, "div", { id: "deaths-list", hidden: true }),
      mk(d, "p", { id: "deaths-worst", hidden: true })])
  ]);
  return d;
}

const listOf = (d, id) => d.getElementById(id).children[0].children[0]; // host > ul
const texts = (ul) => ul.children.map((li) => li.textContent);
const LADDER = { levels: [
  { area_level: 70, maps: 3, deaths: 1, median_text: "6:30", level_ups: 2 },
  { area_level: 69, maps: 1, deaths: 0, median_text: null, level_ups: 1 }],
text: "Highest map level: 70, over 4 maps.", empty_text: "" };

test("mapText and ladderText: one line each, counts worded", () => {
  const rows = r.mapRows(MAPS, 1000, 1005);
  assert.equal(r.mapText(rows[0]), "Savannah (now): level 66, 5:05, 0 deaths");
  assert.equal(r.mapText(rows[1]), "Crypt: level 65, 6:30, 1 death");
  assert.deepEqual(r.ladderRows(LADDER).map(r.ladderText), [
    "Level 70: 3 maps, 1 death, median 6:30, 2 level-ups",
    "Level 69: 1 map, 0 deaths, median --:--, 1 level-up"]);
  assert.equal(r.plural(2, "map"), "2 maps");
  assert.equal(r.plural(undefined, "map"), "0 maps");
});

test("paint: the Maps card's rows, live tick, summary and ladder pages", () => {
  const d = runCards();
  const snap = { now: 1000, maps: Object.assign({}, MAPS, { ladder: LADDER, ladder_all: null }),
    death_recap: null };
  r.paint(d, snap, 1005, true);
  assert.deepEqual(texts(listOf(d, "maps-rows")),
    ["Savannah (now): level 66, 5:05, 0 deaths", "Crypt: level 65, 6:30, 1 death"]);
  assert.equal(d.getElementById("maps-empty").hidden, true);
  r.paint(d, snap, 1010, false);
  assert.equal(texts(listOf(d, "maps-rows"))[0], "Savannah (now): level 66, 5:10, 0 deaths");
  assert.equal(d.getElementById("maps-summary").textContent,
    "Average map: 6:30 over 1 finished map. 1 death in maps.");
  assert.deepEqual(texts(listOf(d, "ladder-rows")), [
    "Level 70: 3 maps, 1 death, median 6:30, 2 level-ups",
    "Level 69: 1 map, 0 deaths, median --:--, 1 level-up"]);
  assert.equal(d.getElementById("ladder-text").textContent, LADDER.text);
  assert.equal(d.getElementById("ladder-text").getAttribute("title"), LADDER.text);
  // the saved sessions page exists only while run history is on
  assert.equal(d.getElementById("ladder-all-open").hidden, true);
  const withAll = Object.assign({}, snap, { maps: Object.assign({}, snap.maps, { ladder_all: LADDER }) });
  r.paint(d, withAll, 1010, true);
  assert.equal(d.getElementById("ladder-all-open").hidden, false);
  // run history goes off while its page shows: the card goes back home
  d.getElementById("ladder-all-open").click();
  assert.equal(d.getElementById("mapsbox").getAttribute("data-shown"), "saved");
  r.paint(d, snap, 1010, true);
  assert.equal(d.getElementById("mapsbox").getAttribute("data-shown"), "main");
  // no maps yet: the empty sentence in place of the list and on the summary page
  r.paint(d, { now: 1, maps: { current: null, recent: [], empty_text: MAPS.empty_text }, death_recap: null }, 1, true);
  assert.equal(d.getElementById("maps-rows").hidden, true);
  assert.equal(d.getElementById("maps-empty").textContent, MAPS.empty_text);
  assert.equal(d.getElementById("maps-summary").textContent, MAPS.empty_text);
});

test("the map list pages at 10 rows (8 compact); a press opens the summary page", () => {
  const recent = [];
  for (let i = 0; i < 11; i += 1) { recent.push({ name: "Map " + i, area_level: 65, time_s: 60, deaths: 0 }); }
  const maps = Object.assign({}, MAPS, { recent });
  ["full", "compact"].forEach((size) => {
    const d = runCards(size);
    r.paint(d, { now: 1000, maps, death_recap: null }, 1000, true);
    assert.equal(listOf(d, "maps-rows").children.length, size === "full" ? 10 : 8, size);
    assert.equal(d.getElementById("maps-rows").children[0].children[1].children[0].textContent,
      size === "full" ? "1-10 of 12" : "1-8 of 12");
  });
  const d = runCards();
  r.paint(d, { now: 1000, maps, death_recap: null }, 1000, true);
  d.getElementById("open-summary").click();
  const shown = d.getElementById("mapsbox").querySelectorAll(".card-page").filter((p) => !p.hidden);
  assert.deepEqual(shown.map((p) => p.getAttribute("data-page")), ["summary"]);
  assert.equal(d.getElementById("mapsbox").querySelector("[data-card-sub]").textContent, "Map summary");
});

test("paint: the Deaths card's recap rows and the most deaths line under them", () => {
  const d = runCards();
  const recap = { recent: [
    { text: "Died in Crypt (area level 65), 0:05 into the zone." },
    { text: "Died in Crypt (area level 65) at level 70." }],
  worst_text: "Most deaths: Crypt (2).", earlier_text: "", empty_text: "No deaths this session." };
  r.paint(d, { now: 1, maps: null, death_recap: recap }, 1, true);
  assert.deepEqual(texts(listOf(d, "deaths-list")), [
    "Died in Crypt (area level 65), 0:05 into the zone.",
    "Died in Crypt (area level 65) at level 70."]);
  const worst = d.getElementById("deaths-worst");
  assert.equal(worst.hidden, false);
  assert.equal(worst.textContent, "Most deaths: Crypt (2).");
  assert.equal(worst.getAttribute("title"), "Most deaths: Crypt (2).");
  // the list shows the core's sentence (zone and level first); the time
  // of a death rides in the whole text after it
  assert.equal(r.deathText({ text: "Died." }), "Died.");
  assert.equal(d.getElementById("deaths-empty").hidden, true);
  // a time comes first when the death has one
  assert.match(r.deathText({ at: 1700000000, text: "Died." }), /^Died\. At \d{1,2}:\d{2}.*\.$/);
  r.paint(d, { now: 1, maps: null, death_recap: Object.assign({}, recap, { recent: [], worst_text: "" }) }, 1, true);
  assert.equal(d.getElementById("deaths-list").hidden, true);
  assert.equal(d.getElementById("deaths-empty").textContent, "No deaths this session.");
  assert.equal(worst.hidden, true);
});

test("the Maps and Deaths cards: pages in the markup, no table, no fold", () => {
  const html = web.source("index.html");
  const at = (id) => html.indexOf('id="' + id + '"');
  const maps = html.slice(at("mapsbox"), html.indexOf("</section>", at("mapsbox")));
  ["summary", "ladder", "saved", "bymap"].forEach((p) => {
    assert.ok(maps.includes('data-card-open="' + p + '"') && maps.includes('data-page="' + p + '"'), p);
  });
  ["maps-rows", "ladder-rows", "ladder-all-rows", "bymap-rows"].forEach((id) => {
    assert.ok(maps.includes('id="' + id + '" class="pager-slot"'), id);
  });
  const deaths = html.slice(at("deathsbox"), html.indexOf("</section>", at("deathsbox")));
  assert.ok(deaths.includes('id="deaths-list" class="pager-slot"'));
  assert.ok(deaths.includes('id="deaths-worst" class="row-meta one-line"'));
  [maps, deaths].forEach((box) => assert.ok(!/<table|<details/.test(box)));
});

/* UTIL-MAP-STATS (research 0064 G5): the By map page shows the saved
   sessions' table while run history is on, else this session's; each row
   is the core's sentence plus the local time of its last run. */
test("paint: the By map page, saved table first, last run as local time", () => {
  const d = runCards();
  const now = new Date(2026, 10, 16, 21, 40, 0).getTime() / 1000;
  const today = new Date(2026, 10, 16, 21, 20, 0).getTime() / 1000;
  const older = new Date(2026, 10, 14, 9, 5, 0).getTime() / 1000;
  const session = { areas: [{ area_id: "MapBog", text: "Bog: 2 runs, 2 deaths, median 4:00",
    last_at: today }], text: "This session: 1 map. Median time counts finished runs.",
  empty_text: "" };
  const saved = { areas: [
    { area_id: "MapBog", text: "Bog: 5 runs, 2 deaths, median 4:00", last_at: today },
    { area_id: "MapCrypt", text: "Crypt: 1 run, 0 deaths, median 6:00", last_at: older },
    { area_id: "MapAsh", text: "Ash: 1 run, 0 deaths, no finished run yet", last_at: null }],
  text: "All saved sessions: 3 maps. Median time counts finished runs.", empty_text: "" };
  const maps = Object.assign({}, MAPS, { ladder: Object.assign({}, LADDER, { by_map: session }),
    ladder_all: null });
  r.paint(d, { now, maps, death_recap: null }, now, true);
  assert.deepEqual(texts(listOf(d, "bymap-rows")), ["Bog: 2 runs, 2 deaths, median 4:00, last run 21:20"]);
  assert.equal(d.getElementById("bymap-text").textContent, session.text);
  const withAll = Object.assign({}, maps, { ladder_all: Object.assign({}, LADDER, { by_map: saved }) });
  r.paint(d, { now, maps: withAll, death_recap: null }, now, true);
  assert.deepEqual(texts(listOf(d, "bymap-rows")), [
    "Bog: 5 runs, 2 deaths, median 4:00, last run 21:20",
    "Crypt: 1 run, 0 deaths, median 6:00, last run 2026-11-14 09:05",
    "Ash: 1 run, 0 deaths, no finished run yet"]);
  assert.equal(d.getElementById("bymap-text").getAttribute("title"), saved.text);
  // no maps yet: the core's empty sentence, no rows
  const empty = { areas: [], text: "", empty_text: "No maps yet. Each map shows here by itself as you play it." };
  r.paint(d, { now, maps: Object.assign({}, MAPS, { ladder: Object.assign({}, LADDER, { by_map: empty }) }),
    death_recap: null }, now, true);
  assert.equal(d.getElementById("bymap-rows").hidden, true);
  assert.equal(d.getElementById("bymap-text").textContent, empty.empty_text);
  assert.equal(r.byMap(null), null);
});
