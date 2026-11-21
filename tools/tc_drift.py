"""TC-DRIFT: watch Path of Building PoE2 releases against the pin.

Decision 0004 item 3, decision 0018, decision 0025. Python stdlib only.

- `check`: one read-only GET of the GitHub releases API (api.github.com only,
  truthful User-Agent, no cookie, no token) compares the newest PoB-PoE2
  release with config/tc_pins.json. At most one check per CHECK_EVERY_S;
  X-RateLimit-Reset / Retry-After push the next check out. State lives in the
  gitignored ops/runtime/tc_drift.json.
- `loop_check`: the al_loop tick hook. Silent until a check is due; on a new
  tag it launches ONE detached `trial` for that tag and reports one line.
  `halted=True` (the loop is HALTed) makes that launch static only.
- `trial --tag vX.Y.Z`: resolves the tag's commit, downloads the commit
  archive twice (both SHA-256 and sizes must agree, as decision 0018 requires
  for a pin), computes the candidate's content digests from the downloaded
  archive (TC-CALC-VERIFY-PIN: content_sha256 and PoB's lua_sha256, read as
  data under the path guard, never run), writes a candidate pin file in the
  sidecar, runs the opt-in
  setup step on it (tools/tc_pin.py) and then, by default, ONLY the static
  drift guard against it (AL_TC_PINS_FILE; reads the candidate's Lua, runs
  none of it): verdict static-green, static-red, untested (nothing ran) or
  error. Decision 0025 amendment (AREA-AUDIT P3-9): candidate PoB Lua runs
  under luajit only with `--live` (a manual trigger), or from the loop when
  config/local.json has "tc_drift_live_unattended": true (default off; no
  env var enables it). Live verdict: live-green (every test passed and live
  tests ran), red, untested (live tests skipped: no luajit.exe) or error.
  Decision 0025 amendment 2026-11-18 (AUTO-12, F-064): after setup the trial
  re-hashes every pob2_files entry from the extracted candidate checkout
  (read as data, never run), moves the candidate pin's entries to the new
  hashes and records old hash, new hash and parsed row count in the trial
  state for review at apply; then it prunes candidate archives, checkouts
  and trial files other than the pin's and this trial's (Recycle Bin only,
  left in place when no safe method exists, FLEET item 9).
- `trial --ref <branch or commit>` (LOOP-DRIFT-REF, decision 0025 / 0028
  amendment 2026-11-18): a rehearsal of a non-release ref (for example the
  next release branch). Same steps as a tag trial, static by default
  (`--live` is the same manual trigger); the candidate keeps the pinned tag
  and carries `rehearsal_ref`, the record goes to the state's `rehearsal`
  key (a release trial record awaiting apply is never overwritten and its
  candidate is never pruned by a rehearsal), and `apply` never accepts it.
- `apply`: writes the live-green candidate into config/tc_pins.json (the pin
  moves in one commit by whoever commits it); refuses anything else (a
  rehearsal included); prints the recorded pob2_files review lines.
- `note`: the dated HOLD line for decision 0004 when the pin stays.

Nothing from an archive is imported here; the bridge tests run in a
subprocess. Exit codes: 0 ok, 1 failure, 2 refused.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tc_pin  # noqa: E402
from server.al import exepin, paths, prio, tradestats, webfetch  # noqa: E402

API_HOSTS = ("api.github.com",)
API = "https://api.github.com/repos/{repo}"
UA_PURPOSE = "dev: Path of Building PoE2 release drift check"
PINS_ENV = paths.TC_PINS_ENV
CHECK_EVERY_S = 24 * 3600
RETRY_S = 3 * 3600
RATE_DEFAULT_S = 3600
TRIAL_STALE_S = 6 * 3600
TRIAL_MAX_LAUNCHES = 3
TRIAL_TESTS = ("tests/test_tc_bridge.py", "tests/test_tc_delta.py",
               "tests/test_tc_pob_drift_guard.py")  # MATH-POB-DRIFT-GUARD
# P3-9: the unattended default runs only the guard's static part (no luajit).
STATIC_TESTS = ("tests/test_tc_pob_drift_guard.py",)
STATIC_SELECT = "not test_live"
LIVE_OPT_IN_KEY = "tc_drift_live_unattended"
TRIAL_TIMEOUT_S = 3600
MAX_ARCHIVE = 2 * 1024 ** 3
API_MAX_BYTES = 256 * 1024
STATE_REL = Path("ops") / "runtime" / "tc_drift.json"

_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
# LOOP-DRIFT-REF: a branch name or commit sha a rehearsal may name (plain
# git ref characters only; no "..", no "//", no leading or trailing "/")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
REHEARSAL_KEY = "rehearsal_ref"  # pob2 key of a rehearsal candidate pin
# AUTO-12: the per-tag files a trial leaves in Build\tc-drift\ (a
# rehearsal's label is ref-<12 hex of its commit>)
_TRIAL_FILE = re.compile(r"^(v\d+\.\d+\.\d+|ref-[0-9a-f]{12})-(pins\.json|junit\.xml)$")
# pob2_files entries with a known data parser: the parsed row count is
# recorded beside the hashes (decision 0037 amendment parser, read as text)
ROW_PARSERS = {tradestats.POB_REL: tradestats.parse_pob_trade_stats}
RECYCLE_TIMEOUT_S = 600
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_RECYCLE_PS = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
               "$p = $env:AL_RECYCLE_PATH; "
               "if (Test-Path -LiteralPath $p -PathType Container) { "
               "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, "
               "'OnlyErrorDialogs', 'SendToRecycleBin') } else { "
               "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, "
               "'OnlyErrorDialogs', 'SendToRecycleBin') }")

RC_OK, RC_FAIL, RC_REFUSED = 0, 1, 2


class DriftError(Exception):
    """A drift step refused (no green trial, bad candidate)."""


class RateLimited(webfetch.FetchError):
    """GitHub asked us to wait; `until` is the epoch of the next allowed call."""

    def __init__(self, until):
        super().__init__(f"rate limited until {int(until)}")
        self.until = until


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


# --- tags ---------------------------------------------------------------

def parse_tag(tag):
    m = _TAG.match(tag) if isinstance(tag, str) else None
    return tuple(int(x) for x in m.groups()) if m else None


def compare(pinned, latest):
    """current / new / behind / unknown (latest vs the pinned tag)."""
    a, b = parse_tag(pinned), parse_tag(latest)
    if a is None or b is None:
        return "unknown"
    if b == a:
        return "current"
    return "new" if b > a else "behind"


# --- GitHub reads (read-only GETs) --------------------------------------

def _headers(accept):
    return {"User-Agent": webfetch.user_agent(UA_PURPOSE), "Accept": accept}


def _get(url, accept, fetch, now):
    status, hdrs, body = webfetch.request("GET", url, _headers(accept), API_HOSTS,
                                          fetch=fetch, max_bytes=API_MAX_BYTES)
    if status in (403, 429):
        until = None
        reset = webfetch.header(hdrs, "X-RateLimit-Reset")
        after = webfetch.header(hdrs, "Retry-After")
        if after and after.strip().isdigit():
            until = now + int(after.strip())
        if reset and reset.strip().isdigit() and webfetch.header(
                hdrs, "X-RateLimit-Remaining") == "0":
            until = max(until or 0, float(reset.strip()))
        if until is None and status == 429:
            until = now + RATE_DEFAULT_S
        if until is not None:
            raise RateLimited(until)
    if status != 200:
        raise webfetch.FetchError(f"HTTP {status} from {url}")
    return body or b""


def latest_release(repo, fetch=None, now=None):
    """{"tag", "published", "draft", "prerelease"} of the newest release."""
    now = time.time() if now is None else now
    body = _get(API.format(repo=repo) + "/releases/latest",
                "application/vnd.github+json", fetch, now)
    try:
        doc = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise webfetch.FetchError(f"releases reply unreadable: {e}") from e
    tag = doc.get("tag_name") if isinstance(doc, dict) else None
    if not isinstance(tag, str):
        raise webfetch.FetchError("releases reply has no tag_name")
    return {"tag": tag, "published": doc.get("published_at"),
            "draft": bool(doc.get("draft")), "prerelease": bool(doc.get("prerelease"))}


def resolve_commit(repo, tag, fetch=None, now=None):
    """The full commit sha the release tag points at."""
    if parse_tag(tag) is None:
        raise ValueError(f"not a release tag: {tag!r}")
    now = time.time() if now is None else now
    body = _get(API.format(repo=repo) + f"/commits/{tag}",
                "application/vnd.github.sha", fetch, now)
    sha = body.decode("ascii", "replace").strip()
    if not _HEX40.match(sha):
        raise webfetch.FetchError(f"tag {tag} did not resolve to a commit sha")
    return sha


def check_ref(ref):
    """The rehearsal ref when it is a plain branch name or commit sha, else
    ValueError (never a URL piece the API path could be bent with)."""
    if (not isinstance(ref, str) or not _REF.match(ref) or ".." in ref
            or "//" in ref or ref.endswith(("/", ".lock", "."))):
        raise ValueError(f"not a branch name or commit: {ref!r}")
    return ref


def resolve_ref(repo, ref, fetch=None, now=None):
    """The full commit sha a branch or commit points at (a rehearsal)."""
    check_ref(ref)
    now = time.time() if now is None else now
    body = _get(API.format(repo=repo) + f"/commits/{ref}",
                "application/vnd.github.sha", fetch, now)
    sha = body.decode("ascii", "replace").strip()
    if not _HEX40.match(sha):
        raise webfetch.FetchError(f"ref {ref} did not resolve to a commit sha")
    return sha


def rehearsal_label(commit):
    """The file label of a rehearsal: ref-<first 12 hex of its commit>."""
    return f"ref-{commit[:12]}"


# --- state --------------------------------------------------------------

def state_file(root):
    return Path(root) / STATE_REL


def load_state(root):
    try:
        doc = json.loads(state_file(root).read_text(encoding="ascii"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(root, st):
    p = state_file(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n", encoding="ascii")
    os.replace(tmp, p)


def _pins(root):
    return tc_pin.load_pins(Path(root) / "config" / "tc_pins.json")


# --- check --------------------------------------------------------------

def check(root, now, fetch=None):
    """One release check; returns and saves the state."""
    doc = _pins(root)
    pob = doc["pob2"]
    st = load_state(root)
    st.update({"checked": iso(now), "pinned": pob["tag"], "repo": pob["repo"]})
    try:
        rel = latest_release(pob["repo"], fetch=fetch, now=now)
    except RateLimited as e:
        st.update({"status": "rate-limited", "next_check": e.until, "error": str(e)})
        save_state(root, st)
        return st
    except webfetch.FetchError as e:
        st.update({"status": "error", "next_check": now + RETRY_S, "error": str(e)})
        save_state(root, st)
        return st
    st.pop("error", None)
    st.update({"latest": rel["tag"], "published": rel["published"],
               "status": compare(pob["tag"], rel["tag"]),
               "next_check": now + CHECK_EVERY_S})
    save_state(root, st)
    return st


def _trial_due(st, now):
    tr = st.get("trial") or {}
    if tr.get("tag") != st.get("latest"):
        return True
    if tr.get("state") != "launched":
        return False
    stale = now - float(tr.get("at_epoch") or 0) > TRIAL_STALE_S
    return stale and int(tr.get("launches") or 0) < TRIAL_MAX_LAUNCHES


def status_text(root):
    """`status` output: the saved state as JSON, or one plain line naming the
    pinned tag before the first check (AUDIT-P6-LOW P6-4)."""
    st = load_state(root)
    if st:
        return json.dumps(st, indent=1, sort_keys=True)
    pinned = _pins(root)["pob2"]["tag"]
    return (f"tc drift: no check run yet; pinned PoB-PoE2 {pinned} "
            "(run `python tools/tc_drift.py check`)")


def summary(st):
    status, pinned, latest = st.get("status"), st.get("pinned"), st.get("latest")
    if status == "current":
        return f"tc drift: PoB-PoE2 {pinned} current"
    if status == "rate-limited":
        return f"tc drift: rate limited, next check {iso(st['next_check'])}"
    if status == "error":
        return f"tc drift: check failed: {st.get('error')}"
    if status == "new":
        tr = st.get("trial") or {}
        if tr.get("state") == "launched":
            return f"tc drift: PoB-PoE2 {latest} released (pin {pinned}), trial launched"
        if tr.get("verdict") == "live-green":
            return (f"tc drift: PoB-PoE2 {latest} trial live-green, pin move ready "
                    "(tools/tc_drift.py apply)")
        if tr.get("verdict") == "static-green":
            return (f"tc drift: PoB-PoE2 {latest} trial static-green, live trial is "
                    f"manual (tools/tc_drift.py trial --tag {latest} --live), hold")
        return f"tc drift: PoB-PoE2 {latest} trial {tr.get('verdict') or tr.get('state')}, hold"
    return f"tc drift: latest {latest} vs pin {pinned}: {status}, hold"


def live_opted_in(root):
    """P3-9: the loop's trial runs candidate Lua only when config/local.json
    carries "tc_drift_live_unattended": true (a real boolean). No env var."""
    try:
        cfg = json.loads((Path(root) / "config" / "local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(cfg, dict) and cfg.get(LIVE_OPT_IN_KEY) is True


def loop_check(root, now, fetch=None, launch=None, halted=False):
    """The al_loop tick hook: None when no check is due (or no pin file);
    else one summary line. A new tag launches one detached trial: static
    only unless the host opted in to unattended live trials (P3-9). While
    the loop is HALTed (`halted`, LOOP-WATCH-SETTLED, ruling Q-13) the read,
    the record and the launch still happen, but the launch is static only
    whatever live_opted_in says."""
    if not (Path(root) / "config" / "tc_pins.json").is_file():
        return None
    st = load_state(root)
    if now < float(st.get("next_check") or 0):
        return None
    try:
        st = check(root, now, fetch=fetch)
    except tc_pin.PinError as e:
        return f"tc drift: pin file refused: {e}"
    if st.get("status") == "new" and _trial_due(st, now):
        prev = st.get("trial") or {}
        n = int(prev.get("launches") or 0) + 1 if prev.get("tag") == st["latest"] else 1
        launch = launch or launch_trial
        try:
            pid = launch(root, st["latest"], live=not halted and live_opted_in(root))
        except OSError as e:
            return f"tc drift: {st['latest']} released, trial launch failed: {e}"
        st["trial"] = {"tag": st["latest"], "state": "launched", "at": iso(now),
                       "at_epoch": now, "launches": n, "pid": pid}
        save_state(root, st)
    return summary(st)


def launch_trial(root, tag, live=False):
    """A detached, windowless `tc_drift.py trial --tag <tag>` (plus `--live`
    only when the host opted in, P3-9); returns its pid."""
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    exe = pyw if pyw.is_file() else exe
    logs = paths.all_runtime_paths()["logs"]
    logs.mkdir(parents=True, exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_NO_WINDOW)
    flags = prio.below_normal(flags)  # RUN-CALC-PRIORITY (F-107): a batch child
    with open(logs / "tc-drift.log", "ab") as out:
        proc = subprocess.Popen([str(exe), str(Path(root) / "tools" / "tc_drift.py"),
                                 "trial", "--tag", tag, *(["--live"] if live else [])],
                                cwd=str(root),
                                stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                creationflags=flags, close_fds=True)
    return proc.pid


# --- trial --------------------------------------------------------------

def candidate(doc, tag, commit, sha256, size, today, archive=None, ref=None):
    """The pin document with PoB-PoE2 moved to tag / commit (LuaJIT kept).
    TC-CALC-VERIFY-PIN: the content digests (content_sha256, lua_sha256) are
    computed from `archive`, the downloaded candidate zip (tc_pin.
    archive_digests: path guard, data only). Without an archive the old
    digests are dropped, so the candidate does not validate (never carried
    over from another commit, never guessed). LOOP-DRIFT-REF: a rehearsal
    (`ref`) keeps the pinned tag and records the ref under REHEARSAL_KEY,
    which apply refuses."""
    out = copy.deepcopy(doc)
    pob = out["pob2"]
    name = pob["repo"].split("/")[1]
    top = f"{name}-{commit}"
    pob.update({"tag": tag, "commit": commit,
                "archive_url": f"https://github.com/{pob['repo']}/archive/{commit}.zip",
                "archive_sha256": sha256, "archive_size": size,
                "top_dir": top, "verified": today})
    pob.pop(tc_pin.CONTENT_KEY, None)
    pob.pop(tc_pin.LUA_KEY, None)
    pob.pop(REHEARSAL_KEY, None)
    if ref is not None:
        pob[REHEARSAL_KEY] = ref
    if archive is not None:
        digests = tc_pin.archive_digests(archive, top)
        pob[tc_pin.CONTENT_KEY] = digests[tc_pin.CONTENT_KEY]
        pob[tc_pin.LUA_KEY] = digests[tc_pin.LUA_KEY]
    return out


def parse_junit(text):
    """{"tests", "failures", "errors", "skipped", "live_ran"} of a junit xml."""
    root = ET.fromstring(text)
    out = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "live_ran": 0}
    for case in root.iter("testcase"):
        out["tests"] += 1
        kinds = {child.tag for child in case}
        if "skipped" in kinds:
            out["skipped"] += 1
            continue
        if "failure" in kinds:
            out["failures"] += 1
        if "error" in kinds:
            out["errors"] += 1
        if case.get("name", "").startswith("test_live"):
            out["live_ran"] += 1
    return out


def download_measure(url, dest):
    """Stream url into dest; (sha256, size)."""
    h, size = hashlib.sha256(), 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with open(part, "wb") as f:
        for block in tc_pin.http_stream(url, MAX_ARCHIVE):
            h.update(block)
            size += len(block)
            f.write(block)
    os.replace(part, dest)
    return h.hexdigest(), size


def trial_argv(junit_path, live=False):
    """The pytest argv of a trial: the static guard only unless live (P3-9).
    Isolated interpreter (-I: no PYTHONPATH, no user site)."""
    select = [*TRIAL_TESTS] if live else [*STATIC_TESTS, "-k", STATIC_SELECT]
    return [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            *select, f"--junitxml={junit_path}"]


def run_bridge_tests(cand_path, junit_path, environ, live=False):
    """The trial tests against the candidate pins, in a subprocess with a
    hard timeout; cwd is the repo, never the extracted candidate tree."""
    env = dict(os.environ)
    env.update(environ or {})
    env[PINS_ENV] = str(cand_path)
    argv = trial_argv(junit_path, live)
    # RUN-CALC-PRIORITY (F-107): the trial's test run is a batch child too
    subprocess.run(argv, cwd=str(ROOT), env=env, timeout=TRIAL_TIMEOUT_S,
                   stdin=subprocess.DEVNULL, capture_output=True,
                   creationflags=prio.below_normal(_NO_WINDOW))
    return parse_junit(Path(junit_path).read_text(encoding="utf-8"))


def _verdict(res, live=True):
    if not live:
        if res["live_ran"]:
            raise DriftError("static trial ran live tests")  # selection broke
        if res["failures"] or res["errors"]:
            return "static-red", (f"{res['failures']} failed, {res['errors']} errors "
                                  f"of {res['tests']} static guard tests")
        if res["tests"] <= res["skipped"]:
            return "untested", "static guard skipped (candidate checkout absent)"
        return "static-green", (f"{res['tests'] - res['skipped']} static guard tests "
                                "passed; live trial is manual (--live)")
    if res["failures"] or res["errors"]:
        return "red", f"{res['failures']} failed, {res['errors']} errors of {res['tests']}"
    if not res["live_ran"]:
        return "untested", (f"live bridge tests skipped ({res['skipped']} skipped): "
                            "no luajit.exe on this host")
    return "live-green", f"{res['tests']} tests, {res['live_ran']} live, all passed"


# --- AUTO-12: pob2_files re-hash and candidate prune --------------------

def _file_sha256(path):
    h, size = hashlib.sha256(), 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def _rel_parts(rel):
    """The parts of a pob2_files key: a plain relative posix path only."""
    p = PurePosixPath(rel) if isinstance(rel, str) else None
    if (p is None or not p.parts or p.is_absolute() or ".." in p.parts
            or "\\" in rel or ":" in rel):
        raise DriftError(f"pob2_files path refused: {rel!r}")
    return p.parts


def rehash_pob2_files(cand, environ=None):
    """Re-hash every pob2_files entry from the candidate's extracted checkout
    (after setup) and move the candidate's entries to the new hash, size and
    commit. Returns {rel: {old_sha256, old_size, new_sha256, new_size, rows,
    changed}} for review at apply. Files are read as data, never run; rows is
    the parsed row count where ROW_PARSERS knows the file, else None. A file
    the candidate lacks keeps its old entry (new_sha256 None), so the static
    guard reports it. The checkout must carry the candidate archive's marker."""
    files = cand.get("pob2_files")
    if not isinstance(files, dict):
        return {}
    checkout = tc_pin.layout(cand, environ)["pob2_checkout"]
    marker = tc_pin.read_marker(checkout)
    if not marker or marker.get("archive_sha256") != cand["pob2"]["archive_sha256"]:
        raise DriftError("candidate checkout missing or not extracted from the "
                         "candidate archive; pob2_files not re-hashed")
    out = {}
    for rel, spec in files.items():
        if rel.startswith("_") or not isinstance(spec, dict):
            continue
        path = checkout.joinpath(*_rel_parts(rel))
        row = {"old_sha256": spec.get("sha256"), "old_size": spec.get("size"),
               "new_sha256": None, "new_size": None, "rows": None}
        if path.is_file() and not path.is_symlink():
            row["new_sha256"], row["new_size"] = _file_sha256(path)
            parse = ROW_PARSERS.get(rel)
            if parse is not None and row["new_size"] <= tradestats.POB_MAX_BYTES:
                try:
                    row["rows"] = len(parse(path.read_bytes().decode("utf-8")))
                except UnicodeDecodeError:
                    row["rows"] = 0
            spec.update({"sha256": row["new_sha256"], "size": row["new_size"],
                         "commit": cand["pob2"]["commit"]})
        row["changed"] = (row["new_sha256"], row["new_size"]) != (row["old_sha256"],
                                                                 row["old_size"])
        out[rel] = row
    return out


