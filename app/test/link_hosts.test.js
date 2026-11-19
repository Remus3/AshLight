"use strict";
/* OVL-LINKS-DOWNLOADS (decision 0041 amendment 2026-11-19): config/link_hosts.json
   is the one list of hosts a companion-window link may open. Every host the
   dashboard can emit must be on it, and nothing else: web/tc.js link builders
   and TREE_HOSTS (the tree URL), the trade search URL of server/al/trade.py,
   and any https host literal (plain or regex-escaped) in a web/ source. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const web = require("./_web.js");
const Link = require("../client/link.js");

const ROOT = path.join(__dirname, "..", "..");
const HOSTS_FILE = path.join(ROOT, "config", "link_hosts.json");
const TRADE_PY = path.join(ROOT, "server", "al", "trade.py");
const tc = web.load("tc.js");

function listed() {
  return JSON.parse(fs.readFileSync(HOSTS_FILE, "utf8")).hosts;
}

function hostOf(url) {
  return new URL(url).hostname;
}

function tradeHost() {
  const m = /^TRADE_SITE = "(https:\/\/[^"]+)"$/m.exec(fs.readFileSync(TRADE_PY, "utf8"));
  assert.ok(m, "TRADE_SITE in server/al/trade.py");
  return hostOf(m[1]);
}

/* https host literals in the web/ sources: "https://host" and the
   regex-escaped "https:\/\/host\.tld" form. */
function webLiteralHosts() {
  const out = new Set();
  const files = [];
  for (const sub of ["", "panels"]) {
    const dir = sub ? path.join(web.dir, sub) : web.dir;
    if (!fs.existsSync(dir)) { continue; }
    for (const n of fs.readdirSync(dir)) {
      if (/\.(js|html)$/.test(n)) { files.push(path.join(dir, n)); }
    }
  }
  for (const f of files) {
    const text = fs.readFileSync(f, "utf8");
    for (const m of text.matchAll(/https:\/\/([a-z0-9-]+(?:\.[a-z0-9-]+)+)/gi)) {
      out.add(m[1].toLowerCase());
    }
    for (const m of text.matchAll(/https:\\\/\\\/((?:[a-z0-9-]+\\\.)+[a-z0-9-]+)/gi)) {
      out.add(m[1].replace(/\\/g, "").toLowerCase());
    }
  }
  return out;
}

function emitted() {
  const hosts = new Set();
  for (const l of tc.links("Some Item")) { hosts.add(hostOf(l.href)); }
  for (const h of tc.LINK_HOSTS) { hosts.add(h); }
  for (const h of tc.TREE_HOSTS) { hosts.add(h); }
  hosts.add(tradeHost());
  for (const h of webLiteralHosts()) { hosts.add(h); }
  return hosts;
}

test("the host file is a plain sorted list of lower-case names", () => {
  const hosts = listed();
  assert.ok(Array.isArray(hosts) && hosts.length > 0);
  for (const h of hosts) { assert.match(h, /^[a-z0-9-]+(\.[a-z0-9-]+)+$/, h); }
  assert.deepEqual(hosts, hosts.slice().sort());
  assert.equal(new Set(hosts).size, hosts.length);
  assert.deepEqual(Link.LINK_HOSTS.slice(), hosts); // the client reads this file
});

test("every host the dashboard can emit is listed", () => {
  const hosts = new Set(listed());
  for (const h of emitted()) { assert.ok(hosts.has(h), "not in config/link_hosts.json: " + h); }
  for (const l of tc.links("Some Item")) { assert.ok(tc.LINK_HOSTS.includes(hostOf(l.href))); }
});

test("the list holds the emitted hosts and nothing more", () => {
  assert.deepEqual(listed().slice().sort(), Array.from(emitted()).sort());
});

test("every emitted link passes the client's rule; others do not", () => {
  for (const h of listed()) { assert.equal(Link.isExternalUrl("https://" + h + "/x"), true, h); }
  assert.equal(Link.isExternalUrl("https://www.pathofexile2.com/passive-skill-tree/A"), true);
  for (const l of tc.links("Some Item")) { assert.equal(Link.isExternalUrl(l.href), true); }
  for (const bad of ["https://poe.ninja/", "https://example.org/", "http://poe2db.tw/us/x",
                     "https://poe2db.tw.evil.example/", "https://notpathofexile.com/"]) {
    assert.equal(Link.isExternalUrl(bad), false, bad);
  }
});

test("a missing or broken host file refuses every link", () => {
  assert.deepEqual(Link.readHosts(path.join(ROOT, "config", "no-such-file.json")), []);
  assert.equal(Link.isExternalUrl("https://poe2db.tw/us/x", []), false);
});
