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

/* RUN-FEED-TRUTH (F-175) and RUN-PERF-DASH-IDLE (F-178): web/app.js
   feedLink and pacer run alone (FEED-PACE markers) with fake EventSource,
   health, timers and visibility. */
function feedPace() {
  const vm = require("node:vm");
  const src = web.source("app.js");
  const m = /\/\* FEED-PACE:begin[\s\S]*?\*\/([\s\S]*?)\/\* FEED-PACE:end \*\//.exec(src);
  assert.ok(m, "FEED-PACE markers in web/app.js");
  const box = {};
  vm.runInNewContext(m[1] + "\nout.feedLink = feedLink; out.pacer = pacer;" +
    " out.RETRY = FEED_RETRY_MS;", { out: box });
  return box;
}

function fakeFeed(healthCodes) {
  const made = [];
  const said = [];
  const frames = [];
  const timers = [];
  let asked = 0;
  let live = false;
  const o = {
    open() {
      const h = {};
      const es = {
        readyState: 0, closed: false,
        addEventListener(n, fn) { (h[n] = h[n] || []).push(fn); },
        close() { this.closed = true; this.readyState = 2; },
        fire(n, m) { (h[n] || []).forEach((fn) => fn(m)); }
      };
      made.push(es);
      return es;
    },
    health() {
      const code = healthCodes[Math.min(asked, healthCodes.length - 1)];
      asked++;
      return code === "reject" ? Promise.reject(new Error("down")) : Promise.resolve(code);
    },
    link(ev) { said.push(ev); if (ev === "open") { live = true; } },
    frame(name, m) { frames.push([name, m.data]); },
    later(fn, ms) { timers.push({ fn, ms }); return timers.length; },
    everLive() { return live; }
  };
  return { o, made, said, frames, timers, asked: () => asked };
}

const flush = () => new Promise((r) => setImmediate(r));

test("RUN-FEED-TRUTH: a 401 after a live feed shows the restarted line and stops", async () => {
  const fp = feedPace();
  const f = fakeFeed([401]);
  const feed = fp.feedLink(f.o);
  feed.open();
  const es = f.made[0];
  es.readyState = 1;
  es.fire("open");
  es.fire("state", { data: "{\"version\":1}" });
  assert.deepEqual(f.frames, [["state", "{\"version\":1}"]]);
  // the core restarted with a new token: the stream answer is a 401, the
  // EventSource closes for good and the page asks /api/health once
  es.readyState = 2;
  es.fire("error");
  await flush();
  assert.equal(f.asked(), 1);
  assert.deepEqual(f.said, ["open", "error", "restarted"]);
  assert.equal(feed.over(), true);
  assert.equal(f.timers.length, 0, "no retry after a restart");
  assert.equal(feed.open(), null);
  // the bar word, from web/status.js
  const p = v.barStatus({ consented: true, reading: true }, "restarted", true);
  assert.equal(p.word, "AshLight restarted. Open it again from the tray.");
  assert.equal(p.word, v.RESTARTED_WORD);
  assert.equal(p.state, "failed");
  assert.equal(p.id, "link_restarted");
  assert.match(p.next, /tray/);
  assert.match(p.word, /^[\x20-\x7e]+$/);
  // before any live feed a 401 is a wrong link, not a restart
  const g = fakeFeed([401]);
  fp.feedLink(g.o).open();
  g.made[0].readyState = 2;
  g.made[0].fire("error");
  await flush();
  assert.deepEqual(g.said, ["error", "notoken"]);
});

