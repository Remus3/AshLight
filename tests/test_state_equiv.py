"""TEST-STATE-EQUIV: tools/state_equiv.py replays one synthetic session and
card corpus through the working tree and a reference revision and compares
the snapshots. Identical on a clean tree, a one-character card sentence
change is named by its key path, and the reference export lands under the
sidecar Temp dir and is removed."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "state_equiv.py"
sys.path.insert(0, str(ROOT / "tools"))

import state_equiv  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None
                                or not (ROOT / ".git").exists(),
                                reason="needs a git checkout")


def _env(tmp_path):
    env = dict(os.environ)
    env["AL_SIDECAR_ROOT"] = str(tmp_path / "sidecar")
    env.pop("PYTHONPATH", None)
    return env


def _run(tmp_path, *args):
    return subprocess.run([sys.executable, str(TOOL), "--ref", "HEAD", *args],
                          cwd=str(ROOT), env=_env(tmp_path), capture_output=True,
                          text=True, timeout=300)


def _export_dir(stderr):
    m = re.search(r"exported to (.+)$", stderr, re.M)
    assert m, stderr
    return Path(m.group(1).strip())


def test_identical_for_head_on_a_clean_tree(tmp_path):
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "server"],
                           cwd=str(ROOT), capture_output=True, text=True)
    if dirty.stdout.strip():
        pytest.skip("server/ has uncommitted changes; HEAD is not this tree")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "state_equiv: identical"
    # the reference export lands under the sidecar Temp and is removed
    ref = _export_dir(r.stderr)
    temp = (tmp_path / "sidecar" / "Temp").resolve()
    assert ref.resolve().parent == temp
    assert not ref.exists()
    assert temp.is_dir() and list(temp.iterdir()) == []


def test_a_one_character_card_change_is_named_by_its_key_path(tmp_path):
    tree = state_equiv.export_ref("HEAD", ROOT, tmp_path / "copy")
    hits = [p for p in sorted((tree / "server" / "al").rglob("*.py"))
            if '" for {slot}: {name}"' in p.read_text(encoding="utf-8")]
    assert hits, "the upgrade notice sentence moved"
    src = hits[0].read_text(encoding="utf-8")
    hits[0].write_text(src.replace('" for {slot}: {name}"', '" fir {slot}: {name}"', 1),
                       encoding="utf-8", newline="\n")
    r = _run(tmp_path, "--tree", str(tree))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "differing key path" in r.stdout
    assert re.search(r"^  card\d+:upgrades/upgrades/items/0/head: ref=.*pgrade for "
                     r".* tree=.*pgrade fir ", r.stdout, re.M), r.stdout
    assert not _export_dir(r.stderr).exists()


def test_bad_rev_is_a_setup_error(tmp_path):
    r = subprocess.run([sys.executable, str(TOOL), "--ref", "no-such-rev-xyz"],
                       cwd=str(ROOT), env=_env(tmp_path), capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 2
    assert r.stdout.startswith("state_equiv: error: ")


def test_diff_names_key_paths():
    a = {"x": {"y": [1, 2, {"z": "a"}]}, "k": 1}
    b = {"x": {"y": [1, 3, {"z": "b"}, 4]}, "j": 1}
    assert state_equiv.diff(a, b) == ["j", "k", "x/y/1", "x/y/2/z", "x/y/3"]
    assert state_equiv.diff(a, a) == []


def test_corpus_is_synthetic_and_covers_every_card_kind():
    doc = state_equiv.corpus()
    kinds = {k for k, _ in doc["cards"]}
    assert {"eval", "price", "build", "upgrades", "line", "event", "dismiss"} <= kinds
    names = [s["name"] for s in doc["sessions"]]
    assert "standard_session-1" in names
    events = {p.get("type") for k, p in doc["cards"] if k == "event"}
    assert {"tailer_reset", "tailer_started"} <= events
    # the tool reads no Client.txt and makes no request
    text = TOOL.read_text(encoding="ascii")
    for word in ("urllib", "http.client", "socket", "Client.txt\")"):
        assert word not in text
