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
  assert.equal(big.reads, 1);
  assert.ok(big.posts[0][1].item.length <= hk.MAX_ITEM_CHARS);
  assert.ok(Buffer.byteLength(JSON.stringify(big.posts[0][1])) <= hk.MAX_BODY_BYTES);
  const bad = fakeDeps("x", true);
  assert.equal(await hk.createEvalHotkey(bad)(), false);
  assert.match(bad.logs[0], /item check not sent: HTTP 401/);
  const throws = fakeDeps("x");
  throws.readText = () => { throw new Error("clipboard busy"); };
  await hk.createEvalHotkey(throws)();
  assert.deepEqual(throws.posts[0][1], { item: "" });
});

test("hotkey: an empty clipboard and an item each cost exactly one read (OVL-COPY-FIRST)", async () => {
  // a press before the game wrote the clipboard posts the blank text once
  // (the core answers "Copy the item first"); no retry, no wait for a
  // change: the player copies and presses again
  for (const text of ["", "  \r\n", null, "Item Class: Rings\nRarity: Rare\nStorm Loop\n"]) {
    const d = fakeDeps(text);
    let t = 20000;
    d.now = () => t;
    const press = hk.createEvalHotkey(d);
    assert.equal(await press(), true);
    await new Promise((r) => setImmediate(r));
    assert.equal(d.reads, 1, JSON.stringify(text));
    assert.equal(d.posts.length, 1);
    assert.deepEqual(d.posts[0], ["/api/eval", { item: text === null ? "" : text }]);
    // the next manual press reads once more, never on its own
    t += hk.REPEAT_GAP_MS + 1;
    assert.equal(await press(), true);
    assert.equal(d.reads, 2);
    assert.equal(d.posts.length, 2);
  }
});

test("hotkey module has no timer and no watcher", () => {
  const src = require("fs").readFileSync(require.resolve("../eval_hotkey.js"), "utf8");
  for (const word of ["setInterval", "setTimeout", "fs.watch", "watchFile", "sendInput", "keyTap"]) {
    assert.ok(!src.includes(word), word);
  }
});

test("hotkey: a copied build fits whole, still one read and one post (TC-PRESS-BUILD)", async () => {
  // the cap is the build size now (a PoB code is about 5-60 KB); no retry
  assert.equal(hk.MAX_ITEM_CHARS, 256 * 1024);
  assert.equal(hk.MAX_BODY_BYTES, 256 * 1024);
  const code = "eNrtWVtv2zYU".padEnd(60 * 1024, "AbC-_9");
  const d = fakeDeps(code);
  assert.equal(await hk.createEvalHotkey(d)(), true);
  assert.equal(d.reads, 1);
  assert.deepEqual(d.posts, [["/api/eval", { item: code }]]);
  // an over-long text is clipped once, never read again, never refused
  const json = "{\"character\": " + "\"q\"".repeat(100 * 1024) + "}";
  const j = fakeDeps(json);
  assert.equal(await hk.createEvalHotkey(j)(), true);
  assert.equal(j.reads, 1);
  assert.equal(j.posts.length, 1);
  assert.ok(Buffer.byteLength(JSON.stringify(j.posts[0][1])) <= hk.MAX_BODY_BYTES);
  assert.ok(json.startsWith(j.posts[0][1].item));
  // non-ASCII takes more bytes than characters
  const wide = hk.fitText("\u00e9".repeat(hk.MAX_ITEM_CHARS));
  assert.ok(Buffer.byteLength(JSON.stringify({ item: wide })) <= hk.MAX_BODY_BYTES);
  assert.equal(hk.fitText(""), "");
});

// TC-WORN-KEY: the optional wear key (decision 0052, no default binding).

function fakeGs(taken) {
  const g = { bound: [], held: new Set(taken || []) };
  g.isRegistered = (k) => g.held.has(k);
  g.register = (k, fn) => {
    if (g.held.has(k)) { return false; }
    g.held.add(k);
    g.bound.push([k, fn]);
    return true;
  };
  return g;
}

