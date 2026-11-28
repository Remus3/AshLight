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

The network half (DEP-17, F-077): stage_from_release(home, release_doc,
...) and `installer update --yes`. release_doc is the trimmed
releases/latest answer that server/al/updates.py (DEP-16) cached, so
there is still ONE releases read per 24 h; this module never asks the
API itself. In order:

1. web data: the home's data/local.json must hold web_data true and an
   acknowledged wording (web_data_ack, updates.ack_ok); else nothing is
   requested.
2. the answer: a tag that is a newer X.Y.Z release than the marker's (a
   pre-release, an older or equal version, or a version
   data/update_skip.json still holds (switch.skipped: a "no health answer"
   skip is offered once more after 7 days) is not staged: nothing is
   requested); the
   assets AshLight-<version>-app.zip, SHA256SUMS.txt and release.json,
   each with a size and a https://github.com/<owner>/<repo>/releases/
   download/<tag>/<name> url (the cached repository when it names one).
   A version already staged from the same zip digest is current with no
   request.
3. gate: as step 1 above (a click, or game_idle true).
4. download, at below-normal priority, into memory through
   payload.installer_stream: only RELEASE_HOSTS (api.github.com,
   github.com and the two GitHub asset hosts; https, exact host on every
   redirect hop), the installer User-Agent, no cookie. Each asset is
   checked against its API size and, when the answer has one, its API
   digest ("sha256:<hex>"); the zip and release.json are then checked
   against their SHA256SUMS.txt lines (two hash sources). An answer
   without a digest field is recorded (report "digest": "absent") and
   SHA256SUMS.txt alone decides. Any mismatch stages nothing.
5. then steps 3 to 6 above from the verified bytes; a runtime pin that
   changed is fetched here, in the installer process, over the pinned
   publisher hosts (payload.place_runtime, checked against the new pin).

The Sigstore attestation is NOT verified here: the standard library
cannot (decision 0065; SECURITY.md says so). The running core never
fetches a release or a runtime.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import NAME, jsonfile, paths, pinfetch, updates
from . import home as homemod
from . import install, payload
from . import selftest as selftestmod
from . import switch as switchmod

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
CURRENT, SKIPPED = "current", "skipped"   # release path: nothing to do (exit 0)

# --- the network half (DEP-17) -----------------------------------------------------
RELEASE_HOSTS = (updates.API_HOST, "github.com",
                 "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com")
RELEASE_STEPS = ("web_data", "release", "gate", "download", "verify", "runtimes",
                 "extract", "selftest", "stage")
ACK_KEY = "web_data_ack"          # core.ACK_KEY: the acknowledged wording version
CACHE_PARTS = ("updates", updates.STATE_NAME)   # under <home>/cache (the core's cache)
SUMS_CAP = payload.MAX_SUMS_BYTES
RELEASE_CAP = payload.MAX_RELEASE_BYTES
LOCAL_MAX_BYTES = 256 * 1024
_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_ASSET_URL = re.compile(r"^https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})"
                        r"/releases/download/([^/?#]{1,64})/([^/?#]{1,200})$")


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


def runtime_folders(home, pins, marker, runtime_dir=None, network=False,
                    fetch=None, opener=None):
    """{python, electron}: the runtime folder names the new version needs.
    A pin whose folder differs from the marker's and is not placed yet is
    placed from runtime_dir; with no runtime_dir and network False that is
    an UpdateFailed (no request: the local half never fetches). network
    True (the release path, DEP-17) fetches it in this process through
    payload.place_runtime (the pinned publisher hosts, the installer
    User-Agent, checked against the new pin; fetch / opener are for
    tests). Returns (folders, placed)."""
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
        if runtime_dir is not None:
            payload.place_runtime(name, pin, home, source_dir=runtime_dir)
        elif network:
            payload.place_runtime(name, pin, home, fetch=fetch, opener=opener)
        else:
            raise UpdateFailed("runtimes", f"the {name} pin changed; pass "
                                           "--runtime-dir with its publisher zip")
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
    def run(home, version, electron=None):
        return selftestmod.run(home, version, idle=idle, clicked=clicked,
                               spawn=spawn, poll_s=poll_s, max_wait_s=max_wait_s,
                               sleep=sleep, clock=clock, electron=electron)
    run.takes_electron = True  # REL-SELFTEST-CLIENT: the new Electron is checked too
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


