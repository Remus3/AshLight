/* BUILD-LIVE: exact output of the build-alert slot helpers (web/buildlive.js,
   decision 0045). The core sends the words; this file only shows and hides
   them. Synthetic names only. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const bl = require("../../web/buildlive.js");

function fakeDoc() {
  const byId = new Map();
  function make(tag) {
    const e = {
      tagName: tag, children: [], hidden: false, textContent: "", className: "",
      _id: "",
      get id() { return this._id; },
      set id(v) { this._id = v; byId.set(v, this); },
      get firstChild() { return this.children[0] || null; },
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children.splice(this.children.indexOf(c), 1); return c; },
    };
    return e;
  }
  const doc = {
    createElement: make,
    getElementById: (id) => byId.get(id) || null,
  };
  const box = make("section");
  box.id = "build-alert";
  box.hidden = true;
  return { doc, box };
}

const ALERT = { kind: "level", text: "Build is from level 42; you are level 51. Paste a fresh PoB code to keep item checks right." };
const UPS = { text: "1 item you checked is an upgrade now.", items: [
  { head: "New upgrade for Ring 1: Storm Loop", line: "Replaces Weak Loop, +12 points.",
    fit: "Fits your Ranger build.", "new": true }] };

test("buildlive: model hides when the build fits and nothing is an upgrade", () => {
  assert.deepEqual(bl.model(null), { show: false, alert: null, upgrades: null });
  assert.deepEqual(bl.model({ build_alert: null, upgrades: { text: "x", items: [] } }),
    { show: false, alert: null, upgrades: null });
});

test("buildlive: model carries the core's words as they are", () => {
  const m = bl.model({ build_alert: ALERT, upgrades: UPS });
  assert.equal(m.show, true);
  assert.deepEqual(m.alert, { kind: "level", text: ALERT.text });
  assert.deepEqual(m.upgrades, { text: UPS.text, items: [{ head: UPS.items[0].head,
    line: "Replaces Weak Loop, +12 points.", fit: "Fits your Ranger build.", isNew: true }] });
});

test("buildlive: model caps the list", () => {
  const items = [];
  for (let i = 0; i < 30; i++) { items.push({ head: "Upgrade " + i }); }
  assert.equal(bl.model({ upgrades: { text: "", items } }).upgrades.items.length, bl.MAX);
});

test("buildlive: paint fills and hides the slot", () => {
  const { doc, box } = fakeDoc();
  bl.paint(doc, { build_alert: ALERT, upgrades: UPS });
  assert.equal(box.hidden, false);
  assert.equal(doc.getElementById("build-alert-title").textContent, bl.TITLE);
  assert.equal(doc.getElementById("build-alert-text").textContent, ALERT.text);
  const list = doc.getElementById("build-upgrades-list");
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].children[0].textContent, UPS.items[0].head);
  // only the alert: the list part hides, nothing is added twice
  bl.paint(doc, { build_alert: ALERT, upgrades: null });
  assert.equal(doc.getElementById("build-upgrades").hidden, true);
  assert.equal(list.children.length, 0);
  assert.equal(box.children.length, 1); // one body, built once
  assert.equal(box.children[0].children.length, 3); // heading, alert, list
  bl.paint(doc, {});
  assert.equal(box.hidden, true);
});

test("buildlive: with the Play tab helper the body goes in through ALTabs.fill", () => {
  const { doc, box } = fakeDoc();
  const filled = [];
  const tabs = { fill: (d, id, node) => { filled.push(id); d.getElementById(id).appendChild(node); } };
  bl.paint(doc, { build_alert: ALERT }, tabs);
  bl.paint(doc, { build_alert: ALERT }, tabs);
  assert.deepEqual(filled, ["build-alert"]); // once
  assert.equal(box.children.length, 1);
  assert.equal(doc.getElementById("build-alert-text").textContent, ALERT.text);
});

test("buildlive: paint without the slot does nothing", () => {
  assert.doesNotThrow(() => bl.paint({ getElementById: () => null }, { build_alert: ALERT }));
});

test("buildlive: a later, different alert is news for Play (merge fix)", () => {
  const { doc } = fakeDoc();
  const said = [];
  const tabs = { fill: (d, id, node) => { d.getElementById(id).appendChild(node); },
    notify: (d, what) => { said.push(what); } };
  bl.paint(doc, { build_alert: ALERT }, tabs);
  bl.paint(doc, { build_alert: ALERT }, tabs);
  assert.deepEqual(said, []); // the first fill is ALTabs.fill's own news
  bl.paint(doc, { build_alert: Object.assign({}, ALERT, { text: "Another alert." }) }, tabs);
  assert.deepEqual(said, ["build alert"]);
});
