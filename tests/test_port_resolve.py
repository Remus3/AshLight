"""TEST-CLEAN-CLONE: one port rule for the core, run.ps1, keepalive and the
overlay (env AL_PORT, then config/local.json "port", then 8960)."""

from pathlib import Path

from server.al import keepalive, ports

ROOT = Path(__file__).resolve().parents[1]


def test_default_is_the_block_base():
    assert ports.resolve({}, {}) == ports.AL_PORT == 8960
    assert ports.resolve({}, {"port": None}) == 8960


def test_env_wins_over_config():
    assert ports.resolve({"AL_PORT": "8963"}, {"port": 8962}) == 8963


def test_config_port_used_without_env():
    assert ports.resolve({}, {"port": 8962}) == 8962
    assert ports.resolve({"AL_PORT": ""}, {"port": "8964"}) == 8964


def test_out_of_block_or_junk_is_ignored():
    assert ports.resolve({"AL_PORT": "80"}, {}) == 8960
    assert ports.resolve({"AL_PORT": "x"}, {"port": 8961}) == 8961
    assert ports.resolve({}, {"port": True}) == 8960
    assert ports.resolve({}, {"port": 9000}) == 8960


def test_keepalive_parser_defers_to_resolve():
    assert keepalive.build_parser().parse_args([]).port is None


def test_run_ps1_uses_resolve_and_passes_the_port_on():
    text = (ROOT / "scripts" / "run.ps1").read_text(encoding="ascii")
    assert "ports.resolve(" in text and "ports.AL_PORT)" not in text
    assert "[int]$Port = 0" in text
    assert "AL_PORT = [string]$port" in text  # overlay + keepalive's core
    assert "'--port', [string]$port" in text


def test_overlay_reads_the_same_sources():
    text = (ROOT / "app" / "main.js").read_text(encoding="utf-8")
    assert "process.env.AL_PORT" in text and "cfg.port" in text


def test_out_of_block_logs_a_warning_and_falls_back(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="al"):
        assert ports.resolve({"AL_PORT": "8080"}, {"port": 65000}) == 8960
    msgs = [r.getMessage() for r in caplog.records]
    assert any("AL_PORT" in m and "8080" in m for m in msgs)
    assert any("config" in m and "65000" in m for m in msgs)


def test_in_block_and_unset_log_nothing(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="al"):
        assert ports.resolve({"AL_PORT": "8979"}, {}) == 8979
        assert ports.resolve({}, {}) == 8960
    assert caplog.records == []


def test_bind_stays_loopback():
    assert ports.LOOPBACK == "127.0.0.1"
    text = (ROOT / "server" / "al" / "http.py").read_text(encoding="ascii")
    assert "(ports.LOOPBACK, int(port))" in text


def test_oauth_redirect_ports_lie_in_the_block_and_differ_from_the_core():
    # TC-GGG-LISTENER (decision 0048): 8979 first, 8978 the fallback.
    redirect = ports.OAUTH_REDIRECT_PORTS
    assert tuple(redirect) == (8979, 8978)
    assert len(set(redirect)) == 2
    for port in redirect:
        assert ports.in_block(port)
        assert port != ports.AL_PORT
        assert port != ports.AL_DEV_PORT


# -- F-091 / P8-4: a bind failure names its cause; --port stays in the block

class _FakeServer:
    port = 0

    def serve_forever(self, poll_interval=0.5):
        return None

    def stop(self):
        return None


