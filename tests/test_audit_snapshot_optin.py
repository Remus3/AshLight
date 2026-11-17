"""AUDIT-SNAPSHOT-OPTIN (finding T1; decisions 0009 / 0013 amended 2026-11-17).

The build-time game-data snapshot follows the one web_data opt-in: it makes
no request while web_data is off, unless the build forces it (-Snapshot /
AL_SNAPSHOT=1, passed on as --opt-in). AL_NO_SNAPSHOT still wins.
No real network request: every fetch here is a stub.
"""

import re
from pathlib import Path

from server.al.theorycraft import snapshot

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build.ps1"


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        raise snapshot.FetchError("network: offline (stub)")


def test_web_data_off_makes_no_request(tmp_path, capsys):
    fetch = Recorder()
    assert snapshot.main(["--dir", str(tmp_path)], environ={}, fetch=fetch,
                         contact="", web_data=False) == 0
    assert fetch.calls == []
    assert "web_data off" in capsys.readouterr().out
    assert not any(tmp_path.iterdir())


def test_web_data_read_from_local_config_strictly(tmp_path, monkeypatch):
    fetch = Recorder()
    for value in ({}, {"web_data": "true"}, {"web_data": 1}, []):
        monkeypatch.setattr(snapshot.paths, "load_local_config", lambda v=value: v)
        snapshot.main(["--dir", str(tmp_path)], environ={}, fetch=fetch, contact="")
        assert fetch.calls == [], value
    monkeypatch.setattr(snapshot.paths, "load_local_config", lambda: {"web_data": True})
    snapshot.main(["--dir", str(tmp_path)], environ={}, fetch=fetch, contact="")
    assert fetch.calls, "web_data true runs the snapshot"


def test_opt_in_flag_forces_a_run_while_off(tmp_path):
    fetch = Recorder()
    snapshot.main(["--dir", str(tmp_path), "--opt-in"], environ={}, fetch=fetch,
                  contact="", web_data=False)
    assert fetch.calls


def test_opt_out_env_wins_over_everything(tmp_path):
    fetch = Recorder()
    assert snapshot.main(["--dir", str(tmp_path), "--opt-in"],
                         environ={"AL_NO_SNAPSHOT": "1"}, fetch=fetch, contact="",
                         web_data=True) == 0
    assert fetch.calls == []


def _snapshot_block():
    ps = BUILD.read_text(encoding="ascii")
    return ps.split("# TC-SNAP", 1)[1].split("# Source fingerprint", 1)[0]


def test_build_script_gates_snapshot_on_web_data():
    ps = BUILD.read_text(encoding="ascii")
    assert re.search(r"\[switch\]\$Snapshot\b", ps)
    block = _snapshot_block()
    assert "web_data" in block and "-eq $true" in block
    assert "AL_SNAPSHOT" in block and "--opt-in" in block
    assert "skipped (web_data off" in block
    # -NoSnapshot / AL_NO_SNAPSHOT are checked first and still win
    assert block.index("if ($NoSnapshot") < block.index("elseif (-not ($forceSnap")
    assert "$env:AL_SNAPSHOT" in block


def test_decisions_record_the_ruling():
    d9 = (ROOT / "docs" / "decisions" / "0009-data-license.md").read_text(encoding="ascii")
    d13 = (ROOT / "docs" / "decisions" / "0013-web-data.md").read_text(encoding="ascii")
    assert "`scripts/build.ps1` (opt-out)" not in d9
    for text in (d9, d13):
        assert "AUDIT-SNAPSHOT-OPTIN" in text
