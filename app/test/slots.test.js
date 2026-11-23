/* TD-02: the slot tables (web/slots.js), no DOM. Glance budget G3 (every
   region fits its track in every state, every open trade has a row, the
   summed tracks equal the grid) and the table half of G11 (hudLine2 and
   cardHolder), docs/plan/03-target-design sections 3.2 to 3.8 and 5. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const S = web.load("slots.js");

/* One snapshot-shaped state per context mode. */
const MODE_STATES = {
  setup: { tailer: { consented: false, reading: false, path: null } },
  error: { tailer: { consented: true, reading: false, path: null } },
  idle: { tailer: { consented: true, reading: true, path: "x" }, game_idle: true },
  map: { tailer: { consented: true, reading: true, path: "x" },
         maps: { count: 1, current: { inside: true } }, area_id: "MapAny" },
  town: { tailer: { consented: true, reading: true, path: "x" }, area_id: "G1_town" },
  guide: { tailer: { consented: true, reading: true, path: "x" }, area_id: "G1_2",
           zone_guide: { kind: "campaign", short: "Kill the boss" } },
  none: { tailer: { consented: true, reading: true, path: "x" } }
};

function trades(n) {
  const out = [];
  for (let i = 0; i < n; i++) { out.push({ id: i + 1, at: 1000 + i, lead: "buyer " + i }); }
  return out;
}

const EVENTS = { death: { at: 1 }, level: { at: 2 }, zone: { at: 3 } };
const BUILD_STATES = {
  fits: { build: { loaded: true }, build_alert: null },
  old: { build: { loaded: true }, build_alert: { kind: "level" } },
  wrong_class: { build: { loaded: true }, build_alert: { kind: "class" } },
  none: { build: null, build_alert: { kind: "missing" } }
};
const KEPT = [{ score_delta: 3, at: 1 }, { score_delta: 9, at: 2 },
              { score_delta: 5, at: 3 }, { score_delta: 1, at: 4 }];

test("trackSet: the track tables of 3.2 and 3.8", () => {
  const full = S.trackSet("full");
  assert.deepEqual(full.tracks, { g: 100, c: 228, t: 204, n: 96, b: 68, i: 360, u: 100 });
  const compact = S.trackSet("compact");
  assert.deepEqual(compact.tracks, { g: 100, c: 212, t: 204, n: 52, b: 68, i: 348, u: 52 });
  assert.equal(compact.pad.u, 4);
  assert.equal(full.pad.u, 8);
  for (const [cls, grid] of [["full", 652], ["compact", 592]]) {
    const t = S.trackSet(cls);
    const col = (list) => list.reduce((a, r) => a + t.tracks[r], 0) + t.gap * (list.length - 1);
    assert.equal(col(t.left), grid, cls + " left");
    assert.equal(col(t.right), grid, cls + " right");
    assert.equal(t.grid + t.chrome, cls === "full" ? 760 : 700);
  }
  // s = 1.25: 1920x950 full and 1920x875 compact
  const f125 = S.trackSet("full", 1.25);
  assert.equal(f125.grid + f125.chrome, 950);
  assert.equal(f125.tracks.c, 285);
  assert.equal(f125.border, 2);
  const c125 = S.trackSet("compact", 1.25);
  assert.equal(c125.grid + c125.chrome, 875);
  assert.equal(c125.tracks.i, 435);
  assert.equal(S.trackSet("flow"), null);
  assert.equal(S.trackSet("full", 3).scale, 1);
});