def pob2_files_review(tr):
    """One review line per re-hashed pob2_files entry of a trial record."""
    lines = []
    for rel, row in sorted((tr.get("pob2_files") or {}).items()):
        if not isinstance(row, dict):
            continue
        old, new = row.get("old_sha256") or "none", row.get("new_sha256")
        rows = row.get("rows")
        rows_text = "" if rows is None else f", {rows} rows parsed"
        if new is None:
            lines.append(f"review pob2_files {rel}: MISSING in the candidate "
                         f"(pin sha256 {old})")
        elif not row.get("changed"):
            lines.append(f"review pob2_files {rel}: unchanged sha256 {new}{rows_text}")
        else:
            lines.append(f"review pob2_files {rel}: sha256 {old} -> {new} "
                         f"(size {row.get('old_size')} -> {row.get('new_size')}"
                         f"{rows_text})")
    return lines


def recycle_path(path):
    """Send one file or folder to the Recycle Bin (FLEET item 9). True when it
    left. Off Windows there is no safe method: the path stays (False)."""
    if os.name != "nt":
        return False
    env = dict(os.environ, AL_RECYCLE_PATH=str(path))
    ps = str(exepin.system_tool("WindowsPowerShell", "v1.0", "powershell.exe"))
    try:
        subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", _RECYCLE_PS],
                       env=env, creationflags=_NO_WINDOW, capture_output=True,
                       timeout=RECYCLE_TIMEOUT_S, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return not Path(path).exists()


