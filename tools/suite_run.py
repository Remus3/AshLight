"""Suite run - the one whole-suite command (TEST-SUITE-RUNNER, F-089).

    python tools/suite_run.py                 run the whole suite (under the gate)
    python tools/suite_run.py argv --owner ID print the one gate command line
    python tools/suite_run.py plan            print the phase commands, run nothing

The whole suite always runs UNDER the kit suite gate (FLEET item 16 c):

    python ops/fleet_kit/fleet_suite_gate.py run --owner ID -- python tools/suite_run.py

The gate sets FLEET_SUITE_SLOT for its child; a run without it is refused
with the command above (exit 2), so the gate is never hidden from.

Two phases, always both, in this order:
1. every test except the `timing` ones: on 4 pytest-xdist workers with
   `--dist loadgroup` when xdist (and execnet) is importable, serial
   otherwise. The mode is picked here; callers pass no flag.
2. the `timing` tests alone, serial, after phase 1 (research 0049 R3,
   row TEST-TIMING-ALONE); "no tests collected" (5) counts as green.
The exit code is the worst phase's. Children run at below-normal priority.

xdist is an optional dev-only test plugin (decision 0002, Test plugins):
this file only asks importlib whether it is present and never imports it.
Stdlib only.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE_REL = "ops/fleet_kit/fleet_suite_gate.py"
SELF_REL = "tools/suite_run.py"
SLOT_ENV = "FLEET_SUITE_SLOT"
WORKERS = 4
XDIST_ARGS = ("-n", str(WORKERS), "--dist", "loadgroup")
PYTEST = ("-m", "pytest", "-q")
NO_TESTS = 5
BELOW_NORMAL = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS


def gate_command(owner):
    """The one spelling of the whole-suite command, as a single line."""
    return f"python {GATE_REL} run --owner {owner} -- python {SELF_REL}"


def xdist_available():
    """True when pytest-xdist and execnet can be imported (not imported here)."""
    try:
        return all(importlib.util.find_spec(m) is not None for m in ("xdist", "execnet"))
    except (ImportError, ValueError):
        return False


def phases(xdist=None, python=None):
    """[(name, argv)] of the two phases, in run order."""
    py = python or sys.executable
    use = xdist_available() if xdist is None else bool(xdist)
    one = [py, *PYTEST, "-m", "not timing"]
    if use:
        one += list(XDIST_ARGS)
    two = [py, *PYTEST, "-m", "timing"]
    return [("parallel" if use else "serial", one), ("timing", two)]


def _default_runner(argv, env):
    kw = {"cwd": str(ROOT), "env": env}
    if sys.platform == "win32":
        kw["creationflags"] = BELOW_NORMAL
    return subprocess.call(argv, **kw)


def worst(codes):
    """The worst exit code: any non-zero beats 0, the larger non-zero wins."""
    return max(codes) if codes else 0


def run(environ=None, runner=None, xdist=None, out=None):
    """Run both phases; return the worst exit code. Refuses outside the gate."""
    env = dict(os.environ if environ is None else environ)
    out = out or sys.stdout
    if not env.get(SLOT_ENV):
        print("suite_run: refused - the whole suite runs only under the suite gate:\n"
              + gate_command("<owner>"), file=out)
        return 2
    runner = runner or _default_runner
    codes = []
    for name, argv in phases(xdist):
        print(f"suite_run: phase {name}: {' '.join(argv[1:])}", file=out, flush=True)
        rc = runner(argv, env)
        if name == "timing" and rc == NO_TESTS:
            rc = 0
        print(f"suite_run: phase {name} exit {rc}", file=out, flush=True)
        codes.append(rc)
    return worst(codes)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="suite_run.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("argv", help="print the gate command line")
    a.add_argument("--owner", required=True)
    sub.add_parser("plan", help="print the phase commands, run nothing")
    ns = ap.parse_args(argv)
    if ns.cmd == "argv":
        print(gate_command(ns.owner))
        return 0
    if ns.cmd == "plan":
        for name, cmd in phases():
            print(f"{name}: {' '.join(cmd[1:])}")
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main())
