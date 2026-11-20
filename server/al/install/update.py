"""`installer update --zip FILE` (DEP-11, finding F-077 local half;
docs/plan/05-deployment.md "How an update swaps versions", steps 1 to 3).

stage_from_zip(home, zip, published_at=None, idle=None, ...) builds the
next version beside the running one from a local release zip, with no
network, in this fixed order:

1. gate: the work starts only on the player's click (clicked=True: the
   typed or pasted `update` line) or while the injected idle() callable
   answers True: the running core's own game_idle status (decision 0029),
   never a process list or a window. False, None or an error waits,
   polled every poll_s up to max_wait_s, then the run is deferred with
   nothing read or written but the report (selftest.wait_for_gate).
2. verify: release.json beside the zip names the version and both runtime
   pins; the zip is AshLight-<version>-app.zip and its bytes match their
   SHA256SUMS.txt line (install.verify); the version is newer than the
   marker's. Nothing is written before this passes.
3. runtimes: a runtime pin that differs from the marker's folder and is
   not placed yet is placed from the --runtime-dir folder of publisher
   zips (checked against the pin); without that folder the update stops
   here (the network half, DEP-17, fetches).
4. extract: the verified bytes, SHA256SUMS.txt and release.json cached in
   <home>/cache/downloads/<version>/ (repair re-extracts from there) and
   <home>/app/<version>/ laid out from the SAME bytes that were hashed
   (install.lay_out: .partial folder, MANIFEST.json check, one rename).
5. self-test: selftest.run of the new version (its children hidden at
   below-normal priority, gated like step 1).
6. stage: <home>/staged/<version>.json = {version, from, published_at,
   apply_after = published_at + 24 h, hashes, python, electron,
   staged_at}, written and read back; a staged document of an older
   version is superseded (removed: it is re-made from its zip).

Steps 2 to 6 run with this process at below-normal priority (restored
after). The marker is never written here: the switch is apply-staged
(REL-UPDATE-SWITCH). A failed self-test moves the new folder to
<home>/temp/failed-<version> and never reaches the marker, so it needs no
rollback. <home>/data is never opened. Every run writes ONE report,
<home>/logs/reports/last-update.json, which names no path; a failed
self-test's own report is folded into it.

Exit codes: 0 staged (or already staged), 1 failed or refused, 2 usage or
a refused home, 3 deferred (game_idle not true). No admin rights; no game
folder is read or written. Runs only in the installer's own process;
standard library only.
"""

import argparse
import contextlib
import hashlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import NAME, jsonfile, paths, pinfetch
from . import home as homemod
from . import install, payload
from . import selftest as selftestmod

REPORT_NAME = "last-update.json"
REPORT_SCHEMA = 1
STAGED_SCHEMA = 1
HOLD = timedelta(hours=24)        # apply_after = published_at + HOLD
STEPS = ("gate", "verify", "runtimes", "extract", "selftest", "stage")
BELOW_NORMAL = 0x00004000         # BELOW_NORMAL_PRIORITY_CLASS
MAX_STAGED_BYTES = 64 * 1024
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_DEFERRED = 3

STAGED, FAILED, DEFERRED, REFUSED = "staged", "failed", "deferred", "refused"


class UpdateFailed(Exception):
    """One step failed; .stage names it, the text is path-free."""

    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


# --- below-normal priority of this process ------------------------------------

