"""Shared capture test helpers (F-147): the capture helper runner and a
real demo core fixture, used by tests/test_capture_helper.py and
tests/test_theme_setting.py.

A non-test module so no test file imports another test file
(tests/test_test_layout.py). The demo core is `python -m server.al --demo
<tracked synthetic fixture> --port 0` with its own sidecar under tmp_path;
it never targets the live core, config/local.json or the live Client.txt.
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ci_timing import ci_scale  # noqa: E402

from server.al import hello, paths, ports  # noqa: E402

HELPER = ROOT / "app" / "test" / "cdp" / "capture.mjs"
FIXTURE = ROOT / "tests" / "fixtures" / "demo"
NODE = shutil.which("node")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
URL_RE = re.compile(r"http://127\.0\.0\.1:(\d+)/#token=([0-9A-Za-z_\-]+)")
SCRATCH_RE = re.compile(r"^demo mode: fixture .+; scratch (.+)$")


def run_helper(args, preload=None, timeout=60):
    cmd = [NODE]
    if preload:
        cmd.append(f"--import={preload}")
    cmd += [str(HELPER), *args]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=ci_scale(timeout),
                       creationflags=NO_WINDOW)
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    doc = json.loads(lines[-1]) if lines else {}
    return r, doc


def _child_env(sidecar):
    env = {k: v for k, v in os.environ.items()
           if k not in (paths.RUNTIME_ENV, paths.SIDECAR_ENV, ports.PORT_ENV)}
    env[paths.SIDECAR_ENV] = str(sidecar)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


@pytest.fixture
def demo_core(tmp_path):
    """A real `python -m server.al --demo <fixture> --port 0` process."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.al", "--demo", str(FIXTURE), "--port", "0"],
        cwd=str(ROOT), env=_child_env(tmp_path / "sidecar"), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", creationflags=NO_WINDOW)
    lines = queue.Queue()
    seen = []

    def read():
        for line in proc.stdout:
            seen.append(line.rstrip("\n"))
            lines.put(line)

    threading.Thread(target=read, daemon=True).start()
    port = token = scratch = None
    deadline = time.monotonic() + ci_scale(60)
    try:
        while (port is None or scratch is None) and time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            m = URL_RE.search(line)
            if m:
                port, token = int(m.group(1)), m.group(2)
            m = SCRATCH_RE.match(line.strip())
            if m:
                scratch = Path(m.group(1))
        assert port and scratch, "no URL / scratch line: " + " | ".join(seen[-20:])
        assert port not in (ports.AL_PORT, ports.AL_DEV_PORT)

        def health():
            req = urllib.request.Request(f"http://{ports.LOOPBACK}:{port}/api/health",
                                         headers={"X-AL-Token": token})
            with hello.NO_PROXY_OPENER.open(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        while time.monotonic() < deadline:
            try:
                if health().get("tailing"):
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            raise AssertionError("the demo core never tailed: " + " | ".join(seen[-20:]))
        yield port, token
    finally:
        if scratch is not None and proc.poll() is None:
            (scratch / "runtime" / "stop.request").write_text("stop\n", encoding="ascii")
            try:
                proc.wait(ci_scale(30))
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait(30)
