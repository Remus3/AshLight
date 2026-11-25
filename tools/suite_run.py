"""Suite run - the one whole-suite command (TEST-SUITE-RUNNER, F-089).

    python tools/suite_run.py                 run the whole suite (under the gate)
    python tools/suite_run.py argv --owner ID print the one gate command line
    python tools/suite_run.py plan            print the phase commands, run nothing

The whole suite always runs UNDER the kit suite gate (FLEET item 16 c):

    python ops/fleet_kit/fleet_suite_gate.py run --owner ID -- python tools/suite_run.py

The gate sets FLEET_SUITE_SLOT for its child; a run without it is refused
with the command above (exit 2), so the gate is never hidden from.

Two phases, always both, in this order:
1. every test except the `timing` ones: on pytest-xdist workers with
   `--dist loadgroup` when xdist (and execnet) is importable, serial
   otherwise. The mode is picked here; callers pass no flag. Workers:
   WORKERS (12), at most the logical CPU count less SPARE_CPUS (4) and
   never under 2 (TEST-SUITE-HOLD-75, research 0049 addendum 2026-11-21).
2. the `timing` tests, after phase 1 and never beside its workers
   (research 0049 R3, row TEST-TIMING-ALONE), as two serial pytest
   streams side by side (TEST-SERIAL-PHASE-CUT, decision 0060 amendment
   2026-11-24): `timing-calc` runs CALC_TIMING_FILES (the live PoB press
   and calc budgets) and `timing-rest` runs every other timing test (the
   tree with those files ignored, so a newly marked test is never left
   out). The CPU-share tests read their own process CPU, the calc tests
   are wall-clock press budgets beside a mostly idle stream; no assert
   or budget moves. SPLIT_TIMING = False restores the one serial
   `timing` phase. "No tests collected" (5) counts as green per stream.
   The first stream prints live; the second is buffered and printed when
   both have ended.
The exit code is the worst phase's. Children run at below-normal priority.

Order (TEST-XDIST-GROUP-RESTORE): FIRST_ENV names, comma-separated, the
tests that tests/conftest.py moves to the front of the collection (FIRST:
the about 24 s test_shots render, so it starts in the first wave of
dispatch instead of late in file order). Under --dist loadgroup the
multi-test groups still go out before any single test.

xdist is an optional dev-only test plugin (decision 0002, Test plugins):
this file only asks importlib whether it is present and never imports it.
Stdlib only.
"""
import argparse
import importlib.util
import os
import io
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE_REL = "ops/fleet_kit/fleet_suite_gate.py"
SELF_REL = "tools/suite_run.py"
SLOT_ENV = "FLEET_SUITE_SLOT"
T0_ENV = "AL_SUITE_T0"  # epoch seconds of the runner start (tests/slow_budget.py)
FIRST_ENV = "AL_SUITE_FIRST"  # node ids run first, read by tests/conftest.py
FIRST = ("tests/test_shots.py::test_real_render_from_a_real_demo_core",)
WORKERS = 12  # research 0049 addendum 2026-11-21 (TEST-SUITE-HOLD-75)
SPARE_CPUS = 4  # logical CPUs left free for the player's own work
MIN_WORKERS = 2
PYTEST = ("-m", "pytest", "-q")
NO_TESTS = 5
SPLIT_TIMING = True  # TEST-SERIAL-PHASE-CUT: phase 2 as two concurrent streams
TESTS_DIR = "tests"
# the timing tests of these files run the optional calc (live PoB through
# LuaJIT) or a fake slow calc; they are the `timing-calc` stream
CALC_TIMING_FILES = ("tests/test_fullstack.py", "tests/test_math_e2e_live.py",
                     "tests/test_math_perf.py", "tests/test_tc_press_staged.py")
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


def workers(cpus=None):
    """The phase 1 worker count: WORKERS, capped at the logical CPU count
    less SPARE_CPUS, never under MIN_WORKERS."""
    n = os.cpu_count() if cpus is None else cpus
    return max(MIN_WORKERS, min(WORKERS, (n or 0) - SPARE_CPUS))


def xdist_args(cpus=None):
    return ("-n", str(workers(cpus)), "--dist", "loadgroup")


def timing_streams(python=None, split=None):
    """[(name, argv)] of the phase 2 streams: two side by side when split,
    else the one serial `timing` run."""
    py = python or sys.executable
    two = [py, *PYTEST, "-m", "timing"]
    if not (SPLIT_TIMING if split is None else split):
        return [("timing", two)]
    calc = two + list(CALC_TIMING_FILES)
    rest = two + [TESTS_DIR] + [f"--ignore={f}" for f in CALC_TIMING_FILES]
    return [("timing-calc", calc), ("timing-rest", rest)]


def phases(xdist=None, python=None, cpus=None, split=None):
    """[(name, argv)] of every phase command, in run order: phase 1, then
    the phase 2 streams (is_timing names them; they run side by side)."""
    py = python or sys.executable
    use = xdist_available() if xdist is None else bool(xdist)
    one = [py, *PYTEST, "-m", "not timing"]
    if use:
        one += list(xdist_args(cpus))
    return [("parallel" if use else "serial", one), *timing_streams(py, split)]


def is_timing(name):
    return name == "timing" or name.startswith("timing-")


def _default_runner(argv, env, out=None):
    """Run one command; with out, its stdout and stderr go there instead
    of the console."""
    kw = {"cwd": str(ROOT), "env": env}
    if sys.platform == "win32":
        kw["creationflags"] = BELOW_NORMAL
    if out is None:
        return subprocess.call(argv, **kw)
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    out.write(p.stdout.decode("utf-8", errors="replace"))
    return p.returncode


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
    if not env.get(T0_ENV):  # an outer runner's value is kept
        env[T0_ENV] = repr(time.time())
    env[FIRST_ENV] = ",".join(FIRST)
    codes = []
    stages = []
    for name, argv in phases(xdist):
        if is_timing(name) and stages and is_timing(stages[-1][0][0]):
            stages[-1].append((name, argv))
        else:
            stages.append([(name, argv)])
    for stage in stages:
        codes += _run_stage(stage, runner, env, out)
    return worst(codes)


def _run_stage(stage, runner, env, out):
    """Run the commands of one stage side by side (one: in this thread);
    the first prints live, the others are buffered and printed after."""
    for name, argv in stage:
        print(f"suite_run: phase {name}: {' '.join(argv[1:])}", file=out, flush=True)
    rcs = [None] * len(stage)
    bufs = [None] + [io.StringIO() for _ in stage[1:]]

    def one(i):
        name, argv = stage[i]
        try:
            rc = runner(argv, env) if bufs[i] is None else runner(argv, env, out=bufs[i])
        except Exception as exc:  # noqa: BLE001 - a crashed stream is a red
            print(f"suite_run: phase {name} failed to run: {exc!r}", file=out, flush=True)
            rc = 1
        if is_timing(name) and rc == NO_TESTS:
            rc = 0
        rcs[i] = rc

    threads = [threading.Thread(target=one, args=(i,), daemon=True)
               for i in range(1, len(stage))]
    for t in threads:
        t.start()
    one(0)
    for t in threads:
        t.join()
    for i, (name, _argv) in enumerate(stage):
        if bufs[i] is not None:
            print(f"suite_run: phase {name} output:", file=out, flush=True)
            out.write(bufs[i].getvalue())
        print(f"suite_run: phase {name} exit {rcs[i]}", file=out, flush=True)
    return rcs


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