def prune_candidates(doc, keep_commit, keep_tag, environ=None, recycle=None,
                     also_keep=()):
    """Recycle trial leftovers other than the pin's and the newest (this
    trial's): PoB-PoE2 archives `<name>-<commit>.zip` and checkouts
    `<name>-<commit>` in the sidecar pob2 cache, and `<tag>-pins.json` /
    `<tag>-junit.xml` in Build\\tc-drift. Only exact name shapes, never a
    link, nothing outside the sidecar. `also_keep` holds more (commit,
    label) pairs to keep (a rehearsal keeps the release trial awaiting
    apply). Returns {"pruned": [...], "left": [...]} (names); a recycle that
    fails leaves the item in place."""
    recycle = recycle or recycle_path
    rt = paths.all_runtime_paths(environ)
    pob = doc["pob2"]
    keep_commits = {pob["commit"], keep_commit}
    keep_tags = {pob["tag"], keep_tag}
    for commit, label in also_keep:
        keep_commits.add(commit)
        keep_tags.add(label)
    name = pob["repo"].split("/")[1]
    shape = re.compile(rf"^{re.escape(name)}-([0-9a-f]{{40}})(\.zip)?$")
    targets = []
    cache = rt["pob2_cache"]
    if cache.is_dir():
        for e in sorted(cache.iterdir()):
            m = shape.match(e.name)
            if not m or e.is_symlink() or m.group(1) in keep_commits:
                continue
            if (e.is_file() if m.group(2) else e.is_dir()):
                targets.append(e)
    work = rt["build"] / "tc-drift"
    if work.is_dir():
        for e in sorted(work.iterdir()):
            m = _TRIAL_FILE.match(e.name)
            if m and e.is_file() and not e.is_symlink() and m.group(1) not in keep_tags:
                targets.append(e)
    out = {"pruned": [], "left": []}
    for t in targets:
        try:
            gone = bool(recycle(t))
        except OSError:
            gone = False
        out["pruned" if gone else "left"].append(t.name)
    return out


