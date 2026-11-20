"""TEST-FLOOR-MEMO: the per-file hit memo of tests/test_floor_static.py.

The floor scan keeps each file's hit list keyed by path, size, mtime_ns,
file id and the BANNED table, so the plant and mutation tests stop paying a
full rescan each. A wrong key would hide a planted call, so these tests pin
that a changed file is always read again. The guard module is loaded by its
file path under a private name (one test file never imports another,
tests/test_test_layout.py), which also gives it a memo of its own.
"""

import importlib.util
import os
import time
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent / "test_floor_static.py"
HOUR_NS = 3600 * 1_000_000_000


@pytest.fixture(scope="module")
def fs():
    spec = importlib.util.spec_from_file_location("_floor_static_memo", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tree(fs, tmp_path):
    fs._SCAN_CACHE.clear()
    (tmp_path / "server").mkdir()
    yield tmp_path
    fs._SCAN_CACHE.clear()


def _old_ns(hours):
    """An mtime well past the racy window, distinct per `hours`."""
    return time.time_ns() - hours * HOUR_NS


def _put(path, data, mtime_ns, in_place=False):
    """Write bytes (in place keeps the file id) and set an exact mtime."""
    if in_place:
        with open(path, "r+b") as f:
            f.write(data)
            f.truncate()
    else:
        path.write_bytes(data)
    os.utime(path, ns=(mtime_ns, mtime_ns))


def _ids(fs, root, rel):
    return [h[1] for h in fs.scan(root) if h[0] == rel]


CLEAN = b"x = 'nothing to see here at all'\n"
PLANT = b"user32.SendInput(1, p, 2) # padx\n"


def test_fixture_pair_has_equal_size():
    assert len(CLEAN) == len(PLANT)


def test_same_size_plant_with_new_mtime_is_caught(fs, tree):
    f = tree / "server" / "m.py"
    _put(f, CLEAN, _old_ns(5))
    assert _ids(fs, tree, "server/m.py") == []
    assert str(f.absolute()) in fs._SCAN_CACHE  # the clean result is memoised
    _put(f, PLANT, _old_ns(4), in_place=True)
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]


def test_rewritten_in_place_and_restored_is_rescanned(fs, tree):
    f = tree / "server" / "m.py"
    _put(f, PLANT, _old_ns(6))
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]
    _put(f, CLEAN, _old_ns(5), in_place=True)
    assert _ids(fs, tree, "server/m.py") == []
    _put(f, PLANT, _old_ns(4), in_place=True)
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]


def test_fresh_rewrite_is_never_memoised(fs, tree):
    """A file written just now sits in the racy window: never stored, so a
    same-size rewrite inside one clock tick cannot be served stale."""
    f = tree / "server" / "m.py"
    f.write_bytes(CLEAN)
    assert _ids(fs, tree, "server/m.py") == []
    assert str(f.absolute()) not in fs._SCAN_CACHE
    with open(f, "r+b") as h:
        h.write(PLANT)
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]


def test_removed_banned_pattern_reports_nothing(fs, tree, monkeypatch):
    f = tree / "server" / "m.py"
    _put(f, PLANT, _old_ns(5))
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]  # memoised
    full = list(fs.BANNED)
    monkeypatch.setattr(fs, "BANNED", [b for b in full if b[0] != "SendInput"])
    assert _ids(fs, tree, "server/m.py") == []
    monkeypatch.setattr(fs, "BANNED", full)
    assert _ids(fs, tree, "server/m.py") == ["SendInput"]


def _poison(fs, f, stamp_st):
    """Store a fake hit list under the key the file has at stamp_st."""
    sig = fs._banned_sig()
    stamp = (stamp_st.st_size, stamp_st.st_mtime_ns, stamp_st.st_ino, sig)
    fs._SCAN_CACHE[str(f.absolute())] = (stamp, (("FAKE", 1, "poison"),))


def test_memo_is_served_only_while_the_key_matches(fs, tree):
    f = tree / "server" / "m.py"
    _put(f, CLEAN, _old_ns(5))
    _poison(fs, f, f.stat())
    assert _ids(fs, tree, "server/m.py") == ["FAKE"]  # the memo is in use


def test_memo_never_served_after_an_mtime_change(fs, tree):
    f = tree / "server" / "m.py"
    _put(f, CLEAN, _old_ns(5))
    _poison(fs, f, f.stat())
    os.utime(f, ns=(_old_ns(4), _old_ns(4)))
    assert _ids(fs, tree, "server/m.py") == []


def test_memo_never_served_after_a_size_change(fs, tree):
    f = tree / "server" / "m.py"
    _put(f, CLEAN, _old_ns(5))
    st = f.stat()
    _poison(fs, f, st)
    _put(f, CLEAN + b"# more\n", st.st_mtime_ns, in_place=True)
    assert f.stat().st_mtime_ns == st.st_mtime_ns
    assert _ids(fs, tree, "server/m.py") == []
