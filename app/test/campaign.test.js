/* UTIL-CAMPAIGN-CHECKS: the campaign hint word in the overlay status slot
   (app/shared/render_gate.js), plus UTIL-WAYSTONE-REWARD's overlay line
   (the core picks it). The core sends the words; these only place them.
   PLAY-LEGACY-OUT-1: web/history.js no longer paints the hint rows (their
   legacy group is retired by region C). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const gate = require("../shared/render_gate.js");
const web = require("./_web.js");
const h = web.load("history.js");
const ch = web.load("chars.js");

const snap = {
  zone: "Ogham Manor", in_hideout: false, zone_entered_at: 1000,
  level: 15, deaths: 0, version: 3
};
const camp = { word: "Cold res 32%", hints: [
  { id: "boss", word: "Cold res 32%", text: "This zone's boss deals mostly cold damage." },
  { id: "boots", word: "Boots: no speed", text: "Your build's boots have no movement speed." }] };

test("campaign word fills the status slot last", () => {
  const m = gate.hudModel({ ...snap, campaign: camp }, 1000, "live");
  assert.equal(m.campaign, "Cold res 32%");
  assert.equal(gate.statusText(m), "Cold res 32%");
  const both = gate.hudModel({ ...snap, campaign: camp, underlevel: { word: "4 lv under" } },
    1000, "live");
  assert.equal(gate.statusText(both), "4 lv under");
  const afk = gate.hudModel({ ...snap, campaign: camp, afk: true }, 1000, "live");
  assert.equal(gate.statusText(afk), "AFK");
  assert.equal(gate.hudModel({ ...snap, campaign: null }, 1000, "live").campaign, "");
  assert.equal(gate.hudModel({ ...snap, campaign: { word: "x".repeat(16) } }, 1000, "live")
    .campaign, "");
  assert.ok(gate.FIELDS.includes("campaign"));
});

test("the history painter no longer writes the campaign hint rows", () => {
  assert.equal(h.campaignHints, undefined);
  const ids = [];
  h.paint({ getElementById: (id) => { ids.push(id); return null; } }, { campaign: camp });
  assert.ok(!ids.includes("campaign-hints"), ids.join(","));
});

test("another character's view drops the campaign hints", () => {
  const s = { character: "Ash", campaign: camp, characters: [
    { name: "Ash", current: true, level: 15 }, { name: "Bo", current: false, level: 3 }] };
  assert.equal(ch.view(s, "Bo").campaign, null);
  assert.equal(ch.view(s, "Ash").campaign, camp);
});