def _record_keep(tr):
    """(commit, label) of a trial record's candidate, or None (a rehearsal
    keeps the release trial awaiting apply out of its prune)."""
    if not isinstance(tr, dict) or not tr.get("tag"):
        return None
    commit = tr.get("commit")
    if not (isinstance(commit, str) and _HEX40.match(commit)) and tr.get("candidate"):
        try:
            commit = json.loads(Path(tr["candidate"]).read_text(
                encoding="ascii"))["pob2"]["commit"]
        except (OSError, ValueError, KeyError, TypeError):
            commit = None
    if not (isinstance(commit, str) and _HEX40.match(commit)):
        return None
    return commit, tr["tag"]


def trial(root, tag=None, environ=None, fetch=None, download=None, setup=None,
          run_tests=None, today=None, live=False, recycle=None, ref=None):
    """Trial `tag`: the static guard only, or the live bridge tests when
    `live` (P3-9); records and returns the result. AUTO-12: the candidate's
    pob2_files are re-hashed after setup, and other candidates are pruned.
    LOOP-DRIFT-REF: `ref` (a branch or commit, instead of `tag`) runs the
    same steps as a rehearsal: static unless `live`, recorded under the
    state's `rehearsal` key, never accepted by apply."""
    if (tag is None) == (ref is None):
        raise ValueError("trial needs exactly one of a tag or a ref")
    download = download or download_measure
    setup = setup or (lambda doc, env: tc_pin.run_setup(doc, environ=env))
    run_tests = run_tests or run_bridge_tests
    today = today or time.strftime("%Y-%m-%d")
    doc = _pins(root)
    work = paths.all_runtime_paths(environ)["build"] / "tc-drift"
    rehearsal = ref is not None
    if rehearsal:
        tag = doc["pob2"]["tag"]  # a rehearsal candidate keeps the pinned tag
    res = {"tag": tag, "state": "done", "at": iso(time.time()), "live": bool(live)}
    if rehearsal:
        res.update({"rehearsal": True, "ref": ref})
    label = tag
    commit = None
    try:
        if rehearsal:
            commit = resolve_ref(doc["pob2"]["repo"], ref, fetch=fetch)
            label = rehearsal_label(commit)
        else:
            commit = resolve_commit(doc["pob2"]["repo"], tag, fetch=fetch)
        res["commit"] = commit
        name = doc["pob2"]["repo"].split("/")[1]
        url = f"https://github.com/{doc['pob2']['repo']}/archive/{commit}.zip"
        archive = paths.all_runtime_paths(environ)["pob2_cache"] / f"{name}-{commit}.zip"
        first = download(url, archive)
        check_copy = work / f"{name}-{commit}.check.zip"
        second = download(url, check_copy)
        try:
            check_copy.unlink()  # a re-downloadable copy, only for the hash check
        except OSError:
            pass
        if first != second:
            raise DriftError(f"two downloads of {tag} differ: {first} vs {second}")
        cand = candidate(doc, tag, commit, first[0], first[1], today, archive=archive,
                         ref=ref)
        problems = tc_pin.validate_pins(cand)
        if problems:
            raise DriftError("candidate pins invalid: " + "; ".join(problems))
        work.mkdir(parents=True, exist_ok=True)
        cand_path = work / f"{label}-pins.json"
        cand_path.write_text(json.dumps(cand, indent=2) + "\n", encoding="ascii")
        res["candidate"] = str(cand_path)
        setup(cand, environ)
        # AUTO-12: the candidate's own pob2_files hashes, recorded for apply
        res["pob2_files"] = rehash_pob2_files(cand, environ)
        cand_path.write_text(json.dumps(cand, indent=2) + "\n", encoding="ascii")
        tests = run_tests(cand_path, work / f"{label}-junit.xml", environ, live=live)
        res["tests"] = tests
        res["verdict"], res["detail"] = _verdict(tests, live)
        if rehearsal:
            res["detail"] += "; rehearsal of a non-release ref, apply never accepts it"
    except (DriftError, webfetch.FetchError, tc_pin.HashMismatch, tc_pin.UnsafeArchive,
            OSError, RuntimeError, ValueError, ET.ParseError, zipfile.BadZipFile,
            subprocess.SubprocessError) as e:
        res["verdict"], res["detail"] = "error", f"{type(e).__name__}: {e}"
    st = load_state(root)
    if commit is not None:
        keep = _record_keep(st.get("trial")) if rehearsal else None
        try:
            res["prune"] = prune_candidates(doc, commit, label, environ, recycle=recycle,
                                            also_keep=[keep] if keep else ())
        except OSError as e:
            res["prune"] = {"pruned": [], "left": [], "error": f"{type(e).__name__}: {e}"}
    if rehearsal:
        st["rehearsal"] = res  # never the trial record apply reads
    else:
        prev = st.get("trial") or {}
        if prev.get("tag") == tag:
            res["launches"] = prev.get("launches", 1)
        st["trial"] = res
    save_state(root, st)
    return res


