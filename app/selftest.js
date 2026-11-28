"use strict";
/* REL-SELFTEST-CLIENT (research 0066 F11a): the client half of the update
   self-test. The installer starts the NEW version's Electron main process
   hidden as `electron.exe <app folder> --selftest`
   (server/al/install/selftest.py, stage "client"); app/main.js then runs
   start() below instead of any window, tray, hotkey or core call.

   Pass (exit 0) only when:
   - every app/parts/*.js file loads (require) and its early hook runs,
     and the ready hook of the side-effect-free parts in SAFE_READY runs,
     all without a throw (a throwing part: exit EXIT.part);
   - the egress lock (app/parts/15-egress.js isLocked) is on for both
     sessions, the default one and the companion's partition (else
     EXIT.egress);
   - no window exists (else EXIT.window);
   - all of it within TIMEOUT_MS (else EXIT.timeout; the installer's own
     limit is 30 s).
   The other parts' ready hooks (hotkeys, which register global keys and
   write ops/runtime/hotkeys.json) are not run: a self-test never takes a
   key or writes player state. One `selftest: <word>` line on stdout, no
   path in it.

   Pure: Electron's app, session and BrowserWindow are passed in, so the
   node tests drive it with fakes. */

const ARG = "--selftest";
const EXIT = { ok: 0, part: 3, egress: 4, window: 5, crash: 6, timeout: 7 };
const TIMEOUT_MS = 25000;
const EGRESS_PART = "15-egress.js";
// ready hooks that only set up session handlers (no key, file or window)
const SAFE_READY = ["12-pages.js", EGRESS_PART];

function wanted(argv) {
  return Array.isArray(argv) && argv.includes(ARG);
}

function readyParts(parts) {
  return (Array.isArray(parts) ? parts : []).filter((p) => SAFE_READY.includes(p.name));
}

/* True when the egress part is loaded and says every session is locked. */
function egressOn(parts, sessions) {
  const part = (Array.isArray(parts) ? parts : []).find((p) => p.name === EGRESS_PART);
  const isLocked = part && part.mod && part.mod.isLocked;
  if (typeof isLocked !== "function") { return false; }
  const list = Array.isArray(sessions) ? sessions : [];
  return list.length > 0 && list.every((s) => isLocked(s) === true);
}

/* {code, word} from what the run saw; part failures win, then the egress
   lock, then a window. */
function verdict(seen) {
  const s = seen && typeof seen === "object" ? seen : {};
  const failures = Array.isArray(s.failures) ? s.failures : [];
  if (failures.length) {
    const f = failures[0];
    return { code: EXIT.part, word: "part " + f.name + " failed in " + f.hook };
  }
  if (s.egress !== true) { return { code: EXIT.egress, word: "egress lock off" }; }
  if (Number(s.windows) !== 0) { return { code: EXIT.window, word: "a window opened" }; }
  return { code: EXIT.ok, word: "ok" };
}

/* Run the self-test. o: {app, session, BrowserWindow, Parts, parts, ctx,
   partition (default: app/client/window.js PARTITION), failures (load
   and early failures so far), out, timeoutMs,
   setTimer}. Ends with app.exit(code); returns a promise of the verdict. */
function start(o) {
  const out = o.out && typeof o.out.write === "function" ? o.out : { write: () => {} };
  const failures = (Array.isArray(o.failures) ? o.failures : []).slice();
  const setTimer = typeof o.setTimer === "function" ? o.setTimer : setTimeout;
  let done = false;
  function finish(v) {
    if (done) { return v; }
    done = true;
    out.write("selftest: " + v.word + "\n");
    o.app.exit(v.code);
    return v;
  }
  const timer = setTimer(() => finish({ code: EXIT.timeout, word: "timed out" }),
    Number(o.timeoutMs) > 0 ? Number(o.timeoutMs) : TIMEOUT_MS);
  if (timer && typeof timer.unref === "function") { timer.unref(); }
  return Promise.resolve()
    .then(() => o.app.whenReady())
    .then(() => {
      if (done) { return null; }
      for (const f of o.Parts.run(readyParts(o.parts), "ready", o.ctx)) { failures.push(f); }
      // the companion's partition, as app/parts/15-egress.js locks it
      const partition = o.partition || require("./client/window.js").PARTITION;
      const sessions = [o.session.defaultSession, o.session.fromPartition(partition)];
      return finish(verdict({
        failures: failures,
        egress: egressOn(o.parts, sessions),
        windows: o.BrowserWindow.getAllWindows().length
      }));
    })
    .catch(() => finish({ code: EXIT.crash, word: "crashed" }));
}

module.exports = { ARG, EXIT, TIMEOUT_MS, SAFE_READY, EGRESS_PART, wanted, readyParts,
                   egressOn, verdict, start };
