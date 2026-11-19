"""AREA-TEST batch 6: the shared runtime-file helper (server/al/jsonfile.py)
and number sanitizer (server/al/num.py), plus the two overflow bugs the
num.py move fixed (runhistory, calcwire). RUN-DURABLE-JSONFILE (F-014):
retried replace, unique temps, fsync, .bak restore and the Saver
(research 0050 cases C7, C8, C9)."""

import json
import os
import sys
import threading
import time
from pathlib import Path

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


def _no_temps(d):
    return [q.name for q in Path(d).iterdir() if q.name.endswith(".tmp")]


def test_replace_retries_on_permission_error_and_leaves_no_temp(tmp_path, monkeypatch):
    """C7: os.replace fails twice with PermissionError, the third try lands
    and no temp file is left; when every try fails the target keeps its old
    content, the error is raised and the temp file is gone."""
    p = tmp_path / "x.json"
    jsonfile.write_json(p, {"v": 1})
    sleeps = []
    monkeypatch.setattr(jsonfile, "_sleep", sleeps.append)
    real = os.replace
    calls = []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) <= 2:
            raise PermissionError(13, "held")
        real(src, dst)

    monkeypatch.setattr(jsonfile.os, "replace", flaky)
    jsonfile.write_json(p, {"v": 2})
    assert len(calls) == 3
    assert jsonfile.read_json(p) == {"v": 2}
    assert _no_temps(tmp_path) == []
    assert len(sleeps) == 2

    def never(src, dst):
        calls.append(src)
        raise PermissionError(13, "held")

    calls.clear()
    sleeps.clear()
    monkeypatch.setattr(jsonfile.os, "replace", never)
    with pytest.raises(PermissionError):
        jsonfile.write_json(p, {"v": 3})
    assert len(calls) == 6  # one try plus 5 retries
    assert abs(sum(sleeps) - 0.25) < 1e-9
    assert jsonfile.read_json(p) == {"v": 2}
    assert _no_temps(tmp_path) == []


