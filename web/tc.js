/* AshLight dashboard: pure view helpers for the build view (TC-VIEW), the
   item check (TC-EVAL-UI) and the graphics advisor (GFX-ADVISOR). UMD:
   CommonJS for node --test (app/test/tc_view.test.js), window.ALTc for the
   page. No DOM, no timers, no network. Item, gem and stat words come from
   the core; these helpers only pick, order and label them. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.ALTc = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* PoB PlayerStat names shown as key stats, in this order. Others stay in
     Path of Building (the view is a summary, not a calculator). */
  var KEY_STATS = [
    ["Life", "Life", ""], ["EnergyShield", "Energy shield", ""], ["Mana", "Mana", ""],
    ["Spirit", "Spirit", ""], ["TotalDPS", "Total DPS", ""],
    ["CombinedDPS", "Combined DPS", ""], ["Armour", "Armour", ""],
    ["Evasion", "Evasion", ""], ["FireResist", "Fire resistance", "%"],
    ["ColdResist", "Cold resistance", "%"], ["LightningResist", "Lightning resistance", "%"],
    ["ChaosResist", "Chaos resistance", "%"], ["EffectiveMovementSpeedMod", "Movement speed", "x"]
  ];
  var GEAR_ORDER = ["Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots",
                    "Amulet", "Ring 1", "Ring 2", "Belt", "Flask 1", "Flask 2",
                    "Charm 1", "Charm 2", "Charm 3"];

  function num(n) {
    if (typeof n !== "number" || !isFinite(n)) { return null; }
    var r = Math.abs(n) >= 100 ? Math.round(n) : Math.round(n * 10) / 10;
    var parts = String(Math.abs(r)).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (r < 0 ? "-" : "") + parts.join(".");
  }

  /* Link-out only (decision 0009): poe2db and the PoE2 wiki pages by name. */
  function links(name) {
    if (!name || typeof name !== "string") { return []; }
    var slug = encodeURIComponent(name.trim().replace(/ /g, "_"));
    return [{ label: "poe2db", href: "https://poe2db.tw/us/" + slug },
            { label: "wiki", href: "https://www.poe2wiki.net/wiki/" + slug }];
  }

  function safeUrl(u) {
    return (typeof u === "string" && /^https:\/\/[^\s]+$/i.test(u)) ? u : "";
  }

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  /* doc: GET /api/build; live: the state snapshot (or null). */
  function buildView(doc, live) {
    var b = doc && doc.loaded ? doc.build : null;
    if (!b) {
      return { loaded: false,
               empty: "No build yet. Paste a Path of Building code or character JSON below. " +
                      "It loads as soon as you paste, and it stays loaded when AshLight restarts." };
    }
    var cls = b.class_name || "Class unknown";
    var title = b.ascendancy ? cls + " - " + b.ascendancy : cls;
    var planned = (b.level === null || b.level === undefined) ? "level unknown" : "level " + b.level;
    var you = "";
    if (live && live.level !== null && live.level !== undefined) {
      you = "You are level " + live.level + (live.zone ? " in " + live.zone : "") + ".";
    } else if (live && live.zone) {
      you = "You are in " + live.zone + ".";
    }
    var stats = [];
    KEY_STATS.forEach(function (k) {
      var v = (b.stats || {})[k[0]];
      var t = num(v);
      if (t === null) { return; }
      stats.push({ label: k[1], value: k[2] === "x" ? t + "x" : t + k[2] });
    });
    var gear = [];
    var slots = Object.keys(b.gear || {});
    slots.sort(function (x, y) {
      var a = GEAR_ORDER.indexOf(x), c = GEAR_ORDER.indexOf(y);
      return (a < 0 ? 99 : a) - (c < 0 ? 99 : c) || (x < y ? -1 : 1);
    });
    slots.forEach(function (slot) {
      var it = b.gear[slot] || {};
      var unique = String(it.rarity || "").toUpperCase() === "UNIQUE";
      gear.push({ slot: slot, name: it.name || it.base || "Unnamed item",
                  base: it.name && it.base ? it.base : "",
                  rarity: it.rarity ? it.rarity.charAt(0) + it.rarity.slice(1).toLowerCase() : "",
                  text: typeof it.text === "string" ? it.text : "",
                  links: unique ? links(it.name) : [] });
    });
    var skills = (b.skills || []).map(function (g, i) {
      var gems = (g.gems || []).map(function (m) {
        var bits = [];
        if (m.level !== null && m.level !== undefined) { bits.push("level " + m.level); }
        if (m.quality) { bits.push(m.quality + "% quality"); }
        if (m.enabled === false) { bits.push("off"); }
        return { name: m.name || "Unnamed gem", detail: bits.join(", "),
                 enabled: m.enabled !== false, links: links(m.name).slice(0, 1) };
      });
      var label = g.label || (gems.length ? gems[0].name : "Skill " + (i + 1));
      var main = b.main_skill_index === i + 1;
      return { label: label, main: main, enabled: g.enabled !== false,
               slot: g.slot || "", gems: gems };
    });
    var tree = null;
    if (b.tree) {
      var n = b.tree.node_count || 0;
      tree = { line: (b.tree.title || "Passive tree") + ": " + plural(n, "point", "points") +
                     " allocated" + (b.tree.tree_version ? " (tree " + b.tree.tree_version + ")" : ""),
               url: safeUrl(b.tree.url),
               jewels: Object.keys(b.tree.jewels || {}).length };
    }
    return { loaded: true, title: title, levelLine: "Planned at " + planned + ".", you: you,
             stats: stats, gear: gear, skills: skills, tree: tree,
             notes: typeof b.notes === "string" ? b.notes.trim() : "",
             code: doc.code || "" };
  }

  /* The paste box's answer for a POST /api/build-code result. */
  function pasteResult(status, body) {
    if (status === 200 && body && body.loaded) {
      var b = body.build || {};
      return { ok: true, text: "Loaded: " + (b.class_name || "a build") +
               (b.level ? ", level " + b.level : "") + "." };
    }
    if (status === 422 && body && body.web_data === false) {
      return { ok: false, text: "Build links need web data, which is off. Turn it on in " +
               "AshLight's settings file, or paste the build code instead." };
    }
    if (status === 422) {
      var hosts = body && Array.isArray(body.hosts) && body.hosts.length
        ? body.hosts.filter(function (h) { return typeof h === "string"; }).join(" and ")
        : "pobb.in and pastebin";
      return { ok: false, text: "AshLight can't open that link. It opens links from " + hosts +
               " only. Or paste the build code instead." };
    }
    if (status === 502) {
      return { ok: false, text: "The build link isn't loading. Check your connection and " +
               "paste it again, or paste the build code." };
    }
    if (status === 413) {
      return { ok: false, text: "That is too long for a build code. Copy just the code and " +
               "paste it again." };
    }
    if (status === 400) {
      return { ok: false, text: "AshLight can't read that as a build. Copy the whole code " +
               "from Path of Building and paste it again. Your last build stays loaded." };
    }
    return { ok: false, text: "Not loaded. Try again." };
  }

  var VERDICT_STATE = { upgrade: "done", sidegrade: "idle", downgrade: "idle" };

  /* ev: the snapshot's eval (or null). clock: (ts) -> "14:05". */
  function evalView(ev, clock) {
    if (!ev || !ev.text) { return null; }
    var t = ev.text;
    var verdict = ev.ok ? String(ev.verdict || "") : "note";
    var word = { upgrade: "Upgrade", sidegrade: "Sidegrade", downgrade: "Downgrade" }[verdict] ||
               "Not checked";
    var unweighted = (ev.unweighted || []).filter(function (k) { return typeof k === "string"; });
    return {
      verdict: verdict, state: VERDICT_STATE[verdict] || "pending", word: word,
      sentence: t.sentence || "", item: t.item || "",
      when: typeof ev.at === "number" && clock ? "Checked at " + clock(ev.at) : "",
      comparisons: ev.ok ? (t.comparisons || []) : [],
      unweighted: unweighted.length
        ? "Not counted (no weight yet): " +
          unweighted.map(function (k) { return k.replace(/#/g, "N"); }).join("; ") + ". Add a weight under Stat weights to count them."
        : ""
    };
  }

  /* GET /api/weights -> editable rows, sorted by stat name. */
  function weightRows(doc) {
    var w = (doc && doc.weights) || {};
    return Object.keys(w).sort(function (a, b) {
      var x = a.toLowerCase(), y = b.toLowerCase();
      return x < y ? -1 : (x > y ? 1 : 0);
    }).map(function (k) { return { key: k, label: k.replace(/#/g, "N"), weight: w[k] }; });
  }

  /* A stat as the player types it ("+N% to Fire Resistance") to the core's
     key ("+#% to Fire Resistance"): a standalone N is the number. */
  function toKey(text) {
    return String(text || "").trim().replace(/(^|[^A-Za-z])N(?=[^A-Za-z]|$)/g, "$1#");
  }

  /* The weights document to PUT: rows (key, value text) plus the band. A
     blank or non-number weight drops that row. */
  function weightsDoc(rows, abs, pct) {
    var out = { weights: {}, sidegrade: {} };
    rows.forEach(function (r) {
      var k = toKey(r.key);
      var v = parseFloat(r.value);
      if (k && isFinite(v)) { out.weights[k] = v; }
    });
    var a = parseFloat(abs), p = parseFloat(pct);
    out.sidegrade.abs = isFinite(a) && a >= 0 ? a : 2;
    out.sidegrade.pct = isFinite(p) && p >= 0 ? p : 5;
    return out;
  }

  /* GET /api/gfx -> the advisor panel. */
  function gfxView(doc) {
    if (!doc) { return null; }
    var hw = doc.hardware || {};
    var lines = [];
    var cpu = hw.cpu || {};
    if (cpu.name) {
      var c = [];
      if (cpu.cores) { c.push(plural(cpu.cores, "core", "cores")); }
      if (cpu.threads) { c.push(plural(cpu.threads, "thread", "threads")); }
      lines.push({ label: "Processor", value: cpu.name + (c.length ? " (" + c.join(", ") + ")" : "") });
    }
    if (hw.gpu && hw.gpu.name) {
      lines.push({ label: "Graphics card", value: hw.gpu.name +
        (hw.gpu.vram_gb ? " (" + hw.gpu.vram_gb + " GB)" : " (video memory unknown)") });
    }
    if (hw.ram_gb) { lines.push({ label: "Memory", value: hw.ram_gb + " GB" }); }
    var d = hw.display;
    if (d && d.width) {
      lines.push({ label: "Screen", value: d.width + "x" + d.height +
        (d.refresh_hz ? " at " + d.refresh_hz + " Hz" : "") });
    }
    var adv = doc.advice || {};
    return { ok: !!doc.ok,
             error: doc.ok ? "" : (doc.error || "AshLight could not read this computer's hardware.") +
                    " These are safe middle settings.",
             hardware: lines, tierText: adv.tier_text || "",
             settings: adv.settings || [], warnings: adv.warnings || [] };
  }

  return { buildView: buildView, pasteResult: pasteResult, evalView: evalView,
           weightRows: weightRows, weightsDoc: weightsDoc, toKey: toKey, gfxView: gfxView,
           links: links, num: num };
}));
