"use strict";
/* OVL-WAKE-COMPANION (decision 0041 amendment 2026-11-19, decision 0053
   parts seam): when the log goes from idle to a fresh line, the companion
   window comes back if it is in the tray or minimised, without focus and
   only on a display other than the overlay's (app/client/link.js
   wakeAction decides, app/client/window.js wake() acts).

   The trigger is the overlay gate (decision 0029: Client.txt freshness
   only): a false -> true change of gate(visible) is idle-to-fresh. No
   process or window of the game is looked at, nothing is sent anywhere,
   no key is registered. An overlay-only start has no client: nothing
   happens. */

const last = new WeakMap(); // ctx -> the previous gate value

function gate(ctx, visible) {
  const now = visible === true;
  const before = ctx && last.has(ctx) ? last.get(ctx) : null;
  if (ctx) { last.set(ctx, now); }
  if (before !== false || now !== true) { return; }
  const client = ctx && typeof ctx.getClient === "function" ? ctx.getClient() : null;
  if (!client || typeof client.wake !== "function") { return; }
  client.wake({ wasIdle: true, fresh: true });
}

module.exports = { gate };
