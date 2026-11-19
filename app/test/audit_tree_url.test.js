"use strict";
/* AUDIT-TREE-URL (audit finding S8): a pasted build's tree URL becomes the
   "Open the tree" link only for known passive-tree hosts; any other host,
   a port, user info or a non-https scheme gives no link. */
const test = require("node:test");
const assert = require("node:assert/strict");
const web = require("./_web.js");
const v = web.load("tc.js");

function treeUrl(url) {
  const doc = { loaded: true, code: "", build: { class_name: "Monk", level: 1, stats: {},
    gear: {}, skills: [], tree: { node_count: 1, url: url } } };
  return v.buildView(doc, null).tree.url;
}

test("known tree hosts keep their link", () => {
  for (const u of ["https://www.pathofexile.com/passive-skill-tree/0_3/AAAA",
                   "https://pathofexile.com/fullscreen-passive-skill-tree/x",
                   "https://www.pathofexile2.com/passive-skill-tree/AAAA",
                   "https://poe2db.tw/us/passive-skill-tree",
                   "https://maxroll.gg/poe2/planner/abc"]) {
    assert.equal(treeUrl(u), u, u);
    assert.equal(v.safeTreeUrl(u), u, u);
  }
});

test("off-list hosts and tricks give no link", () => {
  for (const u of ["https://example.org/tree/endgame",
                   "https://evil.example/www.pathofexile.com/",
                   "https://pathofexile.com.evil.example/tree",
                   "https://notpathofexile.com/tree",
                   "https://user" + "@" + "www.pathofexile.com/tree",
                   "https://www.pathofexile.com:8443/tree",
                   "http://www.pathofexile.com/tree",
                   "javascript:alert(1)",
                   "https://www.pathofexile.com/tree with space",
                   "", null, 42]) {
    assert.equal(treeUrl(u), "", String(u));
  }
});