test("contextMode: 7 modes, first match", () => {
  for (const mode of S.MODES) {
    assert.equal(S.contextMode(MODE_STATES[mode], true), mode, mode);
  }
  // AshLight lost: error, even before consent is known
  assert.equal(S.contextMode(null), "error");
  assert.equal(S.contextMode(Object.assign({ offline: true }, MODE_STATES.setup)), "error");
  // the file went away after a start: the path stays, the reset says missing
  assert.equal(S.contextMode({ tailer: { consented: true, reading: false, path: "x",
                                         last_reset: "missing" } }), "error");
  // a later restart reads again: no longer an error
  assert.equal(S.contextMode({ tailer: { consented: true, reading: true, path: "x",
                                         last_reset: "missing" } }), "none");
  // another reset reason (rotation, truncation) is not an error
  assert.equal(S.contextMode({ tailer: { consented: true, reading: false, path: "x",
                                         last_reset: "truncated" } }), "none");
  // opted in, waiting for the first line: none, not error
  assert.equal(S.contextMode({ tailer: { consented: true, reading: false, path: "x" } }),
               "none");
  // setup wins over idle and every zone mode
  assert.equal(S.contextMode(Object.assign({}, MODE_STATES.guide,
    { tailer: { consented: false }, game_idle: true })), "setup");
  // idle wins over map
  assert.equal(S.contextMode(Object.assign({}, MODE_STATES.map, { game_idle: true }), true),
               "idle");
});

test("contextMode: mapOk false until PLAY-MAP-MODE-ON", () => {
  const live = { consented: true, reading: true, path: "x" };
  // a map zone shows none while mapOk is false
  assert.equal(S.contextMode(MODE_STATES.map), "none");
  assert.equal(S.contextMode(MODE_STATES.map, false), "none");
  assert.equal(S.contextMode(Object.assign({ play: { map_ok: true } }, MODE_STATES.map)),
               "map");
  assert.equal(S.contextMode(Object.assign({ play: { map_ok: true } }, MODE_STATES.map),
                             false), "none");
  // hideout after a map: map with mapOk, town without
  const ho = { tailer: live, in_hideout: true, maps: { count: 2, current: null } };
  assert.equal(S.contextMode(ho, true), "map");
  assert.equal(S.contextMode(ho, false), "town");
  // hideout before any map: town either way
  const fresh = { tailer: live, in_hideout: true, maps: { count: 0 } };
  assert.equal(S.contextMode(fresh, true), "town");
  // an endgame guide entry is not a campaign guide
  assert.equal(S.contextMode({ tailer: live, zone_guide: { kind: "endgame" } }), "none");
});

test("feedRows: trades first, newest on top, then death, level, zone", () => {
  const f0 = S.feedRows([], EVENTS);
  assert.deepEqual(f0.rows.map((r) => r.kind), ["death", "level", "zone"]);
  assert.equal(f0.head, "Recent");
  assert.equal(f0.dismissAll, false);
  const f2 = S.feedRows(trades(2), EVENTS);
  assert.deepEqual(f2.rows.map((r) => r.kind), ["trade", "trade", "death", "level", "zone"]);
  assert.deepEqual(f2.rows.slice(0, 2).map((r) => r.item.id), [2, 1]);
  assert.equal(f2.head, "Trades 2");
  assert.equal(f2.dismissAll, true);
  const f3 = S.feedRows(trades(3), EVENTS);
  assert.deepEqual(f3.rows.map((r) => r.kind), ["trade", "trade", "trade", "death", "level"]);
  const f5 = S.feedRows(trades(5), EVENTS);
  assert.deepEqual(f5.rows.map((r) => r.item.id), [5, 4, 3, 2, 1]);
  assert.equal(S.feedRows(trades(1), {}).dismissAll, false);
  // missing events leave their slot to the next kind
  assert.deepEqual(S.feedRows([], { zone: { at: 1 } }).rows.map((r) => r.kind), ["zone"]);
  // same time: the later arrival is newer; no `at`: input order, newest last
  const tie = S.feedRows([{ id: "a", at: 5 }, { id: "b", at: 5 }], null);
  assert.deepEqual(tie.rows.map((r) => r.item.id), ["b", "a"]);
  const bare = S.feedRows([{ id: "a" }, { id: "b" }], null);
  assert.deepEqual(bare.rows.map((r) => r.item.id), ["b", "a"]);
  // no input gives more than 5 rows
  for (let n = 0; n <= 12; n++) {
    assert.ok(S.feedRows(trades(n), EVENTS).rows.length <= S.FEED_SLOTS, String(n));
  }
  // over 5 (never sent by the core): counted, not silently dropped
  const f6 = S.feedRows(trades(6), EVENTS);
  assert.equal(f6.rows.length, 5);
  assert.equal(f6.over, 1);
  assert.equal(f6.rows[0].item.id, 6);
});

