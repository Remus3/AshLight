"""`installer install` (REL-INSTALL-CMD, finding F-050, DEP-09;
docs/plan/05-deployment.md Design points 3 to 6, 13 to 15, "Installed-mode
layout" and "Repair").

run(zip, home, runtime_dir=None, start=True) installs one release into a
home, in this fixed order:

1. verify: release.json (beside the zip unless given) names the version
   and both runtime pins (each checked, nothing requested); the zip is
   named AshLight-<version>-app.zip and its bytes match their
   SHA256SUMS.txt line. Nothing is written before this passes.
2. extract: the home layout (home.make_layout, <home>/data private), the
   verified bytes, SHA256SUMS.txt and release.json cached in
   <home>/cache/downloads/<version>/ (repair re-extracts from there), then
   <home>/app/<version>/ laid out from the SAME bytes that were hashed. A
   version folder that exists and differs from its manifest is replaced
   whole (repair.reextract), never edited in place.
3. runtimes: both hash-pinned runtimes, from the -RuntimeDir folder or the
   installer fetch (payload.place_runtimes; the player's own act).
4. config: <home>/data/local.json, written once (firstrun; web data off,
   no Client.txt consent: both stay the player's clicks on the first
   window).
5. self-test: the new version proves itself (selftest.run, clicked: the
   pasted line is the player's click). Skipped for the version the marker
   already names (its bytes passed before; a failure would move the
   active folder away).
6. marker: written (first install), switched (another version was
   active; previous, pending_confirm and start_attempts set) or kept.
7. shell entries: shortcuts, uninstall entry, uninstall.ps1 and the
   opt-in logon task (shell.rewrite, every effect through one runner).
8. start: the client (the shortcut's own command line), unless
   start=False (-NoStart).

Any failure before step 6 leaves the marker as it was (no marker on a
first install). Every run writes ONE report,
<home>/logs/reports/last-install.json, which names no path; a failed
self-test's own report is folded into it. A home in a Steam library or
the game's folder is refused before anything is written.

No admin rights are asked for; every location is per-user. No game folder is
read or written. Runs only in the installer's own process; standard
library only.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from .. import NAME, jsonfile, paths
from . import firstrun, payload, repair, shell
from . import home as homemod
from . import selftest as selftestmod

REPORT_NAME = "last-install.json"
REPORT_SCHEMA = 1
SUMS_NAME = "SHA256SUMS.txt"
RELEASE_NAME = "release.json"
STEPS = ("verify", "extract", "runtimes", "config", "selftest", "marker",
         "shell", "start")
CLIENT_ARG = shell.CLIENT_ARG
# the caller's overrides never reach the client the installer starts
DROP_ENV = ("AL_RUNTIME_DIR", "AL_SIDECAR_ROOT", "AL_PORT", "AL_DEV",
            "AL_TC_PINS_FILE", "AL_HOT_RELOAD", "NODE_OPTIONS",
            "ELECTRON_RUN_AS_NODE", "PYTHONPATH", "PYTHONHOME",
            "PYTHONSTARTUP")
DETACHED = 0x00000008      # DETACHED_PROCESS
NEW_GROUP = 0x00000200     # CREATE_NEW_PROCESS_GROUP

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

_ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?<![\w.\-])/(?=[^\s/]+/))[^\s'\"]*")


class InstallFailed(Exception):
    """One step failed; .stage names it, the text is path-free."""

    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


def app_zip_name(version):
    """AshLight-<version>-app.zip (tools/rel_build.py zip_name)."""
    return f"{NAME}-{version}-app.zip"


def downloads_dir(home, version):
    """<home>/cache/downloads/<version>/: the cached release files."""
    return homemod.layout(home)["downloads"] / version


def report_path(home):
    return homemod.layout(home)["reports"] / REPORT_NAME


def scrub(text, home=None):
    """A reason text with every absolute path replaced by '<path>'."""
    text = str(text)
    if home is not None:
        for form in {str(home), str(home).replace("\\", "/")}:
            text = text.replace(form, "<home>")
    return _ABS_PATH.sub("<path>", text)[:300]


def _reason(exc, home):
    text = str(exc).strip() or exc.__class__.__name__
    return scrub(f"{exc.__class__.__name__}: {text}", home)


def write_report(home, doc, now=None):
    """<home>/logs/reports/last-install.json (replaced on every run)."""
    out = dict(doc)
    out["at"] = homemod.now_text(now)
    path = report_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write_text(path, jsonfile.dumps(out), backup=False)
    return path


# --- step 1: verify -------------------------------------------------------------

def verify(zip_path, sums_path, release_path):
    """(version, zip bytes, sums bytes, release bytes, runtime pins) after
    every check; raises on any failure. Writes nothing."""
    doc = payload.read_release(release_path)
    version = doc.get("version")
    if not homemod.is_version(version):
        raise payload.PayloadError("release.json names no X.Y.Z version")
    if doc.get("name") not in (None, NAME):
        raise payload.PayloadError(f"release.json is not for {NAME}")
    pins = payload.pins_from_release(doc, version)
    name, data = payload._zip_bytes(zip_path)
    if name != app_zip_name(version):
        raise payload.PayloadError(f"the app zip is not named {app_zip_name(version)}")
    sums = payload._read_capped(sums_path, payload.MAX_SUMS_BYTES, SUMS_NAME)
    payload.check_zip_bytes(name, data, sums)
    release = payload._read_capped(release_path, payload.MAX_RELEASE_BYTES, RELEASE_NAME)
    return version, data, sums, release, pins


def cache_release(home, version, data, sums, release):
    """Keep the verified bytes for repair: <home>/cache/downloads/<version>/
    {app zip, SHA256SUMS.txt, release.json}; an equal file is left alone."""
    folder = downloads_dir(home, version)
    folder.mkdir(parents=True, exist_ok=True)
    for fname, body in ((app_zip_name(version), data), (SUMS_NAME, sums),
                        (RELEASE_NAME, release)):
        dest = folder / fname
        try:
            if dest.is_file() and dest.read_bytes() == body:
                continue
        except OSError:
            pass
        jsonfile.write_bytes(dest, body)
    return folder


# --- step 2: extract ------------------------------------------------------------------

def lay_out(home, version, data):
    """'laid out', 'current' (an identical folder) or 'restored' (a
    differing folder replaced whole from the verified bytes)."""
    target = homemod.layout(home)["app"] / version
    if os.path.lexists(target):
        if payload._is_link(target) or payload.check_manifest(target, ignore_bytecode=True):
            repair.reextract(home, version, data)
            return "restored"
        payload.extract(data, home, version)
        return "current"
    payload.extract(data, home, version)
    return "laid out"


# --- step 6: marker -------------------------------------------------------------------

def set_marker(home, version, folders, now=None):
    """('written' | 'switched' | 'updated' | 'current', marker)."""
    doc = homemod.read_marker(home)
    if doc is None:
        new = homemod.new_marker(version, folders["python"], folders["electron"], now=now)
        return "written", homemod.write_marker(home, new)
    if doc["version"] != version:
        return "switched", homemod.switch_marker(
            home, version, python=folders["python"], electron=folders["electron"],
            now=now)
    if doc["python"] == folders["python"] and doc["electron"] == folders["electron"]:
        return "current", doc
    doc = dict(doc)
    doc["python"], doc["electron"] = folders["python"], folders["electron"]
    doc["updated_at"] = homemod.now_text(now)
    return "updated", homemod.write_marker(home, doc)


# --- step 8: the client start ----------------------------------------------------------

def client_command(home, marker):
    """[electron.exe, <app folder>, --client]: the shortcut's command line."""
    lay = homemod.layout(home)
    electron = lay["runtime"] / marker["electron"] / paths.ELECTRON_EXE
    app_dir = lay["app"] / marker["version"] / "app"
    return [str(electron), str(app_dir), CLIENT_ARG]