def _current(steps, order=STEPS):
    """The step that was running: the first of `order` not yet recorded."""
    for name in order:
        if name not in steps:
            return name
    return order[-1]


def _work(home, zip_path, sums, release, runtime_dir, marker, published_at,
          selftest, report, now, say):
    version, data, sums_b, release_b, pins = install.verify(zip_path, sums, release)
    report["version"] = version
    _check_newer(version, marker)
    if published_at is None:
        published_at = payload.read_release(release).get("published_at")
    _stage_verified(home, version, data, sums_b, release_b, pins, marker,
                    published_at, selftest, report, now, say,
                    lambda: runtime_folders(home, pins, marker, runtime_dir))


def _stage_verified(home, version, data, sums_b, release_b, pins, marker,
                    published_at, selftest, report, now, say, runtimes):
    """Steps 3 to 6 from bytes that passed every check. runtimes() ->
    (folders, placed): the local half places from --runtime-dir, the
    release path fetches."""
    steps = report["steps"]
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

    folders, placed = runtimes()
    steps["runtimes"] = "placed" if placed else "current"

    install.cache_release(home, version, data, sums_b, release_b)
    steps["extract"] = install.lay_out(home, version, data)
    say(f"update: extract {steps['extract']}")

    electron = homemod.layout(home)["runtime"] / folders["electron"] / paths.ELECTRON_EXE
    res = selftestmod.call(selftest, home, version, electron)
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


# --- the release path (DEP-17) ----------------------------------------------------------

def web_data_allowed(home):
    """True when <home>/data/local.json holds web_data true and an
    acknowledged opt-in wording that covers updates.WORDING_VERSION
    (decision 0013, ruling Q-21). Missing or unreadable: False."""
    doc = jsonfile.read_json(homemod.layout(home)["data"] / "local.json",
                             max_bytes=LOCAL_MAX_BYTES, kind=dict, default=None)
    if not isinstance(doc, dict):
        return False
    return doc.get("web_data") is True and updates.ack_ok(doc.get(ACK_KEY))


def cache_path(home):
    """<home>/cache/updates/update_check.json: the answer the core's daily
    check (server/al/updates.py) keeps in an installed copy."""
    return homemod.layout(home)["cache"].joinpath(*CACHE_PARTS)


def read_cached_release(path):
    """(release answer, repository) from an update_check.json, or
    (None, '') when it is missing, unreadable or holds no answer."""
    doc = jsonfile.read_json(path, max_bytes=updates.STATE_MAX_BYTES, kind=dict,
                             default=None)
    if not isinstance(doc, dict):
        return None, ""
    latest = doc.get("latest")
    return (latest if isinstance(latest, dict) else None), updates.clean_repo(doc.get("repo"))


def release_fetch(opener=None, version=None):
    """fetch(url, max_bytes) for the release assets: payload.installer_stream
    over RELEASE_HOSTS only (https, exact host on every redirect hop), the
    installer User-Agent, no cookie. `opener` is for tests only."""
    def fetch(url, max_bytes):
        return payload.installer_stream(url, max_bytes, version=version,
                                        opener=opener, hosts=RELEASE_HOSTS)
    return fetch


def _asset_names(version):
    return (install.RELEASE_NAME, install.SUMS_NAME, install.app_zip_name(version))


