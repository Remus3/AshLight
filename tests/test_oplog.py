"""RUN-OPLOG (F-153, decision 0067): events.jsonl holds one typed JSON line
per own event; no free-text field type exists; the file is bounded."""

import json

from server.al import metrics, oplog, paths
from server.al.core import Core


def _lines(path):
    return [json.loads(x) for x in path.read_text(encoding="ascii").splitlines()]


def test_free_text_value_is_dropped_and_counted(tmp_path):
    before = metrics.counter(oplog.DROPPED)
    log = oplog.OpLog(tmp_path / oplog.FILE_NAME)
    rec = log.write("press", outcome="Some Item Name", ms=3.5, where="logs/x/Client.txt")
    assert rec is not None and "outcome" not in rec and "where" not in rec
    assert rec["ms"] == 3.5
    assert log.write("chat", text="hi") is None  # an unknown kind is refused
    log.write("fetch", host="poe.ninja", cls="2xx", ms=float("nan"), **{"Bad Key": 1})
    assert log.dropped == 5
    assert metrics.counter(oplog.DROPPED) - before == 5
    text = (tmp_path / oplog.FILE_NAME).read_text(encoding="ascii")
    assert "Some Item" not in text and "Client.txt" not in text and "chat" not in text
    assert [r["kind"] for r in _lines(tmp_path / oplog.FILE_NAME)] == ["press", "fetch"]
    for good in (None, True, 3, 1.5, "poe.ninja", "0.9.0+abc123def456.dev"):
        assert oplog.typed(good)
    for bad in ("Has Space", "a/b", "a\\b", "", "X", "x" * 65, [], {}, float("inf")):
        assert not oplog.typed(bad)


def test_replayed_session_writes_expected_kinds_in_order(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    path = core.runtime / oplog.FILE_NAME
    assert core.oplog.path == path
    core.port = 8962
    oplog.record_start(core)
    core.bus.publish({"type": "tailer_started", "path": str(tmp_path / "Client.txt"),
                      "offset": 0, "file_size": 10, "resumed": False})
    core.bus.publish({"type": "tailer_reset", "reason": "truncated",
                      "path": str(tmp_path / "Client.txt")})
    core.bus.publish({"type": "tailer_restarted", "restarts": 1})
    core.bus.publish({"type": "chat", "text": "not mine to keep"})
    metrics.emit("fetch", host="poe.ninja", cls="2xx", ms=12.0)
    metrics.emit("calc", cmd="calc", outcome="timeout", ms=30000.0)
    metrics.emit("press", outcome="empty", ms=1.0)
    metrics.emit("unrelated", n=1)
    core.record_consent(True)
    core.set_web_data(True)
    core.reload_web += 1
    metrics.inc("calc.start")
    core.oplog_watch.tick(force=True)
    oplog.record_stop(core, "signal", "SIGINT")
    metrics.emit("press", outcome="item", ms=2.0)  # after the stop: no line
    core.close()
    recs = _lines(path)
    assert [r["kind"] for r in recs] == [
        "start", "reader", "reader", "reader", "fetch", "calc", "press",
        "consent", "web_data", "reload", "calc_start", "stop"]
    assert recs[0]["port"] == 8962 and isinstance(recs[0]["pid"], int)
    assert recs[0]["build"]
    assert [r["event"] for r in recs[1:4]] == ["start", "reset", "death"]
    assert recs[2]["reason"] == "truncated" and recs[3]["restarts"] == 1
    assert recs[5]["outcome"] == "timeout"
    assert recs[7] == dict(recs[7], what="log", on=True)
    assert recs[8]["on"] is True and recs[10]["n"] == 1
    assert recs[-1]["reason"] == "signal" and recs[-1]["detail"] == "sigint"
    text = path.read_text(encoding="ascii")
    assert str(tmp_path) not in text and "Client.txt" not in text
    assert "path" not in text and "not mine" not in text
    assert all(set(r) >= {"t", "kind"} and r["t"].endswith("Z") for r in recs)


def test_file_is_bounded_and_rotated(tmp_path):
    path = tmp_path / oplog.FILE_NAME
    log = oplog.OpLog(path, max_bytes=2000)
    for i in range(400):
        assert log.write("press", outcome="item", ms=float(i)) is not None
    old = path.with_name(oplog.FILE_NAME + ".1")
    assert old.exists() and path.exists()
    assert path.stat().st_size <= 2000 + 200
    assert old.stat().st_size <= 2000 + 200
    assert sorted(p.name for p in tmp_path.iterdir()) == [oplog.FILE_NAME,
                                                          oplog.FILE_NAME + ".1"]
    assert _lines(path)[-1]["ms"] == 399.0  # the newest line is kept
    assert log.errors == 0 and log.written == 400
    raw = path.read_bytes() + old.read_bytes()
    assert b"\r" not in raw and all(b < 128 for b in raw)


def test_test_core_writes_under_tmp_runtime_only(tmp_path, monkeypatch):
    sidecar = tmp_path / "sidecar"
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(sidecar))
    core = Core(runtime=tmp_path / "rt", tail=False)
    assert core.oplog.path.parent == core.runtime
    metrics.emit("press", outcome="empty", ms=1.0)
    core.close()
    assert (core.runtime / oplog.FILE_NAME).exists()
    assert not (paths.sidecar_dir("Logs") / oplog.FILE_NAME).exists()
    assert not sidecar.exists() or not any(sidecar.rglob(oplog.FILE_NAME))

    class Real:
        _real = True
        runtime = tmp_path / "unused"
    from server.al.plug import oplog as plug_oplog
    assert plug_oplog.log_path(Real()) == paths.sidecar_dir("Logs") / oplog.FILE_NAME


def test_only_the_newest_log_records_emits_and_subscriptions_stay_one(tmp_path):
    old = oplog.OpLog(tmp_path / "old" / oplog.FILE_NAME)
    old.watch_metrics()
    n = len(metrics.REGISTRY._subs)
    new = oplog.OpLog(tmp_path / "new" / oplog.FILE_NAME)
    new.watch_metrics()
    assert len(metrics.REGISTRY._subs) == n  # one subscription per process
    assert new.owns_metrics() and not old.owns_metrics()
    metrics.emit("press", outcome="empty", ms=1.0)
    assert not old.path.exists()  # an earlier (test) core writes nothing more
    assert [r["kind"] for r in _lines(new.path)] == ["press"]
    new.close()
    metrics.emit("press", outcome="empty", ms=1.0)
    assert len(_lines(new.path)) == 1 and not new.owns_metrics()
