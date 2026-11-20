"""A core that dies must leave a trace in core.log (pythonw has no stderr).

An unhandled exception in any thread is logged; the core also refreshes a
small heartbeat file so the time of a silent external kill is bounded.
OBS-CRASH (F-105): every exit path writes ops/runtime/last-exit.json (stop
request, hot reload, signal, a crash in the main or a worker thread, and
the keepalive's kill of a hung core); atomic, ASCII, LF, bounded.
"""

import json
import logging
import os
import signal
import sys
import threading

import pytest

from server.al import __main__ as entry
from server.al import exitrecord, hotreload, jsonfile
from server.al import keepalive as ka


def test_thread_exception_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    log = logging.getLogger("al.test.crash")
    entry.install_crash_logging(log)

    def boom():
        raise RuntimeError("tail exploded")

    with caplog.at_level(logging.ERROR, logger="al.test.crash"):
        t = threading.Thread(target=boom, name="al-tail")
        t.start()
        t.join()
    rec = [r for r in caplog.records if "al-tail" in r.getMessage()]
    assert rec and rec[0].exc_info and "tail exploded" in str(rec[0].exc_info[1])


def test_main_thread_exception_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    log = logging.getLogger("al.test.crash2")
    entry.install_crash_logging(log)
    with caplog.at_level(logging.ERROR, logger="al.test.crash2"):
        try:
            raise ValueError("main died")
        except ValueError:
            sys.excepthook(*sys.exc_info())
    assert any("main died" in str(r.exc_info[1]) for r in caplog.records if r.exc_info)


def test_heartbeat_file(tmp_path):
    hb = tmp_path / "core.alive"
    entry.write_heartbeat(hb, pid=4242, port=8960, now=1000.0)
    data = json.loads(hb.read_text(encoding="ascii"))
    assert data == {"pid": 4242, "port": 8960, "updated": 1000.0}
    entry.write_heartbeat(hb, pid=4242, port=8960, now=1030.0)
    assert json.loads(hb.read_text(encoding="ascii"))["updated"] == 1030.0


# -- OBS-CRASH (F-105): last-exit.json on every exit path

def _record(runtime):
    raw = (runtime / exitrecord.FILE).read_bytes()
    raw.decode("ascii")  # ASCII only
    assert b"\r" not in raw and raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert len(raw) <= exitrecord.MAX_BYTES
    return json.loads(raw)


def test_record_is_atomic_ascii_lf_and_bounded(tmp_path, monkeypatch):
    calls = []
    real = jsonfile.write_json

    def spy(*a, **k):
        calls.append(a[0])
        return real(*a, **k)
    monkeypatch.setattr(jsonfile, "write_json", spy)
    # built at run time so the leak sweep sees no machine path
    drive = "C" + ":" + "\\".join(["", "Users", "someone", "x.py"])
    detail = ("café failed at " + drive + " and /home/u/a/b.py "
              "and \\\\host\\share\\f\nsecond line " + "y" * 400)
    assert exitrecord.write(tmp_path, exitrecord.CRASH, detail, now=1000.0, pid=42)
    assert calls == [tmp_path / exitrecord.FILE]  # through the atomic helper
    doc = _record(tmp_path)
    assert set(doc) == {"at", "pid", "reason", "detail"}
    assert doc["at"] == 1000.0 and doc["pid"] == 42 and doc["reason"] == "crash"
    d = doc["detail"]
    assert len(d) <= exitrecord.DETAIL_MAX and "\n" not in d
    assert "someone" not in d and "/home/" not in d and "host" not in d
    assert "<path>" in d
    assert [p.name for p in tmp_path.iterdir()] == [exitrecord.FILE]  # no temp left
    assert exitrecord.read(tmp_path)["reason"] == "crash"
    with pytest.raises(ValueError):
        exitrecord.write(tmp_path, "bogus")


def test_failed_write_keeps_old_record_and_never_raises(tmp_path, monkeypatch):
    exitrecord.write(tmp_path, exitrecord.STOP, now=1.0)
    monkeypatch.setattr(jsonfile, "_sleep", lambda s: None)

    def refuse(src, dst):
        raise PermissionError("held")
    monkeypatch.setattr(jsonfile.os, "replace", refuse)
    assert exitrecord.write(tmp_path, exitrecord.CRASH, now=2.0) is False
    monkeypatch.undo()
    assert exitrecord.read(tmp_path)["reason"] == "stop"
    assert [p.name for p in tmp_path.iterdir()] == [exitrecord.FILE]


def test_read_rejects_malformed_and_oversized(tmp_path):
    f = tmp_path / exitrecord.FILE
    assert exitrecord.read(tmp_path) is None
    for text in ("not json", "[]", '{"at": 1, "reason": "nope"}',
                 '{"at": "x", "reason": "stop"}', '{"at": true, "reason": "crash"}'):
        f.write_text(text, encoding="ascii")
        assert exitrecord.read(tmp_path) is None
    f.write_text(json.dumps({"at": 1, "reason": "crash", "detail": "x" * 9000}),
                 encoding="ascii")
    assert exitrecord.read(tmp_path) is None
    c = tmp_path / exitrecord.CLIENT_FILE
    c.write_text('{"at": 5, "reason": "relaunch", "detail": "3 errors"}', encoding="ascii")
    assert exitrecord.read_client(tmp_path) == {"at": 5.0, "pid": None,
                                                "reason": "relaunch", "detail": "3 errors"}
    c.write_text('{"at": 5, "reason": "supervisor-kill"}', encoding="ascii")
    assert exitrecord.read_client(tmp_path) is None


