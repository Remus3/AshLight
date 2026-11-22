"use strict";
/* UI-REVIEW-2 (design 0003): the dashboard's pure view helpers in
   web/status.js - connection and log pills, offline honesty, event kind
   tags, empty-state and trade text. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const v = web.load("status.js");

test("link pill: first failure says what to do; later ones reconnect", () => {
  assert.deepEqual(v.linkView("notoken", false),
    { state: "failed", glyph: "[x]", word: "open AshLight from the link it showed at start" });
  assert.deepEqual(v.linkView("open", false), { state: "done", glyph: "[+]", word: "live" });
  assert.deepEqual(v.linkView("error", false),
    { state: "failed", glyph: "[x]", word: "can't reach AshLight - reopen it from the Start Menu" });
  assert.deepEqual(v.linkView("error", true), { state: "pending", glyph: "[ ]", word: "reconnecting" });
  // F-131: before the first event the pill says it is connecting
  assert.deepEqual(v.linkView("connecting", false), { state: "pending", glyph: "[ ]", word: "connecting" });
  assert.deepEqual(v.linkView(undefined, false), v.linkView("connecting", false));
});

test("F-131: the bar word and the strip's next step come from the one table", () => {
  const read = { consented: true, reading: true, path: "logs/Client.txt" };
  assert.deepEqual(v.barStatus(read, "open"),
    { state: "running", glyph: "[>]", word: "reading Client.txt", id: "reading", next: "" });
  const missing = v.barStatus({ consented: true, reading: false, path: null }, "open");
  assert.equal(missing.word, "Client.txt not found - start the game once");
  assert.equal(missing.next,
    "Start Path of Exile 2 once so it writes Client.txt. AshLight finds it by itself.");
  assert.equal(v.zoneNext({ consented: false }, "open"),
    "Press \"Allow reading Client.txt\" on the Play tab.");
  assert.equal(v.zoneNext(read, "error", false), "Start AshLight again from its Start Menu shortcut.");
  // reconnecting by itself: nothing for the player to do
  assert.equal(v.zoneNext(read, "error", true), "");
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

test("TEST-LIVE-EXIT: a quiet log reads idle and freezes the clocks", () => {
  const idle = { consented: true, reading: true, path: "x", idle: true, last_line_at: 100 };
  const p = v.readingView(idle, true);
  assert.equal(p.state, "blocked");
  assert.equal(p.glyph, "[#]");
  assert.equal(p.word, v.IDLE_WORD);
  // F-131 (0042 F20 f): one root with the overlay's word, no fixed "20 min";
  // FIX-IDLE-WORD: the log is still being read, so the bar says "reading" (G9)
  assert.equal(v.IDLE_WORD, "log quiet, still reading - game closed or AFK?");
  // the feed down still wins: no stale claim
  assert.equal(v.readingView(idle, false).word, "Client.txt status unknown");
  assert.equal(v.clockUntil(idle, 500), 100);
  assert.equal(v.clockUntil({ ...idle, idle: false }, 500), 500);
  assert.equal(v.clockUntil(null, 500), 500);
  assert.equal(v.clockUntil({ idle: true, last_line_at: null }, 500), 500);
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
  assert.equal(v.kindOf({ type: "area_generated" }), "zone");
  assert.equal(v.kindOf({ type: "trade_accepted" }), "trade");
  assert.equal(v.kindOf({ type: "trade_cancelled" }), "trade");
  assert.equal(v.kindOf({ type: "session_connect" }), "log");
  assert.equal(v.kindOf({ type: "something_new" }), "info");
});

test("empty Recent list says what unlocks it", () => {
  assert.equal(v.emptyText(true),
    "Nothing yet. Zones, level-ups, deaths and whispers show up here as you play.");
  assert.equal(v.emptyText(false),
    "Nothing yet. Allow reading Client.txt above, then zones, level-ups, deaths and whispers show up here.");
});

test("session sub line: flags first, else says when the timer starts (UX-U9)", () => {
  assert.equal(v.sessionSub(false, false, false), "Starts when you allow reading Client.txt");
  assert.equal(v.sessionSub(false, false, true), "\u00a0");
  assert.equal(v.sessionSub(true, false, true), "AFK");
  assert.equal(v.sessionSub(true, true, false), "AFK / DND");
  assert.equal(v.sessionSub(false, true, true), "DND");
  assert.equal(v.sessionSub(true, false, false), "AFK");
});

test("eventsKey changes when the recent list changes, not otherwise (UX-PERF)", () => {
  const a = [{ at: 1, type: "death", text: "A died" }, { at: 2, type: "level_up", text: "A reached level 2" }];
  assert.equal(v.eventsKey(a), v.eventsKey(a.map((r) => ({ ...r }))));
  assert.notEqual(v.eventsKey(a), v.eventsKey(a.concat([{ at: 3, type: "death", text: "A died" }])));
  // full list: the oldest drops as one arrives, same length
  assert.notEqual(v.eventsKey(a), v.eventsKey([a[1], { at: 3, type: "death", text: "A died" }]));
  assert.equal(v.eventsKey([]), v.eventsKey(null));
});

test("counts: no number before the opt-in, plurals after (UX-FIRSTRUN)", () => {
  assert.deepEqual(v.countsView(0, 0, false), { deaths: "-", levelups: "Counts once reading starts" });
  assert.deepEqual(v.countsView(3, 1, true), { deaths: "3", levelups: "1 level-up" });
  assert.deepEqual(v.countsView(0, 2, true), { deaths: "0", levelups: "2 level-ups" });
  assert.deepEqual(v.countsView(undefined, null, true), { deaths: "0", levelups: "0 level-ups" });
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

/* RUN-LEDGER-CONSENT (decision 0071): the log record's consent line, with
   its own Allow control beside the Client.txt opt-out. web/app.js
   ledgerView runs alone (LEDGER-VIEW markers); the markup is read as text. */
