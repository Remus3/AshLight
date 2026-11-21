#!/usr/bin/env python3
"""Release stage (DEP-12, F-074, decision 0064): the PASS / FAIL report.

Loaded by tools/release.py for the `stage` sub-command:

    release.py stage [VERSION] [--sandbox] [--owner ID] [--out DIR] [--root DIR]

VERSION defaults to the source VERSION. The static gates run in order; the
first refusal stops the run and every later step reads `skipped`:

    1 clean     the tree is clean (tracked changes and untracked files)
    2 version   VERSION is SemVer, equals the asked version, and every
                version-bearing place holds it (tools/rel_version.py check)
    3 suite     the Python suite, always through the kit suite gate:
                python ops/fleet_kit/fleet_suite_gate.py run --owner ID --
                python tools/suite_run.py
    4 node      npm test --prefix app
    5 builds    two builds of HEAD (tools/rel_build.py build) into two
                scratch folders; every asset must be byte-identical
    6 sweep     tools/leak_sweep.py over the staged tree as written: every
                app zip member and every asset, names and bytes

On PASS the first build's assets move into the release folder
<sidecar>/Build/release/<version>/ (or --out). Every run, PASS or FAIL,
writes <out>/stage.json: schema, version, commit, verdict, steps (name,
status pass | fail | skipped, detail), assets (name, size, sha256),
sums_sha256 (of SHA256SUMS.txt), created (the injected clock, UTC) and
sandbox. A FAIL leaves the tree and every release asset as they were: the
scratch build folders are removed and nothing moves.

Steps are a list of callables (STEPS); a later package adds one step by
appending to it (REL-STAGE-ROUNDTRIP, REL-STAGE-SANDBOX). `--sandbox` is
recorded; with no sandbox step built yet a note says so.

Floor: the tool never looks for the game - no process list, no window
query, no game log access; it only reads the repository. It never uploads,
tags, commits or pushes; no network. Heavy steps (suite, node, builds) run
at below-normal priority. Stdlib only.
"""
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

STAGE_NAME = "stage.json"
SCRATCH_NAME = "_stage"
SCHEMA = 1
GATE_REL = "ops/fleet_kit/fleet_suite_gate.py"
SUITE_REL = "tools/suite_run.py"
NODE_ARGV = ("npm", "test", "--prefix", "app")
OWNER_ENV = "FLEET_CLAIM_OWNER"
DEFAULT_OWNER = "release-stage"
BELOW_NORMAL = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
PASS, FAIL = "PASS", "FAIL"


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "rel_stage_" + name, str(TOOLS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load_tool("rel_build")
rv = rb.rv


class StepFail(Exception):
    """One step refused; the text is the step's detail."""


# --- the default runner and clock ------------------------------------------

def default_run(argv, cwd):
    """Run argv in cwd at below-normal priority; the exit code. The program
    is resolved on PATH first (npm is npm.cmd on Windows)."""
    argv = list(argv)
    found = shutil.which(argv[0])
    if found:
        argv[0] = found
    kw = {"cwd": str(cwd)}
    if sys.platform == "win32":
        kw["creationflags"] = BELOW_NORMAL
    return subprocess.call(argv, **kw)


def created_text(seconds):
    stamp = datetime.datetime.fromtimestamp(float(seconds),
                                            tz=datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- the steps -------------------------------------------------------------

def step_clean(ctx):
    lines = rb.dirty(ctx["root"])
    if lines:
        raise StepFail("the tree is dirty (%d path(s), first: %s)"
                       % (len(lines), lines[0][3:]))
    return "clean"


def step_version(ctx):
    want = ctx["version"]
    try:
        rv.parse(want)
    except rv.VersionError as exc:
        raise StepFail(str(exc))
    try:
        have = rv.source_version(ctx["root"])
    except (rv.VersionError, OSError) as exc:
        raise StepFail(str(exc))
    if have != want:
        raise StepFail("VERSION is %s, stage asked for %s" % (have, want))
    problems = rv.check(ctx["root"])
    if problems:
        raise StepFail("%d version problem(s), first: %s"
                       % (len(problems), problems[0]))
    return "VERSION %s everywhere" % want


def suite_argv(owner, python=None):
    """The suite command: always through the kit suite gate."""
    py = python or sys.executable
    return [py, GATE_REL, "run", "--owner", owner, "--", py, SUITE_REL]


def _call(ctx, argv, label):
    try:
        rc = ctx["run"](argv, ctx["root"])
    except OSError as exc:
        raise StepFail("%s could not start: %s" % (label, exc))
    if rc != 0:
        raise StepFail("%s exit %s" % (label, rc))
    return "%s exit 0" % label


def step_suite(ctx):
    return _call(ctx, suite_argv(ctx["owner"]), "suite gate")


def step_node(ctx):
    return _call(ctx, list(NODE_ARGV), "npm test")


def _asset_bytes(folder):
    """{name: bytes} of the plain files in a build folder."""
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir())
            if p.is_file()}