def check_release(release_doc, repo=""):
    """{version, tag, prerelease, published_at, assets, digest, digests}
    from a cached releases/latest answer, checked before anything is
    requested; assets maps each needed name to {size, digest (hex or
    None), url} (empty for a pre-release, which is never staged). Raises
    UpdateFailed('release', ...) for an unusable answer."""
    if not isinstance(release_doc, dict):
        raise UpdateFailed("release", "no cached release answer; the daily "
                                      "update check has not run yet")
    tag = release_doc.get("tag")
    parsed = updates.parse_version(tag) if isinstance(tag, str) else None
    if parsed is None or not tag.startswith("v") or not homemod.is_version(tag[1:]):
        raise UpdateFailed("release", "the release tag is not v<version>")
    version = tag[1:]
    out = {"version": version, "tag": tag,
           "prerelease": bool(parsed[3]) or release_doc.get("prerelease") is True,
           "published_at": release_doc.get("published_at")
           if parse_time(release_doc.get("published_at")) else None,
           "assets": {}, "digest": None, "digests": {}}
    if out["prerelease"]:
        return out  # never staged: its assets are not looked at
    found = {}
    for asset in release_doc.get("assets") or []:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str):
            found.setdefault(asset["name"], asset)
    caps = {install.RELEASE_NAME: RELEASE_CAP, install.SUMS_NAME: SUMS_CAP,
            install.app_zip_name(version): payload.MAX_APP_ZIP_BYTES}
    for name in _asset_names(version):
        asset = found.get(name)
        if asset is None:
            raise UpdateFailed("release", f"the release has no {name}")
        size = asset.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise UpdateFailed("release", f"{name}: the release lists no size")
        if size > caps[name]:
            raise UpdateFailed("release", f"{name}: {size} bytes is over the "
                                          f"{caps[name]} byte cap")
        url = asset.get("url")
        m = _ASSET_URL.match(url) if isinstance(url, str) else None
        if m is None or m.group(3) != tag or m.group(4) != name or \
                (repo and f"{m.group(1)}/{m.group(2)}".casefold() != repo.casefold()):
            raise UpdateFailed("release", f"{name}: the download address is not "
                                          "this release's GitHub asset")
        digest = asset.get("digest")
        if digest is not None:
            dm = _DIGEST.match(digest.lower()) if isinstance(digest, str) else None
            if dm is None:
                raise UpdateFailed("release", f"{name}: the release digest is "
                                              "not a sha256 digest")
            digest = dm.group(1)
        out["assets"][name] = {"size": size, "digest": digest, "url": url}
    have = [a["digest"] is not None for a in out["assets"].values()]
    out["digest"] = "checked" if all(have) else ("absent" if not any(have) else "partial")
    out["digests"] = {name: "checked" if a["digest"] is not None else "absent"
                      for name, a in out["assets"].items()}
    return out


def _staged_current(home, rel):
    """The staged document when this release is already staged from the
    same zip (its API digest, or its size when the answer has none) and
    its folder still matches MANIFEST.json; else None."""
    version = rel["version"]
    doc = read_staged(home, version)
    if doc is None:
        return None
    asset = rel["assets"][install.app_zip_name(version)]
    hashes = doc.get("hashes") if isinstance(doc.get("hashes"), dict) else {}
    if asset["digest"] is not None and hashes.get("zip") != asset["digest"]:
        return None
    if doc.get("size") != asset["size"]:
        return None
    folder = homemod.layout(home)["app"] / version
    if payload._is_link(folder) or payload.check_manifest(folder, ignore_bytecode=True):
        return None
    return doc


def _download(fetch, name, asset):
    """The asset's bytes, checked against its API size and (when the
    answer has one) its API digest; UpdateFailed('verify') otherwise."""
    parts, got = [], 0
    try:
        for block in fetch(asset["url"], asset["size"]):
            got += len(block)
            if got > asset["size"]:
                raise UpdateFailed("verify", f"{name}: larger than the release lists")
            parts.append(block)
    except pinfetch.HashMismatch as exc:
        raise UpdateFailed("verify", f"{name}: {exc}") from None
    data = b"".join(parts)
    if len(data) != asset["size"]:
        raise UpdateFailed("verify", f"{name}: {len(data)} bytes, the release "
                                     f"lists {asset['size']}")
    if asset["digest"] is not None and _sha(data) != asset["digest"]:
        raise UpdateFailed("verify", f"{name}: SHA-256 differs from the release digest")
    return data


