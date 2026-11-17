"use strict";
/* TC-EVAL-UI: the overlay item check card (format.js evalCard, render_gate
   eval fields and expiry) and the hotkey's one-read-per-press rule
   (eval_hotkey.js, decision 0003). */
const test = require("node:test");
const assert = require("node:assert/strict");
const fmt = require("../shared/format.js");
const gate = require("../shared/render_gate.js");
const hk = require("../eval_hotkey.js");

const snap = {
  zone: "Clearfell", in_hideout: false, zone_entered_at: 1000, level: 3, deaths: 1,
  version: 7,
  trade_requests: [{ id: 1, from: "Quietfox", item: "Plain Belt", price_amount: 5,
                     price_currency: "exalted" }],
  eval: { ok: true, verdict: "upgrade", at: 1000, expires_at: 1020,
          text: { head: "Upgrade +47.5 vs Ring 1", item: "Storm Loop",
                  line: "+35 to maximum Life", sentence: "x", comparisons: [] } }
};

test("evalCard clips the core's words and keeps the verdict", () => {
  assert.deepEqual(fmt.evalCard(snap.eval),
    { head: "Upgrade +47.5 vs Ring 1", item: "Storm Loop", line: "+35 to maximum Life",
      verdict: "upgrade" });
  const long = fmt.evalCard({ ok: true, verdict: "downgrade",
                              text: { head: "H", item: "A".repeat(50), line: "" } });
  assert.equal(long.item.length, 34);
  assert.ok(long.item.endsWith("..."));
  assert.equal(fmt.evalCard({ ok: false, text: { head: "Not an item" } }).verdict, "note");
  assert.deepEqual(fmt.evalCard(null), { head: "", item: "", line: "", verdict: "" });
  assert.deepEqual(fmt.evalCard({ ok: true, text: {} }).head, "");
});

test("the card shows until expires_at, then the trade card comes back", () => {
  const on = gate.hudModel(snap, 1005, "live");
  assert.equal(on.evalHead, "Upgrade +47.5 vs Ring 1");
  assert.equal(on.evalVerdict, "upgrade");
  // one card slot (design 0001 section 10): the trade card waits
  assert.equal(on.tradeFrom, "");
  assert.equal(on.tradeItem, "");
  const off = gate.hudModel(snap, 1020, "live");
  assert.equal(off.evalHead, "");
  assert.equal(off.tradeFrom, "Trade: Quietfox");
  // UX-REVIEW F1: the "1 trade" count in the status slot goes with the card
  assert.equal(on.trades, "1 trade");
  assert.equal(off.trades, "");
  assert.deepEqual(gate.changedFields(on, off).sort(),
    ["evalHead", "evalItem", "evalLine", "evalVerdict", "tradeFrom", "tradeItem",
     "tradeWhere", "trades"].sort());
});

test("the card also shows before the Client.txt opt-in", () => {
  const m = gate.hudModel({ ...snap, tailer: { consented: false } }, 1001, "live");
  assert.equal(m.zone, "AshLight");
  assert.equal(m.evalItem, "Storm Loop");
});

test("msUntilEvalExpires schedules the one repaint that hides the card", () => {
  assert.equal(gate.msUntilEvalExpires(snap, 1005), 15000);
  assert.equal(gate.msUntilEvalExpires(snap, 1019.95), 250);
  assert.equal(gate.msUntilEvalExpires(snap, 1020), null);
  assert.equal(gate.msUntilEvalExpires({ ...snap, eval: null }, 1005), null);
  assert.equal(gate.msUntilEvalExpires(null, 0), null);
});

test("a re-score with the same words costs no frame", () => {
  const a = gate.hudModel(snap, 1005, "live");
  const b = gate.hudModel({ ...snap, version: 9, eval: { ...snap.eval, id: 2 } }, 1005, "live");
  assert.equal(gate.shouldRender(a, b), false);
});

