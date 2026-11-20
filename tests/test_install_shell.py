"""REL-INSTALL-SHELL (finding F-050, DEP-09): the installer's shell entries
and its first-run config.

server/al/install/shell.py rewrites, at every version switch, the two
AshLight shortcuts, the per-user uninstall entry, <home>/uninstall.ps1 and
(when it exists and is ours) the opt-in logon task's action, and reads each
back. server/al/install/firstrun.py writes <home>/data/local.json once,
with player keys only.

Every shell effect here is injected: FakeShell stands in for the one runner
and keeps its shortcuts, uninstall entry and task in a dict, with the
al_shell.ps1 "is it ours" rule. No PowerShell function runs; the only
PowerShell start is a parse-only check of the generated script (no
statement is executed). Homes live under pytest tmp folders.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.al import paths, settingsio
from server.al.install import firstrun, shell
from server.al.install import home as homemod

ROOT = Path(__file__).resolve().parents[1]
SHELL_SRC = ROOT / "server" / "al" / "install" / "shell.py"
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None
WHEN = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
PY_RT = "python-3.12.7"
EL_RT = "electron-45.3.3"
OLD, NEW = "0.1.0", "0.2.0"


def _under(path, root):
    p = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
    r = os.path.normcase(os.path.abspath(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


class FakeShell:
    """The runner, with al_shell.ps1's rules on an in-memory shell."""

    def __init__(self, links=None, entry=None, task=None, sticky=True):
        self.links = links if links is not None else {"Programs": None, "Desktop": None}
        self.entry = entry
        self.task = task
        self.sticky = sticky
        self.requests = []

    def __call__(self, request):
        self.requests.append(json.loads(json.dumps(request)))
        owner = request["owner_root"]
        link = request["shortcut"]
        want_link = {k: link[k] for k in ("target", "arguments", "workdir", "icon")}
        states = []
        for name in ("Programs", "Desktop"):
            have = self.links.get(name)
            if have is not None and not _under(have["target"], owner):
                states.append("elsewhere")
            elif have == want_link and self.sticky:
                states.append("current")
            else:
                if self.sticky:
                    self.links[name] = dict(want_link)
                states.append("written")
        ent = request["uninstall"]
        want_entry = dict(ent)
        if self.entry is not None and not _under(self.entry["install_location"], owner):
            entry_state = "elsewhere"
        elif self.entry == want_entry and self.sticky:
            entry_state = "current"
        else:
            if self.sticky:
                self.entry = want_entry
            entry_state = "written"
        t = request["task"]
        if self.task is None:
            task_state = "absent"
        elif not _under(self.task["workdir"], owner):
            task_state = "elsewhere"
        elif (self.sticky and self.task["execute"] == t["execute"]
              and self.task["arguments"] == t["arguments"]
              and self.task["workdir"] == t["workdir"]):
            task_state = "current"
        else:
            if self.sticky:
                self.task = dict(self.task, execute=t["execute"],
                                 arguments=t["arguments"], workdir=t["workdir"])
            task_state = "written"
        return {"shortcuts": states, "uninstall_entry": entry_state,
                "logon_task": task_state}


def _payload(home, version, uninstall=b"# uninstall v1\n"):
    base = Path(home) / "app" / version
    (base / "scripts").mkdir(parents=True, exist_ok=True)
    (base / "app" / "assets").mkdir(parents=True, exist_ok=True)
    (base / "scripts" / "al_shell.ps1").write_bytes(b"# al_shell\n")
    if uninstall is not None:
        (base / "scripts" / "uninstall.ps1").write_bytes(uninstall)
    return base


@pytest.fixture
def home(tmp_path, monkeypatch):
    for key in (paths.HOME_ENV, paths.SIDECAR_ENV, paths.RUNTIME_ENV):
        monkeypatch.delenv(key, raising=False)
    h = tmp_path / "AshLight"
    homemod.make_layout(h, private=lambda p: None)
    _payload(h, OLD)
    _payload(h, NEW, uninstall=b"# uninstall v2\n")
    homemod.write_marker(h, homemod.new_marker(OLD, PY_RT, EL_RT, now=WHEN))
    homemod.switch_marker(h, NEW, now=WHEN)
    return h


