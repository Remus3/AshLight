"use strict";
/* TC-SNAP-UI: the game-data credit (decision 0009) in the overlay About
   (app/about.js) and the dashboard footer (web/status.js dataCreditText).
   Shown only when /api/version carries data_credit; the non-affiliation
   line always stays first. RUN-BUILD-STAMP-UI: the version line (below). */
const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const about = require("../about.js");
const web = require("./_web.js");
const dash = web.load("status.js");

const DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way.";
const CREDIT = "Game data (c) Grinding Gear Games. Item, mod and stat data comes from the " +
  "RePoE fork community export (repoe-fork). Trade search stat ids are " +
  "Grinding Gear Games' trade site data, passed on by repoe-fork. Ids it lacks come from " +
  "Path of Building Community (PoE2, MIT license) when its optional calc files " +
  "are installed. Passive tree data comes from " +
  "Grinding Gear Games' public skill tree export. AshLight downloaded all of it to " +
  "this computer when it was built.";
const WITH = { name: "AshLight", version: "0.1.0", disclaimer: DISCLAIMER,
               data_credit: { attribution: CREDIT + " " + DISCLAIMER, credit: CREDIT } };
const WITHOUT = { name: "AshLight", version: "0.1.0", disclaimer: DISCLAIMER, data_credit: null };

test("overlay About: disclaimer alone without snapshot data", () => {
  assert.equal(about.creditOf(WITHOUT), "");
  assert.equal(about.creditOf(null), "");
  assert.equal(about.creditOf({}), "");
  assert.equal(about.creditOf({ data_credit: { credit: 5 } }), "");
  assert.equal(about.aboutText(DISCLAIMER, ""), DISCLAIMER);
});

test("overlay About: disclaimer first, then the credit, exact text", () => {
  assert.equal(about.creditOf(WITH), CREDIT);
  assert.equal(about.aboutText(DISCLAIMER, about.creditOf(WITH)), DISCLAIMER + "\n\n" + CREDIT);
  assert.equal(about.creditOf({ data_credit: { credit: "x".repeat(2000) } }).length,
               about.MAX_CREDIT_CHARS);
});

test("dashboard footer credit: exact text, empty without snapshot data", () => {
  assert.equal(dash.dataCreditText(WITH), CREDIT);
  assert.equal(dash.dataCreditText(WITHOUT), "");
  assert.equal(dash.dataCreditText(null), "");
  assert.equal(dash.dataCreditText({ data_credit: {} }), "");
});

test("getVersion sends the token and parses the document", async () => {
  let seen = null;
  const srv = http.createServer((req, res) => {
    seen = { path: req.url, method: req.method, token: req.headers["x-al-token"] };
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(WITH));
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  try {
    const get = about.makeGetVersion(http, srv.address().port, () => "tok");
    const doc = await get();
    assert.deepEqual(seen, { path: "/api/version", method: "GET", token: "tok" });
    assert.equal(about.creditOf(doc), CREDIT);
  } finally {
    srv.close();
  }
});

test("getVersion rejects a refused token (no credit shown)", async () => {
  const srv = http.createServer((req, res) => { res.writeHead(401); res.end("no\n"); });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  try {
    const get = about.makeGetVersion(http, srv.address().port, () => "bad");
    await assert.rejects(get(), /HTTP 401/);
  } finally {
    srv.close();
  }
});

test("firstCredit: the credit, or empty on error or timeout", async () => {
  assert.equal(await about.firstCredit(() => Promise.resolve(WITH), 1000), CREDIT);
  assert.equal(await about.firstCredit(() => Promise.resolve(WITHOUT), 1000), "");
  assert.equal(await about.firstCredit(() => Promise.reject(new Error("down")), 1000), "");
  assert.equal(await about.firstCredit(() => new Promise(() => {}), 10), "");
  assert.equal(about.START_WAIT_MS, 1500);
});

test("overlay page keeps the disclaimer and a hidden credit slot", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "overlay", "index.html"), "utf8");
  assert.ok(html.includes('<p class="about">' + DISCLAIMER + "</p>"));
  assert.ok(html.includes('<p id="aboutData" class="about" hidden></p>'));
});

/* RUN-BUILD-STAMP-UI (F-027, decision 0082 part 2): one version line from
   the core's build string (server/al/buildinfo.py compose) in the overlay
   About, the tray tooltip, the dashboard footer and the Settings About fold. */
