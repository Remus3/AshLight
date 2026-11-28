"use strict";
/* OVL-MAIN-PARTS (decision 0053): the main-process parts seam.

   Later client features land as one file under app/parts/ (NN-name.js)
   instead of another edit of app/main.js or app/client/window.js. A part
   exports any of the hook functions in HOOKS; each is called with the one
   shared ctx that main.js builds, then the hook's own arguments.

   Pure: no Electron, no file access of its own (readdirSync and require
   are passed in), so the node tests load it as is. */

const path = require("path");

/* Every hook main.js runs, in the order a normal client start meets them:
   early (before app ready), ready (before the "overlay started" line),
   overlayWindow (win), clientWindow (win, ses), configChanged, gate
   (visible), toggled, quit. */
const HOOKS = ["early", "ready", "overlayWindow", "clientWindow", "configChanged",
               "gate", "toggled", "quit"];

/* The parts of dir: its *.js files sorted by file name, each loaded with
   req. A missing or unreadable dir is no parts. A part that fails to load
   is logged and skipped; with a failed array it is also recorded there as
   {name, hook: "load", message} (REL-SELFTEST-CLIENT: the client self-test
   fails on it). */
function load(dir, readdirSync, req, log, failed) {
  let names;
  try {
    names = readdirSync(dir);
  } catch (e) {
    return [];
  }
  const out = [];
  for (const name of names.filter((n) => typeof n === "string" && n.endsWith(".js")).sort()) {
    try {
      const mod = req(path.join(dir, name));
      out.push({ name: name, mod: mod || {} });
    } catch (e) {
      const message = String(e && e.message);
      if (typeof log === "function") { log("part " + name + " not loaded: " + message); }
      if (Array.isArray(failed)) { failed.push({ name: name, hook: "load", message: message }); }
    }
  }
  return out;
}

/* Call hook on every part that has it, in order. A throwing part is logged
   through ctx.log and skipped; the rest still run. Returns the failures,
   [{name, hook, message}], empty when every part ran. */
function run(parts, hook, ctx, ...args) {
  const failed = [];
  for (const p of parts) {
    const fn = p.mod && p.mod[hook];
    if (typeof fn !== "function") { continue; }
    try {
      fn(ctx, ...args);
    } catch (e) {
      const message = String(e && e.message);
      failed.push({ name: p.name, hook: hook, message: message });
      if (ctx && typeof ctx.log === "function") {
        ctx.log("part " + p.name + " failed in " + hook + ": " + message);
      }
    }
  }
  return failed;
}

module.exports = { HOOKS, load, run };