function fakeDeps(text, fail) {
  const d = { reads: 0, posts: [], logs: [] };
  d.readText = () => { d.reads += 1; return text; };
  d.post = (path, body) => {
    d.posts.push([path, body]);
    return fail ? Promise.reject(new Error("HTTP 401")) : Promise.resolve(200);
  };
  d.log = (m) => d.logs.push(m);
  return d;
}

test("hotkey: creating it reads nothing; each press reads the clipboard once", async () => {
  const d = fakeDeps("Item Class: Rings\nRarity: Rare\nStorm Loop\n");
  let t = 10000;
  d.now = () => t;
  const press = hk.createEvalHotkey(d);
  assert.equal(d.reads, 0);
  assert.equal(await press(), true);
  assert.equal(d.reads, 1);
  assert.deepEqual(d.posts, [["/api/eval", { item: "Item Class: Rings\nRarity: Rare\nStorm Loop\n" }]]);
  t += hk.REPEAT_GAP_MS + 1;
  await press();
  assert.equal(d.reads, 2);
});

test("hotkey: a held key (auto-repeat) reads the clipboard once (AUDIT-HOTKEY-REPEAT)", async () => {
  // Windows auto-repeat re-fires a held global shortcut every ~30 ms after a
  // 250-1000 ms delay. Decision 0003: one read per manual press, so every
  // event inside REPEAT_GAP_MS of the previous event is the same press.
  const d = fakeDeps("x");
  let t = 5000;
  d.now = () => t;
  const press = hk.createEvalHotkey(d);
  assert.equal(await press(), true);
  t += 1000; // the longest Windows repeat delay
  assert.equal(await press(), false);
  for (let i = 0; i < 100; i++) {
    t += 33;
    assert.equal(await press(), false);
  }
  assert.equal(d.reads, 1);
  assert.equal(d.posts.length, 1);
  t += hk.REPEAT_GAP_MS + 1; // released, then pressed again
  assert.equal(await press(), true);
  assert.equal(d.reads, 2);
  assert.ok(hk.REPEAT_GAP_MS > 1000);
});

test("hotkey: without an injected clock it still guards repeats", async () => {
  const d = fakeDeps("x");
  const press = hk.createEvalHotkey(d);
  assert.equal(await press(), true);
  assert.equal(await press(), false);
  assert.equal(d.reads, 1);
});

test("hotkey: a press while one is in flight reads nothing", async () => {
  const d = fakeDeps("x");
  let release;
  d.post = () => new Promise((r) => { release = r; });
  const press = hk.createEvalHotkey(d);
  const first = press();
  assert.equal(await press(), false);
  assert.equal(d.reads, 1);
  release(200);
  assert.equal(await first, true);
});

test("hotkey: empty or huge clipboard, failures are logged, never thrown", async () => {
  const empty = fakeDeps(null);
  await hk.createEvalHotkey(empty)();
  assert.deepEqual(empty.posts[0][1], { item: "" });
  const big = fakeDeps("A".repeat(hk.MAX_ITEM_CHARS + 10));
  await hk.createEvalHotkey(big)();
  assert.equal(big.posts[0][1].item.length, hk.MAX_ITEM_CHARS);
  const bad = fakeDeps("x", true);
  assert.equal(await hk.createEvalHotkey(bad)(), false);
  assert.match(bad.logs[0], /item check not sent: HTTP 401/);
  const throws = fakeDeps("x");
  throws.readText = () => { throw new Error("clipboard busy"); };
  await hk.createEvalHotkey(throws)();
  assert.deepEqual(throws.posts[0][1], { item: "" });
});

test("hotkey module has no timer and no watcher", () => {
  const src = require("fs").readFileSync(require.resolve("../eval_hotkey.js"), "utf8");
  for (const word of ["setInterval", "setTimeout", "fs.watch", "watchFile", "sendInput", "keyTap"]) {
    assert.ok(!src.includes(word), word);
  }
});
