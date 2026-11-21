"""RUN-OBS-LOGS-PY (F-090, F-027, C23; research 0051 R7): AshLight's Python
logs are bounded, share one format and open every start with the banner.

core.log, keepalive.log and tc-bridge.log move to `<name>.1` at start when
over 1 MB (one old file kept; a failed move keeps appending); core.log also
rolls in run at 2 MB; every line is `<UTC ISO stamp> <LEVEL> <name>[<pid>]
<message>` with no absolute path; the first line of a start is the build
banner (version plus 12 hex). Also the folded RUN-CALC-PRIORITY (F-107)
children that have no test file of their own: the drift trial's two
children and the snapshot build step (server/al/prio.py).
"""

import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import VERSION, buildinfo, logs, paths, prio
from server.al import keepalive as ka

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tc_drift  # noqa: E402

MB = 1024 * 1024
STAMP = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z"
LINE = re.compile(r"^" + STAMP + r" (DEBUG|INFO|WARNING|ERROR|CRITICAL) [\w.-]+\[\d+\] ")
BANNER = re.compile(r"^" + STAMP + r" INFO al\[\d+\] AshLight " + re.escape(VERSION)
                    + r"\+[0-9a-f]{12}(\.dev)? core start \(pid \d+, python [\d.]+")
# an absolute path: a drive path, a UNC share or a POSIX system folder
ABS = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[^\s\\]+\\|(?<![\w.:/])/(home|Users|tmp)/")


def _env(tmp_path):
    env = dict(os.environ)
    env.pop(paths.HOME_ENV, None)
    env[paths.SIDECAR_ENV] = str(tmp_path / "sidecar")
    env[paths.RUNTIME_ENV] = str(tmp_path / "runtime")
    return env


def _log_paths(tmp_path):
    return paths.all_runtime_paths(_env(tmp_path))


def _start_core_logging(tmp_path, tail=""):
    """setup_logging in a fresh interpreter (the real start), one INFO line,
    then `tail` (Python source)."""
    code = ("import logging, sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from server.al import __main__ as entry\n"
            "entry.setup_logging(True)\n"
            "logging.getLogger('al').info('listening on 127.0.0.1:0')\n" + tail)
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=_env(tmp_path),
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=120)


def _lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


# -- rotation at start --------------------------------------------------------