def _entry_env(tmp_path, monkeypatch):
    """main() with its runtime and sidecar under tmp_path, no logging setup,
    a fixed token and a fake core whose first tick asks for a stop; returns
    (entry module, runtime dir)."""
    import sys
    import threading

    from server.al import __main__ as entry
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("AL_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(entry, "setup_logging", lambda quiet: None)
    monkeypatch.setattr(entry, "start_token", lambda rt, tf, log=None: "tok")
    ticks = []

    class FakeCore:
        port = 0

        def __init__(self, **kw):
            ticks.clear()

        def consented(self):
            return False

        def tick_all(self, log):
            ticks.append(1)
            if len(ticks) == 1:
                (runtime / entry.STOP_FILE).write_text("stop\n", encoding="ascii")
            elif len(ticks) > 20:
                raise AssertionError("main loop did not end")

        def close(self):
            pass

    monkeypatch.setattr(entry, "Core", FakeCore)
    return entry, runtime


def _taken_serve(port):
    """A serve() stand-in that tries the real bind of 127.0.0.1:port (held
    by the test) and raises the OS error it gets."""
    import socket

    def serve(*a, **k):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((ports.LOOPBACK, port))
        finally:
            s.close()
        raise AssertionError("the held port was bound twice")
    return serve


def _plain_listener():
    """A plain socket on an OS-picked loopback port that answers one
    request with a non-AshLight HTTP reply. Returns (port, close)."""
    import socket
    import threading

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind((ports.LOOPBACK, 0))
    srv.listen(4)
    srv.settimeout(5)

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            try:
                conn.recv(4096)
                conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
            except OSError:
                pass

    t = threading.Thread(target=run, daemon=True)
    t.start()

    def close():
        srv.close()
        t.join(5)
    return srv.getsockname()[1], close


def test_plain_socket_on_the_port_gives_exit_2_and_error_file(tmp_path, monkeypatch,
                                                              capsys):
    import errno
    import json

    from server.al import exitrecord
    entry, runtime = _entry_env(tmp_path, monkeypatch)
    held, close = _plain_listener()
    try:
        assert entry.probe_core(held, timeout=5) is False
    finally:
        close()
    assert entry.probe_core(0) is False  # an OS-picked port is never probed
    held, close = _plain_listener()
    real_probe = entry.probe_core
    probed = []

    def probe(port, timeout=entry.PROBE_TIMEOUT_S):
        probed.append(port)
        return real_probe(held, timeout=5)  # the port the test holds, never AL_PORT

    monkeypatch.setattr(entry, "serve", _taken_serve(held))
    monkeypatch.setattr(entry, "probe_core", probe)
    try:
        assert entry.main(["--port", str(ports.AL_PORT), "--quiet", "--no-tail"]) == 2
    finally:
        close()
    assert probed == [ports.AL_PORT]  # one probe
    doc = json.loads((runtime / entry.START_ERROR_FILE).read_text(encoding="ascii"))
    assert doc["reason"] == "port_in_use" and doc["port"] == ports.AL_PORT
    assert doc["errno"] in (10048, errno.EADDRINUSE)
    assert f"{ports.PORT_BLOCK[0]}-{ports.PORT_BLOCK[1]}" in doc["fix"]
    assert str(ports.AL_PORT) in doc["fix"] and "\\" not in doc["fix"]
    assert doc["fix"] in capsys.readouterr().err
    rec = json.loads((runtime / exitrecord.FILE).read_text(encoding="ascii"))
    assert rec["reason"] == "stop" and "could not be bound" in rec["detail"]
    # the other cause words name the same one fix
    refused = entry.bind_failure(8962, OSError(errno.EACCES, "denied"))
    assert refused["reason"] == "port_refused" and "8962" in refused["fix"]
    other = entry.bind_failure(8962, OSError(errno.ENOENT, "odd"))
    assert other["reason"] == "bind_error" and ports.PORT_ENV in other["fix"]


def test_answering_ashlight_core_reads_already_running(tmp_path, monkeypatch, capsys):
    import json
    import threading

    from server.al import exitrecord
    from server.al.core import Core
    from server.al.http import serve
    entry, runtime = _entry_env(tmp_path, monkeypatch)
    real_probe = entry.probe_core
    core = Core(runtime=tmp_path / "live", tail=False)
    srv = serve(core, "secret-token", port=0)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    try:
        port = srv.server_address[1]
        assert real_probe(port, timeout=5) is True  # 401 + token required + CSP
        monkeypatch.setattr(entry, "serve", _taken_serve(port))
        monkeypatch.setattr(entry, "probe_core",
                            lambda p, timeout=1.0: real_probe(port, timeout=5))
        assert entry.main(["--port", str(ports.AL_PORT), "--quiet", "--no-tail"]) == 2
    finally:
        srv.stop()
        core.close()
    assert not (runtime / entry.START_ERROR_FILE).exists()
    assert "already running" in capsys.readouterr().err
    rec = json.loads((runtime / exitrecord.FILE).read_text(encoding="ascii"))
    assert rec["detail"] == "already running"


def test_port_flag_outside_block_is_refused_zero_allowed(tmp_path, monkeypatch, capsys):
    lo, hi = ports.PORT_BLOCK
    for ok in (None, 0, lo, hi, ports.AL_DEV_PORT):
        assert ports.flag_refusal(ok) is None
    for bad in (80, lo - 1, hi + 1, 9000, -1, 65535):
        text = ports.flag_refusal(bad)
        assert text and f"{lo}-{hi}" in text and f"--port {bad} " in text
    assert ports.flag_refusal(True)  # a bool is not a port
    entry, runtime = _entry_env(tmp_path, monkeypatch)
    served = []
    monkeypatch.setattr(entry, "serve",
                        lambda *a, **k: served.append(k) or _FakeServer())
    for bad in ("80", str(lo - 1), str(hi + 1), "9000", "-1"):
        assert entry.main(["--port=" + bad, "--quiet", "--no-tail"]) == 2
        err = capsys.readouterr().err
        assert f"--port {bad} is outside" in err and f"{lo}-{hi}" in err
    assert served == [] and list(runtime.iterdir()) == []  # refused before any work
    assert entry.main(["--port", "0", "--quiet", "--no-tail"]) == 0
    assert served[-1]["port"] == 0


def test_check_site_has_no_port_literal():
    text = (ROOT / "server" / "al" / "__main__.py").read_text(encoding="ascii")
    body = text[text.index("def main("):]
    assert "ports.flag_refusal(args.port)" in body
    assert "8960" not in body and "8979" not in body


def test_error_file_is_cleared_by_a_good_start(tmp_path, monkeypatch):
    entry, runtime = _entry_env(tmp_path, monkeypatch)
    stale = runtime / entry.START_ERROR_FILE
    stale.write_text('{"reason": "port_in_use"}\n', encoding="ascii")
    monkeypatch.setattr(entry, "serve", lambda *a, **k: _FakeServer())
    assert entry.main(["--port", "0", "--quiet", "--no-tail"]) == 0
    assert not stale.exists()
