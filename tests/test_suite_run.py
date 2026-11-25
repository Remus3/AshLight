"""tools/suite_run.py - the one whole-suite command (TEST-SUITE-RUNNER).

Phase 1 is every non-timing test, on 12 xdist workers (capped at the
logical CPU count less 4, never under 2) with loadgroup when xdist is
importable and serial otherwise; phase 2 is the timing tests, after
phase 1 and never beside its workers, as two serial streams side by side
(calc files, the rest; TEST-SERIAL-PHASE-CUT) or one with the switch off;
the exit code is the worst phase's; a run outside the
suite gate is refused with the gate command. xdist stays an optional
dev-only plugin: nothing under server/, tools/ or app/ imports it and no
AshLight script runs pip.
"""
import ast
import io
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import suite_run  # noqa: E402

GATED = {"FLEET_SUITE_SLOT": "0"}


def _args(argv):
    return argv[1:]


def test_phase_one_with_xdist_is_twelve_loadgroup_workers_without_timing():
    (name, one), *_ = suite_run.phases(xdist=True, python="py", cpus=16)
    assert name == "parallel"
    assert _args(one) == ["-m", "pytest", "-q", "-m", "not timing",
                          "-n", "12", "--dist", "loadgroup"]


def test_worker_count_leaves_four_cpus_and_never_drops_under_two():
    """TEST-SUITE-HOLD-75: 12 workers on the 16-CPU dev box; a smaller box
    keeps 4 logical CPUs free; 2 is the floor; an unknown count gives 2."""
    assert suite_run.WORKERS == 12
    for cpus, want in ((64, 12), (16, 12), (12, 8), (8, 4), (6, 2), (4, 2),
                       (1, 2), (0, 2)):
        assert suite_run.workers(cpus) == want, cpus
    assert suite_run.workers(None) == suite_run.workers(os.cpu_count())
    for _name, two in suite_run.phases(xdist=True, python="py", cpus=64)[1:]:
        assert "-n" not in two


def test_phase_one_without_xdist_is_serial():
    (name, one), *_ = suite_run.phases(xdist=False, python="py")
    assert name == "serial"
    assert _args(one) == ["-m", "pytest", "-q", "-m", "not timing"]
    assert "-n" not in one


def test_phase_two_unsplit_is_the_timing_tests_alone_and_serial():
    for x in (True, False):
        _, (name, two) = suite_run.phases(xdist=x, python="py", split=False)
        assert name == "timing"
        assert _args(two) == ["-m", "pytest", "-q", "-m", "timing"]


def test_phase_two_split_is_a_calc_stream_and_the_rest():
    """TEST-SERIAL-PHASE-CUT: the calc timing files in one serial stream,
    every other timing test in the other (the tree minus those files, so a
    newly marked file still runs); the switch is on by default."""
    assert suite_run.SPLIT_TIMING is True
    assert suite_run.phases(python="py", xdist=False) == \
        suite_run.phases(python="py", xdist=False, split=True)
    calc_files = list(suite_run.CALC_TIMING_FILES)
    assert calc_files == ["tests/test_fullstack.py", "tests/test_math_e2e_live.py",
                          "tests/test_math_perf.py", "tests/test_tc_press_staged.py"]
    for x in (True, False):
        _, (n1, calc), (n2, rest) = suite_run.phases(xdist=x, python="py", split=True)
        assert (n1, n2) == ("timing-calc", "timing-rest")
        assert _args(calc) == ["-m", "pytest", "-q", "-m", "timing", *calc_files]
        assert _args(rest) == ["-m", "pytest", "-q", "-m", "timing", "tests",
                               *[f"--ignore={f}" for f in calc_files]]
        for argv in (calc, rest):
            assert "-n" not in argv and "--dist" not in argv
    assert all(suite_run.is_timing(n) for n in ("timing", "timing-calc", "timing-rest"))
    assert not any(suite_run.is_timing(n) for n in ("parallel", "serial"))


def test_mode_follows_xdist_presence(monkeypatch):
    monkeypatch.setattr(suite_run, "xdist_available", lambda: False)
    assert suite_run.phases()[0][0] == "serial"
    monkeypatch.setattr(suite_run, "xdist_available", lambda: True)
    assert suite_run.phases()[0][0] == "parallel"


def test_hidden_xdist_reads_as_absent(monkeypatch):
    real = suite_run.importlib.util.find_spec
    monkeypatch.setattr(suite_run.importlib.util, "find_spec",
                        lambda m, *a: None if m == "xdist" else real(m, *a))
    assert suite_run.xdist_available() is False


