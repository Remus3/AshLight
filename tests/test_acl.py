"""SEC-ACL-APPLY (finding F-011, decision 0051): the runtime dir and
config/local.json get an explicit ACL - the player, SYSTEM and the local
admins group (SID S-1-5-32-544), inheritance off - through System32
icacls by absolute path, and a kept token is reused only while the
runtime dir is private.

Every ACL change here is on a pytest tmp dir; the repo, the live
ops/runtime and the live sidecar are never touched.
"""

import os
import subprocess
from pathlib import Path

import pytest

from server.al import __main__ as entry
from server.al import acl, exepin, hotreload
from server.al.core import Core, write_private

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows ACLs only")
USERS_SID = "S-1-5-32-545"  # the local users group: one more writer


def _three():
    return sorted(acl.private_sids())


def _add_writer(path, sid=USERS_SID):
    """Grant one more principal modify rights (inheritable), by SID."""
    subprocess.run([str(exepin.system_tool("icacls.exe")), str(path), "/grant",
                    f"*{sid}:(OI)(CI)M", "/q"], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


class Spy:
    """Records each icacls argv, then runs it for real."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return acl._run(argv)


@WINDOWS
def test_private_dir_lists_exactly_three_principals(tmp_path):
    rt = tmp_path / "runtime"
    child = rt / "theorycraft"
    child.mkdir(parents=True)
    (child / "weights.json").write_text("{}\n", encoding="ascii")
    assert acl.is_private(rt) is False  # tmp dirs inherit their parent
    three = _three()
    assert acl.SYSTEM_SID in three and acl.ADMINS_SID in three
    assert acl.make_private(rt) is True
    assert acl.principals(rt) == three
    protected, entries = acl.read_acl(rt)
    assert protected and len(entries) == 3
    assert all(f & acl.INHERIT_FLAGS == acl.INHERIT_FLAGS and m == acl.FULL_ACCESS
               for _, f, m, _ in entries)
    # a folder and a file that existed before keep access, as the three only
    assert acl.principals(child) == three
    assert acl.principals(child / "weights.json") == three
    # a second make_private changes nothing: no icacls call at all
    spy = Spy()
    assert acl.make_private(rt, run=spy) is True
    assert spy.calls == []
    assert acl.principals(rt) == three


@WINDOWS
def test_token_file_inherits_the_private_acl(tmp_path):
    rt = tmp_path / "runtime"
    rt.mkdir()
    old = rt / "token"
    old.write_text("old\n", encoding="ascii")
    assert acl.make_private(rt) is True
    token = "ab" * 24
    write_private(old, token + "\n")  # a replaced file takes the dir's ACL
    assert acl.principals(old) == _three()
    assert acl.is_private(old) is True
    assert not (rt / "token.tmp").exists()


@WINDOWS
def test_config_file_is_private_after_a_settings_write(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    assert core.private_config is False  # a test core never changes an ACL
    core.set_web_data(False)
    assert acl.is_private(core.config_path) is False
    core.private_config = True  # behave as the real core, on a tmp file
    core.set_web_data(False)
    assert acl.is_private(core.config_path) is True
    assert acl.principals(core.config_path) == _three()
    # a replaced file takes the folder's ACL again; the layout save re-applies
    core.config_path.unlink()
    core.set_overlay_layout({})
    assert core.config_path.exists()
    assert acl.is_private(core.config_path) is True


def _kept(rt, token="cd" * 24):
    tok = rt / "token"
    tok.write_text(token + "\n", encoding="ascii")
    hotreload.mark_token_reuse(rt)
    return tok, token


@WINDOWS
def test_token_reuse_refused_when_the_dir_is_not_private(tmp_path):
    rt = tmp_path / "runtime"
    rt.mkdir()
    # control: a private dir keeps the token across a code reload
    assert acl.make_private(rt) is True
    tok, kept = _kept(rt)
    assert entry.start_token(rt, tok) == kept
    # one more writer: the kept token is not reused and the mark is gone
    _add_writer(rt)
    assert acl.is_private(rt) is False
    assert USERS_SID in acl.principals(rt)
    tok, kept = _kept(rt)
    fresh = entry.start_token(rt, tok)
    assert fresh != kept and len(fresh) == 48
    assert not (rt / hotreload.TOKEN_REUSE_FILE).exists()
    # the start repaired the dir for the next token
    assert acl.is_private(rt) is True
    assert acl.principals(rt) == _three()


def test_token_reuse_refused_when_private_reads_false(tmp_path, monkeypatch):
    rt = tmp_path / "runtime"
    rt.mkdir()
    monkeypatch.setattr(acl, "is_private", lambda p: False)
    monkeypatch.setattr(acl, "make_private", lambda p: False)
    tok, kept = _kept(rt)
    assert entry.start_token(rt, tok) != kept
    assert not (rt / hotreload.TOKEN_REUSE_FILE).exists()


def test_icacls_runs_by_its_system32_path(tmp_path, monkeypatch):
    sids = ("S-1-5-21-1-2-3-1001", acl.SYSTEM_SID, acl.ADMINS_SID)
    argv = acl.icacls_argv(tmp_path, sids, True, extra=(USERS_SID,))
    exe = Path(argv[0])
    assert exe == exepin.system_tool("icacls.exe")
    assert exe.is_absolute() and exe.name == "icacls.exe"
    assert exe.parent.name.lower() == "system32"
    assert argv[1] == str(tmp_path)
    assert "/inheritance:r" in argv and "/grant:r" in argv
    for sid in sids:  # SIDs, never names: locale independent
        assert f"*{sid}:(OI)(CI)F" in argv
    assert argv[argv.index("/remove") + 1] == f"*{USERS_SID}"
    file_argv = acl.icacls_argv(tmp_path / "f", sids, False)
    assert f"*{acl.ADMINS_SID}:F" in file_argv and "/remove" not in file_argv
    seen = {}

    def fake_run(a, **kw):
        seen["argv"], seen["kw"] = a, kw
        return subprocess.CompletedProcess(a, 0, b"", b"")
    monkeypatch.setattr(acl.subprocess, "run", fake_run)
    assert acl._run(argv) is True
    assert seen["argv"] == argv and seen["kw"]["stdin"] == subprocess.DEVNULL
    if os.name == "nt":  # the real path: what make_private ran
        monkeypatch.undo()
        d = tmp_path / "rt"
        d.mkdir()
        spy = Spy()
        assert acl.make_private(d, run=spy) is True
        assert len(spy.calls) == 1
        assert Path(spy.calls[0][0]) == exepin.system_tool("icacls.exe")
        assert Path(spy.calls[0][1]) == d


@WINDOWS
def test_links_and_game_folders_are_refused(tmp_path):
    game = tmp_path / "steamapps" / "x"
    game.mkdir(parents=True)
    spy = Spy()
    assert acl.make_private(game, run=spy) is None and spy.calls == []
    assert acl.main(["apply", str(game)]) == 1
    assert acl.main(["apply"]) == 2


def test_no_op_off_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(acl, "_is_windows", lambda: False)
    monkeypatch.setattr(acl, "_PLAYER_SID", None)

    def boom(*a, **kw):
        raise AssertionError("no process off Windows")
    monkeypatch.setattr(acl.subprocess, "run", boom)
    d = tmp_path / "rt"
    d.mkdir()
    assert acl.player_sid() is None and acl.private_sids() is None
    assert acl.make_private(d) is None
    assert acl.is_private(d) is None
    assert acl.principals(d) is None
    assert acl.read_acl(d) is None
    assert acl.main(["apply", str(d)]) == 0
    # the old behaviour stays: a kept token is reused
    tok, kept = _kept(d)
    assert entry.start_token(d, tok) == kept