def test_main_thread_crash_writes_record(tmp_path, monkeypatch):
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    entry.install_crash_logging(logging.getLogger("al.test.crash3"), tmp_path)
    try:
        raise ValueError("main died")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    doc = _record(tmp_path)
    assert doc["reason"] == "crash" and doc["detail"] == "ValueError: main died"
    assert doc["pid"] == os.getpid()


def test_worker_thread_crash_writes_record(tmp_path, monkeypatch):
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    entry.install_crash_logging(logging.getLogger("al.test.crash4"), tmp_path)

    def boom():
        raise RuntimeError("tail exploded")
    t = threading.Thread(target=boom, name="al-tail")
    t.start()
    t.join()
    doc = _record(tmp_path)
    assert doc["reason"] == "crash"
    assert doc["detail"] == "thread al-tail: RuntimeError: tail exploded"

    def bye():
        sys.exit(0)
    (tmp_path / exitrecord.FILE).unlink()
    t = threading.Thread(target=bye, name="al-quiet")
    t.start()
    t.join()
    assert not (tmp_path / exitrecord.FILE).exists()  # SystemExit is not a crash


class _FakeServer:
    port = 0

    def serve_forever(self, poll_interval=0.5):
        return None

    def stop(self):
        return None


def _run_main(tmp_path, monkeypatch, action):
    """Run the real main() loop with a fake core and server; `action(ctx)`
    runs from the first core tick (ctx: runtime dir, signal handlers)."""
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("AL_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(entry, "setup_logging", lambda quiet: None)
    monkeypatch.setattr(entry, "start_token", lambda rt, tf, log=None: "tok")
    monkeypatch.setattr(entry, "serve", lambda *a, **k: _FakeServer())
    handlers = {}
    monkeypatch.setattr(signal, "signal", lambda sig, fn: handlers.__setitem__(sig, fn))
    ctx = {"runtime": runtime, "handlers": handlers, "ticks": 0}

    class FakeCore:
        port = 0

        def __init__(self, **kw):
            pass

        def consented(self):
            return False

        def tick_all(self, log):
            ctx["ticks"] += 1
            if ctx["ticks"] == 1:
                action(ctx)
            elif ctx["ticks"] > 20:
                raise AssertionError("main loop did not end")

        def close(self):
            pass

    monkeypatch.setattr(entry, "Core", FakeCore)
    runtime.mkdir(parents=True)
    assert entry.main(["--port", "0", "--quiet", "--no-tail"]) == 0
    return _record(runtime)


def test_stop_request_writes_stop(tmp_path, monkeypatch):
    def stop(c):
        (c["runtime"] / entry.STOP_FILE).write_text("stop\n", encoding="ascii")
    doc = _run_main(tmp_path, monkeypatch, stop)
    assert doc["reason"] == "stop" and doc["detail"] == entry.STOP_FILE
    assert doc["pid"] == os.getpid()


def test_hot_reload_restart_writes_reload(tmp_path, monkeypatch):
    def reload(c):
        (c["runtime"] / hotreload.RESTART_FILE).write_text("reload\n", encoding="ascii")
    doc = _run_main(tmp_path, monkeypatch, reload)
    assert doc["reason"] == "reload" and doc["detail"] == "code changed"


def test_signal_writes_signal(tmp_path, monkeypatch):
    sigterm = signal.SIGTERM
    seen = {}

    def fire(c):
        c["handlers"][sigterm](sigterm, None)
        seen.update(_record(c["runtime"]))  # written at once, in the handler
    doc = _run_main(tmp_path, monkeypatch, fire)
    assert seen["reason"] == "signal" and seen["detail"] == "SIGTERM"
    assert doc["reason"] == "signal" and doc["detail"] == "SIGTERM"


def test_keyboard_interrupt_writes_signal(tmp_path, monkeypatch):
    def interrupt(c):
        raise KeyboardInterrupt
    doc = _run_main(tmp_path, monkeypatch, interrupt)
    assert doc["reason"] == "signal" and doc["detail"] == "SIGINT"


def test_exit_reason_order():
    assert entry.exit_reason(False, False) == "stop"
    assert entry.exit_reason(True, False) == "signal"
    assert entry.exit_reason(True, True) == "reload"


def test_supervisor_kill_writes_record(tmp_path):
    entry.write_heartbeat(tmp_path / ka.HEARTBEAT_FILE, pid=4242, port=8960, now=800.0)
    killed = []

    def terminate(pid):
        killed.append(pid)
        return True
    sup = ka.Keepalive(tmp_path, 8960, launch=lambda: 4343, pid_alive=lambda p: True,
                       health=lambda: False, terminate=terminate,
                       now=lambda: 1000.0, created=lambda p: None)
    sup.step()
    assert killed == [4242]
    doc = _record(tmp_path)
    assert doc["reason"] == "supervisor-kill" and doc["pid"] == 4242
    assert doc["at"] == 1000.0 and doc["detail"] == "heartbeat 200 s old"
