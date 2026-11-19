"""SEC-ACL-SETUP (finding F-011, decision 0051).

1. No .ps1 or .vbs under scripts/ starts powershell, cmd, wscript or icacls
   by a bare name (a PATH entry or the current folder could shadow it):
   such a program is started by its System32 path. Comments and
   Get-Command lookups are ignored.
2. setup.ps1 applies the private ACL ('python -m server.al.acl apply') to
   the sidecar root, the runtime dir and config/local.json, logs every line
   to setup.log and never stops on a failure.
3. The acl CLI leaves a tmp sidecar (and a child folder in it) with exactly
   the three SIDs, and a second run changes nothing.

Every ACL change here is on a pytest tmp dir; setup.ps1 is never run and
the live sidecar, the live ops/runtime and config/local.json are never
touched.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import acl

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SETUP = SCRIPTS / "setup.ps1"
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows ACLs only")
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None

PROGRAMS = ("powershell", "pwsh", "cmd", "wscript", "cscript", "icacls")
_NAME = r"(?:%s)(?:\.exe)?" % "|".join(PROGRAMS)
# a string literal that starts with a bare program name
_STRING_HIT = re.compile(r"^\s*" + _NAME + r"(?:\s|$)", re.IGNORECASE)
# a PowerShell command position: line start, after ; & | ( { or
# Start-Process [-FilePath]
_PS_HIT = re.compile(r"(?:^|[;&|({]|\bStart-Process\s+(?:-FilePath\s+)?)\s*"
                     + _NAME + r"(?![\w.\\/:$-])", re.IGNORECASE)


def _strip_ps(text):
    """PowerShell code lines: block and line comments dropped, string
    literals cut out. Returns (code_lines, strings)."""
    text = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    lines, strings = [], []
    for raw in text.splitlines():
        code, i = [], 0
        while i < len(raw):
            c = raw[i]
            if c == "#":
                break
            if c in "'\"":
                j, buf = i + 1, []
                while j < len(raw):
                    d = raw[j]
                    if c == '"' and d == "`" and j + 1 < len(raw):
                        buf.append(raw[j + 1])
                        j += 2
                        continue
                    if d == c:
                        if j + 1 < len(raw) and raw[j + 1] == c:
                            buf.append(c)
                            j += 2
                            continue
                        break
                    buf.append(d)
                    j += 1
                strings.append((raw, "".join(buf)))
                code.append(" S ")
                i = j + 1
                continue
            code.append(c)
            i += 1
        lines.append((raw, "".join(code)))
    return lines, strings


def _strip_vbs(text):
    """VBScript: comments dropped; only string literals can name a program
    to start (Run / Exec / ShellExecute take a string)."""
    strings = []
    for raw in text.splitlines():
        if re.match(r"\s*rem\s", raw, re.IGNORECASE):
            continue
        i = 0
        while i < len(raw):
            c = raw[i]
            if c == "'":
                break
            if c == '"':
                j, buf = i + 1, []
                while j < len(raw):
                    if raw[j] == '"':
                        if j + 1 < len(raw) and raw[j + 1] == '"':
                            buf.append('"')
                            j += 2
                            continue
                        break
                    buf.append(raw[j])
                    j += 1
                strings.append((raw, "".join(buf)))
                i = j + 1
                continue
            i += 1
    return [], strings


def bare_starts(text, suffix):
    """The source lines that start a listed program by a bare name."""
    if suffix.lower() == ".vbs":
        lines, strings = _strip_vbs(text)
    else:
        lines, strings = _strip_ps(text)
    hits = []
    for raw, s in strings:
        if "get-command" in raw.lower():
            continue
        if _STRING_HIT.search(s):
            hits.append(raw.strip())
    for raw, code in lines:
        if "get-command" in code.lower():
            continue
        if _PS_HIT.search(code):
            hits.append(raw.strip())
    return hits


def _scripts():
    found = sorted(list(SCRIPTS.rglob("*.ps1")) + list(SCRIPTS.rglob("*.vbs")))
    assert found, "no scripts found"
    return found


def test_no_script_starts_a_program_by_bare_name():
    # self-check: the detector flags the shapes it is meant to catch
    flagged = [
        ('cmd = "powershell.exe -NoProfile -File x.ps1"', ".vbs"),
        ('sh.Run "cmd /c dir", 0, False', ".vbs"),
        ('sh.Run "wscript //B x.vbs"', ".vbs"),
        ("& icacls $dir /grant x", ".ps1"),
        ("icacls.exe $dir /q", ".ps1"),
        ("$x = 1; powershell -NoProfile", ".ps1"),
        ("Start-Process -FilePath powershell.exe -ArgumentList $a", ".ps1"),
        ("Start-Process 'cmd.exe' '/c'", ".ps1"),
        ("Invoke-AlLogged $log 'icacls' @($p)", ".ps1"),
    ]
    for line, suffix in flagged:
        assert bare_starts(line, suffix), line
    # and leaves alone what is not a bare start
    clean = [
        ("' runs through wscript.exe so no console", ".vbs"),
        ('Set sh = CreateObject("WScript.Shell")', ".vbs"),
        ('here = fso.GetParentFolderName(WScript.ScriptFullName)', ".vbs"),
        ("Dim fso, sh, here, cmd", ".vbs"),
        ('ps = "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"', ".vbs"),
        ("# starts powershell.exe by name", ".ps1"),
        ("<#\n  cmd /c here\n#>", ".ps1"),
        ("$cmd = Get-Command 'powershell' -ErrorAction SilentlyContinue", ".ps1"),
        ("$Wscript = Join-Path $env:SystemRoot 'System32\\wscript.exe'", ".ps1"),
        ("$rc = Invoke-AlLogged $log 'npm.cmd' @('test')", ".ps1"),
        ("if ($cmd) { return $cmd.Source }", ".ps1"),
        ("Write-Host 'Windows PowerShell 5.1 compatible'", ".ps1"),
    ]
    for line, suffix in clean:
        assert not bare_starts(line, suffix), line
    offenders = {}
    for path in _scripts():
        hits = bare_starts(path.read_text(encoding="ascii"), path.suffix)
        if hits:
            offenders[path.relative_to(ROOT).as_posix()] = hits
    assert not offenders, offenders


def _function(text, name):
    m = re.search(r"^function %s\b.*?^}\s*$" % re.escape(name), text,
                  re.DOTALL | re.MULTILINE)
    assert m, f"{name} not found in setup.ps1"
    return m.group(0)


def test_setup_applies_the_acl_to_sidecar_runtime_and_config(tmp_path):
    text = SETUP.read_text(encoding="ascii")
    body = _function(text, "Invoke-AlAcl")
    assert "-m server.al.acl apply $Target" in body
    assert "Write-AlLog" in body and "WARNING acl not applied" in body
    assert not re.search(r"^\s*(throw|exit)\b", body, re.IGNORECASE | re.MULTILINE)
    assert "$ErrorActionPreference = 'Continue'" in body
    # the sidecar and the runtime dir right after they are made ...
    loop = text.index("foreach ($dir in @($paths.runtime")
    logger = text.index("function Write-AlLog")
    side = text.index("Invoke-AlAcl $paths.sidecar\n")
    run = text.index("Invoke-AlAcl $paths.runtime\n")
    assert loop < logger < side < run
    # ... and config/local.json after the one-time copy
    assert "$local = Join-Path $Repo 'config\\local.json'" in text
    copy = text.index("Copy-Item -Path $example -Destination $local")
    conf = text.index("Invoke-AlAcl $local\n")
    assert copy < conf
    if PS51 is None or os.name != "nt":
        return
    # run the function itself on a tmp sidecar: a private line in the log,
    # and a missing path is a warning line, never a stop
    sidecar = tmp_path / "AL"
    (sidecar / "Logs").mkdir(parents=True)
    log = tmp_path / "setup.log"
    missing = tmp_path / "nope"

    def q(p):
        return "'" + str(p).replace("'", "''") + "'"

    script = ("$ErrorActionPreference = 'Stop'; Set-StrictMode -Version 2; "
              f"$Repo = {q(ROOT)}; $py = {q(sys.executable)}; $log = {q(log)}; "
              "function Write-AlLog([string]$Message) { "
              "Add-Content -Path $log -Value $Message -Encoding ASCII }\n"
              + body + "\n"
              f"Invoke-AlAcl {q(sidecar)}\nInvoke-AlAcl {q(missing)}\n"
              "Write-AlLog 'after'\nexit 0\n")
    ps1 = tmp_path / "t.ps1"
    ps1.write_text(script, encoding="ascii")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                        "Bypass", "-File", str(ps1)], capture_output=True, text=True,
                       timeout=120, cwd=tmp_path, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = log.read_text(encoding="ascii").splitlines()
    assert f"setup: acl: private: {sidecar}" in lines, lines
    assert any(l.startswith("setup: WARNING acl not applied (exit 1)")
               and l.endswith(str(missing)) for l in lines), lines
    assert lines[-1] == "after"
    assert acl.principals(sidecar) == sorted(acl.private_sids())


def _apply(target):
    return subprocess.run([sys.executable, "-m", "server.al.acl", "apply", str(target)],
                          capture_output=True, text=True, timeout=120, cwd=ROOT,
                          stdin=subprocess.DEVNULL)


@WINDOWS
def test_acl_cli_makes_a_tmp_sidecar_private(tmp_path):
    sidecar = tmp_path / "AL"
    child = sidecar / "Worktree" / "lane-1"
    child.mkdir(parents=True)
    (child / "f.txt").write_text("x\n", encoding="ascii")
    assert acl.is_private(sidecar) is False  # tmp dirs inherit their parent
    three = sorted(acl.private_sids())
    assert acl.SYSTEM_SID in three and acl.ADMINS_SID in three and len(three) == 3
    r = _apply(sidecar)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == f"acl: private: {sidecar}"
    assert acl.principals(sidecar) == three
    assert acl.principals(child) == three
    assert acl.principals(child / "f.txt") == three
    protected, entries = acl.read_acl(sidecar)
    assert protected and len(entries) == 3
    before = [acl.read_acl(p) for p in (sidecar, child, child / "f.txt")]
    # a second run changes nothing
    r = _apply(sidecar)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == f"acl: private: {sidecar}"
    assert [acl.read_acl(p) for p in (sidecar, child, child / "f.txt")] == before