def test_1_1_mb_log_becomes_dot_1_and_new_file_starts_with_banner(tmp_path):
    p = _log_paths(tmp_path)
    core_log = p["core_log"]
    core_log.parent.mkdir(parents=True)
    old = b"old line\n" * (int(1.1 * MB) // 9)
    core_log.write_bytes(old)
    r = _start_core_logging(tmp_path)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert logs.backup_path(core_log).read_bytes() == old  # one old file kept
    first = _lines(core_log)[0]
    assert "AshLight" in first and " core start (pid " in first
    assert LINE.match(first)
    # a small file is left alone at the next start: it appends
    r = _start_core_logging(tmp_path)
    assert r.returncode == 0
    assert logs.backup_path(core_log).read_bytes() == old
    assert sum(" core start (pid " in ln for ln in _lines(core_log)) == 2

    # keepalive.log: the same scheme, its banner first
    kl = p["keepalive_log"]
    kl.write_bytes(old)
    log = ka._file_logger(kl)
    log("core launched (pid 1)")
    assert logs.backup_path(kl).read_bytes() == old
    lines = _lines(kl)
    assert " keepalive start (pid " in lines[0] and "AshLight" in lines[0]
    assert lines[1].endswith("INFO keepalive[%d] core launched (pid 1)" % os.getpid())


def test_rotation_replaces_the_older_backup_and_a_failed_move_keeps_appending(
        tmp_path, monkeypatch):
    f = tmp_path / "x.log"
    logs.backup_path(f).write_bytes(b"oldest")
    f.write_bytes(b"a" * (MB + 1))
    assert logs.rotate_at_start(f) is True
    assert logs.backup_path(f).stat().st_size == MB + 1 and not f.exists()
    f.write_bytes(b"b" * MB)  # exactly 1 MB is not over it
    assert logs.rotate_at_start(f) is False and f.exists()
    assert logs.rotate_at_start(tmp_path / "missing.log") is False

    def held(src, dst):
        raise PermissionError("held open")
    f.write_bytes(b"c" * (MB + 1))
    monkeypatch.setattr(logs.os, "replace", held)
    assert logs.rotate_at_start(f) is False
    assert logs.start_file(f, "keepalive", "keepalive") is True
    assert f.stat().st_size > MB + 1  # appended to the old file


def test_first_core_log_line_is_version_plus_12_hex(tmp_path):
    if buildinfo.commit() is None:
        pytest.skip("no commit known (not a checkout and no BUILD file)")
    r = _start_core_logging(tmp_path)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    lines = _lines(_log_paths(tmp_path)["core_log"])
    assert BANNER.match(lines[0]), lines[0]
    assert lines[1].endswith("INFO al[%s] listening on 127.0.0.1:0" % lines[0].split("[")[1]
                             .split("]")[0])
    # faulthandler's own file opens with the same banner
    fault = logs.fault_path(_log_paths(tmp_path)["core_log"])
    assert " core start (pid " in _lines(fault)[0]


# -- in-run backstop (C23) ----------------------------------------------------

def _logger(handler, name):
    lg = logging.getLogger(name)
    lg.handlers[:] = [handler]
    lg.propagate = False
    lg.setLevel(logging.INFO)
    return lg


def test_core_log_rolls_at_2_mb_in_run(tmp_path):
    f = tmp_path / "core.log"
    h = logs.BackstopHandler(f)
    h.setFormatter(logs.Formatter())
    lg = _logger(h, "al.test.backstop")
    try:
        assert h.max_bytes == logs.BACKSTOP_BYTES == 2 * MB
        filler = "x" * 1000
        n = 0
        while h.rolls == 0 and n < 5000:
            lg.info("record %d %s", n, filler)
            n += 1
        assert h.rolls == 1
        old = logs.backup_path(f)
        assert old.stat().st_size >= 2 * MB
        assert old.stat().st_size < 2 * MB + 2048  # rolled at the line past 2 MB
        lines = _lines(f)
        assert " core start (pid " in lines[0] and "continued after a roll" in lines[0]
        assert lines[1].endswith("record %d %s" % (n - 1, filler))
        lg.info("after")
        assert _lines(f)[-1].endswith(" after") and h.rolls == 1
    finally:
        lg.handlers[:] = []
        h.close()


def test_a_failed_in_run_roll_keeps_appending(tmp_path, monkeypatch):
    f = tmp_path / "core.log"
    h = logs.BackstopHandler(f, max_bytes=4096)
    h.setFormatter(logs.Formatter())
    lg = _logger(h, "al.test.backstop2")

    def held(src, dst):
        raise PermissionError("held open")
    monkeypatch.setattr(logs.os, "replace", held)
    try:
        for i in range(80):
            lg.info("line %d %s", i, "y" * 100)
        assert h.rolls == 0 and not logs.backup_path(f).exists()
        assert sum(1 for ln in _lines(f) if " line " in ln) == 80  # nothing lost
        monkeypatch.undo()
        for i in range(80):
            lg.info("more %d %s", i, "z" * 100)
        assert h.rolls >= 1 and logs.backup_path(f).exists()
    finally:
        lg.handlers[:] = []
        h.close()


# -- one format, no absolute path ---------------------------------------------

def test_stamp_is_utc_iso_with_level_and_pid():
    assert logs.stamp(0) == "1970-01-01T00:00:00.000Z"
    assert logs.stamp(86400 * 365 + 0.25) == "1971-01-01T00:00:00.250Z"
    assert logs.format_line("al", "warning", "x", now=0, pid=7) == \
        "1970-01-01T00:00:00.000Z WARNING al[7] x"
    rec = logging.LogRecord("al.http", logging.ERROR, __file__, 1, "bad %s", ("thing",),
                            None)
    line = logs.Formatter().format(rec)
    assert LINE.match(line) and line.endswith(" ERROR al.http[%d] bad thing" % os.getpid())
    rec.created = 0.0
    assert logs.Formatter().format(rec).startswith("1970-01-01T00:00:00.000Z ")
    banner = logs.banner("core", pid=42, build="0.1.0+0123456789ab")
    assert banner.startswith("AshLight 0.1.0+0123456789ab core start (pid 42, python ")


def test_no_log_line_holds_an_absolute_path(tmp_path):
    # built at run time so the leak sweep sees no machine path
    drive = "C" + ":" + "\\".join(["", "Users", "someone", "fixture"])
    unc = "\\\\" + "\\".join(["host", "share", "Client.txt"])
    posix = "/" + "/".join(["home", "someone", "a.py"])
    inside = str(ROOT / "server" / "al" / "core.py")
    msgs = [f"demo mode: fixture {drive}, scratch {tmp_path}",
            f"cannot open {unc} (denied)", f"read {posix}", f"at {inside}:12",
            f"quoted '{tmp_path / 'with space' / 'x.log'}'", "route /api/health kept"]
    f = tmp_path / "core.log"
    h = logs.BackstopHandler(f)
    h.setFormatter(logs.Formatter())
    lg = _logger(h, "al.test.paths")
    try:
        for m in msgs:
            lg.warning("%s", m)
        try:
            raise OSError(f"[Errno 2] No such file: '{tmp_path / 'gone.json'}'")
        except OSError:
            lg.exception("load failed")
    finally:
        lg.handlers[:] = []
        h.close()
    text = f.read_text(encoding="utf-8")
    assert not ABS.search(text), text
    assert "someone" not in text and "host" not in text and str(tmp_path) not in text
    assert "server/al/core.py:12" in text  # inside the checkout: relative
    assert "route /api/health kept" in text  # a route is not a path
    assert 'File "tests/test_logs.py", line' in text  # traceback frames relative
    assert "<path>" in text

    # a real start's files hold none either
    r = _start_core_logging(tmp_path, tail=(
        "logging.getLogger('al').info('scratch %s', sys.executable)\n"))
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    p = _log_paths(tmp_path)
    for name in ("core_log",):
        body = p[name].read_text(encoding="utf-8")
        assert not ABS.search(body), body
    assert not ABS.search(logs.fault_path(p["core_log"]).read_text(encoding="ascii"))
    kl = p["keepalive_log"]
    log = ka._file_logger(kl)
    log(f"core launch failed: [WinError 2] {drive}")
    body = kl.read_text(encoding="ascii")
    assert not ABS.search(body) and " WARNING keepalive[" in body


# -- RUN-CALC-PRIORITY: the drift trial and the snapshot build step -----------

def test_below_normal_flag_only_on_windows():
    if os.name == "nt":
        assert prio.below_normal(0x08000000) == 0x08000000 | 0x00004000
    else:
        assert prio.below_normal(0) == 0


def test_drift_trial_children_start_below_normal(tmp_path, monkeypatch):
    seen = []

    class Proc:
        pid = 4242

    def popen(argv, **kw):
        seen.append(("popen", kw.get("creationflags", 0)))
        return Proc()

    def run(argv, **kw):
        seen.append(("run", kw.get("creationflags", 0)))
        Path(argv[-1].split("=", 1)[1]).write_text(
            '<testsuite tests="0" failures="0" errors="0" skipped="0"/>', encoding="utf-8")

        class R:
            returncode = 0
        return R()

    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "sidecar"))
    monkeypatch.setattr(tc_drift.subprocess, "Popen", popen)
    monkeypatch.setattr(tc_drift.subprocess, "run", run)
    assert tc_drift.launch_trial(tmp_path, "v1.2.3") == 4242
    tc_drift.run_bridge_tests(tmp_path / "pins.json", tmp_path / "junit.xml", {})
    assert [k for k, _ in seen] == ["popen", "run"]
    for _, flags in seen:
        assert flags & prio.BELOW_NORMAL if os.name == "nt" else flags == 0


def test_snapshot_build_step_runs_below_normal(monkeypatch):
    ps = (ROOT / "scripts" / "build.ps1").read_text(encoding="ascii")
    block = ps.split("# TC-SNAP", 1)[1].split("# Source fingerprint", 1)[0]
    assert "@('-m', 'server.al.prio', 'server.al.theorycraft.snapshot')" in block
    seen = {}

    class Child:
        def wait(self):
            return 3

    def popen(argv, **kw):
        seen["argv"], seen["flags"] = argv, kw.get("creationflags", 0)
        return Child()
    assert prio.run_module("server.al.theorycraft.snapshot", ["--opt-in"], popen=popen) == 3
    assert seen["argv"] == [sys.executable, "-m", "server.al.theorycraft.snapshot",
                            "--opt-in"]
    assert seen["flags"] == prio.below_normal(0)
    with pytest.raises(ValueError):
        prio.run_module("os", popen=popen)
    assert prio.main(["subprocess"]) == 2  # only AshLight's own modules