def _old_state(h):
    """Entries as an install of OLD left them, all inside the home."""
    app = h / "app" / OLD / "app"
    link = {"target": str(h / "runtime" / EL_RT / "electron.exe"),
            "arguments": '"' + str(app) + '" --client', "workdir": str(app),
            "icon": str(app / "assets" / "icon.ico")}
    entry = {"install_location": str(h), "version": OLD,
             "icon": str(app / "assets" / "icon.ico")}
    task = {"execute": str(h / "runtime" / PY_RT / "pythonw.exe"),
            "arguments": subprocess.list2cmdline(
                [str(h / "app" / OLD / "boot.py"), "server.al.autostart_entry"]),
            "workdir": str(h / "app" / OLD), "user": "player", "delay": "PT30S",
            "description": "AshLight autostart"}
    return link, entry, task


# --- rewrite: everything points at the active version -------------------------

def test_rewrite_moves_every_entry_to_the_active_version(home, tmp_path):
    link, entry, task = _old_state(home)
    fake = FakeShell(links={"Programs": dict(link), "Desktop": dict(link)},
                     entry=dict(entry), task=dict(task))
    scratch = tmp_path / "effects"
    out = shell.rewrite(home, NEW, runner=fake, effect_root=scratch)
    assert out == {"version": NEW, "uninstall_script": "written",
                   "shortcuts": ["written", "written"], "uninstall_entry": "written",
                   "logon_task": "written", "read_back": True}
    payload = home / "app" / NEW
    for name in ("Programs", "Desktop"):
        got = fake.links[name]
        assert got["target"] == str(home / "runtime" / EL_RT / "electron.exe")
        assert got["workdir"] == str(payload / "app")
        assert got["arguments"] == '"' + str(payload / "app") + '" --client'
        assert got["icon"] == str(payload / "app" / "assets" / "icon.ico")
    assert fake.entry == {"install_location": str(home), "version": NEW,
                          "icon": str(payload / "app" / "assets" / "icon.ico")}
    assert fake.task["workdir"] == str(payload)
    assert fake.task["execute"] == str(home / "runtime" / PY_RT / "pythonw.exe")
    assert fake.task["arguments"] == subprocess.list2cmdline(
        [str(payload / "boot.py"), "server.al.autostart_entry"])
    # the player's own task settings stay
    assert (fake.task["user"], fake.task["delay"], fake.task["description"]) == \
        ("player", "PT30S", "AshLight autostart")
    # one rewrite plus one read-back pass, both through the effect root
    assert len(fake.requests) == 2
    assert all(r["effect_root"] == str(scratch) for r in fake.requests)
    assert all(r["al_shell"] == str(payload / "scripts" / "al_shell.ps1")
               for r in fake.requests)


def test_rewrite_reads_back_and_a_rerun_is_a_no_op(home):
    fake = FakeShell()
    first = shell.rewrite(home, NEW, runner=fake)
    assert first["shortcuts"] == ["written", "written"]
    assert first["uninstall_entry"] == "written"
    again = shell.rewrite(home, runner=fake)
    assert again["uninstall_script"] == "current"
    assert again["shortcuts"] == ["current", "current"]
    assert again["uninstall_entry"] == "current"
    assert again["read_back"] is True


def test_a_write_that_does_not_stick_fails_the_read_back(home):
    with pytest.raises(shell.ShellError, match="read-back"):
        shell.rewrite(home, NEW, runner=FakeShell(sticky=False))


def test_entries_that_point_elsewhere_are_left_alone(home, tmp_path):
    other = tmp_path / "checkout"
    link = {"target": str(other / "electron.exe"), "arguments": "x",
            "workdir": str(other), "icon": str(other / "icon.ico")}
    entry = {"install_location": str(other), "version": "9.9.9", "icon": ""}
    task = {"execute": str(other / "pythonw.exe"), "arguments": "-m x",
            "workdir": str(other), "user": "player", "delay": "PT30S",
            "description": "checkout task"}
    fake = FakeShell(links={"Programs": dict(link), "Desktop": None},
                     entry=dict(entry), task=dict(task))
    out = shell.rewrite(home, NEW, runner=fake)
    assert out["shortcuts"] == ["elsewhere", "written"]
    assert out["uninstall_entry"] == "elsewhere"
    assert out["logon_task"] == "elsewhere"
    assert fake.links["Programs"] == link
    assert fake.entry == entry and fake.task == task
    assert fake.links["Desktop"]["workdir"] == str(home / "app" / NEW / "app")