def step_builds(ctx):
    scratch = ctx["scratch"]
    results = []
    for label in ("a", "b"):
        try:
            res = ctx["build"](root=ctx["root"], out=scratch / label)
        except rb.BuildError as exc:
            raise StepFail("build %s refused: %s" % (label, exc))
        results.append(res)
    if results[0]["version"] != ctx["version"]:
        raise StepFail("the build made %s, stage asked for %s"
                       % (results[0]["version"], ctx["version"]))
    first, second = _asset_bytes(scratch / "a"), _asset_bytes(scratch / "b")
    if sorted(first) != sorted(second):
        raise StepFail("the two builds made different asset sets")
    differ = [n for n in sorted(first) if first[n] != second[n]]
    if differ:
        raise StepFail("the two builds differ: %s" % ", ".join(differ))
    if rb.SUMS_NAME not in first:
        raise StepFail("the build wrote no %s" % rb.SUMS_NAME)
    ctx["staged"] = first
    ctx["zip_name"] = results[0]["zip"].name
    return "two identical builds, %d asset(s)" % len(first)


def staged_tree(assets, zip_name):
    """{name: bytes}: every member of the app zip and every other asset."""
    tree = {}
    with zipfile.ZipFile(io.BytesIO(assets[zip_name])) as zf:
        for name in zf.namelist():
            tree[name] = zf.read(name)
    for name, data in assets.items():
        if name != zip_name:
            tree["release/" + name] = data
    return tree


def step_sweep(ctx):
    ra = _load_tool("rel_assets")
    notes = []
    try:
        count = ra.sweep_staged(staged_tree(ctx["staged"], ctx["zip_name"]),
                                notes=notes)
    except (ra.AssetError, zipfile.BadZipFile) as exc:
        raise StepFail(str(exc))
    ctx["notes"].extend(notes)
    return "%d staged file(s) clean%s" % (count, "; " + notes[0] if notes else "")


# The append point: (name, callable). REL-STAGE-ROUNDTRIP and
# REL-STAGE-SANDBOX each append one entry.
STEPS = [
    ("clean", step_clean),
    ("version", step_version),
    ("suite", step_suite),
    ("node", step_node),
    ("builds", step_builds),
    ("sweep", step_sweep),
]


# --- the report ------------------------------------------------------------

def _entry(name, data):
    return {"name": name, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".partial")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def _remove_scratch(scratch):
    # The scratch folder holds only this run's regenerable build output.
    if scratch.exists():
        shutil.rmtree(str(scratch), ignore_errors=True)