const TrayMenu = require("../client/tray_menu.js");
const ROOT = path.join(__dirname, "..", "..");
const SHA = "0123456789ab";
const LINES = [
  [{ build: "0.1.0+" + SHA, version: "0.1.0" }, "Version 0.1.0, build " + SHA],
  [{ build: "0.1.0+" + SHA + ".dev" }, "Version 0.1.0, build " + SHA + ", dev"],
  [{ build: "0.1.0+dev" }, "Version 0.1.0, dev"],
  [{ build: "0.1.0" }, "Version 0.1.0"],
  [{ version: "0.2.3" }, "Version 0.2.3"],
  [{ build: "1.0.0-rc.1+" + SHA }, "Version 1.0.0-rc.1, build " + SHA],
  [null, ""], [{}, ""], [{ build: 5 }, ""], [{ build: "" }, ""],
  [{ build: "0.1+" + SHA }, ""], [{ build: "0.1.0+XYZ" }, ""],
  [{ build: "0.1.0+" + SHA.toUpperCase() }, ""], [{ build: "0.1.0+" + SHA + "ff" }, ""],
  [{ build: "0.1.0+dev." + SHA }, ""], [{ build: "0.1.0+" + SHA + ".dev.dev" }, ""],
  [{ build: "0.1.0+" + SHA + "." + SHA }, ""], [{ build: "0.1.0+" }, ""],
  [{ build: "<b>0.1.0</b>" }, ""], [{ build: "0.1.0+" + "a".repeat(200) }, ""]
];

test("version line: 'Version <x.y.z>, build <12 hex>', ', dev' while hot reload is on", () => {
  for (const [doc, want] of LINES) {
    assert.equal(about.versionLine(doc), want, JSON.stringify(doc));
  }
});

test("overlay About text carries the build string after the disclaimer", () => {
  const v = about.versionLine(LINES[0][0]);
  assert.equal(about.aboutText(DISCLAIMER, "", v), DISCLAIMER + "\n" + v);
  assert.equal(about.aboutText(DISCLAIMER, CREDIT, v), DISCLAIMER + "\n" + v + "\n\n" + CREDIT);
  assert.equal(about.aboutText(DISCLAIMER, CREDIT, ""), DISCLAIMER + "\n\n" + CREDIT);
  assert.ok(about.aboutText(DISCLAIMER, CREDIT, v).startsWith(DISCLAIMER));
});

test("firstDoc: the document, or null on error or timeout", async () => {
  assert.deepEqual(await about.firstDoc(() => Promise.resolve(WITH), 1000), WITH);
  assert.equal(await about.firstDoc(() => Promise.reject(new Error("down")), 1000), null);
  assert.equal(await about.firstDoc(() => new Promise(() => {}), 10), null);
});

test("app/package.json version equals server/al/__init__.py VERSION", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "app", "package.json"), "utf8"));
  const init = fs.readFileSync(path.join(ROOT, "server", "al", "__init__.py"), "utf8");
  const m = /^VERSION = "([^"]+)"$/m.exec(init);
  assert.ok(m, "VERSION line in server/al/__init__.py");
  assert.equal(pkg.version, m[1]);
});

test("tray tooltip carries the build string, within the Windows limit", () => {
  const v = about.versionLine({ build: "0.1.0+" + SHA + ".dev" });
  assert.equal(TrayMenu.tooltipFor(v), TrayMenu.TOOLTIP + "\n" + v);
  assert.ok(TrayMenu.tooltipFor(v).length <= TrayMenu.TOOLTIP_MAX);
  assert.equal(TrayMenu.TOOLTIP_MAX, 127);
  assert.equal(TrayMenu.tooltipFor(""), TrayMenu.TOOLTIP);
  assert.equal(TrayMenu.tooltipFor(null), TrayMenu.TOOLTIP);
  assert.equal(TrayMenu.tooltipFor("x".repeat(300)).length, TrayMenu.TOOLTIP_MAX);
});

