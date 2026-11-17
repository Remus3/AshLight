"""TEST-COVER: tests for the worst in-process gaps in
docs/audit/test-coverage.md - the core entry point helpers
(server/al/__main__.py), the process registry's stop and CLI
(server/al/procs.py), the supervisor's launcher and CLI
(server/al/keepalive.py) and the real one-hop web transport
(server/al/webfetch.py, against a loopback server only).

Everything runs on tmp runtimes; no live core, supervisor, overlay, game or
network is reached.
"""

import http.server
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from server.al import __main__ as entry
from server.al import keepalive as ka
from server.al import paths, ports, procs, webfetch

ROOT = Path(__file__).resolve().parents[1]
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WIN = pytest.mark.skipif(sys.platform != "win32", reason="Windows process APIs")


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    rt = tmp_path / "runtime"
    rt.mkdir()
    monkeypatch.setenv(paths.RUNTIME_ENV, str(rt))
    monkeypatch.setenv(paths.SIDECAR_ENV, str(tmp_path / "AL"))
    monkeypatch.setenv(procs.ELECTRON_DIR_ENV, str(tmp_path / "no-electron"))
    return rt


def _sleeper():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=FLAGS)
    time.sleep(0.3)
    return p


# ------------------------------------------------------------ __main__.py

def test_entry_parser_defaults_and_flags():
    a = entry.build_parser().parse_args([])
    assert a.port is None and not a.no_tail and not a.quiet  # ports.resolve at start
    a = entry.build_parser().parse_args(["--port", "8961", "--no-tail", "--quiet",
                                         "--character", "X"])
    assert (a.port, a.no_tail, a.quiet, a.character) == (8961, True, True, "X")


@pytest.mark.parametrize("value,want", [(None, entry.HEARTBEAT_S), ("2.5", 2.5),
                                        ("0", 0.1), ("junk", entry.HEARTBEAT_S)])
def test_heartbeat_interval_from_env(monkeypatch, value, want):
    if value is None:
        monkeypatch.delenv("AL_HEARTBEAT_S", raising=False)
    else:
        monkeypatch.setenv("AL_HEARTBEAT_S", value)
    assert entry._heartbeat_s() == want


def test_stop_request_helpers(tmp_path):
    p = tmp_path / "stop.request"
    assert not entry.stop_requested(p)
    entry.clear_stop_request(p)  # missing file: no error
    p.write_text("stop", encoding="ascii")
    assert entry.stop_requested(p)
    entry.clear_stop_request(p)
    assert not p.exists()


def test_crash_logging_hooks_log_and_ignore_system_exit():
    records = []

    class H(logging.Handler):
        def emit(self, record):
            records.append(record)

    log = logging.getLogger("al-test-crash")
    log.addHandler(H())
    old_sys, old_thread = sys.excepthook, threading.excepthook
    try:
        entry.install_crash_logging(log)
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        t = threading.Thread(target=lambda: (_ for _ in ()).throw(ValueError("bad")),
                             name="al-worker")
        t.start()
        t.join()
        t2 = threading.Thread(target=sys.exit)
        t2.start()
        t2.join()
    finally:
        sys.excepthook, threading.excepthook = old_sys, old_thread
    msgs = [r.getMessage() for r in records]
    assert any("core exiting" in m for m in msgs)
    assert any("thread al-worker" in m for m in msgs)
    assert len(records) == 2  # SystemExit in a thread is not an error


def test_write_heartbeat_is_atomic_json(tmp_path):
    p = tmp_path / "core.alive"
    entry.write_heartbeat(p, 1234, 8961, now=5.0, created=99)
    assert json.loads(p.read_text("ascii")) == {"pid": 1234, "port": 8961,
                                                "updated": 5.0, "created": 99}
    assert ka.read_heartbeat(p)["created"] == 99
    assert not Path(str(p) + ".tmp").exists()


# --------------------------------------------------------------- procs.py

