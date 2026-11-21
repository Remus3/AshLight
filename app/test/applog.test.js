"use strict";
/* RUN-OBS-LOGS-SHELL (F-090; research 0051 R7): overlay.log (app/applog.js)
   and run.log (scripts/run.ps1, scripts/stop.ps1) are bounded, share the
   one line format of server/al/logs.py and open each start with the build
   banner. */
const test = require("node:test");
const assert = require("node:assert/strict");
const EventEmitter = require("node:events");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const A = require("../applog.js");

const MB = 1024 * 1024;
const ROOT = path.resolve(__dirname, "..", "..");
const STAMP = "\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d\\.\\d{3}Z";
const LINE = new RegExp("^" + STAMP + " (DEBUG|INFO|WARNING|ERROR|CRITICAL) [\\w.-]+\\[\\d+\\] ");
const SHA = "0123456789abcdef0123456789abcdef01234567";

const made = [];
function tmpDir() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "al-applog-"));
  made.push(d);
  return d;
}
test.after(() => { for (const d of made) { fs.rmSync(d, { recursive: true, force: true }); } });

function code(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

function waitClosed(log) {
  return new Promise((resolve) => log.close(resolve));
}

test("rotates over 1 MB, keeps one, banner first", async () => {
  const dir = tmpDir();
  const file = path.join(dir, A.FILE_NAME);
  fs.writeFileSync(file + ".1", "oldest\n");
  const old = Buffer.alloc(MB + 1, 0x61);
  fs.writeFileSync(file, old);
  const log = A.createLog({ electron: "45.3.3", pid: 4242 });
  assert.equal(log.open(dir, "0.1.0+0123456789ab"), true);
  log("overlay started; port 8960");
  log.warn("displays.json not written");
  await waitClosed(log);
  assert.ok(fs.readFileSync(file + ".1").equals(old), "one old file kept, the older one replaced");
  const lines = fs.readFileSync(file, "utf8").split("\n").filter(Boolean);
  assert.match(lines[0], LINE);
  assert.ok(lines[0].endsWith(" INFO client[4242] AshLight 0.1.0+0123456789ab client start " +
    "(pid 4242, electron 45.3.3)"), lines[0]);
  assert.ok(lines[1].endsWith(" INFO client[4242] overlay started; port 8960"), lines[1]);
  assert.ok(lines[2].endsWith(" WARNING client[4242] displays.json not written"), lines[2]);
  // a small file is left alone at the next start: it appends
  const again = A.createLog({ electron: "45.3.3", pid: 4343 });
  again.open(dir, "0.1.0+0123456789ab");
  await waitClosed(again);
  assert.ok(fs.readFileSync(file + ".1").equals(old));
  const all = fs.readFileSync(file, "utf8").split("\n").filter(Boolean);
  assert.equal(all.filter((l) => l.includes(" client start (pid ")).length, 2);
  // the banner never reads as the diag start marker ("overlay started")
  assert.ok(!all[0].includes("overlay started"));
});

test("exactly 1 MB stays; a missing file or a failed move keeps appending", () => {
  const dir = tmpDir();
  const file = path.join(dir, "x.log");
  fs.writeFileSync(file, Buffer.alloc(MB, 0x62));
  assert.equal(A.rotateAtStart(file), false);
  assert.equal(A.rotateAtStart(path.join(dir, "missing.log")), false);
  const held = { statSync: () => ({ size: MB + 1 }),
                 renameSync: () => { throw new Error("EBUSY: held open"); } };
  assert.equal(A.rotateAtStart(file, held), false);
  assert.equal(A.START_LIMIT, MB);
  assert.equal(A.backupPath("a.log"), "a.log.1");
});

test("stream error is swallowed, nothing thrown", () => {
  const errs = [];
  const stderr = { write: (t) => errs.push(t) };
  let stream = null;
  const fake = {
    mkdirSync() {},
    statSync() { throw new Error("ENOENT"); },
    renameSync() {},
    readFileSync() { throw new Error("ENOENT"); },
    createWriteStream() {
      stream = new EventEmitter();
      stream.write = () => { throw new Error("EPIPE"); };
      return stream;
    }
  };
  const log = A.createLog({ fs: fake, stderr: stderr, pid: 7, electron: "45.3.3" });
  // before open: stderr
  assert.doesNotThrow(() => log("early line"));
  assert.equal(errs.length, 1);
  assert.match(errs[0], /INFO client\[7\] early line\n$/);
  // a throwing write: the banner falls back to stderr, nothing thrown
  assert.doesNotThrow(() => log.open("logs", "B"));
  assert.ok(errs[1].includes("AshLight B client start (pid 7, electron 45.3.3)"));
  assert.equal(log.isOpen(), false);
  // an async stream error event is swallowed as well
  const log2 = A.createLog({ fs: Object.assign({}, fake, {
    createWriteStream() { stream = new EventEmitter(); stream.write = () => true; return stream; }
  }), stderr: stderr, pid: 7 });
  assert.equal(log2.open("logs", "B"), true);
  assert.doesNotThrow(() => stream.emit("error", new Error("disk gone")));
  assert.equal(log2.isOpen(), false);
  assert.doesNotThrow(() => log2.error("after the error"));
  assert.match(errs[errs.length - 1], /ERROR client\[7\] after the error\n$/);
  // a folder that cannot be made: false, stderr, nothing thrown
  const log3 = A.createLog({ fs: Object.assign({}, fake, { mkdirSync() { throw new Error("EACCES"); } }),
    stderr: stderr, pid: 7 });
  assert.equal(log3.open("logs", "B"), false);
  assert.equal(log3.open("", "B"), false);
  // nowhere left: even a throwing stderr is swallowed
  const log4 = A.createLog({ fs: fake, stderr: { write() { throw new Error("closed"); } } });
  assert.doesNotThrow(() => log4("x"));
});

test("one line format: UTC ISO stamp, level word, name and pid; no absolute path", () => {
  assert.equal(A.stamp(0), "1970-01-01T00:00:00.000Z");
  assert.equal(A.formatLine("client", "warning", "x", 250, 9), "1970-01-01T00:00:00.250Z WARNING client[9] x");
  assert.equal(A.formatLine("client", "nonsense", "x", 0, 9), "1970-01-01T00:00:00.000Z INFO client[9] x");
  assert.equal(A.formatLine("client", "INFO", "a\r\nb", 0, 9), "1970-01-01T00:00:00.000Z INFO client[9] a b");
  // built at run time so the leak sweep sees no machine path
  const drive = "C" + ":" + "\\" + ["Users", "someone", "x.json"].join("\\");
  const unc = "\\\\" + ["host", "share", "f.txt"].join("\\");
  const line = A.formatLine("client", "INFO", "not written: " + drive + "; " + unc + ".", 0, 1);
  assert.ok(!line.includes("someone") && !line.includes("host"), line);
  assert.ok(line.endsWith("not written: <path>; <path>."), line);
  // a URL and a port are not paths
  assert.ok(A.scrub("core at http://127.0.0.1:8960/api/health").endsWith("127.0.0.1:8960/api/health"));
});

function gitTree(root, opts) {
  const o = opts || {};
  const git = path.join(root, ".git");
  fs.mkdirSync(path.join(git, "refs", "heads"), { recursive: true });
  fs.writeFileSync(path.join(git, "HEAD"), "ref: refs/heads/main\n");
  if (o.packed) {
    fs.writeFileSync(path.join(git, "packed-refs"), "# pack-refs\n" + SHA + " refs/heads/main\n");
  } else {
    fs.writeFileSync(path.join(git, "refs", "heads", "main"), SHA + "\n");
  }
  return git;
}

test("build id: version plus 12 hex from the .git files, else the BUILD file", () => {
  const a = tmpDir();
  gitTree(a);
  assert.equal(A.buildId(a, "0.1.0"), "0.1.0+0123456789ab");
  const b = tmpDir();
  gitTree(b, { packed: true });
  assert.equal(A.buildId(b, "0.1.0"), "0.1.0+0123456789ab");
  // a linked worktree: its .git file names the gitdir, commondir the shared one
  const c = tmpDir();
  const common = gitTree(path.join(c, "main"));
  const wtGit = path.join(common, "worktrees", "w1");
  fs.mkdirSync(wtGit, { recursive: true });
  fs.writeFileSync(path.join(wtGit, "HEAD"), "ref: refs/heads/main\n");
  fs.writeFileSync(path.join(wtGit, "commondir"), "../..\n");
  fs.mkdirSync(path.join(c, "wt"));
  fs.writeFileSync(path.join(c, "wt", ".git"), "gitdir: " + wtGit + "\n");
  assert.equal(A.buildId(path.join(c, "wt"), "0.1.0"), "0.1.0+0123456789ab");
  // a detached HEAD
  const d = tmpDir();
  fs.mkdirSync(path.join(d, ".git"));
  fs.writeFileSync(path.join(d, ".git", "HEAD"), SHA + "\n");
  assert.equal(A.buildId(d, "0.1.0"), "0.1.0+0123456789ab");
  // an installed payload: the BUILD file, only for this version
  const e = tmpDir();
  fs.writeFileSync(path.join(e, "BUILD"), JSON.stringify({ version: "0.1.0", commit: "abcdefabcdef12" }));
  assert.equal(A.buildId(e, "0.1.0"), "0.1.0+abcdefabcdef");
  assert.equal(A.buildId(e, "0.2.0"), "0.2.0");
  // a HEAD pointing outside refs/ is never followed; nothing known: the version
  const f = tmpDir();
  fs.mkdirSync(path.join(f, ".git"));
  fs.writeFileSync(path.join(f, ".git", "HEAD"), "ref: ../../outside\n");
  assert.equal(A.buildId(f, "0.1.0"), "0.1.0");
  assert.equal(A.buildId(tmpDir(), "0.1.0"), "0.1.0");
  // the default version is app/package.json's
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  assert.equal(A.appVersion(), pkg.version);
  assert.ok(A.buildId(tmpDir()) === pkg.version);
});

test("main.js keeps one require of applog.js and no log file code of its own", () => {
  const main = code(fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8"));
  assert.equal((main.match(/require\("\.\/applog\.js"\)/g) || []).length, 1);
  assert.match(main, /const log = AppLog\.createLog\(\{ electron: process\.versions\.electron \}\);/);
  assert.ok(!/function log\(/.test(main));
  assert.ok(!/createWriteStream/.test(main));
  assert.ok(!/overlay\.log/.test(main));
  assert.match(main, /log\.open\(path\.join\(root, "Logs"\)\)/);
  // the module reads AshLight's own files only: no spawn, no network
  const mod = code(fs.readFileSync(path.join(__dirname, "..", "applog.js"), "utf8"));
  for (const word of ["child_process", "require(\"http", "require(\"https", "require(\"net",
                      "require(\"electron\")", "exec("]) {
    assert.ok(!mod.includes(word), word);
  }
});

/* The run.log side (run.ps1 and stop.ps1), a static read of the scripts:
   the rotation, the stamp and the banner are in each script's own
   functions; a live run is covered by the PowerShell 5.1 smoke in the
   package record. */
test("run.ps1 rotates run.log (static read of the script)", () => {
  const run = fs.readFileSync(path.join(ROOT, "scripts", "run.ps1"), "ascii");
  assert.ok(/^[\x09\x0a\x20-\x7e]*$/.test(run) && !run.includes("\r"), "ASCII and LF");
  const startFn = run.slice(run.indexOf("function Start-AlRunLog("), run.indexOf("Start-AlRunLog $log 'run' (Get-AlBuildId)"));
  assert.ok(startFn.length > 0, "Start-AlRunLog is defined before its one call");
  assert.match(startFn, /\$old = \$Path \+ '\.1'/);
  assert.match(startFn, /\.Length -gt 1048576/);
  assert.match(startFn, /\[System\.IO\.File\]::Replace\(\$Path, \$old, \[NullString\]::Value\)/);
  assert.match(startFn, /\[System\.IO\.File\]::Move\(\$Path, \$old\)/);
  assert.match(startFn, /catch \{\s*# held open elsewhere: keep appending/);
  assert.match(startFn, /"AshLight \$Build \$Name start \(pid \$PID, powershell "/);
  // the call sits before the first line any branch writes (the autostart block)
  const call = run.indexOf("Start-AlRunLog $log 'run' (Get-AlBuildId)");
  assert.ok(call > run.indexOf("$log = Join-Path $paths.logs 'run.log'"));
  assert.ok(call < run.indexOf("if ($Autostart) {"));
  // the build id from server.al.buildinfo, checked before use
  assert.match(run, /from server\.al import buildinfo; print\(buildinfo\.build_id\(\)\)/);
  assert.match(run, /if \(\$b -match '\^\[0-9A-Za-z\.\+-\]\{1,64\}\$'\) \{ return \$b \}/);
  // one stamp format: UTC ISO with milliseconds and Z, a level word, run[<pid>]
  const fmt = "[DateTime]::UtcNow.ToString(\"yyyy-MM-dd'T'HH:mm:ss.fff'Z'\"";
  assert.equal(run.split(fmt).length - 1, 2, "Add-AlRunLine and Write-AlLog");
  assert.ok(run.includes("$line = $stamp + ' ' + $Level + ' run[' + $PID + '] ' + $Message"));
  assert.ok(!run.includes("Get-Date -Format 's'"), "no local-time stamp left");
  assert.ok(!/Add-Content -Path \$log -Value \(\(Get-Date/.test(run));
  // stop.ps1: the same scheme under its own name
  const stop = fs.readFileSync(path.join(ROOT, "scripts", "stop.ps1"), "ascii");
  assert.ok(/^[\x09\x0a\x20-\x7e]*$/.test(stop) && !stop.includes("\r"), "ASCII and LF");
  assert.ok(stop.includes("$line = $stamp + ' ' + $Level + ' stop[' + $PID + '] ' + $Message"));
  assert.match(stop, /\.Length -gt 1048576/);
  assert.match(stop, /\[System\.IO\.File\]::Replace\(\$log, \$old, \[NullString\]::Value\)/);
  assert.ok(stop.includes("' stop start (pid ' + $PID + ', powershell '"));
  assert.ok(stop.indexOf("Start-AlStopLog (Get-AlBuildId)") < stop.indexOf("Set-Content -LiteralPath $request"));
  assert.ok(!stop.includes("Get-Date -Format 's'"));
});

test("run.ps1 prints the core's start-error line and stops waiting on it", () => {
  const run = fs.readFileSync(path.join(ROOT, "scripts", "run.ps1"), "ascii");
  const fn = run.slice(run.indexOf("function Get-AlStartError("), run.indexOf("function Get-AlUnixNow"));
  assert.match(fn, /Join-Path \$paths\.runtime 'start-error\.json'/);
  assert.match(fn, /\.Length -gt 4096\) \{ return '' \}/);
  assert.match(fn, /if \(\$at -lt \$Since\) \{ return '' \}/);
  assert.match(fn, /\$fix\.Length -gt 300 -or \$fix -notmatch '\^\[\\x20-\\x7e\]\+\$'/);
  const wait = run.slice(run.indexOf("function Wait-AlCore("));
  const body = wait.slice(0, wait.indexOf("\n}\n"));
  assert.match(body, /\$why = Get-AlStartError \$Since/);
  assert.match(body, /Write-AlLog "run: core did not start: \$why" 'ERROR'/);
  assert.match(body, /within 15 s/);
  // both waits go through it; the launch time bounds the record's age
  assert.equal((run.match(/Wait-AlCore /g) || []).length, 2);
  assert.ok(run.indexOf("$launchedAt = (Get-AlUnixNow) - 1") < run.indexOf("if (-not (Wait-AlCore $launchedAt)) { exit 1 }"));
  assert.ok(run.includes("if (-not (Wait-AlCore ((Get-AlUnixNow) - 60))) { exit 1 }"));
});
