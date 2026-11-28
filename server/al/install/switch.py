"""The version switch of an install: apply-staged, confirm and rollback
(REL-UPDATE-SWITCH, finding F-077, DEP-11; docs/plan/05-deployment.md
"How an update swaps versions" steps 4 and 5, and "Rollback").

- apply(home, now): run by the launcher before every client start
  (`apply-staged --if-due`). While the marker's pending_confirm is true it
  only counts the start (bump_attempt); at the second start without a
  confirm it rolls back by itself. Otherwise, when a staged version is
  due (apply_after reached; without if_due at once: "Update now") and no
  core of this home runs, it switches the marker (previous = old,
  pending_confirm = true, start_attempts = 0), rewrites and reads back the
  shortcuts, the uninstall entry, uninstall.ps1 and the logon task action
  (shell.rewrite) and asks the launcher to relaunch from the marker.
  With nothing staged it reads one folder listing and the marker.
- bump_attempt(home): start_attempts + 1 while pending_confirm, written
  and read back.
- rollback(home): the marker goes back to `previous` (its runtimes too),
  the shell entries are rewritten and read back, the version that was
  left lands in <home>/data/update_skip.json (never applied or offered
  again; a newer release is) and the report gains one line.
- confirm(home, health=callable): the first health answer of the active
  version clears pending_confirm; then the version folders that are
  neither `version`, `previous` nor staged, and the runtime folders none
  of them needs, are removed (AshLight's own extracted folders: each is
  re-made from its cached zip or its pinned publisher zip).

"A core of this home runs" is decided from this home's own files only:
<home>/data/core.alive (pid, recorded creation time) and the supervisor's
keepalive.json / keepalive.lock, by the proven-ours rule of decision 0010
(server/al/procs.py). It never lists processes and never looks at the
game. Every shell effect goes through shell.py and its one injected
runner. Every result line names no path; the lines go to
<home>/logs/reports/last-update.json ("lines", the last LINES_KEPT).
Runs only in the installer's own process; no network but the loopback
health answer of this home's own core; standard library only.
"""

import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .. import NAME, jsonfile, paths, ports
from . import home as homemod
from . import shell as shellmod

MAX_ATTEMPTS = 2              # the second start without a confirm rolls back
SKIP_NAME = "update_skip.json"
SKIP_SCHEMA = 1
SKIP_KEPT = 50
LINES_KEPT = 20
REPORT_NAME = "last-update.json"
REPORT_SCHEMA = 1
MAX_REPORT_BYTES = 256 * 1024
MAX_STAGED_BYTES = 64 * 1024
MAX_HEALTH_BYTES = 64 * 1024
MAX_STATE_BYTES = 4 * 1024 * 1024   # the snapshot default_idle reads
PREVIOUS_RUNTIMES = "previous_runtimes"  # marker key beyond MARKER_FIELDS
RUNTIME_KEYS = ("python", "electron")
HEALTH_TIMEOUT_S = 3.0
CONFIRM_WAIT_S = 60.0
CONFIRM_POLL_S = 1.0

EXIT_OK = 0          # nothing changed: start as usual
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_BUSY = 3        # a core of this home runs: nothing switched
EXIT_SWITCHED = 10   # the marker moved: relaunch from the marker

NOTHING, NOT_DUE, STARTED, SWITCHED, ROLLED_BACK = (
    "nothing staged", "not due", "start counted", "switched", "rolled back")
CONFIRMED, CURRENT, UNCONFIRMED, BUSY, FAILED = (
    "confirmed", "current", "unconfirmed", "busy", "failed")


class SwitchFailed(Exception):
    """The switch could not run; the text names no path."""


# --- small readers ----------------------------------------------------------------

def _now(now):
    when = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _parse_time(text):
    if not isinstance(text, str) or not 10 <= len(text) <= 40:
        return None
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def _plain(name):
    return homemod._plain_name(name)


def staged_versions(home):
    """The versions with a staged document, oldest first (one listing)."""
    folder = homemod.layout(home)["staged"]
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = [n[:-5] for n in names if n.endswith(".json") and homemod.is_version(n[:-5])]
    return sorted(found, key=homemod.version_key)


def read_staged(home, version):
    """<home>/staged/<version>.json as a dict naming that version, or None."""
    path = homemod.layout(home)["staged"] / f"{version}.json"
    doc = jsonfile.read_json(path, max_bytes=MAX_STAGED_BYTES, kind=dict, default=None)
    if not isinstance(doc, dict) or doc.get("version") != version:
        return None
    return doc


