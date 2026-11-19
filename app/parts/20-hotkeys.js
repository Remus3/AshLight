"use strict";
/* OVL-MAIN-PARTS (decision 0053): the two global shortcuts, the first
   part. The keys are the ones app/main.js picked and validated
   (Hotkey.pick, AREA-AUDIT P5-3: env, then config, then the default) and
   passes as ctx.keys; this part only registers them, at app ready, with
   the same two log sentences as before. The item check handler is
   ctx.actions.onEval, built in main.js around the one clipboard read per
   manual press; this part never reads the clipboard. ToS floor: a global
   shortcut only listens for the player's own press; nothing is sent to
   the game. */

/* Register both keys on gs (Electron's globalShortcut, or a test fake). */
function registerKeys(gs, ctx) {
  const keys = ctx.keys || {};
  const acts = ctx.actions || {};
  if (!gs.register(keys.toggle, acts.toggle)) {
    ctx.log("toggle shortcut not available: " + keys.toggle);
  }
  if (!gs.register(keys.eval, acts.onEval)) {
    ctx.log("item check shortcut not available: " + keys.eval);
  }
}

function ready(ctx) {
  registerKeys(require("electron").globalShortcut, ctx);
}

module.exports = { ready, registerKeys };
