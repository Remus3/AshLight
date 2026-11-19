"""RUN-DURABLE-CRLF (F-014): core.alive, keepalive.json, overlay.pid,
restart.request and token.reuse go through jsonfile.write_text, so they are
ASCII + LF (no CRLF from text-mode writes on Windows) and atomic, and
scripts/stop.ps1 and scripts/run.ps1 still read them.

Everything runs on a tmp runtime (AL_RUNTIME_DIR); the PowerShell case
loads only the reading functions of the two scripts (parsed with the 5.1
AST), so no process is started or stopped.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import __main__ as entry
from server.al import hotreload, jsonfile, paths, ports, procs
from server.al import keepalive as ka

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "scripts" / "stop.ps1"
RUN = ROOT / "scripts" / "run.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
TEST_PORT = ports.PORT_BLOCK[1] - 1  # a number only; nothing binds it
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _lf_only(path):
    data = Path(path).read_bytes()
    assert data.endswith(b"\n"), data
    assert b"\r" not in data, data
    data.decode("ascii")
    return data


def _no_tmp_left(folder):
    assert not [p.name for p in Path(folder).iterdir() if p.name.endswith(".tmp")]


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _supervisor(runtime, clock=None, **kw):
    return ka.Keepalive(runtime=runtime, port=TEST_PORT, launch=lambda: 0,
                        pid_alive=lambda p: False, health=lambda: False,
                        terminate=lambda p: True, now=clock or _Clock(),
                        created=lambda p: 0, **kw)


def _write_live_files(runtime):
    """core.alive and keepalive.json naming this (python) test process, as
    the real writers write them."""
    me = os.getpid()
    created = ka.process_created(me)
    entry.write_heartbeat(runtime / ka.HEARTBEAT_FILE, me, TEST_PORT,
                          now=1234.5, created=created)
    sup = _supervisor(runtime)
    sup._write_state("watching")
    return me, created


def test_heartbeat_state_and_overlay_pid_end_in_lf(tmp_path, monkeypatch):
    me, created = _write_live_files(tmp_path)
    hb = _lf_only(tmp_path / ka.HEARTBEAT_FILE)
    want = {"pid": me, "port": TEST_PORT, "updated": 1234.5}
    if created:
        want["created"] = int(created)
    assert json.loads(hb) == want
    assert ka.read_heartbeat(tmp_path / ka.HEARTBEAT_FILE)["pid"] == me
    st = json.loads(_lf_only(tmp_path / ka.STATE_FILE))
    assert st["pid"] == me and st["status"] == "watching" and st["port"] == TEST_PORT

    # overlay.pid: a fake electron (record_overlay only writes for one)
    monkeypatch.setattr(procs, "is_ours", lambda pid, image, created=0: True)
    monkeypatch.setattr(ka, "process_created", lambda pid: 777)
    monkeypatch.setattr(ka, "image_name", lambda pid: "electron.exe")
    runtime = tmp_path / "fresh"  # record_overlay makes the dir
    assert procs.record_overlay(runtime, 4321) is True
    rec = json.loads(_lf_only(runtime / procs.OVERLAY_PID_FILE))
    assert rec["pid"] == 4321 and rec["created"] == 777 and rec["image"] == "electron.exe"
    assert procs.overlay_main_pid(runtime) == 4321
    # a rewrite replaces the file in place, still LF, no temp file left
    entry.write_heartbeat(tmp_path / ka.HEARTBEAT_FILE, me, TEST_PORT, now=1300.0)
    assert json.loads(_lf_only(tmp_path / ka.HEARTBEAT_FILE))["updated"] == 1300.0
    _no_tmp_left(tmp_path)
    _no_tmp_left(runtime)


def test_heartbeat_is_written_unsynced(tmp_path, monkeypatch):
    calls = []
    real = jsonfile.write_text

    def spy(path, text, backup=False, sync=True):
        calls.append((Path(path).name, sync))
        return real(path, text, backup=backup, sync=sync)

    monkeypatch.setattr(jsonfile, "write_text", spy)
    entry.write_heartbeat(tmp_path / ka.HEARTBEAT_FILE, 1, TEST_PORT, now=1.0)
    _supervisor(tmp_path)._write_state("started")
    assert calls == [(ka.HEARTBEAT_FILE, False), (ka.STATE_FILE, True)]


class _CodeWatch:
    def __init__(self):
        self.sig = 1

    def signature(self):
        return self.sig


def test_flag_files_end_in_lf(tmp_path):
    hotreload.mark_token_reuse(tmp_path, now=55.0)
    assert json.loads(_lf_only(tmp_path / hotreload.TOKEN_REUSE_FILE)) == {"at": 55.0}

    clock = _Clock()
    watch = _CodeWatch()
    sup = _supervisor(tmp_path, clock=clock, code_watch=watch,
                      preflight=lambda: (True, None))
    watch.sig = 2
    assert sup._code_step(clock.t) == "reload-pending"
    clock.t += sup.reload_debounce_s + 1
    sup._code_step(clock.t)
    assert _lf_only(tmp_path / hotreload.RESTART_FILE) == b"reload\n"
    assert sup.reloading_since == clock.t
    _no_tmp_left(tmp_path)


def _function_loader(script, name):
    """PowerShell that defines one function of `script`, taken from its 5.1
    AST, at the current scope (nothing else of the script runs)."""
    return (
        "$e=$null; $ast=[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$e); "
        "if ($e.Count) { throw 'parse errors' }; "
        "$fn=$ast.Find({ param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] "
        f"-and $n.Name -eq '{name}' }}, $true); "
        f"if (-not $fn) {{ throw 'no {name}' }}; "
        ". ([scriptblock]::Create($fn.Extent.Text)); "
    )


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_stop_and_run_scripts_read_lf_pid_and_state_files(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    me, created = _write_live_files(runtime)
    for name in (ka.HEARTBEAT_FILE, ka.STATE_FILE):
        _lf_only(runtime / name)
    alive = runtime / ka.HEARTBEAT_FILE
    command = (
        "$ErrorActionPreference='Stop'; Set-StrictMode -Version 2; "
        + _function_loader(STOP, "Get-AlCorePid")
        + _function_loader(RUN, "Get-AlPlan")
        + f"$alive='{alive}'; $py='{sys.executable}'; $Repo='{ROOT}'; "
        + f"$wantOverlay=$true; $electron='{tmp_path / 'no-electron.exe'}'; "
        + "$plan = Get-AlPlan; "
        + "@{ stop_core_pid = (Get-AlCorePid); plan = $plan } | ConvertTo-Json -Depth 6 -Compress"
    )
    env = dict(os.environ)
    env[paths.RUNTIME_ENV] = str(runtime)
    env.pop(procs.ELECTRON_DIR_ENV, None)  # no electron dir scan for a tmp runtime
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", command],
                       capture_output=True, text=True, timeout=120, env=env,
                       cwd=str(tmp_path), creationflags=FLAGS)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    # stop.ps1 parses the LF core.alive itself
    assert out["stop_core_pid"] == me
    # run.ps1's plan (procs status) reads the LF core.alive and keepalive.json
    status = out["plan"]["status"]
    assert status["core"] == {"live": True, "pid": me}
    assert status["supervisor"]["live"] is True and status["supervisor"]["pid"] == me
    assert status["overlay"]["live"] is False
    assert out["plan"]["start"] == []  # overlay missing: nothing to start