def drop_staged(home, version):
    """Remove the staged document of `version` (our own small file, re-made
    from its zip). True when one was removed."""
    path = homemod.layout(home)["staged"] / f"{version}.json"
    try:
        path.unlink()
        return True
    except OSError:
        return False


# --- update_skip.json -----------------------------------------------------------------

def skip_path(home):
    return homemod.layout(home)["data"] / SKIP_NAME


def skipped(home):
    """The versions in <home>/data/update_skip.json, as a set."""
    doc = jsonfile.read_json(skip_path(home), max_bytes=MAX_STAGED_BYTES, kind=dict,
                             default=None, backup=True)
    rows = doc.get("versions") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return set()
    return {r.get("version") for r in rows
            if isinstance(r, dict) and homemod.is_version(r.get("version"))}


def record_skip(home, version, reason, now=None):
    """Add `version` to update_skip.json (one row per version, the newest
    SKIP_KEPT kept), written with one .bak and read back."""
    path = skip_path(home)
    doc = jsonfile.read_json(path, max_bytes=MAX_STAGED_BYTES, kind=dict,
                             default=None, backup=True)
    rows = doc.get("versions") if isinstance(doc, dict) else None
    rows = [r for r in rows if isinstance(r, dict) and homemod.is_version(r.get("version"))
            and r.get("version") != version] if isinstance(rows, list) else []
    rows.append({"version": version, "at": homemod.now_text(now), "reason": str(reason)[:120]})
    out = {"schema": SKIP_SCHEMA, "name": NAME, "versions": rows[-SKIP_KEPT:]}
    jsonfile.write_text(path, jsonfile.dumps(out), backup=True)
    if version not in skipped(home):
        raise SwitchFailed("update_skip.json did not read back")
    return path


# --- the report ---------------------------------------------------------------------

def report_path(home):
    return homemod.layout(home)["reports"] / REPORT_NAME


def add_line(home, line, action, status, version=None, came_from=None, now=None):
    """Append one path-free line to <home>/logs/reports/last-update.json
    ("lines", the last LINES_KEPT) and set its "switch" entry."""
    path = report_path(home)
    doc = jsonfile.read_json(path, max_bytes=MAX_REPORT_BYTES, kind=dict, default=None)
    if not isinstance(doc, dict):
        doc = {"schema": REPORT_SCHEMA, "kind": "update", "name": NAME}
    lines = doc.get("lines") if isinstance(doc.get("lines"), list) else []
    stamp = homemod.now_text(now)
    lines = [str(x) for x in lines] + [f"{stamp} {line}"]
    doc["lines"] = lines[-LINES_KEPT:]
    doc["switch"] = {"action": action, "status": status, "version": version,
                     "from": came_from, "at": stamp}
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write_text(path, jsonfile.dumps(doc), backup=False)
    return path


def _try_line(home, *args, **kw):
    try:
        add_line(home, *args, **kw)
    except (OSError, UnicodeEncodeError):
        pass


# --- is a core of this home running? -------------------------------------------------

def core_running(home):
    """True when a core or supervisor of THIS home is live, read only from
    its own files under <home>/data (decision 0010 proven-ours rule: the
    recorded pid is alive, its image is python and its recorded creation
    time matches; the supervisor's lock or recorded pid). No process list."""
    data = homemod.layout(home)["data"]
    from .. import keepalive as ka  # late: the no-op path imports neither
    from .. import procs
    if not (data / ka.HEARTBEAT_FILE).exists() and not (data / ka.STATE_FILE).exists() \
            and not (data / ka.LOCK_FILE).exists():
        return False
    if procs.core_pid(data):
        return True
    if (data / ka.STATE_FILE).exists() and procs.supervisor_pid(data):
        return True
    return procs.supervisor_locked(data)


# --- marker documents ------------------------------------------------------------------

def _runtimes_of(doc):
    return {k: doc[k] for k in RUNTIME_KEYS}


def _recorded_previous_runtimes(marker):
    rec = marker.get(PREVIOUS_RUNTIMES)
    if isinstance(rec, dict) and all(_plain(rec.get(k)) for k in RUNTIME_KEYS):
        return {k: rec[k] for k in RUNTIME_KEYS}
    return None


