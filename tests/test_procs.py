"""OPS-STOP / OPS-RUN-IDEMP: the process registry (server/al/procs.py) and
scripts/stop.ps1 stop every AshLight process and nothing else.

Everything runs on a tmp runtime (AL_RUNTIME_DIR), a tmp sidecar and a port
that is not the live core's; the fake overlay is a renamed copy of the Python
interpreter called electron.exe in a tmp "electron dist" dir named by
AL_ELECTRON_DIR, so no live AshLight, Electron app or game is ever reached.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from server.al import keepalive as ka
from server.al import paths, ports, procs

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "scripts" / "stop.ps1"
RUN = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
TEST_PORT = ports.PORT_BLOCK[1] - 1  # never the live core's port
WIN = pytest.mark.skipif(sys.platform != "win32", reason="Windows process APIs")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _state(core=False, sup=False, ovl=False):
    return {"core": {"live": core, "pid": 0}, "supervisor": {"live": sup, "pid": 0},
            "overlay": {"live": ovl, "pid": 0, "pids": []}}


# -- the run.ps1 decision ----------------------------------------------------

def test_plan_starts_only_what_is_missing():
    assert procs.plan(_state()) == ["core", "supervisor", "overlay"]
    assert procs.plan(_state(core=True)) == ["supervisor", "overlay"]
    assert procs.plan(_state(core=True, sup=True)) == ["overlay"]
    assert procs.plan(_state(True, True, True)) == []


def test_plan_overlay_independent_of_browser_and_opt_out():
    # -NoBrowser has no say in it; -NoOverlay or a missing install does
    assert "overlay" not in procs.plan(_state(True, True), overlay_wanted=False)
    assert "overlay" not in procs.plan(_state(True, True), overlay_installed=False)


def test_two_runs_converge_to_one_of_each():
    live = {"core": 0, "supervisor": 0, "overlay": 0}

    def run_once():
        st = _state(live["core"] > 0, live["supervisor"] > 0, live["overlay"] > 0)
        for comp in procs.plan(st):
            live[comp] += 1

    run_once()
    run_once()
    run_once()
    assert live == {"core": 1, "supervisor": 1, "overlay": 1}


def test_run_script_uses_the_plan_and_has_no_overlay_gate_on_browser():
    text = RUN.read_text(encoding="ascii")
    assert "server.al.procs" in text and "record-overlay" in text
    assert "-contains 'supervisor'" in text and "-contains 'overlay'" in text
    assert "NoOverlay" in text
    assert "if ($Overlay)" not in text  # the overlay is no longer opt-in


def test_stop_script_calls_the_registry():
    text = STOP.read_text(encoding="ascii")
    assert "server.al.procs stop" in text
    assert "stop.request" in text


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
@pytest.mark.parametrize("script", [RUN, STOP])
def test_scripts_parse_in_powershell_51(script):
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                        f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0", r.stdout


# -- ownership checks ----------------------------------------------------------

def test_scan_off_for_tmp_runtime_without_explicit_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.RUNTIME_ENV, str(tmp_path))
    monkeypatch.delenv(procs.ELECTRON_DIR_ENV, raising=False)
    assert procs.electron_dir() is None
    monkeypatch.setenv(procs.ELECTRON_DIR_ENV, str(tmp_path / "e"))
    assert procs.electron_dir() == (tmp_path / "e").resolve()


@WIN
def test_is_ours_checks_image_and_creation_time():
    me = os.getpid()
    created = ka.process_created(me)
    assert created > 0
    assert procs.is_ours(me, "python", created)
    assert not procs.is_ours(me, "python", created + 1)  # a reused pid
    assert not procs.is_ours(me, "electron.exe")
    assert not procs.is_ours(0, "python")


@WIN
def test_records_with_a_dead_or_foreign_pid_are_not_ours(tmp_path):
    p = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=FLAGS)
    p.wait(timeout=30)
    (tmp_path / ka.STATE_FILE).write_text(json.dumps({"pid": p.pid, "created": 1}),
                                          encoding="ascii")
    (tmp_path / procs.OVERLAY_PID_FILE).write_text(json.dumps({"pid": os.getpid()}),
                                                   encoding="ascii")
    assert procs.supervisor_pid(tmp_path) == 0
    # this test process is python, not electron.exe: never treated as overlay
    assert procs.overlay_pids(tmp_path, edir=tmp_path / "none", processes=[]) == []
    assert procs.record_overlay(tmp_path, os.getpid()) is False


def test_supervisor_lock_is_the_liveness_signal(tmp_path):
    assert procs.supervisor_locked(tmp_path) is False
    fh = ka.acquire_lock(tmp_path)
    try:
        assert procs.supervisor_locked(tmp_path) is True
    finally:
        ka.release_lock(fh)
    assert procs.supervisor_locked(tmp_path) is False


def test_stop_request_cancels_a_pending_restart(tmp_path):
    launched = []
    sup = ka.Keepalive(runtime=tmp_path, port=TEST_PORT, launch=lambda: launched.append(1) or 1,
                       pid_alive=lambda pid: False, health=lambda: False,
                       terminate=lambda pid: True, now=lambda: 1000.0)
    assert sup.step() == "waiting"  # no core: a restart is pending
    (tmp_path / ka.STOP_FILE).write_text("stop\n", encoding="ascii")
    assert sup.step() == "user-stop"
    assert launched == []


def test_status_reports_the_recorded_main_overlay_pid(tmp_path, monkeypatch):
    """OPS-OVL-PID: a lower-pid Electron child (network utility) never
    becomes the overlay "pid"; it stays in "pids"."""
    main, child = 7000, 300
    (tmp_path / procs.OVERLAY_PID_FILE).write_text(
        json.dumps({"pid": main, "created": 5}), encoding="ascii")
    monkeypatch.setattr(procs, "is_ours",
                        lambda pid, prefix, created=0: prefix == procs.ELECTRON_IMAGE
                        and pid in (main, child))
    monkeypatch.setattr(procs, "list_processes",
                        lambda: [(child, "electron.exe"), (main, "electron.exe"),
                                 (42, "PathOfExile.exe")])
    monkeypatch.setattr(procs.ka, "image_path",
                        lambda pid: str(tmp_path / "dist" / "electron.exe"))
    st = procs.status(tmp_path, edir=tmp_path / "dist")["overlay"]
    assert st == {"live": True, "pid": main, "pids": [child, main]}
    # no record (an older run): the scan still reports the overlay live
    (tmp_path / procs.OVERLAY_PID_FILE).unlink()
    st = procs.status(tmp_path, edir=tmp_path / "dist")["overlay"]
    assert st["live"] and st["pid"] == child and st["pids"] == [child, main]
    assert procs.overlay_main_pid(tmp_path) == 0


def test_run_script_no_op_line_prints_the_status_pid():
    text = RUN.read_text(encoding="ascii")
    # DESKTOP-CLIENT (decision 0041): the "overlay" component is the client
    assert "client already running (pid $($plan.status.overlay.pid)" in text


# -- end to end on a tmp runtime ---------------------------------------------

def _fake_electron(folder):
    """A renamed python.exe (plus its DLLs) called electron.exe."""
    base = Path(sys.base_prefix)
    src = base / "python.exe"
    if not src.exists():
        pytest.skip("no python.exe next to the base prefix")
    folder.mkdir(parents=True)
    shutil.copy2(src, folder / "electron.exe")
    for dll in base.glob("*.dll"):
        shutil.copy2(dll, folder / dll.name)
    return folder / "electron.exe"


def _spawn_fake(exe, env):
    p = subprocess.Popen([str(exe), "-c", "import time; time.sleep(120)"],
                         env={**env, "PYTHONHOME": sys.base_prefix},
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=FLAGS)
    time.sleep(0.5)
    if p.poll() is not None:
        pytest.skip("renamed interpreter does not start here")
    return p


def _wait(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.2)
    return None


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return {}


@WIN
@pytest.mark.slow
@pytest.mark.server
@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_stop_script_leaves_no_ashlight_process(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    edir = tmp_path / "electron" / "dist"
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(tmp_path / "AL")
    env[procs.ELECTRON_DIR_ENV] = str(edir)
    env["AL_HEARTBEAT_S"] = "0.5"
    ours_exe = _fake_electron(edir)
    other_exe = _fake_electron(tmp_path / "other-app")  # an unrelated electron.exe

    spawned = []
    try:
        sup_cmd = [sys.executable, "-m", "server.al.keepalive", "--port", str(TEST_PORT),
                   "--poll", "0.5", "--backoff", "0.5,1,2", "--core-args", "--no-tail"]
        sup = subprocess.Popen(sup_cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=FLAGS)
        spawned.append(sup)
        core = _wait(lambda: _read(runtime / "core.alive").get("pid"), 30)
        assert core, "core never wrote a heartbeat"
        ovl = _spawn_fake(ours_exe, env)
        child = _spawn_fake(ours_exe, env)  # an unrecorded renderer-like child
        other = _spawn_fake(other_exe, env)
        spawned += [ovl, child, other]

        old = {k: os.environ.get(k) for k in (paths.RUNTIME_ENV, procs.ELECTRON_DIR_ENV)}
        os.environ[paths.RUNTIME_ENV] = str(runtime)
        os.environ[procs.ELECTRON_DIR_ENV] = str(edir)
        try:
            assert procs.record_overlay(runtime, ovl.pid)
            st = procs.status(runtime)
            assert st["core"]["pid"] == core
            assert st["supervisor"]["live"] and st["supervisor"]["pid"] == sup.pid
            assert sorted(st["overlay"]["pids"]) == sorted([ovl.pid, child.pid])
            assert other.pid not in st["overlay"]["pids"]
            # a re-run of run.ps1 would start nothing (OPS-RUN-IDEMP)
            assert procs.plan(st) == []
            # a second supervisor exits at once (single-instance lock)
            second = subprocess.run(sup_cmd, cwd=str(ROOT), env=env, timeout=30,
                                    capture_output=True, creationflags=FLAGS)
            assert second.returncode == 0
            assert procs.status(runtime)["supervisor"]["pid"] == sup.pid
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                            "Bypass", "-File", str(STOP), "-TimeoutSec", "15"],
                           cwd=str(ROOT), env=env, capture_output=True, text=True,
                           timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
        assert sup.wait(timeout=15) == 0
        for pid in (core, ovl.pid, child.pid):
            assert _wait(lambda: not ka.pid_alive(pid), 10), f"pid {pid} left running"
        assert ka.pid_alive(other.pid), "an unrelated electron.exe was stopped"
        assert not (runtime / procs.OVERLAY_PID_FILE).exists()
        assert not (runtime / "core.alive").exists()
        log = (tmp_path / "AL" / "Logs" / "run.log").read_text(encoding="ascii")
        assert "supervisor exited" in log and "overlay stopped (2 process(es))" in log
    finally:
        for p in spawned:
            if p.poll() is None:
                p.kill()
        pid = _read(runtime / "core.alive").get("pid")
        if pid and procs.is_ours(pid, "python"):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
