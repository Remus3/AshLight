"""SEC-NO-DISCOVERY: a pointed, test or demo core never looks for the live
Client.txt.

Only the real entry point (no runtime dir, no log path) with no configured
"client_log" runs the Steam library scan. A configured path that is missing
stays configured (a Checks row says so) and never falls through to the
scan. Only a file named Client.txt is ever opened. The conftest guard fails
any test that reaches the real registry or Program Files lookup.

Every Steam root here is a fake folder under tmp_path; the real registry
and the live Client.txt are never read.
"""

import time
from pathlib import Path

import pytest

from server.al import diag, logfile
from server.al import core as core_mod
from server.al.core import Core

WAIT_S = 5.0


@pytest.fixture
def scans(monkeypatch):
    """Every Steam library scan the code under test starts (steam_roots
    of each call). The scan itself still runs, so the conftest guard stays
    armed behind it."""
    calls = []
    real = logfile.steam_libraries

    def spy(steam_roots=None):
        calls.append(steam_roots)
        return real(steam_roots)

    monkeypatch.setattr(logfile, "steam_libraries", spy)
    return calls


def consented_runtime(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir(parents=True)
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    return rt


def fake_steam(tmp_path):
    """A Steam root whose libraryfolders.vdf names a second library that
    holds the PoE2 log. Returns (steam_root, library_log)."""
    steam = tmp_path / "Steam"
    lib = tmp_path / "Lib2"
    (steam / "steamapps").mkdir(parents=True)
    vdf = ('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n'
           '\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n') % (
        str(steam).replace("\\", "\\\\"), str(lib).replace("\\", "\\\\"))
    (steam / "steamapps" / "libraryfolders.vdf").write_text(vdf, encoding="utf-8")
    log = lib / logfile.LOG_REL
    log.parent.mkdir(parents=True)
    log.write_bytes(b"")
    return steam, log


def use_fake_steam(monkeypatch, steam):
    """Point the two root lookups at the fake root (over the guard)."""
    monkeypatch.setattr(logfile, "_steam_roots_from_registry", lambda: [steam])
    monkeypatch.setattr(logfile, "_steam_roots_from_env", lambda environ=None: [])


def test_pointed_core_never_calls_discovery(tmp_path, scans):
    rt = consented_runtime(tmp_path)
    log = tmp_path / "game" / "logs" / "Client.txt"
    log.parent.mkdir(parents=True)
    log.write_bytes(b"")
    assert core_mod.discover_default(None, str(log)) is False
    assert core_mod.discover_default(rt, str(log)) is False
    core = Core(runtime=rt, log_path=str(log), poll_s=0.02)
    try:
        assert core.discover is False
        assert core.log_path == log
        assert core.start_tailing()
        # The log vanishes: a pointed core keeps its path, never scans.
        log.unlink()
        end = time.monotonic() + WAIT_S
        while not core.tailer._missing and time.monotonic() < end:
            time.sleep(0.02)
        assert core.tailer._missing
        for i in range(4):
            assert core.ensure_tailing(now=1000.0 + 10 * i) is False
        assert core.log_path == log and core.tailer.path == log
        core.record_consent(True, path=str(log))
        assert core.log_path == log
    finally:
        core.close()
    assert scans == []


def test_runtime_only_core_never_calls_discovery(tmp_path, scans):
    rt = consented_runtime(tmp_path)
    assert core_mod.discover_default(rt, None) is False
    core = Core(runtime=rt, poll_s=0.02)
    try:
        assert core.discover is False
        assert core.log_path is None
        assert core.start_tailing() is False
        for i in range(4):
            assert core.ensure_tailing(now=1000.0 + 10 * i) is False
        assert core.locate_log() is None
        assert core.tailer is None
        facts = core.diag_facts()
        assert facts["log_found"] is False and facts["log_configured"] is False
    finally:
        core.close()
    assert scans == []


def test_configured_missing_path_stays_beside_a_fake_steam_library(tmp_path, monkeypatch,
                                                                    scans):
    steam, lib_log = fake_steam(tmp_path)
    use_fake_steam(monkeypatch, steam)
    rt = consented_runtime(tmp_path)
    missing = tmp_path / "moved" / "logs" / "Client.txt"
    # Even a core allowed to scan keeps a configured path.
    core = Core(runtime=rt, log_path=str(missing), poll_s=0.02, discover=True)
    try:
        assert core.log_path == missing
        assert core.start_tailing()
        assert core.tailer.path == missing
        end = time.monotonic() + WAIT_S
        while not core.tailer._missing and time.monotonic() < end:
            time.sleep(0.02)
        for i in range(3):
            assert core.ensure_tailing(now=2000.0 + 10 * i) is False
        assert core.log_path == missing and core.tailer.path == missing
        facts = core.diag_facts()
        assert facts["log_found"] is False and facts["log_configured"] is True
        rows = {r["id"]: r for r in diag.checks(facts, time.time())}
        assert rows["log"]["status"] == diag.FAIL
        assert rows["log"]["detail"] == "The Client.txt path in your settings is missing."
        assert rows["log"]["fix"] == diag.FIX_LOG_PATH
    finally:
        core.close()
    assert scans == []
    # The function itself: a configured value wins, existing or not.
    assert logfile.discover_client_log(str(missing), steam_roots=[steam]) == missing
    assert scans == []
    # The library log is there all along (the fake is real enough).
    assert logfile.discover_client_log(None, steam_roots=[steam]) is not None


def test_unconfigured_real_shape_still_finds_the_library_log(tmp_path, monkeypatch, scans):
    steam, lib_log = fake_steam(tmp_path)
    use_fake_steam(monkeypatch, steam)
    assert core_mod.discover_default(None, None) is True
    assert core_mod.discover_default(None, "") is True
    rt = consented_runtime(tmp_path)
    # discover=True stands in for the real entry point (runtime None), whose
    # core would read the live runtime dir and config.
    core = Core(runtime=rt, poll_s=0.02, discover=True)
    try:
        assert core.log_path is not None
        assert Path(core.log_path).resolve() == lib_log.resolve()
        assert core.start_tailing()
        facts = core.diag_facts()
        assert facts["log_found"] is True and facts["log_configured"] is False
    finally:
        core.close()
    assert scans and all(r is None for r in scans)


def test_only_a_file_named_client_txt_is_ever_opened(tmp_path, monkeypatch):
    opened = []
    real_open = logfile._open_shared

    def spy(path):
        opened.append(Path(path))
        return real_open(path)

    monkeypatch.setattr(logfile, "_open_shared", spy)
    secret = tmp_path / "notes" / "secrets"
    secret.parent.mkdir()
    secret.write_bytes(b"not a log\n")
    dotted = tmp_path / "keys.json"
    dotted.write_text("{}\n", encoding="ascii")
    game = tmp_path / "Path of Exile 2"
    (game / "logs").mkdir(parents=True)
    upper = tmp_path / "other" / "CLIENT.TXT"
    upper.parent.mkdir()
    upper.write_bytes(b"")
    cases = {
        str(secret): secret / "Client.txt",
        str(dotted): dotted / "Client.txt",
        str(game): game / "logs" / "Client.txt",
        str(tmp_path / "bare"): tmp_path / "bare" / "Client.txt",
        str(upper): upper,
    }
    for configured, want in cases.items():
        got = logfile.discover_client_log(configured, steam_roots=[])
        assert got == want, configured
        assert got.name.lower() == "client.txt"
    # A core pointed at a file of another name tails <file>/Client.txt,
    # which cannot exist, so nothing is opened.
    rt = consented_runtime(tmp_path)
    core = Core(runtime=rt, log_path=str(secret), poll_s=0.02)
    try:
        assert core.log_path == secret / "Client.txt"
        assert core.start_tailing()
        time.sleep(0.2)
    finally:
        core.close()
    # The consent API path: an existing file not named Client.txt is refused
    # and the tailer path does not move.
    core = Core(runtime=consented_runtime(tmp_path / "b"), log_path=str(upper), poll_s=0.02)
    try:
        before = core.log_path
        for bad in (secret, dotted):
            with pytest.raises(ValueError):
                core.record_consent(True, path=str(bad))
            assert core.log_path == before
        core.record_consent(True, path=str(upper))
        assert core.tailer is not None and core.tailer.path == upper
        with open(upper, "ab") as fh:
            fh.write(b"2026/11/18 10:00:00 1 2 [INFO Client 1] hello\n")
        end = time.monotonic() + WAIT_S
        while not opened and time.monotonic() < end:
            time.sleep(0.02)
    finally:
        core.close()
    assert opened, "the CLIENT.TXT core opened its file"
    assert all(p.name.lower() == "client.txt" for p in opened), opened
    assert secret not in opened and dotted not in opened


def test_conftest_guard_fails_a_real_registry_scan(tmp_path, request, _no_real_steam_scan):
    hits = _no_real_steam_scan
    with pytest.raises(pytest.fail.Exception):
        logfile._steam_roots_from_registry()
    with pytest.raises(pytest.fail.Exception):
        logfile._steam_roots_from_env()
    with pytest.raises(pytest.fail.Exception):
        logfile.steam_libraries()
    with pytest.raises(pytest.fail.Exception):
        logfile.discover_client_log(None)
    # A core told to scan with no stub fails the same way.
    with pytest.raises(pytest.fail.Exception):
        Core(runtime=tmp_path / "rt", discover=True)
    assert "_steam_roots_from_registry" in hits
    # An explicit steam_roots never reaches the guard.
    assert logfile.steam_libraries([tmp_path / "none"]) == [tmp_path / "none"]
    markers = "\n".join(request.config.getini("markers"))
    assert "discovery:" in markers
    hits.clear()  # the refusals above were the point of this test


@pytest.mark.discovery
def test_discovery_marker_turns_the_guard_off(_no_real_steam_scan):
    assert _no_real_steam_scan == []
    assert logfile._steam_roots_from_env(environ={"ProgramFiles": "X"}) == [
        Path("X") / "Steam"]