def _cached_runtimes(home, version):
    """The runtime folder names of `version` from its cached release.json
    (<home>/cache/downloads/<version>/), or None."""
    from . import payload  # late: only a rollback without a record needs it
    path = homemod.layout(home)["downloads"] / version / "release.json"
    try:
        pins = payload.pins_from_release(payload.read_release(path), version)
        return {k: payload.runtime_folder(k, pins[k]) for k in RUNTIME_KEYS}
    except Exception:  # noqa: BLE001 - any unreadable cache means unknown
        return None


def previous_runtimes(home, marker):
    """The runtime folder names the marker's previous version needs, or None
    when they are not known."""
    if not marker.get("previous"):
        return None
    return (_recorded_previous_runtimes(marker)
            or _cached_runtimes(home, marker["previous"]))


def _runtime_ready(home, runtimes):
    runtime = homemod.layout(home)["runtime"]
    return all(homemod._is_plain_dir(runtime / runtimes[k]) for k in RUNTIME_KEYS)


# --- bump and rollback ------------------------------------------------------------------

def bump_attempt(home, now=None):
    """start_attempts + 1 while pending_confirm is true, written and read
    back; returns the new count (0 when nothing is pending: no write)."""
    marker = homemod.read_marker(home)
    if marker is None:
        raise SwitchFailed("no valid marker")
    if not marker["pending_confirm"]:
        return 0
    doc = dict(marker)
    doc["start_attempts"] = int(marker["start_attempts"]) + 1
    doc["updated_at"] = homemod.now_text(now)
    back = homemod.write_marker(home, doc)
    return back["start_attempts"]


def _rewrite(home, version, runner, effect_root):
    res = shellmod.rewrite(home, version, runner=runner, effect_root=effect_root)
    return {k: res[k] for k in ("uninstall_script", "shortcuts", "uninstall_entry",
                                "logon_task")}


def rollback(home, reason="by hand", runner=None, effect_root=None, running=None,
             now=None, out=None):
    """Make `previous` the active version again. Returns (exit code, result).
    The version left lands in update_skip.json; one report line is added."""
    say = _say(out)
    result = {"action": "rollback", "status": FAILED, "version": None, "from": None,
              "reason": ""}
    home, refused = _checked(home, result, say, "rollback")
    if refused:
        return refused
    try:
        marker = homemod.read_marker(home)
        if marker is None:
            raise SwitchFailed("no valid marker")
        bad, prev = marker["version"], marker.get("previous")
        result["from"] = bad
        if not prev:
            raise SwitchFailed("no previous version to go back to")
        if (running or core_running)(home):
            result["status"], result["reason"] = BUSY, "a core of this home runs"
            say("rollback: a core of this home runs; stop it first")
            return EXIT_BUSY, result
        if not homemod._is_plain_dir(homemod.layout(home)["app"] / prev):
            raise SwitchFailed(f"no version folder for {prev}")
        runtimes = previous_runtimes(home, marker)
        if runtimes is None or not _runtime_ready(home, runtimes):
            current = _runtimes_of(marker)
            if not _runtime_ready(home, current):
                raise SwitchFailed(f"the runtimes of {prev} are not in place")
            runtimes = current
        record_skip(home, bad, reason, now)
        doc = {k: v for k, v in marker.items() if k != PREVIOUS_RUNTIMES}
        doc.update(version=prev, previous=None, channel=homemod.channel_of(prev),
                   pending_confirm=False, start_attempts=0,
                   updated_at=homemod.now_text(now), **runtimes)
        homemod.write_marker(home, doc)
        result["version"] = prev
        result["shell"] = _rewrite(home, prev, runner, effect_root)
        drop_staged(home, bad)
        result["status"], result["reason"] = ROLLED_BACK, str(reason)
    except (SwitchFailed, homemod.MarkerError, shellmod.ShellError, OSError,
            ValueError) as exc:
        result["reason"] = _reason(exc, home)
        _try_line(home, f"rollback failed: {result['reason']}", "rollback", FAILED,
                  result["version"], result["from"], now)
        say(f"rollback: failed: {result['reason']}")
        return EXIT_FAIL, result
    _try_line(home, f"rolled back from {result['from']} to {result['version']} "
                    f"({result['reason']}); {result['from']} will not be offered again",
              "rollback", ROLLED_BACK, result["version"], result["from"], now)
    say(f"rollback: {result['from']} to {result['version']}")
    return EXIT_SWITCHED, result


