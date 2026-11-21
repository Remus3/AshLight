"""PUB-DEPBOT-TICK: the loop tick launches tools/dependabot_reapply.py run
once per 24 h, never while a worker is alive, never without an origin remote,
never while HALTed, and a fault in the check is a line, never a raise.
Pure: fake git, fake Popen, fake pid check; no process, no network."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import loop_base  # noqa: E402
import loop_depbot  # noqa: E402

DAY = 24 * 3600


class FakePopen:
    def __init__(self, pid=4242, fail=False):
        self.calls = []
        self.pid_next = pid
        self.fail = fail

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        if self.fail:
            raise OSError("no such file")

        class P:
            pass
        p = P()
        p.pid = self.pid_next
        return p


def git_origin(args):
    assert args == ["remote", "get-url", "origin"]
    return 0, "https://example.invalid/owner/repo.git"


def git_none(args):
    return 2, ""


def check(root, now, popen, git=git_origin, alive=lambda pid: False):
    return loop_depbot.loop_check(root, now, git=git, popen=popen, pid_alive=alive)


def test_launches_once_per_24_hours(tmp_path):
    pop = FakePopen()
    line = check(tmp_path, 1000.0, pop)
    assert line == "depbot: re-apply worker launched (pid 4242)"
    assert len(pop.calls) == 1
    argv, kw = pop.calls[0]
    assert argv[1:] == [str(tmp_path / "tools" / "dependabot_reapply.py"), "run"]
    assert Path(argv[0]).name.lower().startswith("python")
    assert kw["cwd"] == str(tmp_path)
    assert kw["stdin"] is subprocess.DEVNULL and kw["stdout"] is subprocess.DEVNULL
    flags = loop_base._NO_WINDOW | loop_base._DETACHED | loop_base._BREAKAWAY
    assert kw["creationflags"] == flags
    st = json.loads((tmp_path / loop_depbot.STATE_REL).read_text(encoding="ascii"))
    assert st == {"launched": 1000.0, "pid": 4242}
    # the worker has ended; still inside 24 h -> nothing
    assert check(tmp_path, 1000.0 + DAY - 1, pop) is None
    assert len(pop.calls) == 1
    # 24 h later -> one more launch
    assert check(tmp_path, 1000.0 + DAY, pop).startswith("depbot: re-apply worker launched")
    assert len(pop.calls) == 2


def test_not_while_a_worker_is_alive(tmp_path):
    pop = FakePopen()
    check(tmp_path, 0.0, pop)
    seen = []

    def alive(pid):
        seen.append(pid)
        return True
    assert check(tmp_path, DAY + 5, pop, alive=alive) == "depbot worker in flight"
    assert seen == [4242] and len(pop.calls) == 1


def test_never_without_origin(tmp_path):
    pop = FakePopen()
    assert check(tmp_path, 0.0, pop, git=git_none) is None
    assert pop.calls == []
    assert not (tmp_path / loop_depbot.STATE_REL).exists()


def test_never_while_halted(tmp_path):
    halt = tmp_path / loop_depbot.HALT_REL
    halt.parent.mkdir(parents=True)
    halt.write_text("", encoding="ascii")
    pop = FakePopen()
    assert check(tmp_path, 0.0, pop) is None
    assert pop.calls == []


def test_a_fault_returns_a_line_never_raises(tmp_path):
    def bad_git(args):
        raise RuntimeError("boom")
    line = check(tmp_path, 0.0, FakePopen(), git=bad_git)
    assert line == "depbot: RuntimeError: boom"


def test_a_failed_launch_is_a_line_and_waits_a_day(tmp_path):
    pop = FakePopen(fail=True)
    line = check(tmp_path, 0.0, pop)
    assert line.startswith("depbot: worker launch failed")
    assert len(pop.calls) == 2  # with and without the breakaway flag
    assert check(tmp_path, 60.0, pop) is None


def test_a_scratch_root_without_seams_does_nothing(tmp_path):
    assert loop_depbot.loop_check(tmp_path, 0.0) is None
    assert not (tmp_path / "ops").exists()


def test_join():
    assert loop_depbot.join(None, None) is None
    assert loop_depbot.join("a", None) == "a"
    assert loop_depbot.join(None, "b") == "b"
    assert loop_depbot.join("a", "b") == "a; b"
    assert loop_depbot.join("  ", None) is None


def test_al_loop_drift_seam_joins_the_depbot_check():
    src = (ROOT / "tools" / "al_loop.py").read_text(encoding="utf-8")
    body = src.split("def _drift_check(", 1)[1].split("\ndef ", 1)[0]
    assert "loop_depbot.loop_check(root, now)" in body
    assert "loop_depbot.join(" in body and "tc_drift.loop_check(root, now)" in body


def test_module_never_imports_al_loop():
    src = (ROOT / "tools" / "loop_depbot.py").read_text(encoding="utf-8")
    assert "import al_loop" not in src and "from al_loop" not in src