def stage(version, sandbox=False, run=None, now=None, root=ROOT, out=None,
          owner=None, build=None, steps=None):
    """Run the static gates; write <out>/stage.json; return the report dict
    (plus "out", the folder). run(argv, cwd) -> exit code and now() ->
    epoch seconds are injected; build defaults to rel_build.build."""
    root = Path(root)
    out = Path(out) if out is not None else rb.default_out(version)
    ctx = {
        "root": root, "version": version, "sandbox": bool(sandbox),
        "run": run or default_run, "build": build or rb.build,
        "owner": owner or os.environ.get(OWNER_ENV) or DEFAULT_OWNER,
        "scratch": out / SCRATCH_NAME, "notes": [], "staged": None,
        "zip_name": None,
    }
    clock = now or time.time
    commit = rb._rev(root, "HEAD^{commit}") or ""
    names = [name for name, _fn in (steps if steps is not None else STEPS)]
    if sandbox and "sandbox" not in names:
        ctx["notes"].append("sandbox asked; the sandbox step is not built yet")
    rows, verdict = [], PASS
    out.mkdir(parents=True, exist_ok=True)
    _remove_scratch(ctx["scratch"])
    try:
        for name, fn in (steps if steps is not None else STEPS):
            if verdict == FAIL:
                rows.append({"name": name, "status": "skipped", "detail": ""})
                continue
            try:
                detail = fn(ctx)
                rows.append({"name": name, "status": "pass",
                             "detail": str(detail or "")})
            except StepFail as exc:
                verdict = FAIL
                rows.append({"name": name, "status": "fail", "detail": str(exc)})
        assets, sums_sha = [], None
        if verdict == PASS and ctx["staged"]:
            for name in sorted(ctx["staged"]):
                _write_atomic(out / name, ctx["staged"][name])
            assets = [_entry(n, ctx["staged"][n]) for n in sorted(ctx["staged"])
                      if n != rb.SUMS_NAME]
            sums_sha = hashlib.sha256(ctx["staged"][rb.SUMS_NAME]).hexdigest()
    finally:
        _remove_scratch(ctx["scratch"])
    report = {
        "schema": SCHEMA, "version": version, "commit": commit,
        "verdict": verdict, "steps": rows, "assets": assets,
        "sums_sha256": sums_sha, "created": created_text(clock()),
        "sandbox": bool(sandbox), "notes": list(ctx["notes"]),
    }
    _write_atomic(out / STAGE_NAME,
                  (json.dumps(report, indent=1, sort_keys=True,
                              ensure_ascii=True) + "\n").encode("ascii"))
    report = dict(report)
    report["out"] = out
    return report


# --- command line ----------------------------------------------------------

def _parser():
    p = argparse.ArgumentParser(
        prog="release.py stage",
        description="Run the release gates and write stage.json (PASS / "
                    "FAIL). No upload, no tag, no network.")
    p.add_argument("version", nargs="?", help="default: the source VERSION")
    p.add_argument("--sandbox", action="store_true",
                   help="also run the sandbox step (recorded)")
    p.add_argument("--owner", help="suite gate owner id (default env %s)"
                                   % OWNER_ENV)
    p.add_argument("--out", help="release folder (default "
                                 "<sidecar>/Build/release/<version>)")
    p.add_argument("--root", default=str(ROOT), help="the repository")
    return p


def main(command, argv):
    """Entry from tools/release.py; returns the exit code (0 PASS, 1 FAIL)."""
    if command != "stage":
        print("rel_stage: unknown sub-command %r" % command, file=sys.stderr)
        return 2
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    version = args.version
    if version is None:
        try:
            version = rv.source_version(Path(args.root))
        except (rv.VersionError, OSError) as exc:
            print("stage: refused: %s" % exc, file=sys.stderr)
            return 1
    rep = stage(version, sandbox=args.sandbox, root=args.root, out=args.out,
                owner=args.owner)
    for row in rep["steps"]:
        print("stage: %-8s %-7s %s" % (row["name"], row["status"], row["detail"]))
    for text in rep["notes"]:
        print("stage: note: %s" % text)
    print("stage: %s %s -> %s" % (rep["verdict"], version,
                                   rep["out"] / STAGE_NAME))
    return 0 if rep["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main("stage", sys.argv[1:]))
