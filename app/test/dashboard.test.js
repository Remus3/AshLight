"use strict";
/* UI-REVIEW-2 (design 0003): the dashboard's pure view helpers in
   web/status.js - connection and log pills, offline honesty, event kind
   tags, empty-state and trade text. */
const test = require("node:test");
const assert = require("node:assert/strict");
const v = require("../../web/status.js");

test("link pill: first failure says what to do; later ones reconnect", () => {
  assert.deepEqual(v.linkView("notoken", false),
    { state: "failed", glyph: "[x]", word: "open AshLight from the link it showed at start" });
  assert.deepEqual(v.linkView("open", false), { state: "done", glyph: "[+]", word: "live" });
  assert.deepEqual(v.linkView("error", false),
    { state: "failed", glyph: "[x]", word: "can't reach AshLight - restart it" });
  assert.deepEqual(v.linkView("error", true), { state: "pending", glyph: "[ ]", word: "reconnecting" });
});

test("log pill: unknown while the feed is down, never a stale claim", () => {
  const reading = { consented: true, reading: true, path: "logs/Client.txt" };
  assert.deepEqual(v.readingView(reading, true),
    { state: "running", glyph: "[>]", word: "reading Client.txt" });
  assert.deepEqual(v.readingView(reading, false),
    { state: "pending", glyph: "[ ]", word: "Client.txt status unknown" });
  assert.deepEqual(v.readingView(null, false),
    { state: "pending", glyph: "[ ]", word: "Client.txt status unknown" });
  assert.deepEqual(v.readingView({ consented: true, reading: false, path: "logs" }, true),
    { state: "blocked", glyph: "[#]", word: "waiting for Client.txt" });
  assert.deepEqual(v.readingView({ consented: true, reading: false, path: null }, true),
    { state: "blocked", glyph: "[#]", word: "Client.txt not found - start the game once" });
  assert.deepEqual(v.readingView({ consented: false }, true),
    { state: "idle", glyph: "[-]", word: "not reading Client.txt" });
});

test("event kind tags name what happened", () => {
  assert.equal(v.kindOf({ type: "whisper_in", trade: true }), "trade");
  assert.equal(v.kindOf({ type: "whisper_in" }), "from");
  assert.equal(v.kindOf({ type: "whisper_out" }), "to");
  assert.equal(v.kindOf({ type: "death" }), "death");
  assert.equal(v.kindOf({ type: "level_up" }), "level");
  assert.equal(v.kindOf({ type: "scene_changed" }), "zone");
  assert.equal(v.kindOf({ type: "tailer_started" }), "log");
  assert.equal(v.kindOf({ type: "tailer_reset" }), "log");
  assert.equal(v.kindOf({ type: "afk_changed" }), "status");
  assert.equal(v.kindOf({ type: "dnd_changed" }), "status");
  assert.equal(v.kindOf({ type: "player_joined_area" }), "party");
  assert.equal(v.kindOf({ type: "trade_accepted" }), "info");
});

test("empty Recent list says what unlocks it", () => {
  assert.equal(v.emptyText(true),
    "Nothing yet. Zones, level-ups, deaths and whispers show up here as you play.");
  assert.equal(v.emptyText(false),
    "Nothing yet. Allow reading Client.txt above, then zones, level-ups, deaths and whispers show up here.");
});

test("trade line uses the core's sentence; never prints undefined", () => {
  assert.deepEqual(v.tradeLine({ text: "Quietfox wants Plain Belt - 5 exalted", where: "tab Sale (3,7)" }),
    { what: "Quietfox wants Plain Belt - 5 exalted", where: "tab Sale (3,7)" });
  const old = v.tradeLine({ from: "Q", kind: "exchange", item: "Chaos Orb" });
  assert.equal(old.what, "Q wants Chaos Orb - trade request");
  assert.equal(old.where, "");
  assert.ok(!/undefined|null/.test(v.tradeLine({}).what));
});

test("corner names are sentence case", () => {
  assert.equal(v.cornerLabel("top-right"), "Top right");
  assert.equal(v.cornerLabel("bottom-center"), "Bottom center");
});