# --- apply / note -------------------------------------------------------

def apply(root):
    """Move config/tc_pins.json to the green trial's candidate; the tag."""
    st = load_state(root)
    tr = st.get("trial") or {}
    if tr.get("rehearsal") or tr.get("ref"):
        raise DriftError("a --ref trial is a rehearsal; apply never accepts it")
    if tr.get("verdict") != "live-green" or not tr.get("live") or not tr.get("candidate"):
        raise DriftError("no live-green trial to apply "
                         f"(trial: {tr.get('verdict') or 'none'})")
    cand = json.loads(Path(tr["candidate"]).read_text(encoding="ascii"))
    if REHEARSAL_KEY in (cand.get("pob2") or {}):
        raise DriftError("the candidate is a rehearsal of a non-release ref; "
                         "apply never accepts it")
    problems = tc_pin.validate_pins(cand)
    if problems or cand["pob2"]["tag"] != tr["tag"]:
        raise DriftError("candidate pins invalid: " + "; ".join(problems or ["tag mismatch"]))
    pins = Path(root) / "config" / "tc_pins.json"
    text = json.dumps(cand, indent=2) + "\n"
    tmp = pins.with_name(pins.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    os.replace(tmp, pins)
    tr["state"] = "applied"
    st["trial"] = tr
    save_state(root, st)
    return tr["tag"]


def hold_note(st):
    """The dated HOLD line for decision 0004 when the pin stays."""
    tr = st.get("trial") or {}
    date = (tr.get("at") or st.get("checked") or iso(time.time()))[:10]
    if st.get("trial") and tr.get("tag") == st.get("latest"):
        date = (st.get("checked") or tr.get("at") or "")[:10] or date
        return (f"{date} HOLD: PoB-PoE2 {tr['tag']} trial {tr.get('verdict')} "
                f"({tr.get('detail')}); pin stays {st.get('pinned')}.")
    return (f"{date} HOLD: no PoB-PoE2 release after {st.get('pinned')} "
            f"(latest {st.get('latest')}); pin stays.")


# --- CLI ----------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="tc_drift", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="one release check now (ignores the daily throttle)")
    t = sub.add_parser("trial", help="trial the bridge tests on a release tag, or "
                       "rehearse a non-release ref (--ref, never applied)")
    which = t.add_mutually_exclusive_group(required=True)
    which.add_argument("--tag")
    which.add_argument("--ref", help="a branch or commit to rehearse (static unless "
                       "--live; apply never accepts it)")
    t.add_argument("--live", action="store_true",
                   help="also run the candidate's Lua under luajit (manual trigger, P3-9)")
    sub.add_parser("apply", help="move the pin to the green trial's candidate")
    sub.add_parser("note", help="print the dated HOLD line for decision 0004")
    sub.add_parser("status", help="print the drift state")
    args = ap.parse_args(argv)
    root = ROOT
    try:
        if args.cmd == "check":
            st = check(root, time.time())
            print(summary(st))
            return RC_FAIL if st.get("status") in ("error", "rate-limited") else RC_OK
        if args.cmd == "trial":
            if args.ref is not None:
                res = trial(root, ref=args.ref, live=args.live)
                print(f"rehearsal {args.ref}: {res['verdict']}: {res['detail']}")
            else:
                res = trial(root, args.tag, live=args.live)
                print(f"trial {args.tag}: {res['verdict']}: {res['detail']}")
            return RC_OK if res["verdict"] in ("live-green", "static-green") else RC_FAIL
        if args.cmd == "apply":
            tag = apply(root)
            for line in pob2_files_review(load_state(root).get("trial") or {}):
                print(line)
            print(f"pin moved to PoB-PoE2 {tag}; commit config/tc_pins.json")
            return RC_OK
        if args.cmd == "note":
            print(hold_note(load_state(root)))
            return RC_OK
        print(status_text(root))
        return RC_OK
    except (DriftError, tc_pin.PinError) as e:
        print(f"refused: {e}")
        return RC_REFUSED


if __name__ == "__main__":
    sys.exit(main())