test("noticePick: the 8 kinds in order, compact head only", () => {
  const all = [7, 6, 5, 4, 3, 2, 1].map((k) => ({ kind: k }));
  for (let k = 1; k <= 7; k++) {
    const q = all.filter((e) => e.kind >= k);
    const p = S.noticePick(q, "full");
    assert.equal(p.kind, k);
    assert.equal(p.more, q.length - 1);
    assert.equal(p.bodyRows, 2);
  }
  const empty = S.noticePick([], "full");
  assert.equal(empty.kind, 8);
  assert.equal(empty.label, "Notices");
  assert.equal(empty.text, "none");
  // compact: kinds 6 and 7 are not shown, head row only
  assert.equal(S.noticePick([{ kind: 6 }, { kind: 7 }], "compact").kind, 8);
  const c = S.noticePick([{ kind: 7 }, { kind: 5 }, { kind: 6 }], "compact");
  assert.equal(c.kind, 5);
  assert.equal(c.more, 0);
  assert.equal(c.bodyRows, 0);
  // a key reminder retires after 3 successful presses
  assert.equal(S.noticePick([{ kind: 7, presses: 3 }], "full").kind, 8);
  assert.equal(S.noticePick([{ kind: 7, presses: 2 }], "full").kind, 7);
  // arrival order breaks a tie; junk entries are ignored
  const first = { kind: 1, id: "a" };
  const p = S.noticePick([{ kind: 9 }, null, first, { kind: 1, id: "b" }], "full");
  assert.equal(p.notice, first);
  assert.equal(p.more, 1);
});

test("buildLine: the 4 states and their words", () => {
  const words = {};
  for (const key of S.BUILD_ORDER) {
    const b = S.buildLine(BUILD_STATES[key]);
    assert.equal(b.state, key);
    words[key] = b.glyph + " " + b.word;
    assert.equal(b.canPaste, key === "none");
  }
  assert.deepEqual(words, { fits: "[+] Build fits", old: "[?] Old build",
                            wrong_class: "[?] Wrong class", none: "[ ] No build" });
  assert.equal(S.buildLine(null).state, "none");
  assert.equal(S.buildLine({ build: { loaded: false } }).state, "none");
  assert.equal(S.buildLine(BUILD_STATES.old).tone, "warn");
  assert.notEqual(S.buildLine(BUILD_STATES.old).word.toLowerCase(), "stale");
});

test("keptChecks: best first against the current build", () => {
  const build = { loaded: true };
  assert.deepEqual(S.keptChecks(KEPT, build, "full").map((x) => x.score_delta), [9, 5, 3]);
  assert.deepEqual(S.keptChecks(KEPT, build, "compact").map((x) => x.score_delta), [9]);
  assert.deepEqual(S.keptChecks(KEPT, null, "full"), []);
  assert.deepEqual(S.keptChecks(KEPT, { loaded: false }, "full"), []);
  // a re-score re-orders it by itself
  const rescored = KEPT.map((x) => Object.assign({}, x, { score_delta: -x.score_delta }));
  assert.deepEqual(S.keptChecks(rescored, build, "full").map((x) => x.at), [4, 1, 3]);
  // no input gives more than 3 rows (1 compact)
  const many = Array.from({ length: 12 }, (_, i) => ({ score_delta: i, at: i }));
  assert.equal(S.keptChecks(many, build, "full").length, 3);
  assert.equal(S.keptChecks(many, build, "compact").length, 1);
  // a zero or negative gain still ranks, best first (each row has its word)
  const down = [{ score_delta: -4, at: 1 }, { score_delta: 0, at: 2 }];
  assert.deepEqual(S.keptChecks(down, build, "full").map((x) => x.score_delta), [0, -4]);
  // a tie goes to the newer check; no number, no row
  const tie = [{ score_delta: 2, at: 1 }, { score_delta: 2, at: 7 }, { at: 9 }];
  assert.deepEqual(S.keptChecks(tie, build, "full").map((x) => x.at), [7, 1]);
});

