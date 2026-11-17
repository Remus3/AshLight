"""A core that dies must leave a trace in core.log (pythonw has no stderr).

An unhandled exception in any thread is logged; the core also refreshes a
small heartbeat file so the time of a silent external kill is bounded.
"""

import json
import logging
import sys
import threading

from server.al import __main__ as entry


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