def _phase_of(argv):
    if "not timing" in argv:
        return 0
    if suite_run.CALC_TIMING_FILES[0] in argv:
        return 1
    return 2 if any(a.startswith("--ignore=") for a in argv) else 1


def _record(codes):
    """A fake runner: the code of each phase by its command (phase 1, then
    the calc stream or the one unsplit timing run, then the rest stream),
    so the side-by-side streams may call it in any order."""
    seen = []
    lock = threading.Lock()

    def runner(argv, env, out=None):
        with lock:
            seen.append((argv, env))
        if out is not None:
            out.write(f"buffered {_phase_of(argv)}\n")
        return codes[_phase_of(argv)]
    return seen, runner


@pytest.fixture(params=[True, False], ids=["split", "unsplit"])
def split(request, monkeypatch):
    monkeypatch.setattr(suite_run, "SPLIT_TIMING", request.param)
    return request.param


def test_phase_two_runs_after_phase_one(split):
    seen, runner = _record([0, 0, 0])
    assert suite_run.run(GATED, runner, xdist=True, out=io.StringIO()) == 0
    assert len(seen) == (3 if split else 2)
    assert "not timing" in seen[0][0] and "-n" in seen[0][0]
    for argv, _env in seen[1:]:
        assert "timing" in argv and "not timing" not in argv
    assert all(e["FLEET_SUITE_SLOT"] == "0" for _a, e in seen)


def test_split_streams_run_side_by_side_and_the_second_is_buffered():
    """Both phase 2 streams are running at once; the calc stream prints
    live, the rest stream's output is printed after both have ended."""
    both = threading.Barrier(2, timeout=10)
    seen = []

    def runner(argv, env, out=None):
        seen.append(_phase_of(argv))
        if _phase_of(argv):
            both.wait()  # raises BrokenBarrierError unless both run at once
        if out is not None:
            out.write("rest says hi\n")
        return 0
    buf = io.StringIO()
    assert suite_run.run(GATED, runner, xdist=False, out=buf) == 0
    assert seen[0] == 0 and sorted(seen[1:]) == [1, 2]
    text = buf.getvalue()
    assert text.index("phase timing-rest output:") < text.index("rest says hi")
    assert text.index("phase timing-calc exit 0") < text.index("phase timing-rest exit 0")


def test_a_stream_that_raises_is_a_red_and_the_other_still_ends():
    def runner(argv, env, out=None):
        if _phase_of(argv) == 2:
            raise OSError("no such exe")
        return 0
    buf = io.StringIO()
    assert suite_run.run(GATED, runner, xdist=False, out=buf) == 1
    assert "phase timing-rest failed to run" in buf.getvalue()
    assert "phase timing-calc exit 0" in buf.getvalue()


def test_exit_code_is_the_worst_phase(monkeypatch):
    monkeypatch.setattr(suite_run, "SPLIT_TIMING", False)
    for codes, want in (([0, 0], 0), ([1, 0], 1), ([0, 1], 1), ([1, 2], 2),
                        ([3, 1], 3), ([0, 5], 0), ([5, 0], 5)):
        seen, runner = _record(codes + [99])
        got = suite_run.run(GATED, runner, xdist=False, out=io.StringIO())
        assert got == want, codes
        assert len(seen) == 2, "phase 2 always runs"
    monkeypatch.setattr(suite_run, "SPLIT_TIMING", True)
    for codes, want in (([0, 0, 0], 0), ([1, 0, 0], 1), ([0, 1, 0], 1),
                        ([0, 0, 1], 1), ([0, 2, 3], 3), ([0, 5, 5], 0),
                        ([0, 5, 1], 1), ([5, 0, 0], 5)):
        seen, runner = _record(codes)
        got = suite_run.run(GATED, runner, xdist=False, out=io.StringIO())
        assert got == want, codes
        assert len(seen) == 3, "both phase 2 streams always run"


def test_both_phases_get_the_same_suite_t0_set_at_start(split):
    seen, runner = _record([0, 0, 0])
    env = dict(GATED)
    env.pop("AL_SUITE_T0", None)
    assert suite_run.run(env, runner, xdist=True, out=io.StringIO()) == 0
    values = [e.get("AL_SUITE_T0") for _argv, e in seen]
    assert values[0] and set(values) == {values[0]}
    assert float(values[0]) > 1e9
    assert "AL_SUITE_T0" not in env, "the caller's mapping is not changed"