def test_a_missing_task_is_never_created(home):
    fake = FakeShell()
    out = shell.rewrite(home, NEW, runner=fake)
    assert out["logon_task"] == "absent" and fake.task is None


def test_uninstall_script_is_copied_to_the_home_root(home):
    dst = home / "uninstall.ps1"
    assert shell.copy_uninstall(home, NEW) == "written"
    assert dst.read_bytes() == b"# uninstall v2\n"
    assert shell.copy_uninstall(home, NEW) == "current"
    dst.write_bytes(b"tampered\n")
    assert shell.copy_uninstall(home, NEW) == "written"
    assert dst.read_bytes() == b"# uninstall v2\n"


def test_refusals_touch_nothing(home, tmp_path):
    fake = FakeShell()
    with pytest.raises(shell.ShellError, match="not the active version"):
        shell.rewrite(home, OLD, runner=fake)
    with pytest.raises(shell.ShellError, match="absolute"):
        shell.rewrite(home, NEW, runner=fake, effect_root="relative")
    (home / "app" / NEW / "scripts" / "al_shell.ps1").unlink()
    with pytest.raises(shell.ShellError, match="al_shell"):
        shell.rewrite(home, NEW, runner=fake)
    with pytest.raises(shell.ShellError, match="no valid marker"):
        shell.rewrite(tmp_path / "empty", runner=fake)
    assert fake.requests == []
    assert not (home / "uninstall.ps1").exists()


def test_missing_payload_uninstall_script_is_refused(home):
    (home / "app" / NEW / "scripts" / "uninstall.ps1").unlink()
    fake = FakeShell()
    with pytest.raises(shell.ShellError, match="uninstall.ps1"):
        shell.rewrite(home, NEW, runner=fake)
    assert fake.requests == []


def test_runner_results_are_validated(home):
    with pytest.raises(shell.ShellError):
        shell.rewrite(home, NEW, runner=lambda req: {"shortcuts": ["removed"],
                                                     "uninstall_entry": "written",
                                                     "logon_task": "absent"})
    with pytest.raises(shell.ShellError):
        shell.rewrite(home, NEW, runner=lambda req: None)


# --- the default runner: al_shell.ps1 under PowerShell 5.1 --------------------

def test_script_uses_only_the_payload_al_shell_with_the_effect_root(home, tmp_path):
    req = shell.plan(home, NEW, effect_root=tmp_path / "fx")
    text = shell.build_script(req)
    text.encode("ascii")
    assert ". " + shell.ps_quote(home / "app" / NEW / "scripts" / "al_shell.ps1") in text
    for fn in ("Install-AlShortcuts", "Set-AlUninstallEntry", "Get-AlLogonTask",
               "Register-AlLogonTask"):
        line = next(ln for ln in text.splitlines() if fn + " " in ln)
        assert "-EffectRoot $er" in line, fn
    assert "$er = " + shell.ps_quote(tmp_path / "fx") in text
    assert "Unregister-AlLogonTask" not in text and "Remove-Al" not in text
    src = SHELL_SRC.read_text(encoding="ascii")
    for word in ("ComObject", "WScript", "HKCU", "HKEY_", "Registry::",
                 "Get-ItemProperty", "New-ItemProperty", "ScheduledTask "):
        assert word not in src, word


def test_ps_quote_doubles_every_quote_character():
    assert shell.ps_quote("a'b") == "'a''b'"
    assert shell.ps_quote("x\u2019y") == "'x\u2019\u2019y'"