# --- apply -------------------------------------------------------------------------------

def _pick(home, marker, skip):
    """The newest staged document newer than the active version and not in
    update_skip.json; staged documents of older, equal or skipped versions
    are removed. Returns the document or None."""
    best = None
    active = homemod.version_key(marker["version"])
    for version in staged_versions(home):
        if homemod.version_key(version) <= active or version in skip:
            drop_staged(home, version)
            continue
        best = version
    return read_staged(home, best) if best is not None else None


def _check_staged(home, doc):
    """Problems that stop a switch to the staged version ([] when none)."""
    from . import payload  # late: the no-op path never needs it
    lay = homemod.layout(home)
    version = doc["version"]
    folder = lay["app"] / version
    if not homemod._is_plain_dir(folder):
        return [f"no version folder for {version}"]
    if not all(_plain(doc.get(k)) for k in RUNTIME_KEYS):
        return ["the staged file names no runtime folders"]
    if not _runtime_ready(home, doc):
        return [f"the runtimes of {version} are not in place"]
    want = (doc.get("hashes") or {}).get("manifest") if isinstance(doc.get("hashes"), dict) \
        else None
    if want:
        try:
            got = hashlib.sha256((folder / payload.MANIFEST_NAME).read_bytes()).hexdigest()
        except OSError:
            got = None
        if got != want:
            return ["MANIFEST.json differs from the staged one"]
    problems = payload.check_manifest(folder, ignore_bytecode=True)
    return [f"{version} does not match its MANIFEST.json"] if problems else []


def apply(home, now=None, if_due=True, runner=None, effect_root=None, running=None,
          out=None):
    """The launcher's step before a client start. Returns (exit code,
    result). EXIT_SWITCHED: the marker moved (switched or rolled back),
    relaunch from it; EXIT_OK: start as usual; EXIT_BUSY: a core of this
    home runs, nothing switched."""
    say = _say(out)
    running = running or core_running
    result = {"action": "apply", "status": FAILED, "version": None, "from": None,
              "reason": ""}
    home, refused = _checked(home, result, say, "apply-staged")
    if refused:
        return refused
    try:
        lay = homemod.layout(home)
        marker = homemod.read_marker(home)
        if marker is None:
            raise SwitchFailed("no valid marker")
        result["from"] = marker["version"]
        if marker["pending_confirm"]:
            return _pending(home, marker, result, runner, effect_root, running, now,
                            out, say)
        if not _listing(lay["staged"]):
            result["status"] = NOTHING
            return EXIT_OK, result
        doc = _pick(home, marker, skipped(home))
        if doc is None:
            result["status"] = NOTHING
            say("apply-staged: nothing staged")
            return EXIT_OK, result
        version = doc["version"]
        result["version"] = version
        due = _parse_time(doc.get("apply_after"))
        if if_due and (due is None or _now(now) < due):
            result["status"] = NOT_DUE
            result["apply_after"] = doc.get("apply_after")
            say(f"apply-staged: {version} applies after {doc.get('apply_after')}")
            return EXIT_OK, result
        if running(home):
            result["status"], result["reason"] = BUSY, "a core of this home runs"
            say("apply-staged: a core of this home runs; not switched")
            return EXIT_BUSY, result
        problems = _check_staged(home, doc)
        if problems:
            drop_staged(home, version)
            raise SwitchFailed(problems[0])
        _switch(home, marker, doc, result, runner, effect_root, now)
        for old in staged_versions(home):
            if homemod.version_key(old) <= homemod.version_key(version):
                drop_staged(home, old)
    except (SwitchFailed, homemod.MarkerError, shellmod.ShellError, OSError,
            ValueError) as exc:
        result["status"], result["reason"] = FAILED, _reason(exc, home)
        _try_line(home, f"apply failed: {result['reason']}", "apply", FAILED,
                  result["version"], result["from"], now)
        say(f"apply-staged: failed: {result['reason']}")
        return EXIT_FAIL, result
    result["status"] = SWITCHED
    _try_line(home, f"switched from {result['from']} to {result['version']}; "
                    "waiting for its first health answer",
              "apply", SWITCHED, result["version"], result["from"], now)
    say(f"apply-staged: switched {result['from']} to {result['version']}")
    return EXIT_SWITCHED, result