test("G3: every state fits every track (7 x 6 x 5 x 8 x 4 x 2)", () => {
  let n = 0;
  for (const cls of S.SIZE_CLASSES) {
    const t = S.trackSet(cls);
    for (const modeName of S.MODES) {
      const mode = S.contextMode(MODE_STATES[modeName], true);
      assert.equal(mode, modeName);
      for (let open = 0; open <= 5; open++) {
        const tr = trades(open);
        const feed = S.feedRows(tr, EVENTS);
        // every open trade has a row
        const ids = feed.rows.filter((r) => r.kind === "trade").map((r) => r.item.id);
        assert.deepEqual(ids.slice().sort(), tr.map((x) => x.id).sort());
        assert.equal(feed.rows.length, Math.min(5, open + 3));
        for (const item of S.ITEM_KINDS) {
          for (const kind of S.NOTICE_KINDS) {
            const queue = kind === 8 ? [] : [{ kind }, { kind: 7 }];
            const notice = S.noticePick(queue, cls);
            for (const bkey of S.BUILD_ORDER) {
              const bstate = BUILD_STATES[bkey];
              const kept = S.keptChecks(KEPT, bstate.build, cls);
              const build = S.buildLine(bstate);
              assert.equal(build.state, bkey);
              const lay = S.layout({ mode, feed, notice, kept, item }, cls);
              for (const r of S.REGIONS) {
                const g = lay.regions[r];
                assert.equal(g.track, t.tracks[r]);
                assert.ok(g.content <= g.track,
                  `${cls} ${mode} ${open} ${item} ${kind} ${bkey}: ${r} ${g.content} > ${g.track}`);
              }
              assert.ok(lay.regions.c.rows <= t.rows.c);
              assert.ok(lay.regions.t.rows <= t.rows.t);
              assert.ok(lay.regions.n.rows <= t.rows.n);
              assert.ok(lay.regions.u.rows <= t.rows.u);
              assert.equal(lay.left, lay.grid);
              assert.equal(lay.right, lay.grid);
              assert.equal(lay.grid, cls === "full" ? 652 : 592);
              n++;
            }
          }
        }
      }
    }
  }
  assert.equal(n, 7 * 6 * 5 * 8 * 4 * 2);
});

test("G3: worst-case content per region (3.7 and 3.8 tables)", () => {
  const worst = (cls, mode) => S.layout({
    mode, feed: S.feedRows(trades(5), EVENTS), notice: S.noticePick([{ kind: 1 }], cls),
    kept: S.keptChecks(KEPT, { loaded: true }, cls), item: "verdict"
  }, cls).regions;
  const full = worst("full", "guide");
  assert.deepEqual([full.g.content, full.c.content, full.t.content, full.n.content,
                    full.b.content, full.i.content, full.u.content],
                   [98, 226, 200, 94, 66, 342, 98]);
  assert.ok(full.i.slack >= 16);
  // T and I follow their input: an empty feed and the teach card are short
  const quiet = S.layout({ mode: "none", feed: S.feedRows([], {}), item: "teach" }, "full");
  assert.equal(quiet.regions.t.content, 2 + 12 + 26 + 32);
  assert.equal(quiet.regions.i.content, 2 + 24 + 66);
  // a sixth row would not fit T: the check is not circular
  const six = { rows: new Array(6).fill({ kind: "trade" }) };
  assert.ok(S.layout({ mode: "none", feed: six }, "full").regions.t.slack < 0);
  const compact = worst("compact", "guide");
  assert.deepEqual([compact.c.content, compact.n.content, compact.i.content, compact.u.content],
                   [204, 50, 342, 50]);
  assert.ok(compact.i.slack >= 6);
  // per mode, full class (3.4): setup 216, idle 204, error 198, town 192, map 182
  const px = (m) => worst("full", m).c.content;
  assert.deepEqual(S.MODES.map(px), [216, 198, 204, 182, 192, 226, 74]);
  // compact: setup drops its promise line, every mode keeps at most 6 rows
  assert.equal(worst("compact", "setup").c.content, 196);
  for (const m of S.MODES) { assert.ok(worst("compact", m).c.slack >= 2, m); }
  for (const r of S.REGIONS) { assert.ok(full[r].slack >= 2, r); }
});

