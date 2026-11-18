"""Leak sweep: synthetic needles only - this file never spells a real one."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import leak_sweep as ls  # noqa: E402

FAKE = ["Zorblax Quux", "acct-0000-fake"]


def _kinds(text, needles=FAKE, rel="x.md"):
    return [k for _, _, k in ls.scan_text(text, rel, ls.compile_needles(needles), rel)]


def test_needle_variants_and_slot_reporting():
    assert _kinds("see zorblax-quux here") == ["needle-slot-0"]
    assert _kinds("ZorblaxQuux") == ["needle-slot-0"]
    assert _kinds("id acct-0000-fake") == ["needle-slot-1"]
    assert _kinds("nothing to see") == []


def test_structural_arm_without_config():
    drive = "C" + ":" + "\\" + "Secret Project\\x.py"
    assert "drive-path" in _kinds(drive, needles=[])
    user = "/" + "Users/" + "somebody/file"
    assert "user-profile" in _kinds(user, needles=[])
    mail = "ping someone" + "@" + "mail.test.org"
    assert "email" in _kinds(mail, needles=[])
    key = "sk-" + "ant-" + "abcdefghijklmnop"
    assert "anthropic-key" in _kinds(key, needles=[])


def test_structural_allowlist():
    generic = "C" + ":" + "\\" + "ProgramData\\thing"
    assert _kinds(generic, needles=[]) == []
    assert _kinds("x" + "@" + "example.com", needles=[]) == []
    sidecar = "E" + ":" + "/" + "Sidecars/<CODE> exists)"
    assert _kinds(sidecar, needles=[]) == []
    assert _kinds("E" + ":" + "\\" + "SidecarsX\\y", needles=[]) == ["drive-path"]
    pinned = "C" + ":" + "\\" + "Anything\\here"
    assert ls.scan_text(pinned, "ops/loop/slots.py", [], "ops/loop/slots.py") == []


def test_load_needles_modes(tmp_path):
    assert ls.load_needles(tmp_path / "none.json", environ={}) == ([], "DEGRADED")
    assert ls.load_needles(tmp_path / "none.json", environ={"AL_LEAK_NEEDLES": "abc;def"}) == \
        (["abc", "def"], "ARMED")
    cfg = tmp_path / "c.json"
    cfg.write_text('{"needles": []}')
    try:
        ls.load_needles(cfg, environ={})
        raise AssertionError("empty config must FAULT")
    except ValueError:
        pass


def test_diff_scans_added_lines_and_paths():
    diff = ("+++ b/docs/zorblax_quux.md\n@@\n+clean line\n-removed " + "C" + ":" +
            "\\" + "Old\\gone\n")
    kinds = [k for _, _, k in ls.scan_diff(diff, ls.compile_needles(FAKE))]
    assert kinds == ["needle-slot-0"]


@pytest.mark.git  # plan 097: git ls-files
def test_tracked_tree_is_clean_structurally():
    findings, n = ls.scan_tree(ls.compile_needles([]))
    if n == 0:
        pytest.skip("no tracked file yet (before the initial commit)")
    assert findings == []


def test_program_files_x86_path_is_allowed_past_its_space():
    bs = "/"
    line = "C:" + bs + "Program Files (x86)" + bs + "Game" + bs + "logs" + bs + "Client.txt"
    assert _kinds(line, needles=[]) == []
    assert "drive-path" in _kinds("D:" + bs + "Games" + bs + "x", needles=[])


def test_regex_escape_time_pattern_is_not_a_drive_path():
    # fix-loop-stall: `\d\d:\d\d` (a HH:MM regex) read as drive `d:` + `\d\d`
    # refused plan 031's lane commit at the pre-commit hook
    bs = "\\"
    line = 'assert re.match(r"^' + bs + "d" + bs + "d:" + bs + "d" + bs + 'd$", s)'
    assert _kinds(line, needles=[]) == []
    assert _kinds("rows = [r" + '"' + bs + "| " + bs + "d" + bs + "d:" + bs + "d" + bs
                  + "d " + bs + '|"]', needles=[]) == []
    # a real drive path after a separator is still flagged
    assert "drive-path" in _kinds('p = "' + "C" + ":" + bs + 'x' + bs + 'y"', needles=[])


# --- pre-push: messages already public on the remote ref (MAIN 2246 sec 4) ---

import subprocess  # noqa: E402


def _g(repo, *args):
    # plan 150: bounded, so a git stuck on a lock or prompt fails, never hangs
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, timeout=60).stdout.decode().strip()


def _commit(repo, name, text, msg):
    (repo / name).write_text(text, newline="\n")
    _g(repo, "add", name)
    # plan 150: the machine's global hooks / signing never run on scratch commits
    _g(repo, "-c", "user.name=t", "-c", "user.email=t@example.com",
       "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
       "commit", "-q", "-m", msg)
    return _g(repo, "rev-parse", "HEAD")


def _repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _g(repo, "init", "-q", "-b", "main")
    return repo


def _push_kinds(repo, local, remote):
    rx = ls.compile_needles(FAKE)
    f, _ = ls.scan_pre_push([f"refs/heads/main {local} refs/heads/main {remote}"], rx, cwd=repo)
    return [k for _, _, k in f]


def _rewritten(repo, old_msg, new_file_text="b\n", new_msg="later"):
    """A public commit holding old_msg, then a rewritten twin of it (new SHA,
    same message) plus one more commit, as a history rewrite leaves it."""
    base = _commit(repo, "a.txt", "a\n", "base")
    remote = _commit(repo, "b.txt", "b\n", old_msg)
    _g(repo, "checkout", "-q", "--detach", base)
    (repo / "pad.txt").write_text("p\n", newline="\n")
    _g(repo, "add", "pad.txt")
    _g(repo, "-c", "user.name=u", "-c", "user.email=u@example.com",
       "commit", "-q", "-m", old_msg)
    local = _commit(repo, "c.txt", new_file_text, new_msg)
    return local, remote


@pytest.mark.git
def test_pre_push_exempts_message_already_on_remote(tmp_path):
    repo = _repo(tmp_path)
    local, remote = _rewritten(repo, "Merge pull request #2 from zorblax-quux/dep")
    assert _push_kinds(repo, local, remote) == []


@pytest.mark.git
def test_pre_push_new_message_with_needle_still_fails(tmp_path):
    repo = _repo(tmp_path)
    local, remote = _rewritten(repo, "plain", new_msg="leak Zorblax Quux")
    assert _push_kinds(repo, local, remote) == ["needle-slot-0"]


@pytest.mark.git
def test_pre_push_one_byte_different_message_still_fails(tmp_path):
    repo = _repo(tmp_path)
    base = _commit(repo, "a.txt", "a\n", "base")
    remote = _commit(repo, "b.txt", "b\n", "Merge from zorblax-quux/dep")
    _g(repo, "checkout", "-q", "--detach", base)
    local = _commit(repo, "c.txt", "c\n", "Merge from zorblax-quux/dep!")
    assert _push_kinds(repo, local, remote) == ["needle-slot-0"]


@pytest.mark.git
def test_pre_push_added_line_with_needle_still_fails(tmp_path):
    repo = _repo(tmp_path)
    local, remote = _rewritten(repo, "from zorblax-quux/dep",
                               new_file_text="acct-0000-fake\n")
    assert _push_kinds(repo, local, remote) == ["needle-slot-1"]


@pytest.mark.git
def test_pre_push_new_branch_gets_no_exemption(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a.txt", "a\n", "base")
    local = _commit(repo, "b.txt", "b\n", "from zorblax-quux/dep")
    assert _push_kinds(repo, local, ls.ZERO) == ["needle-slot-0"]


# --- LEAK-WT: a linked worktree reads the main checkout's needle config ---

def _main_and_worktree(tmp_path):
    main = _repo(tmp_path)
    _commit(main, "a.txt", "a\n", "base")
    wt = tmp_path / "wt"
    _g(main, "worktree", "add", "-q", "--detach", str(wt))
    return main, wt


def _write_cfg(repo, needles):
    (repo / "config").mkdir(exist_ok=True)
    (repo / "config" / "leak_needles.json").write_text(
        '{"needles": [' + ", ".join('"%s"' % n for n in needles) + "]}", newline="\n")


@pytest.mark.git
def test_worktree_without_config_reads_main_checkout(tmp_path):
    main, wt = _main_and_worktree(tmp_path)
    _write_cfg(main, FAKE)
    assert ls.main_checkout(wt) == main.resolve()
    path, source = ls.resolve_config(wt)
    assert source == "main-checkout"
    assert path == main.resolve() / "config" / "leak_needles.json"
    assert ls.load_needles(path, environ={}) == (FAKE, "ARMED")


@pytest.mark.git
def test_worktree_local_config_wins(tmp_path):
    main, wt = _main_and_worktree(tmp_path)
    _write_cfg(main, FAKE)
    _write_cfg(wt, ["local-only-xyz"])
    path, source = ls.resolve_config(wt)
    assert source == "local"
    assert ls.load_needles(path, environ={}) == (["local-only-xyz"], "ARMED")


@pytest.mark.git
def test_no_config_anywhere_stays_degraded(tmp_path):
    main, wt = _main_and_worktree(tmp_path)
    path, source = ls.resolve_config(wt)
    assert source == "none"
    assert ls.load_needles(path, environ={}) == ([], "DEGRADED")
    # the main checkout itself has no fallback beyond its own file
    assert ls.main_checkout(main) is None
    assert ls.resolve_config(main)[1] == "none"


def test_not_a_git_repo_has_no_main_checkout(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert ls.main_checkout(plain) is None
    assert ls.resolve_config(plain)[1] == "none"


@pytest.mark.git
def test_report_names_source_never_needles(tmp_path, capsys):
    main, wt = _main_and_worktree(tmp_path)
    _write_cfg(main, FAKE)
    path, source = ls.resolve_config(wt)
    needles, mode = ls.load_needles(path, environ={})
    assert ls.report([], mode, len(needles), source) == 0
    err = capsys.readouterr().err
    assert "ARMED needles=2 config=main-checkout" in err
    for n in FAKE:
        assert n.lower() not in err.lower()


# --- AUDIT-LEAK-MSG (audit 2026-11-17): commit messages at commit time and a
# full-history mode, so a leak in a message is caught before the first push.

def test_message_mode_scans_message_skips_comments(tmp_path):
    rx = ls.compile_needles(FAKE)
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("subject\n\nbody mentions Zorblax Quux\n# zorblax quux in a comment\n",
                   newline="\n")
    kinds = [k for _, _, k in ls.scan_message(msg.read_text(), rx)]
    assert kinds == ["needle-slot-0"]
    clean = "subject\n\n# acct-0000-fake only in git's comment lines\n"
    assert ls.scan_message(clean, rx) == []
    drive = "subject " + "C" + ":" + "\\" + "Secret Project" + "\\" + "x"
    assert [k for _, _, k in ls.scan_message(drive, rx)] == ["drive-path"]


def test_message_mode_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AL_LEAK_NEEDLES", ";".join(FAKE))
    bad = tmp_path / "bad.txt"
    bad.write_text("fix acct-0000-fake\n", newline="\n")
    good = tmp_path / "good.txt"
    good.write_text("fix the parser\n", newline="\n")
    assert ls.main(["--message", str(bad)]) == 2
    assert ls.main(["--message", str(good)]) == 0
    assert ls.main(["--message", str(tmp_path / "missing.txt")]) == 3
    assert "acct-0000-fake" not in capsys.readouterr().err


@pytest.mark.git
def test_history_mode_finds_leak_in_old_commit_and_message(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a.txt", "a\n", "base")
    _commit(repo, "b.txt", "has Zorblax Quux\n", "add b")
    _commit(repo, "b.txt", "clean now\n", "scrub b")  # removed later: still in history
    _commit(repo, "c.txt", "c\n", "msg names acct-0000-fake")
    rx = ls.compile_needles(FAKE)
    findings, n = ls.scan_history(rx, cwd=repo)
    kinds = sorted(k for _, _, k in findings)
    assert kinds == ["needle-slot-0", "needle-slot-1"]
    assert n == 4
    assert any(w == "commit-message" for w, _, _ in findings)


@pytest.mark.git
def test_history_mode_clean_repo(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a.txt", "a\n", "base")
    findings, n = ls.scan_history(ls.compile_needles(FAKE), cwd=repo)
    assert findings == [] and n == 1


def test_commit_msg_hook_runs_the_message_sweep():
    hook = (ROOT / ".githooks" / "commit-msg").read_text(encoding="ascii")
    assert "leak_sweep.py" in hook and "--message" in hook
    # identity strip first, so a stripped trailer is never swept
    assert hook.index("fleet_identity.py") < hook.index("leak_sweep.py")


# --- GP-02 review: pre-push needle config is required, env only adds ---

def test_push_mode_requires_config_and_env_only_adds(tmp_path):
    missing = tmp_path / "none.json"
    assert ls.load_needles(missing, environ={"AL_LEAK_NEEDLES": "abc"}, push=True) == \
        ([], "DEGRADED")
    cfg = tmp_path / "c.json"
    cfg.write_text('{"needles": ["Zorblax Quux"]}', newline="\n")
    assert ls.load_needles(cfg, environ={"AL_LEAK_NEEDLES": "nothing-xyz"}, push=True) == \
        (["Zorblax Quux", "nothing-xyz"], "ARMED")
    # outside a push the env list still replaces the file (tests, CI)
    assert ls.load_needles(cfg, environ={"AL_LEAK_NEEDLES": "nothing-xyz"}) == \
        (["nothing-xyz"], "ARMED")


def test_binary_blob_gets_needle_arm_only():
    rx = ls.compile_needles(FAKE)
    data = b"\x89PNG\0" + "acct-0000-fake".encode("utf-16-le")
    assert [k for _, _, k in ls.scan_blob(data, "x.png", rx)] == ["needle-slot-1"]
    drive = ("C" + ":" + "\\" + "Secret" + "\\" + "x").encode("ascii")
    assert ls.scan_blob(b"\0" + drive, "x.png", rx) == []
    assert [k for _, _, k in ls.scan_blob(drive, "x.txt", rx)] == ["drive-path"]


def test_tree_names_parse():
    raw = b"100644 a.txt\0" + b"\x01" * 20 + b"40000 sub dir\0" + b"\x02" * 20
    assert ls.tree_names(raw, 20) == ["a.txt", "sub dir"]