def set_priority(cls):
    """Set this process's priority class; returns the previous class, or
    None off Windows or when the call fails (nothing changed then). Only
    the installer's own process is touched."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.GetPriorityClass.argtypes = [wintypes.HANDLE]
        k32.GetPriorityClass.restype = wintypes.DWORD
        k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.SetPriorityClass.restype = wintypes.BOOL
        me = k32.GetCurrentProcess()
        old = k32.GetPriorityClass(me)
        if not old or not k32.SetPriorityClass(me, int(cls)):
            return None
        return int(old)
    except (OSError, AttributeError, ValueError):
        return None


@contextlib.contextmanager
def below_normal(setter=None):
    """Run the block at below-normal priority, then restore the old class.
    setter(cls) -> previous class or None (default set_priority)."""
    setter = setter or set_priority
    old = setter(BELOW_NORMAL)
    try:
        yield old
    finally:
        if old is not None and old != BELOW_NORMAL:
            setter(old)


# --- times ---------------------------------------------------------------------------

def parse_time(text):
    """A UTC datetime from an ISO 8601 stamp ('...Z' or with an offset), or
    None for anything else."""
    if isinstance(text, datetime):
        return text if text.tzinfo else text.replace(tzinfo=timezone.utc)
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


def _now(now):
    when = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def apply_after(published_at):
    """published_at + 24 h as a stamp (the hold of decision 0065)."""
    return homemod.now_text(parse_time(published_at) + HOLD)


# --- the staged document -----------------------------------------------------------

def staged_path(home, version):
    return homemod.layout(home)["staged"] / f"{version}.json"


def report_path(home):
    return homemod.layout(home)["reports"] / REPORT_NAME


def read_staged(home, version):
    """<home>/staged/<version>.json as a dict, or None."""
    if not homemod.is_version(version):
        return None
    doc = jsonfile.read_json(staged_path(home, version), max_bytes=MAX_STAGED_BYTES,
                             kind=dict, default=None)
    if not isinstance(doc, dict) or doc.get("version") != version:
        return None
    return doc


def staged_versions(home):
    """The versions with a staged document, oldest first."""
    folder = homemod.layout(home)["staged"]
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = [n[:-5] for n in names
             if n.endswith(".json") and homemod.is_version(n[:-5])
             and (folder / n).is_file()]
    return sorted(found, key=homemod.version_key)


def write_staged(home, doc):
    """Write the staged document and read it back; returns its path."""
    path = staged_path(home, doc["version"])
    path.parent.mkdir(parents=True, exist_ok=True)
    text = jsonfile.dumps(doc)
    jsonfile.write_text(path, text, backup=False)
    back = read_staged(home, doc["version"])
    if back != doc:
        raise UpdateFailed("stage", "the staged file did not read back as written")
    return path


def supersede_older(home, version):
    """Remove the staged documents of versions older than `version` (our
    own small files, re-made from their zips). Returns their versions."""
    removed = []
    key = homemod.version_key(version)
    for old in staged_versions(home):
        if homemod.version_key(old) < key:
            try:
                staged_path(home, old).unlink()
                removed.append(old)
            except OSError:
                pass
    return removed


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _manifest_sha(home, version):
    path = homemod.layout(home)["app"] / version / payload.MANIFEST_NAME
    try:
        return _sha(path.read_bytes())
    except OSError:
        return None


# --- the steps -------------------------------------------------------------------------

def _active(home):
    marker = homemod.read_marker(home)
    if marker is None:
        raise UpdateFailed("verify", "no install to update; run the install line")
    return marker


def _check_newer(version, marker):
    if homemod.version_key(version) <= homemod.version_key(marker["version"]):
        raise UpdateFailed("verify", f"{version} is not newer than the active "
                                     f"{marker['version']}")


def runtime_folders(home, pins, marker, runtime_dir=None):
    """{python, electron}: the runtime folder names the new version needs.
    A pin whose folder differs from the marker's and is not placed yet is
    placed from runtime_dir; with no runtime_dir that is an UpdateFailed
    (no request: the local half never fetches). Returns (folders, placed)."""
    lay = homemod.layout(home)
    folders, placed = {}, []
    for name in pinfetch.RUNTIME_NAMES:
        pin = pins[name]
        folder = payload.runtime_folder(name, pin)
        folders[name] = folder
        if folder == marker[name] and (lay["runtime"] / folder).is_dir():
            continue
        if pinfetch.runtime_ready(name, pin, lay["runtime"] / folder):
            continue
        if runtime_dir is None:
            raise UpdateFailed("runtimes", f"the {name} pin changed; pass "
                                           "--runtime-dir with its publisher zip")
        payload.place_runtime(name, pin, home, source_dir=runtime_dir)
        placed.append(name)
    return folders, placed


def _already_staged(home, version, hashes):
    doc = read_staged(home, version)
    got = doc.get("hashes") if doc is not None else None
    if not isinstance(got, dict) or got.get("zip") != hashes["zip"]:
        return None
    folder = homemod.layout(home)["app"] / version
    if payload._is_link(folder) or payload.check_manifest(folder, ignore_bytecode=True):
        return None
    return doc


def _default_selftest(idle, clicked, spawn, poll_s, max_wait_s, sleep, clock):
    def run(home, version):
        return selftestmod.run(home, version, idle=idle, clicked=clicked,
                               spawn=spawn, poll_s=poll_s, max_wait_s=max_wait_s,
                               sleep=sleep, clock=clock)
    return run


def write_report(home, doc, now=None):
    """<home>/logs/reports/last-update.json (replaced on every run)."""
    out = dict(doc)
    out["at"] = homemod.now_text(now)
    path = report_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write_text(path, jsonfile.dumps(out), backup=False)
    return path


def stage_from_zip(home, zip, published_at=None, idle=None, clicked=False,
                   sums=None, release=None, runtime_dir=None, selftest=None,
                   spawn=None, priority=None, poll_s=selftestmod.POLL_S,
                   max_wait_s=selftestmod.MAX_WAIT_S, sleep=time.sleep,
                   clock=time.monotonic, now=None, out=None):
    """Stage the release of the local `zip` in `home`. Returns (exit code,
    report dict). published_at: the release's publish time (default: the
    'published_at' of release.json when it is a stamp, else now). idle():
    the core's game_idle status; clicked: the player's own act. selftest
    (home, version) -> selftest.Result, spawn (the self-test children) and
    priority (the class setter) are injection points; their defaults are
    the real ones."""
    say = (lambda line: out.write(line + "\n")) if out is not None else (lambda line: None)
    try:
        home = homemod.check_home(home)
    except paths.HomeRefused as exc:
        say(f"update: home refused, {exc}")
        return EXIT_USAGE, {"status": REFUSED, "stage": "home", "reason": str(exc)}
    zip_path = Path(zip)
    sums = Path(sums) if sums is not None else zip_path.parent / install.SUMS_NAME
    release = Path(release) if release is not None else \
        zip_path.parent / install.RELEASE_NAME
    selftest = selftest or _default_selftest(idle, clicked, spawn, poll_s,
                                             max_wait_s, sleep, clock)
    steps = {}
    report = {"schema": REPORT_SCHEMA, "kind": "update", "name": NAME,
              "from": None, "version": None, "status": FAILED, "stage": "",
              "reason": "", "steps": steps}
    try:
        marker = _active(home)
        report["from"] = marker["version"]
        go, waited = selftestmod.wait_for_gate(idle, clicked, poll_s, max_wait_s,
                                               sleep, clock)
        report["waited"] = waited
        if not go:
            steps["gate"] = "waiting"
            report["status"], report["stage"] = DEFERRED, "gate"
            report["reason"] = ("waiting for game_idle" if idle is not None
                                else "no idle signal and no click")
        else:
            steps["gate"] = "clicked" if clicked else "idle"
            with below_normal(priority):
                _work(home, zip_path, sums, release, runtime_dir, marker,
                      published_at, selftest, report, now, say)
    except UpdateFailed as exc:
        report["stage"], report["reason"] = exc.stage, install.scrub(exc.reason, home)
    except Exception as exc:  # noqa: BLE001 - every failure ends in the one report
        report["stage"] = report["stage"] or _current(steps)
        report["reason"] = install._reason(exc, home)
    try:
        write_report(home, report, now)
    except OSError as exc:
        say(f"update: report not written ({exc.__class__.__name__})")
    status = report["status"]
    if status == STAGED:
        say(f"update: staged {report['version']}, applies after "
            f"{report['apply_after']}")
        return EXIT_OK, report
    if status == DEFERRED:
        say(f"update: deferred at {report['stage']}: {report['reason']}")
        return EXIT_DEFERRED, report
    say(f"update: failed at {report['stage']}: {report['reason']}")
    return EXIT_FAIL, report


def _current(steps):
    """The step that was running: the first of STEPS not yet recorded."""
    for name in STEPS:
        if name not in steps:
            return name
    return STEPS[-1]


def _work(home, zip_path, sums, release, runtime_dir, marker, published_at,
          selftest, report, now, say):
    steps = report["steps"]
    version, data, sums_b, release_b, pins = install.verify(zip_path, sums, release)
    report["version"] = version
    _check_newer(version, marker)
    hashes = {"zip": _sha(data), "sums": _sha(sums_b), "release": _sha(release_b)}
    steps["verify"] = "ok"
    say(f"update: verify ok ({marker['version']} to {version})")

    done = _already_staged(home, version, hashes)
    if done is not None:
        for name in ("runtimes", "extract", "selftest", "stage"):
            steps[name] = "current"
        report.update(status=STAGED, stage="done",
                      published_at=done.get("published_at"),
                      apply_after=done.get("apply_after"))
        return

    folders, placed = runtime_folders(home, pins, marker, runtime_dir)
    steps["runtimes"] = "placed" if placed else "current"

    install.cache_release(home, version, data, sums_b, release_b)
    steps["extract"] = install.lay_out(home, version, data)
    say(f"update: extract {steps['extract']}")

    res = selftest(home, version)
    folded = install._fold_selftest(res)
    report["selftest"] = folded
    steps["selftest"] = folded["status"]
    if folded["status"] == selftestmod.DEFERRED:
        report["status"], report["stage"] = DEFERRED, "selftest"
        report["reason"] = folded["reason"] or "waiting for game_idle"
        return
    if folded["status"] != selftestmod.PASSED:
        raise UpdateFailed("selftest", f"{folded['stage'] or 'self-test'}: "
                                       f"{folded['reason'] or folded['status']}")
    say("update: self-test passed")

    when = _now(now)
    if published_at is None:
        doc = payload.read_release(release)
        published_at = doc.get("published_at")
    published = parse_time(published_at) or when
    hashes["manifest"] = _manifest_sha(home, version)
    staged = {"schema": STAGED_SCHEMA, "name": NAME, "version": version,
              "from": marker["version"],
              "published_at": homemod.now_text(published),
              "apply_after": apply_after(published),
              "hashes": hashes, "size": len(data),
              "python": folders["python"], "electron": folders["electron"],
              "staged_at": homemod.now_text(when)}
    write_staged(home, staged)
    report["superseded"] = supersede_older(home, version)
    steps["stage"] = "written"
    report.update(status=STAGED, stage="done", published_at=staged["published_at"],
                  apply_after=staged["apply_after"])


# --- the command ---------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install update",
        description="build, self-test and stage a newer AshLight release "
                    "from a local zip (no network); applied at a later start")
    p.add_argument("--zip", required=True, help="the app zip AshLight-<ver>-app.zip")
    p.add_argument("--sums", help="SHA256SUMS.txt (default: beside the zip)")
    p.add_argument("--release", help="release.json (default: beside the zip)")
    p.add_argument("--runtime-dir", help="a folder with the publisher zips of a "
                   "changed runtime pin")
    p.add_argument("--published-at", help="the release's publish time (ISO 8601; "
                   "default: release.json, else now)")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "%%LOCALAPPDATA%%\\Programs\\AshLight)")
    return p


def main(argv=None, environ=None, out=None):
    """The typed or pasted `update` line is the player's own act: a click
    (the game_idle gate is for the automatic callers)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    if args.published_at is not None and parse_time(args.published_at) is None:
        print("update: --published-at is not an ISO 8601 time", file=sys.stderr)
        return EXIT_USAGE
    home = install.resolve_home(args.home, environ)
    code, _report = stage_from_zip(home, args.zip, published_at=args.published_at,
                                   clicked=True, sums=args.sums,
                                   release=args.release,
                                   runtime_dir=args.runtime_dir,
                                   out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
