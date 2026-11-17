"""AREA-TEST batch 6: the shared runtime-file helper (server/al/jsonfile.py)
and number sanitizer (server/al/num.py), plus the two overflow bugs the
num.py move fixed (runhistory, calcwire)."""

import json
import os

import pytest

from server.al import jsonfile, num, runhistory
from server.al.theorycraft import calcwire

CAFE = "caf" + chr(0xE9)


def test_read_missing_corrupt_and_wrong_kind(tmp_path):
    p = tmp_path / "x.json"
    assert jsonfile.read_json(p) is None
    assert jsonfile.read_json(p, default={}) == {}
    p.write_text("{not json", encoding="ascii")
    assert jsonfile.read_json(p, default=[]) == []
    p.write_text("[1, 2]", encoding="ascii")
    assert jsonfile.read_json(p) == [1, 2]
    assert jsonfile.read_json(p, kind=dict) is None
    assert jsonfile.read_json(p, kind=(dict, list)) == [1, 2]


def test_read_size_cap(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"a": "b" * 100}), encoding="ascii")
    assert jsonfile.read_json(p, max_bytes=10) is None
    assert jsonfile.read_json(p, max_bytes=10_000)["a"] == "b" * 100


def test_read_encoding(tmp_path):
    p = tmp_path / "x.json"
    p.write_bytes(json.dumps({"n": CAFE}, ensure_ascii=False).encode("utf-8"))
    assert jsonfile.read_json(p) == {"n": CAFE}
    # an ASCII-only reader treats non-ASCII bytes as a corrupt file
    assert jsonfile.read_json(p, encoding="ascii") is None


def test_read_directory_is_tolerated(tmp_path):
    assert jsonfile.read_json(tmp_path, default="d") == "d"


def test_write_json_bytes_ascii_lf(tmp_path):
    p = tmp_path / "deep" / "dir" / "x.json"
    doc = {"b": 1, "a": [CAFE]}
    jsonfile.write_json(p, doc, sort_keys=True)
    raw = p.read_bytes()
    assert raw == (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True)
                   + "\n").encode("ascii")
    assert b"\r" not in raw
    assert not jsonfile.tmp_path(p).exists()
    jsonfile.write_json(p, doc, indent=2)
    assert p.read_bytes() == (json.dumps(doc, indent=2) + "\n").encode("ascii")


def test_write_text_non_ascii_leaves_target(tmp_path):
    p = tmp_path / "x.txt"
    jsonfile.write_text(p, "old\n")
    with pytest.raises(UnicodeEncodeError):
        jsonfile.write_text(p, CAFE)
    assert p.read_text(encoding="ascii") == "old\n"


def test_write_is_atomic_replace(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    jsonfile.write_json(p, {"v": 1})
    seen = []
    real = os.replace

    def spy(src, dst):
        # the old file is still whole while the new text sits in the temp file
        seen.append((jsonfile.read_json(dst), jsonfile.read_json(src)))
        real(src, dst)

    monkeypatch.setattr(jsonfile.os, "replace", spy)
    jsonfile.write_json(p, {"v": 2})
    assert seen == [({"v": 1}, {"v": 2})]
    assert jsonfile.read_json(p) == {"v": 2}


def test_write_bytes(tmp_path):
    p = tmp_path / "a" / "b.bin"
    jsonfile.write_bytes(p, b"\x00\x01")
    assert p.read_bytes() == b"\x00\x01"


@pytest.mark.parametrize("v,want", [
    (1, 1.0), (2.5, 2.5), (-3, -3.0), (True, None), (None, None), ("1", None),
    (float("nan"), None), (float("inf"), None), (10 ** 400, None),
])
def test_finite(v, want):
    assert num.finite(v) == want


def test_runhistory_huge_int_is_dropped_not_raised(tmp_path):
    """Regression (found by the num.py move): a 400-digit started_at in a
    hand-edited run_history.json raised OverflowError out of load()."""
    p = tmp_path / "runs.json"
    p.write_text('{"schema": 1, "runs": [{"started_at": 1' + "0" * 400 + '},'
                 ' {"started_at": 5}]}', encoding="ascii")
    got = runhistory.load(p)
    assert [r["started_at"] for r in got] == [5.0]
    assert runhistory.clean_run({"started_at": -1}) is None


def test_calcwire_huge_int_is_not_a_number():
    """Regression: math.isfinite(10**400) raised OverflowError in map_outputs."""
    assert calcwire._num(10 ** 400) is None
    assert calcwire._num(7) == 7.0
    assert calcwire.map_outputs({"FullDPS": 10 ** 400, "CombinedDPS": 3,
                                 "TotalEHP": 9})["dps"] == 3.0