def _verify_release(version, data, sums_b, release_b):
    """(release.json document, runtime pins) after the SHA256SUMS.txt
    checks of the zip and release.json; UpdateFailed('verify') otherwise."""
    try:
        doc = json.loads(release_b.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise UpdateFailed("verify", "release.json unreadable") from None
    if not isinstance(doc, dict) or doc.get("version") != version:
        raise UpdateFailed("verify", f"release.json is not for {version}")
    if doc.get("name") not in (None, NAME):
        raise UpdateFailed("verify", f"release.json is not for {NAME}")
    try:
        pins = payload.pins_from_release(doc, version)
        payload.check_zip_bytes(install.app_zip_name(version), data, sums_b)
        listed = payload.parse_sums(sums_b)
    except (pinfetch.PinError, pinfetch.HashMismatch, payload.PayloadError) as exc:
        raise UpdateFailed("verify", f"{exc.__class__.__name__}: {exc}") from None
    if install.RELEASE_NAME not in listed:
        raise UpdateFailed("verify", "SHA256SUMS.txt has no line for release.json")
    if listed[install.RELEASE_NAME] != _sha(release_b):
        raise UpdateFailed("verify", "release.json: SHA-256 differs from SHA256SUMS.txt")
    return doc, pins


def _release_work(home, rel, marker, fetch, opener, runtime_fetch, selftest,
                  report, now, say):
    steps = report["steps"]
    version = rel["version"]
    fetch = fetch or release_fetch(opener=opener)
    got = {name: _download(fetch, name, rel["assets"][name])
           for name in _asset_names(version)}
    steps["download"] = "ok"
    say(f"update: download ok ({version})")
    zip_name = install.app_zip_name(version)
    doc, pins = _verify_release(version, got[zip_name], got[install.SUMS_NAME],
                                got[install.RELEASE_NAME])
    published_at = rel["published_at"] or doc.get("published_at")
    _stage_verified(home, version, got[zip_name], got[install.SUMS_NAME],
                    got[install.RELEASE_NAME], pins, marker, published_at,
                    selftest, report, now, say,
                    lambda: runtime_folders(home, pins, marker, network=True,
                                            fetch=runtime_fetch, opener=opener))


def stage_from_release(home, release_doc, repo="", fetch=None, opener=None,
                       runtime_fetch=None, idle=None, clicked=False, allowed=None,
                       selftest=None, spawn=None, priority=None,
                       poll_s=selftestmod.POLL_S, max_wait_s=selftestmod.MAX_WAIT_S,
                       sleep=time.sleep, clock=time.monotonic, now=None, out=None):
    """Download, verify and stage the release of the cached releases/latest
    answer `release_doc` (server/al/updates.py's trimmed shape) in `home`.
    Returns (exit code, report dict).

    repo: '<owner>/<name>' the answer was read for ('' skips that check).
    allowed: the web-data gate (bool or callable; None reads the home's
    data/local.json). idle() / clicked: the gate of the download, as in
    stage_from_zip. fetch(url, max_bytes) (the release assets), opener (the
    request opener of both default fetches), runtime_fetch, selftest, spawn
    and priority are injection points; their defaults are the real ones.
    Exit 0 also when there is nothing to stage (status 'current' or
    'skipped'); nothing is requested then."""
    say = (lambda line: out.write(line + "\n")) if out is not None else (lambda line: None)
    try:
        home = homemod.check_home(home)
    except paths.HomeRefused as exc:
        say(f"update: home refused, {exc}")
        return EXIT_USAGE, {"status": REFUSED, "stage": "home", "reason": str(exc)}
    selftest = selftest or _default_selftest(idle, clicked, spawn, poll_s,
                                             max_wait_s, sleep, clock)
    steps = {}
    report = {"schema": REPORT_SCHEMA, "kind": "update", "name": NAME,
              "source": "release", "from": None, "version": None,
              "status": FAILED, "stage": "", "reason": "", "steps": steps}
    try:
        marker = _active(home)
        report["from"] = marker["version"]
        if allowed is None:
            ok = web_data_allowed(home)
        else:
            ok = bool(allowed() if callable(allowed) else allowed)
        if not ok:
            raise UpdateFailed("web_data", "web data is off or its update wording "
                                           "is not acknowledged; nothing was requested")
        steps["web_data"] = "on"
        rel = check_release(release_doc, repo)
        version = rel["version"]
        report.update(version=version, digest=rel["digest"], digests=rel["digests"])
        if rel["prerelease"]:
            report.update(status=SKIPPED, stage="release",
                          reason="a pre-release is never staged")
        elif homemod.version_key(version) <= homemod.version_key(marker["version"]):
            report.update(status=CURRENT, stage="release",
                          reason=f"{version} is not newer than the active "
                                 f"{marker['version']}")
        elif version in switchmod.skipped(home, now):
            report.update(status=SKIPPED, stage="release",
                          reason=f"{version} was rolled back and is not staged again")
        else:
            steps["release"] = "ok"
            done = _staged_current(home, rel)
            if done is not None:
                for name in ("gate", "download", "verify", "runtimes", "extract",
                             "selftest", "stage"):
                    steps[name] = "current"
                report.update(status=STAGED, stage="done",
                              published_at=done.get("published_at"),
                              apply_after=done.get("apply_after"))
            else:
                _release_gate(home, rel, marker, fetch, opener, runtime_fetch,
                              idle, clicked, selftest, priority, poll_s,
                              max_wait_s, sleep, clock, report, now, say)
    except UpdateFailed as exc:
        report["stage"], report["reason"] = exc.stage, install.scrub(exc.reason, home)
    except Exception as exc:  # noqa: BLE001 - every failure ends in the one report
        report["stage"] = report["stage"] or _current(steps, RELEASE_STEPS)
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
    if status in (CURRENT, SKIPPED):
        say(f"update: nothing to stage: {report['reason']}")
        return EXIT_OK, report
    if status == DEFERRED:
        say(f"update: deferred at {report['stage']}: {report['reason']}")
        return EXIT_DEFERRED, report
    say(f"update: failed at {report['stage']}: {report['reason']}")
    return EXIT_FAIL, report


def _release_gate(home, rel, marker, fetch, opener, runtime_fetch, idle, clicked,
                  selftest, priority, poll_s, max_wait_s, sleep, clock, report,
                  now, say):
    """The click / game_idle gate, then the download and the rest at
    below-normal priority."""
    steps = report["steps"]
    go, waited = selftestmod.wait_for_gate(idle, clicked, poll_s, max_wait_s,
                                           sleep, clock)
    report["waited"] = waited
    if not go:
        steps["gate"] = "waiting"
        report["status"], report["stage"] = DEFERRED, "gate"
        report["reason"] = ("waiting for game_idle" if idle is not None
                            else "no idle signal and no click")
        return
    steps["gate"] = "clicked" if clicked else "idle"
    with below_normal(priority):
        _release_work(home, rel, marker, fetch, opener, runtime_fetch, selftest,
                      report, now, say)


# --- the command ---------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install update",
        description="build, self-test and stage a newer AshLight release, "
                    "from a local zip (no network) or, with --yes, downloaded "
                    "from the release the daily update check found; applied "
                    "at a later start")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", help="the app zip AshLight-<ver>-app.zip")
    src.add_argument("--yes", action="store_true",
                     help="download, verify and stage the newer release of the "
                          "cached update check (web data on and acknowledged)")
    p.add_argument("--release-cache", help="the update check answer (default: "
                   "<home>\\cache\\updates\\update_check.json)")
    p.add_argument("--sums", help="SHA256SUMS.txt (default: beside the zip)")
    p.add_argument("--release", help="release.json (default: beside the zip)")
    p.add_argument("--runtime-dir", help="a folder with the publisher zips of a "
                   "changed runtime pin")
    p.add_argument("--published-at", help="the release's publish time (ISO 8601; "
                   "default: release.json, else now)")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "%%LOCALAPPDATA%%\\Programs\\AshLight)")
    return p


def main(argv=None, environ=None, out=None, opener=None):
    """The typed or pasted `update` line is the player's own act: a click
    (the game_idle gate is for the automatic callers). `opener` is for
    tests only (the --yes downloads)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    if args.yes:
        if any(v is not None for v in (args.sums, args.release, args.runtime_dir,
                                       args.published_at)):
            print("update: --yes takes only --home and --release-cache",
                  file=sys.stderr)
            return EXIT_USAGE
        home = install.resolve_home(args.home, environ)
        try:
            homemod.check_home(home)
        except paths.HomeRefused:
            release_doc, repo = None, ""   # refused below; nothing read there
        else:
            cache = Path(args.release_cache) if args.release_cache else cache_path(home)
            release_doc, repo = read_cached_release(cache)
        code, _report = stage_from_release(home, release_doc, repo=repo,
                                           clicked=True, opener=opener,
                                           out=out or sys.stdout)
        return code
    if args.release_cache is not None:
        print("update: --release-cache needs --yes", file=sys.stderr)
        return EXIT_USAGE
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
