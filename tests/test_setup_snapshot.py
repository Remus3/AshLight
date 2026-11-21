"""DATA-SNAP-SETUP: scripts/setup.ps1 runs the game-data snapshot when web
data is already on (decisions 0009 / 0013, AUDIT-SNAPSHOT-OPTIN).

- One setup command fills the sidecar game-data cache once 'Use web data'
  is ticked (config/local.json "web_data": true, strictly a JSON true); no
  second command.
- While web data is off the step makes no request and starts no process;
  setup never passes --opt-in (only build.ps1 -Snapshot forces a run).
- -NoSnapshot and AL_NO_SNAPSHOT=1 skip the step and win.
- The step runs the snapshot module at below-normal priority through
  server.al.prio; a failing or offline source never fails setup.
The PowerShell runs are Windows PowerShell 5.1 with the step function cut
out of setup.ps1 by the parser (setup.ps1 itself never runs), against a
stub repo whose server.al.prio only records its arguments: no network.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / "scripts" / "setup.ps1"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
FN = "Invoke-AlSnapshotStep"

STUB_PRIO = (
    "import json, os, sys\n"
    "out = os.environ['PDATA_SNAP_SETUP_OUT']\n"
    "with open(out, 'w', encoding='ascii') as fh:\n"
    "    json.dump(sys.argv[1:], fh)\n"
    "print('snapshot: stub ran')\n"
    "sys.exit(int(os.environ.get('PDATA_SNAP_SETUP_RC', '0')))\n"
)


def _text():
    return SETUP.read_bytes().decode("ascii")


def _ps_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def _stub_repo(tmp_path, config):
    repo = tmp_path / "repo"
    pkg = repo / "server" / "al"
    pkg.mkdir(parents=True)
    (repo / "server" / "__init__.py").write_text("", encoding="ascii")
    (pkg / "__init__.py").write_text("", encoding="ascii")
    (pkg / "prio.py").write_text(STUB_PRIO, encoding="ascii")
    (repo / "config").mkdir()
    if config is not None:
        raw = config if isinstance(config, str) else json.dumps(config)
        (repo / "config" / "local.json").write_text(raw, encoding="ascii")
    return repo


def _run_step(tmp_path, config, skip=False, env_extra=None, rc=0):
    repo = _stub_repo(tmp_path, config)
    out = tmp_path / "argv.json"
    log = tmp_path / "snap.log"
    prog = (
        "$ErrorActionPreference = 'Stop'\n"
        "Set-StrictMode -Version 2\n"
        "$__ast = [System.Management.Automation.Language.Parser]::ParseFile("
        + _ps_str(SETUP) + ", [ref]$null, [ref]$null)\n"
        "$__fns = @($__ast.FindAll({ param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "($n.Name -eq '" + FN + "' -or $n.Name -eq 'Test-AlWebDataOn') }, $true))\n"
        "if ($__fns.Count -ne 2) { throw 'function missing' }\n"
        "foreach ($f in $__fns) { . ([scriptblock]::Create($f.Extent.Text)) }\n"
        "$r = " + FN + " " + _ps_str(sys.executable) + " " + _ps_str(repo) + " "
        + _ps_str(log) + " " + ("$true" if skip else "$false") + "\n"
        "Write-Output ('<<' + $r + '>>')\n")
    env = dict(os.environ)
    env.pop("AL_NO_SNAPSHOT", None)
    env["PDATA_SNAP_SETUP_OUT"] = str(out)
    env["PDATA_SNAP_SETUP_RC"] = str(rc)
    env.update(env_extra or {})
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", prog], capture_output=True, text=True, timeout=90,
                       env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"<<(.*?)>>", r.stdout)
    assert m, r.stdout + r.stderr
    argv = json.loads(out.read_text(encoding="ascii")) if out.exists() else None
    return m.group(1), argv, log


needs_ps = pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")


@needs_ps
def test_web_data_on_runs_the_snapshot_once(tmp_path):
    status, argv, log = _run_step(tmp_path, {"web_data": True})
    assert argv == ["server.al.theorycraft.snapshot"], argv
    assert "--opt-in" not in argv
    assert status.startswith("rc 0"), status
    assert "snapshot: stub ran" in log.read_text(encoding="ascii")


@needs_ps
@pytest.mark.parametrize("config", [None, {}, {"web_data": False}, {"web_data": "true"},
                                    {"web_data": 1}, "not json"])
def test_web_data_off_starts_nothing(tmp_path, config):
    status, argv, _ = _run_step(tmp_path, config)
    assert argv is None
    assert status.startswith("skipped (web_data off"), status


@needs_ps
def test_no_snapshot_switch_and_env_win(tmp_path):
    status, argv, _ = _run_step(tmp_path, {"web_data": True}, skip=True)
    assert argv is None and status == "skipped (NoSnapshot)"
    status, argv, _ = _run_step(tmp_path / "e", {"web_data": True},
                                env_extra={"AL_NO_SNAPSHOT": "1"})
    assert argv is None and status == "skipped (NoSnapshot)"


@needs_ps
def test_a_failing_snapshot_never_fails_setup(tmp_path):
    status, argv, _ = _run_step(tmp_path, {"web_data": True}, rc=1)
    assert argv == ["server.al.theorycraft.snapshot"]
    assert status.startswith("rc 1"), status


def test_setup_wires_the_step_before_the_node_check():
    text = _text()
    assert re.search(r"\[switch\]\$NoSnapshot\b", text)
    call = text.index("$snapStatus = " + FN)
    assert call < text.index("$node = Get-Command node")
    assert text.index("\nfunction " + FN) < call
    assert "Write-AlLog \"setup: game-data snapshot $snapStatus\"" in text
    # the step goes through server.al.prio (below-normal) and never forces
    body = text.split("\nfunction " + FN, 1)[1].split("\n}\n", 1)[0]
    assert "'server.al.prio'" in body and "'server.al.theorycraft.snapshot'" in body
    assert "--opt-in" not in body
    assert "DATA-SNAP-SETUP" in text


def test_setup_parses_in_windows_powershell():
    if PS51 is None:
        pytest.skip("Windows PowerShell 5.1 only")
    prog = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            + _ps_str(SETUP) + ", [ref]$null, [ref]$e); if ($e.Count) { $e | % { $_.Message };"
            " exit 1 }")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", prog],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