function webLedgerView() {
  const vm = require("node:vm");
  const src = web.source("app.js");
  const m = /\/\* LEDGER-VIEW:begin[\s\S]*?\*\/([\s\S]*?)\/\* LEDGER-VIEW:end \*\//.exec(src);
  assert.ok(m, "LEDGER-VIEW markers in web/app.js");
  const box = {};
  vm.runInNewContext(m[1] + "\nout.f = ledgerView;", { out: box });
  return (tl) => JSON.parse(JSON.stringify(box.f(tl)));
}

test("ledger consent line with its own Allow control", () => {
  const html = web.source("index.html");
  // PLAY-TD-21A-SETTINGS-RAIL: both moved from the footer to Settings,
  // Reading and web data; the ledger line still sits right after the opt-out
  const foot = /<footer[^>]*>([\s\S]*?)<\/footer>/.exec(html)[1];
  assert.ok(!foot.includes('id="ledger-line"') && !foot.includes('id="consent-no"'));
  const sec = /<section id="set-reading"[^>]*>([\s\S]*?)<\/section>/.exec(html)[1];
  const line = /<p id="ledger-line"[^>]*>([\s\S]*?)<\/p>/.exec(sec);
  assert.ok(line, "the ledger line sits in Reading and web data, beside the Client.txt opt-out");
  assert.match(line[0], /<p id="ledger-line"[^>]*\bhidden\b/);
  assert.ok(sec.indexOf('id="consent-no"') < sec.indexOf('id="ledger-line"'));
  assert.ok(sec.indexOf('id="consent-said"') < sec.indexOf('id="ledger-line"'));
  // its own control: a plain button, never the app's one primary button
  const btn = /<button id="ledger-allow"([^>]*)>([^<]*)<\/button>/.exec(line[1]);
  assert.ok(btn, "the line has its own button");
  assert.match(btn[1], /type="button"/);
  assert.doesNotMatch(btn[1], /primary/);
  assert.match(btn[1], /aria-describedby="ledger-text ledger-said"/);
  assert.equal(btn[2], "Allow the log record");
  assert.notEqual(btn[2], "Allow reading Client.txt");

  const view = webLedgerView();
  // hidden until Client.txt is read; the Client.txt opt-in alone allows nothing
  assert.equal(view({}).shown, false);
  assert.equal(view({ consented: false, ledger: true }).shown, false);
  const off = view({ consented: true });
  assert.deepEqual(off, view({ consented: true, ledger: false }));
  assert.equal(off.shown, true);
  assert.equal(off.on, false);
  assert.equal(off.send, true);
  assert.equal(off.button, "Allow the log record");
  assert.match(off.text, /^Log record: off\. /);
  // plain words for what is kept, where, and what is not
  assert.match(off.text, /counts the kinds of log lines/);
  assert.match(off.text, /on this computer/);
  assert.match(off.text, /Names, chat and item words are blanked out/);
  assert.match(off.text, /Nothing is sent\./);
  // only ledger === true is on (a truthy non-bool is not)
  assert.equal(view({ consented: true, ledger: "yes" }).on, false);
  const on = view({ consented: true, ledger: true });
  assert.equal(on.on, true);
  assert.equal(on.send, false);
  assert.equal(on.button, "Stop the log record");
  assert.match(on.text, /^Log record: on\. /);
  assert.match(on.text, /Stopping it deletes the file\.$/);
  for (const s of [off.text, on.text, off.button, on.button]) {
    assert.match(s, /^[\x20-\x7e]+$/, "ASCII");
    for (const sentence of s.split(/(?<=\.) /)) {
      assert.ok(sentence.split(" ").length <= 20, sentence);
    }
    assert.doesNotMatch(s, /\b(core|token|tailer|ledger|consent)\b/i);
  }

  // the click posts only the ledger flag, through the token-carrying api()
  const app = web.source("app.js");
  assert.match(app, /api\("POST", "\/api\/consent", \{ ledger: ledgerSend \}\)/);
  assert.match(app, /\$\("ledger-allow"\)\.addEventListener\("click", toggleLedger\)/);
});