def client_env(home, environ=None):
    """The caller's environment minus DROP_ENV, plus AL_HOME = home."""
    env = dict(os.environ if environ is None else environ)
    for key in list(env):
        if key.upper() in DROP_ENV:
            del env[key]
    env[paths.HOME_ENV] = str(home)
    return env


def start_flags():
    return (DETACHED | NEW_GROUP) if os.name == "nt" else 0


def start_client(home, marker, spawn=None, environ=None):
    """Start the client detached from the installer; returns the child."""
    cmd = client_command(home, marker)
    if not Path(cmd[0]).is_file():
        raise InstallFailed("start", "the client runtime has no electron.exe")
    spawn = spawn or subprocess.Popen
    return spawn(cmd, cwd=cmd[1], env=client_env(home, environ),
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True,
                 creationflags=start_flags())


# --- the self-test fold ---------------------------------------------------------------

def _fold_selftest(res):
    """The self-test result as a dict; its own report file is read into it
    and removed, so last-install.json stays the one report."""
    out = {"status": res.status, "stage": res.stage, "reason": res.reason,
           "exit_code": res.exit_code, "moved": res.moved}
    rpt = getattr(res, "report", None)
    if rpt is not None:
        doc = jsonfile.read_json(rpt, max_bytes=64 * 1024, kind=dict, default=None)
        if isinstance(doc, dict):
            out["report"] = doc
        try:
            Path(rpt).unlink()
        except OSError:
            pass
    return out


def _default_selftest(home, version):
    return selftestmod.run(home, version, clicked=True)


# --- the run --------------------------------------------------------------------------------

