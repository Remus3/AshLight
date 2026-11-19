"""DESKTOP-CLIENT (decision 0041) and the decision 0029 amendment.

- the snapshot carries game_idle (the 0029 idle "game may be closed" state
  as one boolean): true after the quiet-log idle, false again on the next
  fresh line; the overlay hides on it (app/overlay_gate.js, node tests);
- the overlay exists only while the client runs: main.js exits on a start
  without --client (bar the bounded smoke), run.ps1 starts the client with
  --client and never a bare overlay;
- setup.ps1's shortcut writer is idempotent (PS 5.1, into tmp only);
- docs: decision 0041, the 0029 amendment, the ROADMAP row, CLAUDE.md.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from server.al import summary
from server.al.state import SessionState

ROOT = Path(__file__).resolve().parents[1]
IDLE = summary.IDLE_S
PS51 = shutil.which("powershell.exe") if sys.platform == "win32" else None


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _state():
    clk = Clock()
    st = SessionState(clock=clk)
    st.set_tailer(consented=True, reading=True, path="logs/Client.txt")
    st.apply({"type": "area_generated", "area_id": "MapCrypt", "area_level": 65,
              "seed": "1", "recv_ts": 1000.0})
    return st, clk


def test_snapshot_game_idle_follows_the_0029_idle_state():
    st, clk = _state()
    assert st.snapshot()["game_idle"] is False
    assert st.check_log_idle(now=1000.0 + IDLE) is True
    clk.t = 1000.0 + IDLE + 5
    assert st.snapshot()["game_idle"] is True  # overlay hides
    st.apply({"type": "whisper_in", "from": "Someone", "text": "hi",
              "recv_ts": 1000.0 + IDLE + 60})
    assert st.snapshot()["game_idle"] is False  # fresh line: overlay shows


def test_game_idle_needs_consent():
    st = SessionState(clock=Clock())
    st.tailer["idle"] = True  # without consent nothing is tailed
    assert st.snapshot()["game_idle"] is False


def _code(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", js)


def test_overlay_lives_only_inside_the_client():
    main = _code((ROOT / "app" / "main.js").read_text(encoding="utf-8"))
    assert "const OVERLAY_ALONE_TEST = !CLIENT_MODE && SMOKE_S > 0;" in main
    guard = main.index("if (!CLIENT_MODE && !OVERLAY_ALONE_TEST)")
    assert guard < main.index("requestSingleInstanceLock()") < main.index("app.whenReady()")
    # the one gate hook, fed only by the overlay page
    assert "function setOverlayGate(visible)" in main
    assert 'ipcMain.on("al:gate"' in main and "e.sender !== win.webContents" in main
    # the window is shown by the gate, never straight on ready-to-show
    assert 'win.once("ready-to-show", () => win.showInactive())' not in main


def test_run_ps1_starts_the_client_not_a_bare_overlay():
    text = (ROOT / "scripts" / "run.ps1").read_text(encoding="ascii")
    assert "'--client'" in text
    starts = [ln for ln in text.splitlines() if "Start-AlDetached -FilePath $electron" in ln]
    assert len(starts) == 1 and "$clientArgs" in starts[0]
    assert "$wantOverlay = -not ($NoOverlay -or $NoBrowser -or $Browser -or $EdgeApp)" in text
    # the client (and so the core) is started with -NoBrowser: no loop
    launcher = (ROOT / "app" / "client" / "launcher.js").read_text(encoding="utf-8")
    assert '"-NoBrowser"' in launcher


def _shortcut_fn():
    text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="ascii")
    start = text.index("function Set-AlShortcut")
    end = text.index("function Install-AlShortcuts")
    return text[start:end]


@pytest.mark.skipif(PS51 is None, reason="Windows PowerShell 5.1 only")
def test_shortcut_writer_is_idempotent(tmp_path):
    target = tmp_path / "electron.exe"
    target.write_bytes(b"")
    icon = tmp_path / "ashlight.ico"
    icon.write_bytes(b"")
    link = tmp_path / "AshLight.lnk"
    call = (f"Set-AlShortcut '{link}' '{target}' '\"{tmp_path}\" --client' '{tmp_path}' "
            f"'{icon}'")
    script = _shortcut_fn() + f"\n{call}\n{call}\n" + (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{link}'); "
        "Write-Output ('ARGS=' + $s.Arguments)")
    r = subprocess.run([PS51, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", script], capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stderr
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    assert lines[:2] == ["True", "False"], lines  # written, then a no-op
    assert lines[2] == f'ARGS="{tmp_path}" --client'
    assert link.is_file()


def test_setup_writes_per_user_shortcuts_only():
    text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="ascii")
    assert "GetFolderPath('Programs')" in text and "GetFolderPath('Desktop')" in text
    assert "CommonPrograms" not in text and "CommonDesktop" not in text
    assert "assets\\icon.ico" in text and "client\\icon.js" not in text and "[switch]$NoShortcut" in text
    assert text.count("Install-AlShortcuts\n") == 2  # both exits of the npm step


def test_decision_and_records():
    d = (ROOT / "docs" / "decisions" / "0041-desktop-client.md").read_text(encoding="ascii")
    for word in ("## Decision", "## Alternatives", "## Why", "## Reverses if",
                 "electron-builder", "--client", "shell.openExternal"):
        assert word in d, word
    a = (ROOT / "docs" / "decisions" / "0029-game-exit-log-staleness.md").read_text(
        encoding="ascii")
    assert "Amendment 2026-11-17" in a and "game_idle" in a
    claude = (ROOT / "CLAUDE.md").read_text(encoding="ascii")
    assert "(decision 0041)" in claude
    assert re.search(r"Game exit shows as an idle.*?amended 2026-11-17", claude, flags=re.S)
    # AUTO-02: a done row may have been pruned into docs/roadmap/archive/.
    texts = [(ROOT / "ROADMAP.md").read_text(encoding="ascii")]
    texts += [p.read_text(encoding="ascii")
              for p in sorted((ROOT / "docs" / "roadmap" / "archive").glob("*.md"))]
    roadmap = "\n".join(texts)
    m = re.search(r"^- \[[ xX]\] DESKTOP-CLIENT\b", roadmap, flags=re.M)
    assert m, "DESKTOP-CLIENT row in ROADMAP.md or docs/roadmap/archive/"
    row = roadmap[m.start():][:3000]
    assert "ZERO-CLICK:" in row