def test_an_existing_suite_t0_is_not_overwritten(split):
    seen, runner = _record([0, 0, 0])
    env = dict(GATED, AL_SUITE_T0="1234.5")
    suite_run.run(env, runner, xdist=False, out=io.StringIO())
    assert {e["AL_SUITE_T0"] for _argv, e in seen} == {"1234.5"}


def test_both_phases_name_the_render_to_run_first(split):
    """TEST-XDIST-GROUP-RESTORE: the long test_shots render is named in
    AL_SUITE_FIRST for both phases; tests/conftest.py moves it first."""
    seen, runner = _record([0, 0, 0])
    env = dict(GATED)
    assert suite_run.run(env, runner, xdist=True, out=io.StringIO()) == 0
    want = "tests/test_shots.py::test_real_render_from_a_real_demo_core"
    assert suite_run.FIRST == (want,)
    assert {e.get(suite_run.FIRST_ENV) for _argv, e in seen} == {want}
    assert suite_run.FIRST_ENV not in env, "the caller's mapping is not changed"


@pytest.mark.slow  # one collect-only run of the whole tree
def test_the_named_first_test_is_collected_first():
    """The real conftest hook: with AL_SUITE_FIRST set the render is the
    first collected item, and the collection keeps every other test."""
    def collect(first):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PYTEST_") and k != suite_run.FIRST_ENV}
        if first:
            env[suite_run.FIRST_ENV] = ",".join(suite_run.FIRST)
        p = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                            "-m", "not timing"], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
        return [ln for ln in p.stdout.splitlines() if "::" in ln]
    plain, ordered = collect(False), collect(True)
    assert ordered[0] == suite_run.FIRST[0]
    assert plain[0] != suite_run.FIRST[0]
    assert sorted(plain) == sorted(ordered)


def test_run_outside_the_gate_is_refused_with_the_gate_command():
    seen, runner = _record([0, 0, 0])
    buf = io.StringIO()
    assert suite_run.run({}, runner, xdist=True, out=buf) == 2
    assert seen == []
    text = buf.getvalue()
    assert "refused" in text
    assert ("python ops/fleet_kit/fleet_suite_gate.py run --owner <owner> -- "
            "python tools/suite_run.py") in text


PROBE_INI = ("[pytest]\naddopts = -p no:cacheprovider\n"
             "markers =\n    timing: wall-clock sensitive\n")
PROBE_TEST = "\n".join((
    "import os",
    "import pytest",
    "",
    "",
    "def _mark(name):",
    "    with open(os.environ['AL_PROBE_OUT'], 'a', encoding='ascii') as fh:",
    "        fh.write(name + chr(10))",
    "",
    "",
    "def test_plain():",
    "    _mark('plain')",
    "",
    "",
    "@pytest.mark.timing",
    "def test_timed():",
    "    _mark('timed')",
    ""))


