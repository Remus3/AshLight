/* AshLight dashboard: the panel registry (TEST-WEB-REGISTRY, finding F-135;
   research 0047 R4 (c)). Every dashboard panel registers itself here, and
   web/app.js runs render(), tick() and start() as three loops over the
   registered panels with a try / catch per panel, so one throwing paint
   no longer blanks the cards after it and a new card edits no shared
   function: it registers one more entry with its own order.

   UMD like web/fmt.js: CommonJS for node --test (app/test/registry.test.js),
   window.ALApp in the page, where it is the second script tag (after
   fmt.js). The Play regions keep their own registry (web/regions.js); app.js
   calls it after these loops.

   No DOM, no timers, no network, no clipboard, no live region: the registry
   only calls the panels' own functions.

   Exports (one shared registry; create() makes a fresh one for tests):
   - register(spec): spec = {name, order, paint, tick, wire}. name: a unique
     non-empty string (a second panel with a name already taken is
     refused with a TypeError). order: a finite number; panels run in
     ascending order, equal orders in register order. paint, tick, wire:
     each optional, but a panel has at least one. A panel registered after
     start() is wired at once.
   - render(...args): every paint, in order, with the given arguments.
   - tick(...args): every tick, in order, with the given arguments.
   - start(...args): every wire, in order, once; a second call does nothing.
   - names(): the panel names in run order.
   One panel that throws is caught and said once on the console per panel,
   phase and cause (at most 20 lines a page); the panels after it still
   run. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALApp = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SAY_CAP = 20; // console lines a page, so a broken panel cannot flood it

  function isFn(v) { return typeof v === "function"; }
  function isName(v) { return typeof v === "string" && v.length > 0; }

  function defaultWarn(text) {
    if (typeof console !== "undefined" && console && isFn(console.warn)) { console.warn(text); }
  }

  function create(opts) {
    var warn = opts && isFn(opts.warn) ? opts.warn : defaultWarn;
    var panels = [];     // in run order
    var said = {};       // "name phase cause" -> true: each failure is said once
    var saidCount = 0;
    var started = false;
    var startArgs = [];

    function clean(spec) {
      if (!spec || typeof spec !== "object" || !isName(spec.name)) {
        throw new TypeError("ALApp.register: a panel needs a name");
      }
      panels.forEach(function (p) {
        if (p.name === spec.name) {
          throw new TypeError("ALApp.register: " + spec.name + " is registered twice");
        }
      });
      if (typeof spec.order !== "number" || !isFinite(spec.order)) {
        throw new TypeError("ALApp.register: " + spec.name + " needs a number order");
      }
      var p = {
        name: spec.name,
        order: spec.order,
        paint: isFn(spec.paint) ? spec.paint : null,
        tick: isFn(spec.tick) ? spec.tick : null,
        wire: isFn(spec.wire) ? spec.wire : null
      };
      if (!p.paint && !p.tick && !p.wire) {
        throw new TypeError("ALApp.register: " + spec.name + " has no paint, tick or wire");
      }
      return p;
    }

    /* Run one panel function; a throw is caught, said once per panel,
       phase and cause (at most SAY_CAP lines a page), and the loop goes on
       with the next panel. */
    function guard(p, phase, args) {
      try {
        p[phase].apply(null, args);
        return true;
      } catch (e) {
        var msg = e && e.message ? e.message : String(e);
        var key = p.name + " " + phase + " " + msg;
        if (!said[key] && saidCount < SAY_CAP) {
          said[key] = true;
          saidCount += 1;
          warn("panel " + p.name + " " + phase + " failed: " + msg);
        }
        return false;
      }
    }

    function each(phase, args) {
      panels.slice().forEach(function (p) {
        if (p[phase]) { guard(p, phase, args); }
      });
    }

    function register(spec) {
      var p = clean(spec);
      var at = panels.length;
      while (at > 0 && panels[at - 1].order > p.order) { at -= 1; }
      panels.splice(at, 0, p);
      if (started && p.wire) { guard(p, "wire", startArgs); }
      return p.name;
    }

    function render() { each("paint", Array.prototype.slice.call(arguments)); }
    function tick() { each("tick", Array.prototype.slice.call(arguments)); }

    function start() {
      if (started) { return; }
      started = true;
      startArgs = Array.prototype.slice.call(arguments);
      each("wire", startArgs);
    }

    function names() { return panels.map(function (p) { return p.name; }); }

    return { register: register, render: render, tick: tick, start: start, names: names };
  }

  var api = create();
  api.create = create;
  return api;
}));
