"use strict";
/* F-131: one status vocabulary. Each state of server/al/data/status_words.json
   gives the table's words on the dashboard bar (web/status.js barStatus and
   its two pills), on the overlay status slot (app/shared/render_gate.js) and
   as the strip's next step (web/status.js zoneNext); the Checks detail is
   tested in tests/test_status_words.py. The two JS copies equal the JSON. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const web = require("./_web.js");
const dash = web.load("status.js");
const gate = require("../shared/render_gate.js");

const ROOT = path.join(__dirname, "..", "..");
const SOURCE = JSON.parse(fs.readFileSync(
  path.join(ROOT, "server", "al", "data", "status_words.json"), "ascii"));
const W = SOURCE.states;
const BEGIN = "/* STATUS_WORDS BEGIN: copy of server/al/data/status_words.json */";
const END = "/* STATUS_WORDS END */";

function withoutReadme(doc) {
  const out = {};
  Object.keys(doc).forEach((k) => { if (k !== "_README") { out[k] = doc[k]; } });
  return out;
}

function copyIn(rel) {
  const text = fs.readFileSync(path.join(ROOT, rel), "ascii");
  assert.equal(text.split(BEGIN).length, 2, rel + ": one begin marker");
  assert.equal(text.split(END).length, 2, rel + ": one end marker");
  const body = text.split(BEGIN)[1].split(END)[0].trim();
  const prefix = "var STATUS_WORDS =";
  assert.ok(body.startsWith(prefix) && body.endsWith(";"), rel);
  return JSON.parse(body.slice(prefix.length, -1));
}

/* The inputs that put each surface in a state. tailer and link feed
   web/status.js; snap and status feed render_gate.hudModel. */
const SNAP = { zone: "Clearfell", in_hideout: false, zone_entered_at: 1000, level: 3, deaths: 1 };
const CASES = {
  reading: { tailer: { consented: true, reading: true, path: "logs/Client.txt" }, link: "open",
             status: "live" },
  live: { tailer: { consented: true, reading: true, path: "logs/Client.txt" }, link: "open",
          status: "live" },
  // the feed is live but the core sends no tailer (an older core); with the
  // feed down the feed state outranks it (see "the worse of" below)
  unknown: { tailer: null, link: "open" },
  link_wait: { tailer: null, link: "connecting", status: "connecting" },
  link_retry: { tailer: { consented: true, reading: true }, link: "error", everLive: true,
                status: "offline" },
  off: { tailer: { consented: false, reading: false, path: null }, link: "open", status: "live" },
  waiting: { tailer: { consented: true, reading: false, path: "logs/Client.txt" }, link: "open",
             status: "live" },
  idle: { tailer: { consented: true, reading: true, path: "x", idle: true, last_line_at: 900 },
          link: "open", status: "live" },
  missing: { tailer: { consented: true, reading: false, path: null }, link: "open",
             status: "live" },
  unreadable: { tailer: { consented: true, reading: false, path: "logs/Client.txt",
                          unreadable: true }, link: "open", status: "live" },
  link_down: { tailer: null, link: "error", everLive: false, status: "offline" },
  link_token: { tailer: null, link: "notoken", everLive: false }
};

test("both JS copies equal the JSON source", () => {
  const want = withoutReadme(SOURCE);
  assert.deepEqual(copyIn("web/status.js"), want);
  assert.deepEqual(copyIn("app/shared/render_gate.js"), want);
  assert.deepEqual(dash.STATUS_WORDS, want);
  assert.deepEqual(gate.STATUS_WORDS, want);
});

test("every state with a dashboard or overlay word has a case here", () => {
  Object.keys(W).forEach((id) => {
    if (W[id].bar !== null || W[id].overlay !== null) { assert.ok(CASES[id], id); }
  });
});

test("bar: each state gives the table's glyph and word", () => {
  Object.keys(CASES).forEach((id) => {
    const c = CASES[id];
    const s = W[id];
    if (s.bar === null) { return; }
    const linkId = dash.linkState(c.link, c.everLive);
    const readId = dash.readingState(c.tailer, linkId === "live");
    // the state shows on its own pill
    const own = readId === id ? dash.readingView(c.tailer, linkId === "live")
                              : dash.linkView(c.link, c.everLive);
    assert.deepEqual(own, { state: s.kit, glyph: s.glyph, word: s.bar }, id);
    if (id === "live") { return; } // "live" and "reading" share the bar; reading wins a tie
    const b = dash.barStatus(c.tailer, c.link, c.everLive);
    assert.equal(b.id, id, id);
    assert.deepEqual([b.state, b.glyph, b.word], [s.kit, s.glyph, s.bar], id);
  });
});