def run(zip, home, runtime_dir=None, start=True, sums=None, release=None,
        selftest=None, runner=None, spawn=None, private=None, effect_root=None,
        opener=None, environ=None, now=None, out=None):
    """Install the release of `zip` into `home`. Returns (exit code, report
    dict). sums / release default to SHA256SUMS.txt / release.json beside
    the zip. selftest(home, version) -> selftest.Result, runner (shell),
    spawn (the client start), private (the data ACL) and opener (runtime
    fetch) are injection points; their defaults are the real ones."""
    say = (lambda line: out.write(line + "\n")) if out is not None else (lambda line: None)
    try:
        home = homemod.check_home(home)
    except paths.HomeRefused as exc:
        say(f"install: home refused, {exc}")
        return EXIT_USAGE, {"status": "refused", "stage": "home", "reason": str(exc)}
    zip_path = Path(zip)
    sums = Path(sums) if sums is not None else zip_path.parent / SUMS_NAME
    release = Path(release) if release is not None else zip_path.parent / RELEASE_NAME
    selftest = selftest or _default_selftest
    steps = {}
    report = {"schema": REPORT_SCHEMA, "kind": "install", "name": NAME,
              "version": None, "status": "failed", "stage": "", "reason": "",
              "steps": steps}
    stage = "verify"
    try:
        version, data, sums_b, release_b, pins = verify(zip_path, sums, release)
        report["version"] = version
        steps["verify"] = "ok"
        say(f"install: verify ok ({version})")

        stage = "extract"
        homemod.make_layout(home, private=private)
        cache_release(home, version, data, sums_b, release_b)
        steps["extract"] = lay_out(home, version, data)
        say(f"install: extract {steps['extract']}")

        stage = "runtimes"
        folders = payload.place_runtimes(pins, home, source_dir=runtime_dir,
                                         opener=opener)
        steps["runtimes"] = "placed"
        say("install: runtimes placed")

        stage = "config"
        steps["config"] = firstrun.write_first_run(home)
        say(f"install: config {steps['config']}")

        stage = "selftest"
        before = homemod.read_marker(home)
        if before is not None and before["version"] == version:
            steps["selftest"] = "skipped"
        else:
            res = selftest(home, version)
            folded = _fold_selftest(res)
            report["selftest"] = folded
            steps["selftest"] = folded["status"]
            if folded["status"] != selftestmod.PASSED:
                raise InstallFailed("selftest", scrub(
                    f"{folded['stage'] or 'self-test'}: {folded['reason'] or folded['status']}",
                    home))
        say(f"install: self-test {steps['selftest']}")

        stage = "marker"
        steps["marker"], marker = set_marker(home, version, folders, now=now)
        say(f"install: marker {steps['marker']}")

        stage = "shell"
        res = shell.rewrite(home, version, runner=runner, effect_root=effect_root)
        steps["shell"] = "read back"
        report["shell"] = {k: res[k] for k in ("uninstall_script", "shortcuts",
                                               "uninstall_entry", "logon_task")}
        say("install: shell entries read back")

        stage = "start"
        if start:
            start_client(home, marker, spawn=spawn, environ=environ)
            steps["start"] = "started"
        else:
            steps["start"] = "not started"
        say(f"install: client {steps['start']}")
    except InstallFailed as exc:
        report["stage"], report["reason"] = exc.stage, exc.reason
    except Exception as exc:  # noqa: BLE001 - every failure ends in the one report
        report["stage"], report["reason"] = stage, _reason(exc, home)
    else:
        report["status"] = "installed"
        report["stage"] = "done"
    try:
        write_report(home, report, now)
    except OSError as exc:
        say(f"install: report not written ({exc.__class__.__name__})")
    if report["status"] != "installed":
        say(f"install: failed at {report['stage']}: {report['reason']}")
        return EXIT_FAIL, report
    say(f"install: done ({report['version']})")
    return EXIT_OK, report


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install install",
        description="install an AshLight release into a per-user home")
    p.add_argument("--zip", required=True, help="the app zip AshLight-<ver>-app.zip")
    p.add_argument("--sums", help="SHA256SUMS.txt (default: beside the zip)")
    p.add_argument("--release", help="release.json (default: beside the zip)")
    p.add_argument("--runtime-dir", help="a folder with the two publisher zips "
                   "(no runtime fetch)")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "%%LOCALAPPDATA%%\\Programs\\AshLight)")
    p.add_argument("--no-start", action="store_true", help="do not start the client")
    p.add_argument("--effect-root", help=argparse.SUPPRESS)  # al_shell -EffectRoot
    return p


def resolve_home(arg, environ=None):
    """--home, else AL_HOME, else the default player home."""
    env = os.environ if environ is None else environ
    if arg:
        return Path(os.path.abspath(arg))
    value = (env.get(paths.HOME_ENV) or "").strip().strip('"')
    if value:
        return Path(os.path.abspath(value))
    return paths.default_home(env)


def main(argv=None, environ=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    home = resolve_home(args.home, environ)
    code, _report = run(args.zip, home, runtime_dir=args.runtime_dir,
                        start=not args.no_start, sums=args.sums,
                        release=args.release, effect_root=args.effect_root,
                        environ=environ, out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