test("main.js: one /api/version read feeds the About text and the tray tooltip", () => {
  const main = fs.readFileSync(path.join(ROOT, "app", "main.js"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
  assert.match(main, /versionText = About\.versionLine\(doc\) \|\| versionText;/);
  assert.match(main, /credits: About\.aboutText\(DISCLAIMER, dataCredit, versionText,\s*DOWNLOAD_LINE\)/);
  assert.match(main, /t\.setToolTip\(TrayMenu\.tooltipFor\(versionText\)\);/);
  // at start (before the page loads) and on every core restart
  assert.match(main, /About\.firstDoc\(getVersion, About\.START_WAIT_MS\)\.then\(\(doc\) => \{\s*setAbout\(doc\);/);
  assert.match(main, /getVersion\(\)\.then\(\(doc\) => setAbout\(doc\),/);
  // the tray shows it as soon as the client builds its tray
  assert.match(main, /client\.open\(\);\s*setTrayTooltip\(\);/);
});

/* The dashboard's own copy of the words: web/app.js versionText, run alone. */
function webVersionText() {
  const src = web.source("app.js");
  const m = /\/\* BUILD-STAMP:begin[\s\S]*?\*\/([\s\S]*?)\/\* BUILD-STAMP:end \*\//.exec(src);
  assert.ok(m, "BUILD-STAMP markers in web/app.js");
  const box = {};
  vm.runInNewContext(m[1] + "\nout.f = versionText;", { out: box });
  return box.f;
}

test("dashboard versionText says exactly what the About text says", () => {
  const f = webVersionText();
  for (const [doc, want] of LINES) {
    assert.equal(f(doc), want, JSON.stringify(doc));
  }
});

test("dashboard footer: one muted build line, hidden until the core answers", () => {
  const html = web.source("index.html");
  const foot = /<footer[^>]*>([\s\S]*?)<\/footer>/.exec(html)[1];
  assert.ok(foot.includes('<p id="build-line" class="muted" hidden></p>'));
  assert.ok(foot.indexOf(DISCLAIMER) < foot.indexOf('id="build-line"'),
            "the disclaimer stays first");
  assert.equal((html.match(/id="build-line"/g) || []).length, 1);
});

test("Settings > About and data carries the same string as the footer", () => {
  // PLAY-TD-21B-SETTINGS-ABOUT: the About fold became the rail's About and
  // data section, open, with the version as its last line
  const html = web.source("index.html");
  const settings = html.slice(html.indexOf('id="panel-settings"'), html.indexOf("</main>"));
  const at = settings.indexOf('<section id="set-about"');
  assert.ok(at > 0, "About and data in the Settings tab");
  const about = settings.slice(at, settings.indexOf("</section>", at));
  assert.match(about, /<h3 id="about-title">About and data<\/h3>/);
  assert.ok(!settings.includes('id="about-fold"'), "no About fold left");
  assert.match(about, /<p id="about-version" class="muted">/);
  const js = web.source("app.js");
  assert.match(js, /var ver = versionText\(doc\);\s*if \(ver\) \{\s*\$\("build-line"\)\.textContent = ver;\s*\$\("build-line"\)\.hidden = false;\s*\$\("about-version"\)\.textContent = ver;/);
});

/* PUB-GUIDE-DOWNLOAD-PLACE (F-126): the one download place, the releases
   page of config/public_repo.json, closes the overlay About text. */
const PLACE = "AshLight releases appear at github.com/owner-1/Repo.name/releases.";

test("download line: from a GitHub-shaped owner/name only, else no line", () => {
  assert.equal(about.downloadLine({ repo: "owner-1/Repo.name" }), PLACE);
  for (const bad of [null, {}, { repo: 5 }, { repo: "" }, { repo: "owner" },
                     { repo: "a/b/c" }, { repo: "-x/y" }, { repo: "x/.." }, { repo: "x/." },
                     { repo: "x y/z" }, { repo: "x/<b>" }, { repo: "x/y\nz" }]) {
    assert.equal(about.downloadLine(bad), "", JSON.stringify(bad));
  }
});

test("aboutText with a download line: disclaimer first, the line last", () => {
  const v = "Version 0.1.0";
  assert.equal(about.aboutText(DISCLAIMER, CREDIT, v, PLACE),
               DISCLAIMER + "\n" + v + "\n\n" + CREDIT + "\n\n" + PLACE);
  assert.equal(about.aboutText(DISCLAIMER, "", "", PLACE), DISCLAIMER + "\n\n" + PLACE);
  assert.equal(about.aboutText(DISCLAIMER, CREDIT, v, ""), DISCLAIMER + "\n" + v + "\n\n" + CREDIT);
  assert.ok(about.aboutText(DISCLAIMER, CREDIT, v, PLACE).startsWith(DISCLAIMER));
});

test("main.js reads config/public_repo.json once at start for the download line", () => {
  const main = fs.readFileSync(path.join(ROOT, "app", "main.js"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
  assert.match(main, /^const DOWNLOAD_LINE = About\.downloadLine\(readJson\(path\.join\(REPO, "config", "public_repo\.json"\)\)\);$/m);
  assert.equal((main.match(/public_repo\.json/g) || []).length, 1);
  assert.equal((main.match(/About\.aboutText\(/g) || []).length, 1);
});

test("the tracked address gives the same line README and the guide carry", () => {
  const doc = JSON.parse(fs.readFileSync(path.join(ROOT, "config", "public_repo.json"), "utf8"));
  const line = about.downloadLine(doc);
  assert.ok(line.endsWith(about.DOWNLOAD_SUFFIX));
  for (const rel of ["README.md", "docs/guide/download.md", "docs/guide/faq.md"]) {
    const text = fs.readFileSync(path.join(ROOT, rel), "utf8").split(/\s+/).join(" ");
    assert.ok(text.includes(line), rel);
  }
});
