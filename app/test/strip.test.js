/* PLAY-TD-10-STRIP (web/strip.js, F-087, F-159): region G prints zone,
   level, deaths and session from snap.play.strip and the snapshot numbers,
   the bar carries the character, stale or empty values are marked
   (body[data-fresh=no], data-empty), and the bar word is neutral while ok.
   Never a clipboard read, a network call, a timer or ALTabs.notify. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ST = require("../../web/strip.js");
const R = require("../../web/regions.js");

const WEB = path.join(__dirname, "..", "..", "web");
const SRC = fs.readFileSync(path.join(WEB, "strip.js"), "utf8");
const CSS = fs.readFileSync(path.join(WEB, "strip.css"), "utf8");
const HTML = fs.readFileSync(path.join(WEB, "index.html"), "utf8");

/* A small DOM: ids, classes, children, attributes, hidden. */
function makeDoc() {
  const doc = { byId: {}, all: [] };
  function elem(tag) {
    const n = {
      tagName: tag.toUpperCase(), attrs: {}, children: [], parentNode: null,
      hidden: false, textContent: "",
      get id() { return this.attrs.id || ""; },
      set id(v) { this.attrs.id = String(v); doc.byId[v] = this; },
      get className() { return this.attrs.class || ""; },
      set className(v) { this.attrs.class = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      setAttribute(k, v) {
        if (k === "id") { this.id = v; return; }
        this.attrs[k] = String(v);
      },
      removeAttribute(k) { delete this.attrs[k]; },
      appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
    };
    doc.all.push(n);
    return n;
  }
  doc.createElement = elem;
  doc.getElementById = (id) => doc.byId[id] || null;
  doc.querySelector = (sel) => {
    assert.equal(sel, '#play-g [data-slot="g"]');
    return doc.slot;
  };
  doc.querySelectorAll = (sel) => {
    const m = /^\[([a-z-]+)\]$/.exec(sel);
    return m ? doc.all.filter((n) => n.getAttribute(m[1]) !== null) : [];
  };
  doc.body = elem("body");
  const region = elem("section");
  region.id = "play-g";
  region.setAttribute("data-region", "g");
  doc.slot = region.appendChild(elem("div"));
  doc.slot.setAttribute("data-slot", "g");
  const legacy = region.appendChild(elem("div"));
  legacy.setAttribute("data-legacy", "g-tiles");
  const bc = elem("p");
  bc.id = "bar-char";
  const pill = elem("p");
  pill.id = "reading";
  pill.setAttribute("data-state", "running");
  doc.region = region;
  doc.legacy = legacy;
  doc.pill = pill;
  return doc;
}

function cell(doc, key) {
  const root = doc.slot.children[0];
  return root.children.find((c) => c.getAttribute("data-cell") === key);
}
function value(doc, key) { return cell(doc, key).children[1].children[0]; }
function shown(doc, key) { return value(doc, key).textContent; }
function said(doc, key) { return cell(doc, key).children[1].children[1]; }
function sub(doc, key) { return cell(doc, key).children[2]; }
function zoneTime(doc) { return cell(doc, "zone").children[1].children[1]; }

const NOW = 10000;
const PLAYING = {
  zone: "Clearfell", zone_entered_at: NOW - 125, session_started_at: NOW - 3725,
  level: 4, deaths: 1, character: "Emberdemo", "class": "Sorceress", game_idle: false,
  tailer: { consented: true, reading: true, idle: false },
  play: { strip: { zone: "Clearfell", sub: "Act 1 - area level 2", level_sub: "Sorceress",
    deaths_sub: "1 this zone", session_sub: "3 level-ups", fresh: true } }
};

test("a playing snapshot fills the four cells and the bar's character", () => {
  ST.reset();
  const doc = makeDoc();
  ST.wire(doc);
  ST.paint(doc, PLAYING, NOW);
  assert.deepEqual(cell(doc, "zone").children[0].textContent, "Zone");
  assert.equal(shown(doc, "zone"), "Clearfell");
  assert.equal(value(doc, "zone").getAttribute("title"), "Clearfell");
  assert.equal(zoneTime(doc).textContent, "2:05");
  assert.equal(sub(doc, "zone").textContent, "Act 1 - area level 2");
  assert.equal(shown(doc, "level"), "4");
  assert.equal(sub(doc, "level").textContent, "Sorceress");
  assert.equal(sub(doc, "level").getAttribute("data-tone"), "neutral");
  assert.equal(shown(doc, "deaths"), "1");
  assert.equal(sub(doc, "deaths").textContent, "1 this zone");
  assert.equal(shown(doc, "session"), "1:02:05");
  assert.equal(sub(doc, "session").textContent, "3 level-ups");
  for (const k of ["zone", "level", "deaths", "session"]) {
    assert.equal(cell(doc, k).getAttribute("data-empty"), null, k);
  }
  assert.equal(doc.getElementById("bar-char").textContent, "Emberdemo (Sorceress)");
  assert.equal(doc.getElementById("bar-char").getAttribute("title"), "Emberdemo (Sorceress)");
  assert.equal(doc.body.getAttribute("data-fresh"), "yes");
});

test("the labels, the value and sub classes give the glance sizes", () => {
  ST.reset();
  const doc = makeDoc();
  ST.paint(doc, PLAYING, NOW);
  assert.deepEqual(ST.CELLS.map((c) => c.label), ["Zone", "Level", "Deaths", "Session"]);
  assert.match(value(doc, "zone").className, /\brow-glance\b/, "zone 28 px");
  for (const k of ["level", "deaths", "session"]) {
    assert.match(value(doc, k).className, /\brow-hero\b/, k + " 32 px");
  }
  for (const k of ["zone", "level", "deaths", "session"]) {
    assert.match(sub(doc, k).className, /\brow-title\b/, k + " sub 20 px");
    assert.match(cell(doc, k).children[0].className, /\brow-title\b.*\bmuted\b/);
  }
  assert.match(zoneTime(doc).className, /\brow-title\b/, "the zone timer 20 px");
});

test("under-levelled the level sub line is the overlay word with its glyph", () => {
  ST.reset();
  const doc = makeDoc();
  const snap = JSON.parse(JSON.stringify(PLAYING));
  snap.underlevel = { word: "3 lv under", gap: 3 };
  snap.play.strip.level_sub = "3 lv under";
  ST.paint(doc, snap, NOW);
  assert.equal(sub(doc, "level").textContent, "[?] 3 lv under");
  assert.equal(sub(doc, "level").getAttribute("data-tone"), "warn");
});

test("first run: empty cells are marked and say what is missing", () => {
  ST.reset();
  const doc = makeDoc();
  doc.pill.setAttribute("data-state", "idle");
  const snap = { zone: null, level: null, deaths: 0, tailer: { consented: false },
    play: { strip: { zone: null, sub: "", level_sub: "", deaths_sub: "", session_sub: "",
      fresh: true } } };
  ST.paint(doc, snap, NOW);
  assert.equal(shown(doc, "zone"), "No zone yet");
  assert.equal(zoneTime(doc).textContent, "--:--");
  assert.equal(zoneTime(doc).getAttribute("data-empty"), "yes");
  assert.equal(shown(doc, "level"), "-");
  assert.equal(shown(doc, "deaths"), "-", "no count before the opt-in");
  assert.equal(shown(doc, "session"), "--:--");
  for (const k of ["zone", "level", "deaths", "session"]) {
    assert.equal(cell(doc, k).getAttribute("data-empty"), "yes", k);
  }
  // the dash is hidden from screen readers; they hear the words
  assert.equal(said(doc, "deaths").textContent, "not counted yet");
  assert.equal(said(doc, "deaths").hidden, false);
  assert.equal(value(doc, "deaths").getAttribute("aria-hidden"), "true");
  assert.equal(doc.getElementById("bar-char").textContent, "");
  // a value arriving clears the mark
  ST.paint(doc, PLAYING, NOW);
  assert.equal(cell(doc, "deaths").getAttribute("data-empty"), null);
  assert.equal(said(doc, "deaths").hidden, true);
  assert.equal(value(doc, "deaths").getAttribute("aria-hidden"), null);
});

test("stale: the idle log or a down feed sets body[data-fresh=no]", () => {
  ST.reset();
  const doc = makeDoc();
  const idle = JSON.parse(JSON.stringify(PLAYING));
  idle.game_idle = true;
  idle.tailer.idle = true;
  idle.tailer.last_line_at = NOW - 1200;
  idle.play.strip.fresh = false;
  idle.play.strip.sub = "Act 1 - frozen 14:02";
  ST.paint(doc, idle, NOW);
  assert.equal(doc.body.getAttribute("data-fresh"), "no");
  assert.equal(sub(doc, "zone").textContent, "Act 1 - frozen 14:02");
  // the clocks stop at the last line (decision 0029)
  assert.equal(zoneTime(doc).textContent, "0:00", "the last line came before this zone timer");
  ST.paint(doc, PLAYING, NOW);
  assert.equal(doc.body.getAttribute("data-fresh"), "yes");
  for (const kit of ["pending", "failed"]) {
    doc.pill.setAttribute("data-state", kit);
    ST.tick(doc, PLAYING, NOW + 1);
    assert.equal(doc.body.getAttribute("data-fresh"), "no", kit);
  }
  for (const kit of ["running", "blocked", "idle", "done"]) {
    doc.pill.setAttribute("data-state", kit);
    ST.tick(doc, PLAYING, NOW + 1);
    assert.equal(doc.body.getAttribute("data-fresh"), "yes", kit);
  }
});

test("the timers stop at the idle log's last line", () => {
  const snap = JSON.parse(JSON.stringify(PLAYING));
  snap.tailer.idle = true;
  snap.tailer.last_line_at = NOW - 100;
  const t = ST.timers(snap, NOW);
  assert.equal(t.zone, "0:25");
  assert.equal(t.session, "1:00:25");
  assert.equal(ST.timers({ tailer: { consented: false }, zone_entered_at: 1 }, 5).session, "--:--");
  assert.equal(ST.duration(null), "--:--");
  assert.equal(ST.duration(59), "0:59");
  assert.equal(ST.duration(3600), "1:00:00");
});

test("tick moves only the timers; paint is idempotent", () => {
  ST.reset();
  const doc = makeDoc();
  ST.paint(doc, PLAYING, NOW);
  const before = doc.all.length;
  ST.tick(doc, PLAYING, NOW + 10);
  assert.equal(zoneTime(doc).textContent, "2:15");
  assert.equal(shown(doc, "session"), "1:02:15");
  ST.paint(doc, PLAYING, NOW + 10);
  assert.equal(doc.all.length, before, "the nodes are made once");
  assert.equal(doc.slot.children.length, 1);
});

test("the G5 guard drops optional parts in a fixed order, frozen last", () => {
  const m = ST.model(PLAYING, NOW);
  assert.equal(ST.WORD_CAP, 20);
  // 4 labels + 16 words of values and sub lines + the 3-word heading
  assert.equal(ST.wordCount(m, 3), 23);
  const fit = ST.fitWords(ST.model(PLAYING, NOW), 3);
  assert.equal(fit.zoneSub, "Act 1", "the area level goes first");
  assert.equal(fit.sessionSub, "3 level-ups");
  assert.ok(ST.wordCount(fit, 3) <= 20);
  const tight = ST.fitWords(ST.model(PLAYING, NOW), 8);
  assert.equal(tight.sessionSub, "");
  assert.equal(tight.deathsSub, "");
  const idle = JSON.parse(JSON.stringify(PLAYING));
  idle.play.strip.sub = "Act 1 - area level 2 - frozen 14:02";
  const f = ST.fitWords(ST.model(idle, NOW), 7);
  assert.equal(f.zoneSub, "frozen 14:02", "the frozen tag is kept longest");
  // a fitting model is left alone
  assert.equal(ST.fitWords(ST.model(PLAYING, NOW), 0).zoneSub, "Act 1 - area level 2");
});

test("the model reads play.strip and the snapshot defensively", () => {
  const m = ST.model(null, null);
  assert.equal(m.zone, "");
  assert.equal(m.level, "");
  assert.equal(m.deaths, "");
  assert.equal(m.fresh, true);
  assert.equal(ST.model({ play: { strip: "x" }, zone: "Clearfell" }, 0).zone, "Clearfell");
  assert.equal(ST.model({ level: "4" }, 0).level, "");
  assert.equal(ST.charLine({ character: "A" }), "A");
  assert.equal(ST.charLine({ character: "A", "class": "Monk" }), "A (Monk)");
  assert.equal(ST.feedLive(null), true);
});

test("it registers as region g and retires the g-tiles group", () => {
  assert.equal(ST.spec.name, "strip");
  assert.equal(ST.spec.region, "g");
  assert.deepEqual(ST.spec.retires, ["g-tiles"]);
  ST.reset();
  const doc = makeDoc();
  const reg = R.create({ warn: () => {} });
  reg.register(ST.spec);
  reg.start(doc, { api: () => null, getSnap: () => null, serverNow: () => 0, tabs: null });
  assert.equal(doc.legacy.hidden, true);
  assert.equal(doc.region.getAttribute("data-fit"), "yes");
  reg.paint(doc, PLAYING, NOW);
  assert.equal(shown(doc, "level"), "4");
  reg.tick(doc, PLAYING, NOW + 1);
  assert.equal(zoneTime(doc).textContent, "2:06");
});

test("the stale look, the empty look and the neutral bar word are in the CSS", () => {
  assert.match(CSS, /body\[data-fresh="no"\] #play-g \.st-value/);
  assert.match(CSS, /body\[data-fresh="no"\] #play-g \.st-time/);
  assert.match(CSS, /#play-g \[data-empty\] \.st-value/);
  assert.match(CSS, /color: var\(--fk-text-muted\)/);
  // F-159: colour only for blocked or failed
  assert.match(CSS, /#reading\.pill:not\(\[data-state="blocked"\]\):not\(\[data-state="failed"\]\)/);
  assert.match(CSS, /#reading\.pill \{ font-size: var\(--al-fs-title\)/, "the bar word is 20 px");
  assert.doesNotMatch(CSS, /animation|transition/, "nothing moves");
});

test("the floor: no clipboard, no notify, no timer, no network", () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of [/clipboard/i, /\.notify\(/, /setInterval|setTimeout/,
    /fetch\(|XMLHttpRequest|EventSource/, /innerHTML/, /aria-live/, /ALChars/]) {
    assert.doesNotMatch(code, bad, String(bad));
  }
  assert.match(SRC, /module\.exports = api;/);
  assert.doesNotMatch(SRC + CSS, /[^\x0a\x20-\x7e]/, "ASCII and LF");
});

test("the page pre-links the files and keeps the bar word and character slot", () => {
  assert.match(HTML, /<script src="\/web\/strip\.js" defer><\/script>/);
  assert.match(HTML, /<link rel="stylesheet" href="\/web\/strip\.css">/);
  assert.match(HTML, /id="bar-char"/);
  assert.match(HTML, /id="reading"/);
});