/* ---- G11, table half: hudLine2 ------------------------------------------- */

const BASE = { data: true, level: 74, deaths: 3 };
const line = (extra) => S.hudLine2(Object.assign({}, BASE, extra));
const text = (l) => (l.guide ? l.guide
  : [l.level && l.deaths ? l.level + "  " + l.deaths : l.level, l.status]
    .filter(Boolean).join(" | "));

test("hudLine2: the 7 ranks, one order, first match", () => {
  const all = { log: "waiting for log", coveredTrades: 2, under: "3 lv under",
                away: "AFK", zoneGuide: "always", guideShort: "Find the well",
                campaign: "Boss: cold", now: 100, bumpAt: null };
  const order = [
    [1, "log", "waiting for log"],
    [2, "coveredTrades", "2 trades"],
    [3, "under", "3 lv under"],
    [4, "away", "AFK"],
    [5, "guideShort", "Find the well"],
    [6, "campaign", "Boss: cold"]
  ];
  const input = Object.assign({}, all);
  for (const [rank, field, shown] of order) {
    const l = line(input);
    assert.equal(l.rank, rank, field);
    assert.equal(rank === 5 ? l.guide : l.status, shown);
    delete input[field];
  }
  const plain = line(input);
  assert.equal(plain.rank, 7);
  assert.equal(text(plain), "Lv 74  3 deaths");
  // the singular as the overlay's format.tradeCount says it today
  assert.equal(line({ coveredTrades: 1 }).status, "1 trade");
  // the 5.2 words all fit the 27-character limit
  for (const w of S.LOG_WORDS) { assert.ok(w.length <= S.WORD_MAX, w); }
  assert.equal(line({ deaths: 1 }).deaths, "1 death");
});

test("hudLine2: before any data the log word stands alone", () => {
  for (const w of S.LOG_WORDS) {
    const l = S.hudLine2({ data: false, log: w, level: 74, deaths: 3 });
    assert.deepEqual([l.rank, l.level, l.deaths, l.status], [1, "", "", w]);
  }
  const quiet = S.hudLine2({ data: false, level: 74 });
  assert.deepEqual([quiet.level, quiet.deaths, quiet.status], ["", "", ""]);
});

test("hudLine2: the 26-character rule", () => {
  // fits: "Lv 74  3 deaths" + "3 lv under" = 25
  const a = line({ under: "3 lv under" });
  assert.equal(text(a), "Lv 74  3 deaths | 3 lv under");
  assert.equal(S.line2Chars(a), 25);
  // over 26: the deaths text drops
  const b = line({ campaign: "Boots: no speed" });
  assert.deepEqual([b.level, b.deaths, b.status], ["Lv 74", "", "Boots: no speed"]);
  const c = line({ level: 100, deaths: 999, campaign: "Boots: no speed" });
  assert.equal(text(c), "Lv 100 | Boots: no speed");
  // a word over 20 stands alone; at most 27
  const d = line({ log: "not reading - see dashboard" });
  assert.deepEqual([d.level, d.deaths, d.status], ["", "", "not reading - see dashboard"]);
  assert.equal(S.line2Chars(d), 27);
  const e = line({ campaign: "x".repeat(28) });
  assert.equal(e.rank, 7);
  assert.equal(e.status, "");
  // every rank and level from 1 to 100 with up to 999 deaths keeps the rule
  const words = S.LOG_WORDS.concat(["2 trades", "5 trades", "12 lv under", "AFK", "DND",
                                    "Boss: cold", "Boots: no speed"]);
  for (const level of [1, 9, 74, 100]) {
    for (const deaths of [0, 1, 99, 999]) {
      for (const w of words) {
        const l = line({ level, deaths, campaign: w });
        const n = S.line2Chars(l);
        assert.ok(l.status.length > S.WORD_ALONE ? n <= S.WORD_MAX : n <= S.LINE2_CHARS,
                  `${level} ${deaths} ${w}: ${n}`);
      }
    }
  }
});