test("wear key: one clipboard read per press, posted to /api/wear", async () => {
  const d = fakeDeps("Item Class: Rings\nRarity: Rare\nStorm Loop\n");
  let t = 30000;
  d.now = () => t;
  const press = hk.createEvalHotkey(d, hk.POST_WEAR);
  assert.equal(d.reads, 0); // creating it reads nothing
  assert.equal(await press(), true);
  assert.equal(d.reads, 1);
  assert.deepEqual(d.posts, [["/api/wear", { item: "Item Class: Rings\nRarity: Rare\nStorm Loop\n" }]]);
  t += hk.REPEAT_GAP_MS + 1;
  assert.equal(await press(), true);
  assert.equal(d.reads, 2);
  assert.equal(d.posts.length, 2);
  // the default path stays the item check; an unknown path never leaves
  const e = fakeDeps("x");
  await hk.createEvalHotkey(e)();
  assert.equal(e.posts[0][0], "/api/eval");
  const o = fakeDeps("x");
  await hk.createEvalHotkey(o, "/api/settings/import")();
  assert.equal(o.posts[0][0], "/api/eval");
  // a failure names the wear key and is never thrown
  const bad = fakeDeps("x", true);
  assert.equal(await hk.createEvalHotkey(bad, hk.POST_WEAR)(), false);
  assert.match(bad.logs[0], /worn item not sent: HTTP 401/);
});

test("wear key: a held key (auto-repeat) reads the clipboard once", async () => {
  const d = fakeDeps("x");
  let t = 40000;
  d.now = () => t;
  const press = hk.createEvalHotkey(d, hk.POST_WEAR);
  assert.equal(await press(), true);
  t += 1000;
  assert.equal(await press(), false);
  for (let i = 0; i < 50; i++) {
    t += 33;
    assert.equal(await press(), false);
  }
  assert.equal(d.reads, 1);
  assert.deepEqual(d.posts, [["/api/wear", { item: "x" }]]);
});

test("wear key: unset registers nothing; a set key binds, never a taken one", () => {
  const fn = () => {};
  for (const unset of [null, undefined, ""]) {
    const g = fakeGs();
    assert.equal(hk.registerWearKey(g, unset, fn, ["Alt+Shift+A", "Alt+Shift+E"]), null);
    assert.deepEqual(g.bound, []);
  }
  const g = fakeGs(["Alt+Shift+A", "Alt+Shift+E"]);
  assert.equal(hk.registerWearKey(g, "Ctrl+Shift+F7", fn, ["Alt+Shift+A", "Alt+Shift+E"]),
    "Ctrl+Shift+F7");
  assert.deepEqual(g.bound, [["Ctrl+Shift+F7", fn]]);
  // the item check's key (wanted or held) is never taken, and no fallback is tried
  const logs = [];
  const h = fakeGs(["Ctrl+Shift+F9"]);
  assert.equal(hk.registerWearKey(h, "Alt+Shift+E", fn, ["Alt+Shift+A", "Alt+Shift+E"],
    (m) => logs.push(m)), null);
  assert.equal(hk.registerWearKey(h, "Ctrl+Shift+F9", fn, [], (m) => logs.push(m)), null);
  assert.deepEqual(h.bound, []);
  assert.equal(logs.length, 2);
  assert.ok(logs.every((m) => !m.includes("item check shortcut not available")));
  // a throwing register is a refusal, not a crash
  const t = { register: () => { throw new Error("bad key"); } };
  assert.equal(hk.registerWearKey(t, "Ctrl+Shift+F7", fn, []), null);
});

test("wear key: main.js picks it with no default and shares the one read", () => {
  const src = require("fs").readFileSync(require.resolve("../main.js"), "utf8");
  assert.ok(src.includes("Hotkey.pick([raw], null, log)"));
  assert.ok(!/DEFAULT_WEAR/.test(src));
  assert.equal((src.match(/clipboard\.readText\(/g) || []).length, 1);
  assert.ok(src.includes("EvalKey.createEvalHotkey(pressDeps, EvalKey.POST_EVAL)"));
  assert.ok(src.includes("EvalKey.createEvalHotkey(pressDeps, EvalKey.POST_WEAR)"));
});