def test_procs_cli_status_and_plan_on_empty_runtime(runtime, capsys):
    assert procs.main(["status"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert not any(st[c]["live"] for c in procs.COMPONENTS)
    assert procs.main(["plan", "--no-overlay"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["start"] == ["core", "supervisor"]
    assert procs.main(["plan", "--overlay-missing"]) == 0
    assert json.loads(capsys.readouterr().out)["start"] == ["core", "supervisor"]


def test_procs_stop_with_nothing_running(runtime, capsys):
    (runtime / procs.OVERLAY_PID_FILE).write_text("{}", encoding="ascii")
    assert procs.main(["stop", "--wait", "0.2"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep == {"supervisor": "not running", "overlay": "not running", "left": []}
    assert not (runtime / procs.OVERLAY_PID_FILE).exists()


def test_procs_record_overlay_of_a_dead_pid_fails(runtime):
    assert procs.main(["record-overlay", "999999"]) == 1


@WIN
def test_procs_stop_forces_a_recorded_supervisor_that_stays(runtime):
    p = _sleeper()
    try:
        (runtime / ka.STATE_FILE).write_text(json.dumps(
            {"pid": p.pid, "created": ka.process_created(p.pid)}), encoding="ascii")
        assert procs.supervisor_pid(runtime) == p.pid
        rep = procs.stop(runtime, wait_s=0.3)
        assert rep["supervisor"] == "stopped (forced)"
        assert p.wait(10) is not None
    finally:
        p.kill()
        p.wait(10)


@WIN
def test_procs_never_terminates_a_foreign_image(runtime):
    p = _sleeper()
    try:
        assert procs._terminate(p.pid, "electron") is False
        assert p.poll() is None
    finally:
        p.kill()
        p.wait(10)


def test_wait_gone_returns_what_is_left():
    t = [0.0]
    left = procs._wait_gone([999999], 1.0, sleep=lambda s: t.__setitem__(0, t[0] + s),
                            now=lambda: t[0])
    assert left == []


# ------------------------------------------------------------ keepalive.py

def test_core_command_targets_the_core_module():
    cmd = ka.core_command(8961, ["--no-tail"])
    assert cmd[1:] == ["-m", "server.al", "--quiet", "--port", "8961", "--no-tail"]
    assert Path(cmd[0]).name.lower().startswith("python")


def test_launcher_starts_and_reaps(tmp_path):
    launch = ka._Launcher([sys.executable, "-c", "pass"])
    pid1 = launch()
    launch.child.wait(30)
    pid2 = launch()  # polls (reaps) the previous child first
    launch.child.wait(30)
    assert pid1 > 0 and pid2 > 0


def test_file_logger_writes_ascii_lines(tmp_path):
    log = ka._file_logger(tmp_path / "logs" / "keepalive.log")
    log("core launched \u00e9")
    text = (tmp_path / "logs" / "keepalive.log").read_bytes().decode("ascii")
    assert text.endswith("core launched ?\n") and "keepalive[" in text


def test_keepalive_main_exits_when_another_holds_the_lock(runtime):
    held = ka.acquire_lock(runtime)
    try:
        assert ka.main(["--runtime", str(runtime), "--port", "8961"]) == 0
    finally:
        ka.release_lock(held)


def test_keepalive_main_gives_up_and_records_it(runtime, monkeypatch):
    # a supervisor whose launches all fail gives up (rc 3) without a real core
    monkeypatch.setattr(ka, "_Launcher", lambda cmd: (lambda: (_ for _ in ()).throw(
        OSError("no python"))))
    rc = ka.main(["--runtime", str(runtime), "--port", "8961", "--poll", "0",
                  "--backoff", "0", "--cap", "2"])
    assert rc == 3
    assert json.loads((runtime / ka.STATE_FILE).read_text("ascii"))["status"] == "gave-up"


def test_health_check_without_token_is_false(tmp_path):
    assert ka.health_check(tmp_path, 1) is False


# ------------------------------------------------------------- webfetch.py

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/big":
            body = b"x" * 5000
            self.send_response(200)
        elif self.path == "/moved":
            body = b""
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
        else:
            body = b'{"ok": true}'
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def loopback():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.mark.server
def test_transport_one_hop_size_cap_and_errors(loopback):
    fetch = webfetch.make_transport(max_bytes=1000, timeout=5)
    status, headers, body = fetch("GET", loopback + "/ok", {"User-Agent": "t"})
    assert status == 200 and json.loads(body) == {"ok": True}
    assert webfetch.header(headers, "content-length") == str(len(body))
    status, headers, _ = fetch("GET", loopback + "/moved", {})
    assert status == 302 and webfetch.header(headers, "LOCATION").endswith("/elsewhere")
    with pytest.raises(webfetch.FetchError, match="too large"):
        fetch("GET", loopback + "/big", {})
    with pytest.raises(webfetch.FetchError, match="network"):
        fetch("GET", "http://127.0.0.1:1/", {})
