"""`installer repair` (REL-INSTALL-CMD, finding F-050, DEP-09;
docs/plan/05-deployment.md "Repair").

run(home) checks the active version of the marker (payload.verify_active:
every shipped file against MANIFEST.json, and both runtime folders). A
changed, missing or unlisted file is reported and the whole version is
re-extracted from the cached zip in <home>/cache/downloads/<version>/,
checked again against its cached SHA256SUMS.txt line first. Installed code
is never edited in place: reextract() moves the damaged folder aside to
<home>/temp, lays the version out anew through <version>.partial and one
rename, and only then removes the aside copy (replaceable: it is re-made
from the zip); a failed extract moves it back. A missing runtime is placed
again from the cached release.json pins (the -RuntimeDir folder, or the
installer fetch: repair is one of the three installer acts that may fetch
a runtime, plan 05 Design point 13). The shell entries are then rewritten
and read back (shell.rewrite; every effect through one runner).

Exit codes: 0 repaired or nothing to repair, 1 a failure (the lines say
which), 2 usage or a refused home. Prints `repair: ...` lines with no
path. No admin rights; no game folder is read or written. Runs only in the
installer's own process; standard library only.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from .. import NAME, pinfetch, paths
from . import home as homemod
from . import payload, shell

ASIDE_PREFIX = "repair-"
SUMS_NAME = "SHA256SUMS.txt"
RELEASE_NAME = "release.json"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


class RepairError(Exception):
    """The active version could not be repaired."""


def _cached(home, version):
    """(zip path, sums path, release path) in the downloads cache."""
    folder = homemod.layout(home)["downloads"] / version
    return (folder / f"{NAME}-{version}-app.zip", folder / SUMS_NAME,
            folder / RELEASE_NAME)


def cached_zip_bytes(home, version):
    """The cached app zip's bytes after its SHA256SUMS.txt check."""
    zip_path, sums_path, _rel = _cached(home, version)
    if not zip_path.is_file() or not sums_path.is_file():
        raise RepairError(f"no cached zip for {version}; re-run the install line")
    name, data = payload._zip_bytes(zip_path)
    sums = payload._read_capped(sums_path, payload.MAX_SUMS_BYTES, SUMS_NAME)
    payload.check_zip_bytes(name, data, sums)
    return data


def reextract(home, version, data):
    """Replace <home>/app/<version> whole from the zip bytes `data`: the
    old folder goes aside to <home>/temp/repair-<version>-<hex>, the
    version is laid out anew (payload.extract), then the aside copy is
    removed. On a failed extract the aside copy is moved back. A link or
    junction in the folder's place is refused, never followed."""
    lay = homemod.layout(home)
    target = lay["app"] / version
    if not homemod.is_version(version):
        raise RepairError(f"not a version: {version!r}")
    if payload._is_link(target):
        raise RepairError(f"the folder of {version} is a link; not touched")
    aside = None
    if os.path.lexists(target):
        lay["temp"].mkdir(parents=True, exist_ok=True)
        aside = lay["temp"] / f"{ASIDE_PREFIX}{version}-{os.urandom(4).hex()}"
        os.replace(target, aside)
    try:
        payload.extract(data, home, version)
    except BaseException:
        if aside is not None and not os.path.lexists(target):
            try:
                os.replace(aside, target)
                aside = None
            except OSError:
                pass
        raise
    if aside is not None:
        shutil.rmtree(aside, ignore_errors=True)
    return target


def _runtime_problem(text):
    return text.startswith("runtime missing: ")


def run(home, runtime_dir=None, runner=None, effect_root=None, opener=None,
        out=None):
    """Repair the active version of `home`. Returns (exit code, result
    dict {status, version, problems, steps})."""
    say = (lambda line: out.write(line + "\n")) if out is not None else (lambda line: None)
    try:
        home = homemod.check_home(home)
    except paths.HomeRefused as exc:
        say(f"repair: home refused, {exc}")
        return EXIT_USAGE, {"status": "refused", "version": None, "problems": [],
                            "steps": {}}
    steps = {}
    check = payload.verify_active(home)
    version = check["version"]
    result = {"status": "failed", "version": version,
              "problems": list(check["problems"]), "steps": steps}
    if version is None:
        say("repair: no valid install marker; run the install line")
        return EXIT_FAIL, result
    for text in check["problems"]:
        say(f"repair: {text}")
    stage = "code"
    try:
        code_problems = [p for p in check["problems"] if not _runtime_problem(p)]
        if code_problems:
            reextract(home, version, cached_zip_bytes(home, version))
            steps["code"] = "re-extracted"
        else:
            steps["code"] = "ok"
        say(f"repair: code {steps['code']}")

        stage = "runtimes"
        if any(_runtime_problem(p) for p in check["problems"]):
            _zip, _sums, rel_path = _cached(home, version)
            pins = payload.pins_from_release(payload.read_release(rel_path), version)
            marker = homemod.read_marker(home)
            for name in pinfetch.RUNTIME_NAMES:
                folder = payload.runtime_folder(name, pins[name])
                if folder != marker[name]:
                    raise RepairError(f"{name}: the cached pin is not the marker's runtime")
            payload.place_runtimes(pins, home, source_dir=runtime_dir, opener=opener)
            steps["runtimes"] = "placed"
        else:
            steps["runtimes"] = "ok"
        say(f"repair: runtimes {steps['runtimes']}")

        stage = "check"
        after = payload.verify_active(home)
        if not after["ok"]:
            raise RepairError("still differs: " + "; ".join(after["problems"][:5]))

        stage = "shell"
        shell.rewrite(home, version, runner=runner, effect_root=effect_root)
        steps["shell"] = "read back"
        say("repair: shell entries read back")
    except Exception as exc:  # noqa: BLE001 - reported as one line, exit 1
        text = str(exc).strip() or exc.__class__.__name__
        for form in {str(home), str(home).replace("\\", "/")}:
            text = text.replace(form, "<home>")
        result["stage"] = stage
        say(f"repair: failed at {stage}: {text[:300]}")
        return EXIT_FAIL, result
    result["status"] = "repaired" if check["problems"] else "ok"
    say(f"repair: {result['status']} ({version})")
    return EXIT_OK, result


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install repair",
        description="check the active version and re-extract it from the cached zip")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "the home of this payload, else the default player home)")
    p.add_argument("--runtime-dir", help="a folder with the two publisher zips "
                   "(no runtime fetch)")
    p.add_argument("--effect-root", help=argparse.SUPPRESS)  # al_shell -EffectRoot
    return p


def resolve_home(arg, environ=None):
    env = os.environ if environ is None else environ
    if arg:
        return Path(os.path.abspath(arg))
    try:
        found = paths.install_home(env)
    except paths.HomeRefused:
        found = None
    return found if found is not None else paths.default_home(env)


def main(argv=None, environ=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    code, _res = run(resolve_home(args.home, environ), runtime_dir=args.runtime_dir,
                     effect_root=args.effect_root, out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