def _listing(folder):
    try:
        return bool(os.listdir(folder))
    except OSError:
        return False


def _pending(home, marker, result, runner, effect_root, running, now, out, say):
    """pending_confirm: count this start, or roll back at the second one."""
    result["version"] = marker["version"]
    if running(home):
        result["status"], result["reason"] = BUSY, "a core of this home runs"
        return EXIT_BUSY, result
    if int(marker["start_attempts"]) + 1 >= MAX_ATTEMPTS:
        code, res = rollback(home, reason="no health answer after "
                             f"{MAX_ATTEMPTS} starts", runner=runner,
                             effect_root=effect_root, running=lambda _h: False,
                             now=now, out=out)
        res["action"] = "apply"
        return code, res
    result["start_attempts"] = bump_attempt(home, now)
    result["status"] = STARTED
    say(f"apply-staged: start {result['start_attempts']} of {marker['version']} "
        "before its confirm")
    return EXIT_OK, result


def _switch(home, marker, doc, result, runner, effect_root, now):
    """Write the switched marker, rewrite the shell entries and read them
    back; on a shell failure the old marker and entries are put back."""
    version = doc["version"]
    new = dict(marker)
    new.update(version=version, previous=marker["version"],
               channel=homemod.channel_of(version),
               python=doc["python"], electron=doc["electron"],
               pending_confirm=True, start_attempts=0,
               updated_at=homemod.now_text(now))
    new[PREVIOUS_RUNTIMES] = _runtimes_of(marker)
    homemod.write_marker(home, new)
    try:
        result["shell"] = _rewrite(home, version, runner, effect_root)
    except shellmod.ShellError:
        homemod.write_marker(home, marker)
        try:
            _rewrite(home, marker["version"], runner, effect_root)
        except shellmod.ShellError:
            pass
        raise


# --- confirm -------------------------------------------------------------------------------

def default_health(home, timeout=HEALTH_TIMEOUT_S):
    """A health(home) callable: the /api/health document of THIS home's own
    core, or None. The port comes from <home>/data/core.alive and the token
    from <home>/data/token; the listener proves it is the core first
    (hello.verify, decision 0054), loopback only, no proxy."""
    return _core_doc(home, "/api/health", MAX_HEALTH_BYTES, timeout)


def default_idle(home, timeout=HEALTH_TIMEOUT_S):
    """REL-UPDATE-AUTO-IDLE (research 0066 F4): the game_idle flag of THIS
    home's own core snapshot (decision 0029: the log's staleness, never a
    process list): True or False, None when the core does not answer or
    the flag is not a boolean. Same proof and route rules as
    default_health."""
    doc = _core_doc(home, "/api/state", MAX_STATE_BYTES, timeout)
    idle = doc.get("game_idle") if isinstance(doc, dict) else None
    return idle if isinstance(idle, bool) else None


