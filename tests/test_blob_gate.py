"""Go-public gate 6 blob checker (decision 0079); tmp git repos only."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import blob_gate as bg  # noqa: E402

KB = 1000


def _g(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, timeout=60).stdout.decode().strip()


def _commit(repo, files, msg="c"):
    for name, data in files.items():
        p = repo / name
        if data is None:
            _g(repo, "rm", "-q", name)
            continue
        p.write_bytes(data)
        _g(repo, "add", name)
    _g(repo, "-c", "user.name=t", "-c", "user.email=t@example.com",
       "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
       "commit", "-q", "-m", msg)


def _repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _g(repo, "init", "-q", "-b", "main")
    _commit(repo, {"small.bin": b"\x00\x01" * 100, "a.txt": b"hello\n"})
    return repo


def _text(n):
    line = b"plain ascii text line\n"
    return (line * (n // len(line) + 1))[:n]


def _binary(n):
    return (b"\x89PNG\x00\xff" * (n // 6 + 1))[:n]


def test_is_text():
    assert bg.is_text(b"abc\n")
    assert bg.is_text(b"caf\xc3\xa9")
    assert not bg.is_text(b"ab\x00c")
    assert not bg.is_text(b"\xff\xfe bad utf-8")


def test_clean_repo_passes(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert bg.main(["--repo", str(repo)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("blob-gate: ok ref=main")


def test_text_between_limits_passes(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"plan.json": _text(1300 * KB)})
    findings, _ = bg.scan(repo)
    assert findings == []


def test_binary_over_500kb_fails(tmp_path, capsys):
    repo = _repo(tmp_path)
    _commit(repo, {"big.png": _binary(501 * KB)})
    assert bg.main(["--repo", str(repo)]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("blob-gate: binary blob ")
    assert out[0].endswith(f"{501 * KB} B over {500 * KB} B: big.png")


def test_binary_at_limit_passes(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"edge.png": _binary(500 * KB)})
    assert bg.scan(repo)[0] == []


def test_invalid_utf8_without_nul_counts_as_binary(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"latin.txt": _text(600 * KB) + b"\xe9\n"})
    findings, _ = bg.scan(repo)
    assert [(f[2], f[4]) for f in findings] == [("binary", "latin.txt")]


def test_text_over_2mb_fails(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"huge.json": _text(2 * 1000 * KB + 1)})
    findings, _ = bg.scan(repo)
    assert [(f[2], f[3], f[4]) for f in findings] == [("text", 2 * 1000 * KB, "huge.json")]


def test_history_only_blob_is_checked(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"old.bin": _binary(700 * KB)}, "add")
    _commit(repo, {"old.bin": None}, "remove")
    findings, _ = bg.scan(repo)
    assert [f[4] for f in findings] == ["old.bin"]


def test_blob_off_the_ref_is_ignored(tmp_path):
    repo = _repo(tmp_path)
    _g(repo, "checkout", "-q", "-b", "side")
    _commit(repo, {"side.bin": _binary(700 * KB)})
    _g(repo, "checkout", "-q", "main")
    assert bg.scan(repo, "main")[0] == []
    assert [f[4] for f in bg.scan(repo, "side")[0]] == ["side.bin"]


def test_custom_limits(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"mid.txt": _text(300 * KB)})
    assert bg.scan(repo, binary_max=100 * KB, text_max=200 * KB)[0][0][2] == "text"


def test_missing_ref_fails_closed(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert bg.main(["--repo", str(repo), "--ref", "nope"]) == 1
    assert capsys.readouterr().out.startswith("blob-gate: FAULT ")
