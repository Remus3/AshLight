"""RUN-METRICS-PROBE (finding F-032, decision 0067): python -m server.al.probe.

A real core on a tmp runtime (AL_RUNTIME_DIR) and a tmp sidecar
(AL_SIDECAR_ROOT), served on a leased test port (TEST-PORT-LEASE), never
8960. The probe prints one line per item and exits 0 while the core is
live, 1 once it is stopped; no line holds the token, a path or a pid.
"""

import io
import os
import re
import subprocess
import sys
import threading

import pytest

from server.al import http as al_http
from server.al import metrics, ports, probe
from server.al.core import Core
from srcpaths import ROOT
from tc_live_util import leased_port  # noqa: F401 (a fixture)

TOKEN = "probe-test-token-0123456789abcdef"


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "token").write_text(TOKEN + "\n", encoding="ascii")
    monkeypatch.setenv("AL_RUNTIME_DIR", str(rt))
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))
    monkeypatch.delenv("AL_PORT", raising=False)
    metrics.reset()
    yield rt
    metrics.reset()


@pytest.fixture
def live_core(tmp_path, runtime, leased_port):  # noqa: F811
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=runtime, log_path=str(log), tail=False)
    srv = al_http.serve(core, TOKEN, port=leased_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    state = {"srv": srv, "core": core, "port": srv.port, "log": log}

    def stop():
        if state["srv"] is not None:
            state["srv"].shutdown()
            state["srv"].server_close()
            t.join(5)
            state["srv"] = None
            core.close()

    state["stop"] = stop
    try:
        yield state
    finally:
        stop()


def run_probe(port):
    out = io.StringIO()
    rc = probe.main(["--port", str(port), "--timeout", "3"], out=out)
    return rc, out.getvalue()


def test_probe_exits_0_live_and_1_stopped(live_core):
    port = live_core["port"]
    assert port != ports.AL_PORT
    rc, text = run_probe(port)
    assert rc == 0, text
    lines = text.splitlines()
    keys = [ln.split(":", 1)[0] for ln in lines]
    assert lines[0] == "core: live"
    for key in ("build", "uptime", "reader", "feed", "calc", "fetch"):
        assert key in keys, text
    # one line per item: no key printed twice, every line "key: value"
    assert len(keys) == len(set(keys))
    assert all(re.fullmatch(r"[a-z]+: \S.*", ln) for ln in lines), text

    live_core["stop"]()
    rc, text = run_probe(port)
    assert rc == 1
    assert text.splitlines()[0] == "core: stopped"


def test_probe_with_no_token_file_is_stopped(runtime, leased_port):  # noqa: F811
    (runtime / "token").unlink()
    rc, text = run_probe(leased_port)
    assert rc == 1
    assert text.splitlines()[0] == "core: stopped"


def test_probe_command_line_stopped_core_exits_1(runtime, leased_port):  # noqa: F811
    env = dict(os.environ)
    proc = subprocess.run([sys.executable, "-m", "server.al.probe", "--port",
                           str(leased_port), "--timeout", "2"],
                          cwd=str(ROOT), env=env, capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode == 1, proc.stderr
    assert proc.stdout.splitlines()[0] == "core: stopped"


def test_probe_output_holds_no_token_path_or_pid(live_core, tmp_path, runtime):
    rc, text = run_probe(live_core["port"])
    assert rc == 0, text
    assert TOKEN not in text
    for p in (str(tmp_path), str(runtime), str(live_core["log"]), str(ROOT)):
        assert p not in text
        assert p.replace("\\", "/") not in text
    assert "\\" not in text and "/" not in text.replace(" / ", "")
    assert not re.search(r"\b[A-Za-z]:", text)
    assert "pid" not in text.lower()
    assert not re.search(rf"\b{os.getpid()}\b", text)
    assert text.isascii()


def test_probe_never_prints_a_bad_value():
    # a body value that is not a plain number / word is shown as "?"
    drive = chr(ord("A") + 2) + ":"  # built, so no drive literal is tracked
    doc = {"uptime_s": drive + "\\x", "tailer": {"running": True, "lines": "tok"},
           "counters": {"calc.starts": 2, "fetch/odd name": 3}}
    out = io.StringIO()
    probe.render({"ok": True, "build": "1.2.3+abc " + drive + "\\evil",
                  "mode": "checkout"}, doc, out)
    text = out.getvalue()
    assert drive not in text and "\\" not in text and "tok" not in text
    assert "calc: starts=2" in text
    assert "odd" not in text