@pytest.mark.parametrize("xdist", [False, True])
def test_real_phases_keep_timing_tests_out_of_the_parallel_pass(tmp_path, xdist):
    """TEST-TIMING-ALONE: run the real phase commands on a probe project:
    phase 1 (parallel when xdist is present) deselects -m timing, phase 2
    runs the timing test alone, serially."""
    if xdist and not suite_run.xdist_available():
        pytest.skip("pytest-xdist not installed (optional dev-only plugin)")
    proj = tmp_path / "probe"
    proj.mkdir()
    (proj / "pytest.ini").write_text(PROBE_INI, newline="\n")
    (proj / "test_probe.py").write_text(PROBE_TEST, newline="\n")
    ran = {}
    # TEST-PROBE-XDIST-2: cpus=6 makes phase 1 run at -n 2, not the full 12.
    for name, argv in suite_run.phases(xdist=xdist, cpus=6, split=False):
        out = tmp_path / f"{name}.txt"
        env = dict(os.environ, AL_PROBE_OUT=str(out))
        env.pop("PYTEST_XDIST_WORKER", None)
        p = subprocess.run(argv, cwd=str(proj), env=env, capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 0, p.stdout + p.stderr
        ran[name] = out.read_text(encoding="ascii").split() if out.exists() else []
        if name != "timing":
            assert ("-n" in argv) is xdist
    first = "parallel" if xdist else "serial"
    assert list(ran) == [first, "timing"]
    assert ran[first] == ["plain"], ran  # timing deselected beside the workers
    assert ran["timing"] == ["timed"], ran  # and run alone afterwards
    timing_argv = suite_run.phases(xdist=xdist, cpus=6, split=False)[1][1]
    assert "-n" not in timing_argv and "--dist" not in timing_argv


def test_real_split_streams_share_out_the_timing_tests(tmp_path):
    """TEST-SERIAL-PHASE-CUT on a probe project: the calc stream runs only
    the timed tests of the calc files, the rest stream every other timed
    test (a file it was never told about included), neither a plain one."""
    proj = tmp_path / "probe"
    (proj / "tests").mkdir(parents=True)
    (proj / "pytest.ini").write_text(PROBE_INI.replace(
        "addopts", "testpaths = tests\naddopts"), newline="\n")
    files = list(suite_run.CALC_TIMING_FILES) + ["tests/test_probe.py",
                                                 "tests/test_new_timed.py"]
    for rel in files:
        tag = Path(rel).stem
        (proj / rel).write_text(PROBE_TEST.replace("'timed'", repr(tag)), newline="\n")
    ran = {}
    for name, argv in suite_run.phases(xdist=False, split=True):
        out = tmp_path / f"{name}.txt"
        env = dict(os.environ, AL_PROBE_OUT=str(out))
        env.pop("PYTEST_XDIST_WORKER", None)
        p = subprocess.run(argv, cwd=str(proj), env=env, capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 0, p.stdout + p.stderr
        ran[name] = sorted(out.read_text(encoding="ascii").split())
    assert ran["serial"] == ["plain"] * len(files)
    assert ran["timing-calc"] == sorted(Path(f).stem for f in suite_run.CALC_TIMING_FILES)
    assert ran["timing-rest"] == ["test_new_timed", "test_probe"]


def test_script_refuses_outside_the_gate():
    env = {k: v for k, v in os.environ.items() if k != "FLEET_SUITE_SLOT"}
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "suite_run.py")],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       timeout=60)
    assert p.returncode == 2
    assert "fleet_suite_gate.py run --owner" in p.stdout


def test_argv_prints_exactly_one_line():
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "suite_run.py"),
                        "argv", "--owner", "x"], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0
    assert p.stdout == ("python ops/fleet_kit/fleet_suite_gate.py run --owner x -- "
                        "python tools/suite_run.py\n")


def _sources(folder, exts):
    base = ROOT / folder
    for p in sorted(base.rglob("*")):
        if p.suffix in exts and p.is_file() and "node_modules" not in p.parts:
            yield p


def test_no_product_code_imports_xdist():
    hits = []
    for folder in ("server", "tools"):
        for p in _sources(folder, {".py"}):
            tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(n.split(".")[0] in ("xdist", "execnet") for n in names):
                    hits.append(str(p.relative_to(ROOT)))
    for p in _sources("app", {".js", ".cjs", ".mjs"}):
        if re.search(r"\bxdist\b", p.read_text(encoding="utf-8", errors="replace")):
            hits.append(str(p.relative_to(ROOT)))
    assert hits == []


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def test_no_script_runs_pip():
    hits = []
    for folder in ("scripts", "tools"):
        for p in _sources(folder, {".ps1", ".psm1", ".cmd", ".bat"}):
            for n, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
                code = _QUOTED.sub("", line.split("#", 1)[0])
                if re.search(r"\bpip(3)?(\.exe)?\b", code, re.I):
                    hits.append(f"{p.relative_to(ROOT)}:{n}")
        for p in _sources(folder, {".py"}):
            tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if re.fullmatch(r"pip(3)?(\.exe)?", node.value, re.I):
                        hits.append(f"{p.relative_to(ROOT)}:{node.lineno}")
                    elif re.match(r"\s*(python\S*\s+-m\s+)?pip(3)?\s+(install|download)\b",
                                  node.value, re.I):
                        hits.append(f"{p.relative_to(ROOT)}:{node.lineno}")
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                             else [node.module or ""])
                    if any(x.split(".")[0] == "pip" for x in names):
                        hits.append(f"{p.relative_to(ROOT)}:{node.lineno}")
    assert hits == []


def test_requirements_pin_xdist_and_execnet_with_hashes():
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    for name in ("pytest-xdist", "execnet"):
        m = re.search(rf"^{re.escape(name)}==\S+ \\\n\s+--hash=sha256:[0-9a-f]{{64}}$",
                      text, re.M)
        assert m, name