test("hudLine2: rank 5 under Always, the 20 s return, never under On entry", () => {
  const g = { zoneGuide: "always", guideShort: "Find the well", now: 1000 };
  assert.equal(line(g).rank, 5);
  assert.equal(line(g).level, "");
  // a death or level-up puts level and deaths back for 20 s
  assert.equal(line(Object.assign({ bumpAt: 990 }, g)).rank, 7);
  assert.equal(text(line(Object.assign({ bumpAt: 990 }, g))), "Lv 74  3 deaths");
  assert.equal(line(Object.assign({ bumpAt: 981 }, g)).rank, 7);
  assert.equal(line(Object.assign({ bumpAt: 980 }, g)).rank, 5);
  // the campaign word shows meanwhile, under the guide's yield
  assert.equal(line(Object.assign({ bumpAt: 990, campaign: "Boss: cold" }, g)).rank, 6);
  // ranks 1-4 win at once
  assert.equal(line(Object.assign({ away: "DND" }, g)).rank, 4);
  // On entry (the default) and Never: rank 5 never fires
  for (const zoneGuide of ["on_entry", "never", undefined]) {
    assert.equal(line(Object.assign({}, g, { zoneGuide })).rank, 7);
  }
  // no short or one over 34 characters: no guide line
  assert.equal(line(Object.assign({}, g, { guideShort: "" })).rank, 7);
  assert.equal(line(Object.assign({}, g, { guideShort: "x".repeat(35) })).rank, 7);
  assert.equal(line(Object.assign({}, g, { guideShort: "x".repeat(34) })).rank, 5);
});

/* ---- G11, table half: cardHolder ----------------------------------------- */

test("cardHolder: the 5 holders, first match", () => {
  const press = { at: 100, expiresAt: 120 };
  const open = trades(3);
  const moment = { kind: "zone", at: 100 };
  const hint = { due: true, key: "Ctrl+Alt+Shift+F12" };
  const all = { now: 105, press, trades: open, moment, hint };
  const h1 = S.cardHolder(all);
  assert.equal(h1.holder, "press");
  assert.equal(h1.card, press);
  const h2 = S.cardHolder(Object.assign({}, all, { press: null }));
  assert.equal(h2.holder, "trade");
  assert.equal(h2.card.id, 3);
  assert.equal(h2.more, 2);
  const h3 = S.cardHolder(Object.assign({}, all, { press: null, trades: [] }));
  assert.equal(h3.holder, "moment");
  const h4 = S.cardHolder({ now: 105, hint });
  assert.equal(h4.holder, "hint");
  assert.equal(h4.line1, "Check: Ctrl+Alt+Shift+F12");
  assert.ok(h4.line1.length <= S.CARD_CHARS);
  const h5 = S.cardHolder({ now: 105 });
  assert.equal(h5.holder, "none");
  assert.deepEqual([h1, h2, h3, h4, h5].map((h) => h.rank), [1, 2, 3, 4, 5]);
  assert.deepEqual([h1, h2, h3, h4, h5].map((h) => h.holder), S.HOLDERS);
});