test("bar: the worse of the reading and the feed state", () => {
  const read = { consented: true, reading: true, path: "x" };
  assert.equal(dash.barStatus(read, "open").id, "reading");
  assert.equal(dash.barStatus(read, "error", true).id, "link_retry");
  assert.equal(dash.barStatus(read, "error", false).id, "link_down");
  assert.equal(dash.barStatus(read, undefined).id, "link_wait");
  assert.equal(dash.barStatus({ consented: false }, "open").id, "off");
  // a missing log outranks a live feed; a dead feed hides the log state
  assert.equal(dash.barStatus({ consented: true, reading: false }, "open").id, "missing");
  assert.equal(dash.barStatus({ consented: true, reading: false }, "error", true).id,
               "link_retry");
});

test("strip: the next step is the table's, empty when the player has no act", () => {
  Object.keys(CASES).forEach((id) => {
    if (id === "live") { return; }
    const c = CASES[id];
    assert.equal(dash.zoneNext(c.tailer, c.link, c.everLive), W[id].next, id);
  });
  assert.equal(dash.zoneNext({ consented: true, reading: true }, "open"), "");
});

test("overlay: each state gives the table's word in the status slot", () => {
  Object.keys(CASES).forEach((id) => {
    const c = CASES[id];
    const s = W[id];
    if (s.overlay === null || !c.status) { return; }
    const snap = id === "link_wait" ? null : { ...SNAP, tailer: c.tailer || undefined };
    const m = gate.hudModel(snap, 1060, c.status);
    assert.equal(gate.statusText(m), s.overlay, id);
    // an alone word stands without the level text; others sit beside it
    if (s.overlay_alone) {
      assert.equal(m.level, "", id);
      assert.ok(s.overlay.length <= SOURCE.overlay_alone_max, id);
    } else {
      assert.ok(s.overlay.length <= SOURCE.overlay_beside_max, id);
    }
  });
  assert.equal(gate.IDLE_WORD, W.idle.overlay);
});

test("overlay: the page's own connection words are the table's", () => {
  // app/overlay/overlay.js passes these words as the status argument
  const src = fs.readFileSync(path.join(ROOT, "app", "overlay", "overlay.js"), "ascii");
  assert.ok(src.includes('status = "' + W.link_wait.overlay + '"'));
  assert.ok(src.includes('status = "' + W.link_down.overlay + '"'));
  assert.equal(W.link_retry.overlay, W.link_down.overlay);
});

test("kit glyphs and the fault rule hold for every row", () => {
  const kit = JSON.parse(fs.readFileSync(
    path.join(ROOT, "ops", "fleet_kit", "tokens.json"), "utf8")).states;
  Object.keys(W).forEach((id) => {
    const s = W[id];
    assert.ok(kit[s.kit], id);
    assert.equal(s.glyph, kit[s.kit].row, id);
    if (s.fault) { assert.ok(s.next && s.check, id); }
  });
});

test("unreadable: bar, overlay and Checks name the same state", () => {
  /* RUN-UNREADABLE-WORD (review SRW-1): the file is there but can't be
     read. It wins over a quiet log (nothing can be read, so the log goes
     quiet) and over a stale reading flag; with the feed down the feed
     state still outranks it. */
  const s = W.unreadable;
  const base = { consented: true, reading: false, path: "logs/Client.txt", unreadable: true };
  [base, { ...base, idle: true, last_line_at: 900 }, { ...base, reading: true }].forEach((tl) => {
    const b = dash.barStatus(tl, "open");
    assert.equal(b.id, "unreadable");
    assert.deepEqual([b.state, b.glyph, b.word], ["blocked", "[#]", "can't read Client.txt"]);
    assert.equal(b.next, s.next);
    const m = gate.hudModel({ ...SNAP, tailer: tl }, 1060, "live");
    assert.equal(gate.statusText(m), s.overlay);
  });
  assert.ok(s.overlay.length <= SOURCE.overlay_beside_max);
  assert.equal(s.check_row, "reading");
  assert.equal(s.fault, true);
  assert.equal(dash.barStatus(base, "error", true).id, "link_retry");
  // not opted in: nothing is read, so nothing is unreadable
  assert.equal(dash.readingState({ consented: false, unreadable: true }, true), "off");
});