def _core_doc(home, route, max_bytes, timeout):
    """The JSON object a GET of `route` on this home's own core answers,
    or None (no heartbeat, no token, the hello proof failed, an error, a
    body over max_bytes or not an object)."""
    from .. import hello
    from .. import keepalive as ka
    data = homemod.layout(home)["data"]
    beat = ka.read_heartbeat(data / ka.HEARTBEAT_FILE)
    port = beat["port"] if beat else 0
    if not port:
        return None
    try:
        token = (data / "token").read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return None
    if not token or not hello.verify(port, token, opener=hello.NO_PROXY_OPENER,
                                     timeout=timeout):
        return None
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}{route}",
                                 headers={"X-AL-Token": token})
    try:
        with hello.NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            body = resp.read(max_bytes + 1)
        if len(body) > max_bytes:
            return None
        doc = json.loads(body.decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        hello.forget(port)
        return None
    return doc if isinstance(doc, dict) else None


def _answered(doc, version):
    if isinstance(doc, str):
        return doc == version
    return isinstance(doc, dict) and doc.get("version") == version


def cleanup(home, marker):
    """Remove the version folders that are neither `version`, `previous`
    nor staged, and the runtime folders none of them needs (only when the
    previous version's runtimes are known). Returns {"versions": [...],
    "runtimes": [...]} of the names removed."""
    lay = homemod.layout(home)
    staged = [d for d in (read_staged(home, v) for v in staged_versions(home)) if d]
    keep = {marker["version"], marker.get("previous")} | {d["version"] for d in staged}
    removed = {"versions": [], "runtimes": []}
    for name in homemod.version_dirs(home):
        if name not in keep and _remove_dir(lay["app"], name):
            removed["versions"].append(name)
    prev = previous_runtimes(home, marker) if marker.get("previous") else {}
    if prev is None:
        return removed
    need = set(_runtimes_of(marker).values()) | set(prev.values())
    for doc in staged:
        need |= {doc[k] for k in RUNTIME_KEYS if _plain(doc.get(k))}
    try:
        names = sorted(os.listdir(lay["runtime"]))
    except OSError:
        names = []
    for name in names:
        if name in need or not name.startswith(tuple(k + "-" for k in RUNTIME_KEYS)):
            continue
        if _remove_dir(lay["runtime"], name):
            removed["runtimes"].append(name)
    return removed


def _remove_dir(parent, name):
    """Remove parent/name when it is a plain folder (never a link or a
    junction: those are left alone). True when it is gone."""
    path = parent / name
    if not _plain(name) or not homemod._is_plain_dir(path):
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not os.path.lexists(path)


def confirm(home, health=None, wait_s=0.0, poll_s=CONFIRM_POLL_S, sleep=time.sleep,
            clock=time.monotonic, now=None, out=None):
    """Clear pending_confirm on the first health answer of the active
    version, then clean up. health(home) -> the /api/health document (or
    the version text) or None; polled every poll_s up to wait_s. Returns
    (exit code, result)."""
    say = _say(out)
    health = health or default_health
    result = {"action": "confirm", "status": FAILED, "version": None, "reason": ""}
    home, refused = _checked(home, result, say, "confirm")
    if refused:
        return refused
    try:
        marker = homemod.read_marker(home)
        if marker is None:
            raise SwitchFailed("no valid marker")
        version = result["version"] = marker["version"]
        if not marker["pending_confirm"]:
            result["status"] = CURRENT
            say(f"confirm: {version} needs no confirm")
            return EXIT_OK, result
        deadline = clock() + max(0.0, float(wait_s))
        while True:
            try:
                doc = health(home)
            except Exception:  # noqa: BLE001 - an unanswered probe waits
                doc = None
            if _answered(doc, version):
                break
            if clock() >= deadline:
                result["status"] = UNCONFIRMED
                result["reason"] = "no health answer from the new version"
                say(f"confirm: {version} gave no health answer")
                return EXIT_FAIL, result
            sleep(poll_s)
        marker = homemod.read_marker(home)
        if marker is None or marker["version"] != version:
            raise SwitchFailed("the marker changed while waiting")
        doc = dict(marker)
        doc.update(pending_confirm=False, start_attempts=0,
                   updated_at=homemod.now_text(now))
        marker = homemod.write_marker(home, doc)
        result["removed"] = cleanup(home, marker)
    except (SwitchFailed, homemod.MarkerError, OSError, ValueError) as exc:
        result["reason"] = _reason(exc, home)
        say(f"confirm: failed: {result['reason']}")
        return EXIT_FAIL, result
    result["status"] = CONFIRMED
    gone = len(result["removed"]["versions"]) + len(result["removed"]["runtimes"])
    _try_line(home, f"confirmed {version}; removed {gone} old folder(s)", "confirm",
              CONFIRMED, version, marker.get("previous"), now)
    say(f"confirm: {version} confirmed")
    return EXIT_OK, result


# --- shared ---------------------------------------------------------------------------------

def _checked(home, result, say, name):
    """(home as a checked Path, None), or (None, (EXIT_USAGE, result)) for a
    refused home (a Steam library or the game's folder, path text only)."""
    try:
        return homemod.check_home(home), None
    except paths.HomeRefused as exc:
        result["status"], result["reason"] = "refused", str(exc)
        say(f"{name}: home refused, {exc}")
        return None, (EXIT_USAGE, result)


def _say(out):
    return (lambda line: out.write(line + "\n")) if out is not None else (lambda line: None)


def _reason(exc, home=None):
    from . import install  # late: its path scrubber
    text = str(exc).strip() or exc.__class__.__name__
    return install.scrub(text, home)


def resolve_home(arg, environ=None):
    """--home, else AL_HOME, else the default player home."""
    from . import install
    return install.resolve_home(arg, environ)