test("cardHolder: press card time, trade return, moment never waits", () => {
  const press = { at: 100, expiresAt: 120 };
  // the press card leaves at its time and the trade comes back by itself
  assert.equal(S.cardHolder({ now: 119.9, press, trades: trades(1) }).holder, "press");
  assert.equal(S.cardHolder({ now: 120, press, trades: trades(1) }).holder, "trade");
  assert.equal(S.cardHolder({ now: 120, press, trades: trades(1) }).more, 0);
  // a moment card lasts 12 s
  const m = { kind: "act", at: 200 };
  assert.equal(S.cardHolder({ now: 211.9, moment: m }).holder, "moment");
  assert.equal(S.cardHolder({ now: 212, moment: m }).holder, "none");
  assert.equal(S.cardHolder({ now: 199, moment: m }).holder, "none");
  // arrived while a press card held the slot: dropped, never shown later
  const busy = { at: 195, expiresAt: 205 };
  assert.equal(S.cardHolder({ now: 206, moment: m, press: busy }).holder, "none");
  // a press after the moment interrupts it for good
  const later = { at: 203, expiresAt: 206 };
  assert.equal(S.cardHolder({ now: 204, moment: m, press: later }).holder, "press");
  assert.equal(S.cardHolder({ now: 207, moment: m, press: later }).holder, "none");
  // a press that ended before the moment came does not block it
  const old = { at: 150, expiresAt: 170 };
  assert.equal(S.cardHolder({ now: 205, moment: m, press: old }).holder, "moment");
  // a moment the caller marked dropped (a trade card held or took the
  // slot, then closed) never shows, even inside its 12 s
  assert.equal(S.cardHolder({ now: 205, moment: { kind: "zone", at: 200, dropped: true },
                              hint: { due: true, key: "F" } }).holder, "hint");
  // an unknown moment kind is not a card
  assert.equal(S.cardHolder({ now: 205, moment: { kind: "tip", at: 200 } }).holder, "none");
});

test("cardHolder: the key hint fits the 26-character line", () => {
  assert.equal(S.KEY_NAME_MAX, 19);
  assert.equal(S.CARD_CHARS, 26);
  const key19 = "K".repeat(19);
  // over 26 with the full wording: the short form "Check: <key>" (overlayview)
  assert.equal(S.cardHolder({ hint: { due: true, key: key19 } }).line1, "Check: " + key19);
  assert.equal(S.cardHolder({ hint: { due: true, key: "Alt+Shift+E" } }).line1,
               "Alt+Shift+E: check an item");
  // CARD-HINT-TWIN (CL2-1): both forms at their edges, the twin of
  // overlayview._hint_head
  const line = (key) => S.cardHolder({ hint: { due: true, key } }).line1;
  assert.equal(line("K".repeat(11)), "K".repeat(11) + ": check an item");
  assert.equal(line("K".repeat(11)).length, 26);
  assert.equal(line("K".repeat(12)), "Check: " + "K".repeat(12));
  assert.equal(line("Ctrl+Shift+E"), "Check: Ctrl+Shift+E");
  assert.equal(line(key19).length, 26);
  // a key too long for either form shows no hint, never a cut key
  assert.equal(S.cardHolder({ hint: { due: true, key: key19 + "K" } }).holder, "none");
  assert.equal(S.cardHolder({ hint: { due: false, key: "F" } }).holder, "none");
  assert.equal(S.cardHolder({ hint: { due: true, key: "" } }).holder, "none");
  assert.equal(S.CARD_EDGE_PX, 62);
  assert.deepEqual(S.STATUS_CARD_WORDS, ["Build loaded", "Not an item", "Copy the item first"]);
});

test("slots.js is pure: no DOM, timer, network or clipboard", () => {
  const src = web.source("slots.js");
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  for (const bad of ["document", "window", "setTimeout", "setInterval", "fetch(",
                     "XMLHttpRequest", "clipboard", "localStorage", "EventSource",
                     "require("]) {
    assert.ok(!code.includes(bad), bad);
  }
  assert.ok(/^[\x00-\x7f]*$/.test(src), "ASCII only");
  assert.ok(!src.includes("\r"), "LF only");
});
