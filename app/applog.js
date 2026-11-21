"use strict";
/* RUN-OBS-LOGS-SHELL (F-090; research 0051 R7): the client's own log,
   overlay.log in the sidecar Logs folder, in the one format of AshLight's
   Python logs (server/al/logs.py).

   - At start a file over START_LIMIT bytes (1 MB) moves to overlay.log.1,
     replacing an older .1 (one old file kept). A move that fails (the file
     is held open elsewhere) is not an error: the log keeps appending.
   - Every line is `<UTC ISO stamp> <LEVEL> <name>[<pid>] <message>`, e.g.
     `2026-11-21T14:35:31.123Z INFO client[4242] overlay started; ...`.
   - The first line of every start is the build banner: `AshLight <build>
     client start (pid <n>, electron <x.y.z>)`, the build id as
     server/al/buildinfo.py composes it (version plus 12 hex) from the same
     files only: the .git files of a checkout (HEAD, a loose ref, then
     packed-refs; a linked worktree's .git file and commondir followed),
     else the BUILD file at the payload root. No subprocess, no network.
   - An absolute path in a message is written as <path> (a drive path or a
     UNC share), so no line names a folder of the player's machine.
   - A write or stream error is swallowed: the log never throws into the
     app. After a stream error the lines go to stderr.
   Nothing here reads anything but AshLight's own files. */

const fs = require("fs");
const path = require("path");

const FILE_NAME = "overlay.log";
const START_LIMIT = 1024 * 1024;
const BACKUP_SUFFIX = ".1";
const NAME = "client";
const COMMIT_LEN = 12;
const SMALL_MAX = 4096;
const PACKED_MAX = 16 * 1024 * 1024;
const REF_HOPS = 5;
const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const PATH_MARK = "<path>";
const TAIL = ".,;:)]}";