test("RUN-FEED-TRUTH: other errors reconnect every 3 s", async () => {
  const fp = feedPace();
  assert.equal(fp.RETRY, 3000);
  const f = fakeFeed([503, "reject", 0, 200]);
  const feed = fp.feedLink(f.o);
  feed.open();
  f.made[0].readyState = 1;
  f.made[0].fire("open");
  for (let i = 0; i < 4; i++) {
    const es = f.made[f.made.length - 1];
    es.readyState = 2;
    es.fire("error");
    es.fire("error"); // a second error while asking asks nothing more
    await flush();
    assert.equal(f.asked(), i + 1);
    assert.equal(f.timers.length, i + 1);
    assert.equal(f.timers[i].ms, 3000);
    f.timers[i].fn();
    assert.equal(f.made.length, i + 2, "a new EventSource after 3 s");
    assert.equal(es.closed, true);
  }
  assert.equal(feed.over(), false);
  assert.ok(!f.said.includes("restarted"));
  // a feed the browser is only reconnecting (readyState 0) asks nothing
  const last = f.made[f.made.length - 1];
  last.readyState = 0;
  last.fire("error");
  await flush();
  assert.equal(f.asked(), 4);
  // a replaced EventSource's events are ignored
  f.made[0].fire("state", { data: "old" });
  assert.ok(!f.frames.some((x) => x[1] === "old"));
  // with a retry hook the page reconnects through it (connect())
  const g = fakeFeed([500]);
  let retried = 0;
  g.o.retry = () => { retried++; };
  fp.feedLink(g.o).open();
  g.made[0].readyState = 2;
  g.made[0].fire("error");
  await flush();
  g.timers[0].fn();
  assert.equal(retried, 1);
  assert.equal(g.made.length, 1);
  // the page wires it so: retry is connect(), the health read carries the token
  const app = web.source("app.js");
  assert.match(app, /retry: connect,/);
  assert.match(app, /fetch\("\/api\/health", \{ headers: \{ "X-AL-Token": token \}, cache: "no-store" \}\)/);
});

function fakePace(hidden) {
  const st = { hidden, painted: [], ticks: 0, every: 0, stops: 0 };
  st.p = feedPace().pacer({
    hidden: () => st.hidden,
    paint: (s) => { st.painted.push(s); },
    tick: () => { st.ticks++; },
    every: (fn, ms) => { assert.equal(ms, 1000); st.every++; return st.every; },
    stop: () => { st.stops++; }
  });
  return st;
}

test("RUN-PERF-DASH-IDLE: a hidden page runs no painter; one paint on return", () => {
  const st = fakePace(true);
  st.p.sync();
  assert.equal(st.p.ticking(), false, "no ticker while hidden");
  for (let i = 1; i <= 5; i++) { assert.equal(st.p.push({ version: i }), false); }
  assert.deepEqual(st.painted, []);
  assert.equal(st.ticks, 0);
  assert.equal(st.p.held(), true);
  st.hidden = false;
  st.p.shown();
  assert.deepEqual(st.painted, [{ version: 5 }], "one paint, the newest snapshot");
  assert.equal(st.p.ticking(), true);
  assert.equal(st.p.held(), false);
  // shown again with nothing held: only the clocks move
  st.p.shown();
  assert.equal(st.painted.length, 1);
  assert.equal(st.ticks, 1);
  // a visible push lets the caller paint
  assert.equal(st.p.push({ version: 6 }), true);
  // hidden again: the ticker stops
  st.hidden = true;
  st.p.shown();
  assert.equal(st.p.ticking(), false);
  assert.equal(st.stops, 1);
  // render() holds the guard at its top, and the visibility change runs shown()
  const app = web.source("app.js");
  const at = app.indexOf("  function render(s) {");
  const body = app.slice(at, app.indexOf("\n  }\n", at));
  assert.ok(body.indexOf("if (pace && !pace.push(s)) { return; }") > 0);
  assert.ok(body.indexOf("if (pace && !pace.push(s)) { return; }") <
            body.indexOf("A.render(s, charView(s));"));
  assert.match(app, /document\.addEventListener\("visibilitychange", pace\.shown\);/);
  assert.doesNotMatch(app, /setInterval\(tick, 1000\)/);
});

test("RUN-PERF-DASH-IDLE: the ticker stops while idle and restarts on a fresh line", () => {
  const st = fakePace(false);
  st.p.sync();
  assert.equal(st.p.ticking(), true);
  assert.equal(st.p.push({ version: 1, game_idle: false }), true);
  assert.equal(st.every, 1, "one ticker, not one per push");
  assert.equal(st.p.push({ version: 2, game_idle: true }), true);
  assert.equal(st.p.ticking(), false);
  assert.equal(st.stops, 1);
  st.p.push({ version: 3, game_idle: true });
  assert.equal(st.every, 1);
  // a fresh log line clears game_idle: the next push starts the ticker
  st.p.push({ version: 4, game_idle: false });
  assert.equal(st.p.ticking(), true);
  assert.equal(st.every, 2);
  // a page shown again while the game is idle starts no ticker
  st.p.push({ version: 5, game_idle: true });
  st.hidden = true;
  st.p.shown();
  st.hidden = false;
  st.p.shown();
  assert.equal(st.p.ticking(), false);
});