def test_powershell_runner_runs_the_system32_powershell(home, tmp_path):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        seen["kw"] = kw
        return subprocess.CompletedProcess(
            argv, 0, stdout='noise\nALSHELL {"shortcuts":"written",'
            '"uninstall_entry":"current","logon_task":"absent"}\n', stderr="")

    runner = shell.PowerShellRunner(run=fake_run,
                                    environ={"SystemRoot": str(tmp_path / "Windows")})
    req = shell.plan(home, NEW, effect_root=tmp_path / "fx")
    got = runner(req)
    assert got == {"shortcuts": "written", "uninstall_entry": "current",
                   "logon_task": "absent"}
    argv = seen["argv"]
    assert argv[0] == str(tmp_path / "Windows" / "System32" / "WindowsPowerShell"
                          / "v1.0" / "powershell.exe")
    assert argv[-2] == "-EncodedCommand"
    assert base64.b64decode(argv[-1]).decode("utf-16-le") == shell.build_script(req)
    assert seen["kw"]["timeout"] == shell.TIMEOUT_S


def test_powershell_runner_failures_raise(home, tmp_path):
    req = shell.plan(home, NEW)
    bad = shell.PowerShellRunner(
        run=lambda a, **k: subprocess.CompletedProcess(a, 1, "", "al_shell: boom\n"),
        environ={"SystemRoot": str(tmp_path / "Windows")})
    with pytest.raises(shell.ShellError, match="boom"):
        bad(req)
    silent = shell.PowerShellRunner(
        run=lambda a, **k: subprocess.CompletedProcess(a, 0, "nothing\n", ""),
        environ={"SystemRoot": str(tmp_path / "Windows")})
    with pytest.raises(shell.ShellError, match="no result"):
        silent(req)
    with pytest.raises(shell.ShellError, match="SystemRoot"):
        shell.PowerShellRunner(environ={}).command("x")


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_generated_script_parses_under_powershell_51(home, tmp_path):
    """Parse only: Parser::ParseFile, no statement of the script runs."""
    weird = tmp_path / "it's \u2019odd"
    req = shell.plan(home, NEW, effect_root=weird)
    script = tmp_path / "gen.ps1"
    script.write_text(shell.build_script(req), encoding="utf-8-sig")
    check = ("$t = $null; $e = $null; "
             "[void][System.Management.Automation.Language.Parser]::ParseFile("
             + shell.ps_quote(script) + ", [ref]$t, [ref]$e); "
             "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }; 'parsed'")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-Command", check],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "parsed" in r.stdout


# --- the first-run config ------------------------------------------------------

def test_first_run_config_has_player_keys_only(home):
    assert firstrun.write_first_run(home) == "written"
    path = home / "data" / "local.json"
    raw = path.read_bytes()
    raw.decode("ascii")
    assert b"\r\n" not in raw
    doc = json.loads(raw)
    assert doc["web_data"] is False
    for key in firstrun.NEVER_KEYS + firstrun.DEV_KEYS:
        assert key not in doc, key
    assert not any("consent" in k for k in doc)
    assert set(doc) <= set(settingsio.ALLOWED)
    assert not set(doc) & set(settingsio.NEVER)
    assert set(firstrun.DEV_KEYS) >= {"loop", "hot_reload", "tc_drift_live_unattended"}
    # no Client.txt consent record is made either
    assert sorted(p.name for p in (home / "data").iterdir()) == ["local.json"]


def test_an_existing_local_json_is_never_overwritten(home):
    path = home / "data" / "local.json"
    path.write_bytes(b'{"web_data": true, "contact": "me"}\n')
    assert firstrun.write_first_run(home) == "kept"
    assert path.read_bytes() == b'{"web_data": true, "contact": "me"}\n'
    path.unlink()
    bak = home / "data" / "local.json.bak"
    bak.write_bytes(b"{}\n")
    assert firstrun.write_first_run(home) == "kept"
    assert not path.exists() and bak.read_bytes() == b"{}\n"


def test_first_run_needs_the_laid_out_data_folder(tmp_path):
    with pytest.raises(firstrun.FirstRunError):
        firstrun.write_first_run(tmp_path / "bare")
    assert not (tmp_path / "bare").exists()


def test_first_run_document_is_a_fresh_copy():
    doc = firstrun.first_run_config()
    doc["web_data"] = True
    assert firstrun.first_run_config()["web_data"] is False