const HEX = /^[0-9a-f]{40}([0-9a-f]{24})?$/;
const SHORT = /^[0-9a-f]{12,64}$/;
const REF = /^refs\/[A-Za-z0-9._\/-]+$/;
const DRIVE = /(^|[^A-Za-z0-9])[A-Za-z]:[\\/][^\s"'<>|]*/g;
const UNC = /\\\\[^\s\\"'<>|]+\\[^\s"'<>|]*/g;

function backupPath(file) {
  return file + BACKUP_SUFFIX;
}

/* Move `file` to `<file>.1` when it is over `limit` bytes. True when it
   moved; false when it was small, missing or could not move. Never throws. */
function rotateAtStart(file, fsi, limit) {
  const f = fsi || fs;
  const lim = typeof limit === "number" ? limit : START_LIMIT;
  try {
    if (f.statSync(file).size <= lim) { return false; }
    f.renameSync(file, backupPath(file));
    return true;
  } catch (e) {
    return false;
  }
}

function stamp(now) {
  const d = now instanceof Date ? now : new Date(typeof now === "number" ? now : Date.now());
  return d.toISOString();
}

function level(word) {
  const w = String(word || "INFO").toUpperCase();
  return LEVELS.indexOf(w) >= 0 ? w : "INFO";
}

/* The trailing punctuation of a path match stays (as logs.py _TAIL). */
function mark(match) {
  let tail = "";
  let m = match;
  while (m && TAIL.indexOf(m[m.length - 1]) >= 0) { tail = m[m.length - 1] + tail; m = m.slice(0, -1); }
  return PATH_MARK + tail;
}

/* Every absolute path as <path>. */
function scrub(text) {
  return String(text)
    .replace(UNC, (m) => mark(m))
    .replace(DRIVE, (m, lead) => lead + mark(m.slice(lead.length)));
}

/* One line in the one format (no line end). */
function formatLine(name, lvl, message, now, pid) {
  const id = typeof pid === "number" ? pid : process.pid;
  return stamp(now) + " " + level(lvl) + " " + name + "[" + id + "] " +
    scrub(message).replace(/[\r\n]+/g, " ");
}

/* -- the build id (mirror of server/al/buildinfo.py, files only) -------- */

function small(fsi, file) {
  try {
    const st = fsi.statSync(file);
    if (!st.isFile() || st.size > SMALL_MAX) { return null; }
    const text = fsi.readFileSync(file, "latin1");
    if (!/^[\x00-\x7f]*$/.test(text)) { return null; }
    return text.trim();
  } catch (e) {
    return null;
  }
}

function gitDirs(fsi, root) {
  const dot = path.join(root, ".git");
  let st = null;
  try { st = fsi.statSync(dot); } catch (e) { return null; }
  if (st.isDirectory()) { return [dot, dot]; }
  const text = small(fsi, dot);
  if (!text || text.indexOf("gitdir:") !== 0) { return null; }
  let gitdir = text.slice("gitdir:".length).trim();
  if (!path.isAbsolute(gitdir)) { gitdir = path.join(root, gitdir); }
  let common = gitdir;
  const rel = small(fsi, path.join(gitdir, "commondir"));
  if (rel) { common = path.isAbsolute(rel) ? rel : path.join(gitdir, rel); }
  return [gitdir, common];
}

function packed(fsi, common, ref) {
  const file = path.join(common, "packed-refs");
  try {
    const st = fsi.statSync(file);
    if (!st.isFile() || st.size > PACKED_MAX) { return null; }
    for (const raw of fsi.readFileSync(file, "latin1").split("\n")) {
      const line = raw.trim();
      if (!line || line[0] === "#" || line[0] === "^") { continue; }
      const sp = line.indexOf(" ");
      if (sp > 0 && line.slice(sp + 1) === ref && HEX.test(line.slice(0, sp))) {
        return line.slice(0, sp);
      }
    }
  } catch (e) {
    return null;
  }
  return null;
}

function resolveRef(fsi, gitdir, common, start) {
  let ref = start;
  for (let i = 0; i < REF_HOPS; i++) {
    if (!REF.test(ref) || ref.split("/").indexOf("..") >= 0) { return null; }
    let text = null;
    for (const base of [gitdir, common]) {
      text = small(fsi, path.join(base, ...ref.split("/")));
      if (text) { break; }
    }
    if (!text) { return packed(fsi, common, ref); }
    if (text.indexOf("ref:") === 0) { ref = text.slice(4).trim(); continue; }
    return HEX.test(text) ? text : null;
  }
  return null;
}

function gitCommit(root, fsi) {
  const f = fsi || fs;
  const dirs = gitDirs(f, root);
  if (!dirs) { return null; }
  const head = small(f, path.join(dirs[0], "HEAD"));
  if (!head) { return null; }
  const sha = head.indexOf("ref:") === 0
    ? resolveRef(f, dirs[0], dirs[1], head.slice(4).trim())
    : (HEX.test(head) ? head : null);
  return sha ? sha.slice(0, COMMIT_LEN) : null;
}

function buildFileCommit(root, version, fsi) {
  const text = small(fsi || fs, path.join(root, "BUILD"));
  if (!text) { return null; }
  let doc = null;
  try { doc = JSON.parse(text); } catch (e) { return null; }
  if (!doc || typeof doc !== "object" || doc.version !== version) { return null; }
  if (typeof doc.commit !== "string" || !SHORT.test(doc.commit)) { return null; }
  return doc.commit.slice(0, COMMIT_LEN);
}

/* The version of app/package.json (the one VERSION, DOCS-FRESH). */
function appVersion(fsi) {
  try {
    const v = JSON.parse((fsi || fs).readFileSync(path.join(__dirname, "package.json"), "utf8")).version;
    return typeof v === "string" && /^[0-9A-Za-z.+-]{1,32}$/.test(v) ? v : "0.0.0";
  } catch (e) {
    return "0.0.0";
  }
}

/* '<version>[+<12 hex>]' for the checkout or payload root (default: the
   folder above app/, the repository or the installed payload). */
function buildId(root, version, fsi) {
  const ver = typeof version === "string" && version ? version : appVersion(fsi);
  root = root || path.dirname(__dirname);
  let sha = null;
  try { sha = gitCommit(root, fsi) || buildFileCommit(root, ver, fsi); } catch (e) { sha = null; }
  return sha ? ver + "+" + sha : ver;
}

function banner(build, pid, electron) {
  const id = typeof pid === "number" ? pid : process.pid;
  return "AshLight " + build + " client start (pid " + id + ", electron " +
    (electron || "unknown") + ")";
}

/* -- the log ------------------------------------------------------------- */

/* createLog(opts) -> log(message); log.warn / log.error write the other
   level words; log.open(dir, build) opens <dir>/overlay.log (rotated at
   start, banner first; build defaults to buildId()); before it, after
   log.close() and after a stream error, lines go to stderr. opts (all
   optional, injectable for tests): fs, stderr, now, pid, electron (the
   version string). */
function createLog(opts) {
  const o = opts || {};
  const f = o.fs || fs;
  const errOut = o.stderr || process.stderr;
  const now = o.now || (() => new Date());
  const pid = typeof o.pid === "number" ? o.pid : process.pid;
  let stream = null;

  function toStderr(line) {
    try { errOut.write(line); } catch (e) { /* nowhere left to say it */ }
  }

  function write(lvl, message) {
    const line = formatLine(NAME, lvl, message, now(), pid) + "\n";
    if (!stream) { toStderr(line); return; }
    try {
      stream.write(line);
    } catch (e) {
      stream = null;
      toStderr(line);
    }
  }

  const log = (message) => write("INFO", message);
  log.warn = (message) => write("WARNING", message);
  log.error = (message) => write("ERROR", message);

  /* Open the file; false when it could not be opened (stderr then). */
  log.open = (dir, build) => {
    if (!dir) { return false; }
    try {
      f.mkdirSync(dir, { recursive: true });
      const file = path.join(dir, FILE_NAME);
      rotateAtStart(file, f);
      const s = f.createWriteStream(file, { flags: "a" });
      s.on("error", () => { if (stream === s) { stream = null; } });
      stream = s;
    } catch (e) {
      stream = null;
      return false;
    }
    write("INFO", banner(build || buildId(null, null, f), pid, o.electron));
    return true;
  };

  log.isOpen = () => stream !== null;

  /* End the file (will-quit, tests); later lines go to stderr. done(),
     when given, runs once the file is flushed and closed. */
  log.close = (done) => {
    const s = stream;
    stream = null;
    const cb = typeof done === "function" ? done : () => {};
    if (!s || typeof s.end !== "function") { cb(); return; }
    try { s.end(cb); } catch (e) { cb(); }
  };
  return log;
}

module.exports = { FILE_NAME, START_LIMIT, NAME, backupPath, rotateAtStart, stamp, scrub,
                   formatLine, gitCommit, buildFileCommit, appVersion, buildId, banner,
                   createLog };