def test_non_permission_error_is_not_retried(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    calls = []

    def boom(src, dst):
        calls.append(src)
        raise OSError(28, "disk full")

    monkeypatch.setattr(jsonfile.os, "replace", boom)
    with pytest.raises(OSError):
        jsonfile.write_json(p, {"v": 1})
    assert len(calls) == 1
    assert not p.exists()
    assert _no_temps(tmp_path) == []


def test_fsync_runs_unless_sync_false(tmp_path, monkeypatch):
    seen = []
    real = os.fsync
    monkeypatch.setattr(jsonfile.os, "fsync", lambda fd: (seen.append(fd), real(fd)))
    jsonfile.write_json(tmp_path / "a.json", {"v": 1})
    assert len(seen) == 1
    jsonfile.write_text(tmp_path / "hb.json", "{}\n", sync=False)
    assert len(seen) == 1
    jsonfile.write_json(tmp_path / "b.json", {"v": 1}, backup=True)
    assert len(seen) == 3  # main and .bak


@pytest.mark.skipif(sys.platform != "win32", reason="Windows share modes")
def test_reader_holding_target_never_sees_torn_file(tmp_path, monkeypatch):
    """C8 (Windows): a reader holds the target open (no delete sharing) while
    a write runs; the replace is retried until the reader lets go, and every
    read, during and after, is a whole document, old or new."""
    p = tmp_path / "x.json"
    old = {"v": 1, "pad": "a" * 50000}
    new = {"v": 2, "pad": "b" * 50000}
    jsonfile.write_json(p, old)
    held = threading.Event()
    release = threading.Event()
    reads = []

    def holder():
        with open(p, "rb") as fh:
            held.set()
            release.wait(5)
            reads.append(json.loads(fh.read().decode("ascii")))

    t = threading.Thread(target=holder)
    t.start()
    assert held.wait(5)
    sleeps = []

    def sleep(d):
        sleeps.append(d)
        if len(sleeps) == 2:
            release.set()
            t.join(5)

    monkeypatch.setattr(jsonfile, "_sleep", sleep)
    jsonfile.write_json(p, new)
    t.join(5)
    assert sleeps, "the held target made the replace retry"
    assert reads == [old]
    assert jsonfile.read_json(p) == new
    assert _no_temps(tmp_path) == []

    # a busy reader loop beside a writer loop: never a torn read
    monkeypatch.setattr(jsonfile, "_sleep", time.sleep)
    stop = threading.Event()
    bad = []

    def reader():
        while not stop.is_set():
            try:
                raw = p.read_bytes()
            except OSError:
                continue
            try:
                doc = json.loads(raw.decode("ascii"))
            except ValueError:
                bad.append(len(raw))
                continue
            if doc["pad"] not in ("a" * 50000, "b" * 50000):
                bad.append("mixed")

    r = threading.Thread(target=reader)
    r.start()
    try:
        for i in range(40):
            doc = old if i % 2 else new
            try:
                jsonfile.write_json(p, doc)
            except PermissionError:
                pass  # held longer than 250 ms: the old file stays whole
    finally:
        stop.set()
        r.join(5)
    assert bad == []
    assert jsonfile.read_json(p)["v"] in (1, 2)
    assert _no_temps(tmp_path) == []


def test_backup_restores_when_main_is_empty_or_half(tmp_path):
    """C9: config/local.json cut to 0 bytes, then to half: the backup is
    restored (into the main file too) and a later write works."""
    p = tmp_path / "config" / "local.json"
    doc = {"web_data": True, "contact": "x", "layout": list(range(50))}
    jsonfile.write_json(p, doc, backup=True)
    bak = jsonfile.bak_path(p)
    assert bak.read_bytes() == p.read_bytes()
    jsonfile.pop_restored()

    p.write_bytes(b"")
    assert jsonfile.read_json(p) is None
    assert jsonfile.read_json(p, default={}, backup=True) == doc
    assert jsonfile.read_json(p) == doc  # main rewritten from the backup
    assert jsonfile.pop_restored() == [str(p)]
    assert jsonfile.pop_restored() == []

    raw = p.read_bytes()
    p.write_bytes(raw[: len(raw) // 2])
    assert jsonfile.read_json(p, kind=dict, backup=True) == doc
    assert jsonfile.read_json(p) == doc
    assert jsonfile.pop_restored() == [str(p)]

    doc2 = dict(doc, web_data=False)
    jsonfile.write_json(p, doc2, backup=True)
    assert jsonfile.read_json(p, backup=True) == doc2
    assert jsonfile.read_json(bak) == doc2
    assert jsonfile.pop_restored() == []
    assert _no_temps(p.parent) == []


def test_backup_edges(tmp_path):
    p = tmp_path / "x.json"
    # a missing main file is not restored (a cleared store removes both)
    jsonfile.write_json(p, {"v": 1}, backup=True)
    p.unlink()
    assert jsonfile.read_json(p, default="d", backup=True) == "d"
    assert not p.exists()
    # wrong kind in main counts as damaged
    p.write_text("[1]", encoding="ascii")
    assert jsonfile.read_json(p, kind=dict, backup=True) == {"v": 1}
    # a broken backup gives the default and leaves the main file alone
    p.write_text("{", encoding="ascii")
    jsonfile.bak_path(p).write_text("{", encoding="ascii")
    assert jsonfile.read_json(p, default={}, backup=True) == {}
    assert p.read_text(encoding="ascii") == "{"
    # without backup=True the .bak is never read
    jsonfile.bak_path(p).write_text('{"v": 9}', encoding="ascii")
    assert jsonfile.read_json(p) is None
    jsonfile.pop_restored()


def test_unique_temp_names_do_not_collide(tmp_path):
    p = tmp_path / "x.json"
    names = {jsonfile._unique_tmp(p) for _ in range(200)}
    assert len(names) == 200
    assert all(n.parent == tmp_path and n.name.startswith("x.json.")
               and n.name.endswith(".tmp") for n in names)
    assert jsonfile.tmp_path(p) == tmp_path / "x.json.tmp"
    # a stale fixed-name temp from an old build does not block a write
    jsonfile.tmp_path(p).write_text("junk", encoding="ascii")
    jsonfile.write_json(p, {"v": 0})
    assert jsonfile.read_json(p) == {"v": 0}

    # two writers on one target at once: every write lands whole
    errors = []

    def writer(k):
        for i in range(25):
            try:
                jsonfile.write_json(p, {"k": k, "i": i})
            except Exception as exc:  # pragma: no cover - the failure report
                errors.append(repr(exc))

    ts = [threading.Thread(target=writer, args=(k,)) for k in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert errors == []
    assert jsonfile.read_json(p)["i"] == 24
    assert _no_temps(tmp_path) == ["x.json.tmp"]


def test_saver_backoff_1_5_30_60():
    now = [0.0]
    attempts = []
    fail = [True]

    def save():
        attempts.append(now[0])
        if fail[0]:
            raise OSError(28, "disk full")

    s = jsonfile.Saver(save, clock=lambda: now[0])
    assert s.flush() is True and attempts == []  # nothing dirty
    s.mark()
    while now[0] <= 160:
        s.flush()
        s.mark()  # changes keep coming; they do not shorten the wait
        now[0] += 0.5
    assert attempts == [0.0, 1.0, 6.0, 36.0, 96.0, 156.0]
    assert s.dirty and s.failures == 6
    assert s.last_error.startswith("OSError")
    # force ignores the back-off; a success clears everything
    fail[0] = False
    assert s.flush(force=True) is True
    assert not s.dirty and s.failures == 0 and s.last_error is None
    assert s.flush() is True
    n = len(attempts)
    s.mark()
    assert s.flush() is True and len(attempts) == n + 1
    # the next failure starts again at 1 s
    fail[0] = True
    s.mark()
    t0 = now[0]
    assert s.flush() is False
    assert s.next_at == t0 + 1.0
    assert s.flush(now=t0 + 0.9) is False and len(attempts) == n + 2
    assert s.flush(now=t0 + 1.0) is False and len(attempts) == n + 3


def test_saver_with_jsonfile_store(tmp_path):
    p = tmp_path / "store.json"
    data = {"runs": []}
    s = jsonfile.Saver(lambda: jsonfile.write_json(p, data, backup=True),
                       clock=lambda: 0.0)
    data["runs"].append(1)
    s.mark()
    assert s.flush() is True
    assert jsonfile.read_json(p) == {"runs": [1]}
    assert jsonfile.read_json(jsonfile.bak_path(p)) == {"runs": [1]}


def test_written_files_end_in_lf(tmp_path):
    files = []
    a = tmp_path / "a.json"
    jsonfile.write_json(a, {"x": [1, {"y": "z"}], "n": CAFE}, backup=True)
    files += [a, jsonfile.bak_path(a)]
    b = tmp_path / "b.txt"
    jsonfile.write_text(b, "one\ntwo\n", sync=False)
    files.append(b)
    for f in files:
        raw = f.read_bytes()
        assert raw.endswith(b"\n")
        assert b"\r" not in raw
        raw.decode("ascii")


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
